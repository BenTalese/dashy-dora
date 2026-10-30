"""C-10.5 / FU-422 — `POST /api/ingest/link-status`.

Read-side companion to the ingest endpoint. A source pushes the same
identifiers it would use on the write path — `(store, merchant_stockcode)`
first, `(store, name)` fallback — and gets back per-item link status so it
can decorate its own search UI with "already linked".

Auth reuses the batch endpoint's bearer flow (test_ingest_batch covers the
missing/bad/disabled key cases against `submit_ingestion_batch`; the
route-agnostic middleware exemption + `find_ingestion_source` helper mean
`ingest_link_status` inherits the same auth behaviour — one auth case
below just pins that on the new route).
"""
import uuid

import requests

BASE = "http://localhost:5170/api"
INGEST = f"{BASE}/ingest"
LINK_STATUS = f"{INGEST}/link-status"
SOURCES = f"{BASE}/ingestion-sources"
STOCK_ITEMS = f"{BASE}/stock-items"


def _mint_key(label: str | None = None) -> tuple[str, str]:
    payload = {"label": label or f"src-{uuid.uuid4().hex[:8]}"}
    resp = requests.post(SOURCES, json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body["source"]["id"], body["key"]


def _seeded_store_id() -> str:
    stores = requests.get(f"{BASE}/stores").json()["items"]
    assert stores, "expected seed to provision at least one store"
    return stores[0]["store_id"]


def _map_store(source_id: str, external_name: str, store_id: str) -> None:
    resp = requests.put(
        f"{SOURCES}/{source_id}/store-mappings",
        json={"external_name": external_name, "store_id": store_id},
    )
    assert resp.status_code in (200, 201, 204), resp.text


def _post_ingest(key: str, body: dict) -> requests.Response:
    return requests.post(
        INGEST, json=body,
        headers={"Authorization": f"Bearer {key}"},
    )


def _post_link_status(key: str, body: dict) -> requests.Response:
    return requests.post(
        LINK_STATUS, json=body,
        headers={"Authorization": f"Bearer {key}"},
    )


def _seed_ingested_product(key: str, source_id: str, external_store: str,
                           stockcode: str, name: str) -> str:
    """Push a product through the write path so the lookup has something to
    find. Returns the created product_id."""
    resp = _post_ingest(key, {
        "products": [{
            "ref": "seed",
            "name": name,
            "store": external_store,
            "merchant_stockcode": stockcode,
        }],
        "offers": [{
            "product_ref": "seed",
            "price_now": 2.50,
            "observed_at": "2026-07-12T00:00:00+00:00",
        }],
    })
    assert resp.status_code == 200, resp.text
    accepted = [r for r in resp.json()["accepted"] if r["kind"] == "product"]
    assert accepted, resp.text
    return accepted[0]["id"]


def _link_to_a_stock_item(product_id: str) -> str:
    """Uses the existing session-authed link endpoint. Session auth is
    already provisioned by the `api` fixture on the requests module."""
    stock_items = requests.get(STOCK_ITEMS).json()["items"]
    assert stock_items, "expected seed to provision at least one stock item"
    stock_item_id = stock_items[0]["stock_item_id"]
    resp = requests.post(
        f"{STOCK_ITEMS}/{stock_item_id}/products",
        json={"product_id": product_id},
    )
    assert resp.status_code in (200, 201, 204), resp.text
    return stock_item_id


# ── Auth ──────────────────────────────────────────────────────────────

def test__link_status__rejects_missing_bearer(api):
    resp = requests.post(LINK_STATUS, json={"items": []})
    assert resp.status_code == 401, resp.text


# ── Contract ──────────────────────────────────────────────────────────

def test__link_status__unknown_store_returns_store_not_mapped(api):
    _sid, key = _mint_key()
    resp = _post_link_status(key, {
        "items": [{"ref": "a", "store": "Nowhere", "merchant_stockcode": "X"}],
    })
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0] == {
        "ref": "a", "product_id": None,
        "linked_stock_item_id": None, "linked_stock_item_name": None,
        "reason": "store_not_mapped",
    }


