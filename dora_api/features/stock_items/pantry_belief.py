"""P8-07 — The Zero-Input Pantry belief service (FLAGSHIP).

Server-owned (R-003) confidence-weighted belief about each stock item's
level, inferred from the closed loop instead of manual logging:

  • intake  (P6-01) — the last purchase anchors the belief to Stocked and
    starts a fresh depletion clock.
  • cadence (P6-04) — the typical gap between purchases estimates how long
    a fresh buy lasts.
  • cooking (P6-07) — consumption events draw the belief down faster than
    the calendar alone would (cooking three times this week is not an
    untouched week).
  • time decay — the longer since any hard signal, the lower the confidence
    and the more the belief drifts Stocked → Low → Out.

Charter alignment (Part II):
  1 Effortless — replaces manual logging; the user maintains nothing.
  2 Coarse-by-design — a BAND (Out/Low/Stocked), never a fake exact count.
  3 Self-correcting & honest — every belief carries a confidence + a plain
    reason; thin data yields low confidence, never a confident wrong answer.
  5 Leverage the loop — reads purchases + cooking + cadence together.
  7 Explainable — the `reason` is the "why" the UI surfaces.

Manual override wins (P8-07 spec): a recent `last_checked_at` (the user
confirming the level) pins the belief to the recorded level at high
confidence — inference never argues with a fresh human check.

The core (`compute_belief`) is a **pure function** of gathered inputs so
it is unit-testable without a database; the `gather_*` helpers do the repo
access. All thresholds below are coarse and deliberately tunable — the
point is a robust band, not false precision.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo
from uuid import UUID

from dora_api.persistence.aware import as_utc
from dora_api.domain.cadence_math import mean_gap_days
from dora_api.domain.entities.consumption_event import ConsumptionEvent
from dora_api.domain.entities.shopping_list import (SHOPPING_LIST_STATUS_DONE,
                                                    ShoppingList,
                                                    ShoppingListLine)
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.stock_status import (LOW_STOCK_SEQUENCE,
                                          OUT_OF_STOCK_SEQUENCE,
                                          STOCKED_SEQUENCE)
from dora_api.features.app_settings.clock import household_timezone, household_today
from dora_api.features.shopping_lists._line_price import line_paid_unit_price
from dora_api.features.stock_items._level_access import resolve_levels_by_item
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


# ── Coarse, tunable thresholds ───────────────────────────────────────────

# A check/level-change within this many days is treated as a fresh hard
# read — inference defers to it entirely (manual override wins).
_HARD_SIGNAL_FRESH_DAYS = 3

# Need at least this many unique purchase dates to estimate a cadence
# (2 dates → 1 gap). Below this we can't project from purchases.
_MIN_PURCHASE_DATES_FOR_CADENCE = 2

# Depletion progress → band cut-points. progress ≈ 1.0 means "a full
# purchase cycle's worth has elapsed / been cooked through".
_PROGRESS_LOW = 0.75      # at/after this fraction of a cycle → ~Low
_PROGRESS_OUT = 1.15      # comfortably past a full cycle → ~Out

# Each consumption (cook) event since the last purchase advances depletion
# by this fraction of a cycle — so cooking with an item empties it sooner
# than the calendar cadence alone implies (this is the P6-07 signal).
_CONSUMPTION_WEIGHT = 0.34

# Confidence band cut-points (0..1).
_CONF_HIGH = 0.66
_CONF_MEDIUM = 0.33

# Confidence when we're leaning on a stale recorded level with no cadence
# to project from (thin history) — decays with staleness but never claims
# certainty.
_THIN_BASE_CONFIDENCE = 0.4


@dataclass(slots=True)
class BeliefInputs:
    """Everything `compute_belief` needs, already gathered from the repo."""
    recorded_sequence: int | None
    stock_level_last_updated: date | None
    last_checked_at: date | None
    purchase_dates: list[date]      # unique, ascending
    consumption_dates: list[date]   # ascending
    today: date


@dataclass(slots=True)
class PantryBelief:
    believed_sequence: int
    believed_band: str            # 'out' | 'low' | 'stocked'
    confidence: float             # 0..1
    confidence_band: str          # 'high' | 'medium' | 'low'
    reason: str
    # True when the belief is a genuine inference (extrapolated), False when
    # it merely echoes a freshly-confirmed recorded level.
    is_inferred: bool
    # True when the inferred band differs from what the user last recorded —
    # the chip nudges and the quick-check generator may ask.
    differs_from_recorded: bool


_BAND_BY_SEQUENCE = {
    STOCKED_SEQUENCE: "stocked",
    LOW_STOCK_SEQUENCE: "low",
    OUT_OF_STOCK_SEQUENCE: "out",
}


def _band_of(sequence: int) -> str:
    if sequence >= OUT_OF_STOCK_SEQUENCE:
        return "out"
    return _BAND_BY_SEQUENCE.get(sequence, "stocked")


def _confidence_band(confidence: float) -> str:
    if confidence >= _CONF_HIGH:
        return "high"
    if confidence >= _CONF_MEDIUM:
        return "medium"
    return "low"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _plural(n: int, unit: str = "day") -> str:
    return f"{n} {unit}{'s' if n != 1 else ''}"


def compute_belief(inputs: BeliefInputs) -> PantryBelief:
    """Pure belief inference. See module docstring for the model."""
    recorded = inputs.recorded_sequence
    today = inputs.today

    # ── 1. Manual override / fresh hard read wins ────────────────────────
    # A recent check (or a just-now level change) is ground truth; inference
    # must not argue with it. Prefer whichever hard signal is more recent.
    hard_dates = [d for d in (inputs.last_checked_at, inputs.stock_level_last_updated) if d]
    if recorded is not None and hard_dates:
        last_hard = max(hard_dates)
        days_since_hard = (today - last_hard).days
        if days_since_hard <= _HARD_SIGNAL_FRESH_DAYS:
            confirmed = inputs.last_checked_at is not None and inputs.last_checked_at == last_hard
            if confirmed:
                reason = (
                    "You confirmed this "
                    + ("today" if days_since_hard == 0 else f"{_plural(days_since_hard)} ago")
                    + "."
                )
            else:
                reason = (
                    "Updated "
                    + ("today" if days_since_hard == 0 else f"{_plural(days_since_hard)} ago")
                    + "."
                )
            return PantryBelief(
                believed_sequence=recorded,
                believed_band=_band_of(recorded),
                confidence=0.95,
                confidence_band="high",
                reason=reason,
                is_inferred=False,
                differs_from_recorded=False,
            )

    # ── 2. Cadence-based projection (the main inference path) ─────────────
    cadence_days: float | None = None
    if len(inputs.purchase_dates) >= _MIN_PURCHASE_DATES_FOR_CADENCE:
        cadence_days = mean_gap_days(inputs.purchase_dates)

    if cadence_days and inputs.purchase_dates:
        last_purchase = inputs.purchase_dates[-1]
        days_since_purchase = (today - last_purchase).days
        cooks_since_purchase = sum(
            1 for d in inputs.consumption_dates if d >= last_purchase
        )
        progress = days_since_purchase / cadence_days
        progress += _CONSUMPTION_WEIGHT * cooks_since_purchase

        if progress >= _PROGRESS_OUT:
            believed = OUT_OF_STOCK_SEQUENCE
        elif progress >= _PROGRESS_LOW:
            believed = LOW_STOCK_SEQUENCE
        else:
            believed = STOCKED_SEQUENCE

        # Confidence: richer purchase history + being closer to a fresh buy
        # (less extrapolation) = more confident. Deep extrapolation past a
        # full cycle is where an un-logged restock could have happened, so
        # confidence tapers — honesty over false certainty.
        data_factor = _clamp((len(inputs.purchase_dates) - 1) / 3.0, 0.25, 1.0)
        recency_factor = _clamp(1.1 - 0.5 * progress, 0.2, 1.0)
        confidence = _clamp(data_factor * recency_factor, 0.1, 0.95)

        reason = _cadence_reason(
            believed=believed,
            days_since_purchase=days_since_purchase,
            cadence_days=cadence_days,
            cooks_since_purchase=cooks_since_purchase,
        )
        differs = recorded is not None and believed != recorded
        return PantryBelief(
            believed_sequence=believed,
            believed_band=_band_of(believed),
            confidence=confidence,
            confidence_band=_confidence_band(confidence),
            reason=reason,
            is_inferred=True,
            differs_from_recorded=differs,
        )

    # ── 3. Thin data — lean on the recorded level, decay confidence ──────
    if recorded is not None:
        # How stale is the recorded level? Confidence decays the longer it
        # has been since any hard signal.
        ref = max(hard_dates) if hard_dates else None
        days_stale = (today - ref).days if ref else None
        confidence = _THIN_BASE_CONFIDENCE
        if days_stale is not None:
            # Halve confidence roughly every 30 stale days, floored low.
            confidence = _clamp(_THIN_BASE_CONFIDENCE * (0.5 ** (days_stale / 30.0)), 0.1, _THIN_BASE_CONFIDENCE)
        stale_str = (
            f" (last known {_plural(days_stale)} ago)" if days_stale is not None else ""
        )
        return PantryBelief(
            believed_sequence=recorded,
            believed_band=_band_of(recorded),
            confidence=confidence,
            confidence_band=_confidence_band(confidence),
            reason=f"Based on the last recorded level{stale_str}. Not enough history yet.",
            is_inferred=True,
            differs_from_recorded=False,
        )

    # ── 4. Nothing to go on ──────────────────────────────────────────────
    return PantryBelief(
        believed_sequence=STOCKED_SEQUENCE,
        believed_band="stocked",
        confidence=0.1,
        confidence_band="low",
        reason="Not sure yet. No purchases or checks on record.",
        is_inferred=True,
        differs_from_recorded=False,
    )


def _cadence_reason(
    *,
    believed: int,
    days_since_purchase: int,
    cadence_days: float,
    cooks_since_purchase: int,
) -> str:
    # Owner, 2026-09-12: no band prefix here. Every surface that shows this
    # reason already shows the believed band beside it ("Dora thinks low"), so
    # leading with "~Low — " said it twice. The tildes went with it — the
    # sentence already hedges in words ("about", "usual").
    cadence = round(cadence_days)
    bought = "Bought today" if days_since_purchase == 0 else f"Bought {_plural(days_since_purchase)} ago"
    cooked = (
        f", cooked with {cooks_since_purchase}× since"
        if cooks_since_purchase > 0 else ""
    )
    if believed == OUT_OF_STOCK_SEQUENCE:
        return f"{bought}{cooked}; your usual {cadence}-day supply should be gone."
    if believed == LOW_STOCK_SEQUENCE:
        return f"{bought}{cooked}; you usually finish in about {_plural(cadence)}."
    return f"{bought}{cooked}; you buy about every {_plural(cadence)}."


# ── Repo gathering ───────────────────────────────────────────────────────


def _household_date(value: datetime | date | None, tz: ZoneInfo) -> date | None:
    """Calendar day of a stored instant in the household zone (R-021).

    Stored timestamps are UTC (naive on SQLite); taking `.date()` of them put
    a morning level change on *yesterday* for every household east of
    Greenwich — "Updated 1 day ago" the moment you set it (finalisation
    07-R1; the same FU-525 class the buy verdict fixed).
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return as_utc(value).astimezone(tz).date()
    return value


