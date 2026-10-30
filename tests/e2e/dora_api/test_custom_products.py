"""OD-2 — hand-entered ("custom") products.

`PreferredBuy` was supposed to cover shops no scraper reaches, but it is a
*label*: no price, no store, no history. So recording "the butcher's mince is
$12/kg" meant choosing between a note you couldn't compare and a product you
couldn't create.

The interesting tests here are the two isolation ones. A custom product is the
user's own figure, and the two ways it could be silently overwritten by
machinery are ingestion dedupe and the scheduled sync.
"""
from uuid import uuid4

import requests

from tests.support import assert_problem

BASE = "http://localhost:5170/api"


def _store_name() -> str:
    return requests.get(f"{BASE}/stores").json()["items"][0]["name"]


def _create_custom(**overrides) -> str:
    body = {
        "name": f"Butcher Mince-{uuid4().hex[:8]}",
        "store_name": _store_name(),
        "brand": "Local Butcher",
        "is_active": True,
        "is_available": True,
        "price_now": 12.0,
        "size": "1kg",
        "size_unit": "KG",
        "size_value": 1.0,
    }
    body.update(overrides)
    resp = requests.post(f"{BASE}/products", json=body)
    assert resp.status_code == 201, resp.text
    return resp.headers["location"].rsplit(":", 1)[-1]


def _fetch(product_id: str) -> dict:
    items = requests.get(f"{BASE}/products").json()["items"]
    return next(p for p in items if p["product_id"] == product_id)


def test__a_manually_created_product_is_marked_custom():
    product_id = _create_custom()

    assert _fetch(product_id)["is_custom"] is True


def test__price_was_is_optional_and_defaults_to_no_markdown():
    """A hand-entered product usually has no "was" price. Defaulting to 0.0
    would make every custom product look permanently discounted."""
    product_id = _create_custom(price_now=12.0)

    product = _fetch(product_id)

    assert product["price_now"] == 12.0
    assert product["price_was"] == 12.0


def test__price_was_is_kept_when_supplied():
    product_id = _create_custom(price_now=9.0, price_was=12.0)

    product = _fetch(product_id)

    assert product["price_now"] == 9.0
    assert product["price_was"] == 12.0


def test__an_ingested_product_is_not_marked_custom():
    """Guards the marking: if `is_custom` were true for everything, the two
    isolation tests below would pass for the wrong reason."""
    items = requests.get(f"{BASE}/products").json()["items"]
    seeded = [p for p in items if not p["is_custom"]]

    assert seeded, "the seed should hold ingested (non-custom) products"


# ── Isolation: the two ways a custom product could be silently overwritten ──

def test__ingestion_does_not_adopt_a_custom_product_with_the_same_name():
    """Dedupe falls back to (store, name) for records without a stockcode, so
    a scraped "Mince" would otherwise match a hand-entered "Mince" at the same
    store and overwrite its brand, size and price — the user's own figure
    quietly replaced by scraped data."""
    store = _store_name()
    name = f"Contested Mince-{uuid4().hex[:8]}"
    custom_id = _create_custom(name=name, price_now=12.0, brand="Local Butcher")

    # A producer pushes a product of exactly the same name, same store.
    source = requests.post(f"{BASE}/ingestion-sources", json={
        "label": f"clash-{uuid4().hex[:6]}",
    }).json()
    key, source_id = source["key"], source["source"]["id"]
    external = f"Clash-{uuid4().hex[:6]}"
    push = {
        "products": [{
            "ref": "p0", "name": name, "store": external,
            "brand": "Supermarket Brand", "size": "500g",
            "size_unit": "G", "size_value": 500.0,
        }],
        "offers": [{
            "product_ref": "p0", "price_now": 3.0, "price_was": 4.0,
            "observed_at": "2026-09-08T00:00:00+00:00",
        }],
    }
    headers = {"Authorization": f"Bearer {key}", "Idempotency-Key": uuid4().hex}
    requests.post(f"{BASE}/ingest", headers=headers, json=push)
    store_id = next(
        s["store_id"] for s in requests.get(f"{BASE}/stores").json()["items"]
        if s["name"] == store
    )
    requests.put(
        f"{BASE}/ingestion-sources/{source_id}/store-mappings",
        json={"external_name": external, "store_id": store_id},
    )
    requests.post(f"{BASE}/ingest", headers={
        "Authorization": f"Bearer {key}", "Idempotency-Key": uuid4().hex,
    }, json=push)

    custom = _fetch(custom_id)
    assert custom["is_custom"] is True
    assert custom["price_now"] == 12.0, "the scrape overwrote the user's price"
    assert custom["brand"] == "Local Butcher", "the scrape overwrote the brand"


def test__the_sync_list_excludes_custom_products():
    """A custom product has no upstream to refresh from — offering it to a
    producer wastes a request at best, and has it matched against something
    else entirely at worst."""
    store = _store_name()
    name = f"Sync Excluded-{uuid4().hex[:8]}"
    _create_custom(name=name)

    source = requests.post(f"{BASE}/ingestion-sources", json={
        "label": f"sync-{uuid4().hex[:6]}",
    }).json()
    key, source_id = source["key"], source["source"]["id"]
    store_id = next(
        s["store_id"] for s in requests.get(f"{BASE}/stores").json()["items"]
        if s["name"] == store
    )
    requests.put(
        f"{BASE}/ingestion-sources/{source_id}/store-mappings",
        json={"external_name": store, "store_id": store_id},
    )

    listed = requests.get(
        f"{BASE}/ingest/products", headers={"Authorization": f"Bearer {key}"},
    ).json()["items"]

    assert all(row["name"] != name for row in listed)


