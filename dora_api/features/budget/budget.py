"""P2-05 — grocery budget (cross-shopping-list).

  GET /api/budget/status    — current-period spend, remaining, projection
  GET /api/budget/history   — last N completed periods (default 6) for trend

Budget settings (amount + period) are a single install-wide household value
on `AppSetting` (spend is summed across every *shared* shopping list, so the
target must be shared too). Any household member edits them via
`PATCH /api/budget/settings`; clients read them via `/api/health.budget_policy`.
Value-driven: `budget_amount` NULL/≤0 ⇒ the feature is off.

"Spent" in a period = the sum of every line on every archived shopping
list whose `completed_at` falls inside the rolling period, using the same
price-priority ladder the rest of the app uses:
  1. actual_unit_price  (user-entered, P2-02)
  2. picked_offer_price (offer snapshot; only on lines finished before
     2026-09-17, nothing writes it since)
  3. — skipped — no price means no contribution rather than a guess.

Cross-list by construction: every completed shop in the period counts,
no matter which list it was on.

"Projected" = same calculation but for active (non-archived) lists, using
the chosen offer's current price_now. Lets the dashboard show "if you
finish this shop you'll be at $X" without committing to numbers we can't
defend (offers can drift between now and finish). Only lists whose shop day
falls in the period count toward it (owner 2026-10-15): a list planned for
next week is next week's money. See `counts_toward_period`.

`?on=YYYY-MM-DD` asks about the period containing that date rather than
today's, which is how the meal planner prices the week it is showing.

**Shared arithmetic** — `period_bounds(today, period)`, `period_spent(...)`,
and `period_headroom(on_date, repository)` are the only functions authorised
to compute budget windows and remaining-money figures. The trim-to-budget
optimiser (FU-448) and any future budget-aware surface call `period_headroom`
rather than re-deriving it in a second place. R-003 state-ownership.
"""
import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from uuid import UUID

from flask import request
from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.product_offer import ProductOffer
from dora_api.domain.entities.shopping_list import (SHOPPING_LIST_STATUS_DONE,
                                                    ShoppingList,
                                                    ShoppingListLine)
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.features.app_settings.clock import household_timezone, household_today
from dora_api.domain.entities.app_setting import (ALLOWED_BUDGET_PERIODS,
                                                  AppSetting,
                                                  BUDGET_PERIOD_MONTHLY,
                                                  BUDGET_PERIOD_WEEKLY)
from dora_api.features.routers import BUDGET_ROUTER
from dora_api.features.shopping_lists._line_price import (line_paid_unit_price,
                                                         spend_lines)
from dora_api.persistence.aware import as_utc
from dora_api.infrastructure.api_response import bad_request, ok, unauthorized
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.session_user import current_user_id

_LOGGER = logging.getLogger(__name__)


# ── Period boundaries ────────────────────────────────────────────────────
# Date-only arithmetic anchored on `household_today`, with the datetime
# comparison done at the *household's* midnight (R-021). It used to be UTC
# midnight: in a +10 household a shop finished Monday 08:00 local landed in
# the previous week's budget for the first ten hours of every period
# (finalisation 12-R2). `completed_at` is stored as a UTC instant, so a
# household-midnight boundary is converted to UTC before the query.

def period_bounds(today: date, period: str) -> tuple[date, date]:
    """Return [start, end) for the rolling period containing `today`.
    Week starts Monday (ISO weekday convention). Exported so the
    trim-to-budget optimiser can compute headroom for a shop scheduled
    in a later period."""
    if period == BUDGET_PERIOD_MONTHLY:
        start = today.replace(day=1)
        # First of next month — handles year rollover too.
        if start.month == 12:
            end = date(start.year + 1, 1, 1)
        else:
            end = date(start.year, start.month + 1, 1)
        return start, end
    # Default = weekly. Monday-start.
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=7)
    return start, end


def _boundary_utc(d: date, tz: ZoneInfo) -> datetime:
    """The household's midnight starting day `d`, as the UTC instant the
    `completed_at` column compares against."""
    return datetime.combine(d, time.min, tzinfo=tz).astimezone(timezone.utc)


def _household_date(completed_at: datetime, tz: ZoneInfo) -> date:
    """Calendar day of a stored instant in the household zone."""
    return as_utc(completed_at).astimezone(tz).date()