def test__link_status__mapped_store_but_unknown_product_returns_not_found(api):
    sid, key = _mint_key()
    _map_store(sid, "ExternalStore", _seeded_store_id())
    resp = _post_link_status(key, {
        "items": [{"ref": "a", "store": "ExternalStore",
                   "merchant_stockcode": uuid.uuid4().hex[:10]}],
    })
    assert resp.status_code == 200, resp.text
    item = resp.json()["items"][0]
    assert item["product_id"] is None
    assert item["reason"] == "product_not_found"


def test__link_status__known_product_unlinked_reports_no_stock_item(api):
    sid, key = _mint_key()
    _map_store(sid, "ExternalStore", _seeded_store_id())
    stockcode = uuid.uuid4().hex[:10]
    product_id = _seed_ingested_product(
        key, sid, "ExternalStore", stockcode, f"Unlinked {uuid.uuid4().hex[:6]}",
    )

    resp = _post_link_status(key, {
        "items": [{"ref": "a", "store": "ExternalStore",
                   "merchant_stockcode": stockcode}],
    })
    assert resp.status_code == 200, resp.text
    item = resp.json()["items"][0]
    assert item["product_id"] == product_id
    assert item["linked_stock_item_id"] is None
    assert item["linked_stock_item_name"] is None
    assert item.get("reason") is None


def test__link_status__known_product_linked_returns_stock_item(api):
    sid, key = _mint_key()
    _map_store(sid, "ExternalStore", _seeded_store_id())
    stockcode = uuid.uuid4().hex[:10]
    name = f"Linked {uuid.uuid4().hex[:6]}"
    product_id = _seed_ingested_product(key, sid, "ExternalStore", stockcode, name)
    stock_item_id = _link_to_a_stock_item(product_id)

    resp = _post_link_status(key, {
        "items": [{"ref": "a", "store": "ExternalStore",
                   "merchant_stockcode": stockcode}],
    })
    assert resp.status_code == 200, resp.text
    item = resp.json()["items"][0]
    assert item["product_id"] == product_id
    assert item["linked_stock_item_id"] == stock_item_id
    assert item["linked_stock_item_name"], "expected a name for the linked stock item"


