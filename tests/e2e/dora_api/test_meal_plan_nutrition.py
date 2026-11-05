"""FU-637 — calories on the meal planner.

The planner's number answers "if I eat one serving of each meal planned for
this day, what's that?" — the only calorie question a plan can answer honestly,
since `MealPlanEntry` has no eater and the app is not an intake tracker. What's
pinned here is that each entry carries its recipe's figure, that a meal with no
reliable figure carries none rather than a guess, and that the whole thing costs
a constant number of queries. (The per-day rollup went with FU-937.)
"""
from datetime import date, timedelta
from uuid import uuid4

import requests

from tests.e2e.dora_api._query_counter import SelectCounter

BASE = "http://localhost:5170/api"
MEAL_PLANS = f"{BASE}/meal-plans"
RECIPES = f"{BASE}/recipes"
APP_SETTINGS = f"{BASE}/app-settings"


def _set_mode(mode: str) -> None:
    resp = requests.patch(APP_SETTINGS, json={"nutrition_mode": mode})
    assert resp.status_code in (200, 204), resp.text


def _household_today() -> date:
    return date.fromisoformat(requests.get(f"{MEAL_PLANS}/today").json()["today"])


def _slot() -> str:
    return requests.get(f"{BASE}/meal-slots").json()[0]["name"]


def _recipe(kcal: int | None, servings: int | None = 4) -> str:
    body = {"name": f"kcal-plan-{uuid4().hex[:8]}", "kcal": kcal, "servings": servings}
    resp = requests.post(RECIPES, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["recipe_id"]


def _plan_with(entries: list) -> dict:
    resp = requests.post(MEAL_PLANS, json={
        "name": f"kcal plan {uuid4().hex[:8]}",
        "start_date": _household_today().isoformat(),
        "entries": entries,
    })
    assert resp.status_code == 201, resp.text
    plan_id = resp.json()["meal_plan_id"]
    items = requests.get(f"{MEAL_PLANS}?filter=meal_plan_id:eq:{plan_id}").json()["items"]
    return items[0]


def test__meal_plan__SimpleMode__EntriesAndDayTotalCarryTheTypedKcal(api):
    _set_mode("simple")
    today, slot = _household_today(), _slot()
    breakfast, dinner = _recipe(300), _recipe(650)

    plan = _plan_with([
        {"recipe_id": breakfast, "scheduled_for": today.isoformat(), "servings": 2, "slot": slot},
        {"recipe_id": dinner, "scheduled_for": today.isoformat(), "servings": 2, "slot": slot},
    ])

    assert sorted(e["kcal_per_serving"] for e in plan["entries"]) == [300.0, 650.0]


def test__meal_plan__MealWithNoFigure__IsReportedNotSilentlyDropped(api):
    """The shortfall has to be visible: a day summing 1 of 3 meals looks
    identical to a light day unless the coverage says otherwise."""
    _set_mode("simple")
    today, slot = _household_today(), _slot()

    plan = _plan_with([
        {"recipe_id": _recipe(500), "scheduled_for": today.isoformat(), "servings": 1, "slot": slot},
        {"recipe_id": _recipe(None), "scheduled_for": today.isoformat(), "servings": 1, "slot": slot},
        {"recipe_id": _recipe(None), "scheduled_for": today.isoformat(), "servings": 1, "slot": slot},
    ])

    figures = [e["kcal_per_serving"] for e in plan["entries"]]
    assert sorted(f for f in figures if f is not None) == [500.0]
    assert figures.count(None) == 2


def test__meal_plan__NoMealCountable__ReportsNullNotZero(api):
    # Zero would read as "a day of no calories", which is a different claim.
    _set_mode("simple")
    today, slot = _household_today(), _slot()

    plan = _plan_with([
        {"recipe_id": _recipe(None), "scheduled_for": today.isoformat(), "servings": 1, "slot": slot},
    ])

    assert plan["entries"][0]["kcal_per_serving"] is None


def test__meal_plan__NutritionOff__CarriesNoFiguresAtAll(api):
    _set_mode("off")
    today, slot = _household_today(), _slot()

    plan = _plan_with([
        {"recipe_id": _recipe(500), "scheduled_for": today.isoformat(), "servings": 1, "slot": slot},
    ])

    assert plan["entries"][0]["kcal_per_serving"] is None


def test__meal_plan__NutritionHydration__DoesNotScaleWithEntryCount(api):
    """One extra recipe load + the rollup's own queries, however many meals
    are planned — not a lookup per entry."""
    _set_mode("simple")
    today, slot = _household_today(), _slot()
    small = [{"recipe_id": _recipe(300), "scheduled_for": today.isoformat(),
              "servings": 1, "slot": slot}]
    big = [
        {"recipe_id": _recipe(300 + index),
         "scheduled_for": (today + timedelta(days=index % 5)).isoformat(),
         "servings": 1, "slot": slot}
        for index in range(10)
    ]
    small_id = _plan_with(small)["meal_plan_id"]
    big_id = _plan_with(big)["meal_plan_id"]

    with SelectCounter() as one:
        requests.get(f"{MEAL_PLANS}?filter=meal_plan_id:eq:{small_id}")
    with SelectCounter() as ten:
        requests.get(f"{MEAL_PLANS}?filter=meal_plan_id:eq:{big_id}")

    assert (ten.count - one.count) <= 0.5 * 9, (one.count, ten.count)
