"""Price-observation logging for a stock item — the everyday "what this cost
me" substrate (PROPOSAL_PRODUCTS_AS_OVERLAY §3.2 / FU-227 chunk 2).

Folded shape (A1): the user logs TOTAL price + TOTAL measure + unit. Per-unit
cost is derived server-side (R-003 — ``get_stock_item_unit_cost_with_unit_at``); the
client never divides. Optional ``store_id`` (A2) for "Last seen at Coles".
The ``source`` enum is gone (A4 revised) — provenance comes from the FK
``shopping_list_line_id`` on rows the ``/finish`` handler harvests (chunk 5);
this manual endpoint writes ``None`` for it.

Money/spend feature gates the UI surfaces, not the endpoint (mirrors the
products endpoints).
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain import units
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_item_price_observation import \
    StockItemPriceObservation
from dora_api.domain.entities.store import Store
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.infrastructure.api_response import bad_request, no_content, not_found
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


class AddPriceObservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_price: float = Field(gt=0)
    total_measure: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=32)
    observed_at: datetime | None = None
    store_id: UUID | None = None
    # Multipack metadata (FU-227 follow-up). None ⇒ single pack /
    # free-weight (common case). The math doesn't read pack_count —
    # `total_measure` is still the TOTAL — pack_count is purely the
    # "4 × 125g" display context so we don't lose it on entry.
    pack_count: int | None = Field(default=None, gt=0)


@dataclass(slots=True)
class PriceObservationMutationResponse:
    stock_item_not_found: bool = False
    observation_not_found: bool = False
    invalid_unit: str | None = None         # the offending unit string
    store_not_found: bool = False


class PriceObservationHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def add(self, stock_item_id: UUID, request: AddPriceObservationRequest) -> PriceObservationMutationResponse:
        if not self.repository.get(StockItem).exists(stock_item_id):
            return PriceObservationMutationResponse(stock_item_not_found=True)

        # unit must be on the supported price list (volume / mass / count).
        # Normalised via the chunk-1 domain helper so "L", " L ", "litre" all
        # land. Rejected units include kJ, °C, mm — those are recipe-side, not
        # price-side (R-001-equivalent: one validation source).
        unit_def = units.find_unit(request.unit)
        if unit_def is None or unit_def.dimension not in units.PRICE_DIMENSIONS:
            return PriceObservationMutationResponse(invalid_unit=request.unit)

        # A2 — optional store. If supplied, validate it exists (FK would also
        # reject, but a friendly 400 beats a 500).
        if request.store_id is not None and not self.repository.get(Store).exists(request.store_id):
            return PriceObservationMutationResponse(store_not_found=True)

        self.repository.add(StockItemPriceObservation(
            stock_item_id=stock_item_id,
            total_price=float(request.total_price),
            total_measure=float(request.total_measure),
            unit=unit_def.canonical,    # persist the canonical form, not the alias
            observed_at=request.observed_at or datetime.now(timezone.utc),
            store_id=request.store_id,
            shopping_list_line_id=None,  # manual entries have no provenance line
            created_at=datetime.now(timezone.utc),
            pack_count=request.pack_count,
        ))
        self.repository.save_changes()
        return PriceObservationMutationResponse()

    def delete(self, stock_item_id: UUID, observation_id: UUID) -> PriceObservationMutationResponse:
        match = self.repository.get(StockItemPriceObservation).one(
            EntityField(StockItemPriceObservation, "id").eq(observation_id)
            & EntityField(
                StockItemPriceObservation,
                StockItemPriceObservation.Fields.STOCK_ITEM_ID,
            ).eq(stock_item_id)
        )
        if match is None:
            return PriceObservationMutationResponse(observation_not_found=True)
        self.repository.remove(match)
        self.repository.save_changes()
        return PriceObservationMutationResponse()


@STOCK_ITEM_ROUTER.route("<uuid:stock_item_id>/price-observations", methods=["POST"])
@has_request_body(AddPriceObservationRequest)
def add_price_observation(stock_item_id: UUID):
    _Handler = PriceObservationHandler(SqlAlchemyRepository())
    _Request: AddPriceObservationRequest = get_request_body()
    _Response = _Handler.add(stock_item_id, _Request)
    if _Response.stock_item_not_found:
        return not_found(StockItem.__name__, stock_item_id)
    if _Response.invalid_unit is not None:
        return bad_request(
            f"Unit {_Response.invalid_unit!r} is not supported for price entry. "
            f"Use a volume (L, ml, …), mass (kg, g, …) or count (ea, dozen, pack) unit."
        )
    if _Response.store_not_found:
        return not_found(Store.__name__, _Request.store_id)
    _LOGGER.info("Logged a price for stock item %s", stock_item_id)
    return no_content()


@STOCK_ITEM_ROUTER.route("<uuid:stock_item_id>/price-observations/<uuid:observation_id>", methods=["DELETE"])
def delete_price_observation(stock_item_id: UUID, observation_id: UUID):
    _Handler = PriceObservationHandler(SqlAlchemyRepository())
    _Response = _Handler.delete(stock_item_id, observation_id)
    if _Response.observation_not_found:
        return not_found(StockItemPriceObservation.__name__, observation_id)
    return no_content()
