"""FU-596 — "Build my week" auto-planner ranker unit tests.

Drives the pure ranker (`select_recipes` / `place_entries` / `apply_budget_cap`
/ `_fill_one_day` / `_buildable_days` / `reason_chip`) with fixture candidates —
no DB, no HTTP. The repo-touching orchestrator (`compute_auto_build`) + the
endpoint are covered end-to-end by `tests/e2e/dora_api/test_meal_plan_router.py`.
"""
from datetime import date
from uuid import uuid4

from dora_api.features.meal_plans.build_week import (
    CHIP_BUDGET, CHIP_COOKABLE_NOW, CHIP_FAVOURITE, CHIP_NOT_MADE_RECENTLY,
    CHIP_USES_EXPIRING, EMPHASIS_FAVOURITES, EMPHASIS_SURPRISE,
    EMPHASIS_USE_UP_STOCK, EMPHASIS_VARIETY, RecipeCandidate, _buildable_days,
    _entry_cost, _fill_one_day, apply_budget_cap, cost_per_serving,
    place_entries, place_entries_batched, reason_chip, select_recipes)


def _cand(name, *, time_of_day=None, cookable=None, expiring=0, favourite=False,
          plan_count=0, not_recent=False, cuisine=None, category=None,
          cost=None, servings=2):
    return RecipeCandidate(
        recipe_id=uuid4(), name=name, time_of_day=time_of_day, cookable=cookable,
        expiring_count=expiring, is_favourite=favourite, plan_count=plan_count,
        not_made_recently=not_recent, cuisine_id=cuisine, category_id=category,
        estimated_cost=cost, servings=servings, missing_stock_item_names=(),
    )


# ── select_recipes — emphasis weighting ────────────────────────────────────


def test__use_up_stock__prefers_expiring_then_cookable():
    expiring = _cand("zeta", expiring=2, cuisine=uuid4())
    cookable = _cand("yankee", cookable=True, cuisine=uuid4())
    plain = _cand("xray", cuisine=uuid4())
    out = select_recipes([plain, cookable, expiring], EMPHASIS_USE_UP_STOCK, 2, set())
    assert {c.name for c in out} == {"zeta", "yankee"}
    assert out[0].name == "zeta"  # expiring outranks cookable-now


def test__favourites__prefers_favourites():
    fav = _cand("fav", favourite=True, cuisine=uuid4())
    other = _cand("other", cuisine=uuid4())
    out = select_recipes([other, fav], EMPHASIS_FAVOURITES, 1, set())
    assert [c.name for c in out] == ["fav"]


def test__variety__spreads_cuisines_not_four_of_one():
    a = uuid4()
    pool = [
        _cand("a1", not_recent=True, cuisine=a),
        _cand("a2", not_recent=True, cuisine=a),
        _cand("a3", not_recent=True, cuisine=a),
        _cand("b1", not_recent=True, cuisine=uuid4()),
        _cand("c1", not_recent=True, cuisine=uuid4()),
    ]
    out = select_recipes(pool, EMPHASIS_VARIETY, 3, set())
    assert len({c.cuisine_id for c in out}) == 3  # three distinct cuisines


def test__excludes_already_planned():
    keep = _cand("keep", favourite=True, cuisine=uuid4())
    planned = _cand("planned", favourite=True, cuisine=uuid4())
    out = select_recipes([keep, planned], EMPHASIS_FAVOURITES, 5, {planned.recipe_id})
    assert [c.name for c in out] == ["keep"]  # planned excluded, distinct only


def test__count_capped_at_distinct_pool():
    pool = [_cand("one", cuisine=uuid4()), _cand("two", cuisine=uuid4())]
    out = select_recipes(pool, EMPHASIS_USE_UP_STOCK, 10, set())
    assert len(out) == 2  # never repeats a recipe to hit the count


def test__surprise__is_deterministic_for_a_seed_and_respects_exclusions():
    import random
    pool = [_cand(f"r{i}", not_recent=True, cuisine=uuid4()) for i in range(6)]
    excluded = {pool[0].recipe_id}
    out = select_recipes(pool, EMPHASIS_SURPRISE, 3, excluded, random.Random(1))
    assert len(out) == 3
    assert pool[0].recipe_id not in {c.recipe_id for c in out}


