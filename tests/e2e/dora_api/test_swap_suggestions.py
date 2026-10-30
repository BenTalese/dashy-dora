"""FU-451 — budget-defense swap endpoints (end-to-end).

Covers the money-features gate, the swap-suggestions shape, and the
apply → undo round-trip through the real endpoints. The ranker's candidate
logic is pinned separately in `tests/test_swap_suggestions.py`; here we drive
apply/undo with an explicit `to_recipe_id` so the round-trip doesn't depend on
the ranker producing a candidate.
"""
import uuid
from datetime import date

import requests

BASE = "http://localhost:5170/api"
MEAL_PLANS = f"{BASE}/meal-plans"


def _set_money(on: bool) -> None:
    # Money is a single install-wide flag now — no per-user layer.
    requests.patch(f"{BASE}/app-settings", json={"money_enabled": on})


def _set_budget(amount, period: str = "weekly") -> None:
    # Household budget (install-wide), edited via the any-user endpoint.
    requests.patch(f"{BASE}/budget/settings", json={"amount": amount, "period": period})


def _two_recipe_ids() -> tuple[str, str]:
    items = requests.get(f"{BASE}/recipes?limit=5").json()["items"]
    assert len(items) >= 2, "seed data should have >= 2 recipes"
    return items[0]["recipe_id"], items[1]["recipe_id"]


def _today() -> date:
    return date.fromisoformat(requests.get(f"{MEAL_PLANS}/today").json()["today"])


def _plan_entries(plan_id: str) -> list:
    plans = requests.get(f"{MEAL_PLANS}?limit=100").json()["items"]
    plan = next((p for p in plans if p["meal_plan_id"] == plan_id), None)
    assert plan is not None, "created plan should be listed"
    return plan["entries"]


def _make_plan_with_entry(recipe_id: str) -> tuple[str, str]:
    today = _today()
    created = requests.post(MEAL_PLANS, json={
        "start_date": today.isoformat(),
        "entries": [{
            "recipe_id": recipe_id,
            "scheduled_for": today.isoformat(),
            "servings": 2,
            "slot": "Dinner",
        }],
    })
    assert created.status_code in (200, 201), created.text
    plan_id = created.json()["meal_plan_id"]
    entry_id = _plan_entries(plan_id)[0]["meal_plan_entry_id"]
    return plan_id, entry_id


def test__swap_suggestions__shape_and_money_gate(api):
    recipe_a, _ = _two_recipe_ids()
    _set_money(True)
    # Tiny budget so any priced week is projected over.
    _set_budget(1.0, "weekly")
    plan_id, _ = _make_plan_with_entry(recipe_a)
    try:
        resp = requests.get(f"{MEAL_PLANS}/{plan_id}/swap-suggestions")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        for key in (
            "projected_over", "cost_per_week", "cost_per_week_priced_ratio",
            "budget_amount", "overshoot", "projected_after_applying_all", "candidates",
        ):
            assert key in body, f"missing {key}"
        assert isinstance(body["candidates"], list)

        # Money off → the whole surface zeroes out defensively.
        _set_money(False)
        off = requests.get(f"{MEAL_PLANS}/{plan_id}/swap-suggestions").json()
        assert off["projected_over"] is False
        assert off["candidates"] == []
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")
        _set_money(True)


def test__apply_and_undo_swap__round_trips_the_entry_recipe(api):
    recipe_a, recipe_b = _two_recipe_ids()
    _set_money(True)
    plan_id, entry_id = _make_plan_with_entry(recipe_a)
    try:
        applied = requests.post(f"{MEAL_PLANS}/{plan_id}/apply-swap", json={
            "kind": "recipe", "entry_id": entry_id, "to_recipe_id": recipe_b,
        })
        assert applied.status_code == 200, applied.text
        ledger_id = applied.json()["swap_ledger_id"]

        after = _plan_entries(plan_id)
        assert after[0]["recipe_id"] == recipe_b, "entry should now hold the swapped recipe"

        undone = requests.post(f"{MEAL_PLANS}/{plan_id}/undo-swap", json={
            "swap_ledger_id": ledger_id,
        })
        assert undone.status_code == 200, undone.text

        restored = _plan_entries(plan_id)
        assert restored[0]["recipe_id"] == recipe_a, "undo should restore the original recipe"

        # Second undo of the same ledger row is rejected.
        again = requests.post(f"{MEAL_PLANS}/{plan_id}/undo-swap", json={
            "swap_ledger_id": ledger_id,
        })
        assert again.status_code == 422, again.text
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")


