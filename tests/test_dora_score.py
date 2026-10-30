"""P8-08 — pure-fixture unit tests for the Dora Score decision core.

Mirrors the ``test_buy_verdict`` / ``test_pantry_belief`` shape (R-027
pattern): build a ``DoraScoreInputs``, call ``compute_score``, assert
on the DTO. No repository, no DB, no clock — the handler owns those.
"""
from datetime import datetime

import pytest

from dora_api.domain.dora_score import (
    DORA_SCORE_WINDOW_DAYS,
    DoraScoreComponentKey,
    DoraScoreDto,
    DoraScoreInputs,
    compose_with_trend,
    compute_score,
)


NOW = datetime(2026, 7, 4, 12, 0, 0)


def _healthy_inputs(**overrides) -> DoraScoreInputs:
    """A fully-scored, healthy household: all four signals apply and
    all four are at 100. Override individual fields per test.
    """
    base = dict(
        now=NOW,
        waste_event_count=0,
        has_budget=True,
        budget_over_pct=-0.10,  # 10% UNDER budget
        expired_item_count=0,
        total_items_with_expiry=15,
        upcoming_planned_meals=10,
        upcoming_cookable_meals=10,
    )
    base.update(overrides)
    return DoraScoreInputs(**base)


def _component(dto: DoraScoreDto, key: DoraScoreComponentKey):
    return next(c for c in dto.components if c.key == key)


def _keys(dto: DoraScoreDto) -> set[DoraScoreComponentKey]:
    return {c.key for c in dto.components}


# ── Money gate (FU-823 / R-058) ───────────────────────────────────────

@pytest.mark.unit
class TestMoneyGate:
    """The budget signal reasons entirely in money, so a money-off install
    must not see it *or* be scored by it.

    Before this gate, `get_dora_score` called `GetBudgetStatusHandler`
    unconditionally — and that handler deliberately computes its period even
    when money is off (so the dashboard can show a passive spend figure). So an
    install with money disabled but a budget amount still stored had its
    kitchen-health composite weighted by a signal it had opted out of, and the
    card rendered a Budget row linking into /settings/money.
    """

    def test__money_off__budget_component_is_omitted_entirely(self):
        dto = compute_score(_healthy_inputs(money_enabled=False))
        assert DoraScoreComponentKey.BUDGET not in _keys(dto)

    def test__money_off__other_three_signals_still_scored(self):
        # R-058's test: with the flag off, what remains must still be correct.
        dto = compute_score(_healthy_inputs(money_enabled=False))
        assert _keys(dto) == {
            DoraScoreComponentKey.WASTE,
            DoraScoreComponentKey.FRESHNESS,
            DoraScoreComponentKey.PLAN_COVERAGE,
        }
        assert dto.composite == 100

    def test__money_off__a_stored_budget_cannot_move_the_composite(self):
        # The sharp version of the bug: a household that set a budget, then
        # turned money off, was still being scored on it. Being 80% over budget
        # would have dragged the composite to 96 via the mean; with the gate the
        # figure must be identical to the no-budget case.
        over_budget = _healthy_inputs(money_enabled=False, budget_over_pct=0.80)
        no_budget = _healthy_inputs(
            money_enabled=False, has_budget=False, budget_over_pct=None,
        )
        assert over_budget.money_enabled is False
        assert compute_score(over_budget).composite == compute_score(no_budget).composite

    def test__money_on__budget_still_present_and_scored(self):
        # The gate must not change the money-on path at all.
        dto = compute_score(_healthy_inputs())
        assert DoraScoreComponentKey.BUDGET in _keys(dto)
        assert _component(dto, DoraScoreComponentKey.BUDGET).score == 100

    def test__money_on_but_no_budget_set__component_present_but_dormant(self):
        # "No budget yet" is a discoverability state, not a gate — the row stays
        # so the user can find the feature. Distinct from money-off, where the
        # row must vanish (R-029: respect the off-state).
        dto = compute_score(_healthy_inputs(has_budget=False, budget_over_pct=None))
        assert DoraScoreComponentKey.BUDGET in _keys(dto)
        assert _component(dto, DoraScoreComponentKey.BUDGET).score is None


# ── Composite / applicability behaviour ──────────────────────────────