def test__reshuffle__different_rng_varies_the_pick_when_the_pool_has_slack():
    # The "Reshuffle" bug: use_up_stock was fully deterministic, so a fresh
    # request returned the identical plan. With a per-request rng the picked
    # set now varies while still honouring the emphasis.
    import random
    # Equal-signal candidates (all cookable) so only the tiebreak decides.
    pool = [_cand(f"r{i}", cookable=True, cuisine=uuid4()) for i in range(10)]
    picks = {
        frozenset(c.recipe_id for c in select_recipes(
            pool, EMPHASIS_USE_UP_STOCK, 3, set(), random.Random(seed)))
        for seed in range(8)
    }
    assert len(picks) > 1  # not always the same three


def test__reshuffle__varies_even_when_the_signals_are_not_equal():
    """The 2026-09-12 complaint: on real data every recipe carries a different
    signal, the top-scoring ones won every time, and Reshuffle looked inert.
    Sampling among the near-best is what fixes that — these three are within
    the window of each other, so which of them leads varies."""
    import random
    pool = [
        _cand("expiring", expiring=1, cuisine=uuid4()),
        _cand("cookable", cookable=True, cuisine=uuid4()),
        _cand("both", cookable=True, not_recent=True, cuisine=uuid4()),
    ]
    firsts = {
        select_recipes(pool, EMPHASIS_USE_UP_STOCK, 1, set(), random.Random(seed))[0].name
        for seed in range(12)
    }
    assert len(firsts) > 1


def test__reshuffle__no_rng_is_still_deterministic():
    pool = [_cand(f"r{i}", cookable=True, cuisine=uuid4()) for i in range(10)]
    a = [c.recipe_id for c in select_recipes(pool, EMPHASIS_USE_UP_STOCK, 3, set())]
    b = [c.recipe_id for c in select_recipes(pool, EMPHASIS_USE_UP_STOCK, 3, set())]
    assert a == b


def test__reshuffle__strong_signal_still_wins_over_the_tiebreak():
    # A single strongly-expiring recipe outranks the jitter every time.
    import random
    hot = _cand("hot", expiring=3, cuisine=uuid4())
    pool = [hot] + [_cand(f"r{i}", cookable=True, cuisine=uuid4()) for i in range(9)]
    for seed in range(8):
        out = select_recipes(pool, EMPHASIS_USE_UP_STOCK, 3, set(), random.Random(seed))
        assert hot.recipe_id in {c.recipe_id for c in out}


# ── _fill_one_day + place_entries — day×slot cell filling ──────────────────


def test__fill_one_day__recipe_claims_its_own_time_of_day_slot():
    # "b" names Dinner, so it wins Dinner even though "a" outranks it.
    a, b = _cand("a"), _cand("b", time_of_day="Dinner")
    out = _fill_one_day([a, b], ["Breakfast", "Dinner"])
    assert out == [(a, "Breakfast"), (b, "Dinner")]


def test__fill_one_day__falls_to_rank_order_when_no_time_of_day():
    a, b, c = _cand("a"), _cand("b"), _cand("c")
    out = _fill_one_day([a, b, c], ["Breakfast", "Lunch", "Dinner"])
    assert out == [(a, "Breakfast"), (b, "Lunch"), (c, "Dinner")]


def test__fill_one_day__time_of_day_outside_the_chosen_slots_ignored():
    c = _cand("dish", time_of_day="Snack")
    assert _fill_one_day([c], ["Dinner"]) == [(c, "Dinner")]


def test__fill_one_day__short_pool_leaves_later_slots_empty():
    a = _cand("a")
    assert _fill_one_day([a], ["Breakfast", "Lunch"]) == [(a, "Breakfast")]


def test__place_entries__one_meal_per_day_slot_cell():
    d0, d1 = date(2026, 8, 3), date(2026, 8, 4)
    picks = [_cand("a"), _cand("b"), _cand("c"), _cand("d")]
    placements = place_entries(picks, [d0, d1], ["Lunch", "Dinner"])
    assert [(day, slot) for (_c, day, slot) in placements] == [
        (d0, "Lunch"), (d0, "Dinner"), (d1, "Lunch"), (d1, "Dinner"),
    ]
    # Every cell gets a distinct recipe — no repeats across the week.
    assert len({c.recipe_id for (c, _d, _s) in placements}) == 4


