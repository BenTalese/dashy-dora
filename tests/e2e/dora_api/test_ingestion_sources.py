"""C-10.1 — admin CRUD over `IngestionSource` (PROPOSAL_INGESTION_API §2.1).

Covers the admin "API access" page contract:
- create returns the raw key exactly once, never again
- list/patch/delete round-trip via the dataclass DTO
- patching toggles enabled / relabels
- delete revokes the credential

The bearer-auth side of the credential is pinned by `test_ingest_batch.py`
and friends; this file pins the admin surface only.
"""
import uuid

import requests

BASE = "http://localhost:5170/api"
SOURCES = f"{BASE}/ingestion-sources"


def _create(label: str | None = None) -> dict:
    payload = {"label": label or f"src-{uuid.uuid4().hex[:8]}"}
    resp = requests.post(SOURCES, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test__ingestion_sources__create_returns_raw_key_once(api):
    body = _create()
    assert "key" in body and body["key"], body
    assert "source" in body
    src = body["source"]
    # The raw key is NEVER in the source DTO — only handed back once on create.
    assert "key" not in src
    assert "key_hash" not in src
    assert src["enabled"] is True
    assert src["accepted_count"] == 0
    assert src["skipped_count"] == 0
    assert src["failed_count"] == 0
    assert src["last_used_at"] is None

    listed = requests.get(SOURCES).json()["items"]
    listing = next(it for it in listed if it["id"] == src["id"])
    # Confirm the listing never carries the raw key either.
    assert "key" not in listing


def test__ingestion_sources__patch_toggle_and_relabel(api):
    src = _create("before")["source"]
    sid = src["id"]

    renamed = requests.patch(f"{SOURCES}/{sid}", json={"label": "after"})
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["label"] == "after"

    disabled = requests.patch(f"{SOURCES}/{sid}", json={"enabled": False})
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["enabled"] is False


def test__ingestion_sources__delete_revokes(api):
    src = _create()["source"]
    sid = src["id"]

    resp = requests.delete(f"{SOURCES}/{sid}")
    assert resp.status_code == 204, resp.text

    # Subsequent ops on the deleted id 404.
    assert requests.patch(f"{SOURCES}/{sid}", json={"label": "x"}).status_code == 404
    assert requests.delete(f"{SOURCES}/{sid}").status_code == 404


def test__ingestion_sources__blank_label_rejected(api):
    resp = requests.post(SOURCES, json={"label": ""})
    assert resp.status_code == 400, resp.text


def test__ingestion_sources__bad_trust_rejected(api):
    resp = requests.post(SOURCES, json={"label": "x", "trust": "ultra"})
    assert resp.status_code == 400, resp.text