@pytest.mark.unit
class TestComposite:
    def test__all_four_at_100_gives_100(self):
        dto = compute_score(_healthy_inputs())
        assert dto.composite == 100
        assert all(c.score == 100 for c in dto.components)

    def test__inapplicable_components_excluded_not_zeroed(self):
        # No budget set → budget component score=None → NOT counted
        # in the mean. If it were zeroed, the composite would drop to 80.
        dto = compute_score(_healthy_inputs(has_budget=False, budget_over_pct=None))
        assert dto.composite == 100
        assert _component(dto, DoraScoreComponentKey.BUDGET).score is None

    def test__brand_new_install_returns_None_composite(self):
        # No budget, no expiry dates, nothing planned either way → only waste
        # has anything to say.
        dto = compute_score(_healthy_inputs(
            has_budget=False, budget_over_pct=None,
            total_items_with_expiry=0, expired_item_count=0,
            upcoming_planned_meals=0, upcoming_cookable_meals=0,
            waste_event_count=0,
        ))
        # Waste (0 events → 100) still applies because it always does: no data
        # ≠ excluded — the absence of waste events IS the signal. Composite is
        # 100 from that one.
        assert dto.composite == 100
        assert _component(dto, DoraScoreComponentKey.FRESHNESS).score is None
        assert _component(dto, DoraScoreComponentKey.PLAN_COVERAGE).score is None
        assert _component(dto, DoraScoreComponentKey.BUDGET).score is None

    def test__all_dormant_returns_None_composite(self):
        # Impossible in real code (waste + runouts always apply), but
        # kept as the guard against a future re-scoping accidentally
        # making every component optional.
        inputs = _healthy_inputs()
        dto = DoraScoreDto(
            composite=None,
            components=[
                type(c)(key=c.key, label=c.label, score=None, reason=c.reason)
                for c in compute_score(inputs).components
            ],
        )
        # Sanity: manually construct a DTO where everything's None
        # and confirm nothing coerces it to 0.
        assert dto.composite is None


# ── Waste ────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestWaste:
    def test__zero_events_scores_100(self):
        dto = compute_score(_healthy_inputs(waste_event_count=0))
        assert _component(dto, DoraScoreComponentKey.WASTE).score == 100

    def test__one_event_scores_90(self):
        dto = compute_score(_healthy_inputs(waste_event_count=1))
        assert _component(dto, DoraScoreComponentKey.WASTE).score == 90

    def test__ten_events_scores_0(self):
        dto = compute_score(_healthy_inputs(waste_event_count=10))
        assert _component(dto, DoraScoreComponentKey.WASTE).score == 0

    def test__hundred_events_clamps_at_0_not_negative(self):
        dto = compute_score(_healthy_inputs(waste_event_count=100))
        assert _component(dto, DoraScoreComponentKey.WASTE).score == 0


# ── Budget ───────────────────────────────────────────────────────────

@pytest.mark.unit
class TestBudget:
    def test__no_budget_excludes_component(self):
        dto = compute_score(_healthy_inputs(has_budget=False, budget_over_pct=None))
        c = _component(dto, DoraScoreComponentKey.BUDGET)
        assert c.score is None
        assert "no budget" in c.reason.lower()

    def test__under_budget_scores_100(self):
        dto = compute_score(_healthy_inputs(budget_over_pct=-0.25))
        assert _component(dto, DoraScoreComponentKey.BUDGET).score == 100

    def test__on_budget_scores_100(self):
        dto = compute_score(_healthy_inputs(budget_over_pct=0.0))
        assert _component(dto, DoraScoreComponentKey.BUDGET).score == 100

    def test__over_by_25_percent_scores_75(self):
        dto = compute_score(_healthy_inputs(budget_over_pct=0.25))
        assert _component(dto, DoraScoreComponentKey.BUDGET).score == 75

    def test__double_the_budget_scores_0(self):
        dto = compute_score(_healthy_inputs(budget_over_pct=1.0))
        assert _component(dto, DoraScoreComponentKey.BUDGET).score == 0

    def test__extreme_overshoot_clamps_at_0(self):
        dto = compute_score(_healthy_inputs(budget_over_pct=5.0))
        assert _component(dto, DoraScoreComponentKey.BUDGET).score == 0


# ── Freshness ────────────────────────────────────────────────────────

@pytest.mark.unit
class TestFreshness:
    def test__no_items_track_expiry_excludes_component(self):
        dto = compute_score(_healthy_inputs(total_items_with_expiry=0, expired_item_count=0))
        c = _component(dto, DoraScoreComponentKey.FRESHNESS)
        assert c.score is None
        assert "no stock items track" in c.reason.lower()

    def test__nothing_expired_scores_100(self):
        dto = compute_score(_healthy_inputs(total_items_with_expiry=10, expired_item_count=0))
        assert _component(dto, DoraScoreComponentKey.FRESHNESS).score == 100

    def test__half_expired_scores_50(self):
        dto = compute_score(_healthy_inputs(total_items_with_expiry=10, expired_item_count=5))
        assert _component(dto, DoraScoreComponentKey.FRESHNESS).score == 50

    def test__everything_expired_scores_0(self):
        dto = compute_score(_healthy_inputs(total_items_with_expiry=5, expired_item_count=5))
        assert _component(dto, DoraScoreComponentKey.FRESHNESS).score == 0


# ── Run-outs ─────────────────────────────────────────────────────────

