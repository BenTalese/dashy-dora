"""FU-512 — `POST /shopping-list-templates` is a unit of work.

Pre-FU-512 committed twice (template row, then lines). Now: one commit.
"""
from uuid import uuid4

import requests

from tests.support import assert_problem

BASE = "http://localhost:5170/api"
SL_TEMPLATES = f"{BASE}/shopping-list-templates"


def _a_stock_item_id() -> str:
    return requests.get(f"{BASE}/stock-items?limit=1").json()["items"][0]["stock_item_id"]


def test__create_shopping_list_template__with_lines__commits_template_and_lines_together(api):
    template_id = None
    try:
        resp = requests.post(SL_TEMPLATES, json={
            "name": f"FU-512 SL tpl {uuid4()}",
            "lines": [
                {"stock_item_id": _a_stock_item_id(), "quantity": 2},
            ],
        })
        assert resp.status_code == 201, resp.text
        template_id = resp.json()["template_id"]

        detail = requests.get(f"{SL_TEMPLATES}/{template_id}")
        assert detail.status_code == 200, detail.text
        assert len(detail.json()["lines"]) == 1
    finally:
        if template_id:
            requests.delete(f"{SL_TEMPLATES}/{template_id}")


def test__create_shopping_list_template__empty_lines__commits_the_template(api):
    template_id = None
    try:
        resp = requests.post(SL_TEMPLATES, json={
            "name": f"FU-512 empty SL tpl {uuid4()}",
            "lines": [],
        })
        assert resp.status_code == 201, resp.text
        template_id = resp.json()["template_id"]

        detail = requests.get(f"{SL_TEMPLATES}/{template_id}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["lines"] == []
    finally:
        if template_id:
            requests.delete(f"{SL_TEMPLATES}/{template_id}")


def test__list_templates__line_count_matches_the_lines(api):
    """03-R17 — the summary's `line_count` is a grouped count."""
    items = requests.get(f"{BASE}/stock-items?limit=2").json()["items"]
    template_id = None
    try:
        resp = requests.post(SL_TEMPLATES, json={
            "name": f"03-R17 tpl {uuid4()}",
            "lines": [{"stock_item_id": i["stock_item_id"], "quantity": 1} for i in items],
        })
        assert resp.status_code == 201, resp.text
        template_id = resp.json()["template_id"]
        summary = next(t for t in requests.get(SL_TEMPLATES).json() if t["template_id"] == template_id)
        assert summary["line_count"] == len(items) == 2
    finally:
        if template_id:
            requests.delete(f"{SL_TEMPLATES}/{template_id}")


def test__create_shopping_list_template__UnknownStockItemId__Is422AndNothingCreated(api):
    # The FK used to surface as an IntegrityError → 500.
    name = f"Unknown item tpl {uuid4()}"
    missing = str(uuid4())

    resp = requests.post(SL_TEMPLATES, json={
        "name": name, "lines": [{"stock_item_id": missing, "quantity": 1}],
    })

    assert_problem(resp, 422, field="lines", title="Entity(s) were not found.")
    assert all(t["name"] != name for t in requests.get(SL_TEMPLATES).json())


def test__create_shopping_list_template__RepeatedStockItem__FoldsToOneLine(api):
    item_id = _a_stock_item_id()
    resp = requests.post(SL_TEMPLATES, json={
        "name": f"Dup item tpl {uuid4()}",
        "lines": [
            {"stock_item_id": item_id, "quantity": 2},
            {"stock_item_id": item_id, "quantity": 5},
        ],
    })
    assert resp.status_code == 201, resp.text

    lines = requests.get(f"{SL_TEMPLATES}/{resp.json()['template_id']}").json()["lines"]

    assert len(lines) == 1
    assert lines[0]["quantity"] == 2


def test__create_shopping_list_template__ZeroQuantity__IsKeptAndInstantiatesAsOne(api):
    # The editor's stepper goes down to 0 ("none yet"); the template keeps it,
    # and instantiating clamps the list line to the >= 1 a list requires.
    resp = requests.post(SL_TEMPLATES, json={
        "name": f"Zero qty tpl {uuid4()}",
        "lines": [{"stock_item_id": _a_stock_item_id(), "quantity": 0}],
    })
    assert resp.status_code == 201, resp.text
    template_id = resp.json()["template_id"]
    assert requests.get(f"{SL_TEMPLATES}/{template_id}").json()["lines"][0]["quantity"] == 0

    inst = requests.post(f"{SL_TEMPLATES}/{template_id}/instantiate", json={})
    assert inst.status_code in (200, 201), inst.text
    list_id = inst.json()["shopping_list_id"]
    lines = requests.get(f"http://localhost:5170/api/shopping-lists/{list_id}").json()["lines"]
    assert [l["quantity"] for l in lines] == [1]