def test__place_entries__does_not_dump_everything_in_first_slot():
    # The FU-596 regression: with a multi-slot pool and no time_of_day, meals
    # must spread across slots rather than all landing in the first one.
    d0 = date(2026, 8, 3)
    picks = [_cand("a"), _cand("b"), _cand("c")]
    placements = place_entries(picks, [d0], ["Breakfast", "Lunch", "Dinner"])
    assert sorted(slot for (_c, _d, slot) in placements) == ["Breakfast", "Dinner", "Lunch"]


def test__place_entries__repeat_same_day__duplicates_one_line_up():
    d0, d1, d2 = date(2026, 8, 3), date(2026, 8, 4), date(2026, 8, 5)
    a, b = _cand("a"), _cand("b")
    placements = place_entries([a, b], [d0, d1, d2], ["Lunch", "Dinner"], repeat_same_day=True)
    assert len(placements) == 6
    # The same (recipe, slot) pattern on every selected day.
    for day in (d0, d1, d2):
        assert [(c.name, slot) for (c, d, slot) in placements if d == day] == [
            ("a", "Lunch"), ("b", "Dinner"),
        ]


def test__place_entries__no_days__places_nothing():
    assert place_entries([_cand("a")], [], ["Dinner"]) == []


# ── apply_budget_cap ────────────────────────────────────────────────────────


def test__budget_cap__swaps_dearest_for_cheaper():
    # `_cand` yields 2 servings, so planning 2 servings of each is the whole
    # pot: $10 + $5 against $8 left, and the dear one has to go.
    dear = _cand("dear", cost=10.0)
    mid = _cand("mid", cost=5.0)
    cheap = _cand("cheap", cost=2.0)
    selected, swapped = apply_budget_cap(
        [dear, mid], [cheap], budget_remaining=8.0, servings_per_meal=2,
    )
    names = {c.name for c in selected}
    assert names == {"cheap", "mid"}
    assert cheap.recipe_id in swapped


def test__budget_cap__counts_the_plan_not_the_pot():
    """Owner 2026-09-12 — the cap used to compare the recipe's whole yield
    against the budget however many servings were actually being planned, and
    counted a batch cook once per day it spanned. One serving each of these two
    is $7.50 of a $8 budget: nothing needs swapping."""
    dear = _cand("dear", cost=10.0)
    mid = _cand("mid", cost=5.0)
    cheap = _cand("cheap", cost=2.0)
    selected, swapped = apply_budget_cap(
        [dear, mid], [cheap], budget_remaining=8.0, servings_per_meal=1,
    )
    assert {c.name for c in selected} == {"dear", "mid"}
    assert swapped == set()

    # The same two picks, each cooked once and eaten across 3 days, cost 3×.
    selected, swapped = apply_budget_cap(
        [dear, mid], [cheap], budget_remaining=8.0,
        servings_per_meal=1, meals_per_pick=3,
    )
    assert "cheap" in {c.name for c in selected}


def test__budget_cap__no_cheaper_alternative__unchanged():
    dear = _cand("dear", cost=10.0)
    selected, swapped = apply_budget_cap([dear], [], budget_remaining=1.0)
    assert [c.name for c in selected] == ["dear"]
    assert swapped == set()


def test__budget_cap__compares_the_rounded_entry_costs_the_response_sums():
    # FU-976: one serving of a $10.01, 3-serving recipe is $3.34 in the
    # response. Unrounded, three such meals were $10.01 and passed a $10.015
    # budget, then summed to $10.02 once each entry rounded: over.
    picks = [_cand(name, cost=10.01, servings=3) for name in ("a", "b", "c")]
    cheap = _cand("cheap", cost=1.0)
    selected, _ = apply_budget_cap(
        picks, [cheap], budget_remaining=10.015, servings_per_meal=1,
    )
    assert "cheap" in {c.name for c in selected}


# ── cost per serving ────────────────────────────────────────────────────────


def test__cost_per_serving__divides_the_pot_by_the_recipe_yield():
    assert cost_per_serving(_cand("a", cost=12.0, servings=4)) == 3.0
    # An unpriced recipe stays unpriced rather than becoming a zero.
    assert cost_per_serving(_cand("b", cost=None)) is None
    # A recipe with no stated yield is one serving, not a divide-by-zero.
    assert cost_per_serving(_cand("c", cost=7.0, servings=None)) == 7.0


