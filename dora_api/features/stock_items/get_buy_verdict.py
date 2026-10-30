"""P8-05 — "Should I buy this?" oracle.

    GET /api/stock-items/<id>/buy-verdict

Returns a per-item verdict {buy / wait / skip / unsure} plus a strength, a
confidence, per-axis reasons, a one-tap action, and the data the composer
reasoned from. See `docs/04_proposals/PROPOSAL_BUY_VERDICT_ORACLE.md` for the
full charter alignment + composition rules.

Design points that keep this honest:

* **Strength and confidence are different questions** (owner call
  2026-08-24). `strength` (0-3) is how much you should care; `confidence`
  is how good the evidence is. They used to be one dial, so "very likely
  worth buying, but I've only seen two shops" was unsayable and a
  well-evidenced weak call read the same as a guessed strong one.
* **Essential grades the need axis.** `strength` starts from
  `is_essential` x band — 3 for an essential you're out of, 1 for a
  non-essential you marked low — because `stock_attention.py` already
  ranks shortages on exactly that axis. Without it, the same item was
  "not worth a notification" there and "Worth buying now" here.
  The card's headline grades off it, so a non-essential you marked low
  reads "Might be worth buying" rather than "Worth buying now".
* **Personal data only.** Price samples come from completed shopping-
  list lines via the existing `line_paid_unit_price` ladder (R-003
  chokepoint). Cadence is derived inline. Waste rate reads
  `StockItemWasteEvent`. No external calls, no crowd data.
* **One cadence engine.** The `need` axis consumes `pantry_belief`
  (D-11 / `IMPL_PLAN_STOCK_SIGNAL_CONSOLIDATION.md`). It used to carry
  its own copy of belief's mean-gap math over belief's own inputs, so
  the two surfaces could state the same fact in different — sometimes
  contradictory — prose. Belief factors cook events; this never did.
* **Pure composer.** The axes are three pure functions
  (`_price_axis`, `_need_axis`, `_waste_axis`) that never touch a
  session; the endpoint fetches raw data once and passes it in. Tests
  drive the composer with fixture dataclasses — no DB, no HTTP.
* **Thin data collapses to `unsure`.** Charter P3 (Honest) + P12
  (No-invent) — the composer never fabricates a verdict from one
  sample.
"""
import logging
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import Optional
from uuid import UUID

from dora_api.persistence.aware import as_utc
from dora_api.domain.cadence_math import mean_gap_days
from dora_api.domain.entities.shopping_list import (
    SHOPPING_LIST_STATUS_DONE, ShoppingList, ShoppingListLine,
)
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_item_waste_event import StockItemWasteEvent
from dora_api.domain.entities.stock_level import StockLevel
from dora_api.domain.stock_status import (
    is_low_stock, is_out_of_stock,
)
from dora_api.features.app_settings.access import money_features_enabled
from dora_api.features.app_settings.clock import (
    household_timezone, household_today,
)
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.features.shopping_lists._line_price import line_paid_unit_price
from dora_api.features.stock_items._level_access import resolve_levels_by_item
from dora_api.features.stock_items.pantry_belief import (
    PantryBelief, gather_beliefs_for_items,
)
from dora_api.features.stock_items.planned_demand import (
    URGENCY_BLOCKING, URGENCY_WATCH, PlannedDemand, gather_planned_demand,
)
from dora_api.infrastructure.api_response import forbidden, not_found, ok
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


_LOGGER = logging.getLogger(__name__)

# Money is a prerequisite for the whole verdict surface, not a per-reason
# suppression (owner call 2026-08-27). Two of the three axes are price-driven:
# `_price_axis` reasons entirely in money, and the `wait` direction is only
# reachable via `above_usual` / `fake_markdown`. With money off, what's left is
# need + waste — which `PantryBeliefCard` and `stock_attention` already say, in
# the same words. So an install with money off gets no verdict at all rather
# than a dollar-branded restatement of its neighbour whose strength is still
# being silently modulated by price data the household opted out of.
#
# Shared with `get_list_buy_verdicts`, which gates identically.
MONEY_DISABLED_DETAIL = (
    "Buy verdicts need money features, which are turned off for this install."
)


def _local_date(dt: datetime, tz: tzinfo) -> date:
    """Calendar day of a (UTC) observation timestamp *in the household zone*.
    FU-525: bucketing UTC timestamps with a bare `.date()` while `today` is
    household-local (R-021) drifts the day by one for non-UTC households and can
    flip the wait-hint's `next_low <= today` staleness check. Take the date in
    the same zone as `today` so the two clocks agree."""
    return as_utc(dt).astimezone(tz).date()


# ── Tunables (single source, easy to iterate) ─────────────────────────

# Thin-data thresholds — see the proposal §2.3.
_MIN_PRICE_SAMPLES = 3
_MIN_UNIQUE_PURCHASE_DATES = 2
_MIN_PURCHASES_FOR_WASTE_RATE = 3