def _budget_amount(setting: AppSetting) -> float | None:
    """Positive household budget_amount as a float, or None when off / unset."""
    if setting.budget_amount is not None and setting.budget_amount > 0:
        return float(setting.budget_amount)
    return None


def _budget_period(setting: AppSetting) -> str:
    """The household budget period, defaulting to weekly if unset."""
    return setting.budget_period or BUDGET_PERIOD_WEEKLY


@dataclass(frozen=True, slots=True)
class HouseholdBudget:
    amount: float
    period: str


def household_budget(repository: SqlAlchemyRepository) -> HouseholdBudget | None:
    """The household's positive grocery budget, or None when money is off
    install-wide or no budget is set. Every budget-aware surface reads it here
    so the cap gate and the displayed figure can't disagree (02-R13)."""
    setting = get_or_create_app_setting(repository)
    if not setting.money_enabled:
        return None
    amount = _budget_amount(setting)
    if amount is None:
        return None
    return HouseholdBudget(amount=amount, period=_budget_period(setting))


def period_spent(
    period_start: date,
    period_end: date,
    repository: SqlAlchemyRepository,
) -> float:
    """Sum of archived shopping-list lines whose completed_at falls in the
    half-open window `[period_start, period_end)`, read through
    `_line_price.spend_lines` (actual > picked-offer > drop). Household-wide by construction
    (the schema is single-household): every completed shop in the period
    counts, no matter which list or user it was on.

    Only **ticked** lines count. A price on a line is not evidence it was
    bought: `picked_offer_price` used to be snapshotted when the line was
    *added*, so an older unticked line with a linked offer carries a price it
    never cost. Left
    unfiltered, finishing a list with leftovers billed the whole list to the
    budget and inflated `period_headroom` by the same amount. This mirrors
    `compute_list_totals`' `spent_only` rule, which a done list's own receipt
    has always applied."""
    tz = household_timezone(repository)
    lines = spend_lines(
        repository.session,
        _boundary_utc(period_start, tz),
        _boundary_utc(period_end, tz),
    )
    return sum(line.spent for line in lines)


def period_headroom(
    on_date: date,
    repository: SqlAlchemyRepository,
) -> float | None:
    """The single source of truth for "how much money is left in the household
    budget for the period containing `on_date`" — the trim-to-budget optimiser,
    the meal-plan swap suggestions and the auto-build cap all read it.
    Returns None when there's no household budget (money off install-wide, or
    no positive amount) — the same gate `household_budget` applies. A future
    period has no spend landed yet, so it returns the full amount; the current
    or a past period deducts actual spend so far in that window."""
    budget = household_budget(repository)
    if budget is None:
        return None
    start, end = period_bounds(on_date, budget.period)
    return budget.amount - period_spent(start, end, repository)


# ── Line-price ladder ────────────────────────────────────────────────────
# The actual→picked ladder lives in `shopping_lists._line_price`
# (`line_paid_unit_price`, K2 extract). Budget's projection adds one more
# rung (the selected product's *current* offer) on top of it.


def projected_unit_price(
    line: ShoppingListLine,
    current_offer_lookup: dict[UUID, ProductOffer],
) -> float | None:
    """Price for a line on an active list. Tries actual → snapshot →
    current offer of the selected product. Lines without any of those
    don't contribute. Public — the trim-to-budget optimiser reads the
    same ladder so the projected figure it constrains against matches
    the dashboard's projection to the cent."""
    direct = line_paid_unit_price(line)
    if direct is not None:
        return direct
    if line.selected_product_id and line.selected_product_id in current_offer_lookup:
        offer = current_offer_lookup[line.selected_product_id]
        if offer.price_now is not None:
            return float(offer.price_now)
    return None


def counts_toward_period(
    planned_shop_date: date | None,
    period_start: date,
    period_end: date,
    today: date,
) -> bool:
    """Whether an open list's spend belongs to the period `[start, end)`.

    A list dated inside the period belongs to it. In the *current* period an
    undated list belongs too (it could be shopped any day now), and so does
    one whose date has already passed without being finished: it is still
    money about to be spent. A later period only gets the lists dated in it.
    """
    if planned_shop_date is not None and period_start <= planned_shop_date < period_end:
        return True
    is_current = period_start <= today < period_end
    return is_current and (planned_shop_date is None or planned_shop_date < period_start)