def gather_belief_inputs(repository: SqlAlchemyRepository, item: StockItem) -> BeliefInputs:
    """Gather inputs for a single item (detail-page path)."""
    return gather_belief_inputs_for_items(repository, [item])[item.id]


def gather_beliefs_for_items(
    repository: SqlAlchemyRepository, items: list[StockItem],
) -> dict[UUID, PantryBelief]:
    """A belief per item in bulk (overview path), avoiding N+1."""
    return {
        item_id: compute_belief(inputs)
        for item_id, inputs in gather_belief_inputs_for_items(repository, items).items()
    }


def gather_belief_inputs_for_items(
    repository: SqlAlchemyRepository, items: list[StockItem],
) -> dict[UUID, BeliefInputs]:
    """The composer inputs per item, with a fixed number of queries
    (finalisation 07-R9: was one function returning either shape behind a
    private flag)."""
    if not items:
        return {}
    today = household_today(repository)
    tz = household_timezone(repository)
    item_ids = [i.id for i in items]
    # Resolved by foreign key rather than read off `item.stock_level`: the
    # relationship is `lazy="noload"` and an `.include()` doesn't reliably
    # populate it, which read as "this item has no recorded level" and sent
    # belief down its no-data path. See `_level_access`.
    levels_by_item = resolve_levels_by_item(repository, items)

    # Purchase dates — completed-list lines with a paid price, per item.
    lines: list[ShoppingListLine] = repository.get(ShoppingListLine).all(
        EntityField(ShoppingListLine, ShoppingListLine.Fields.STOCK_ITEM_ID).in_(item_ids)
    )
    list_ids = list({l.shopping_list_id for l in lines})
    completed_at_by_list: dict[UUID, datetime | None] = {}
    if list_ids:
        lists = repository.get(ShoppingList).all(
            EntityField(ShoppingList, "id").in_(list_ids)
        )
        for l in lists:
            if l.status == SHOPPING_LIST_STATUS_DONE:
                completed_at_by_list[l.id] = l.completed_at
    purchase_dates_by_item: dict[UUID, set[date]] = {i.id: set() for i in items}
    for line in lines:
        completed_at = completed_at_by_list.get(line.shopping_list_id)
        if completed_at is None:
            continue
        if line_paid_unit_price(line) is None:
            continue
        d = _household_date(completed_at, tz)
        if d is not None:
            purchase_dates_by_item.setdefault(line.stock_item_id, set()).add(d)

    # Consumption (depletion) dates per item.
    events: list[ConsumptionEvent] = repository.get(ConsumptionEvent).all(
        EntityField(ConsumptionEvent, ConsumptionEvent.Fields.STOCK_ITEM_ID).in_(item_ids)
    )
    consumption_dates_by_item: dict[UUID, list[date]] = {}
    for e in events:
        d = _household_date(e.occurred_at, tz)
        if d is not None:
            consumption_dates_by_item.setdefault(e.stock_item_id, []).append(d)

    out: dict[UUID, BeliefInputs] = {}
    for item in items:
        out[item.id] = BeliefInputs(
            recorded_sequence=(
                levels_by_item[item.id].sequence
                if levels_by_item.get(item.id) is not None else None
            ),
            stock_level_last_updated=_household_date(item.stock_level_last_updated, tz),
            last_checked_at=_household_date(item.last_checked_at, tz),
            purchase_dates=sorted(purchase_dates_by_item.get(item.id, set())),
            consumption_dates=sorted(consumption_dates_by_item.get(item.id, [])),
            today=today,
        )
    return out
