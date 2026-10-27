"""FU-351 — the "Draft my shop" server contract on `POST /shopping-lists/auto-generate`
(verify-campaign Batch: Dashboard).

The dashboard card leans on two create-new-path behaviours the unit-of-work
test doesn't cover:

* **Zero candidates defers list creation.** A call whose sources yield nothing
  answers `nothing_to_add: true` with a null `shopping_list_id` and leaves NO
  phantom list behind — the card renders an honest "Nothing to draft yet."
  toast instead of stranding a "Weekly shop · <date>" shell in the sidebar.
* **The explicit `name` is honoured** on the created list (the card sends
  "Weekly shop · <weekday> <day> <month>" instead of the generic "Auto N ·
  <date>" default).
"""
from uuid import uuid4

import requests

BASE = "http://localhost:5170/api"
LISTS = f"{BASE}/shopping-lists"
AUTO = f"{LISTS}/auto-generate"


def _list_ids() -> set[str]:
    resp = requests.get(LISTS)
    assert resp.status_code == 200, resp.text
    return {l["shopping_list_id"] for l in resp.json()}


def test__auto_generate__zero_candidates_on_create_new__no_phantom_list(api):
    before = _list_ids()

    # A meal-plan week far in the future has no entries, and every other
    # source is off → zero candidates.
    resp = requests.post(AUTO, json={
        "name": f"FU-351 phantom {uuid4().hex[:8]}",
        "sources": {"meal_plan_week": "2030-01-01"},
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["nothing_to_add"] is True
    assert body["shopping_list_id"] is None
    assert body["added_count"] == 0

    # The list collection is untouched — creation was deferred, not rolled back.
    assert _list_ids() == before


def test__auto_generate__create_new_honours_the_explicit_name(api):
    stock_level_id = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    item_resp = requests.post(f"{BASE}/stock-items", json={
        "name": f"FU-351 named {uuid4().hex[:8]}",
        "stock_level_id": stock_level_id,
        "is_essential": True,
    })
    assert item_resp.status_code == 201, item_resp.text
    stock_item_id = item_resp.json()["stock_item_id"]

    list_name = f"Weekly shop · test {uuid4().hex[:8]}"
    generated_list_id = None
    try:
        resp = requests.post(AUTO, json={
            "name": list_name,
            "sources": {"essentials": True},
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert not body["nothing_to_add"], body
        generated_list_id = body["shopping_list_id"]

        detail = requests.get(f"{LISTS}/{generated_list_id}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["display_name"] == list_name
    finally:
        if generated_list_id:
            requests.delete(f"{LISTS}/{generated_list_id}")
        requests.patch(f"{BASE}/stock-items/{stock_item_id}", json={"is_essential": False})
        requests.delete(f"{BASE}/stock-items/{stock_item_id}")


def test__auto_generate__recipe_source__lists_unstocked_and_reports_unlinked(api):
    """03-R12 — the recipe source loads every recipe at once: an unstocked
    ingredient becomes a line, a stocked one doesn't, an unlinked one is
    reported for manual adding."""
    levels = {l["sequence"]: l["stock_level_id"] for l in requests.get(f"{BASE}/stock-levels").json()["items"]}
    suffix = uuid4().hex[:8]
    out_id = requests.post(f"{BASE}/stock-items", json={
        "name": f"03-R12 out {suffix}", "stock_level_id": levels[max(levels)],
    }).json()["stock_item_id"]
    stocked_id = requests.post(f"{BASE}/stock-items", json={
        "name": f"03-R12 stocked {suffix}", "stock_level_id": levels[min(levels)],
    }).json()["stock_item_id"]
    recipe = requests.post(f"{BASE}/recipes", json={
        "name": f"03-R12 soup {suffix}",
        "ingredients": [
            {"stock_item_id": out_id, "quantity": 1, "unit": "g"},
            {"stock_item_id": stocked_id, "quantity": 1, "unit": "g"},
            {"raw_text": "a pinch of something"},
        ],
    })
    assert recipe.status_code == 201, recipe.text
    recipe_id = recipe.json()["recipe_id"]
    list_id = None
    try:
        resp = requests.post(AUTO, json={"sources": {"recipes": [recipe_id]}})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        list_id = body["shopping_list_id"]
        line_items = {l["stock_item_id"] for l in requests.get(f"{LISTS}/{list_id}").json()["lines"]}
        assert out_id in line_items
        assert stocked_id not in line_items
        assert [u["ingredient_name"] for u in body["unlinked_skipped"]] == ["a pinch of something"]
    finally:
        if list_id:
            requests.delete(f"{LISTS}/{list_id}")
        requests.delete(f"{BASE}/recipes/{recipe_id}")
        requests.delete(f"{BASE}/stock-items/{out_id}")
        requests.delete(f"{BASE}/stock-items/{stocked_id}")
