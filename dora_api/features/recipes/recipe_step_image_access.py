"""PROPOSAL_RECIPE_IMAGE_STEPS — read/write helpers for image-mode steps.

A recipe in `steps_mode = 'image'` owns 0..N `RecipeStepImage` rows ordered
by `sequence`. Each row stores the same `data:image/...;base64,...` UTF-8
bytes shape as `Recipe.image` (the client picks → resizes → emits a data
URL; the server stores the encoded bytes; the bytes endpoint decodes +
serves raw).

`replace_step_images_for_recipe` is the single write path: wipe + re-create
from the request (mirrors `replace_steps_for_recipe`). A PATCH may name an
already-saved image by its id instead of re-uploading it;
`resolve_step_image_entries` turns those ids back into their stored bytes
*before* the wipe so they survive (in their new position).
"""
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select

from dora_api.app import db

# Soft cap mirrored on the client. The hard guard lives here so the API
# rejects a runaway client payload before allocating bytes.
MAX_STEP_IMAGES_PER_RECIPE = 20


@dataclass(slots=True)
class StepImageWrite:
    """Wire shape for a single step image on create/update.

    `image_data_url` is the encoded `data:image/<jpeg|png|webp>;base64,...`
    string the client uploaded. None of the call sites need a separate MIME
    field — the format lives inside the data URL, same as Recipe.image.
    """
    sequence: int
    image_data_url: str


def _step_image_table():
    return db.metadata.tables["RecipeStepImage"]


def get_step_image_metadata_for_recipe(recipe_id: UUID) -> list[dict]:
    """Return ordered {id, sequence} dicts for the detail DTO. Bytes are
    never inlined — the SPA loads each image via the dedicated bytes
    endpoint so list/detail JSON stays slim."""
    table = _step_image_table()
    rows = db.session.execute(
        select(table.c.id, table.c.sequence)
        .where(table.c.recipe_id == recipe_id)
        .order_by(table.c.sequence)
    ).all()
    return [{"id": row[0], "sequence": row[1]} for row in rows]


def get_step_image_bytes(recipe_id: UUID, image_id: UUID) -> bytes | None:
    """Load the encoded data-URL bytes for a single step image. Returns
    None when the image isn't on this recipe (or doesn't exist)."""
    table = _step_image_table()
    row = db.session.execute(
        select(table.c.image)
        .where(table.c.id == image_id)
        .where(table.c.recipe_id == recipe_id)
    ).first()
    return row[0] if row else None


class UnknownStepImageId(ValueError):
    """A PATCH entry named a step-image id that isn't one of this recipe's
    saved images."""


def resolve_step_image_entries(
    recipe_id: UUID, entries: list[str]
) -> list[StepImageWrite]:
    """Map the PATCH `step_images` list to ordered writes. Each entry is
    either a `data:image/...` data URL (new bytes) or the id of an image this
    recipe already has (keep its bytes). Anything that isn't a valid UUID is
    passed through as a data URL so `_validate_writes` reports it.

    Raises `UnknownStepImageId` for a well-formed id that doesn't belong to
    this recipe.
    """
    table = _step_image_table()
    existing = {
        str(row[0]): row[1]
        for row in db.session.execute(
            select(table.c.id, table.c.image).where(table.c.recipe_id == recipe_id)
        ).all()
    }
    writes: list[StepImageWrite] = []
    for sequence, entry in enumerate(entries):
        if entry.startswith("data:"):
            writes.append(StepImageWrite(sequence=sequence, image_data_url=entry))
            continue
        try:
            image_id = str(UUID(entry))
        except ValueError:
            writes.append(StepImageWrite(sequence=sequence, image_data_url=entry))
            continue
        if image_id not in existing:
            raise UnknownStepImageId(
                f"Step image '{entry}' is not one of this recipe's images."
            )
        writes.append(StepImageWrite(
            sequence=sequence,
            image_data_url=existing[image_id].decode("utf-8"),
        ))
    return writes


def _validate_writes(writes: list[StepImageWrite]) -> None:
    if len(writes) > MAX_STEP_IMAGES_PER_RECIPE:
        raise ValueError(
            f"Too many step images ({len(writes)}); the cap is "
            f"{MAX_STEP_IMAGES_PER_RECIPE} per recipe."
        )
    for write in writes:
        if not (write.image_data_url or "").startswith("data:image/"):
            raise ValueError(
                "Each step image must be a 'data:image/<type>;base64,...' "
                "data URL."
            )


def replace_step_images_for_recipe(
    recipe_id: UUID, writes: list[StepImageWrite]
) -> None:
    """Wipe existing step images and re-insert from `writes`. Empty list
    clears all rows; the recipe still has `steps_mode = 'image'` (the
    endpoint validates that the mode + payload agree).
    """
    _validate_writes(writes)

    table = _step_image_table()
    db.session.execute(table.delete().where(table.c.recipe_id == recipe_id))

    if not writes:
        return

    db.session.execute(table.insert(), [
        {
            "id": uuid4(),
            "recipe_id": recipe_id,
            "sequence": write.sequence,
            "image": write.image_data_url.encode("utf-8"),
        }
        for write in writes
    ])
