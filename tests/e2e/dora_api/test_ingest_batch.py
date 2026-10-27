"""C-10.2 — `POST /api/ingest` (PROPOSAL_INGESTION_API §2.2-§2.4 + FU-190).

Covers the producer-facing contract:
- bearer-auth (good, missing, bad, disabled key)
- products dedupe (stockcode-first, name fallback) — shared catalogue
- offers append-only with the dedupe key
- per-record result DTO (a bad record never fails the batch)
- Idempotency-Key replay = no-op
- FU-190: unknown merchant quarantines into IngestionStoreMapping;
  mapping it then unblocks future ingest for that name.
- FU-232: multipack `pack_count` round-trips onto the Product row.
"""
import uuid

import requests

from dora_api.app import app
from dora_api.domain.entities.product import Product
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

BASE = "http://localhost:5170/api"
INGEST = f"{BASE}/ingest"
SOURCES = f"{BASE}/ingestion-sources"


def _mint_key(label: str | None = None) -> tuple[str, str]:
    """Returns (source_id, raw_key)."""
    payload = {"label": label or f"src-{uuid.uuid4().hex[:8]}"}
    resp = requests.post(SOURCES, json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body["source"]["id"], body["key"]


def _post_ingest(key: str, body: dict, idem: str | None = None) -> requests.Response:
    headers = {"Authorization": f"Bearer {key}"}
    if idem is not None:
        headers["Idempotency-Key"] = idem
    return requests.post(INGEST, json=body, headers=headers)


def _seeded_store_id() -> str:
    """Reuse a seeded Store — the test DB is session-scoped and other
    tests assert on the seeded store total, so we must not pollute."""
    stores = requests.get(f"{BASE}/stores").json()["items"]
    assert stores, "expected seed to provision at least one store"
    return stores[0]["store_id"]


def _map_store(source_id: str, external_name: str, store_id: str) -> None:
    """C-10.3 admin route — used here to satisfy FU-190 before pushing
    real records. Defined in C-10.3 (ingestion_source_admin)."""
    resp = requests.put(
        f"{SOURCES}/{source_id}/store-mappings",
        json={"external_name": external_name, "store_id": store_id},
    )
    assert resp.status_code in (200, 201, 204), resp.text


def test__ingest__rejects_missing_bearer(api):
    resp = requests.post(INGEST, json={"products": []})
    assert resp.status_code == 401, resp.text


def test__ingest__rejects_bad_bearer(api):
    resp = requests.post(INGEST, json={"products": []},
                         headers={"Authorization": "Bearer not-a-real-key"})
    assert resp.status_code == 401, resp.text


def test__ingest__rejects_disabled_key(api):
    sid, key = _mint_key()
    requests.patch(f"{SOURCES}/{sid}", json={"enabled": False})
    resp = _post_ingest(key, {"products": []})
    assert resp.status_code == 401, resp.text


def test__ingest__unknown_store_quarantines(api):
    """FU-190 — an unknown merchant name does NOT auto-create. The
    product record is skipped with `store_not_mapped`."""
    _sid, key = _mint_key()
    body = {
        "products": [{
            "ref": "p1",
            "name": "Brand X Oat Milk 1L",
            "store": "MysteryStore",
            "merchant_stockcode": "ABC123",
        }],
    }
    resp = _post_ingest(key, body)
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["skipped"] and result["skipped"][0]["reason"] == "store_not_mapped"
    assert not result["accepted"]


def test__ingest__roundtrip_after_store_mapping(api):
    """Map the store, push a product + offer, observe it appended."""
    sid, key = _mint_key()
    store_id = _seeded_store_id()
    _map_store(sid, "ExternalStoreName", store_id)

    body = {
        "products": [{
            "ref": "p1",
            "name": f"Brand X Oat Milk {uuid.uuid4().hex[:6]}",
            "store": "ExternalStoreName",
            "merchant_stockcode": uuid.uuid4().hex[:10],
        }],
        "offers": [{
            "product_ref": "p1",
            "price_now": 4.50,
            "price_was": 5.00,
            "observed_at": "2026-06-17T10:00:00+00:00",
        }],
    }
    resp = _post_ingest(key, body)
    assert resp.status_code == 200, resp.text
    result = resp.json()
    accepted_kinds = sorted(r["kind"] for r in result["accepted"])
    assert accepted_kinds == ["offer", "product"], result


def test__ingest__product_dedupe_by_stockcode_then_offer_appends(api):
    """Re-push the same product (same stockcode) → it dedupes; the
    new offer appends a new historic point."""
    sid, key = _mint_key()
    store_id = _seeded_store_id()
    _map_store(sid, "ExternalStore", store_id)
    stockcode = uuid.uuid4().hex[:10]

    first = _post_ingest(key, {
        "products": [{
            "ref": "p1",
            "name": "Same Product",
            "store": "ExternalStore",
            "merchant_stockcode": stockcode,
        }],
        "offers": [{
            "product_ref": "p1",
            "price_now": 3.00,
            "observed_at": "2026-06-17T10:00:00+00:00",
        }],
    })
    assert first.status_code == 200, first.text

    second = _post_ingest(key, {
        "products": [{
            "ref": "p1",
            "name": "Same Product",
            "store": "ExternalStore",
            "merchant_stockcode": stockcode,
        }],
        "offers": [{
            "product_ref": "p1",
            "price_now": 2.50,
            "observed_at": "2026-06-17T11:00:00+00:00",
        }],
    })
    assert second.status_code == 200, second.text
    result = second.json()
    # Product row is "updated" not "created" on the resend.
    product_acks = [r for r in result["accepted"] if r["kind"] == "product"]
    assert product_acks and "updated" in (product_acks[0].get("note") or "")
    # New offer accepted (different observed_at + price).
    offer_acks = [r for r in result["accepted"] if r["kind"] == "offer"]
    assert offer_acks, result


def test__ingest__duplicate_offer_skipped(api):
    """Same (product, observed_at, price_now) twice → second is
    deduped as `duplicate`, not appended."""
    sid, key = _mint_key()
    store_id = _seeded_store_id()
    _map_store(sid, "ExternalStore", store_id)

    stockcode = uuid.uuid4().hex[:10]
    base = {
        "products": [{
            "ref": "p1",
            "name": "Dup Test",
            "store": "ExternalStore",
            "merchant_stockcode": stockcode,
        }],
        "offers": [{
            "product_ref": "p1",
            "price_now": 9.99,
            "observed_at": "2026-06-17T12:00:00+00:00",
        }],
    }
    first = _post_ingest(key, base)
    assert first.status_code == 200, first.text

    second = _post_ingest(key, base)
    assert second.status_code == 200, second.text
    skipped = [r for r in second.json()["skipped"] if r["kind"] == "offer"]
    assert skipped and skipped[0]["reason"] == "duplicate"


def test__ingest__idempotency_key_replays_to_noop(api):
    sid, key = _mint_key()
    store_id = _seeded_store_id()
    _map_store(sid, "ExternalStore", store_id)
    idem = uuid.uuid4().hex

    body = {
        "products": [{
            "ref": "p1",
            "name": "Idem Test",
            "store": "ExternalStore",
            "merchant_stockcode": uuid.uuid4().hex[:10],
        }],
        "offers": [{
            "product_ref": "p1",
            "price_now": 1.00,
            "observed_at": "2026-06-17T13:00:00+00:00",
        }],
    }
    first = _post_ingest(key, body, idem=idem)
    assert first.status_code == 200, first.text
    assert first.json()["idempotent_replay"] is False
    assert len(first.json()["accepted"]) == 2

    second = _post_ingest(key, body, idem=idem)
    assert second.status_code == 200, second.text
    assert second.json()["idempotent_replay"] is True
    assert second.json()["accepted"] == []
    assert second.json()["skipped"] == []


def _insert_idempotency_row(source_id: str, key: str, *, expired: bool) -> None:
    """Plant an `IdempotencyKey` row directly — the only way to put a
    *past-TTL* row on file without waiting seven days."""
    from datetime import datetime, timedelta, timezone

    from dora_api.domain.entities.idempotency_key import IdempotencyKey

    now = datetime.now(timezone.utc)
    delta = -timedelta(days=1) if expired else timedelta(days=7)
    with app.app_context():
        repo = SqlAlchemyRepository()
        repo.add(IdempotencyKey(
            key=key,
            source_id=source_id,
            expires_at=now + delta,
            created_at=now - timedelta(days=8),
        ))
        repo.save_changes()


def _idempotency_rows(source_id: str, key: str) -> list:
    from dora_api.domain.entities.idempotency_key import IdempotencyKey

    with app.app_context():
        repo = SqlAlchemyRepository()
        field_key = EntityField(IdempotencyKey, IdempotencyKey.Fields.KEY)
        field_src = EntityField(IdempotencyKey, IdempotencyKey.Fields.SOURCE_ID)
        return repo.get(IdempotencyKey).all(field_key.eq(key) & field_src.eq(source_id))


def test__ingest__expired_idempotency_key_is_reprocessed_not_500(api):
    """Finalisation 16-R2 — a key past its 7-day TTL used to be let through
    *and then* re-inserted, which the unique `(source_id, key)` index rejected
    at commit: a 500 after the batch had been applied in the session, so the
    whole batch rolled back. A producer reusing a stable key (the companion's
    scheduler tick id) hit it a week after first use. The row is refreshed in
    place now and the batch lands."""
    sid, key = _mint_key()
    store_id = _seeded_store_id()
    _map_store(sid, "ExternalStore", store_id)
    idem = uuid.uuid4().hex
    _insert_idempotency_row(sid, idem, expired=True)

    resp = _post_ingest(key, {
        "products": [{
            "ref": "p1",
            "name": f"Stale Key {uuid.uuid4().hex[:6]}",
            "store": "ExternalStore",
            "merchant_stockcode": uuid.uuid4().hex[:10],
        }],
        "offers": [{
            "product_ref": "p1",
            "price_now": 2.00,
            "observed_at": "2026-06-17T10:00:00+00:00",
        }],
    }, idem=idem)
    assert resp.status_code == 200, resp.text
    assert resp.json()["idempotent_replay"] is False
    assert len(resp.json()["accepted"]) == 2, resp.text

    rows = _idempotency_rows(sid, idem)
    assert len(rows) == 1, "the expired row must be refreshed, not duplicated"
    expires = rows[0].expires_at
    from datetime import datetime, timezone
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    assert expires > datetime.now(timezone.utc)

    # And the refreshed key now short-circuits like any live key.
    replay = _post_ingest(key, {"products": [], "offers": []}, idem=idem)
    assert replay.status_code == 200 and replay.json()["idempotent_replay"] is True


def test__ingest__stamping_a_key_purges_expired_rows(api):
    """Finalisation 16-R3 — nothing ever deleted past-TTL rows, so the table
    grew by one row per keyed push forever. A keyed push now sweeps them."""
    sid, key = _mint_key()
    store_id = _seeded_store_id()
    _map_store(sid, "ExternalStore", store_id)
    stale_a, stale_b, live = uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex
    _insert_idempotency_row(sid, stale_a, expired=True)
    _insert_idempotency_row(sid, stale_b, expired=True)
    _insert_idempotency_row(sid, live, expired=False)

    resp = _post_ingest(key, {"products": [], "offers": []}, idem=uuid.uuid4().hex)
    assert resp.status_code == 200, resp.text

    assert _idempotency_rows(sid, stale_a) == []
    assert _idempotency_rows(sid, stale_b) == []
    assert len(_idempotency_rows(sid, live)) == 1, "a live key must survive the sweep"


def test__ingest__bad_record_does_not_fail_batch(api):
    """A bad record returns per-record `failed`, not a 4xx."""
    sid, key = _mint_key()
    store_id = _seeded_store_id()
    _map_store(sid, "ExternalStore", store_id)

    body = {
        "products": [{
            "ref": "p1",
            "name": "Good Product",
            "store": "ExternalStore",
            "merchant_stockcode": uuid.uuid4().hex[:10],
        }],
        "offers": [
            {
                "product_ref": "p1",
                "price_now": 2.00,
                "observed_at": "2026-06-17T10:00:00+00:00",
            },
            {
                "product_ref": "p-does-not-exist",
                "price_now": 3.00,
                "observed_at": "2026-06-17T10:00:00+00:00",
            },
        ],
    }
    resp = _post_ingest(key, body)
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert any(r["kind"] == "product" for r in result["accepted"])
    assert any(r["kind"] == "offer" for r in result["accepted"])
    assert any(
        r["kind"] == "offer" and r["reason"] == "product_unknown"
        for r in result["failed"]
    ), result


def test__ingest__pack_count_round_trips_on_product(api):
    """FU-232 — the multipack `pack_count` column (schema added with the
    FU-227 follow-up) is now accepted on `_ProductIn` and persisted on
    `Product.pack_count`. Re-pushing the same product with a different
    `pack_count` updates the row (additive: a NULL push doesn't clobber
    an existing value, matching the other `or existing.*` fields)."""
    sid, key = _mint_key()
    store_id = _seeded_store_id()
    _map_store(sid, "MultipackStore", store_id)

    stockcode = uuid.uuid4().hex[:10]
    name = f"Activia 4-pack {uuid.uuid4().hex[:6]}"
    body = {
        "products": [{
            "ref": "p1",
            "name": name,
            "store": "MultipackStore",
            "merchant_stockcode": stockcode,
            "size_value": 500.0,    # total across the bundle
            "size_unit": "g",
            "pack_count": 4,
        }],
    }
    resp = _post_ingest(key, body)
    assert resp.status_code == 200, resp.text
    assert resp.json()["accepted"][0]["kind"] == "product", resp.text

    with app.app_context():
        repo = SqlAlchemyRepository()
        stockcode_field = EntityField(Product, Product.Fields.MERCHANT_STOCKCODE)
        rows = repo.get(Product).all(stockcode_field.eq(stockcode))
        assert len(rows) == 1, rows
        assert rows[0].pack_count == 4
        assert rows[0].size_value == 500.0

    # Push the same product again with no pack_count — the existing
    # value sticks (matches `existing.pack_count or existing.pack_count`).
    body_no_pack = {
        "products": [{
            "ref": "p1",
            "name": name,
            "store": "MultipackStore",
            "merchant_stockcode": stockcode,
        }],
    }
    resp = _post_ingest(key, body_no_pack)
    assert resp.status_code == 200, resp.text
    with app.app_context():
        repo = SqlAlchemyRepository()
        stockcode_field = EntityField(Product, Product.Fields.MERCHANT_STOCKCODE)
        rows = repo.get(Product).all(stockcode_field.eq(stockcode))
        assert rows[0].pack_count == 4

    # And rejects a non-positive pack_count (Field(gt=0)).
    body_bad = {
        "products": [{
            "ref": "p1",
            "name": f"bad {uuid.uuid4().hex[:6]}",
            "store": "MultipackStore",
            "pack_count": 0,
        }],
    }
    resp = _post_ingest(key, body_bad)
    assert resp.status_code == 400, resp.text


def test__ingest__rejects_price_observations_field(api):
    """FU-227 chunk 7 (J1) — observations are in-app input only; the producer
    path was removed. A payload still sending `price_observations[]` is
    rejected by `extra="forbid"` (400) before any record is processed. This
    pins the contract removal so a future agent can't quietly re-add the
    field without revisiting Idea A."""
    _, key = _mint_key()
    body = {
        "products": [],
        "offers": [],
        "price_observations": [{
            "product_ref": "p1",
            "price": 1.00,
            "observed_at": "2026-06-17T10:00:00+00:00",
        }],
    }
    resp = _post_ingest(key, body)
    assert resp.status_code == 400, resp.text
    # Structured per-field errors from the request middleware — the same shape
    # every route answers with (finalisation 16-R9 / 16-R34); it used to be
    # one concatenated `str(ValidationError)`.
    errors = resp.json()["errors"]
    assert "price_observations" in errors, resp.text
    assert errors["price_observations"][0]["code"] == "extra_forbidden", resp.text


def test__ingest__product_image_round_trips_and_serves(api):
    """Owner 2026-10-17 — a product saved from the companion arrives with its
    picture. `image` is a data URL stored on the product and served by
    `GET /products/<id>/image`; a later push replaces it, a push without one
    leaves it, and one that isn't a data URL is dropped without failing the
    record."""
    import base64

    sid, key = _mint_key()
    store_id = _seeded_store_id()
    _map_store(sid, "ImageStore", store_id)

    png = b"\x89PNG\r\n\x1a\n" + b"first"
    stockcode = uuid.uuid4().hex[:10]
    product = {
        "ref": "p1",
        "name": f"Pictured {uuid.uuid4().hex[:6]}",
        "store": "ImageStore",
        "merchant_stockcode": stockcode,
        "image": "data:image/png;base64," + base64.b64encode(png).decode(),
    }
    resp = _post_ingest(key, {"products": [product]})
    assert resp.status_code == 200, resp.text
    product_id = resp.json()["accepted"][0]["id"]

    served = requests.get(f"{BASE}/products/{product_id}/image")
    assert served.status_code == 200, served.text
    assert served.headers["Content-Type"].startswith("image/png")
    assert served.content == png

    # No image on a re-push: the stored one stays.
    resp = _post_ingest(key, {"products": [{**product, "image": None}]})
    assert resp.status_code == 200, resp.text
    assert requests.get(f"{BASE}/products/{product_id}/image").content == png

    # Not a data URL: dropped, the record still accepted, the image unchanged.
    resp = _post_ingest(key, {"products": [{**product, "image": "https://cdn.example/x.png"}]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["accepted"][0]["kind"] == "product"
    assert requests.get(f"{BASE}/products/{product_id}/image").content == png

    # A new picture replaces the old one.
    jpeg = b"\xff\xd8\xff" + b"second"
    replaced = {**product, "image": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}
    resp = _post_ingest(key, {"products": [replaced]})
    assert resp.status_code == 200, resp.text
    served = requests.get(f"{BASE}/products/{product_id}/image")
    assert served.headers["Content-Type"].startswith("image/jpeg")
    assert served.content == jpeg

    # The product list reports it, which is what My products keys the thumb on.
    listed = requests.get(
        f"{BASE}/products", params={"filter": f"product_id:eq:{product_id}"},
    ).json()["items"]
    assert len(listed) == 1 and listed[0]["has_image"] is True, listed


def test__ingest__a_cheaper_second_offer_reads_as_a_new_low(api):
    """The history holds every pushed price, the current one included, so the
    price-drops report has to compare against points *before* the current
    offer; taking the low over all of it meant no ingested product could ever
    be a new low."""
    sid, key = _mint_key()
    _map_store(sid, "DropStore", _seeded_store_id())
    stockcode = uuid.uuid4().hex[:10]
    product = {"ref": "p1", "name": f"Drop test {stockcode}", "store": "DropStore",
               "merchant_stockcode": stockcode}
    for price, when in ((10.0, "2026-06-01T10:00:00+00:00"), (8.0, "2026-06-08T10:00:00+00:00")):
        resp = _post_ingest(key, {"products": [product], "offers": [{
            "product_ref": "p1", "price_now": price, "price_was": 12.0, "observed_at": when,
        }]})
        assert resp.status_code == 200, resp.text

    rows = requests.get(f"{BASE}/reports/price-drops", params={"limit": 20}).json()["rows"]
    row = next(r for r in rows if r["name"] == product["name"])
    assert row["price_now"] == 8.0
    assert row["previous_low"] == 10.0
