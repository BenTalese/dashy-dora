"""FU-390 — AI-path assistant reliability.

The Dora AI path (SLM tool-calling in ``ask_assistant.py``) has a few
guarantees that must hold regardless of which model is wired up, and that a
model can't be trusted to enforce. We pin the *deterministic* ones here — no
live model, no network:

1. **Registry integrity.** Every tool the model is offered (``TOOL_SCHEMAS``)
   is actually dispatchable, data and action tools are disjoint, and every
   action tool has a schema. A drift here means the model calls a tool that
   either 500s or silently no-ops.
2. **The mutation gate.** Every action (mutating) tool is classified as an
   action — never a data tool — so ``ask_assistant`` short-circuits it into a
   *proposal* the user must confirm, and it can never be executed via
   ``run_tool``. This is the single most important safety property of an
   action-taking assistant (proposal §B.0); a regression that mislabels an
   action tool as data would let the model mutate the DB unprompted.
3. **Every action tool has a proposer.** The ``_propose_action`` dispatch
   covers every action tool (the bespoke add-to-list flow or a confirm card).
4. **Graceful degradation.** With no model configured, ``/assistant/ask``
   returns ``available=false`` (so the SPA falls back to Basic mode) rather
   than erroring.
"""
import re
from pathlib import Path

import pytest
import requests

from dora_api.app import app
from dora_api.features.assistant import confirm_actions, tools

BASE = "http://localhost:5170/api"


def _schema_names() -> list[str]:
    return [s["function"]["name"] for s in tools.TOOL_SCHEMAS]


def test__tool_registry__every_schema_is_dispatchable():
    """Each tool offered to the model resolves to exactly one executor path."""
    for name in _schema_names():
        is_data = tools.is_data_tool(name)
        is_action = tools.is_action_tool(name)
        assert is_data ^ is_action, (
            f"tool '{name}' must be exactly one of data/action "
            f"(data={is_data}, action={is_action})"
        )


def test__tool_registry__schema_names_are_unique():
    names = _schema_names()
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"duplicate tool schema names: {sorted(dupes)}"


def test__tool_registry__data_and_action_sets_are_disjoint():
    overlap = set(tools._TOOLS) & set(tools._ACTION_TOOLS)
    assert not overlap, f"tools classified as both data and action: {sorted(overlap)}"


def test__tool_registry__every_dispatch_target_has_a_schema():
    """No orphan executors — the model can only call what it's shown, so a
    dispatch entry with no schema is dead weight (and a sign of drift)."""
    schema_names = set(_schema_names())
    for name in set(tools._TOOLS) | set(tools._ACTION_TOOLS):
        assert name in schema_names, f"dispatchable tool '{name}' has no TOOL_SCHEMA"


def test__mutation_gate__action_tools_are_never_data_tools():
    """The gate that keeps the LLM from mutating data on its own."""
    for name in tools._ACTION_TOOLS:
        assert tools.is_action_tool(name) is True
        assert tools.is_data_tool(name) is False, (
            f"action tool '{name}' is mislabelled as a data tool — it could be "
            f"executed without user confirmation"
        )


def test__mutation_gate__run_tool_refuses_action_tools():
    """``run_tool`` is the read-only executor. Handing it an action tool must
    raise (KeyError) rather than mutate — actions only ever flow through the
    propose→confirm path."""
    for name in tools._ACTION_TOOLS:
        with pytest.raises(KeyError):
            tools.run_tool(name, {})


def test__mutation_gate__every_action_tool_has_a_proposer():
    """``_propose_action`` routes add-to-shopping-list to its bespoke flow and
    everything else through a confirm card. An action tool that matches
    neither would fall through to the fail-soft branch and silently do
    nothing — assert full coverage."""
    for name in tools._ACTION_TOOLS:
        covered = (name == tools.ADD_TO_SHOPPING_LIST) or confirm_actions.is_confirm_action(name)
        assert covered, f"action tool '{name}' has no proposer (add-flow or confirm card)"


def test__nav_for__never_offers_navigation_for_an_action_tool():
    """Post-answer navigation is a data-tool affordance; actions resolve via a
    confirm card, not a nav button."""
    for name in tools._ACTION_TOOLS:
        assert tools.nav_for(name) is None, f"action tool '{name}' should not carry a nav hint"


