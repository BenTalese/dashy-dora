"""FU-512 — `POST /shopping-list-templates/<id>/instantiate` is a unit of work.

Pre-FU-512 committed twice (new list, then lines) and skipped the second
commit when every template line pointed at a deleted stock item. Now: one
commit; a template with no persistable lines still creates an empty list.
"""
from uuid import uuid4

import requests

BASE = "http://localhost:5170/api"
SL_TEMPLATES = f"{BASE}/shopping-list-templates"
LISTS = f"{BASE}/shopping-lists"


def _a_stock_item_id() -> str:
    return requests.get(f"{BASE}/stock-items?limit=1").json()["items"][0]["stock_item_id"]


def test__instantiate_shopping_list_template__all_valid__commits_list_and_lines_together(api):
    template_id = requests.post(SL_TEMPLATES, json={
        "name": f"FU-512 SL tpl {uuid4()}",
        "lines": [{"stock_item_id": _a_stock_item_id(), "quantity": 1}],
    }).json()["template_id"]

    list_id = None
    try:
        resp = requests.post(f"{SL_TEMPLATES}/{template_id}/instantiate", json={
            "name": f"FU-512 instantiate {uuid4()}",
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["line_count"] == 1
        list_id = resp.json()["shopping_list_id"]

        detail = requests.get(f"{LISTS}/{list_id}")
        assert detail.status_code == 200, detail.text
        assert len(detail.json()["lines"]) == 1
    finally:
        if list_id:
            requests.delete(f"{LISTS}/{list_id}")
        requests.delete(f"{SL_TEMPLATES}/{template_id}")


def test__instantiate__merge_into_list__tops_up_and_skips_items_already_on_it(api):
    """03-R33 — a template merges into an existing list in one call."""
    items = [i["stock_item_id"] for i in requests.get(f"{BASE}/stock-items?limit=2").json()["items"]]
    template_id = requests.post(f"{BASE}/shopping-list-templates", json={
        "name": f"03-R33 tpl {uuid4()}",
        "lines": [{"stock_item_id": i, "quantity": 1} for i in items],
    }).json()["template_id"]
    list_name = f"03-R33 list {uuid4().hex[:8]}"
    list_id = requests.post(f"{BASE}/shopping-lists", json={"name": list_name}).json()["shopping_list_id"]
    try:
        assert requests.post(f"{BASE}/shopping-lists/{list_id}/lines", json={"stock_item_id": items[0]}).status_code in (200, 201)
        resp = requests.post(f"{BASE}/shopping-list-templates/{template_id}/instantiate", json={
            "merge_into_list_id": list_id,
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["shopping_list_id"] == list_id
        assert (body["line_count"], body["skipped_count"]) == (1, 1)
        detail = requests.get(f"{BASE}/shopping-lists/{list_id}").json()
        assert detail["display_name"] == list_name
        assert sorted(l["stock_item_id"] for l in detail["lines"]) == sorted(items)
    finally:
        requests.delete(f"{BASE}/shopping-lists/{list_id}")
        requests.delete(f"{BASE}/shopping-list-templates/{template_id}")
