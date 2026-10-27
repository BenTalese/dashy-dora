"""FU-334 — read/write helpers for shopping-list receipt attachments.

A shopping list (status='shopping' or 'done') owns 0..N
`ShoppingListAttachment` rows ordered by `sequence`. Each row stores
the same `data:image/...;base64,...` UTF-8 bytes shape as Recipe.image /
RecipeStepImage (client picks → `processImageFile` → data URL; server
stores encoded bytes; bytes endpoint decodes + serves raw).

Unlike step images, receipts are mutated **one at a time** (tap to add,
tap trash to delete) — there is no wholesale replace. So this module
exposes individual `add` / `delete` helpers rather than the recipe's
`replace_step_images_for_recipe`.

Pure record-keeping — no OCR, no parsing, no auto-matching to lines.
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select

from dora_api.app import db
from dora_api.domain.entities.shopping_list_attachment import \
    ShoppingListAttachment
from dora_api.infrastructure.ports import Repository
from dora_api.persistence.field import EntityField


# Soft cap. Receipts can legitimately span several photos (long till
# rolls, two-store shops), but anything beyond this is almost certainly
# accidental. Mirrored on the client.
MAX_ATTACHMENTS_PER_LIST = 20

# Hard guard on encoded size. processImageFile caps at ~1600px JPEG q0.85
# which lands well under 1MB encoded; this is defence-in-depth against a
# runaway client payload. The data-URL prefix adds ~30 bytes of overhead.
MAX_ATTACHMENT_BYTES = 3 * 1024 * 1024


def _on_list(shopping_list_id: UUID):
    return EntityField(ShoppingListAttachment, ShoppingListAttachment.Fields.SHOPPING_LIST_ID).eq(
        shopping_list_id
    )


# R-005 carve-out: the two column-only reads below select `id` / `sequence`
# through Core because loading the entities would pull every image blob
# (up to 3 MB each) just to list or number them.

def get_attachment_metadata_for_list(shopping_list_id: UUID) -> list[dict]:
    """Return ordered {id, sequence} dicts for the detail DTO. Bytes are
    never inlined — the SPA loads each image via the dedicated bytes
    endpoint so detail JSON stays slim."""
    table = db.metadata.tables["ShoppingListAttachment"]
    rows = db.session.execute(
        select(table.c.id, table.c.sequence)
        .where(table.c.shopping_list_id == shopping_list_id)
        .order_by(table.c.sequence)
    ).all()
    return [{"id": row[0], "sequence": row[1]} for row in rows]


def _next_sequence(shopping_list_id: UUID) -> int:
    table = db.metadata.tables["ShoppingListAttachment"]
    current_max = db.session.execute(
        select(func.max(table.c.sequence))
        .where(table.c.shopping_list_id == shopping_list_id)
    ).scalar()
    return (current_max + 1) if current_max is not None else 0


def _find(repository: Repository, shopping_list_id: UUID, attachment_id: UUID):
    return repository.get(ShoppingListAttachment).one(
        EntityField(ShoppingListAttachment, "id").eq(attachment_id) & _on_list(shopping_list_id)
    )


def get_attachment_bytes(
    repository: Repository, shopping_list_id: UUID, attachment_id: UUID,
) -> bytes | None:
    """The encoded data-URL bytes for one attachment, or None when it isn't
    on this list (or doesn't exist)."""
    attachment = _find(repository, shopping_list_id, attachment_id)
    return attachment.image if attachment is not None else None


def _validate_data_url(image_data_url: str) -> None:
    if not (image_data_url or "").startswith("data:image/"):
        raise ValueError(
            "Attachment must be a 'data:image/<type>;base64,...' data URL."
        )
    if len(image_data_url) > MAX_ATTACHMENT_BYTES:
        raise ValueError(
            f"Attachment is too large (max {MAX_ATTACHMENT_BYTES // (1024 * 1024)}MB encoded)."
        )


def add_attachment(repository: Repository, shopping_list_id: UUID, image_data_url: str) -> UUID:
    """Append a new attachment, returning its id. Raises ValueError on a
    malformed data URL, oversize payload, or when the list is already at
    MAX_ATTACHMENTS_PER_LIST. The lifecycle gate (draft lists rejected)
    lives in the handler — this helper only enforces shape + cap."""
    _validate_data_url(image_data_url)
    if repository.get(ShoppingListAttachment).count(_on_list(shopping_list_id)) >= MAX_ATTACHMENTS_PER_LIST:
        raise ValueError(
            f"Too many attachments (cap is {MAX_ATTACHMENTS_PER_LIST} per list)."
        )
    attachment = ShoppingListAttachment(
        shopping_list_id=shopping_list_id,
        sequence=_next_sequence(shopping_list_id),
        image=image_data_url.encode("utf-8"),
        created_at=datetime.now(timezone.utc),
    )
    repository.add(attachment)
    return attachment.id


def delete_attachment(repository: Repository, shopping_list_id: UUID, attachment_id: UUID) -> bool:
    """Delete a single attachment. Returns True when a row was removed,
    False when the id wasn't found on this list."""
    attachment = _find(repository, shopping_list_id, attachment_id)
    if attachment is None:
        return False
    repository.remove(attachment)
    return True