# "Cheapest in 3 months" and "usual price" bands. Both expressed as
# multiples of the trimmed-mean price so a heavy tail doesn't skew the
# call ("cheapest in months" needs to be materially cheaper, not $0.02
# under mean).
_CHEAP_BAND_FRACTION = 0.92    # ≤ 92% of usual → "cheapest"
_ABOVE_BAND_FRACTION = 1.08    # ≥ 108% of usual → "above usual"

# Waste-rate bands (events ÷ purchases over last 12 months).
_WASTES_OFTEN_RATE = 0.40
_WASTES_SOMETIMES_RATE = 0.10

# 12-month window for both price + waste rate; the shopping app is
# personal and seasonal, and a year is the smallest window that catches
# household patterns like "we only buy soy sauce every 6 months".
_HISTORY_WINDOW_DAYS = 365
_PRICE_RECENT_WINDOW_DAYS = 90   # "cheapest in 3 months" window

# ── Strength (owner call 2026-08-24) ──────────────────────────────────
# The need axis grades rather than switches. Before this, marking any item low
# produced "Worth buying now" — which contradicted `stock_attention.py`, whose
# whole point is that *"a non-essential item that is low or out does not need
# attention"*. The same item was therefore not worth a notification and worth
# buying now at the same time: the two-rules-for-one-idea defect (B4) that
# module was written to end. Grading on the same `is_essential` x band axis it
# already ranks on is what makes the two agree.
_MAX_STRENGTH = 3

# Keyed by the need axis's own signal, not its band, so there is nothing to
# translate between here and `_need_axis`. `thin_data` is absent and scores 0.
_STRENGTH_BY_NEED_SIGNAL = {"out_of_stock": 2, "low_stock": 1, "stocked": 0}
# A planned meal that needs an item you're short of lifts the buy by one; one
# that needs something you have changes nothing (owner 2026-10-15).
_PLAN_STRENGTH_MODIFIER = {URGENCY_WATCH: 1, URGENCY_BLOCKING: 1}
_PRICE_STRENGTH_MODIFIER = {"cheapest_3mo": 1, "above_usual": -1}
_WASTE_STRENGTH_MODIFIER = {"wastes_often": -2, "wastes_sometimes": -1}


# cycle detection for the `wait` verdict's time-boxed hint.
# Reuses `_CHEAP_BAND_FRACTION` to define a "low" (same threshold P8-05
# uses for `cheapest_3mo`), so there is one definition of "low" the whole
# oracle agrees on. We need ≥2 lows to measure a gap; the CV guard drops
# the hint when the observed cycle is too erratic to trust (Charter P3).
_MIN_LOWS_FOR_CYCLE = 2
_CYCLE_CV_MAX = 0.5


# ── DTOs — one shape shared by the composer + the response ────────────


@dataclass(frozen=True, slots=True)
class VerdictReasonDto:
    axis: str      # "price" | "need" | "waste" | "plan"
    signal: str    # see PROPOSAL §2.3
    label: str
    detail: Optional[str] = None
    # The two money amounts a price-axis detail line is about, unformatted.
    # The server never formats currency (D-006): it emits raw numbers and the
    # SPA renders them through `formatMoney`, so the install's currency +
    # locale apply. These used to be baked into `detail` as a hardcoded
    # `f"${x:.2f}"`, which rendered a dollar sign to a household on EUR.
    # Set only by `_price_axis`; every other axis leaves them None and uses
    # `detail` for its prose.
    amount_last: Optional[float] = None
    amount_usual: Optional[float] = None


@dataclass(frozen=True, slots=True)
class OneTapActionDto:
    kind: str      # "add_to_list" | "skip" | "mark_stocked" |
                   # "remove_from_list" | "none"
    label: str


@dataclass(frozen=True, slots=True)
class VerdictDataUsedDto:
    price_samples: int
    price_average: Optional[float]
    price_last: Optional[float]
    price_last_at: Optional[str]           # ISO date; SPA-friendly
    days_since_last_purchase: Optional[int]
    average_days_between_purchase: Optional[float]
    waste_events_last_12mo: int
    purchases_last_12mo: int
    stock_level_band: str                   # "out" | "low" | "stocked" | "unknown"


@dataclass(frozen=True, slots=True)
class WaitHintDto:
    """P8-06 — the time-boxed *when* attached to a `wait` verdict.

    Both fields are always populated when the DTO exists: `until` is the
    machine-readable expected next-low date (ISO), `reason` is the human
    explanation the card renders as a sub-caption. Fires only when the
    composer landed on `wait` AND `_wait_hint` found a confident cycle
    over the user's own price history.
    """
    until: str          # ISO date (yyyy-mm-dd) of the next expected low
    reason: str         # human "why" — always paired with `until`
    # Days from the household's today to `until` (R-021): the card's "in ~N
    # days" counts from here, not from the reader's browser date.
    days_until: int