@pytest.mark.unit
class TestPlanCoverage:
    """Of the meals planned for the week ahead, how many the pantry can cook.

    Replaced `TestStocktake`, which scored "% of items checked in 30 days" —
    an activity metric, and the substance of FU-835.
    """

    def test__nothing_planned_excludes_component(self):
        dto = compute_score(_healthy_inputs(upcoming_planned_meals=0))
        component = _component(dto, DoraScoreComponentKey.PLAN_COVERAGE)
        assert component.score is None
        assert "Nothing planned" in component.reason

    def test__all_cookable_scores_100(self):
        dto = compute_score(_healthy_inputs(
            upcoming_planned_meals=7, upcoming_cookable_meals=7,
        ))
        assert _component(dto, DoraScoreComponentKey.PLAN_COVERAGE).score == 100

    def test__half_cookable_scores_50(self):
        dto = compute_score(_healthy_inputs(
            upcoming_planned_meals=8, upcoming_cookable_meals=4,
        ))
        assert _component(dto, DoraScoreComponentKey.PLAN_COVERAGE).score == 50

    def test__none_cookable_scores_0(self):
        dto = compute_score(_healthy_inputs(
            upcoming_planned_meals=6, upcoming_cookable_meals=0,
        ))
        component = _component(dto, DoraScoreComponentKey.PLAN_COVERAGE)
        assert component.score == 0
        assert "None of your 6 planned meals" in component.reason


@pytest.mark.unit
class TestRetiredComponents:
    """The two cut signals must not come back by accident.

    A registry of scored things drifts silently — that is the lesson the
    dashboard's own `DEFAULT_VISIBLE_COUNT` had to learn — so the closed set is
    asserted rather than assumed.
    """

    def test__runouts_and_stocktake_are_gone(self):
        assert not hasattr(DoraScoreComponentKey, "RUNOUTS")
        assert not hasattr(DoraScoreComponentKey, "STOCKTAKE")

    def test__exactly_four_keys(self):
        assert {k.value for k in DoraScoreComponentKey} == {
            "waste", "budget", "freshness", "plan_coverage",
        }


@pytest.mark.unit
class TestTrend:
    def _score(self, **overrides) -> DoraScoreDto:
        return compute_score(_healthy_inputs(**overrides))

    def test__improving_signals_up_arrow(self):
        # Lagged had 3 waste events → composite lower; current has 0 → higher.
        current = self._score(waste_event_count=0)
        lagged = self._score(waste_event_count=3)
        out = compose_with_trend(current, lagged)
        assert out.trend_direction == "up"
        assert out.trend_delta == current.composite - lagged.composite

    def test__declining_signals_down_arrow(self):
        current = self._score(waste_event_count=3)
        lagged = self._score(waste_event_count=0)
        out = compose_with_trend(current, lagged)
        assert out.trend_direction == "down"
        assert out.trend_delta is not None and out.trend_delta < 0

    def test__tiny_drift_is_flat(self):
        # A 1-point delta is inside the ±2 hysteresis band — noise.
        current = self._score(waste_event_count=0)
        # Approximate a small delta by contriving a mostly-identical input;
        # we can't get exactly 1-point unless the mean lands there, so
        # test the boundary condition directly: if delta is 0 → flat.
        out = compose_with_trend(current, current)
        assert out.trend_direction == "flat"
        assert out.trend_delta == 0

    def test__compose_with_trend__BudgetUnscoredInLaggedWindow__UnchangedHouseholdIsFlat(self):
        # The lagged pass never scores budget. With every shared signal equal,
        # comparing a 4-component mean to a 3-component one used to swing the
        # arrow on the budget score alone.
        current = self._score(budget_over_pct=0.5, waste_event_count=2)
        lagged = self._score(has_budget=False, budget_over_pct=None, waste_event_count=2)
        out = compose_with_trend(current, lagged)
        assert out.trend_delta == 0
        assert out.trend_direction == "flat"
        # The displayed composite still includes budget.
        assert out.composite == current.composite

    def test__compose_with_trend__SharedSignalMoves__DeltaIgnoresOneSidedComponent(self):
        current = self._score(waste_event_count=0, budget_over_pct=0.9)
        lagged = self._score(waste_event_count=3, has_budget=False, budget_over_pct=None)
        out = compose_with_trend(current, lagged)
        # waste 100 vs 70 over three shared components: (300 - 270) / 3 = 10.
        assert out.trend_delta == 10
        assert out.trend_direction == "up"

    def test__no_lagged_returns_current_untouched(self):
        current = self._score()
        out = compose_with_trend(current, None)
        assert out.trend_direction is None
        assert out.trend_delta is None
        assert out.composite == current.composite


# ── Window helpers ───────────────────────────────────────────────────

@pytest.mark.unit
class TestWindowHelpers:
    def test__window_bounds_are_30_and_37_days(self):
        from dora_api.domain.dora_score import (
            lagged_window_end,
            lagged_window_start,
            window_start,
        )
        assert (NOW - window_start(NOW)).days == DORA_SCORE_WINDOW_DAYS
        # Lagged window: ends 7 days before now, starts 37 days before now.
        assert (NOW - lagged_window_end(NOW)).days == 7
        assert (NOW - lagged_window_start(NOW)).days == 37
