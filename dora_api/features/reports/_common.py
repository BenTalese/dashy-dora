"""Shared plumbing for the Reports endpoints: the money gate and the range
token (`range=30d|90d|1y|2y|5y|all`). `range=all` means "no lower bound"
everywhere a range is accepted; the bound itself is the household's midnight
(`features._ranges`, finalisation 12-R3)."""

from datetime import datetime, timezone

from sqlalchemy import func, select

from dora_api.domain.entities.shopping_list import ShoppingList
from dora_api.domain.entities.cook_event import CookEvent
from dora_api.domain.entities.stock_level_change import StockLevelChange
from dora_api.domain.entities.stock_item_price_observation import (
    StockItemPriceObservation)
from dora_api.domain.entities.stock_item_waste_event import StockItemWasteEvent
from dora_api.features.app_settings.access import money_features_enabled
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.features._ranges import RANGE_DAYS, range_start


# ───── Money gate ─────────────────────────────────────────────────────────

# FU-816 / R-058. `ReportsPage.vue` imported no feature flag at all, so an
# install that had opted out of money still got spend by store, savings, spend
# by category, year-over-year and two dollar-formatted chart axes — a live
# contradiction with the owner feedback bullet the whole money opt-in was built
# from. Gating the render alone is not enough: the same lesson as the buy
# verdict (R-058) is that a money surface must refuse at the endpoint too, or
# the next caller re-opens the hole.
MONEY_DISABLED_DETAIL = (
    "This report answers in dollars, and money features are turned off for "
    "this install."
)


def money_off() -> bool:
    return not money_features_enabled(SqlAlchemyRepository())


# ───── Range helpers ──────────────────────────────────────────────────────

def parse_range(raw: str | None, repository: Repository | None = None) -> datetime | None:
    """Returns the lower-bound datetime for filtering, or None for 'all'.
    Defaults to 30 days when the param is missing or unrecognised — that's
    the most useful default for the page's initial render. The bound is the
    household's midnight (finalisation 12-R3)."""
    return range_start(range_days(raw), repository or SqlAlchemyRepository())


def range_days(raw: str | None) -> int | None:
    """Number of days the range spans, or None for 'all'. Used by
    endpoints that need to compute a same-length prior window (YoY)."""
    token = (raw or "30d").strip().lower()
    if token == "all":
        return None
    return RANGE_DAYS.get(token, 30)


def earliest_activity(repository: Repository) -> datetime | None:
    """The oldest dated record any report on the page reads from."""
    session = repository.session
    candidates = [
        session.execute(select(func.min(column))).scalar()
        for column in (
            ShoppingList.created_at,
            CookEvent.occurred_at,
            StockLevelChange.changed_at,
            StockItemWasteEvent.occurred_at,
            StockItemPriceObservation.observed_at,
        )
    ]
    found = [c for c in candidates if c is not None]
    return min(found, key=lambda d: d.replace(tzinfo=None)) if found else None

def bucket_size_days(since: datetime | None) -> int:
    """Pick a day-bucket size that keeps the time series readable.
    30d → daily, 90d → daily, 1y → weekly. 2y/5y/all-time → monthly.
    """
    if since is None:
        return 30
    span = (datetime.now(timezone.utc) - since).days
    if span > 500:
        return 30    # monthly-ish for 2y/5y/all
    if span > 120:
        return 7     # weekly for 1y
    return 1         # daily for 30d/90d


# ───── 1. (retired) Stock value over time ─────────────────────────────────
# `StockValueOverTimeHandler` / `GET /reports/stock-value-over-time` were
# deleted in finalisation 12-R1 (R-057): the Reports card went in C-waste,
# the dashboard `pantry_value` card on 2026-09-04, and the SPA service method
# had no caller — while the handler itself read `item.stock_level` and
# `item.products` off `lazy="noload"` relationships, so every figure it
# produced was systematically undercounted (R-032). If a pantry-value series
# is ever revived, include both relationships and reuse `bucket_size_days`.