@dataclass(frozen=True, slots=True)
class BuyVerdictDto:
    verdict: str                # "buy" | "wait" | "skip" | "unsure"
    confidence: str             # "high" | "medium" | "low"
    # How much you should care, 0-3 — see `_need_strength` and the module
    # docstring's strength table. Orthogonal to `confidence`, which is how good
    # the evidence is: "very likely worth buying, but I've only seen two shops"
    # needs both numbers to be sayable.
    strength: int
    reasons: list[VerdictReasonDto]
    one_tap_action: OneTapActionDto
    data_used: VerdictDataUsedDto
    # populated only on `wait` verdicts when a confident cycle
    # is detected. `None` otherwise (non-wait verdicts, thin data, or
    # unstable/overdue cycles — see `_wait_hint`).
    wait_hint: Optional[WaitHintDto] = None


# ── Raw inputs (fetched once by the endpoint, passed to composer) ─────


@dataclass(slots=True)
class VerdictInputs:
    # Prices are (unit_price, completed_at) tuples over the 12-month
    # window. Sorted newest-first.
    price_samples: list[tuple[float, datetime]] = field(default_factory=list)
    # Unique purchase dates over the window — used for cadence.
    unique_purchase_dates: list[date] = field(default_factory=list)
    waste_events_12mo: int = 0
    purchases_12mo: int = 0     # size of unique_purchase_dates
    stock_level_band: str = "unknown"        # "out" | "low" | "stocked" | "unknown"
    # The item's own Essential flag. The need axis grades on it — see
    # `_need_strength`; this is the same fact `stock_attention.is_essential_low`
    # reasons from, so the two surfaces agree about which shortages matter.
    is_essential: bool = False
    is_on_open_list: bool = False            # drives one_tap_action for "skip"
    today: date = field(default_factory=date.today)
    # Household zone (R-021 / FU-525) — the zone `today` is expressed in, and the
    # zone UTC observation timestamps are bucketed into via `_local_date` so the
    # two clocks agree. Defaults to UTC (tests build samples at UTC-noon).
    tz: tzinfo = timezone.utc
    # D-11 — Dora's inferred level for this item, or None when belief
    # wasn't gathered (older call sites / composer unit tests). When belief
    # has something to say the `need` axis prefers it over the recorded
    # level; see `_need_band`. Server-owned reasoning either way (R-003).
    belief: Optional[PantryBelief] = None
    # FU-450 — at least one product linked to this item is currently
    # running an inflated "special" (claims a saving, but the household has
    # paid less recently). Demotes a price-driven `buy` to `wait` and
    # surfaces the honesty reason. See `deals/deal_quality.py`.
    fake_markdown: bool = False
    # Owner 2026-10-15 — the stock page's planned-meals card belonged in here:
    # *"should be part of the buy verdict, no?"*. What the upcoming plan wants
    # of this item (`planned_demand.py`, the same allocation the planner reads).
    # None when nothing planned uses it.
    planned_demand: Optional[PlannedDemand] = None


# ── Per-axis composers — pure, testable ───────────────────────────────


def _trimmed_mean(values: list[float]) -> float:
    """Drop the single min + single max before averaging when we have
    ≥ 5 samples. Robust enough for household-scale shopping data
    without pulling in numpy."""
    if not values:
        return 0.0
    if len(values) >= 5:
        sorted_v = sorted(values)
        trimmed = sorted_v[1:-1]
        return sum(trimmed) / len(trimmed)
    return sum(values) / len(values)


def _price_axis(inputs: VerdictInputs) -> tuple[Optional[VerdictReasonDto], str]:
    """Return (reason, signal). `signal` is always set so the composer
    can key off it; `reason` is None when the axis contributes nothing
    (thin data)."""
    samples = inputs.price_samples
    if len(samples) < _MIN_PRICE_SAMPLES:
        return None, "thin_data"

    prices = [p for p, _ in samples]
    usual = _trimmed_mean(prices)
    last_price, last_at = samples[0]
    # Window boundary anchored to household-local midnight (R-021 / FU-525), so
    # the "cheapest in 3 months" cutoff agrees with `today`. Both sides are
    # tz-aware, so the comparison is a correct absolute-instant one.
    horizon = (
        datetime.combine(inputs.today, datetime.min.time(), tzinfo=inputs.tz)
        - timedelta(days=_PRICE_RECENT_WINDOW_DAYS)
    )
    recent = [p for p, ts in samples if ts >= horizon]
    recent_min = min(recent) if recent else last_price

    # Every branch carries the same two amounts; only the label differs. They
    # travel as numbers, not prose — see `VerdictReasonDto.amount_last`.
    amounts = {
        "amount_last": round(last_price, 2),
        "amount_usual": round(usual, 2),
    }

    if last_price <= _CHEAP_BAND_FRACTION * usual and last_price <= recent_min:
        return VerdictReasonDto(
            axis="price",
            signal="cheapest_3mo",
            label="Cheapest you've paid in 3 months",
            **amounts,
        ), "cheapest_3mo"
    if last_price >= _ABOVE_BAND_FRACTION * usual:
        return VerdictReasonDto(
            axis="price",
            signal="above_usual",
            label="Above your usual price",
            **amounts,
        ), "above_usual"
    return VerdictReasonDto(
        axis="price",
        signal="usual_price",
        label="Usual price",
        **amounts,
    ), "usual_price"


