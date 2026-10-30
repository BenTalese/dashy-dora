"""POST /api/shopping-lists/<id>/trim-to-budget — the HTTP seam.

The classifier tiers are unit-pinned in `tests/test_trim_to_budget.py` over a
hand-built demand map. What only a live request can prove is that the demand
map is actually *built*: `_load_meal_demand` read the noload
`RecipeIngredient.stock_item` relationship (R-032), so it always came back
empty and no meal-demand rule ever fired.

Dates derive from the household-today anchor (2026-07-10 timezone-flake rule).
"""
from datetime import date, timedelta
from uuid import uuid4

import requests

from dora_api.features.shopping_lists.trim_to_budget import (
    FAR_OUT_MIN_DAYS, SHORT_TERM_DEMAND_DAYS)

BASE = "http://localhost:5170/api"
LISTS = f"{BASE}/shopping-lists"


def _household_today() -> date:
    return date.fromisoformat(requests.get(f"{BASE}/meal-plans/today").json()["today"])


def _stocked_item() -> str:
    levels = requests.get(f"{BASE}/stock-levels").json()["items"]
    resp = requests.post(f"{BASE}/stock-items", json={
        "name": f"trim-{uuid4().hex[:8]}",
        "stock_level_id": next(l["stock_level_id"] for l in levels if l["sequence"] == 0),
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["stock_item_id"]


def _plan_meal_needing(stock_item_id: str, *, days_out: int) -> str:
    recipe_name = f"Trim Recipe {uuid4().hex[:8]}"
    recipe = requests.post(f"{BASE}/recipes", json={
        "name": recipe_name,
        "ingredients": [{"stock_item_id": stock_item_id, "quantity": 1, "unit": "cup"}],
    })
    assert recipe.status_code == 201, recipe.text
    today = _household_today()
    plan = requests.post(f"{BASE}/meal-plans", json={
        "start_date": today.isoformat(),
        "entries": [{
            "recipe_id": recipe.json()["recipe_id"],
            "scheduled_for": (today + timedelta(days=days_out)).isoformat(),
            "servings": 2,
            "slot": requests.get(f"{BASE}/meal-slots").json()[0]["name"],
        }],
    })
    assert plan.status_code == 201, plan.text
    return recipe_name


def _list_with_priced_line(stock_item_id: str) -> str:
    list_id = requests.post(LISTS, json={"name": f"Trim-{uuid4().hex[:8]}"}).json()["shopping_list_id"]
    line_id = requests.post(
        f"{LISTS}/{list_id}/lines", json={"stock_item_id": stock_item_id},
    ).json()["line_id"]
    assert requests.patch(
        f"{LISTS}/{list_id}/lines/{line_id}", json={"actual_unit_price": 10.0},
    ).status_code == 204
    return list_id


def test__trim_to_budget__ItemNeededByAFarOffMeal__CutWithTheRecipeReason(api):
    assert FAR_OUT_MIN_DAYS < SHORT_TERM_DEMAND_DAYS  # the meal must sit inside the window
    item_id = _stocked_item()
    recipe_name = _plan_meal_needing(item_id, days_out=FAR_OUT_MIN_DAYS)
    list_id = _list_with_priced_line(item_id)

    resp = requests.post(f"{LISTS}/{list_id}/trim-to-budget", json={"budget_target": 0})

    assert resp.status_code == 200, resp.text
    trimmed = resp.json()["trimmed"]
    assert len(trimmed) == 1
    assert trimmed[0]["tier"] == 5
    assert recipe_name in trimmed[0]["reason_chip"]