def test__the_sync_list_still_offers_ingested_products():
    """Guards the test above — if the list were simply empty, it would pass
    without the exclusion doing anything."""
    source = requests.post(f"{BASE}/ingestion-sources", json={
        "label": f"sync2-{uuid4().hex[:6]}",
    }).json()
    key, source_id = source["key"], source["source"]["id"]
    stores = requests.get(f"{BASE}/stores").json()["items"]
    for store in stores:
        requests.put(
            f"{BASE}/ingestion-sources/{source_id}/store-mappings",
            json={"external_name": store["name"], "store_id": store["store_id"]},
        )

    listed = requests.get(
        f"{BASE}/ingest/products", headers={"Authorization": f"Bearer {key}"},
    ).json()["items"]

    assert listed, "no ingested products offered — the exclusion is too broad"


# ── Photos: settable on custom products only (owner 2026-10-17) ─────────────

# 1x1 transparent PNG — the shape `processImageFile` hands the API.
_PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def test__a_custom_product_photo_can_be_set_served_and_cleared():
    product_id = _create_custom()

    resp = requests.patch(f"{BASE}/products/{product_id}", json={"image": _PNG_DATA_URL})
    assert resp.status_code == 204, resp.text
    assert _fetch(product_id)["has_image"] is True
    image = requests.get(f"{BASE}/products/{product_id}/image")
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/png")

    resp = requests.patch(f"{BASE}/products/{product_id}", json={"clear_image": True})
    assert resp.status_code == 204, resp.text
    assert _fetch(product_id)["has_image"] is False


def test__an_ingested_product_photo_cannot_be_changed():
    """The picture of a scraped product belongs to its source; a hand-set one
    would be overwritten by (or silently diverge from) the next ingest."""
    items = requests.get(f"{BASE}/products").json()["items"]
    ingested = next(p for p in items if not p["is_custom"])

    set_resp = requests.patch(
        f"{BASE}/products/{ingested['product_id']}", json={"image": _PNG_DATA_URL},
    )
    clear_resp = requests.patch(
        f"{BASE}/products/{ingested['product_id']}", json={"clear_image": True},
    )

    assert set_resp.status_code == 422, set_resp.text
    assert clear_resp.status_code == 422, clear_resp.text
    assert _fetch(ingested["product_id"])["has_image"] is ingested["has_image"]


def test__a_custom_product_photo_must_be_an_image_data_url():
    product_id = _create_custom()

    resp = requests.patch(f"{BASE}/products/{product_id}", json={"image": "not-a-data-url"})

    assert resp.status_code == 422, resp.text
    assert _fetch(product_id)["has_image"] is False


def test__a_custom_product_can_be_created_with_a_photo():
    product_id = _create_custom(image=_PNG_DATA_URL)

    assert _fetch(product_id)["has_image"] is True


# ── pack_count (FU-856) ──────────────────────────────────────────────────


def test__pack_count_is_kept_when_created():
    product_id = _create_custom(
        name=f"Free Range Eggs-{uuid4().hex[:8]}",
        size="700g", size_unit="G", size_value=700.0, pack_count=12,
    )

    assert _fetch(product_id)["pack_count"] == 12


def test__pack_count_defaults_to_none():
    assert _fetch(_create_custom())["pack_count"] is None


def test__pack_count_must_be_positive_on_create():
    body = {
        "name": f"Eggs-{uuid4().hex[:8]}", "store_name": _store_name(),
        "is_active": True, "is_available": True, "price_now": 5.5,
        "size": "700g", "size_unit": "G", "size_value": 700.0, "pack_count": 0,
    }

    assert requests.post(f"{BASE}/products", json=body).status_code == 400


def test__pack_count_can_be_set_and_cleared_on_an_ingested_product():
    """The case the field exists for: a scraped carton of eggs whose source
    never said how many are in it."""
    items = requests.get(f"{BASE}/products").json()["items"]
    product_id = next(p for p in items if not p["is_custom"])["product_id"]

    set_resp = requests.patch(f"{BASE}/products/{product_id}", json={"pack_count": 6})
    assert set_resp.status_code == 204, set_resp.text
    assert _fetch(product_id)["pack_count"] == 6

    untouched = requests.patch(f"{BASE}/products/{product_id}", json={"is_active": True})
    assert untouched.status_code == 204
    assert _fetch(product_id)["pack_count"] == 6

    clear_resp = requests.patch(f"{BASE}/products/{product_id}", json={"pack_count": None})
    assert clear_resp.status_code == 204
    assert _fetch(product_id)["pack_count"] is None


def test__pack_count_must_be_positive_on_update():
    product_id = _create_custom()

    resp = requests.patch(f"{BASE}/products/{product_id}", json={"pack_count": 0})

    assert resp.status_code == 400


def test__create__web_url_must_be_http_and_strings_fit_their_columns():
    """`web_url` is rendered as an "Open on store" href, so `javascript:` is
    refused; and every string is capped at its `String(255)` column (Postgres
    enforces it — an over-long value used to 500 instead of 400)."""
    body = {
        "name": f"Url-{uuid4().hex[:8]}",
        "store_name": _store_name(),
        "is_active": True,
        "is_available": True,
        "price_now": 3.0,
        "size": "1kg",
        "size_unit": "KG",
        "size_value": 1.0,
    }
    for field, value in (
        ("web_url", "javascript:alert(1)"),
        ("web_url", "https://example.test/" + "a" * 250),
        ("name", "n" * 256),
        ("brand", "b" * 256),
        ("size", "s" * 256),
        ("size_unit", "u" * 256),
        ("merchant_stockcode", "m" * 256),
    ):
        assert_problem(requests.post(f"{BASE}/products", json={**body, field: value}),
                       400, field=field)

    product_id = _create_custom(web_url="https://example.test/mince")
    assert _fetch(product_id)["web_url"] == "https://example.test/mince"
