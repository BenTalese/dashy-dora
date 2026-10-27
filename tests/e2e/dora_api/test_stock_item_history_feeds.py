"""History tab — the Bought + Cooked event feeds on the stock-item detail DTO
(2026-06-30 feedback; verify-campaign Batch 3).

The expiry-event trail (set/pushed/cleared/no-op) and the per-kind cap →
`history_older_count` footer are already pinned in ``test_stock_item_router``.
This file pins the two feeds that had no server tests:

* **purchase_events** — projected from ShoppingListLines that were *ticked* on
  a genuinely *finished* list (`status=done` + `completed_at`); price and store
  are optional chips, an unticked line never surfaces, and a ticked line on an
  in-flight list is mid-shop, not bought.
* **cook_events** — written by ``POST /recipes/<id>/cook`` and surfaced only on
  items the recipe actually references via RecipeIngredient (never a wildcard);
  `meals_cooked` rides along for the "× N meals" badge, and a zero-meal cook
  (the bare `last_made_on` bump) records no event.
"""
import uuid

import requests

BASE = "http://localhost:5170/api"
STOCK_ITEMS = f"{BASE}/stock-items"
SHOPPING_LISTS = f"{BASE}/shopping-lists"
RECIPES = f"{BASE}/recipes"


def _new_stock_item() -> str:
    level = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    resp = requests.post(STOCK_ITEMS, json={
        "name": f"histfeed-{uuid.uuid4().hex[:8]}", "stock_level_id": level,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["stock_item_id"]


def _detail(item_id: str) -> dict:
    return requests.get(f"{STOCK_ITEMS}/{item_id}/detail").json()


def _new_list_with_line(item_id: str) -> tuple[str, str]:
    list_id = requests.post(
        SHOPPING_LISTS, json={"name": f"histfeed-{uuid.uuid4().hex[:8]}"}
    ).json()["shopping_list_id"]
    assert requests.post(
        f"{SHOPPING_LISTS}/{list_id}/lines", json={"stock_item_id": item_id}
    ).status_code in (200, 201)
    line_id = requests.get(f"{SHOPPING_LISTS}/{list_id}").json()["lines"][0]["line_id"]
    return list_id, line_id


def _finish(list_id: str) -> None:
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/finish").status_code == 200


# ── Bought (purchase_events) ─────────────────────────────────────────


def test__purchase_event__ticked_priced_line_surfaces_after_finish(api):
    item = _new_stock_item()
    assert _detail(item)["purchase_events"] == []
    list_id, line_id = _new_list_with_line(item)
    assert requests.patch(
        f"{SHOPPING_LISTS}/{list_id}/lines/{line_id}",
        json={"actual_unit_price": 2.10, "is_ticked": True},
    ).status_code == 204

    _finish(list_id)

    events = _detail(item)["purchase_events"]
    assert len(events) == 1
    e = events[0]
    assert e["actual_unit_price"] == 2.10
    assert e["quantity"] == 1
    assert e["shopping_list_id"] == list_id
    assert e["shopping_list_name"]
    assert e["occurred_at"]            # the parent list's completed_at stamp
    assert e["store_name"] is None     # no store captured on this line


def test__purchase_event__unpriced_no_store_line_still_surfaces(api):
    # The Finish flow leaving price/store blank still emits a Bought entry —
    # the SPA just renders fewer body chips (title always renders).
    item = _new_stock_item()
    list_id, line_id = _new_list_with_line(item)
    assert requests.patch(
        f"{SHOPPING_LISTS}/{list_id}/lines/{line_id}", json={"is_ticked": True},
    ).status_code == 204

    _finish(list_id)

    events = _detail(item)["purchase_events"]
    assert len(events) == 1
    assert events[0]["actual_unit_price"] is None
    assert events[0]["store_name"] is None


def test__purchase_event__store_resolved_to_name(api):
    item = _new_stock_item()
    list_id, line_id = _new_list_with_line(item)
    store = requests.get(f"{BASE}/stores").json()["items"][0]
    assert requests.patch(
        f"{SHOPPING_LISTS}/{list_id}/lines/{line_id}",
        json={"is_ticked": True, "purchased_store_id": store["store_id"]},
    ).status_code == 204

    _finish(list_id)

    events = _detail(item)["purchase_events"]
    assert len(events) == 1
    assert events[0]["store_name"] == store["name"]


def test__purchase_event__unticked_line_never_surfaces(api):
    # Finishing restocks only what you bought; an unticked line was never
    # purchased and must not fabricate a Bought entry.
    item = _new_stock_item()
    list_id, _ = _new_list_with_line(item)

    _finish(list_id)

    assert _detail(item)["purchase_events"] == []


def test__purchase_event__ticked_line_on_inflight_list_is_not_bought_yet(api):
    # A tick during an active shop is mid-shop state, not a purchase — only a
    # genuinely finished (`done` + completed_at) parent list surfaces it.
    item = _new_stock_item()
    list_id, line_id = _new_list_with_line(item)
    assert requests.patch(
        f"{SHOPPING_LISTS}/{list_id}", json={"status": "shopping"},
    ).status_code == 204
    assert requests.patch(
        f"{SHOPPING_LISTS}/{list_id}/lines/{line_id}", json={"is_ticked": True},
    ).status_code == 204

    assert _detail(item)["purchase_events"] == []


# ── Cooked (cook_events) ─────────────────────────────────────────────


def _new_recipe_with_ingredient(item_id: str) -> str:
    resp = requests.post(RECIPES, json={
        "name": f"histfeed recipe {uuid.uuid4().hex[:8]}",
        "servings": 2,
        "ingredients": [{"stock_item_id": item_id, "quantity": 1, "unit": "ea"}],
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["recipe_id"]


def test__cook_event__surfaces_on_ingredient_items_only(api):
    ingredient = _new_stock_item()
    bystander = _new_stock_item()
    recipe_id = _new_recipe_with_ingredient(ingredient)

    resp = requests.post(f"{RECIPES}/{recipe_id}/cook", json={"meals_cooked": 2})
    assert resp.status_code == 200, resp.text

    events = _detail(ingredient)["cook_events"]
    assert len(events) == 1
    assert events[0]["recipe_id"] == recipe_id
    assert events[0]["recipe_name"]
    assert events[0]["meals_cooked"] == 2   # drives the "× N meals" badge
    assert events[0]["occurred_at"]

    # The join is via RecipeIngredient.stock_item_id, not a wildcard — an
    # unrelated item's timeline stays untouched.
    assert _detail(bystander)["cook_events"] == []


def test__cook_event__zero_meal_cook_records_nothing(api):
    # meals_cooked=0 exists purely to bump `last_made_on`; it must not
    # fabricate a "Used in <recipe>" timeline entry.
    item = _new_stock_item()
    recipe_id = _new_recipe_with_ingredient(item)

    resp = requests.post(f"{RECIPES}/{recipe_id}/cook", json={"meals_cooked": 0})
    assert resp.status_code == 200, resp.text

    assert _detail(item)["cook_events"] == []


# ── Level history (finalisation 06-R3) ───────────────────────────────

def test__level_history__carries_the_level_sequence_not_just_its_name(api):
    """The timeline reads "restocked" / "dropped" off the sequence; it used to
    regex the level's name, which a household can rename."""
    levels = sorted(requests.get(f"{BASE}/stock-levels").json()["items"], key=lambda l: l["sequence"])
    created = requests.post(STOCK_ITEMS, json={
        "name": f"histfeed-{uuid.uuid4().hex[:8]}", "stock_level_id": levels[0]["stock_level_id"],
    })
    assert created.status_code == 201, created.text
    item_id = created.json()["stock_item_id"]
    assert requests.patch(
        f"{STOCK_ITEMS}/{item_id}", json={"stock_level_id": levels[-1]["stock_level_id"]},
    ).status_code in (200, 204)

    history = _detail(item_id)["level_history"]
    sequence_by_name = {l["name"]: l["sequence"] for l in levels}
    assert history
    for change in history:
        assert "stock_level_id" not in change
        assert change["stock_level_sequence"] == sequence_by_name[change["stock_level_name"]]
    assert levels[-1]["sequence"] in {c["stock_level_sequence"] for c in history}
