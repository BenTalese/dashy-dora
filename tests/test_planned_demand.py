"""Planned demand + the shared cooked-batch pool model (owner, 2026-09-03).

Two pure rules are pinned here — the allocation (`allocate_pool`) and the
grading (`urgency_for`, `build_reason`) — with no DB and no HTTP, the same way
`test_pantry_belief.py` pins the belief model. The repo walk on top of them is
a thin gather; the e2e suite covers it end to end.

The thing worth pinning hardest is that **coverage is all-or-nothing per
entry**: a 4-serving meal against a 3-serving pool still has to be cooked, so
its ingredients are still demand. Getting that wrong in the generous direction
would make the signal go quiet exactly when a batch has *nearly* run out,
which is the moment it is most worth saying something.
"""
from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest

from dora_api.domain.stock_status import (LOW_STOCK_SEQUENCE,
                                          OUT_OF_STOCK_SEQUENCE,
                                          STOCKED_SEQUENCE)
from dora_api.features.meal_plans.planned_meals import (PlannedMeal,
                                                        PlannedMealSnapshot,
                                                        allocate_pool,
                                                        recipe_shortfalls)
from dora_api.features.stock_items.planned_demand import (URGENCY_BLOCKING,
                                                          URGENCY_NONE,
                                                          URGENCY_WATCH,
                                                          build_reason,
                                                          urgency_for)

_TODAY = date(2026, 9, 3)
_RECIPE = UUID("11111111-1111-1111-1111-111111111111")


def _meal(day_offset: int, servings: int = 2, recipe_id: UUID = _RECIPE,
          name: str = "Fried Rice", cook_batch_id: UUID | None = None,
          cook_fresh: bool = False) -> PlannedMeal:
    return PlannedMeal(
        entry_id=uuid4(),
        recipe_id=recipe_id,
        recipe_name=name,
        scheduled_for=_TODAY + timedelta(days=day_offset),
        servings=servings,
        covered=False,
        cook_batch_id=cook_batch_id,
        cook_fresh=cook_fresh,
    )


# ── allocate_pool ────────────────────────────────────────────────────────

def test__allocate_pool__no_pool__covers_nothing():
    meals = allocate_pool([_meal(1), _meal(3), _meal(5)], 0)
    assert [m.covered for m in meals] == [False, False, False]


def test__allocate_pool__spends_on_the_soonest_meals_first():
    # The owner's example: three planned fried rice, a pool of four servings,
    # two-serving meals — so the first two are covered and the third is not.
    meals = allocate_pool([_meal(5), _meal(1), _meal(3)], 4)
    assert [(m.scheduled_for.day, m.covered) for m in meals] == [
        (_TODAY.day + 1, True), (_TODAY.day + 3, True), (_TODAY.day + 5, False),
    ]


def test__allocate_pool__partial_coverage_does_not_count_as_covered():
    # 3 servings in the pool, a 4-serving meal: you are still cooking it.
    meals = allocate_pool([_meal(1, servings=4)], 3)
    assert meals[0].covered is False


def test__allocate_pool__leftovers_reach_a_later_smaller_meal():
    # 3 in the pool; the 4-serving meal on day 1 can't be covered, but the
    # 2-serving one on day 4 can — the pool isn't consumed by the miss.
    meals = allocate_pool([_meal(1, servings=4), _meal(4, servings=2)], 3)
    assert [m.covered for m in meals] == [False, True]


def test__allocate_pool__negative_pool_is_treated_as_empty():
    assert allocate_pool([_meal(1)], -5)[0].covered is False


# ── allocate_pool: cook batches are ONE unit ─────────────────────────────
#
# A cook batch is one cook eaten across several days. Allocating it per day
# would let a small pool "cover" its first day and leave the rest reading as
# further cooks that do not exist — and would put a chef hat on a leftovers
# day, which nobody has to cook. Owner, 2026-09-03, on multi-day cooks:
# *"feels like a feature that has great potential to break."*

_BATCH = UUID("22222222-2222-2222-2222-222222222222")


