"""2026-10-15 — Dora's stores as the companion's source of truth.

* `GET /api/ingest/stores` lists Dora's stores (bearer-authed).
* `GET /api/ingest/stores/<id>/image` serves a store's logo to the same caller.
* `/api/ingest` and `/api/ingest/link-status` accept `store_id` in place of a
  mapped external `store` name.
* `/api/ingest/products` carries `store_id`, and lists products pushed by id.
"""
import uuid
from datetime import datetime, timezone

import requests

BASE = "http://localhost:5170/api"
INGEST = f"{BASE}/ingest"
SOURCES = f"{BASE}/ingestion-sources"


def _mint_key() -> str:
    resp = requests.post(SOURCES, json={"label": f"src-{uuid.uuid4().hex[:8]}"})
    assert resp.status_code == 201, resp.text
    return resp.json()["key"]


def _auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def _seeded_store() -> dict:
    stores = requests.get(f"{BASE}/stores").json()["items"]
    assert stores
    return stores[0]


def test__ingest_stores__requires_the_bearer_key(api):
    assert requests.get(f"{INGEST}/stores").status_code == 401


def test__ingest_stores__lists_dora_stores(api):
    key = _mint_key()
    resp = requests.get(f"{INGEST}/stores", headers=_auth(key))
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    store = _seeded_store()
    row = next(i for i in items if i["store_id"] == store["store_id"])
    assert row["name"] == store["name"]
    assert isinstance(row["has_image"], bool)


def test__ingest_store_image__404_when_no_logo(api):
    # A fresh store has no logo, whatever the seed's stores carry.
    created = requests.post(f"{BASE}/stores", json={"name": f"Bare {uuid.uuid4().hex[:8]}"})
    assert created.status_code == 201, created.text
    bare_id = created.json()["store_id"]
    key = _mint_key()
    stores = requests.get(f"{INGEST}/stores", headers=_auth(key)).json()["items"]
    assert next(s for s in stores if s["store_id"] == bare_id)["has_image"] is False

    resp = requests.get(f"{INGEST}/stores/{bare_id}/image", headers=_auth(key))
    assert resp.status_code == 404


def test__ingest__by_store_id_creates_the_product_and_lists_it(api):
    key = _mint_key()
    store = _seeded_store()
    name = f"ById {uuid.uuid4().hex[:8]}"
    body = {
        "products": [{
            "ref": "p0", "name": name, "store_id": store["store_id"],
            "merchant_stockcode": f"SKU-{uuid.uuid4().hex[:6]}",
        }],
        "offers": [{
            "product_ref": "p0", "price_now": 4.5,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }],
    }
    resp = requests.post(INGEST, json=body, headers=_auth(key))
    assert resp.status_code == 200, resp.text
    assert {r["kind"] for r in resp.json()["accepted"]} == {"product", "offer"}

    listed = requests.get(f"{INGEST}/products?limit=500", headers=_auth(key)).json()["items"]
    row = next(r for r in listed if r["name"] == name)
    assert row["store_id"] == store["store_id"]

    status = requests.post(f"{INGEST}/link-status", headers=_auth(key), json={
        "items": [{"ref": "x", "store_id": store["store_id"], "name": name}],
    }).json()["items"][0]
    assert status["product_id"] == row["product_id"]


def test__ingest__unknown_store_id_is_skipped(api):
    key = _mint_key()
    body = {"products": [{"ref": "p0", "name": "Nowhere", "store_id": str(uuid.uuid4())}]}
    resp = requests.post(INGEST, json=body, headers=_auth(key))
    assert resp.status_code == 200, resp.text
    assert resp.json()["skipped"][0]["reason"] == "store_unknown"


def test__ingest__store_and_store_id_together_is_a_400(api):
    key = _mint_key()
    store = _seeded_store()
    body = {"products": [{
        "ref": "p0", "name": "Both", "store": "Woolworths", "store_id": store["store_id"],
    }]}
    assert requests.post(INGEST, json=body, headers=_auth(key)).status_code == 400
