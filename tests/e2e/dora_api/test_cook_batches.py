"""PROPOSAL_MEAL_PLANS_PART_2 Phase 1 — cook-batch write path + read view.

Covers the `cook_key` grouping on create/update, the structural validation of a
cook batch (>=2 days, one recipe, one slot, distinct days), the server-derived
read view (is_cook_day / total yield / size), and the forward-replace batch
lifecycle (a batch is replaced on edit, un-linking on removal, no orphans).

Determinism: dates derive from the household-today anchor; slots from the live
vocabulary (2026-07-10 timezone-flake rule), mirroring test_meal_plan_router.py.
"""
from datetime import timedelta
from uuid import uuid4

import requests

from tests.support import assert_envelope

BASE = "http://localhost:5170/api"
MEAL_PLANS = f"{BASE}/meal-plans"
RECIPES = f"{BASE}/recipes"
APP_SETTINGS = f"{BASE}/app-settings"


def _household_today():
    from datetime import date
    return date.fromisoformat(requests.get(f"{MEAL_PLANS}/today").json()["today"])


def _slot_names() -> list[str]:
    return [s["name"] for s in requests.get(f"{BASE}/meal-slots").json()]


def _make_recipe(prefix="CookBatch Recipe") -> str:
    resp = requests.post(RECIPES, json={"name": f"{prefix} {uuid4().hex[:8]}"})
    assert resp.status_code == 201, resp.text
    return resp.json()["recipe_id"]


def _create(entries, expect=201):
    body = {"start_date": _household_today().isoformat(), "entries": entries}
    resp = requests.post(MEAL_PLANS, json=body)
    assert resp.status_code == expect, resp.text
    return resp


def _by_id(meal_plan_id: str) -> dict | None:
    items = assert_envelope(
        requests.get(f"{MEAL_PLANS}?filter=meal_plan_id:eq:{meal_plan_id}")
    )
    return items[0] if items else None


# ── create: a valid cook batch links entries and derives the view ──────────

def test__create__cook_batch__links_entries_and_derives_view(api):
    today = _household_today()
    slot = _slot_names()[0]
    recipe = _make_recipe()
    resp = _create([
        {"recipe_id": recipe, "scheduled_for": (today + timedelta(days=d)).isoformat(),
         "servings": 2, "slot": slot, "cook_key": "c1"}
        for d in (2, 0, 1)  # deliberately out of order — cook-day is the earliest
    ])
    plan = _by_id(resp.json()["meal_plan_id"])
    entries = plan["entries"]
    assert len(entries) == 3

    batch_ids = {e["cook_batch_id"] for e in entries}
    assert batch_ids != {None} and len(batch_ids) == 1, "all three share one batch"

    for e in entries:
        assert e["cook_batch_size"] == 3
        assert e["cook_batch_total_servings"] == 6  # 3 x 2 servings
    cook_days = [e for e in entries if e["is_cook_day"]]
    assert len(cook_days) == 1, "exactly one cook-day"
    assert cook_days[0]["scheduled_for"] == today.isoformat(), "earliest day is the cook"


def test__create__standalone_entries__have_no_batch(api):
    today = _household_today()
    slot = _slot_names()[0]
    recipe = _make_recipe()
    resp = _create([
        {"recipe_id": recipe, "scheduled_for": today.isoformat(), "slot": slot},
        {"recipe_id": recipe, "scheduled_for": (today + timedelta(days=1)).isoformat(), "slot": slot},
    ])
    entries = _by_id(resp.json()["meal_plan_id"])["entries"]
    for e in entries:
        assert e["cook_batch_id"] is None
        assert e["is_cook_day"] is False
        assert e["cook_batch_total_servings"] is None
        assert e["cook_batch_size"] is None


# ── create: structural validation (all → 400) ─────────────────────────────

def _bad(entries):
    resp = _create(entries, expect=400)
    return resp.text