def test__entry_cost__is_priced_at_the_planned_servings():
    """The builder used to quote the whole pot for every entry, so the servings
    control on step 1 changed nothing and a 3-day batch cook was counted three
    times (owner 2026-09-12)."""
    pot = _cand("pie", cost=12.0, servings=4)
    assert _entry_cost(pot, 1) == 3.0
    assert _entry_cost(pot, 4) == 12.0
    # Three days of a batch cook at 2 servings each: one pot and a half, not
    # three pots.
    assert round(sum(_entry_cost(pot, 2) for _ in range(3)), 2) == 18.0


# ── reason_chip ─────────────────────────────────────────────────────────────


def test__reason_chip__priorities():
    assert reason_chip(_cand("x", expiring=1), EMPHASIS_USE_UP_STOCK, False) == CHIP_USES_EXPIRING
    assert reason_chip(_cand("x", cookable=True), EMPHASIS_USE_UP_STOCK, False) == CHIP_COOKABLE_NOW
    assert reason_chip(_cand("x", favourite=True), EMPHASIS_FAVOURITES, False) == CHIP_FAVOURITE
    assert reason_chip(_cand("x", not_recent=True), EMPHASIS_VARIETY, False) == CHIP_NOT_MADE_RECENTLY
    assert reason_chip(_cand("x", cost=2.0), EMPHASIS_USE_UP_STOCK, True) == CHIP_BUDGET


# ── _buildable_days ─────────────────────────────────────────────────────────


def test__buildable_days__drops_past_days_and_keeps_today():
    today = date(2026, 7, 29)  # Wednesday
    requested = [date(2026, 7, 27), date(2026, 7, 29), date(2026, 7, 31)]
    assert _buildable_days(requested, today) == [date(2026, 7, 29), date(2026, 7, 31)]


def test__buildable_days__de_duplicates_and_orders():
    today = date(2026, 7, 29)
    requested = [date(2026, 7, 31), date(2026, 7, 30), date(2026, 7, 31)]
    assert _buildable_days(requested, today) == [date(2026, 7, 30), date(2026, 7, 31)]


def test__buildable_days__all_past__empty():
    assert _buildable_days([date(2026, 7, 28)], date(2026, 7, 29)) == []


# ── place_entries_batched (PROPOSAL_MEAL_PLANS_PART_2 §9) ────────────────────


def test__batched__chunks_days_into_runs_sharing_one_cook():
    # 3 recipes, one dinner slot, 6 days, span 3 → two cooks of three days each.
    pool = [_cand(n, time_of_day="Dinner", cuisine=uuid4()) for n in ("a", "b", "c")]
    days = [date(2026, 7, d) for d in range(1, 7)]
    out = place_entries_batched(pool, days, ["Dinner"], span=3)
    assert len(out) == 6  # every day filled
    # each 3-day run is one recipe + one shared cook_key
    keys = [key for (_c, _d, _s, key) in out]
    assert keys[0] == keys[1] == keys[2] and keys[0] is not None
    assert keys[3] == keys[4] == keys[5] and keys[3] is not None
    assert keys[0] != keys[3]
    recipes = [c.name for (c, _d, _s, _k) in out]
    assert recipes[0] == recipes[1] == recipes[2]      # one cook = one recipe
    assert recipes[0] != recipes[3]                    # distinct recipe per cook


def test__batched__single_day_run_has_no_cook_key():
    # 4 days, span 3 → runs of [3, 1]; the trailing 1-day run is a normal meal.
    pool = [_cand(n, time_of_day="Dinner", cuisine=uuid4()) for n in ("a", "b")]
    days = [date(2026, 7, d) for d in range(1, 5)]
    out = place_entries_batched(pool, days, ["Dinner"], span=3)
    keys = [key for (_c, _d, _s, key) in out]
    assert keys[0] == keys[1] == keys[2] and keys[0] is not None  # the 3-run links
    assert keys[3] is None                                        # the lone day is standalone


def test__batched__stops_when_pool_runs_dry():
    # One recipe, 6 days, span 3 → only the first run can be filled.
    pool = [_cand("only", time_of_day="Dinner", cuisine=uuid4())]
    days = [date(2026, 7, d) for d in range(1, 7)]
    out = place_entries_batched(pool, days, ["Dinner"], span=3)
    assert len(out) == 3  # first run only; no recipe left for the second
    assert {d for (_c, d, _s, _k) in out} == set(days[:3])