def test__allocate_pool__batch_is_covered_as_a_whole_or_not_at_all():
    # Mon + Wed, 2 servings each: the cook has to yield 4. A pool of 3 covers
    # neither day, even though it would have covered Monday alone.
    meals = allocate_pool(
        [_meal(1, cook_batch_id=_BATCH), _meal(3, cook_batch_id=_BATCH)], 3,
    )
    assert [m.covered for m in meals] == [False, True]
    # …and the one that reads as uncovered is the COOK day, not the leftovers.
    assert [m.is_cook_day for m in meals] == [True, False]


def test__allocate_pool__leftover_days_are_never_flagged_as_needing_a_cook():
    meals = allocate_pool(
        [_meal(1, cook_batch_id=_BATCH), _meal(3, cook_batch_id=_BATCH)], 0,
    )
    needing = [m for m in meals if not m.covered]
    assert len(needing) == 1
    assert needing[0].is_cook_day is True


def test__allocate_pool__batch_covered_when_the_pool_reaches_its_whole_yield():
    meals = allocate_pool(
        [_meal(1, cook_batch_id=_BATCH), _meal(3, cook_batch_id=_BATCH)], 4,
    )
    assert all(m.covered for m in meals)


def test__allocate_pool__batch_spends_the_pool_at_its_cook_day_position():
    # A standalone meal on day 2 sits between the batch's Mon and Wed. The
    # batch queues at its cook day (day 1), so it is served first and the
    # 2-serving pool goes to it, leaving day 2 uncovered.
    standalone = _meal(2)
    meals = allocate_pool(
        [_meal(1, servings=1, cook_batch_id=_BATCH),
         _meal(3, servings=1, cook_batch_id=_BATCH),
         standalone], 2,
    )
    by_day = {m.scheduled_for.day: m.covered for m in meals}
    assert by_day[_TODAY.day + 1] is True
    assert by_day[_TODAY.day + 3] is True
    assert by_day[_TODAY.day + 2] is False


def test__recipe_shortfalls__earliest_needed_is_a_batch_cook_day():
    meals = allocate_pool(
        [_meal(1, cook_batch_id=_BATCH), _meal(3, cook_batch_id=_BATCH)], 0,
    )
    snapshot = PlannedMealSnapshot(meals=meals, available_by_recipe={_RECIPE: 0})
    [row] = recipe_shortfalls(snapshot)
    # Day 3 is a leftovers day, so the date the ingredients must exist by is
    # day 1 — the day the single cook happens.
    assert row.earliest_needed == _TODAY + timedelta(days=1)
    # The servings gap is unchanged by the grouping: a batch's members still
    # each carry their own share of the yield.
    assert row.committed_meals == 4


# ── allocate_pool: fresh meals stand outside the pool (owner 2026-09-04) ──

def test__allocate_pool__fresh_meal_is_never_covered_even_with_a_full_pool():
    [meal] = allocate_pool([_meal(1, cook_fresh=True)], 10)
    assert meal.covered is False
    assert meal.is_cook_day is True


def test__allocate_pool__fresh_meal_does_not_spend_the_pool():
    # Owner: *"it should not take a meal, and it should also not demand a meal
    # from the pool."* Without the carve-out the day-1 fresh meal would eat
    # both portions and the day-3 batch meal would read as needing a cook.
    meals = allocate_pool([_meal(1, cook_fresh=True), _meal(3)], 2)
    by_day = {m.scheduled_for.day: m.covered for m in meals}
    assert by_day[_TODAY.day + 1] is False
    assert by_day[_TODAY.day + 3] is True


# ── recipe_shortfalls ────────────────────────────────────────────────────

def test__recipe_shortfalls__pool_covers_everything__recipe_absent():
    snapshot = PlannedMealSnapshot(
        meals=allocate_pool([_meal(1), _meal(3)], 4),
        available_by_recipe={_RECIPE: 4},
    )
    assert recipe_shortfalls(snapshot) == []


