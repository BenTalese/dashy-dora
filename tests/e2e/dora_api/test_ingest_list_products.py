"""Batch D — `GET /api/ingest/products`, the list a source refreshes against.

PF-7: the companion pulls what Dora holds, re-scrapes it, pushes back. Pinned
here: bearer auth, PF-8 (inactive products are excluded — "inactive" means
"don't scrape"), the per-source store-name mapping being the *inverse* of what
the write side resolves, and paging.
"""
from uuid import uuid4

import requests

BASE = "http://localhost:5170/api"
INGEST_PRODUCTS = f"{BASE}/ingest/products"


def _mint_source() -> tuple[str, str]:
    """Returns (source_id, raw_key). The key is only ever shown at create."""
    resp = requests.post(f"{BASE}/ingestion-sources", json={
        "label": f"puller-{uuid4().hex[:8]}",
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body["source"]["id"], body["key"]


def _auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def _push(key: str, *, store: str, name: str, stockcode: str) -> None:
    """Create a product the way a producer really does, so the store mapping
    exists on the same path the read side reverses."""
    resp = requests.post(f"{BASE}/ingest", headers={
        **_auth(key), "Idempotency-Key": uuid4().hex,
    }, json={
        "products": [{
            "ref": "p0", "name": name, "store": store,
            "merchant_stockcode": stockcode, "brand": "Test",
            "size": "1L", "size_unit": "L", "size_value": 1.0,
            "web_url": "https://example.test/p",
        }],
        "offers": [{
            "product_ref": "p0", "price_now": 2.0, "price_was": 3.0,
            "observed_at": "2026-09-06T00:00:00+00:00",
        }],
    })
    assert resp.status_code in (200, 201), resp.text


def _map_store(source_id: str, external: str, store_name: str = "Woolworths") -> None:
    """Point the quarantined external name at a real Dora store, admin-side —
    the same thing the operator does on the API access page."""
    stores = requests.get(f"{BASE}/stores").json()["items"]
    store_id = next(s["store_id"] for s in stores if s["name"] == store_name)
    resp = requests.put(
        f"{BASE}/ingestion-sources/{source_id}/store-mappings",
        json={"external_name": external, "store_id": store_id},
    )
    assert resp.status_code in (200, 201, 204), resp.text


def _items(key: str, **params) -> list[dict]:
    resp = requests.get(INGEST_PRODUCTS, headers=_auth(key), params=params or None)
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


def test__list__requires_a_bearer_key():
    assert requests.Session().get(INGEST_PRODUCTS).status_code == 401


def test__list__rejects_a_bad_key():
    assert requests.Session().get(
        INGEST_PRODUCTS, headers={"Authorization": "Bearer nope"},
    ).status_code == 401


def test__list__carries_store_id_on_every_row_even_without_mappings():
    """2026-10-15: a source can push by Dora store id, which has no mapping
    row, so the list no longer hides unmapped stores. Every row names its
    store by id; the caller skips what it can't scrape."""
    _, key = _mint_source()

    items = _items(key)
    assert items, "seeded scraped products are listed"
    assert all(row["store_id"] for row in items)


def test__list__returns_mapped_products_with_the_sources_own_store_name():
    source_id, key = _mint_source()
    external = f"ExternalMart-{uuid4().hex[:6]}"
    name = f"Pullable-{uuid4().hex[:6]}"
    # First push quarantines the unknown store name; mapping it is the admin
    # step; the second push then lands the product.
    _push(key, store=external, name=name, stockcode="SKU-1")
    _map_store(source_id, external)
    _push(key, store=external, name=name, stockcode="SKU-1")

    rows = [r for r in _items(key) if r["name"] == name]

    assert len(rows) == 1, "the pushed product didn't come back"
    row = rows[0]
    assert row["store"] == external, (
        "store must be the name this source pushed, not Dora's store name — "
        "otherwise it can't push the refreshed offer back"
    )
    assert row["merchant_stockcode"] == "SKU-1"
    assert row["product_id"]


def test__list__omits_inactive_products():
    """PF-8 — inactive means "don't scrape me", not merely "don't show me"."""
    source_id, key = _mint_source()
    external = f"ExternalMart-{uuid4().hex[:6]}"
    name = f"Deselected-{uuid4().hex[:6]}"
    _push(key, store=external, name=name, stockcode="SKU-2")
    _map_store(source_id, external)
    _push(key, store=external, name=name, stockcode="SKU-2")

    product_id = next(r["product_id"] for r in _items(key) if r["name"] == name)
    assert requests.patch(
        f"{BASE}/products/{product_id}", json={"is_active": False},
    ).status_code == 204

    assert all(r["name"] != name for r in _items(key))


def test__list__pages():
    source_id, key = _mint_source()
    external = f"ExternalMart-{uuid4().hex[:6]}"
    _push(key, store=external, name=f"Page-{uuid4().hex[:6]}", stockcode="SKU-A")
    _map_store(source_id, external)
    for i in range(3):
        _push(
            key, store=external,
            name=f"Paged-{i}-{uuid4().hex[:6]}", stockcode=f"SKU-P{i}",
        )

    first = _items(key, limit=1)
    second = _items(key, limit=1, offset=1)

    assert len(first) == 1 and len(second) == 1
    assert first[0]["product_id"] != second[0]["product_id"]


def test__list__rejects_nonsense_paging():
    _, key = _mint_source()

    assert requests.get(
        INGEST_PRODUCTS, headers=_auth(key), params={"limit": "banana"},
    ).status_code == 400
    assert requests.get(
        INGEST_PRODUCTS, headers=_auth(key), params={"limit": 0},
    ).status_code == 400
    assert requests.get(
        INGEST_PRODUCTS, headers=_auth(key), params={"offset": -1},
    ).status_code == 400


def test__list__same_named_products_page_in_a_stable_id_order():
    """Ordering by `name` alone left same-named products (one per store) in
    no defined order, so offset paging could skip or repeat one. `id` breaks
    the tie."""
    _, key = _mint_source()
    stores = requests.get(f"{BASE}/stores").json()["items"]
    name = f"AAA-Twin-{uuid4().hex[:6]}"
    for store in stores[:3]:
        resp = requests.post(f"{BASE}/ingest", headers=_auth(key), json={
            "products": [{"ref": "p0", "name": name, "store_id": store["store_id"]}],
            "offers": [],
        })
        assert resp.status_code == 200, resp.text

    twins = [r["product_id"] for r in _items(key, limit=500) if r["name"] == name]
    assert len(twins) == len(stores[:3]) >= 2
    assert twins == sorted(twins)
