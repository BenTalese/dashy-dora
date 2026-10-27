"""Per-stock-item unioned price-history series (FU-227 chunk 6 / C5b).

  GET /api/stock-items/<id>/price-history

Powers the "Full history" bottom-sheet opened from the YourPrices widget. The
series unions the item's own observations ("your data") with its linked
products' offer history ("context"), every point normalised to the active
dimension's canonical unit so they share one y-axis (R-003 — normalisation is
server-owned, see ``your_prices.build_stock_item_price_series``). The baseline
block (median / above-usual / sample count) rides along so the chart can draw
the reference line + above-usual chip without a second round-trip.

UI-gated only (I3) — the only entry point is the money-gated widget; the
endpoint itself stays open, mirroring the manual observation endpoints.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.features.stock_items.your_prices import (
    build_stock_item_price_series, build_your_prices_for_item)
from dora_api.infrastructure.api_response import not_found, ok
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StockItemPriceHistoryPointDto:
    observed_at: datetime
    unit_price: float           # per canonical unit (L / kg / ea)
    source: str                 # "observation" | "offer"
    store_name: str | None


@dataclass(frozen=True, slots=True)
class StockItemPriceHistoryDto:
    stock_item_id: UUID
    name: str
    # The display denominator every point + the baseline share ("100ml",
    # "kg", "ea", or "oz" on a US install). None when the item has neither
    # observations nor a sized linked offer.
    display_unit: str | None
    # Baseline block (server-derived, R-003) for the chart's reference line +
    # above-usual chip. Null baseline below MIN_SAMPLES.
    baseline: float | None
    baseline_unit: str | None
    current: float | None
    above_baseline: bool
    sample_count: int
    points: list[StockItemPriceHistoryPointDto]


class StockItemPriceHistoryHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, stock_item_id: UUID) -> StockItemPriceHistoryDto | None:
        item = self.repository.get(StockItem).by_id(stock_item_id)
        if item is None:
            return None

        display_unit, points = build_stock_item_price_series(self.repository, stock_item_id)
        # Reuse the chunk-4 baseline chokepoint — one definition of median /
        # above-usual / sample_count across the widget + the chart.
        yp = build_your_prices_for_item(self.repository, stock_item_id)

        return StockItemPriceHistoryDto(
            stock_item_id=item.id,
            name=item.name,
            display_unit=display_unit,
            baseline=yp.baseline,
            baseline_unit=yp.baseline_unit,
            current=yp.current,
            above_baseline=yp.above_baseline,
            sample_count=yp.sample_count,
            points=[
                StockItemPriceHistoryPointDto(
                    observed_at=p.observed_at,
                    unit_price=p.unit_price,
                    source=p.source,
                    store_name=p.store_name,
                )
                for p in points
            ],
        )


@STOCK_ITEM_ROUTER.route("<uuid:stock_item_id>/price-history", methods=["GET"])
def get_stock_item_price_history(stock_item_id: UUID):
    _Result = StockItemPriceHistoryHandler(SqlAlchemyRepository()).handle(stock_item_id)
    if _Result is None:
        return not_found(StockItem.__name__, stock_item_id)
    _LOGGER.debug(
        "Stock item %s price history: %d points (unit=%s)",
        stock_item_id, len(_Result.points), _Result.display_unit,
    )
    return ok(_Result)