# Need-axis labels, keyed by band: (recorded, inferred). The inferred wording
# hedges because that band is Dora's guess disagreeing with what the user last
# recorded — asserting "You're out of stock" about an inference is exactly the
# overclaim Charter P3 (Honest) forbids.
_NEED_LABELS: dict[str, tuple[str, str]] = {
    "out": ("You're out of stock", "Probably out of stock"),
    "low": ("Running low", "Probably running low"),
    "stocked": ("Stocked", "Probably still stocked"),
}

_NEED_SIGNALS: dict[str, str] = {
    "out": "out_of_stock",
    "low": "low_stock",
    "stocked": "stocked",
}


def _need_band(inputs: VerdictInputs) -> tuple[str, bool]:
    """Resolve the band the `need` axis reasons from, and whether belief
    supplied it (D-11).

    Belief wins when it has signal; the recorded level is the floor. A
    low-confidence belief defers — it is the thin-data / no-history path, and
    a guess Dora wouldn't show the user as a chip has no business overruling
    a level that user set by hand.
    """
    belief = inputs.belief
    if belief is None or belief.confidence_band == "low":
        return inputs.stock_level_band, False
    return belief.believed_band, True


def _need_is_soft_inference(inputs: VerdictInputs) -> bool:
    """True when the need band is an inference that *disagrees* with the
    recorded level — the case where the composer should hedge (both in the
    label and in the verdict's confidence). Belief merely echoing what the
    user recorded is not soft; it is the recorded level."""
    band, from_belief = _need_band(inputs)
    if not from_belief:
        return False
    belief = inputs.belief
    assert belief is not None      # implied by from_belief
    return belief.is_inferred and band != inputs.stock_level_band


def _need_axis(inputs: VerdictInputs) -> tuple[Optional[VerdictReasonDto], str]:
    band, from_belief = _need_band(inputs)
    if band not in _NEED_SIGNALS:
        # Unknown stock band means we don't have a status at all, and belief
        # had nothing to add — treat as thin-data on this axis; the composer
        # will absorb the drop in confidence.
        return None, "thin_data"

    recorded_label, inferred_label = _NEED_LABELS[band]
    soft = _need_is_soft_inference(inputs)
    # When belief drove the band, its own `reason` is the explanation — one
    # voice for the cadence story instead of two phrasings of it.
    detail = (
        inputs.belief.reason if from_belief and inputs.belief is not None
        else _cadence_detail(inputs)
    )
    signal = _NEED_SIGNALS[band]
    return VerdictReasonDto(
        axis="need",
        signal=signal,
        label=inferred_label if soft else recorded_label,
        detail=detail,
    ), signal


def _cadence_detail(inputs: VerdictInputs) -> Optional[str]:
    """Fallback cadence prose for items with no belief (see `_need_band`).
    The averaging itself is shared (`domain/cadence_math.py`, R-003) so this
    can no longer drift from what belief says."""
    dates = inputs.unique_purchase_dates
    if len(dates) < _MIN_UNIQUE_PURCHASE_DATES:
        return None
    avg_days = mean_gap_days(dates)
    if avg_days is None:
        return None
    days_since = (inputs.today - dates[-1]).days
    if days_since >= avg_days:
        return f"Bought every ~{avg_days:.0f} days · last shop {days_since} days ago"
    remaining = max(0, int(round(avg_days - days_since)))
    return f"Bought every ~{avg_days:.0f} days · ~{remaining} days to run-out"


def _waste_axis(inputs: VerdictInputs) -> tuple[Optional[VerdictReasonDto], str]:
    if inputs.purchases_12mo < _MIN_PURCHASES_FOR_WASTE_RATE:
        # Not enough purchase history to compute a rate. Distinguish
        # "we've never seen you waste this" from "we don't know" via
        # the events count.
        if inputs.waste_events_12mo == 0:
            return None, "no_waste_history"
        return None, "thin_data"

    rate = inputs.waste_events_12mo / inputs.purchases_12mo
    if rate >= _WASTES_OFTEN_RATE:
        return VerdictReasonDto(
            axis="waste",
            signal="wastes_often",
            label=f"You've wasted this {int(round(rate * 100))}% of the time",
            detail=(
                f"{inputs.waste_events_12mo} thrown away vs "
                f"{inputs.purchases_12mo} purchased (last 12 months)"
            ),
        ), "wastes_often"
    if rate >= _WASTES_SOMETIMES_RATE:
        return VerdictReasonDto(
            axis="waste",
            signal="wastes_sometimes",
            label="Occasionally goes to waste",
            detail=(
                f"{inputs.waste_events_12mo} thrown away vs "
                f"{inputs.purchases_12mo} purchased (last 12 months)"
            ),
        ), "wastes_sometimes"
    return None, "no_waste_history"


