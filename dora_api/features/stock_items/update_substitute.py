"""FU-034 — PATCH endpoint for editing an existing substitute pair's
metadata (notes + structured ratio).

Mirrors `add_substitute.py`'s shape and uses the same shared validation /
direction-flip helpers in `dora_api.features.substitutes.metadata` so
the rules live in one place (R-003).

Idempotent — re-sending the same body produces the same row.
"""
import logging
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.app import db
from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.features.substitutes.canonical import canonical_pair
from dora_api.features.substitutes.metadata import (
    SubstituteMetadata, build_metadata, validate_metadata,
)
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  no_content, not_found)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


class UpdateSubstituteRequest(BaseModel):
    """Whole-metadata replace — any field omitted is treated as "clear it".

    Rationale: this keeps the API simple (one body shape, no partial
    semantics) and matches the UI's "edit and save" flow where the user
    holds the whole bundle in their head. Direction is the caller's
    perspective — `qty_in` is "this stock item", `qty_out` is "the
    substitute" — the handler reorients into canonical storage."""
    model_config = ConfigDict(extra="forbid")

    notes: str | None = Field(default=None, max_length=255)
    ratio_quantity_in: float | None = None
    ratio_unit_in: str | None = Field(default=None, max_length=32)
    ratio_quantity_out: float | None = None
    ratio_unit_out: str | None = Field(default=None, max_length=32)


@dataclass(slots=True)
class UpdateSubstituteResponse:
    stock_item_not_found: bool = False
    link_not_found: bool = False
    invalid_ratio: str | None = None


class UpdateSubstituteHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(
        self,
        stock_item_id: UUID,
        substitute_id: UUID,
        request: UpdateSubstituteRequest,
    ) -> UpdateSubstituteResponse:
        if stock_item_id == substitute_id:
            return UpdateSubstituteResponse(link_not_found=True)
        if not self.repository.get(StockItem).exists(stock_item_id):
            return UpdateSubstituteResponse(stock_item_not_found=True)

        meta = SubstituteMetadata(
            notes=request.notes,
            ratio_quantity_in=request.ratio_quantity_in,
            ratio_unit_in=request.ratio_unit_in,
            ratio_quantity_out=request.ratio_quantity_out,
            ratio_unit_out=request.ratio_unit_out,
        )
        error = validate_metadata(meta)
        if error is not None:
            return UpdateSubstituteResponse(invalid_ratio=error)

        a_id, b_id = canonical_pair(stock_item_id, substitute_id)
        persisted = build_metadata(
            meta=meta,
            from_id=stock_item_id,
            canonical_a_id=a_id,
        )

        _Assoc = db.metadata.tables["StockItemSubstitute"]
        _Result = db.session.execute(
            _Assoc.update()
            .where(
                (_Assoc.c.stock_item_a_id == a_id)
                & (_Assoc.c.stock_item_b_id == b_id)
            )
            .values(
                notes=persisted.notes,
                ratio_quantity_in=persisted.ratio_quantity_in,
                ratio_unit_in=persisted.ratio_unit_in,
                ratio_quantity_out=persisted.ratio_quantity_out,
                ratio_unit_out=persisted.ratio_unit_out,
            )
        )
        if _Result.rowcount == 0:
            return UpdateSubstituteResponse(link_not_found=True)

        self.repository.save_changes()
        return UpdateSubstituteResponse()


@STOCK_ITEM_ROUTER.route(
    "<uuid:stock_item_id>/substitutes/<uuid:substitute_id>", methods=["PATCH"]
)
@has_request_body(UpdateSubstituteRequest)
def update_substitute(stock_item_id: UUID, substitute_id: UUID):
    _Handler = UpdateSubstituteHandler(SqlAlchemyRepository())
    _Request: UpdateSubstituteRequest = get_request_body()
    _Response = _Handler.handle(stock_item_id, substitute_id, _Request)

    if _Response.stock_item_not_found:
        return not_found(StockItem.__name__, stock_item_id)
    if _Response.link_not_found:
        return not_found("StockItemSubstitute link", substitute_id)
    if _Response.invalid_ratio is not None:
        return business_rule_violation(_Response.invalid_ratio)

    _LOGGER.info(
        "Updated substitute metadata %s ↔ %s", stock_item_id, substitute_id,
    )
    return no_content()
