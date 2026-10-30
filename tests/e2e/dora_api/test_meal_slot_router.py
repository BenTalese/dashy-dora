"""C-2.A — household-wide meal-slot vocabulary.

Covers:
  * CRUD round-trip (list seeded defaults, create, rename, reorder, delete).
  * Write-time name validation: an off-vocab slot on a recipe or meal-plan
    write is rejected with a 400.
  * Delete-preserves-label: deleting a slot leaves a meal-plan entry that used
    it with its slot label intact (no FK, no cascade).
"""
from datetime import date, timedelta

import requests

MEAL_SLOTS = "http://localhost:5170/api/meal-slots"
MEAL_PLANS = "http://localhost:5170/api/meal-plans"
RECIPES = "http://localhost:5170/api/recipes"

_DEFAULT_SLOTS = {"Breakfast", "Lunch", "Dinner", "Snack", "Dessert"}


def _list() -> list[dict]:
    resp = requests.get(MEAL_SLOTS)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _create(name: str) -> str:
    resp = requests.post(MEAL_SLOTS, json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["meal_slot_id"]


def _delete(slot_id: str) -> dict:
    resp = requests.delete(f"{MEAL_SLOTS}/{slot_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _a_recipe_id() -> str:
    resp = requests.get(f"{RECIPES}?limit=1")
    assert resp.status_code == 200, resp.text
    return resp.json()["items"][0]["recipe_id"]


def _future_iso(days: int = 7) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _plan_from_list(plan_id: str) -> dict:
    # There is no GET-by-id meal-plan route; read it back off the list.
    resp = requests.get(MEAL_PLANS)
    assert resp.status_code == 200, resp.text
    return next(p for p in resp.json()["items"] if p["meal_plan_id"] == plan_id)


# ───── CRUD round-trip ─────────────────────────────────────────────────────

def test_list_is_seeded_with_the_five_defaults():
    names = {s["name"] for s in _list()}
    assert _DEFAULT_SLOTS.issubset(names), names
    # Dessert in particular (the gap C-2.A closes) is present.
    assert "Dessert" in names


def test_list_is_ordered_by_sequence_and_carries_usage_count():
    slots = _list()
    sequences = [s["sequence"] for s in slots]
    assert sequences == sorted(sequences)
    for s in slots:
        assert "usage_count" in s
        assert isinstance(s["usage_count"], int)


def test_usage_count_tallies_plan_entries_by_label():
    slot_id = _create("Second breakfast")
    recipe_id = _a_recipe_id()
    resp = requests.post(MEAL_PLANS, json={
        "name": "Usage-count plan",
        "start_date": _future_iso(),
        "entries": [
            {"recipe_id": recipe_id, "scheduled_for": _future_iso(), "servings": 1, "slot": "Second breakfast"},
            {"recipe_id": recipe_id, "scheduled_for": _future_iso(8), "servings": 1, "slot": "Second breakfast"},
        ],
    })
    assert resp.status_code == 201, resp.text
    try:
        counts = {s["name"]: s["usage_count"] for s in _list()}
        assert counts["Second breakfast"] == 2
    finally:
        requests.delete(f"{MEAL_PLANS}/{resp.json()['meal_plan_id']}")
        _delete(slot_id)


def test_create_rename_reorder_delete_roundtrip():
    slot_id = _create("Brunch")
    try:
        assert "Brunch" in {s["name"] for s in _list()}

        # Rename.
        rename = requests.patch(f"{MEAL_SLOTS}/{slot_id}", json={"name": "Late Brunch"})
        assert rename.status_code == 200, rename.text
        assert "Late Brunch" in {s["name"] for s in _list()}
        assert "Brunch" not in {s["name"] for s in _list()}

        # Reorder: send the full current ordering, moving the new slot to 0.
        current = _list()
        others = [s for s in current if s["meal_slot_id"] != slot_id]
        ordering = [{"meal_slot_id": slot_id, "sequence": 0}] + [
            {"meal_slot_id": s["meal_slot_id"], "sequence": i + 1}
            for i, s in enumerate(others)
        ]
        reorder = requests.patch(f"{MEAL_SLOTS}/reorder", json={"slots": ordering})
        assert reorder.status_code == 200, reorder.text
        assert _list()[0]["meal_slot_id"] == slot_id
    finally:
        _delete(slot_id)
    assert "Late Brunch" not in {s["name"] for s in _list()}


def test_rename_carries_planned_meals_with_it():
    """FU-957 (owner, 2026-10-30) — renaming "Elevenses" to "Morning tea"
    moves the meals planned under it, rather than stranding them on a label
    the planner no longer has a row for."""
    slot_id = _create("Elevenses")
    recipe_id = _a_recipe_id()
    resp = requests.post(MEAL_PLANS, json={
        "name": "Rename-cascade plan",
        "start_date": _future_iso(),
        "entries": [
            {"recipe_id": recipe_id, "scheduled_for": _future_iso(), "servings": 1, "slot": "Elevenses"},
        ],
    })
    assert resp.status_code == 201, resp.text
    plan_id = resp.json()["meal_plan_id"]
    try:
        rename = requests.patch(f"{MEAL_SLOTS}/{slot_id}", json={"name": "Morning tea"})
        assert rename.status_code == 200, rename.text
        assert [e["slot"] for e in _plan_from_list(plan_id)["entries"]] == ["Morning tea"]
        counts = {s["name"]: s["usage_count"] for s in _list()}
        assert counts["Morning tea"] == 1
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")
        _delete(slot_id)


def test_create_rejects_case_insensitive_duplicate():
    resp = requests.post(MEAL_SLOTS, json={"name": "dinner"})
    assert resp.status_code == 422, resp.text


def test_delete_unknown_slot_is_404():
    resp = requests.delete(f"{MEAL_SLOTS}/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404, resp.text


def test_reorder_unknown_id_is_rejected():
    resp = requests.patch(
        f"{MEAL_SLOTS}/reorder",
        json={"slots": [{"meal_slot_id": "00000000-0000-0000-0000-000000000000", "sequence": 0}]},
    )
    assert resp.status_code == 422, resp.text


# ───── Write-time name validation ──────────────────────────────────────────

def test_meal_plan_write_rejects_off_vocab_slot():
    recipe_id = _a_recipe_id()
    resp = requests.post(MEAL_PLANS, json={
        "name": "Off-vocab plan",
        "start_date": _future_iso(),
        "entries": [{
            "recipe_id": recipe_id,
            "scheduled_for": _future_iso(),
            "servings": 1,
            "slot": "Elevenses",  # not in the vocabulary
        }],
    })
    assert resp.status_code == 400, resp.text
    assert "Elevenses" in resp.text


def test_meal_plan_write_accepts_a_vocab_slot():
    recipe_id = _a_recipe_id()
    resp = requests.post(MEAL_PLANS, json={
        "name": "In-vocab plan",
        "start_date": _future_iso(),
        "entries": [{
            "recipe_id": recipe_id,
            "scheduled_for": _future_iso(),
            "servings": 1,
            "slot": "Dinner",
        }],
    })
    assert resp.status_code == 201, resp.text
    requests.delete(f"{MEAL_PLANS}/{resp.json()['meal_plan_id']}")


def test_recipe_time_of_day_write_rejects_off_vocab_slot():
    recipe_id = _a_recipe_id()
    resp = requests.patch(f"{RECIPES}/{recipe_id}", json={"time_of_day": "Elevenses"})
    assert resp.status_code == 400, resp.text
    assert "Elevenses" in resp.text


def test_recipe_time_of_day_write_accepts_a_vocab_slot():
    recipe_id = _a_recipe_id()
    resp = requests.patch(f"{RECIPES}/{recipe_id}", json={"time_of_day": "Lunch"})
    assert resp.status_code == 204, resp.text


def test_recipe_keeps_editable_after_its_slot_is_deleted():
    # The other half of "deleting a slot preserves the label" (2026-09-01):
    # preservation is worthless if the record can no longer be SAVED. The
    # recipe editor resends `time_of_day` on every save, so validating it
    # against the live vocabulary alone made a recipe tagged with a
    # since-deleted slot permanently unsaveable — you could not even fix the
    # slot without the request being refused for carrying it.
    recipe_id = _a_recipe_id()
    slot_id = _create("Elevenses Proper")
    assert requests.patch(
        f"{RECIPES}/{recipe_id}", json={"time_of_day": "Elevenses Proper"},
    ).status_code == 204
    _delete(slot_id)

    # An unrelated edit that resends the now-off-vocab label.
    resp = requests.patch(
        f"{RECIPES}/{recipe_id}",
        json={"time_of_day": "Elevenses Proper", "servings": 3},
    )
    assert resp.status_code == 204, resp.text

    # …but a slot this recipe has never held is still refused.
    assert requests.patch(
        f"{RECIPES}/{recipe_id}", json={"time_of_day": "Brunchtime"},
    ).status_code == 400


# ───── Delete preserves the label (no FK, no cascade) ──────────────────────

def test_deleting_a_slot_leaves_an_entry_label_intact():
    recipe_id = _a_recipe_id()
    slot_id = _create("CampfireDinner")

    # An entry written while the slot is in-vocab.
    plan_resp = requests.post(MEAL_PLANS, json={
        "name": "Label-preservation plan",
        "start_date": _future_iso(),
        "entries": [{
            "recipe_id": recipe_id,
            "scheduled_for": _future_iso(),
            "servings": 1,
            "slot": "CampfireDinner",
        }],
    })
    assert plan_resp.status_code == 201, plan_resp.text
    plan_id = plan_resp.json()["meal_plan_id"]

    try:
        # Deleting the vocab row reports the affected entry but does NOT
        # cascade — the entry keeps its label string.
        deleted = _delete(slot_id)
        assert deleted["entries_affected"] >= 1

        plan = _plan_from_list(plan_id)
        slots = [e["slot"] for e in plan["entries"]]
        assert "CampfireDinner" in slots
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")