# ── P8-06 — wait-hint (time-boxed hint on the `wait` verdict) ─────────


def _wait_hint(inputs: VerdictInputs) -> Optional[WaitHintDto]:
    """Predict *when* the user's usual low tends to land, so a `wait`
    verdict has time-boxed advice ("expect the next dip around Nov 15")
    instead of just "above your usual price".

    Pure function; the composer only calls this when it has already
    decided on `wait`. Returns None whenever the cycle prediction can't
    be made honestly — thin history, unstable cadence, or an overdue
    prediction (Charter P3 — silence beats a fabricated date)."""
    samples = inputs.price_samples
    if len(samples) < _MIN_PRICE_SAMPLES:
        return None

    prices = [p for p, _ in samples]
    usual = _trimmed_mean(prices)
    if usual <= 0:
        return None

    # Same "low" definition `_price_axis` uses for `cheapest_3mo` — one
    # threshold, not two. `low_dates` sorted oldest→newest so gaps read
    # left-to-right chronologically.
    low_dates = sorted({
        _local_date(ts, inputs.tz) for price, ts in samples
        if price <= _CHEAP_BAND_FRACTION * usual
    })
    if len(low_dates) < _MIN_LOWS_FOR_CYCLE:
        return None

    gaps = [
        (low_dates[i] - low_dates[i - 1]).days
        for i in range(1, len(low_dates))
    ]
    gaps = [g for g in gaps if g > 0]
    if not gaps:
        return None

    median_gap = statistics.median(gaps)
    if median_gap <= 0:
        return None
    # Coefficient of variation drops the hint when the cadence is too
    # erratic to trust ("prices swing wildly" isn't actionable timing).
    # `pstdev` (population) is safe for len==1; regular `stdev` needs 2+.
    stdev = statistics.pstdev(gaps) if len(gaps) >= 1 else 0.0
    if stdev / median_gap > _CYCLE_CV_MAX:
        return None

    next_low = low_dates[-1] + timedelta(days=int(round(median_gap)))
    if next_low <= inputs.today:
        # The cycle predicts a low that's already passed — the pattern
        # has broken (or prices shifted upward across the whole cycle).
        # Stay silent rather than surface a stale date.
        return None

    return WaitHintDto(
        until=next_low.isoformat(),
        days_until=(next_low - inputs.today).days,
        reason=(
            f"Your usual low lands ~every {int(round(median_gap))} days. "
            f"Expect the next around {next_low.strftime('%b %d')}."
        ),
    )


# ── The composer itself ────────────────────────────────────────────────


def _need_strength(inputs: VerdictInputs, need_signal: str) -> int:
    """Base strength from the need axis:

                    out   low   stocked
        essential    3     2      0
        normal       2     1      0

    Essential only lifts an actual shortage — an essential you already have
    plenty of is no more worth buying than any other stocked item.
    """
    base = _STRENGTH_BY_NEED_SIGNAL.get(need_signal, 0)
    if base > 0 and inputs.is_essential:
        base += 1
    return base


def _plan_axis(inputs: VerdictInputs) -> Optional[VerdictReasonDto]:
    """The planned-meals reason, or None when nothing upcoming needs it.

    It is a fact about the user's own plan, not evidence about the shelf, so it
    never costs confidence and never decides direction on its own. It adds to
    strength only when the recorded level says the plan is at risk (see
    `_PLAN_STRENGTH_MODIFIER`): a planned meal that needs something you're Low
    or Out of is more reason to buy than the shortage alone. When the item is
    already on an open list the need is handled, so the reason says so and adds
    nothing (FU-776).
    """
    demand = inputs.planned_demand
    if demand is None or demand.planned_meals <= 0:
        return None
    n = demand.needed_meals if demand.needed_meals > 0 else demand.planned_meals
    one = n == 1
    meals = f"{n} planned meal{'' if one else 's'}"
    if demand.urgency == URGENCY_BLOCKING:
        label = f"{meals} can't be cooked without it"
    elif demand.urgency == URGENCY_WATCH:
        label = f"{meals} {'needs' if one else 'need'} it, and you're low"
    else:
        label = f"{meals} {'uses' if one else 'use'} it"
    detail = demand.reason or None
    if _plan_is_handled(inputs):
        detail = f"{detail} Already on a shopping list." if detail else "Already on a shopping list."
    return VerdictReasonDto(
        axis="plan",
        signal=f"planned_{demand.urgency}",
        label=label,
        detail=detail,
    )