def test__create__cook_batch_single_day__rejected(api):
    today = _household_today()
    slot = _slot_names()[0]
    recipe = _make_recipe()
    txt = _bad([{"recipe_id": recipe, "scheduled_for": today.isoformat(), "slot": slot, "cook_key": "c1"}])
    assert "at least two days" in txt


def test__create__cook_batch_two_recipes__rejected(api):
    today = _household_today()
    slot = _slot_names()[0]
    r1, r2 = _make_recipe(), _make_recipe()
    txt = _bad([
        {"recipe_id": r1, "scheduled_for": today.isoformat(), "slot": slot, "cook_key": "c1"},
        {"recipe_id": r2, "scheduled_for": (today + timedelta(days=1)).isoformat(), "slot": slot, "cook_key": "c1"},
    ])
    assert "single recipe" in txt


def test__create__cook_batch_two_slots__rejected(api):
    slots = _slot_names()
    if len(slots) < 2:
        import pytest
        pytest.skip("needs >=2 configured meal slots")
    today = _household_today()
    recipe = _make_recipe()
    txt = _bad([
        {"recipe_id": recipe, "scheduled_for": today.isoformat(), "slot": slots[0], "cook_key": "c1"},
        {"recipe_id": recipe, "scheduled_for": (today + timedelta(days=1)).isoformat(), "slot": slots[1], "cook_key": "c1"},
    ])
    assert "same meal slot" in txt


def test__create__cook_batch_repeated_day__rejected(api):
    today = _household_today()
    slot = _slot_names()[0]
    recipe = _make_recipe()
    txt = _bad([
        {"recipe_id": recipe, "scheduled_for": today.isoformat(), "slot": slot, "cook_key": "c1"},
        {"recipe_id": recipe, "scheduled_for": today.isoformat(), "slot": slot, "cook_key": "c1"},
    ])
    assert "same day" in txt


# ── update: forward batch is replaced; removal un-links with no orphan ──────

def test__update__replaces_and_unlinks_batch(api):
    today = _household_today()
    slot = _slot_names()[0]
    recipe = _make_recipe()
    resp = _create([
        {"recipe_id": recipe, "scheduled_for": (today + timedelta(days=d)).isoformat(),
         "servings": 1, "slot": slot, "cook_key": "c1"}
        for d in (0, 1)
    ])
    plan_id = resp.json()["meal_plan_id"]
    first_batch = _by_id(plan_id)["entries"][0]["cook_batch_id"]
    assert first_batch is not None

    # Re-plan the same week as a NEW batch of three days.
    patch = requests.patch(f"{MEAL_PLANS}/{plan_id}", json={"entries": [
        {"recipe_id": recipe, "scheduled_for": (today + timedelta(days=d)).isoformat(),
         "servings": 1, "slot": slot, "cook_key": "c2"}
        for d in (0, 1, 2)
    ]})
    assert patch.status_code == 204, patch.text
    entries = _by_id(plan_id)["entries"]
    assert len(entries) == 3
    new_ids = {e["cook_batch_id"] for e in entries}
    assert len(new_ids) == 1 and first_batch not in new_ids, "old batch replaced by a new one"

    # Now drop the grouping entirely — entries become standalone, no orphan batch.
    patch2 = requests.patch(f"{MEAL_PLANS}/{plan_id}", json={"entries": [
        {"recipe_id": recipe, "scheduled_for": today.isoformat(), "servings": 1, "slot": slot},
    ]})
    assert patch2.status_code == 204, patch2.text
    entries = _by_id(plan_id)["entries"]
    assert len(entries) == 1
    assert entries[0]["cook_batch_id"] is None