# ── Status ───────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class BudgetStatusDto:
    enabled: bool
    amount: float | None
    period: str
    period_start: str | None
    period_end: str | None
    spent: float
    projected_active: float
    remaining: float | None
    over_budget: bool


class GetBudgetStatusHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, on_date: date | None = None) -> BudgetStatusDto:
        setting = get_or_create_app_setting(self.repository)

        # Compute boundaries even when the feature is off — the dashboard
        # surfaces "this week's spend" as a passive figure even when no
        # budget is set. R-021 — week/month windows align to the household
        # calendar boundary, not server-local.
        today = household_today(self.repository)
        period = _budget_period(setting)
        start, end = period_bounds(on_date or today, period)

        # Spent = archived lines in the window. Extracted to the shared
        # `period_spent` helper so the trim-to-budget optimiser reads the
        # same number.
        spent = period_spent(start, end, self.repository)

        # Projected still lives here — dashboard-only. Walks active lists'
        # lines, adding one more rung (current offer of the selected
        # product) beyond the archived ladder.
        active = [
            lst for lst in self.repository.get(ShoppingList).all(
                EntityField(ShoppingList, ShoppingList.Fields.STATUS).ne(SHOPPING_LIST_STATUS_DONE)
            )
            if counts_toward_period(lst.planned_shop_date, start, end, today)
        ]
        active_ids = [l.id for l in active]
        active_lines: list[ShoppingListLine] = []
        if active_ids:
            active_lines = self.repository.get(ShoppingListLine).all(
                EntityField(ShoppingListLine, ShoppingListLine.Fields.SHOPPING_LIST_ID)
                .in_(active_ids)
            )

        active_product_ids = list({
            l.selected_product_id for l in active_lines
            if l.selected_product_id is not None
        })
        offer_lookup: dict[UUID, ProductOffer] = {}
        if active_product_ids:
            offers = self.repository.get(ProductOffer).all(
                EntityField(ProductOffer, "_product_id").in_(active_product_ids)
            )
            for offer in offers:
                # ProductOffer's FK is mapped as `_product_id` (table_mappings).
                offer_lookup[offer._product_id] = offer

        projected_active = 0.0
        for line in active_lines:
            qty = line.quantity if line.quantity is not None else 1
            if qty <= 0:
                continue
            price = projected_unit_price(line, offer_lookup)
            if price is not None:
                projected_active += price * qty

        amount = _budget_amount(setting)
        remaining = (amount - spent) if amount is not None else None
        return BudgetStatusDto(
            enabled=amount is not None,
            amount=amount,
            period=period,
            period_start=start.isoformat(),
            period_end=end.isoformat(),
            spent=round(spent, 2),
            projected_active=round(projected_active, 2),
            remaining=round(remaining, 2) if remaining is not None else None,
            over_budget=amount is not None and spent > amount,
        )


@BUDGET_ROUTER.route("/status", methods=["GET"])
def get_budget_status():
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()
    on_raw = request.args.get("on")
    on_date: date | None = None
    if on_raw:
        try:
            on_date = date.fromisoformat(on_raw)
        except ValueError:
            return bad_request("`on` must be a date (YYYY-MM-DD).")
    dto = GetBudgetStatusHandler(SqlAlchemyRepository()).handle(on_date)
    _LOGGER.debug(
        "budget status user=%s period=%s spent=%.2f remaining=%s",
        user_id, dto.period, dto.spent,
        f"{dto.remaining:.2f}" if dto.remaining is not None else "n/a",
    )
    return ok(dto)


# ── History ──────────────────────────────────────────────────────────────
# A small N-period look-back for the dashboard trend chip ("3 of your last
# 6 weeks went over"). Reuses the same line-walk; kept separate from
# /status so the dashboard's common case (just this week) stays cheap.

@dataclass(frozen=True, slots=True)
class BudgetHistoryRowDto:
    period_start: str
    period_end: str
    spent: float
    over_budget: bool


class GetBudgetHistoryHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, periods: int) -> list[BudgetHistoryRowDto]:
        setting = get_or_create_app_setting(self.repository)

        # R-021 — current period anchored on household-tz today.
        today = household_today(self.repository)
        period = _budget_period(setting)
        amount = _budget_amount(setting)

        # Walk back N periods. The current period is index 0; older
        # rows come from anchoring the boundary calculator to a date
        # in each earlier window.
        anchors: list[date] = []
        cursor = today
        for _ in range(periods):
            start, _end = period_bounds(cursor, period)
            anchors.append(cursor)
            # One day before the period start lands inside the previous
            # period, regardless of week vs month.
            cursor = start - timedelta(days=1)

        earliest_start, _ = period_bounds(anchors[-1], period)
        _latest_start, latest_end = period_bounds(anchors[0], period)
        tz = household_timezone(self.repository)
        full_start_dt = _boundary_utc(earliest_start, tz)
        full_end_dt = _boundary_utc(latest_end, tz)

        # One read for the whole range, bucketed by household date so history
        # and the current period agree on what "spent" means.
        lines = spend_lines(self.repository.session, full_start_dt, full_end_dt)

        rows: list[BudgetHistoryRowDto] = []
        for anchor in anchors:
            start, end = period_bounds(anchor, period)
            window_total = sum(
                line.spent for line in lines
                if start <= _household_date(line.completed_at, tz) < end
            )
            rows.append(BudgetHistoryRowDto(
                period_start=start.isoformat(),
                period_end=end.isoformat(),
                spent=round(window_total, 2),
                over_budget=amount is not None and window_total > amount,
            ))
        return rows


@BUDGET_ROUTER.route("/history", methods=["GET"])
def get_budget_history():
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()
    try:
        periods = int(request.args.get("periods", "6"))
    except (TypeError, ValueError):
        periods = 6
    # Clamp to a sensible spread — the SPA never needs hundreds of rows
    # and an open-ended N is an easy DoS surface.
    periods = max(1, min(periods, 26))
    rows = GetBudgetHistoryHandler(SqlAlchemyRepository()).handle(periods)
    return ok({"rows": rows})


# ── Settings (household budget) ────────────────────────────────────────────
# The budget amount + period are an install-wide household value on
# AppSetting (moved off User — spend is shared, so the target must be too).
# Unlike the rest of AppSetting (admin-only PATCH /app-settings), this is
# editable by ANY authenticated household member: the grocery budget is
# kitchen-setup-grade shared config, same access class as shared shopping
# lists / stores / stock locations that any member curates. Value-driven —
# an amount of null / 0 clears the budget (no separate enabled flag).

class UpdateBudgetSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Present-in-body semantics: send `amount` (incl. explicit null / 0) to set
    # it, omit to leave unchanged. 0 or null ⇒ budget off.
    amount: float | None = Field(default=None, ge=0)
    period: str | None = None


@dataclass(frozen=True, slots=True)
class BudgetSettingsDto:
    amount: float | None
    period: str


@BUDGET_ROUTER.route("/settings", methods=["PATCH"])
@has_request_body(UpdateBudgetSettingsRequest)
def update_budget_settings():
    if current_user_id() is None:
        return unauthorized()
    request: UpdateBudgetSettingsRequest = get_request_body()
    set_fields = request.model_fields_set

    if "period" in set_fields and request.period is not None:
        if request.period not in ALLOWED_BUDGET_PERIODS:
            return bad_request(
                "Invalid budget period.",
                detail=f"'{request.period}' is not a valid budget period "
                       f"(expected one of {list(ALLOWED_BUDGET_PERIODS)}).",
            )

    repository = SqlAlchemyRepository()
    setting = get_or_create_app_setting(repository)
    if "amount" in set_fields:
        # Value-driven: 0 / null clears the budget (feature off).
        setting.budget_amount = (
            float(request.amount)
            if request.amount is not None and request.amount > 0
            else None
        )
    if "period" in set_fields and request.period is not None:
        setting.budget_period = request.period
    repository.save_changes()

    _LOGGER.info(
        "Household budget updated (amount=%s period=%s).",
        setting.budget_amount, setting.budget_period,
    )
    return ok(BudgetSettingsDto(
        amount=float(setting.budget_amount) if setting.budget_amount else None,
        period=setting.budget_period or BUDGET_PERIOD_WEEKLY,
    ))