def _plan_is_handled(inputs: VerdictInputs) -> bool:
    """A shortfall the plan exposes is already on an open list, so pushing the
    buy harder would be double-counting it (FU-776)."""
    demand = inputs.planned_demand
    return (
        demand is not None
        and demand.urgency in _PLAN_STRENGTH_MODIFIER
        and inputs.is_on_open_list
    )


def compose_verdict(inputs: VerdictInputs) -> BuyVerdictDto:
    price_reason, price_signal = _price_axis(inputs)
    need_reason,  need_signal  = _need_axis(inputs)
    waste_reason, waste_signal = _waste_axis(inputs)
    plan_reason = _plan_axis(inputs)

    reasons: list[VerdictReasonDto] = []
    for r in (plan_reason, need_reason, price_reason, waste_reason):
        if r is not None:
            reasons.append(r)

    thin = [s for s in (price_signal, need_signal, waste_signal) if s == "thin_data"]

    # Three thin axes collapse to a single explicit "not enough history"
    # reason so the user sees one honest message rather than a wall of blanks.
    # The plan reason survives it: it is about the plan, not about history.
    if len(thin) == 3:
        return BuyVerdictDto(
            verdict="unsure",
            confidence="low",
            strength=0,
            reasons=([plan_reason] if plan_reason is not None else []) + [VerdictReasonDto(
                axis="need",
                signal="thin_data",
                label="Not enough history yet",
                detail="Log a few shops or waste events and Dora will start weighing in.",
            )],
            one_tap_action=OneTapActionDto(kind="none", label=""),
            data_used=_data_used_dto(inputs),
        )

    # Strength — how much you should care. Need sets the base, price and waste
    # modulate it; see the module docstring's table.
    strength = _need_strength(inputs, need_signal)
    strength += _PRICE_STRENGTH_MODIFIER.get(price_signal, 0)
    strength += _WASTE_STRENGTH_MODIFIER.get(waste_signal, 0)
    if inputs.planned_demand is not None and not _plan_is_handled(inputs):
        strength += _PLAN_STRENGTH_MODIFIER.get(inputs.planned_demand.urgency, 0)
    if inputs.fake_markdown:
        strength -= 1
    strength = max(0, min(_MAX_STRENGTH, strength))

    # Direction. Anything with strength left is a buy; at zero, the axis that
    # pushed it there decides how to say so. A fake markdown reads as `wait`
    # for the same reason `above_usual` does — there is a real price reason to
    # hold off, and a genuine special may well follow this one.
    if strength > 0:
        verdict = "buy"
    elif waste_signal == "wastes_often":
        verdict = "skip"
    elif price_signal == "above_usual" or inputs.fake_markdown:
        verdict = "wait"
    else:
        verdict = "unsure"

    # Confidence answers a different question: how good is the evidence? It
    # used to double as the strength dial (a `low`-stock item was "buy/medium"
    # purely because low is weaker than out), which is why a well-evidenced
    # weak call and a guessed strong one both read "medium". Each thin axis
    # costs a step; nothing else does.
    confidence = "high"
    for _ in thin:
        confidence = _step_down(confidence)

    # D-11 — a need band Dora *inferred*, against what the user last
    # recorded, is weaker evidence than a level they set themselves. Belief
    # can reach "high" on Low/Stocked with only ~3-4 logged purchases and has
    # no quantity awareness at all (plan §1.3), so a `buy/high` built on top of
    # one would overclaim. Step down; the reason still reads as a guess.
    if _need_is_soft_inference(inputs):
        confidence = _step_down(confidence)

    # FU-450 — an inflated markdown on a linked product is an honesty
    # signal, not a need signal. It costs a point of strength above (don't
    # celebrate a fake special) but can't overturn a genuine shortage — you're
    # out, you need it regardless of whether this particular "special" is real,
    # and an essential you're out of still lands at 2. Either way the reason
    # surfaces so the card is honest (Charter P8). Skipped on the thin-data
    # early return above — no verdict there to demote.
    if inputs.fake_markdown:
        reasons.insert(0, VerdictReasonDto(
            axis="price",
            signal="fake_markdown",
            label="Markdown looks inflated",
            detail="You've paid less than this \"special\" recently.",
        ))

    one_tap = _pick_action(verdict, inputs)
    # attach the time-boxed hint only when the verdict actually
    # landed on `wait`. The helper self-guards on thin/unstable/overdue
    # cycles, so a `wait` with unreliable history simply gets `None`.
    wait_hint = _wait_hint(inputs) if verdict == "wait" else None
    return BuyVerdictDto(
        verdict=verdict,
        confidence=confidence,
        strength=strength,
        reasons=reasons,
        one_tap_action=one_tap,
        data_used=_data_used_dto(inputs),
        wait_hint=wait_hint,
    )