def test__assistant_ask__no_model_configured__degrades_to_unavailable(api):
    """The seed user has no LLM configured (llm_enabled defaults False), so the
    AI path must report unavailable + defer to local Basic mode — never 500."""
    resp = requests.post(f"{BASE}/assistant/ask", json={
        "message": "what's expiring soon?",
        "current_path": "/",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["available"] is False, body
    assert body["defer_to_local"] is True, body


# Finalisation 11-R1 — three proposers queried the dropped `is_primary`
# column and raised AttributeError on propose, which `/ask` turned into a 500.
# The registry tests above only checked that a proposer *exists*. Each proposer
# gets arguments that reach past its "which item?" early-return so the body
# actually runs against the seeded data; the outcome shape, not the outcome,
# is what's pinned.
_PROPOSER_SMOKE_ARGS = {
    "update_stock_level": {"item_name": "zz-no-such-item", "level": "low"},
    "mark_opened": {"item_name": "zz-no-such-item"},
    "push_expiry": {"item_name": "zz-no-such-item", "days": 3},
    "tick_shopping_line": {"item_name": "zz-no-such-item"},
    "move_item": {"item_name": "zz-no-such-item", "destination": "Pantry"},
    "plan_meal_for_date": {"meal_name": "zz-no-such-recipe", "date": "2030-01-01"},
    "add_recipe_to_list": {"recipe_name": "zz-no-such-recipe"},
    "cook_recipe": {"recipe_name": "zz-no-such-recipe"},
    "adjust_recipe_meals": {"recipe_name": "zz-no-such-recipe", "delta": 1},
    "trim_list_to_budget": {},
}


def test__proposers__smoke_args_cover_every_proposer():
    assert set(_PROPOSER_SMOKE_ARGS) == set(confirm_actions.PROPOSERS)


@pytest.mark.parametrize("name", sorted(confirm_actions.PROPOSERS))
def test__proposers__every_proposer_runs_without_raising(api, name):
    with app.test_request_context():
        result = confirm_actions.PROPOSERS[name](_PROPOSER_SMOKE_ARGS[name])
    assert isinstance(result, dict)
    assert result.get("type") == name
    assert "status" in result


def test__trim_to_budget__propose_and_commit_reach_the_handler(api):
    """The smoke test above returns before the handler (no signed-in user),
    which is how a signature change to `TrimToBudgetHandler.handle` went
    unnoticed. Signed in, with a draft list, both halves call it."""
    from flask import session
    from dora_api.domain.entities.user import User
    from dora_api.infrastructure.session_user import SESSION_USER_ID_KEY
    from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

    list_id = requests.post(f"{BASE}/shopping-lists", json={"name": "Trim smoke"}).json()["shopping_list_id"]
    try:
        with app.test_request_context():
            session[SESSION_USER_ID_KEY] = str(SqlAlchemyRepository().get(User).all()[0].id)
            proposed = confirm_actions.PROPOSERS["trim_list_to_budget"]({})
            committed = confirm_actions.commit_trim_list_to_budget(
                {"shopping_list_id": list_id, "list_name": "Trim smoke"},
            )
        assert proposed["type"] == "trim_list_to_budget"
        assert committed["ok"] is False
    finally:
        requests.delete(f"{BASE}/shopping-lists/{list_id}")


def test__add_to_list_plan__resolves_without_raising(api):
    """The add-to-list flow has its own resolver beside PROPOSERS; its stock
    match used `EntityField` without importing it, so every LLM-mode "add X to
    my list" raised a NameError."""
    from dora_api.features.assistant import shopping_actions

    with app.test_request_context():
        plan = shopping_actions.resolve_add_plan([{"name": "milk", "quantity": 1}])
    assert plan["type"] == "add_to_shopping_list"
    assert plan["items"][0]["status"] in {"ready", "not_found", "ambiguous", "too_many"}


# Finalisation 11-R3 — 11 of 24 nav hints pointed at retired routes
# (`/recipes`, `/product-search`, `/settings/preferences`), so the "See it"
# button under an answer landed on the 404 page. Pin every hint against the
# SPA's route table: each path segment must be declared somewhere in
# `routes.ts`. (Segment-level, because the file nests children — strong
# enough to catch a retired top-level route, which is the failure seen.)
_ROUTES_TS = Path(__file__).resolve().parents[3] / "web_app" / "src" / "router" / "routes.ts"


def _declared_route_segments() -> set[str]:
    source = _ROUTES_TS.read_text(encoding="utf-8")
    segments: set[str] = set()
    for raw in re.findall(r"path:\s*'([^']*)'", source):
        for seg in raw.strip("/").split("/"):
            if seg and not seg.startswith(":"):
                segments.add(seg)
    return segments


def test__tool_nav__every_hint_targets_a_declared_spa_route():
    declared = _declared_route_segments()
    assert declared, f"could not read route segments from {_ROUTES_TS}"
    for name, hint in tools._TOOL_NAV.items():
        path = hint["path"].split("?", 1)[0]
        assert path.startswith("/"), f"{name}: nav path must be absolute, got {path!r}"
        for seg in path.strip("/").split("/"):
            assert seg in declared, (
                f"nav hint for '{name}' points at {path!r}; segment {seg!r} is "
                f"not declared in routes.ts"
            )


# Finalisation 11-R2 — `waste_insights` referenced `timezone` without a
# module-level import and raised NameError the first time a model called it.
# The data tools are plain functions over the seeded dataset; run each with
# empty arguments and require a list back. Tools whose only early-return is
# "argument required" still exercise their import paths.
@pytest.mark.parametrize("name", sorted(tools._TOOLS))
def test__data_tools__every_tool_runs_with_empty_args(api, name):
    with app.test_request_context():
        result = tools.run_tool(name, {})
    assert isinstance(result, list), f"{name} returned {type(result).__name__}"


# Finalisation 11-R8 (R-057) — the SPA's `ConfirmActionType` union must name
# every proposer; three were missing and the chat only worked because the
# value arrives from JSON.
_ASSISTANT_SERVICE_TS = (
    Path(__file__).resolve().parents[3] / "web_app" / "src" / "services" / "api" / "assistantApiService.ts"
)


def test__confirm_action_type_union__mirrors_proposers():
    source = _ASSISTANT_SERVICE_TS.read_text(encoding="utf-8")
    start = source.index("export type ConfirmActionType =")
    end = source.index(";", start)
    members = set(re.findall(r"'([a-z_]+)'", source[start:end]))
    assert members == set(confirm_actions.PROPOSERS), (
        f"ConfirmActionType {sorted(members)} != PROPOSERS {sorted(confirm_actions.PROPOSERS)}"
    )


def test__recipes_using_item__finds_the_recipe_from_its_ingredient(api):
    """11-R41 — the lookup starts from the ingredient side now."""
    level = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    item = requests.post(f"{BASE}/stock-items", json={"name": "Zz ladder saffron", "stock_level_id": level}).json()["stock_item_id"]
    recipe = requests.post(f"{BASE}/recipes", json={
        "name": "Zz saffron rice",
        "ingredients": [{"stock_item_id": item, "quantity": 1, "unit": "g"}],
    }).json()["recipe_id"]
    try:
        with app.test_request_context():
            rows = tools._TOOLS["recipes_using_item"]({"item_name": "Zz ladder saffron"})
        assert [r["name"] for r in rows] == ["Zz saffron rice"]
    finally:
        requests.delete(f"{BASE}/recipes/{recipe}")
        requests.delete(f"{BASE}/stock-items/{item}")


def test__commit_plan_meal_for_date__PlanWithPastDayAndBatch__AddsKeepingIdsAndBatch(api):
    """The commit used to resend every unconsumed entry — a past one tripped
    "Can't plan a meal in the past" — and dropped ids and cook keys, so every
    forward entry was re-created and its batch lost."""
    from datetime import date, timedelta
    from uuid import uuid4

    from sqlalchemy import text

    from dora_api.app import db
    from tests.support import uuid_bind

    meal_plans = f"{BASE}/meal-plans"
    today = date.fromisoformat(requests.get(f"{meal_plans}/today").json()["today"])
    slot = requests.get(f"{BASE}/meal-slots").json()[0]["name"]
    recipe_id = requests.post(f"{BASE}/recipes", json={"name": f"Assistant plan {uuid4().hex[:8]}"}).json()["recipe_id"]
    previous = requests.get(f"{BASE}/app-settings").json()["auto_drain_past_meals"]
    requests.patch(f"{BASE}/app-settings", json={"auto_drain_past_meals": False})
    try:
        plan = requests.post(meal_plans, json={"start_date": today.isoformat(), "entries": [
            {"recipe_id": recipe_id, "scheduled_for": today.isoformat(), "slot": slot},
            {"recipe_id": recipe_id, "scheduled_for": (today + timedelta(days=1)).isoformat(),
             "slot": slot, "cook_key": "b"},
            {"recipe_id": recipe_id, "scheduled_for": (today + timedelta(days=2)).isoformat(),
             "slot": slot, "cook_key": "b"},
        ]}).json()
        past_entry = next(e for e in plan["entries"] if e["cook_batch_id"] is None)
        with app.app_context(), db.engine.begin() as conn:
            conn.execute(
                text('UPDATE "MealPlanEntry" SET scheduled_for = :d WHERE id = :eid'),
                {"d": (today - timedelta(days=1)).isoformat(), "eid": uuid_bind(past_entry["meal_plan_entry_id"])},
            )
        forward_before = {
            e["meal_plan_entry_id"]: e["cook_batch_id"]
            for e in plan["entries"] if e["cook_batch_id"] is not None
        }

        with app.test_request_context():
            result = confirm_actions.commit_plan_meal_for_date({
                "meal_plan_id": plan["meal_plan_id"], "recipe_id": recipe_id,
                "meal_name": "x", "scheduled_for": (today + timedelta(days=3)).isoformat(),
                "slot": slot, "servings": 1,
            })
    finally:
        requests.patch(f"{BASE}/app-settings", json={"auto_drain_past_meals": previous})

    assert result["ok"] is True, result
    after = requests.get(f"{meal_plans}?filter=meal_plan_id:eq:{plan['meal_plan_id']}").json()["items"][0]
    by_id = {e["meal_plan_entry_id"]: e for e in after["entries"]}
    assert len(after["entries"]) == 4
    assert past_entry["meal_plan_entry_id"] in by_id
    assert set(forward_before) <= set(by_id)
    assert len({by_id[i]["cook_batch_id"] for i in forward_before}) == 1
    assert by_id[next(iter(forward_before))]["cook_batch_id"] is not None
