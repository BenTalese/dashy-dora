"""FU-519 / PROPOSAL_TEST_SUITE_IMPROVEMENTS §5.D — meal-plan router e2e coverage.

Plan CRUD, entry management (replace / clear semantics), start_date
window filters, and the key 400/404/422 error paths. Complements (does
not duplicate) test_meal_plan_preview.py, test_meal_plan_today.py,
test_meal_plan_template_*.py, test_meal_slot_router.py,
test_swap_suggestions.py and the reconcile suites.

Determinism: every date derives from the single household-today anchor
(GET /api/meal-plans/today) — never a local wall-clock read (2026-07-10
timezone-flake rule). Slot names come from the live /api/meal-slots
vocabulary, not hardcoded labels.
"""
from datetime import date, timedelta
from uuid import uuid4

import pytest
import requests
from sqlalchemy import text

from dora_api.app import app, db
from tests.e2e.dora_api._error_assertions import domain_err, validation_err
from tests.support import (assert_envelope, assert_problem, is_valid_uuid,
                           uuid_bind)

BASE = "http://localhost:5170/api"
MEAL_PLANS = f"{BASE}/meal-plans"
RECIPES = f"{BASE}/recipes"
APP_SETTINGS = f"{BASE}/app-settings"


def _set_auto_drain(value: bool) -> None:
    resp = requests.patch(APP_SETTINGS, json={"auto_drain_past_meals": value})
    assert resp.status_code == 200, resp.text

#region ---------------- setup ----------------


def _household_today() -> date:
    return date.fromisoformat(
        requests.get(f"{MEAL_PLANS}/today").json()["today"]
    )


def _slot_names() -> list[str]:
    return [s["name"] for s in requests.get(f"{BASE}/meal-slots").json()]


def _make_recipe(name_prefix: str = "MealPlan Router Recipe") -> str:
    resp = requests.post(RECIPES, json={"name": f"{name_prefix} {uuid4().hex[:8]}"})
    assert resp.status_code == 201, resp.text
    return resp.json()["recipe_id"]