def _step_down(confidence: str) -> str:
    return {"high": "medium", "medium": "low", "low": "low"}[confidence]


def _pick_action(verdict: str, inputs: VerdictInputs) -> OneTapActionDto:
    if verdict == "buy":
        return OneTapActionDto(kind="add_to_list", label="Add to list")
    if verdict == "skip":
        if inputs.is_on_open_list:
            return OneTapActionDto(kind="remove_from_list", label="Remove from list")
        # Well-stocked + wasteful ⇒ nudge to close the loop on inventory.
        return OneTapActionDto(kind="mark_stocked", label="Already stocked")
    if verdict == "wait":
        return OneTapActionDto(kind="skip", label="Skip for now")
    # `unsure` — no action; the user makes the call.
    return OneTapActionDto(kind="none", label="")


def _data_used_dto(inputs: VerdictInputs) -> VerdictDataUsedDto:
    price_average: Optional[float] = None
    price_last: Optional[float] = None
    price_last_at: Optional[str] = None
    if inputs.price_samples:
        prices = [p for p, _ in inputs.price_samples]
        price_average = round(_trimmed_mean(prices), 2)
        price_last = round(inputs.price_samples[0][0], 2)
        price_last_at = _local_date(inputs.price_samples[0][1], inputs.tz).isoformat()

    days_since: Optional[int] = None
    avg_days: Optional[float] = None
    dates = inputs.unique_purchase_dates
    if dates:
        days_since = max(0, (inputs.today - dates[-1]).days)
    if len(dates) >= _MIN_UNIQUE_PURCHASE_DATES:
        mean_gap = mean_gap_days(dates)
        if mean_gap is not None:
            avg_days = round(mean_gap, 1)

    return VerdictDataUsedDto(
        price_samples=len(inputs.price_samples),
        price_average=price_average,
        price_last=price_last,
        price_last_at=price_last_at,
        days_since_last_purchase=days_since,
        average_days_between_purchase=avg_days,
        waste_events_last_12mo=inputs.waste_events_12mo,
        purchases_last_12mo=inputs.purchases_12mo,
        stock_level_band=inputs.stock_level_band,
    )


# ── Data gathering (the only part that touches the repo) ──────────────


def _stock_level_band(level: StockLevel | None) -> str:
    if level is None:
        return "unknown"
    if is_out_of_stock(level):
        return "out"
    if is_low_stock(level):
        return "low"
    return "stocked"


def gather_verdict_inputs_for_items(
    repository: SqlAlchemyRepository, items: list[StockItem],
) -> dict[UUID, VerdictInputs]:
    """Gather composer inputs for many items with a fixed number of queries.

    B6 — every surface that shows more than one verdict used to fetch them a
    row at a time (`useBuyVerdict` per stock row, `BuyVerdictBadgeInline` per
    shopping-list line), so a 40-line list meant 40 requests each doing this
    walk for a single item. Shaped on `gather_beliefs_for_items`.

    The items need no `.include()`: the recorded level is resolved by foreign
    key (see `_level_access`), not off the relationship.
    """
    if not items:
        return {}

    today = household_today(repository)
    tz = household_timezone(repository)
    horizon_start = datetime.combine(
        today - timedelta(days=_HISTORY_WINDOW_DAYS),
        datetime.min.time(), tzinfo=tz,
    )
    item_ids = [i.id for i in items]

    # Shopping-list lines for every item, bucketed per item.
    lines: list[ShoppingListLine] = repository.get(ShoppingListLine).all(
        EntityField(ShoppingListLine, ShoppingListLine.Fields.STOCK_ITEM_ID).in_(item_ids)
    )
    lines_by_item: dict[UUID, list[ShoppingListLine]] = {}
    for line in lines:
        lines_by_item.setdefault(line.stock_item_id, []).append(line)

    list_ids = list({l.shopping_list_id for l in lines})
    completed_lookup: dict[UUID, datetime | None] = {}
    open_list_ids: set[UUID] = set()
    if list_ids:
        lists = repository.get(ShoppingList).all(
            EntityField(ShoppingList, "id").in_(list_ids)
        )
        for l in lists:
            if l.status == SHOPPING_LIST_STATUS_DONE:
                completed_lookup[l.id] = as_utc(l.completed_at)
            else:
                open_list_ids.add(l.id)

    # Waste events over the same window, counted per item.
    waste_events: list[StockItemWasteEvent] = repository.get(StockItemWasteEvent).all(
        EntityField(StockItemWasteEvent, StockItemWasteEvent.Fields.STOCK_ITEM_ID).in_(item_ids)
    )
    waste_in_window_by_item: dict[UUID, int] = {}
    for e in waste_events:
        if e.occurred_at and as_utc(e.occurred_at) >= horizon_start:
            waste_in_window_by_item[e.stock_item_id] = (
                waste_in_window_by_item.get(e.stock_item_id, 0) + 1
            )

    # D-11 — the need axis reasons from belief, so gather that in bulk too.
    beliefs = gather_beliefs_for_items(repository, items)
    levels_by_item = resolve_levels_by_item(repository, items)
    fake_markdown_items = _items_with_fake_markdown(repository, item_ids)
    demand_by_item = gather_planned_demand(
        repository,
        recorded_by_item={
            item_id: level.sequence
            for item_id, level in levels_by_item.items()
            if level is not None
        },
    )

    out: dict[UUID, VerdictInputs] = {}
    for item in items:
        item_lines = lines_by_item.get(item.id, [])
        samples: list[tuple[float, datetime]] = []
        for line in item_lines:
            # R-061 — only a bought line is a purchase: ticked, and not
            # deferred by trim-to-budget (same rule as `spend_lines`).
            if not line.is_ticked or line.deferred_by_budget:
                continue
            completed_at = completed_lookup.get(line.shopping_list_id)
            if completed_at is None:
                continue
            if completed_at < horizon_start:
                continue
            price = line_paid_unit_price(line)
            if price is None:
                continue
            samples.append((price, completed_at))
        samples.sort(key=lambda s: s[1], reverse=True)
        unique_dates = sorted({_local_date(s[1], tz) for s in samples})

        out[item.id] = VerdictInputs(
            price_samples=samples,
            unique_purchase_dates=unique_dates,
            waste_events_12mo=waste_in_window_by_item.get(item.id, 0),
            purchases_12mo=len(unique_dates),
            stock_level_band=_stock_level_band(levels_by_item.get(item.id)),
            is_essential=item.is_essential,
            is_on_open_list=any(
                line.shopping_list_id in open_list_ids for line in item_lines
            ),
            today=today,
            tz=tz,
            belief=beliefs.get(item.id),
            fake_markdown=item.id in fake_markdown_items,
            planned_demand=demand_by_item.get(item.id),
        )
    return out