def test__apply_swap__stale_expected_from_recipe__conflicts(api):
    recipe_a, recipe_b = _two_recipe_ids()
    _set_money(True)
    plan_id, entry_id = _make_plan_with_entry(recipe_a)
    try:
        resp = requests.post(f"{MEAL_PLANS}/{plan_id}/apply-swap", json={
            "kind": "recipe", "entry_id": entry_id, "to_recipe_id": recipe_b,
            "expected_from_recipe_id": str(uuid.uuid4()),  # not the real current recipe
        })
        assert resp.status_code == 409, resp.text
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")


def test__apply_swap__CookBatchDay__Refused(api):
    """FU-956 (owner, 2026-10-30) — one day of a cook batch can't take a
    different recipe; the batch would mix recipes."""
    recipe_a, recipe_b = _two_recipe_ids()
    _set_money(True)
    today = _today()
    created = requests.post(MEAL_PLANS, json={
        "start_date": today.isoformat(),
        "entries": [
            {"recipe_id": recipe_a, "scheduled_for": today.isoformat(),
             "servings": 2, "slot": "Dinner", "cook_key": "b"},
            {"recipe_id": recipe_a, "scheduled_for": date.fromordinal(today.toordinal() + 1).isoformat(),
             "servings": 2, "slot": "Dinner", "cook_key": "b"},
        ],
    })
    assert created.status_code in (200, 201), created.text
    plan_id = created.json()["meal_plan_id"]
    try:
        entry = _plan_entries(plan_id)[0]
        assert entry["cook_batch_id"] is not None
        resp = requests.post(f"{MEAL_PLANS}/{plan_id}/apply-swap", json={
            "kind": "recipe", "entry_id": entry["meal_plan_entry_id"], "to_recipe_id": recipe_b,
        })
        assert resp.status_code == 422, resp.text
        assert {e["recipe_id"] for e in _plan_entries(plan_id)} == {recipe_a}
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")


def test__apply_swap__money_off__rejected(api):
    recipe_a, recipe_b = _two_recipe_ids()
    _set_money(True)
    plan_id, entry_id = _make_plan_with_entry(recipe_a)
    _set_money(False)
    try:
        resp = requests.post(f"{MEAL_PLANS}/{plan_id}/apply-swap", json={
            "kind": "recipe", "entry_id": entry_id, "to_recipe_id": recipe_b,
        })
        assert resp.status_code == 422, resp.text
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")
        _set_money(True)


def test__swap_suggestions__PlanInAFutureWeek__MeasuredAgainstThatWeeksPeriod(api, monkeypatch):
    """The plan's cost is compared to the money left in the period its week
    falls in, not today's — planning next week against this week's part-spent
    budget flagged it over budget spuriously."""
    from datetime import timedelta

    import dora_api.features.meal_plans.swap_suggestions as swaps

    asked: list[date] = []
    monkeypatch.setattr(swaps, "period_headroom", lambda on, repo: asked.append(on) or 1000.0)
    _set_money(True)
    _set_budget(100.0, "weekly")
    next_week = _today() + timedelta(days=7)
    created = requests.post(MEAL_PLANS, json={"start_date": next_week.isoformat()})
    assert created.status_code == 201, created.text

    resp = requests.get(f"{MEAL_PLANS}/{created.json()['meal_plan_id']}/swap-suggestions")

    assert resp.status_code == 200, resp.text
    assert asked == [next_week]


def test__period_headroom__MoneyFeaturesOff__IsNone(api):
    """Same gate `household_budget` applies: a stored budget on a money-off
    install constrains nothing (the trim optimiser read it ungated)."""
    from dora_api.app import app
    from dora_api.features.budget.budget import period_headroom
    from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

    _set_money(True)
    _set_budget(100.0, "weekly")
    _set_money(False)
    try:
        with app.app_context():
            headroom = period_headroom(_today(), SqlAlchemyRepository())
    finally:
        _set_money(True)

    assert headroom is None