def test__update__BatchStraddlingTodayWithOneForwardDay__IsAccepted(api):
    """The cook day is past (preserved server-side), so the payload carries just
    one leftover day under the batch's id. That's still a two-day batch — the
    one-member rule used to reject it and freeze the week."""
    from sqlalchemy import text

    from dora_api.app import app, db
    from tests.support import uuid_bind

    today = _household_today()
    slot = _slot_names()[0]
    recipe = _make_recipe()
    plan_id = _create([
        {"recipe_id": recipe, "scheduled_for": (today + timedelta(days=d)).isoformat(),
         "servings": 1, "slot": slot, "cook_key": "c1"}
        for d in (0, 1)
    ]).json()["meal_plan_id"]
    entries = _by_id(plan_id)["entries"]
    cook_day = next(e for e in entries if e["scheduled_for"] == today.isoformat())
    batch_id = cook_day["cook_batch_id"]
    with app.app_context(), db.engine.begin() as conn:
        conn.execute(
            text('UPDATE "MealPlanEntry" SET scheduled_for = :d WHERE id = :eid'),
            {"d": (today - timedelta(days=1)).isoformat(),
             "eid": uuid_bind(cook_day["meal_plan_entry_id"])},
        )

    patch = requests.patch(f"{MEAL_PLANS}/{plan_id}", json={"entries": [
        {"recipe_id": recipe, "scheduled_for": (today + timedelta(days=1)).isoformat(),
         "servings": 1, "slot": slot, "cook_key": batch_id},
    ]})

    assert patch.status_code == 204, patch.text
    assert {e["cook_batch_id"] for e in _by_id(plan_id)["entries"]} == {batch_id}


# ── demand is batch-invariant (the Σ-yield model): the ingredient demand for a
#    linked batch equals the demand for the same entries unlinked — cooking once
#    vs three times buys the same food. Pins that the aggregation ignores linking
#    (PROPOSAL_MEAL_PLANS_PART_2 §6 correction). Uses a seeded recipe that has
#    ingredients so the comparison is non-trivial; skips if none is found.

def _ingredients(meal_plan_id: str) -> list:
    # Envelope since 2026-08-27 — `{items, unlinked}`; unlinked rows have no
    # stock item so they can't ride inside the item list.
    resp = requests.get(f"{MEAL_PLANS}/{meal_plan_id}/ingredients")
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


def _recipe_with_ingredients() -> str | None:
    listing = assert_envelope(requests.get(f"{RECIPES}?limit=50"))
    for r in listing:
        rid = r["recipe_id"]
        today = _household_today()
        slot = _slot_names()[0]
        probe = requests.post(MEAL_PLANS, json={
            "start_date": today.isoformat(),
            "entries": [{"recipe_id": rid, "scheduled_for": today.isoformat(),
                         "servings": 1, "slot": slot}],
        })
        if probe.status_code != 201:
            continue
        pid = probe.json()["meal_plan_id"]
        if _ingredients(pid):
            requests.delete(f"{MEAL_PLANS}/{pid}")
            return rid
        requests.delete(f"{MEAL_PLANS}/{pid}")
    return None


def test__ingredient_demand__is_identical_linked_vs_unlinked(api):
    recipe = _recipe_with_ingredients()
    if recipe is None:
        import pytest
        pytest.skip("no seeded recipe with ingredients to compare against")
    today = _household_today()
    slot = _slot_names()[0]
    days = [(today + timedelta(days=d)).isoformat() for d in (0, 1, 2)]

    linked = _create([
        {"recipe_id": recipe, "scheduled_for": d, "servings": 2, "slot": slot, "cook_key": "c1"}
        for d in days
    ]).json()["meal_plan_id"]
    unlinked = _create([
        {"recipe_id": recipe, "scheduled_for": d, "servings": 2, "slot": slot}
        for d in days
    ]).json()["meal_plan_id"]

    def norm(rows):
        return sorted((r["stock_item_id"], r["total_quantity"], r["unit"]) for r in rows)

    assert norm(_ingredients(linked)) == norm(_ingredients(unlinked)), \
        "cooking once vs three times must need the same ingredients (Σ-yield model)"


# ── builder auto-proposal (§9): Batch households get grouped cooks ──────────

