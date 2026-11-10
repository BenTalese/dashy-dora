"""2026-11-10: link a product to a stock item as the companion saves it.

* `GET /api/ingest/stock-items` lists stock items (bearer-authed).
* `stock_item_id` on a pushed product links it, reported as a `link` record.
"""
import uuid

import requests

from tests.factories import make_stock_item

BASE = "http://localhost:5170/api"
INGEST = f"{BASE}/ingest"
SOURCES = f"{BASE}/ingestion-sources"


def _mint_key() -> str:
    resp = requests.post(SOURCES, json={"label": f"src-{uuid.uuid4().hex[:8]}"})
    assert resp.status_code == 201, resp.text
    return resp.json()["key"]


def _auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def _item(prefix: str) -> dict:
    level = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    return make_stock_item(stock_level_id=level, name=f"{prefix} {uuid.uuid4().hex[:8]}")


def _push(key: str, stock_item_id: str | None, name: str) -> dict:
    store = requests.get(f"{BASE}/stores").json()["items"][0]
    product = {"ref": "p0", "name": name, "store_id": store["store_id"]}
    if stock_item_id is not None:
        product["stock_item_id"] = stock_item_id
    resp = requests.post(INGEST, json={"products": [product], "offers": []}, headers=_auth(key))
    assert resp.status_code == 200, resp.text
    return resp.json()


def test__ingest_stock_items__requires_the_bearer_key(api):
    assert requests.get(f"{INGEST}/stock-items").status_code == 401


def test__ingest_stock_items__lists_id_and_name(api):
    item = _item("Ingest Oats")
    resp = requests.get(f"{INGEST}/stock-items", headers=_auth(_mint_key()))
    assert resp.status_code == 200, resp.text
    row = next(i for i in resp.json()["items"] if i["stock_item_id"] == item["stock_item_id"])
    assert row == {"stock_item_id": item["stock_item_id"], "name": item["name"]}


def test__ingest__stock_item_id_links_the_saved_product(api):
    key = _mint_key()
    item = _item("Ingest Rice")
    body = _push(key, item["stock_item_id"], f"Rice {uuid.uuid4().hex[:8]}")

    product_id = next(r["id"] for r in body["accepted"] if r["kind"] == "product")
    link = next(r for r in body["accepted"] if r["kind"] == "link")
    assert link == {"kind": "link", "ref": "p0", "id": item["stock_item_id"], "note": "linked"}

    detail = requests.get(f"{BASE}/stock-items/{item['stock_item_id']}/detail").json()
    assert product_id in [p["product_id"] for p in detail["products"]]


def test__ingest__relinking_the_same_item_is_a_no_op(api):
    key = _mint_key()
    item = _item("Ingest Tea")
    name = f"Tea {uuid.uuid4().hex[:8]}"
    _push(key, item["stock_item_id"], name)
    body = _push(key, item["stock_item_id"], name)
    assert next(r for r in body["accepted"] if r["kind"] == "link")["note"] == "already_linked"


def test__ingest__link_to_another_item_is_skipped_and_the_product_still_saves(api):
    key = _mint_key()
    first, second = _item("Ingest Flour"), _item("Ingest Sugar")
    name = f"Flour {uuid.uuid4().hex[:8]}"
    _push(key, first["stock_item_id"], name)
    body = _push(key, second["stock_item_id"], name)
    assert any(r["kind"] == "product" for r in body["accepted"])
    assert body["skipped"] == [{"kind": "link", "ref": "p0", "reason": "linked_elsewhere"}]


def test__ingest__unknown_stock_item_is_skipped(api):
    body = _push(_mint_key(), str(uuid.uuid4()), f"Ghost {uuid.uuid4().hex[:8]}")
    assert any(r["kind"] == "product" for r in body["accepted"])
    assert body["skipped"] == [{"kind": "link", "ref": "p0", "reason": "stock_item_unknown"}]
