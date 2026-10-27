"""FU-512 — `POST /shopping-list-templates` is a unit of work.

Pre-FU-512 committed twice (template row, then lines). Now: one commit.
"""
from uuid import uuid4

import requests

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