def _auto_build(days, slot):
    resp = requests.post(f"{MEAL_PLANS}/auto-build", json={
        "days": days, "emphasis": "use_up_stock", "slot_names": [slot],
        "repeat_same_day": False, "budget_cap": False,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body.get("entries") or body.get("data", {}).get("entries")


def test__auto_build__batch_household_proposes_grouped_cooks(api):
    from collections import Counter
    today = _household_today()
    slot = next((s for s in _slot_names() if "dinner" in s.lower()), _slot_names()[0])
    days = [(today + timedelta(days=d)).isoformat() for d in range(6)]  # 6 upcoming days

    # Fresh cook-style (seed default): a distinct recipe per day, no groups.
    requests.patch(APP_SETTINGS, json={"batch_features_enabled": False})
    fresh = _auto_build(days, slot)
    assert all(e["cook_key"] is None for e in fresh), "fresh household never groups"

    # Batch cook-style: fewer distinct recipes, each spanning a run of days.
    requests.patch(APP_SETTINGS, json={"batch_features_enabled": True})
    try:
        batch = _auto_build(days, slot)
        keys = [e["cook_key"] for e in batch if e["cook_key"]]
        assert keys, "batch household should propose at least one cook group"
        counts = Counter(keys)
        assert any(v >= 2 for v in counts.values()), "a cook spans several days"
        # every grouped run is a single recipe
        for key, n in counts.items():
            recipes = {e["recipe_id"] for e in batch if e["cook_key"] == key}
            assert len(recipes) == 1
        # fewer distinct recipes than the 6 a fresh build would use
        assert len({e["recipe_id"] for e in batch}) < 6
    finally:
        requests.patch(APP_SETTINGS, json={"batch_features_enabled": False})


# ── coverage verdict across a batch (owner 2026-10-15, the affogato report) ─

def test__batch_with_nothing_cooked__cook_day_needs_cooking_and_leftovers_wait(api):
    """A 2+2 batch with an empty pool: the cook day owes the whole cook, and the
    leftovers day is neither a cook nor sitting on a ready portion."""
    today = _household_today()
    slot = _slot_names()[0]
    recipe = _make_recipe("Affogato")
    requests.patch(APP_SETTINGS, json={"batch_features_enabled": True})
    try:
        resp = _create([
            {"recipe_id": recipe, "scheduled_for": (today + timedelta(days=d)).isoformat(),
             "servings": 2, "slot": slot, "cook_key": "c1"}
            for d in (1, 2)
        ])
        entries = sorted(
            _by_id(resp.json()["meal_plan_id"])["entries"],
            key=lambda e: e["scheduled_for"],
        )
        cook, leftovers = entries
        assert cook["is_cook_day"] and cook["needs_cooking"]
        assert cook["cook_batch_total_servings"] == 4
        assert cook["cook_batch_pending"] is False
        assert not leftovers["is_cook_day"]
        assert leftovers["needs_cooking"] is False
        assert leftovers["cook_batch_pending"] is True
    finally:
        requests.patch(APP_SETTINGS, json={"batch_features_enabled": False})


def test__batch_covered_by_the_pool__leftovers_are_not_waiting(api):
    today = _household_today()
    slot = _slot_names()[0]
    recipe = _make_recipe("Covered batch")
    assert requests.post(f"{RECIPES}/{recipe}/adjust-meals", json={"delta": 4}).status_code == 200
    requests.patch(APP_SETTINGS, json={"batch_features_enabled": True})
    try:
        resp = _create([
            {"recipe_id": recipe, "scheduled_for": (today + timedelta(days=d)).isoformat(),
             "servings": 2, "slot": slot, "cook_key": "c1"}
            for d in (1, 2)
        ])
        for e in _by_id(resp.json()["meal_plan_id"])["entries"]:
            assert e["needs_cooking"] is False
            assert e["cook_batch_pending"] is False
    finally:
        requests.patch(APP_SETTINGS, json={"batch_features_enabled": False})
