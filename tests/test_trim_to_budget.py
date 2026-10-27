"""FU-448 — Unit-level coverage of the trim-to-budget classifier.

The classifier is a pure function of `(lines, ctx, excluded)` — all repo
touching lives in the handler. That's what these tests exercise. E2E
wiring for the HTTP endpoint is in
`tests/e2e/dora_api/test_trim_to_budget.py`.

The five tiers (brief §4):
  1. Habit — can wait                       (habit buy, no demand, not out)
  2. N days' cover left / Not urgent        (band=low with ≥5 days cover, no demand)
  3. Above your usual price                 (verdict=wait, no demand in 3d, not out)
  4. Out, but no meal booked                (out, no demand in 7d)
  5. For <Recipe> on <Day> /
     Needed for N meals later               (a meal needs it, scheduled ≥5d out)

Tiers 1/2/5 were keyed off the line's `added_via` provenance string until
2026-09-19. That enum is gone; they now read live signals — the habit
ranking, the item's current stock band, and the meal demand map.

Never-cut: essentials, meals in next 2d, verdict=buy on low/out, < $2.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from dora_api.features.shopping_lists.trim_to_budget import (
    MIN_LINE_VALUE,
    REASON_ABOVE_USUAL_PRICE,
    REASON_COVER_LEFT,
    REASON_FOR_RECIPE_ON_DAY,
    REASON_HABIT_CAN_WAIT,
    REASON_NEEDED_FOR_N_MEALS,
    REASON_NOT_URGENT,
    REASON_OUT_NO_MEAL,
    _classify_lines,
    _Ctx,
    _MealDemand,
)


TODAY = date(2026, 7, 6)


# ── Minimal stand-ins so the classifier stays repo-free ────────────────


@dataclass
class _StockLevel:
    sequence: int = 0     # 0 stocked · 1 low · 2 out


def _item(item_id, *, band="stocked", is_essential=False):
    return SimpleNamespace(
        id=item_id,
        is_essential=is_essential,
        stock_level=_StockLevel(sequence={"stocked": 0, "low": 1, "out": 2}[band]),
    )


def _line(item_id, *, quantity=1, sequence=0):
    return SimpleNamespace(
        id=uuid4(),
        stock_item_id=item_id,
        selected_product_id=None,
        quantity=quantity,
        is_ticked=False,
        deferred_by_budget=False,
        actual_unit_price=None,
        picked_offer_price=10.00,
        sequence=sequence,
    )


def _verdict(v="unsure", confidence="medium"):
    return SimpleNamespace(
        verdict=v,
        confidence=confidence,
        reasons=[],
        one_tap_action=None,
        data_used=None,
        wait_hint=None,
    )


def _ctx(items, *, demand=None, verdicts=None, cover=None, habits=None):
    ctx = _Ctx(
        today=TODAY,
        stock_items_by_id={it.id: it for it in items},
        offer_by_product_id={},
        demand=demand or {},
        habit_item_ids=set(habits or []),
    )
    ctx.verdicts = verdicts or {}
    ctx.cover_days = cover or {}
    return ctx


# ── Tier 1: habit items ────────────────────────────────────────────────


def test_tier1_habit_can_wait():
    item = _item(uuid4())
    line = _line(item.id)
    ctx = _ctx([item], verdicts={item.id: _verdict()}, habits=[item.id])
    out = _classify_lines([line], ctx, excluded=set())
    assert len(out) == 1
    tier, _, reason, saved = out[0]
    assert tier == 1
    assert reason == REASON_HABIT_CAN_WAIT
    assert saved == 10.00


def test_tier1_not_applied_when_out():
    item = _item(uuid4(), band="out")
    line = _line(item.id)
    # Falls through to Tier 4 (out, no meal).
    ctx = _ctx([item], verdicts={item.id: _verdict()}, habits=[item.id])
    out = _classify_lines([line], ctx, excluded=set())
    assert out[0][0] == 4
    assert out[0][2] == REASON_OUT_NO_MEAL


def test_tier1_not_applied_when_meal_booked_soon():
    item = _item(uuid4())
    line = _line(item.id)
    # Meal booked in 5 days — outside the 2-day never-cut window, but
    # inside the 7-day short-term demand window; Tier 1 rejects.
    demand = {item.id: _MealDemand(
        earliest=TODAY + timedelta(days=5),
        recipe_names=["Soup"],
        entry_count=1,
    )}
    ctx = _ctx(
        [item], demand=demand,
        verdicts={item.id: _verdict()}, habits=[item.id],
    )
    out = _classify_lines([line], ctx, excluded=set())
    # Tier 1 passes it over, and tier 5 picks it up: a meal needs it, but
    # not for 5 days. Before 2026-09-19 tier 5 also demanded the line be
    # stamped auto_recipe/auto_meal_plan, so a habit-sourced line for the
    # same far-off meal fell through every tier and was never offered as a
    # trim. The stamp is gone and the demand map — which is what actually
    # answers "when is this needed" — decides alone.
    assert len(out) == 1
    tier, _, reason, _saved = out[0]
    assert tier == 5
    day_label = (TODAY + timedelta(days=5)).strftime("%a")
    assert reason == REASON_FOR_RECIPE_ON_DAY.format(recipe="Soup", day=day_label)


# ── Tier 2: low-stock with cover ───────────────────────────────────────


def test_tier2_low_stock_with_cover():
    item = _item(uuid4(), band="low")
    line = _line(item.id)
    ctx = _ctx(
        [item],
        verdicts={item.id: _verdict()},
        cover={item.id: 8},
    )
    out = _classify_lines([line], ctx, excluded=set())
    assert out[0][0] == 2
    assert out[0][2] == REASON_COVER_LEFT.format(n=8)


def test_tier2_low_stock_no_cadence_signal_falls_to_not_urgent():
    item = _item(uuid4(), band="low")
    line = _line(item.id)
    ctx = _ctx([item], verdicts={item.id: _verdict()}, cover={item.id: None})
    out = _classify_lines([line], ctx, excluded=set())
    assert out[0][0] == 2
    assert out[0][2] == REASON_NOT_URGENT


def test_tier2_ignores_lines_with_short_term_demand():
    item = _item(uuid4(), band="low")
    line = _line(item.id)
    demand = {item.id: _MealDemand(earliest=TODAY + timedelta(days=3))}
    ctx = _ctx(
        [item], demand=demand,
        verdicts={item.id: _verdict()}, cover={item.id: 10},
    )
    out = _classify_lines([line], ctx, excluded=set())
    assert out == []


# ── Tier 3: buy-verdict wait ───────────────────────────────────────────


def test_tier3_verdict_wait_no_demand():
    item = _item(uuid4())
    line = _line(item.id)
    ctx = _ctx([item], verdicts={item.id: _verdict("wait")})
    out = _classify_lines([line], ctx, excluded=set())
    assert out[0][0] == 3
    assert out[0][2] == REASON_ABOVE_USUAL_PRICE


def test_tier3_skipped_when_out_of_stock():
    item = _item(uuid4(), band="out")
    line = _line(item.id)
    ctx = _ctx([item], verdicts={item.id: _verdict("wait")})
    out = _classify_lines([line], ctx, excluded=set())
    # Wait+out is a rough spot; brief §4 tier 3 requires not-out. Falls
    # through to Tier 4.
    assert out[0][0] == 4


def test_tier3_skipped_when_meal_booked_in_3d():
    item = _item(uuid4())
    line = _line(item.id)
    demand = {item.id: _MealDemand(earliest=TODAY + timedelta(days=2))}
    # But NOT in next 2 days (that would be never-cut). Set 2 == the
    # boundary — never-cut window is `<2 days`, so day-2 is exactly on
    # the demand boundary for tier 3 (< 3d window). Should be skipped.
    ctx = _ctx([item], demand=demand, verdicts={item.id: _verdict("wait")})
    out = _classify_lines([line], ctx, excluded=set())
    # Day-2 demand: never-cut window (< 2 days from today) is only
    # strictly less. `earliest - today = 2 days` — outside never-cut,
    # inside tier-3 (< 3d) filter → tier-3 skipped, but no other tier
    # matches a manual line without other signals.
    assert out == []


# ── Tier 4: out, no meal booked ────────────────────────────────────────


def test_tier4_out_no_meal_short_term():
    item = _item(uuid4(), band="out")
    line = _line(item.id)
    ctx = _ctx([item], verdicts={item.id: _verdict()})
    out = _classify_lines([line], ctx, excluded=set())
    assert out[0][0] == 4
    assert out[0][2] == REASON_OUT_NO_MEAL


# ── Tier 5: recipe / meal-plan scheduled ≥ 5 days out ──────────────────


def test_tier5_single_recipe_far_out():
    item = _item(uuid4())
    line = _line(item.id)
    demand = {item.id: _MealDemand(
        earliest=TODAY + timedelta(days=6),
        recipe_names=["Coq au vin"],
        entry_count=1,
    )}
    ctx = _ctx([item], demand=demand, verdicts={item.id: _verdict()})
    out = _classify_lines([line], ctx, excluded=set())
    assert out[0][0] == 5
    day_label = (TODAY + timedelta(days=6)).strftime("%a")
    assert out[0][2] == REASON_FOR_RECIPE_ON_DAY.format(recipe="Coq au vin", day=day_label)


def test_tier5_multi_meal_reference():
    item = _item(uuid4())
    line = _line(item.id)
    demand = {item.id: _MealDemand(
        earliest=TODAY + timedelta(days=6),
        recipe_names=["Soup", "Stew"],
        entry_count=4,
    )}
    ctx = _ctx([item], demand=demand, verdicts={item.id: _verdict()})
    out = _classify_lines([line], ctx, excluded=set())
    assert out[0][0] == 5
    assert out[0][2] == REASON_NEEDED_FOR_N_MEALS.format(n=4)


# ── Never-cut set ──────────────────────────────────────────────────────


def test_never_cut_essential():
    item = _item(uuid4(), is_essential=True)
    line = _line(item.id)
    ctx = _ctx([item], verdicts={item.id: _verdict()}, habits=[item.id])
    assert _classify_lines([line], ctx, excluded=set()) == []


def test_never_cut_meal_within_2_days():
    item = _item(uuid4())
    line = _line(item.id)
    # Meal tomorrow — never-cut wins over every tier.
    demand = {item.id: _MealDemand(earliest=TODAY + timedelta(days=1))}
    ctx = _ctx(
        [item], demand=demand,
        verdicts={item.id: _verdict()}, habits=[item.id],
    )
    assert _classify_lines([line], ctx, excluded=set()) == []


def test_never_cut_buy_verdict_on_low_stock():
    item = _item(uuid4(), band="low")
    line = _line(item.id)
    ctx = _ctx(
        [item],
        verdicts={item.id: _verdict("buy")},
        cover={item.id: 10},
    )
    assert _classify_lines([line], ctx, excluded=set()) == []


def test_never_cut_sub_two_dollar_line():
    item = _item(uuid4())
    line = _line(item.id)
    # Force the line under $2 by picked_offer_price × qty.
    line.picked_offer_price = 1.50
    line.quantity = 1
    ctx = _ctx([item], verdicts={item.id: _verdict()}, habits=[item.id])
    assert _classify_lines([line], ctx, excluded=set()) == []
    # Sanity: MIN_LINE_VALUE didn't drift out of range.
    assert MIN_LINE_VALUE == pytest.approx(2.00)


def test_excluded_line_not_cut():
    item = _item(uuid4())
    line = _line(item.id)
    ctx = _ctx([item], verdicts={item.id: _verdict()}, habits=[item.id])
    assert _classify_lines([line], ctx, excluded={line.id}) == []
