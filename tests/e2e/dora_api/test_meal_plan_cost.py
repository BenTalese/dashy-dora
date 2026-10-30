"""Owner 2026-09-05 — money on the meal planner.

*"Can't see much in the way of budget and money… no display of estimated weekly
cost for meals."* The planner now carries a cost per planned meal, per day and
per week. What's pinned here is the part a screen can't be trusted to prove:
that the per-entry figure scales with the meal's **planned** servings rather
than quoting the recipe's own total, that the rollups agree with the entries
they're built from, that an unpriceable meal is reported in the coverage rather
than quietly dropped, and that the whole thing disappears when money features
are off (R-058 / the install-wide gate).

Determinism: dates come from the household-today anchor, never a local
wall-clock read (2026-07-10 timezone-flake rule).
"""
from datetime import date
from uuid import uuid4

import pytest
import requests

from tests.factories import make_stock_item
from tests.support import set_money_enabled

BASE = "http://localhost:5170/api"
MEAL_PLANS = f"{BASE}/meal-plans"
RECIPES = f"{BASE}/recipes"


@pytest.fixture(autouse=True)
def _restore_money_setting(api):
    """`money_enabled` is install-wide, so a test that flips it would leak into
    every test after it in the session. Put it back."""
    original = requests.get(f"{BASE}/app-settings").json()["money_enabled"]
    yield
    set_money_enabled(original)


def _household_today() -> date:
    return date.fromisoformat(requests.get(f"{MEAL_PLANS}/today").json()["today"])


def _slot() -> str:
    return requests.get(f"{BASE}/meal-slots").json()[0]["name"]


def _stock_level_id(sequence: int) -> str:
    levels = requests.get(f"{BASE}/stock-levels").json()["items"]
    return next(l["stock_level_id"] for l in levels if l["sequence"] == sequence)


def _priced_item(*, price_now: float, size_value: float) -> dict:
    """A stocked item linked to an active product, giving a unit price of
    `price_now / size_value` per litre. Same construction as the recipe
    router's cost suite — the real StockItemProduct → Product → ProductOffer
    join, not a stubbed price."""
    item = make_stock_item(
        stock_level_id=_stock_level_id(0), name=f"Plan cost item {uuid4().hex[:8]}",
    )
    suffix = uuid4().hex[:8]
    product = requests.post(f"{BASE}/products", json={
        "name": f"PlanCostProduct-{suffix}",
        "store_name": "Woolworths",
        "merchant_stockcode": f"PLANCOST-{suffix}",
        "brand": "Test",
        "price_now": price_now,
        "price_was": price_now + 5,
        "is_active": True,
        "is_available": True,
        "size": f"{size_value}L",
        "size_unit": "L",
        "size_value": size_value,
    })
    assert product.status_code == 201, product.text
    product_id = product.headers["location"].rsplit(":", 1)[-1]
    link = requests.post(
        f"{BASE}/stock-items/{item['stock_item_id']}/products",
        json={"product_id": product_id},
    )
    assert link.status_code in (200, 204), link.text
    return item