def test__link_status__name_fallback_matches_when_no_stockcode(api):
    """Stockcode-first, name-fallback — same order as the write side, so a
    caller that only has a name still resolves."""
    sid, key = _mint_key()
    _map_store(sid, "ExternalStore", _seeded_store_id())
    name = f"NameOnly {uuid.uuid4().hex[:6]}"
    stockcode = uuid.uuid4().hex[:10]
    product_id = _seed_ingested_product(key, sid, "ExternalStore", stockcode, name)

    resp = _post_link_status(key, {
        "items": [{"ref": "a", "store": "ExternalStore", "name": name}],
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["items"][0]["product_id"] == product_id


def test__link_status__mixed_batch_resolves_per_item(api):
    """One request, one call — a batch with a hit, a miss, and an
    unmapped-store row each get their own per-item verdict."""
    sid, key = _mint_key()
    _map_store(sid, "ExternalStore", _seeded_store_id())
    stockcode = uuid.uuid4().hex[:10]
    name = f"Batch {uuid.uuid4().hex[:6]}"
    product_id = _seed_ingested_product(key, sid, "ExternalStore", stockcode, name)

    resp = _post_link_status(key, {
        "items": [
            {"ref": "hit", "store": "ExternalStore", "merchant_stockcode": stockcode},
            {"ref": "miss", "store": "ExternalStore",
             "merchant_stockcode": uuid.uuid4().hex[:10]},
            {"ref": "unmapped", "store": "Nowhere", "merchant_stockcode": "X"},
        ],
    })
    assert resp.status_code == 200, resp.text
    by_ref = {i["ref"]: i for i in resp.json()["items"]}
    assert by_ref["hit"]["product_id"] == product_id
    assert by_ref["miss"]["reason"] == "product_not_found"
    assert by_ref["unmapped"]["reason"] == "store_not_mapped"


def test__link_status__item_without_stockcode_or_name_is_not_found(api):
    sid, key = _mint_key()
    _map_store(sid, "ExternalStore", _seeded_store_id())
    resp = _post_link_status(key, {
        "items": [{"ref": "a", "store": "ExternalStore"}],
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["items"][0]["reason"] == "product_not_found"


def test__link_status__never_resolves_a_custom_product__and_bearer_delete_refuses_it(api):
    """Finalisation 16-R8 — the read side used to look products up without
    the OD-2 `is_custom` filter the write side dedupes with. A name the user
    had typed in by hand came back "already in Dora", and the companion's
    unsave then deleted the user's own product through the bearer door. Now:
    the lookup says not held, a push of the same name creates its own row,
    and the bearer delete refuses a custom id outright."""
    sid, key = _mint_key()
    store = requests.get(f"{BASE}/stores").json()["items"][0]
    _map_store(sid, "ExternalStore", store["store_id"])
    name = f"Butcher Mince {uuid.uuid4().hex[:6]}"

    created = requests.post(f"{BASE}/products", json={
        "name": name,
        "store_name": store["name"],
        "brand": "Local Butcher",
        "is_active": True,
        "is_available": True,
        "price_now": 12.0,
        "size": "1kg",
        "size_unit": "KG",
        "size_value": 1.0,
    })
    assert created.status_code == 201, created.text
    custom_id = created.headers["location"].rsplit(":", 1)[-1]

    # Read side: a custom product is not "held" as far as a producer is told.
    status = _post_link_status(key, {
        "items": [{"ref": "a", "store": "ExternalStore", "name": name}],
    })
    assert status.status_code == 200, status.text
    assert status.json()["items"][0]["product_id"] is None
    assert status.json()["items"][0]["reason"] == "product_not_found"

    # Write side: the same name creates its own row, never adopts the custom one.
    pushed = _post_ingest(key, {
        "products": [{"ref": "p", "name": name, "store": "ExternalStore"}],
        "offers": [],
    })
    assert pushed.status_code == 200, pushed.text
    ingested_id = pushed.json()["accepted"][0]["id"]
    assert ingested_id != custom_id

    # And a producer holding a custom id (stale or guessed) cannot delete it.
    refused = requests.Session().delete(
        f"{INGEST}/products/{custom_id}", headers={"Authorization": f"Bearer {key}"},
    )
    assert refused.status_code == 403, refused.text
    still_there = requests.get(f"{BASE}/products", params={"filter": f"product_id:eq:{custom_id}"})
    assert len(still_there.json()["items"]) == 1


def test__link_status__name_fallback_is_scoped_to_the_named_store(api):
    """The read-side lookup filtered on the Store entity without joining it,
    so SQLAlchemy built a cartesian `FROM Product, Store` and the name
    fallback matched a same-named product at ANY store; the companion's
    unsave then deleted the wrong product. A product held only at store A is
    not held at store B."""
    stores = requests.get(f"{BASE}/stores").json()["items"]
    assert len(stores) >= 2, "expected seed to provision at least two stores"
    sid, key = _mint_key()
    _map_store(sid, "StoreA", stores[0]["store_id"])
    _map_store(sid, "StoreB", stores[1]["store_id"])
    name = f"TwoStore {uuid.uuid4().hex[:6]}"
    product_id = _seed_ingested_product(key, sid, "StoreA", uuid.uuid4().hex[:10], name)

    resp = _post_link_status(key, {
        "items": [
            {"ref": "a", "store": "StoreA", "name": name},
            {"ref": "b", "store": "StoreB", "name": name},
        ],
    })
    assert resp.status_code == 200, resp.text
    by_ref = {i["ref"]: i for i in resp.json()["items"]}
    assert by_ref["a"]["product_id"] == product_id
    assert by_ref["b"]["product_id"] is None
    assert by_ref["b"]["reason"] == "product_not_found"


def test__link_status__over_the_item_cap_is_rejected(api):
    _sid, key = _mint_key()
    resp = _post_link_status(key, {
        "items": [
            {"ref": f"r{i}", "store": "s", "merchant_stockcode": "x"}
            for i in range(201)
        ],
    })
    assert resp.status_code == 400, resp.text
