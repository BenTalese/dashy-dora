"""Owner feedback 2026-08-27 — the meal-plan ingredient aggregate gained two
facts the shared add-to-list picker needs: whether an item is *optional* across
the whole week, and which ingredient rows couldn't be turned into list lines at
all.

Both are aggregation rules rather than per-row echoes, which is exactly why they
belong to the server (R-003) and why they're pinned here: "optional" only holds
when every contributing row was optional, and an unlinked row must be *reported*
rather than silently skipped — FU-505's guarantee, which used to be delivered by
the auto-generate endpoint the picker replaced.

Drives `aggregate_meal_plan_ingredients` against a fake repository — no DB, no
HTTP. The endpoints are covered end-to-end by
`tests/e2e/dora_api/test_meal_plan_preview.py`.
"""
from types import SimpleNamespace
from uuid import uuid4

from dora_api.features.meal_plans.get_meal_plan_ingredients import (
    aggregate_meal_plan_ingredients)


def _stock_item(name):
    return SimpleNamespace(id=uuid4(), name=name)


def _ingredient(stock_item, *, quantity=1.0, unit="g", is_optional=False,
                raw_text=None):
    return SimpleNamespace(
        stock_item=stock_item, quantity=quantity, unit=unit,
        is_optional=is_optional, raw_text=raw_text,
    )


class _FakeRepository:
    """Answers the one query shape the aggregator makes:
    `.get(Recipe).include(...).then_include(...).all(id.in_(ids))`."""

    def __init__(self, recipes_by_id):
        self._recipes = recipes_by_id

    def get(self, _entity):
        return self

    def include(self, _field):
        return self

    def then_include(self, _field):
        return self

    def all(self, id_filter):
        return [self._recipes[i] for i in id_filter.values if i in self._recipes]


def _recipe(name, ingredients, *, servings=1):
    return SimpleNamespace(
        id=uuid4(), name=name, servings=servings, ingredients=ingredients,
    )


def _aggregate(recipes, demand):
    repo = _FakeRepository({r.id: r for r in recipes})
    return aggregate_meal_plan_ingredients(repo, demand)


# ── is_optional — "required wins" across the whole week ────────────────────


def test__optional_in_every_recipe__stays_optional():
    parsley = _stock_item("parsley")
    a = _recipe("soup", [_ingredient(parsley, is_optional=True)])
    b = _recipe("stew", [_ingredient(parsley, is_optional=True)])

    result = _aggregate([a, b], {a.id: 1, b.id: 1})

    assert [i.is_optional for i in result.items] == [True]


def test__required_in_one_recipe__whole_item_is_required():
    """The week has to buy it, so the picker must tick it by default — an
    optional garnish in one meal doesn't make it optional in the other."""
    parsley = _stock_item("parsley")
    garnish = _recipe("soup", [_ingredient(parsley, is_optional=True)])
    core = _recipe("salsa verde", [_ingredient(parsley, is_optional=False)])

    result = _aggregate([garnish, core], {garnish.id: 1, core.id: 1})

    assert [i.is_optional for i in result.items] == [False]


def test__required_row_seen_after_optional_row__still_required():
    """Order-independence: the flag starts True and can only be cleared, so a
    late required row can't be overwritten by an earlier optional one."""
    parsley = _stock_item("parsley")
    both = _recipe("two rows", [
        _ingredient(parsley, is_optional=True),
        _ingredient(parsley, is_optional=False),
    ])

    result = _aggregate([both], {both.id: 1})

    assert [i.is_optional for i in result.items] == [False]


# ── unlinked rows — reported, not dropped ─────────────────────────────────


def test__unlinked_ingredient__is_reported_with_its_recipe():
    linked = _stock_item("flour")
    recipe = _recipe("pancakes", [
        _ingredient(linked),
        _ingredient(None, raw_text="1 cup of something"),
    ])

    result = _aggregate([recipe], {recipe.id: 1})

    assert [i.stock_item_name for i in result.items] == ["flour"]
    assert len(result.unlinked) == 1
    assert result.unlinked[0].recipe_name == "pancakes"
    assert result.unlinked[0].ingredient_name == "1 cup of something"


def test__unlinked_ingredient_with_no_raw_text__gets_a_placeholder_name():
    """A nameless row still has to be nameable in the dialog's list."""
    recipe = _recipe("mystery", [_ingredient(None, raw_text="   ")])

    result = _aggregate([recipe], {recipe.id: 1})

    assert result.items == []
    assert [u.ingredient_name for u in result.unlinked] == ["(unnamed ingredient)"]


def test__empty_demand__returns_an_empty_envelope():
    result = _aggregate([], {})

    assert result.items == []
    assert result.unlinked == []


# ── the existing scaling contract still holds through the envelope ─────────


def test__quantities_still_scale_by_servings():
    flour = _stock_item("flour")
    recipe = _recipe("bread", [_ingredient(flour, quantity=100.0)], servings=2)

    result = _aggregate([recipe], {recipe.id: 6})

    assert result.items[0].total_quantity == 300.0