def test__recipe_shortfalls__reports_the_servings_gap_and_first_uncovered_date():
    snapshot = PlannedMealSnapshot(
        meals=allocate_pool([_meal(1), _meal(3), _meal(5)], 2),
        available_by_recipe={_RECIPE: 2},
    )
    [row] = recipe_shortfalls(snapshot)
    assert row.committed_meals == 6
    assert row.available_meals == 2
    assert row.shortfall == 4
    # Day 1 is covered by the pool, so the first date anything is actually
    # needed by is day 3 — not day 1, which the old SQL would have reported.
    assert row.earliest_needed == _TODAY + timedelta(days=3)


def test__recipe_shortfalls__fresh_meals_are_not_committed_against_the_pool():
    # Saturday's fresh roast is not two more portions the household has to
    # batch-cook, so it contributes nothing to the shortfall — the same recipe
    # planned normally on day 3 is the whole of it.
    snapshot = PlannedMealSnapshot(
        meals=allocate_pool([_meal(1, cook_fresh=True), _meal(3)], 0),
        available_by_recipe={_RECIPE: 0},
    )
    [row] = recipe_shortfalls(snapshot)
    assert row.committed_meals == 2
    assert row.shortfall == 2
    assert row.earliest_needed == _TODAY + timedelta(days=3)


def test__recipe_shortfalls__only_fresh_meals__recipe_absent_entirely():
    snapshot = PlannedMealSnapshot(
        meals=allocate_pool([_meal(1, cook_fresh=True)], 0),
        available_by_recipe={_RECIPE: 0},
    )
    assert recipe_shortfalls(snapshot) == []


# ── urgency_for ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("recorded,expected", [
    (OUT_OF_STOCK_SEQUENCE, URGENCY_BLOCKING),
    (LOW_STOCK_SEQUENCE, URGENCY_WATCH),
    (STOCKED_SEQUENCE, URGENCY_NONE),
    (None, URGENCY_NONE),
])
def test__urgency_for__grades_against_the_recorded_level(recorded, expected):
    assert urgency_for(recorded, needed_meals=2) == expected


def test__urgency_for__nothing_left_to_cook__is_never_urgent():
    # Every planned meal already covered by a batch: the plan wants nothing.
    assert urgency_for(OUT_OF_STOCK_SEQUENCE, needed_meals=0) == URGENCY_NONE


# ── build_reason ─────────────────────────────────────────────────────────

def test__build_reason__names_the_meals_and_the_first_date():
    reason = build_reason(
        planned_meals=3, covered_meals=0,
        recipe_names=["Fried Rice"], earliest_needed=date(2026, 9, 5),
    )
    assert reason.startswith("3 planned meals coming up need this: Fried Rice")
    assert "First needed Sat, 5 Sept" in reason  # en-AU, as Intl prints it (FU-969)


def test__build_reason__mentions_the_batch_allocation_when_there_is_one():
    reason = build_reason(
        planned_meals=3, covered_meals=2,
        recipe_names=["Fried Rice"], earliest_needed=date(2026, 9, 12),
    )
    assert "2 already covered by a cooked batch" in reason


def test__build_reason__caps_the_named_recipes():
    reason = build_reason(
        planned_meals=4, covered_meals=0,
        recipe_names=["Fried Rice", "Congee", "Risotto", "Paella"],
        earliest_needed=date(2026, 9, 4),
    )
    assert "Fried Rice, Congee and 2 others" in reason
    assert "Risotto" not in reason


def test__build_reason__two_recipes__joins_with_and_not_a_comma():
    reason = build_reason(
        planned_meals=3, covered_meals=0,
        recipe_names=["Sunday Ragu", "Egg Fried Rice"],
        earliest_needed=date(2026, 9, 4),
    )
    assert "Sunday Ragu and Egg Fried Rice" in reason


def test__build_reason__no_planned_meals__says_nothing():
    assert build_reason(
        planned_meals=0, covered_meals=0, recipe_names=[], earliest_needed=None,
    ) == ""


def test__build_reason__dates_follow_the_household_locale():
    # FU-969: the date was always English, day first.
    reason = build_reason(
        planned_meals=1, covered_meals=0, recipe_names=["Soup"],
        earliest_needed=date(2026, 9, 5), locale="en-US",
    )
    assert "First needed Sat, Sep 5" in reason
