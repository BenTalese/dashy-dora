"""P6-01 Chunk 7 — planned_shop_date persistence + DTO exposure.

A list can be created with an ISO planned_shop_date, the value round-trips through
the summary + detail DTOs, PATCH can change it, and PATCH with explicit `null`
clears it.
"""
from datetime import date

import requests

from dora_api.domain.locale_format import format_list_label

SHOPPING_LISTS = "http://localhost:5170/api/shopping-lists"


def _create(payload: dict) -> str:
    resp = requests.post(SHOPPING_LISTS, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["shopping_list_id"]


def _detail(list_id: str) -> dict:
    resp = requests.get(f"{SHOPPING_LISTS}/{list_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _patch(list_id: str, payload: dict) -> None:
    resp = requests.patch(f"{SHOPPING_LISTS}/{list_id}", json=payload)
    assert resp.status_code == 204, resp.text


def _cleanup(list_id: str) -> None:
    requests.delete(f"{SHOPPING_LISTS}/{list_id}")


def test_create_with_planned_shop_date_roundtrips_through_dtos():
    list_id = _create({"name": "Chunk 7 create", "planned_shop_date": "2026-07-01"})
    try:
        detail = _detail(list_id)
        assert detail["planned_shop_date"] == "2026-07-01"
        # Summary DTO also exposes it.
        all_lists = requests.get(SHOPPING_LISTS).json()
        summary = next(s for s in all_lists if s["shopping_list_id"] == list_id)
        assert summary["planned_shop_date"] == "2026-07-01"
    finally:
        _cleanup(list_id)


def test_create_without_planned_shop_date_defaults_null():
    list_id = _create({"name": "Chunk 7 no date"})
    try:
        detail = _detail(list_id)
        assert detail["planned_shop_date"] is None
    finally:
        _cleanup(list_id)


def test_patch_sets_and_clears_planned_shop_date():
    list_id = _create({"name": "Chunk 7 patch"})
    try:
        assert _detail(list_id)["planned_shop_date"] is None

        _patch(list_id, {"planned_shop_date": "2026-08-15"})
        assert _detail(list_id)["planned_shop_date"] == "2026-08-15"

        # Explicit null clears.
        _patch(list_id, {"planned_shop_date": None})
        assert _detail(list_id)["planned_shop_date"] is None
    finally:
        _cleanup(list_id)


def test_patch_without_planned_shop_date_field_does_not_touch_it():
    # Set a date, then PATCH something else — the date must survive.
    list_id = _create({"name": "Chunk 7 preserve", "planned_shop_date": "2026-09-01"})
    try:
        _patch(list_id, {"name": "Chunk 7 renamed"})
        detail = _detail(list_id)
        assert detail["name"] == "Chunk 7 renamed"
        assert detail["planned_shop_date"] == "2026-09-01"
    finally:
        _cleanup(list_id)


def test_display_name_follows_the_name_then_date_ladder():
    """FU-165 L509 — server-owned `display_name` (R-003): a custom name wins;
    clearing it self-labels from the planned shop date; changing the shop day
    re-labels; clearing the date too falls back to a non-empty creation-date
    label. Dates are in a far year so the label carries the year and reads
    the same whatever the run day (en-AU, the seeded household locale)."""
    d1 = date(2030, 3, 15)
    list_id = _create({"name": "Weekly big shop", "planned_shop_date": d1.isoformat()})
    try:
        # Custom name wins over the date.
        assert _detail(list_id)["display_name"] == "Weekly big shop"

        # Clear the name → self-labels from the planned shop date.
        _patch(list_id, {"name": None})
        assert _detail(list_id)["display_name"] == format_list_label(d1, date.today(), "en-AU")

        # Change the shop day → re-labels.
        d2 = date(2030, 12, 24)
        _patch(list_id, {"planned_shop_date": d2.isoformat()})
        assert _detail(list_id)["display_name"] == format_list_label(d2, date.today(), "en-AU")

        # Clear the date too (name still cleared) → non-empty creation-date
        # fallback (exact value is a UTC/local edge — assert it's present).
        _patch(list_id, {"planned_shop_date": None})
        assert _detail(list_id)["display_name"]
    finally:
        _cleanup(list_id)
