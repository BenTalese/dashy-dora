import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from dora_api.app import db
from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.features.substitutes.canonical import canonical_pair
from dora_api.features.substitutes.metadata import (
    SubstituteMetadata, build_metadata, validate_metadata,
)
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  entity_existence_failure,
                                                  no_content, not_found)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import (field_of, get_request_body)
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


class AddSubstituteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    substitute_id: UUID
    # free-text hint + optional structured ratio. Both default to
    # None for backward compatibility with callers that don't care. The
    # ratio direction (in/out) is *from the perspective of stock_item_id*;
    # the handler reorients it into the canonical pair direction before
    # persisting.
    notes: str | None = Field(default=None, max_length=255)
    ratio_quantity_in: float | None = None
    ratio_unit_in: str | None = Field(default=None, max_length=32)
    ratio_quantity_out: float | None = None
    ratio_unit_out: str | None = Field(default=None, max_length=32)


@dataclass(slots=True)
class AddSubstituteResponse:
    stock_item_not_found: bool = False
    substitute_not_found: bool = False
    is_self: bool = False
    already_linked: bool = False
    # ratio validation failure (a single message; the API layer
    # turns it into a business-rule-violation response).
    invalid_ratio: str | None = None


class AddSubstituteHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, stock_item_id: UUID, request: AddSubstituteRequest) -> AddSubstituteResponse:
        if stock_item_id == request.substitute_id:
            return AddSubstituteResponse(is_self=True)

        if not self.repository.get(StockItem).exists(stock_item_id):
            return AddSubstituteResponse(stock_item_not_found=True)
        if not self.repository.get(StockItem).exists(request.substitute_id):
            return AddSubstituteResponse(substitute_not_found=True)

        # validate the requested metadata (all-or-none ratio,
        # positive quantities, units in the canonical catalogue).
        _Meta = SubstituteMetadata(
            notes=request.notes,
            ratio_quantity_in=request.ratio_quantity_in,
            ratio_unit_in=request.ratio_unit_in,
            ratio_quantity_out=request.ratio_quantity_out,
            ratio_unit_out=request.ratio_unit_out,
        )
        _Error = validate_metadata(_Meta)
        if _Error is not None:
            return AddSubstituteResponse(invalid_ratio=_Error)

        # Undirected pair stored canonically (a_id < b_id). Idempotent: a
        # duplicate is reported as already-linked rather than an error.
        a_id, b_id = canonical_pair(stock_item_id, request.substitute_id)
        _Assoc = db.metadata.tables["StockItemSubstitute"]
        _Existing = db.session.execute(
            select(_Assoc.c.stock_item_a_id).where(
                (_Assoc.c.stock_item_a_id == a_id)
                & (_Assoc.c.stock_item_b_id == b_id)
            )
        ).first()
        if _Existing is not None:
            return AddSubstituteResponse(already_linked=True)

        # flip the ratio in/out to the canonical A→B direction
        # if the caller passed it the B→A way round.
        _Persisted = build_metadata(
            meta=_Meta,
            from_id=stock_item_id,
            canonical_a_id=a_id,
        )
        db.session.execute(
            _Assoc.insert().values(
                stock_item_a_id=a_id,
                stock_item_b_id=b_id,
                notes=_Persisted.notes,
                ratio_quantity_in=_Persisted.ratio_quantity_in,
                ratio_unit_in=_Persisted.ratio_unit_in,
                ratio_quantity_out=_Persisted.ratio_quantity_out,
                ratio_unit_out=_Persisted.ratio_unit_out,
                created_at=datetime.now(timezone.utc),
            )
        )
        self.repository.save_changes()
        return AddSubstituteResponse()


@STOCK_ITEM_ROUTER.route("<uuid:stock_item_id>/substitutes", methods=["POST"])
@has_request_body(AddSubstituteRequest)
def add_substitute(stock_item_id: UUID):
    _Handler = AddSubstituteHandler(SqlAlchemyRepository())
    _Request: AddSubstituteRequest = get_request_body()
    _Response = _Handler.handle(stock_item_id, _Request)

    if _Response.stock_item_not_found:
        return not_found(StockItem.__name__, stock_item_id)
    if _Response.is_self:
        return business_rule_violation("A stock item can't be its own substitute.")
    if _Response.substitute_not_found:
        return entity_existence_failure(
            StockItem.__name__,
            field_of(AddSubstituteRequest, "substitute_id"),
            _Request.substitute_id,
        )
    if _Response.invalid_ratio is not None:
        return business_rule_violation(_Response.invalid_ratio)

    _LOGGER.info(
        "Added substitute %s to stock item %s%s",
        _Request.substitute_id,
        stock_item_id,
        " (already linked)" if _Response.already_linked else "",
    )
    return no_content()
