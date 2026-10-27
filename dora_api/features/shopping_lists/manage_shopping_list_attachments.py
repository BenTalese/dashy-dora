"""FU-334 — add / delete / serve-bytes for shopping-list receipt attachments.

Three endpoints, all under `/api/shopping-lists/<list_id>/attachments`:

  POST   /                   → add a new attachment from a data URL
  DELETE /<attachment_id>    → remove a single attachment
  GET    /<attachment_id>    → bytes endpoint (raw image with Content-Type)

The bytes endpoint mirrors `/recipes/<id>/step-images/<image_id>`: the
stored data URL is decoded by `infrastructure/data_url.py`, which serves
only raster image types.

The lifecycle gate is enforced here (no attaching to a `draft` list); the
access helper enforces shape + cap. Unlike step images, receipts are
add/delete one at a time — there is no wholesale replace.
"""
import logging
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.shopping_list import (
    SHOPPING_LIST_STATUS_DRAFT, ShoppingList)
from dora_api.features.routers import SHOPPING_LIST_ROUTER
from dora_api.features.shopping_lists.shopping_list_attachment_access import (
    MAX_ATTACHMENT_BYTES, add_attachment, delete_attachment,
    get_attachment_bytes)
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  no_content, not_found, ok)
from dora_api.infrastructure.data_url import data_url_response
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


# ───── Add ────────────────────────────────────────────────────────────────

class AddShoppingListAttachmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # `data:image/<type>;base64,...` string. The client (processImageFile)
    # already validated MIME + resized + re-encoded; the server validates
    # shape + size as defence-in-depth.
    image_data_url: str = Field(min_length=1, max_length=MAX_ATTACHMENT_BYTES)


@dataclass(slots=True)
class AddShoppingListAttachmentResponse:
    not_found: bool = False
    draft_rejected: bool = False
    invalid_payload: str | None = None
    attachment_id: UUID | None = None


class AddShoppingListAttachmentHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(
        self,
        request: AddShoppingListAttachmentRequest,
        shopping_list_id: UUID,
    ) -> AddShoppingListAttachmentResponse:
        lst: ShoppingList | None = self.repository.get(ShoppingList).by_id(
            shopping_list_id
        )
        if lst is None:
            return AddShoppingListAttachmentResponse(not_found=True)
        if lst.status == SHOPPING_LIST_STATUS_DRAFT:
            return AddShoppingListAttachmentResponse(draft_rejected=True)

        try:
            attachment_id = add_attachment(
                self.repository, shopping_list_id, request.image_data_url
            )
        except ValueError as exc:
            return AddShoppingListAttachmentResponse(invalid_payload=str(exc))

        self.repository.save_changes()
        return AddShoppingListAttachmentResponse(attachment_id=attachment_id)


@SHOPPING_LIST_ROUTER.route(
    "/<uuid:shopping_list_id>/attachments", methods=["POST"]
)
@has_request_body(AddShoppingListAttachmentRequest)
def add_shopping_list_attachment(shopping_list_id: UUID):
    _Request: AddShoppingListAttachmentRequest = get_request_body()
    _Response = AddShoppingListAttachmentHandler(SqlAlchemyRepository()).handle(
        _Request, shopping_list_id,
    )
    if _Response.not_found:
        return not_found("ShoppingList", shopping_list_id)
    if _Response.draft_rejected:
        return business_rule_violation(
            "Receipts can only be attached to a list that's being shopped or "
            "finished. Start shopping the list first."
        )
    if _Response.invalid_payload:
        return business_rule_violation(_Response.invalid_payload)
    _LOGGER.info(
        "Added attachment %s to shopping list %s",
        _Response.attachment_id, shopping_list_id,
    )
    return ok({"attachment_id": _Response.attachment_id})


# ───── Delete ─────────────────────────────────────────────────────────────

@dataclass(slots=True)
class DeleteShoppingListAttachmentResponse:
    not_found: bool = False


class DeleteShoppingListAttachmentHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(
        self, shopping_list_id: UUID, attachment_id: UUID,
    ) -> DeleteShoppingListAttachmentResponse:
        lst: ShoppingList | None = self.repository.get(ShoppingList).by_id(
            shopping_list_id
        )
        if lst is None:
            return DeleteShoppingListAttachmentResponse(not_found=True)
        removed = delete_attachment(self.repository, shopping_list_id, attachment_id)
        if not removed:
            return DeleteShoppingListAttachmentResponse(not_found=True)
        self.repository.save_changes()
        return DeleteShoppingListAttachmentResponse()


@SHOPPING_LIST_ROUTER.route(
    "/<uuid:shopping_list_id>/attachments/<uuid:attachment_id>", methods=["DELETE"]
)
def delete_shopping_list_attachment(
    shopping_list_id: UUID, attachment_id: UUID,
):
    _Response = DeleteShoppingListAttachmentHandler(SqlAlchemyRepository()).handle(
        shopping_list_id, attachment_id,
    )
    if _Response.not_found:
        return not_found("ShoppingListAttachment", attachment_id)
    _LOGGER.info(
        "Deleted attachment %s from shopping list %s",
        attachment_id, shopping_list_id,
    )
    return no_content()


# ───── Bytes ──────────────────────────────────────────────────────────────

@SHOPPING_LIST_ROUTER.route(
    "/<uuid:shopping_list_id>/attachments/<uuid:attachment_id>", methods=["GET"]
)
def get_shopping_list_attachment_bytes(shopping_list_id: UUID, attachment_id: UUID):
    return data_url_response(
        get_attachment_bytes(SqlAlchemyRepository(), shopping_list_id, attachment_id),
        lambda: not_found("ShoppingListAttachment", attachment_id),
    )
