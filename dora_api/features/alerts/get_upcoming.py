"""GET /api/alerts/upcoming — the "this fortnight" forward view (C-9.6).

A **server-owned aggregation** (R-003): the client never re-derives the window
or fans out across entities. It folds three already-existing dated signals into
one date-grouped shape over the next N days (default 14):

  - **expiries**  — `StockItem.expiry_date` falling in the window.
  - **shopping**  — not-yet-done `ShoppingList`s with a `planned_shop_date` in it.
  - **meals**     — `MealPlanEntry`s scheduled in it (with the recipe name).

The window is anchored on the **household** today (C-2.K timezone), the same
boundary the C-9.4 nudges use — so "the next 14 days" means the same thing here,
in the bell, and in the planner. Only days that carry at least one event are
returned; the client builds the empty grid from `start` + `days` and looks each
date up.
"""
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List

from dora_api.domain.entities.meal_plan_entry import MealPlanEntry
from dora_api.domain.entities.shopping_list import (SHOPPING_LIST_STATUS_DONE,
                                                    ShoppingList)
from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.app_settings.clock import household_today
from dora_api.features.routers import ALERT_ROUTER
from dora_api.infrastructure.api_response import ok
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from flask import request

_LOGGER = logging.getLogger(__name__)

# Default horizon (the "fortnight"); clamped so a caller can't ask for an
# unbounded scan. One source for the bounds (R-003).
_DEFAULT_DAYS = 14
_MAX_DAYS = 31


@dataclass(frozen=True, slots=True)
class UpcomingExpiry:
    stock_item_id: str
    name: str


@dataclass(frozen=True, slots=True)
class UpcomingShopping:
    list_id: str
    name: str


@dataclass(frozen=True, slots=True)
class UpcomingMeal:
    recipe_id: str
    recipe_name: str
    slot: str


@dataclass(frozen=True, slots=True)
class UpcomingDay:
    date: str
    expiries: List[UpcomingExpiry] = field(default_factory=list)
    shopping: List[UpcomingShopping] = field(default_factory=list)
    meals: List[UpcomingMeal] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class UpcomingDto:
    start: str           # household-today (ISO) — first cell of the grid
    end: str             # last day in the window (inclusive, ISO)
    days: int            # window length, so the client can size the grid
    dates: List[UpcomingDay] = field(default_factory=list)  # non-empty days only


class GetUpcomingHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, days: int) -> UpcomingDto:
        today = household_today(self.repository)
        end = today + timedelta(days=days - 1)

        # One mutable accumulator per date; emitted sorted, non-empty only.
        by_date: Dict[date, UpcomingDay] = {}

        def _day(d: date) -> UpcomingDay:
            existing = by_date.get(d)
            if existing is None:
                existing = UpcomingDay(date=d.isoformat())
                by_date[d] = existing
            return existing

        # ── Expiries ──────────────────────────────────────────────────
        expiring: List[StockItem] = self.repository.get(StockItem).all(
            EntityField(StockItem, StockItem.Fields.EXPIRY_DATE).between(today, end)
        )
        for item in expiring:
            _day(item.expiry_date).expiries.append(
                UpcomingExpiry(stock_item_id=str(item.id), name=item.name)
            )

        # ── Planned shopping days (not yet done) ──────────────────────
        lists: List[ShoppingList] = self.repository.get(ShoppingList).all(
            EntityField(ShoppingList, ShoppingList.Fields.PLANNED_SHOP_DATE)
            .between(today, end)
            & EntityField(ShoppingList, ShoppingList.Fields.STATUS)
            .ne(SHOPPING_LIST_STATUS_DONE)
        )
        for lst in lists:
            _day(lst.planned_shop_date).shopping.append(
                UpcomingShopping(list_id=str(lst.id), name=lst.display_name)
            )

        # ── Meal-plan days ────────────────────────────────────────────
        entries: List[MealPlanEntry] = (
            self.repository.get(MealPlanEntry)
            .include(MealPlanEntry.Fields.RECIPE)
            .all(
                EntityField(MealPlanEntry, MealPlanEntry.Fields.SCHEDULED_FOR)
                .between(today, end)
            )
        )
        for entry in entries:
            _day(entry.scheduled_for).meals.append(
                UpcomingMeal(
                    recipe_id=str(entry.recipe.id),
                    recipe_name=entry.recipe.name,
                    slot=entry.slot,
                )
            )

        dates = [by_date[d] for d in sorted(by_date)]
        for day in dates:
            day.expiries.sort(key=lambda e: e.name.lower())
            day.shopping.sort(key=lambda s: s.name.lower())
            day.meals.sort(key=lambda m: (m.slot.lower(), m.recipe_name.lower()))

        return UpcomingDto(
            start=today.isoformat(),
            end=end.isoformat(),
            days=days,
            dates=dates,
        )


@ALERT_ROUTER.route("/upcoming", methods=["GET"])
def get_upcoming():
    try:
        days = int(request.args.get("days", _DEFAULT_DAYS))
    except (TypeError, ValueError):
        days = _DEFAULT_DAYS
    days = max(1, min(days, _MAX_DAYS))
    _Upcoming = GetUpcomingHandler(SqlAlchemyRepository()).handle(days)
    _LOGGER.debug(
        "Upcoming: %d day(s) with events over a %d-day window",
        len(_Upcoming.dates), days,
    )
    return ok(_Upcoming)
