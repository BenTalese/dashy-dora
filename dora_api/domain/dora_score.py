"""P8-08 — The Dora Score.

A single, honest, explainable kitchen-health metric derived from four
signals: three over a rolling 30-day window, one over the week ahead (§P8-08 in
``docs/01_charter/DASHY_DORA_CHAMPION_PLAN.md``). Renders on the
dashboard as one composite number + a per-component breakdown + a
trend arrow (score vs. same score computed 7 days ago).

Design shape follows **R-027 + ADR-023** — a pure decision core with
no repository or DB access. The endpoint handler
(``features/dashboard/get_dora_score.py``) gathers the raw inputs and
delegates to :func:`compute_score` here. The same pattern is already
used for :mod:`buy_verdict` and :mod:`pantry_belief`; keeping the
score consistent with them means the unit tests never need a
database.

Charter guardrails baked in:

* **P3 Honest** — a component that has no data in the window is
  *excluded* from the mean (its weight goes to zero), not treated as
  zero. A user with no budget set doesn't drag the score down; a
  user with no waste tracking gets a 4-signal score, not a fake 5th.
* **P1 Effortless** — the score never nags; the frontend renders it
  as a positive-framed number ("you're at 72") with actions that
  *improve* the weak component, never "you failed at X".
* **R-003** — the score itself, the components, and their thresholds
  live server-side. The client renders whatever the server hands it.
* **R-010** — the component keys form a closed set (see
  :class:`DoraScoreComponentKey`). No stringly-typed enums.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import List


# Rolling window every component is evaluated over. 30 days matches
# typical grocery cadence (~4 weekly shops) and gives the 7-day-delta
# trend arrow something to move against without becoming twitchy. Not
# user-configurable — the score compares like-for-like across users.
DORA_SCORE_WINDOW_DAYS = 30

# The 7-day-back window the trend arrow compares against — a full 30-day
# window ending 7 days ago. So the arrow answers: "compared to the same
# 30-day view a week ago, are you trending up or down?"
DORA_SCORE_TREND_LAG_DAYS = 7


class DoraScoreComponentKey(str, Enum):
    """R-010 closed set. Same keys are used on the wire and by the SPA
    to route each component to a remediating action.

    **Owner review, 2026-09-04.** He asked whether these were the right
    signals: *"Run-outs seems like an odd metric to base kitchen health on.
    Are we sure we have the best set of metrics for this score? We want it to
    be useful, not fluff/bloat."* Two were cut, two added, on one test — does
    the component measure a **kitchen outcome**, or does it measure **how
    diligently you use the app**?

      RUNOUTS (cut)    scored "you ran out of something that wasn't on a
                       list". Defensible in principle — a well-run kitchen
                       isn't surprised — but it only fires for households
                       that log consumption, so it graded logging, and it
                       punished a household for running a pantry deliberately
                       tight. FU-835 had already made the same case about its
                       neighbour.
      STOCKTAKE (cut)  scored "% of items you checked in the last 30 days",
                       which is entirely an activity metric: doing a stocktake
                       does not make the kitchen healthier, it makes Dora's
                       picture of it more accurate. That is FU-835 verbatim,
                       and cutting it resolves that follow-up.
      PLAN_ADHERENCE   did what you planned actually get settled on the
      (cut 09-27)      reconcile queue? The owner cut it as a bit dumb: it
                       graded keeping up with admin, not the kitchen.
      PLAN_COVERAGE    can your pantry actually cook the week you planned?
      (new)            The one forward-looking signal: every other component
                       grades the last 30 days, this one grades the next 7.
    """
    WASTE = "waste"
    BUDGET = "budget"
    FRESHNESS = "freshness"
    PLAN_COVERAGE = "plan_coverage"


@dataclass(frozen=True, slots=True)
class DoraScoreComponent:
    """One of the signals contributing to the composite."""
    key: DoraScoreComponentKey
    label: str
    # 0-100 (higher = healthier), or None when we lack the data to
    # score this component in the window. None components are
    # *excluded* from the mean (see ``composite`` in
    # ``compute_score`` below), not treated as zero.
    score: int | None
    # One short user-facing sentence explaining why the score is what
    # it is. Charter P3 — the score must be explainable. Kept
    # server-side so we can retune wording without a SPA release.
    reason: str


@dataclass(frozen=True, slots=True)
class DoraScoreDto:
    """Wire shape. Full recompute (both windows) fits in a single
    endpoint hit, so the trend arrow travels with the score itself."""
    # 0-100 composite, or None when NOT ONE of the components has
    # any data (a brand-new install). SPA renders "getting started"
    # copy in that case instead of a zero.
    composite: int | None
    components: List[DoraScoreComponent] = field(default_factory=list)
    # Score - (score 7 days ago) = trend. None when we can't compute
    # both windows (e.g. brand-new install, or lagging window has no
    # data at all). Positive = improving, negative = declining.
    trend_delta: int | None = None
    # "up" | "down" | "flat" | None — precomputed for the SPA so it
    # doesn't have to know about the +/- 2 hysteresis band.
    trend_direction: str | None = None
    # Days in the evaluation window; travels for the SPA caption so
    # any future tuning doesn't require a wire-shape change.
    window_days: int = DORA_SCORE_WINDOW_DAYS


@dataclass(frozen=True, slots=True)
class DoraScoreInputs:
    """Everything :func:`compute_score` needs, prepared by the handler.
    Isolated so the pure function stays trivially unit-testable — no
    repository, no clock, no config lookups inside the core.

    Every count / value here is aggregated against the *current*
    30-day window ending at ``now``. The 7-day-lagged window is passed
    as a second ``DoraScoreInputs`` to compute the trend.
    """
    now: datetime
    # Waste — number of StockItemWasteEvent rows in the window. Any
    # waste event counts, regardless of reason (expired, spoiled, etc.).
    waste_event_count: int
    # Budget — whether a budget is configured, and how much you're
    # over/under. `over_pct` is spent / budgeted - 1 (so 0.15 = 15% over).
    # `has_budget=False` excludes budget from the composite.
    has_budget: bool
    budget_over_pct: float | None
    # Freshness — count of tracked stock items whose ``expiry_date``
    # has passed as of ``now``, over the total tracked-with-expiry set.
    # We only score if any items track expiry at all; otherwise the
    # signal is dormant and excluded.
    expired_item_count: int
    total_items_with_expiry: int
    # Plan coverage — of the meals planned for the next 7 days, how many the
    # pantry can currently cook (no missing ingredients). Entries whose
    # cookability is unknown (unlinked ingredients, empty recipe) are excluded
    # from BOTH counts by the handler rather than being scored as failures:
    # "I can't tell" is not "you can't cook it".
    upcoming_planned_meals: int
    upcoming_cookable_meals: int
    # FU-823 / R-058 — whether this install has money features on.
    #
    # The budget signal reasons entirely in money, so on a money-off install it
    # must not be gathered, must not weight the composite, and must not appear
    # in the component list at all (a dormant "Budget — no budget set" row with
    # a "Set a budget →" link is still a money surface). R-058's test: with the
    # flag off, is what remains correct? Yes — the mean of the other four
    # signals is a valid kitchen-health score. So budget is a *dependent*
    # signal, dropped rather than zeroed.
    #
    # Defaults True so the existing pure-core tests keep exercising the
    # money-on path unchanged; the handler always passes it explicitly.
    money_enabled: bool = True


def compute_score(inputs: DoraScoreInputs) -> DoraScoreDto:
    """Compute the current-window score (no trend). The endpoint calls
    this twice — once with current inputs, once with lagged inputs —
    and stitches the trend on top."""
    components: list[DoraScoreComponent] = [_score_waste(inputs)]
    # FU-823 / R-058 — the budget signal is *omitted*, not dormant, when money
    # features are off. A dormant component still renders a row on the card
    # (with its "Set a budget →" action), which is a money surface on an install
    # that opted out of money. The composite stays correct because
    # `_composite_of` means over applicable components either way.
    if inputs.money_enabled:
        components.append(_score_budget(inputs))
    components.extend([
        _score_freshness(inputs),
        _score_plan_coverage(inputs),
    ])
    composite = _composite_of(components)
    return DoraScoreDto(
        composite=composite,
        components=components,
        trend_delta=None,
        trend_direction=None,
    )


def compose_with_trend(
    current: DoraScoreDto,
    lagged: DoraScoreDto | None,
) -> DoraScoreDto:
    """Stitch a trend arrow onto ``current`` using ``lagged`` (the
    score computed for the 30d window ending 7 days ago). Kept
    separate so the endpoint can skip the lagged compute cheaply if
    the user's data doesn't span a week yet."""
    if current.composite is None or lagged is None or lagged.composite is None:
        return current
    delta = current.composite - lagged.composite
    # Hysteresis: don't render an arrow for tiny drift (±2 points).
    # The composite is 0-100 and each component is a mean of a small
    # integer signal — 2 points isn't a real change.
    if abs(delta) < 2:
        direction = "flat"
    elif delta > 0:
        direction = "up"
    else:
        direction = "down"
    return DoraScoreDto(
        composite=current.composite,
        components=current.components,
        trend_delta=delta,
        trend_direction=direction,
        window_days=current.window_days,
    )


# ── Per-component scoring ────────────────────────────────────────────

def _score_waste(inputs: DoraScoreInputs) -> DoraScoreComponent:
    # Zero waste in the window = 100. Each waste event costs 10
    # points, floored at 0 — 10 events (≈ two thrown-out things a
    # week) tanks the component. The 10-point step is a UX-tuning
    # knob rather than a load-bearing science number; the honest
    # signal is "any waste at all", the granularity is presentation.
    count = inputs.waste_event_count
    score = max(0, 100 - count * 10)
    if count == 0:
        reason = "No waste logged in the last 30 days."
    elif count == 1:
        reason = "1 waste event logged in the last 30 days."
    else:
        reason = f"{count} waste events logged in the last 30 days."
    return DoraScoreComponent(
        key=DoraScoreComponentKey.WASTE,
        label="Waste",
        score=score,
        reason=reason,
    )


def _score_budget(inputs: DoraScoreInputs) -> DoraScoreComponent:
    if not inputs.has_budget:
        return DoraScoreComponent(
            key=DoraScoreComponentKey.BUDGET,
            label="Budget",
            score=None,
            reason="No budget set, so this is skipped.",
        )
    over = inputs.budget_over_pct if inputs.budget_over_pct is not None else 0.0
    if over <= 0:
        return DoraScoreComponent(
            key=DoraScoreComponentKey.BUDGET,
            label="Budget",
            score=100,
            reason="Under budget this period.",
        )
    # Over by X%: linear penalty. 100% over → 0. The over_pct is a
    # ratio (0.15 = 15% over), so a 1.0 ratio tanks the component.
    score = max(0, int(round(100 - over * 100)))
    return DoraScoreComponent(
        key=DoraScoreComponentKey.BUDGET,
        label="Budget",
        score=score,
        reason=f"Over budget by {int(round(over * 100))}% this period.",
    )


def _score_freshness(inputs: DoraScoreInputs) -> DoraScoreComponent:
    total = inputs.total_items_with_expiry
    if total <= 0:
        return DoraScoreComponent(
            key=DoraScoreComponentKey.FRESHNESS,
            label="Freshness",
            score=None,
            reason="No stock items track an expiry date yet.",
        )
    expired = inputs.expired_item_count
    # % of tracked-with-expiry items that AREN'T past their date.
    score = int(round(100 - (expired / total) * 100))
    score = max(0, min(100, score))
    if expired == 0:
        reason = "Nothing expired sitting in your pantry."
    elif expired == 1:
        reason = "1 item past its expiry date."
    else:
        reason = f"{expired} items past their expiry dates."
    return DoraScoreComponent(
        key=DoraScoreComponentKey.FRESHNESS,
        label="Freshness",
        score=score,
        reason=reason,
    )


def _score_plan_coverage(inputs: DoraScoreInputs) -> DoraScoreComponent:
    """Can the pantry cook the week you planned?

    The one **forward**-looking component. Every other signal grades the
    trailing 30 days; this one grades the next 7, which means it contributes
    nothing to the trend arrow — the lagged recompute sees the same future and
    returns the same number, so it cancels in the delta. That is a real
    limitation and it is the right trade: the arrow is a secondary flourish,
    and "your plan is half-uncookable" is the single most actionable thing this
    card can say. Anyone re-tuning the trend should know it moves on three
    signals, not four.
    """
    total = inputs.upcoming_planned_meals
    if total <= 0:
        return DoraScoreComponent(
            key=DoraScoreComponentKey.PLAN_COVERAGE,
            label="Plan coverage",
            score=None,
            reason="Nothing planned for the week ahead.",
        )
    cookable = max(0, min(inputs.upcoming_cookable_meals, total))
    score = int(round((cookable / total) * 100))
    score = max(0, min(100, score))
    if cookable == total:
        reason = "You can cook everything you've planned this week."
    elif cookable == 0:
        reason = f"None of your {total} planned meals can be cooked right now."
    else:
        reason = f"{cookable} of {total} planned meals can be cooked right now."
    return DoraScoreComponent(
        key=DoraScoreComponentKey.PLAN_COVERAGE,
        label="Plan coverage",
        score=score,
        reason=reason,
    )


def _composite_of(components: list[DoraScoreComponent]) -> int | None:
    """Equal-weight mean of *applicable* components (None-scored
    components are excluded, not zeroed). None when nothing scored —
    a brand-new install has nothing to say about kitchen health."""
    scored = [c.score for c in components if c.score is not None]
    if not scored:
        return None
    return int(round(sum(scored) / len(scored)))


# ── Helpers used by the handler ──────────────────────────────────────

def window_start(now: datetime) -> datetime:
    """Start of the current evaluation window."""
    return now - timedelta(days=DORA_SCORE_WINDOW_DAYS)


def lagged_window_start(now: datetime) -> datetime:
    """Start of the 7-day-lagged window (for trend)."""
    return now - timedelta(days=DORA_SCORE_WINDOW_DAYS + DORA_SCORE_TREND_LAG_DAYS)


def lagged_window_end(now: datetime) -> datetime:
    """End of the 7-day-lagged window (exclusive)."""
    return now - timedelta(days=DORA_SCORE_TREND_LAG_DAYS)

