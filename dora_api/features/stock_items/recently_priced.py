"""GET /api/stock-items/recently-priced — stock items you logged a price for
most recently, newest first.

The log-price picker's shortlist (owner, 2026-09-04). Price logging is bursty
and repetitive — you come home from a shop and log four things, or you log the
same staple every fortnight — so "what did I price last?" is a far better
opening guess than the stock-level ordering the picker used before.

Shaped after `shopping_lists/frequently_added.py`, deliberately: same
one-grouped-query + hydrate-names pattern, same best-effort posture on the
client (a failure just falls back to the old ordering).

R-003 — the recency ordering is server-owned. The client renders the order it
is given; it never sorts observations itself (it doesn't hold them).
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List
from uuid import UUID

from flask import request
from sqlalchemy import func, select

from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_item_price_observation import \
    StockItemPriceObservation
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.infrastructure.api_response import ok
from dora_api.infrastructure.ports import Repository
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RecentlyPricedDto:
    stock_item_id: UUID
    name: str
    last_priced_at: datetime


class GetRecentlyPricedHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, limit: int) -> List[RecentlyPricedDto]:
        session = self.repository.session
        # One grouped query for the recency key; StockItem is read only for the
        # name (a caller with no items cached can still render the shortlist).
        # No level here on purpose: `StockItem.stock_level` is `lazy="noload"`
        # (R-082) and the picker already holds the full item from its own store
        # — it looks each id up there and gets the level with it.
        rows = session.execute(
            select(
                StockItemPriceObservation.stock_item_id,
                func.max(StockItemPriceObservation.observed_at).label("last_priced_at"),
            ).group_by(StockItemPriceObservation.stock_item_id)
        ).all()
        if not rows:
            return []

        latest: dict[UUID, datetime] = {row[0]: row[1] for row in rows if row[1] is not None}
        out: List[RecentlyPricedDto] = []
        if not latest:
            return []
        # Only the items that have an observation — not the whole pantry to
        # hydrate at most `limit` names (finalisation 06-R9).
        priced_items = self.repository.get(StockItem).all(
            EntityField(StockItem, "id").in_(list(latest))
        )
        for item in priced_items:
            observed_at = latest.get(item.id)
            if observed_at is None:
                continue
            out.append(RecentlyPricedDto(
                stock_item_id = item.id,
                name = item.name,
                last_priced_at = observed_at,
            ))
        # Most-recent first; alphabetical tiebreak so two observations logged in
        # the same second still come back in a stable order.
        out.sort(key=lambda r: (-r.last_priced_at.timestamp(), r.name.lower()))
        return out[:limit]


@STOCK_ITEM_ROUTER.route("/recently-priced", methods=["GET"])
def get_recently_priced():
    try:
        _Limit = int(request.args.get("limit", "12"))
    except (TypeError, ValueError):
        _Limit = 12
    _Limit = max(1, min(_Limit, 50))
    _Results = GetRecentlyPricedHandler(SqlAlchemyRepository()).handle(_Limit)
    _LOGGER.debug("Recently-priced returned %d items (limit %d)", len(_Results), _Limit)
    return ok(_Results)