def _recipe(*, servings: int | None, ingredients: list) -> str:
    resp = requests.post(RECIPES, json={
        "name": f"plan-cost-{uuid4().hex[:8]}",
        "servings": servings,
        "ingredients": ingredients,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["recipe_id"]


def _plan_with(entries: list) -> dict:
    resp = requests.post(MEAL_PLANS, json={
        "name": f"cost plan {uuid4().hex[:8]}",
        "start_date": _household_today().isoformat(),
        "entries": entries,
    })
    assert resp.status_code == 201, resp.text
    plan_id = resp.json()["meal_plan_id"]
    items = requests.get(f"{MEAL_PLANS}?filter=meal_plan_id:eq:{plan_id}").json()["items"]
    return items[0]


def _four_dollar_recipe(servings: int = 4) -> str:
    """$8.00 per litre, 0.5 L in the recipe → $4.00 for the whole recipe."""
    priced = _priced_item(price_now=8.0, size_value=1.0)
    return _recipe(
        servings=servings,
        ingredients=[{"stock_item_id": priced["stock_item_id"],
                      "quantity": 0.5, "unit": "L"}],
    )


def _unpriced_recipe(servings: int = 4) -> str:
    item = make_stock_item(
        stock_level_id=_stock_level_id(0), name=f"Unpriced {uuid4().hex[:8]}",
    )
    return _recipe(
        servings=servings,
        ingredients=[{"stock_item_id": item["stock_item_id"],
                      "quantity": 1, "unit": "L"}],
    )


def test__meal_plan_cost__EntryIsPricedAtItsPlannedServings__NotTheRecipesOwn(api):
    """The recipe costs $4.00 and yields 4 servings, so it is $1.00 a serving.
    Planned for 2 the meal costs $2.00 — quoting the recipe's $4.00 would price
    the pot rather than the plan."""
    set_money_enabled(True)
    today, slot = _household_today(), _slot()

    plan = _plan_with([
        {"recipe_id": _four_dollar_recipe(), "scheduled_for": today.isoformat(),
         "servings": 2, "slot": slot},
    ])

    assert plan["entries"][0]["estimated_cost"] == 2.0
    assert plan["estimated_cost"] == 2.0
    assert (plan["cost_counted_meals"], plan["cost_total_meals"]) == (1, 1)


def test__create_meal_plan__PricedRecipe__ResponseBodyCarriesTheCost(api):
    """The POST echo is built by `handle_by_id`; while it held the plan, its
    recipes sat in the identity map with `ingredients` noloaded EMPTY and the
    cost pass priced nothing (R-032)."""
    set_money_enabled(True)
    today, slot = _household_today(), _slot()

    resp = requests.post(MEAL_PLANS, json={
        "start_date": today.isoformat(),
        "entries": [{"recipe_id": _four_dollar_recipe(), "scheduled_for": today.isoformat(),
                     "servings": 2, "slot": slot}],
    })

    assert resp.status_code == 201, resp.text
    assert resp.json()["entries"][0]["estimated_cost"] == 2.0
    assert resp.json()["estimated_cost"] == 2.0


def test__meal_plan_cost__DayAndWeekTotals__AgreeWithTheEntriesTheySum(api):
    set_money_enabled(True)
    today, slot = _household_today(), _slot()

    plan = _plan_with([
        {"recipe_id": _four_dollar_recipe(), "scheduled_for": today.isoformat(),
         "servings": 2, "slot": slot},
        {"recipe_id": _four_dollar_recipe(), "scheduled_for": today.isoformat(),
         "servings": 4, "slot": slot},
    ])

    assert sorted(e["estimated_cost"] for e in plan["entries"]) == [2.0, 4.0]
    day = next(d for d in plan["day_cost"] if d["scheduled_for"] == today.isoformat())
    assert day["estimated_cost"] == 6.0
    assert (day["counted_meals"], day["total_meals"]) == (2, 2)
    assert plan["estimated_cost"] == 6.0


def test__meal_plan_cost__UnpriceableMeal__IsReportedNotSilentlyDropped(api):
    """A week summing 1 of 2 meals looks identical to a cheap week unless the
    coverage says otherwise (R-041)."""
    set_money_enabled(True)
    today, slot = _household_today(), _slot()

    plan = _plan_with([
        {"recipe_id": _four_dollar_recipe(), "scheduled_for": today.isoformat(),
         "servings": 4, "slot": slot},
        {"recipe_id": _unpriced_recipe(), "scheduled_for": today.isoformat(),
         "servings": 4, "slot": slot},
    ])

    assert plan["estimated_cost"] == 4.0
    assert (plan["cost_counted_meals"], plan["cost_total_meals"]) == (1, 2)


def test__meal_plan_cost__RecipeWithNoServings__CannotBeScaledSoCarriesNoFigure(api):
    """There is no per-serving figure to multiply, and inventing one would be a
    guess — the same rule the cookbook's cost-per-serving sort follows."""
    set_money_enabled(True)
    today, slot = _household_today(), _slot()

    plan = _plan_with([
        {"recipe_id": _four_dollar_recipe(servings=None),
         "scheduled_for": today.isoformat(), "servings": 2, "slot": slot},
    ])

    assert plan["entries"][0]["estimated_cost"] is None
    # None rather than 0.0: zero would read as a free week.
    assert plan["estimated_cost"] is None
    assert (plan["cost_counted_meals"], plan["cost_total_meals"]) == (0, 1)


def test__meal_plan_cost__MoneyOff__CarriesNoFiguresAtAll(api):
    set_money_enabled(False)
    today, slot = _household_today(), _slot()

    plan = _plan_with([
        {"recipe_id": _four_dollar_recipe(), "scheduled_for": today.isoformat(),
         "servings": 2, "slot": slot},
    ])

    assert plan["entries"][0]["estimated_cost"] is None
    assert plan["day_cost"] == []
    assert plan["estimated_cost"] is None