def _make_plan(**overrides) -> dict:
    """Create a plan (default: named, starting household-today, no
    entries) and return the echoed DTO."""
    body = {
        "name": f"E2E Plan {uuid4().hex[:8]}",
        "start_date": _household_today().isoformat(),
        **overrides,
    }
    resp = requests.post(MEAL_PLANS, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _by_id(meal_plan_id: str) -> dict | None:
    items = assert_envelope(
        requests.get(f"{MEAL_PLANS}?filter=meal_plan_id:eq:{meal_plan_id}")
    )
    return items[0] if items else None

#endregion setup

#region ---------------- create ----------------


def test__create_meal_plan__WithEntries__PlanCreatedAndDtoEchoed(api):
    _Today = _household_today()
    _Slot = _slot_names()[0]
    _RecipeId = _make_recipe()

    _Plan = _make_plan(entries=[
        {
            "recipe_id": _RecipeId,
            "scheduled_for": _Today.isoformat(),
            "servings": 2,
            "slot": _Slot,
        },
        {
            "recipe_id": _RecipeId,
            "scheduled_for": (_Today + timedelta(days=2)).isoformat(),
            "slot": _Slot,
        },
    ])

    assert is_valid_uuid(_Plan["meal_plan_id"])
    assert _Plan["start_date"] == _Today.isoformat()
    assert len(_Plan["entries"]) == 2
    _First = next(e for e in _Plan["entries"] if e["scheduled_for"] == _Today.isoformat())
    assert _First["recipe_id"] == _RecipeId
    assert _First["servings"] == 2
    assert _First["slot"] == _Slot
    assert _First["consumed_at"] is None
    assert is_valid_uuid(_First["meal_plan_entry_id"])
    # Rich-card display fields travel on every entry DTO (§6.5 / Q6).
    assert {"recipe_name", "cook_time_minutes", "category_name", "cuisine_name", "has_image"} <= _First.keys()
    # Omitted servings defaults to 1.
    _Second = next(e for e in _Plan["entries"] if e["scheduled_for"] != _Today.isoformat())
    assert _Second["servings"] == 1


def test__create_meal_plan__NoEntries__EmptyPlanCreated(api):
    _Plan = _make_plan()

    assert _Plan["entries"] == []
    assert _by_id(_Plan["meal_plan_id"]) is not None


def test__create_meal_plan__MissingStartDate__IsRequiredInputsValidationFailure(api):
    _Response = requests.post(MEAL_PLANS, json={})

    assert_problem(_Response, 400, title="Malformed request.")
    assert _Response.json()["errors"] == {
        "start_date": [validation_err("missing", "Field required")],
    }


def test__create_meal_plan__EntryScheduledInThePast__IsBadRequest(api):
    _Today = _household_today()
    _RecipeId = _make_recipe()

    _Response = requests.post(MEAL_PLANS, json={
        "start_date": (_Today - timedelta(days=7)).isoformat(),
        "entries": [{
            "recipe_id": _RecipeId,
            "scheduled_for": (_Today - timedelta(days=1)).isoformat(),
            "slot": _slot_names()[0],
        }],
    })

    _Body = assert_problem(_Response, 400)
    assert _Body["title"] == "Meal plan entries cannot be scheduled in the past."


def test__create_meal_plan__UnknownRecipe__IsEntityExistenceFailure(api):
    _FakeID = uuid4()

    _Response = requests.post(MEAL_PLANS, json={
        "start_date": _household_today().isoformat(),
        "entries": [{
            "recipe_id": str(_FakeID),
            "scheduled_for": _household_today().isoformat(),
            "slot": _slot_names()[0],
        }],
    })

    _Body = assert_problem(_Response, 422, field="entries")
    assert _Body["errors"]["entries"] == [
        domain_err(f"Recipe(s) with the ID(s) '{_FakeID}' were not found."),
    ]


def test__create_meal_plan__OffVocabularySlot__IsBadRequest(api):
    # R-010 — slot labels are validated against the household MealSlot
    # vocabulary on every new write.
    _RecipeId = _make_recipe()

    _Response = requests.post(MEAL_PLANS, json={
        "start_date": _household_today().isoformat(),
        "entries": [{
            "recipe_id": _RecipeId,
            "scheduled_for": _household_today().isoformat(),
            "slot": "second-breakfast",
        }],
    })

    _Body = assert_problem(_Response, 400)
    assert "second-breakfast" in _Body["title"]


def test__create_meal_plan__ZeroServings__IsValidationFailure(api):
    _RecipeId = _make_recipe()

    _Response = requests.post(MEAL_PLANS, json={
        "start_date": _household_today().isoformat(),
        "entries": [{
            "recipe_id": _RecipeId,
            "scheduled_for": _household_today().isoformat(),
            "servings": 0,
            "slot": _slot_names()[0],
        }],
    })

    assert_problem(_Response, 400, title="Malformed request.")

#endregion create

#region ---------------- read ----------------


def test__get_meal_plans__FilterById__ReturnsCreatedPlanWithEntries(api):
    _Today = _household_today()
    _RecipeId = _make_recipe()
    _Plan = _make_plan(entries=[{
        "recipe_id": _RecipeId,
        "scheduled_for": _Today.isoformat(),
        "slot": _slot_names()[0],
    }])

    _Row = _by_id(_Plan["meal_plan_id"])

    assert _Row is not None
    assert _Row["name"] == _Plan["name"]
    assert _Row["start_date"] == _Today.isoformat()
    assert len(_Row["entries"]) == 1
    assert _Row["entries"][0]["recipe_id"] == _RecipeId


def test__get_meal_plans__StartDateWindowFilter__ReturnsOnlyPlansInWindow(api):
    # Date-window query via the standard filter DSL (start_date is a
    # mapped attribute, so ge/le compose into a window). All three plans
    # hang off the same household-today anchor.
    _Today = _household_today()
    _InWindowId = _make_plan(start_date=(_Today + timedelta(days=14)).isoformat())["meal_plan_id"]
    _BeforeId = _make_plan(start_date=(_Today + timedelta(days=1)).isoformat())["meal_plan_id"]
    _AfterId = _make_plan(start_date=(_Today + timedelta(days=28)).isoformat())["meal_plan_id"]

    _Lo = (_Today + timedelta(days=10)).isoformat()
    _Hi = (_Today + timedelta(days=20)).isoformat()
    _Items = assert_envelope(requests.get(
        f"{MEAL_PLANS}?filter=start_date:ge:{_Lo}&filter=start_date:le:{_Hi}&limit=500"
    ))

    _Ids = {p["meal_plan_id"] for p in _Items}
    assert _InWindowId in _Ids
    assert _BeforeId not in _Ids
    assert _AfterId not in _Ids


def test__get_meal_plans__NoSortRequested__NewestWeekFirst(api):
    """Sorted by id alone the 50-row page was an arbitrary slice of the
    household's weeks; the default is now `start_date` descending."""
    _Today = _household_today()
    _make_plan(start_date=(_Today + timedelta(days=400)).isoformat())
    _Newest = _make_plan(start_date=(_Today + timedelta(days=500)).isoformat())

    _Items = assert_envelope(requests.get(f"{MEAL_PLANS}?limit=5"))

    assert _Items[0]["meal_plan_id"] == _Newest["meal_plan_id"]
    _Starts = [p["start_date"] for p in _Items]
    assert _Starts == sorted(_Starts, reverse=True)


def test__get_meal_plans__FilteringOnNonExistentAttribute__IsBadRequest(api):
    _Response = requests.get(f"{MEAL_PLANS}?filter=poopusgoopus:eq:1")

    _Body = assert_problem(_Response, 400)
    assert _Body["title"] == "Field 'poopusgoopus' is not filterable on 'MealPlan'."


@pytest.mark.parametrize(
    "query,invalid_field",
    [
        ("page=true&limit=2", "page"),
        ("page=1&limit=true", "limit"),
    ],
    ids=["page-is-not-integer", "limit-is-not-integer"],
)
def test__get_meal_plans__pagination_value_is_not_integer__IsBadRequest(api, query, invalid_field):
    _Response = requests.get(f"{MEAL_PLANS}?{query}")

    _Body = assert_problem(_Response, 400)
    assert _Body["title"] == f"'{invalid_field}' must be an integer."

#endregion read

#region ---------------- update ----------------


def test__update_meal_plan__RenameAndShiftStartDate__ChangesPersisted(api):
    _Today = _household_today()
    _Plan = _make_plan()
    _NewName = f"E2E Renamed Plan {uuid4().hex[:8]}"
    _NewStart = (_Today + timedelta(days=7)).isoformat()

    _PatchResponse = requests.patch(
        f"{MEAL_PLANS}/{_Plan['meal_plan_id']}",
        json={"name": _NewName, "start_date": _NewStart},
    )
    _After = _by_id(_Plan["meal_plan_id"])

    assert _PatchResponse.status_code == 204
    assert _After["name"] == _NewName
    assert _After["start_date"] == _NewStart


def test__update_meal_plan__ReplacingEntries__FutureEntriesReplaced(api):
    _Today = _household_today()
    _Slot = _slot_names()[0]
    _OriginalRecipeId = _make_recipe("MealPlan Original")
    _ReplacementRecipeId = _make_recipe("MealPlan Replacement")
    _Plan = _make_plan(entries=[{
        "recipe_id": _OriginalRecipeId,
        "scheduled_for": _Today.isoformat(),
        "slot": _Slot,
    }])

    _PatchResponse = requests.patch(
        f"{MEAL_PLANS}/{_Plan['meal_plan_id']}",
        json={"entries": [{
            "recipe_id": _ReplacementRecipeId,
            "scheduled_for": (_Today + timedelta(days=3)).isoformat(),
            "servings": 4,
            "slot": _Slot,
        }]},
    )
    _After = _by_id(_Plan["meal_plan_id"])

    assert _PatchResponse.status_code == 204
    assert len(_After["entries"]) == 1
    assert _After["entries"][0]["recipe_id"] == _ReplacementRecipeId
    assert _After["entries"][0]["servings"] == 4
    assert _After["entries"][0]["scheduled_for"] == (_Today + timedelta(days=3)).isoformat()


def test__update_meal_plan__ResendingEntryIds__KeepsThemAndEditsInPlace(api):
    """FU-878 — a save used to delete and re-insert the forward week, so every
    entry got a new id even when only a different meal changed."""
    _Today = _household_today()
    _Slot = _slot_names()[0]
    _RecipeA = _make_recipe("MealPlan Keep A")
    _RecipeB = _make_recipe("MealPlan Keep B")
    _Plan = _make_plan(entries=[
        {"recipe_id": _RecipeA, "scheduled_for": _Today.isoformat(), "slot": _Slot},
        {"recipe_id": _RecipeB, "scheduled_for": (_Today + timedelta(days=1)).isoformat(), "slot": _Slot},
    ])
    _Before = {e["recipe_id"]: e for e in _by_id(_Plan["meal_plan_id"])["entries"]}
    _NewRecipe = _make_recipe("MealPlan Keep New")

    _PatchResponse = requests.patch(
        f"{MEAL_PLANS}/{_Plan['meal_plan_id']}",
        json={"entries": [
            {
                "meal_plan_entry_id": _Before[_RecipeA]["meal_plan_entry_id"],
                "recipe_id": _RecipeA,
                "scheduled_for": _Today.isoformat(),
                "servings": 3,
                "slot": _Slot,
            },
            {"recipe_id": _NewRecipe, "scheduled_for": (_Today + timedelta(days=2)).isoformat(), "slot": _Slot},
        ]},
    )
    _After = {e["recipe_id"]: e for e in _by_id(_Plan["meal_plan_id"])["entries"]}

    assert _PatchResponse.status_code == 204
    assert set(_After) == {_RecipeA, _NewRecipe}
    assert _After[_RecipeA]["meal_plan_entry_id"] == _Before[_RecipeA]["meal_plan_entry_id"]
    assert _After[_RecipeA]["servings"] == 3
    assert _After[_NewRecipe]["meal_plan_entry_id"] not in {
        e["meal_plan_entry_id"] for e in _Before.values()
    }


def test__update_meal_plan__SameEntryIdTwice__SecondRowIsANewEntry(api):
    _Today = _household_today()
    _Slot = _slot_names()[0]
    _Recipe = _make_recipe("MealPlan Dup")
    _Plan = _make_plan(entries=[
        {"recipe_id": _Recipe, "scheduled_for": _Today.isoformat(), "slot": _Slot},
    ])
    _EntryId = _by_id(_Plan["meal_plan_id"])["entries"][0]["meal_plan_entry_id"]
    _Row = {"meal_plan_entry_id": _EntryId, "recipe_id": _Recipe, "slot": _Slot}

    _PatchResponse = requests.patch(
        f"{MEAL_PLANS}/{_Plan['meal_plan_id']}",
        json={"entries": [
            {**_Row, "scheduled_for": _Today.isoformat()},
            {**_Row, "scheduled_for": (_Today + timedelta(days=1)).isoformat()},
        ]},
    )
    _Ids = [e["meal_plan_entry_id"] for e in _by_id(_Plan["meal_plan_id"])["entries"]]

    assert _PatchResponse.status_code == 204
    assert len(_Ids) == 2
    assert _EntryId in _Ids
    assert len(set(_Ids)) == 2


def test__update_meal_plan__ResendingASinceDeletedSlot__IsAccepted(api):
    # Owner report 2026-09-01: "getting errors 'could not update the plan'
    # after fiddling with the meal slot settings."
    #
    # Deleting a meal slot is deliberately NON-cascading — entries keep their
    # label — but the update endpoint validated the whole payload against the
    # live vocabulary, and the planner resends every forward entry on each
    # edit. So one preserved entry made the entire week unsaveable, and the
    # non-destructive delete was only non-destructive until the next edit.
    _Today = _household_today()
    _RecipeId = _make_recipe("MealPlan Doomed Slot")
    _SlotName = f"Doomed Slot {uuid4().hex[:8]}"
    _Created = requests.post(f"{BASE}/meal-slots", json={"name": _SlotName})
    assert _Created.status_code == 201, _Created.text
    _SlotId = _Created.json()["meal_slot_id"]

    _Plan = _make_plan(entries=[{
        "recipe_id": _RecipeId,
        "scheduled_for": _Today.isoformat(),
        "slot": _SlotName,
    }])

    assert requests.delete(f"{BASE}/meal-slots/{_SlotId}").status_code == 200
    assert _SlotName not in _slot_names()

    # The planner's next edit: resend the existing entry, plus a new one on a
    # slot that IS in the vocabulary.
    _PatchResponse = requests.patch(
        f"{MEAL_PLANS}/{_Plan['meal_plan_id']}",
        json={"entries": [
            {
                "recipe_id": _RecipeId,
                "scheduled_for": _Today.isoformat(),
                "slot": _SlotName,
            },
            {
                "recipe_id": _RecipeId,
                "scheduled_for": (_Today + timedelta(days=1)).isoformat(),
                "slot": _slot_names()[0],
            },
        ]},
    )
    _After = _by_id(_Plan["meal_plan_id"])

    assert _PatchResponse.status_code == 204, _PatchResponse.text
    assert len(_After["entries"]) == 2
    assert _SlotName in {e["slot"] for e in _After["entries"]}


def test__update_meal_plan__NewOffVocabularySlot__IsStillBadRequest(api):
    # The allowance above is scoped to labels the plan ALREADY holds. A slot
    # name nothing on this plan has ever used is still refused, so the
    # vocabulary keeps meaning something.
    _Today = _household_today()
    _RecipeId = _make_recipe()
    _Plan = _make_plan(entries=[{
        "recipe_id": _RecipeId,
        "scheduled_for": _Today.isoformat(),
        "slot": _slot_names()[0],
    }])

    _PatchResponse = requests.patch(
        f"{MEAL_PLANS}/{_Plan['meal_plan_id']}",
        json={"entries": [{
            "recipe_id": _RecipeId,
            "scheduled_for": _Today.isoformat(),
            "slot": "second-breakfast",
        }]},
    )

    _Body = assert_problem(_PatchResponse, 400)
    assert "second-breakfast" in _Body["title"]
    # The refusal names the live vocabulary, never the per-plan allowance —
    # listing a deleted slot as "Allowed" would read as an invitation.
    assert "second-breakfast" not in _Body["title"].split("Allowed:")[1]


def test__update_meal_plan__EmptyEntriesWithoutConfirmFlag__IsBadRequest(api):
    # Destructive-clear guard: `entries: []` alone must not nuke the plan.
    _Today = _household_today()
    _RecipeId = _make_recipe()
    _Plan = _make_plan(entries=[{
        "recipe_id": _RecipeId,
        "scheduled_for": _Today.isoformat(),
        "slot": _slot_names()[0],
    }])

    _PatchResponse = requests.patch(
        f"{MEAL_PLANS}/{_Plan['meal_plan_id']}", json={"entries": []},
    )

    _Body = assert_problem(_PatchResponse, 400)
    assert "confirm_clear_entries" in _Body["title"]
    # The entries survived the refused clear.
    assert len(_by_id(_Plan["meal_plan_id"])["entries"]) == 1


def test__update_meal_plan__EmptyEntriesWithConfirmFlag__FutureEntriesCleared(api):
    _Today = _household_today()
    _RecipeId = _make_recipe()
    _Plan = _make_plan(entries=[{
        "recipe_id": _RecipeId,
        "scheduled_for": _Today.isoformat(),
        "slot": _slot_names()[0],
    }])

    _PatchResponse = requests.patch(
        f"{MEAL_PLANS}/{_Plan['meal_plan_id']}",
        json={"entries": [], "confirm_clear_entries": True},
    )

    assert _PatchResponse.status_code == 204
    assert _by_id(_Plan["meal_plan_id"])["entries"] == []


def test__update_meal_plan__EntryScheduledInThePast__IsBadRequest(api):
    _Today = _household_today()
    _RecipeId = _make_recipe()
    _Plan = _make_plan()

    _PatchResponse = requests.patch(
        f"{MEAL_PLANS}/{_Plan['meal_plan_id']}",
        json={"entries": [{
            "recipe_id": _RecipeId,
            "scheduled_for": (_Today - timedelta(days=1)).isoformat(),
            "slot": _slot_names()[0],
        }]},
    )

    _Body = assert_problem(_PatchResponse, 400)
    assert _Body["title"] == "Meal plan entries cannot be scheduled in the past."


def _backdate_entry(plan_id: str, entry_id: str, to: date) -> None:
    """Move an existing entry (and its plan's start_date) into the past via
    raw SQL. The create/update validators refuse a past `scheduled_for`, so
    this is the only way to seed the past-day state FU-595 concerns. Created
    for today then backdated, and `/today` is never re-hit afterwards, so the
    reconcile sweep never sees it — the entry stays past AND unconsumed
    regardless of the auto-drain setting."""
    with app.app_context(), db.engine.begin() as conn:
        conn.execute(
            text('UPDATE "MealPlanEntry" SET scheduled_for = :d WHERE id = :eid'),
            {"d": to.isoformat(), "eid": uuid_bind(entry_id)},
        )
        conn.execute(
            text('UPDATE "MealPlan" SET start_date = :d WHERE id = :pid'),
            {"d": to.isoformat(), "pid": uuid_bind(plan_id)},
        )


def test__update_meal_plan__PastUnconsumedEntryPresent__PreservedAndAddSucceeds(api):
    """FU-595 regression — a past-dated *unconsumed* entry (auto-drain off, or
    reconciled "didn't cook") must be preserved as history when the forward
    plan is replaced, and must NOT freeze the week. The fixed client resends
    only forward entries; the server preserves the past one on its own, so the
    add succeeds instead of tripping the past-date guard."""
    _Today = _household_today()
    _Slot = _slot_names()[0]
    _PastRecipe = _make_recipe("FU595 Past")
    _NewRecipe = _make_recipe("FU595 New")

    # Auto-drain OFF is the reachable path that leaves a past entry *unconsumed*
    # (the other is reconcile "didn't cook"). With it ON the sweep would stamp
    # consumed_at and we'd only be exercising the old consumed-preservation path.
    _Prev = requests.get(APP_SETTINGS).json()["auto_drain_past_meals"]
    _set_auto_drain(False)
    try:
        # Seed a past-day unconsumed entry: create for today, backdate to yesterday.
        _Plan = _make_plan(entries=[{
            "recipe_id": _PastRecipe,
            "scheduled_for": _Today.isoformat(),
            "slot": _Slot,
        }])
        _PastEntryId = _Plan["entries"][0]["meal_plan_entry_id"]
        _Yesterday = _Today - timedelta(days=1)
        _backdate_entry(_Plan["meal_plan_id"], _PastEntryId, _Yesterday)

        # The fixed client sends only the forward entry — never the past one.
        _Tomorrow = _Today + timedelta(days=1)
        _Patch = requests.patch(
            f"{MEAL_PLANS}/{_Plan['meal_plan_id']}",
            json={"entries": [{
                "recipe_id": _NewRecipe,
                "scheduled_for": _Tomorrow.isoformat(),
                "slot": _Slot,
            }]},
        )
        assert _Patch.status_code == 204, _Patch.text

        _After = _by_id(_Plan["meal_plan_id"])
    finally:
        _set_auto_drain(_Prev)

    _ByDate = {e["scheduled_for"]: e for e in _After["entries"]}
    # Past-unconsumed entry preserved as history; new future entry added.
    assert len(_After["entries"]) == 2
    assert _Tomorrow.isoformat() in _ByDate
    _Past = _ByDate.get(_Yesterday.isoformat())
    assert _Past is not None, "past-unconsumed entry was dropped (FU-595 regression)"
    assert _Past["recipe_id"] == _PastRecipe
    assert _Past["consumed_at"] is None


def test__update_meal_plan__UnknownRecipeInEntries__IsEntityExistenceFailure(api):
    _FakeID = uuid4()
    _Plan = _make_plan()

    _PatchResponse = requests.patch(
        f"{MEAL_PLANS}/{_Plan['meal_plan_id']}",
        json={"entries": [{
            "recipe_id": str(_FakeID),
            "scheduled_for": _household_today().isoformat(),
            "slot": _slot_names()[0],
        }]},
    )

    _Body = assert_problem(_PatchResponse, 422, field="entries")
    assert _Body["errors"]["entries"] == [
        domain_err(f"Recipe(s) with the ID(s) '{_FakeID}' were not found."),
    ]


def test__update_meal_plan__PlanDoesNotExist__MealPlanNotFound(api):
    _FakeID = uuid4()

    _Response = requests.patch(f"{MEAL_PLANS}/{_FakeID}", json={})

    _Body = assert_problem(_Response, 404, title="Entity was not found.")
    assert _Body["detail"] == f"MealPlan with the ID '{_FakeID}' was not found."

#endregion update

#region ---------------- delete ----------------


def test__delete_meal_plan__DeletingPlan__PlanGoneFromList(api):
    _Plan = _make_plan()

    _DeleteResponse = requests.delete(f"{MEAL_PLANS}/{_Plan['meal_plan_id']}")

    assert _DeleteResponse.status_code == 204
    assert _by_id(_Plan["meal_plan_id"]) is None


def test__delete_meal_plan__PlanDoesNotExist__MealPlanNotFound(api):
    _FakeID = uuid4()

    _Response = requests.delete(f"{MEAL_PLANS}/{_FakeID}")

    _Body = assert_problem(_Response, 404, title="Entity was not found.")
    assert _Body["detail"] == f"MealPlan with the ID '{_FakeID}' was not found."

#endregion delete

#region ---------------- rail suggestions ----------------
# BRIEF_MEAL_PLANNER_RAIL_AND_SHELL §4.4. The ranking itself is unit-tested in
# tests/test_build_week.py against fixture candidates; these cover the contract
# the SPA's rail depends on — shape, the week exclusion, the count clamp, and
# the argument validation.


def _suggestions(week_start: date, **params) -> requests.Response:
    query = {"week_start": week_start.isoformat(), **params}
    return requests.get(f"{MEAL_PLANS}/suggestions", params=query)


def test__suggestions__ValidWeek__ReturnsRecipeIdAndFrozenChipToken(api):
    _Monday = _household_today()

    _Response = _suggestions(_Monday)

    assert _Response.status_code == 200, _Response.text
    _Items = _Response.json()["suggestions"]
    assert _Items, "a seeded install should have something to suggest"
    for _Item in _Items:
        assert is_valid_uuid(_Item["recipe_id"])
        # The server ships its own frozen vocabulary, not prose — the client
        # owns the wording (R-003).
        assert _Item["reason_chip"] in {
            "uses_expiring", "cookable_now", "favourite",
            "not_made_recently", "variety", "budget_friendly", "picked",
        }


def test__suggestions__RecipeAlreadyPlannedThatWeek__IsExcluded(api):
    _Monday = _household_today()
    _Slot = _slot_names()[0]

    _Before = {s["recipe_id"] for s in _suggestions(_Monday).json()["suggestions"]}
    assert _Before, "need at least one suggestion to plan away"
    _Planned = next(iter(_Before))

    _make_plan(entries=[{
        "recipe_id": _Planned,
        "scheduled_for": _Monday.isoformat(),
        "servings": 2,
        "slot": _Slot,
    }])

    _After = {s["recipe_id"] for s in _suggestions(_Monday).json()["suggestions"]}
    assert _Planned not in _After


def test__suggestions__SameWeekTwice__IsDeterministic(api):
    # A rail that reshuffled on every render would be unscannable, so the
    # endpoint deliberately passes no rng.
    _Monday = _household_today()

    _First = _suggestions(_Monday).json()["suggestions"]
    _Second = _suggestions(_Monday).json()["suggestions"]

    assert _First == _Second


def test__suggestions__CountAboveMaximum__IsClampedNotRejected(api):
    _Monday = _household_today()

    _Response = _suggestions(_Monday, count=500)

    assert _Response.status_code == 200, _Response.text
    assert len(_Response.json()["suggestions"]) <= 20


def test__suggestions__MissingWeekStart__IsBadRequest(api):
    _Response = requests.get(f"{MEAL_PLANS}/suggestions")

    assert _Response.status_code == 400, _Response.text


def test__suggestions__UnparseableWeekStart__IsBadRequest(api):
    _Response = requests.get(
        f"{MEAL_PLANS}/suggestions", params={"week_start": "next-tuesday"}
    )

    assert _Response.status_code == 400, _Response.text

#endregion rail suggestions