def _gather_inputs(
    repository: SqlAlchemyRepository, item: StockItem,
) -> VerdictInputs:
    """Single-item path (the detail endpoint). Delegates to the bulk gather so
    there is one definition of what the composer reasons from (R-003)."""
    return gather_verdict_inputs_for_items(repository, [item])[item.id]


def _items_with_fake_markdown(
    repository: SqlAlchemyRepository, stock_item_ids: list[UUID],
) -> set[UUID]:
    """FU-450 — the subset of these items with a linked product running an
    inflated markdown right now. Delegates the per-product judgement to the
    shared `deal_quality` signal (R-003 — one definition of "fake"); the
    per-product answer is memoised because one product can be linked to
    several stock items."""
    from sqlalchemy import select
    from dora_api.app import db
    from dora_api.features.deals.deal_quality import get_deal_quality

    if not stock_item_ids:
        return set()

    link_table = db.metadata.tables["StockItemProduct"]
    rows = db.session.execute(
        select(link_table.c.stock_item_id, link_table.c.product_id).where(
            link_table.c.stock_item_id.in_(stock_item_ids)
        )
    ).all()

    fake_by_product: dict[UUID, bool] = {}
    out: set[UUID] = set()
    for stock_item_id, product_id in rows:
        if product_id not in fake_by_product:
            dq = get_deal_quality(product_id, repository)
            fake_by_product[product_id] = dq is not None and dq.fake_markdown
        if fake_by_product[product_id]:
            out.add(stock_item_id)
    return out


# ── Endpoint ───────────────────────────────────────────────────────────


@STOCK_ITEM_ROUTER.route("/<uuid:stock_item_id>/buy-verdict", methods=["GET"])
def get_buy_verdict(stock_item_id: UUID):
    repo = SqlAlchemyRepository()
    if not money_features_enabled(repo):
        return forbidden(MONEY_DISABLED_DETAIL)
    # No `.include(STOCK_LEVEL)` here: the gather resolves the recorded level
    # by foreign key (`_level_access`) because the include doesn't reliably
    # hydrate it, which is what made this endpoint answer `unsure/low` for
    # every item. Asking for an include we don't read would be theatre.
    item: StockItem | None = repo.get(StockItem).by_id(stock_item_id)
    if item is None:
        return not_found("StockItem", stock_item_id)
    inputs = _gather_inputs(repo, item)
    verdict = compose_verdict(inputs)
    _LOGGER.debug(
        "buy-verdict %s → %s/%s (%d reasons, %d price samples, %d waste events)",
        stock_item_id, verdict.verdict, verdict.confidence,
        len(verdict.reasons), len(inputs.price_samples), inputs.waste_events_12mo,
    )
    return ok(verdict)
