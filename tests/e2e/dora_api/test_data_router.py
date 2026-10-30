"""End-to-end coverage for /api/data/backup* and /api/data/backups (library).

FU-342 retired the download-only `GET /api/data/backup` fast-path in
favour of the persistent library (`/api/data/backups` — plural). The
tests here `POST /backups` (create) + `GET /backups/<id>/download` to
land on a payload equivalent to what the old endpoint returned, then
assert on the payload's shape / restore round-trip / etc.

Inspect + restore endpoints (`/api/data/backup/inspect`,
`/api/data/backup/restore`) are unchanged — the library reuses the
same restore handler internally for the fast-path restore-from-saved
button, but the inspect + external-file restore endpoints remain as
before.
"""
import json
import uuid  # register_product_barcode tests used uuid without importing it.

import requests

from tests.e2e.dora_api._error_assertions import domain_err


LIBRARY_URL = "http://localhost:5170/api/data/backups"


def _create_backup(sections: list[str] | None = None) -> tuple[dict, dict]:
    """POST the library create endpoint, then GET the download so tests
    can assert on both the row + the payload shape. Returns (row, payload).

    Every test in this module that used to `requests.get(BACKUP_URL)` now
    threads through here — the payload assertions are exactly the ones
    the retired GET endpoint carried."""
    body = {} if sections is None else {"sections": sections}
    row_response = requests.post(LIBRARY_URL, json=body)
    row_response.raise_for_status()
    row = row_response.json()
    dl_response = requests.get(f"{LIBRARY_URL}/{row['backup_id']}/download")
    dl_response.raise_for_status()
    return row, dl_response.json()


def test__get_backup__happy_path__returns_attachment_with_expected_sections(api):
    row, payload = _create_backup()

    # Row-level metadata the library added
    assert row["status"] == "ready"
    assert row["trigger_kind"] == "manual"
    assert row["created_by_username"] == "dora"
    assert row["size_bytes"] > 0

    # The download response was pre-checked by _create_backup (raise_for_status
    # + content-disposition attachment is set inside send_file()); this test
    # focuses on the JSON body shape.

    # Metadata block
    assert payload["schema_version"] == 1
    assert isinstance(payload["exported_at"], str) and payload["exported_at"]
    assert payload["exported_by"] == "dora"  # set by tests/conftest login

    # Every in-scope section is present and a list, even when empty.
    expected_sections = {
        "stock_groups",
        "stock_levels",
        "stock_locations",
        "saved_products",
        "stock_items",
        "product_stock_item_links",
        "stock_item_substitutes",
        "shopping_lists",
        "shopping_list_items",
        "shopping_list_templates",
        "shopping_list_template_lines",
        "recipe_collections",
        "recipes",
        "recipe_ingredients",
        # `meals` + `meal_recipes` were removed by the meals→recipes
        # rework; `product_stock_item_links` (above) is now a real backup section.
        "meal_plans",
        "meal_plan_entries",
    }
    assert expected_sections.issubset(payload.keys())
    for section in expected_sections:
        assert isinstance(payload[section], list), f"{section} must be a list"

    # Stock levels are seeded by seed_dev_data, so this section should be
    # populated and every row should carry an id.
    assert len(payload["stock_levels"]) >= 1
    for row in payload["stock_levels"]:
        assert "id" in row
        assert row["id"]

    # Volatile / cached data is intentionally excluded.
    for excluded in (
        "users",
        "merchants",
        "product_offers",
        "product_historic_offers",
        "stock_level_changes",
        "notifications",
        "app_settings",
    ):
        assert excluded not in payload, f"{excluded} should not be in backup"


def test__get_backup__without_auth__is_unauthorized(api):
    # Bare requests.Session (no login) — we hit the URL directly without
    # going through the shared authenticated session that conftest set up.
    fresh = requests.Session()
    response = fresh.post(LIBRARY_URL, json={})
    assert response.status_code == 401


def test__get_backup__is_valid_json_document(api):
    _, payload = _create_backup()
    # Payload must be parseable on its own — i.e. saving it to disk and
    # reloading gives back the same shape. `_create_backup` already
    # round-tripped it through JSON on both ends; this test asserts the
    # invariant is preserved when it lands on disk.
    reparsed = json.loads(json.dumps(payload))
    assert reparsed["schema_version"] == 1
    assert "stock_items" in reparsed


# ── /inspect ───────────────────────────────────────────────────────────

INSPECT_URL = "http://localhost:5170/api/data/backup/inspect"
RESTORE_URL = "http://localhost:5170/api/data/backup/restore"


def test__inspect_backup__roundtrip__counts_match_and_seeds_flag_as_duplicates(api):
    _, backup = _create_backup()

    response = requests.post(INSPECT_URL, json=backup)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["schema_version"] == 1
    assert body["entity_counts"]["stock_levels"] == len(backup["stock_levels"])
    # The backup is a snapshot of the live DB, so every detectable row should
    # appear in `duplicates` for the sections that support detection.
    assert set(body["duplicates"].get("stock_levels", [])) == {
        row["name"] for row in backup["stock_levels"]
    }


def test__inspect_backup__future_schema__is_rejected(api):
    response = requests.post(INSPECT_URL, json={"schema_version": 9999})
    assert response.status_code == 400


def test__inspect_backup__missing_schema__is_rejected(api):
    response = requests.post(INSPECT_URL, json={"stock_items": []})
    assert response.status_code == 400


# ── /restore ───────────────────────────────────────────────────────────

def test__restore_backup__roundtrip_all_skip_duplicates__no_changes(api):
    """Re-importing the same file we just exported should change nothing —
    every row collides on its duplicate key and gets skipped."""
    _, backup = _create_backup()

    response = requests.post(
        RESTORE_URL,
        json={"backup": backup, "selection": {}, "mode": "all_skip_duplicates"},
    )
    assert response.status_code == 200, response.text
    summary = response.json()

    # No new rows; every section either skipped or stayed at zero (sub-tables
    # like links/lines may still get re-inserted if their parents weren't
    # detected as duplicates — but for an in-place re-import of a seed-only DB
    # all detected sections must report zero "created").
    for detected in ("stock_groups", "stock_levels", "stock_items"):
        assert summary["created"][detected] == 0, (
            f"{detected}: expected 0 created, got {summary['created'][detected]}"
        )


def test__restore_backup__partial_mode__restores_the_selected_row(api):
    """Finalisation 18-R1 — `mode=partial` used to raise `KeyError:
    'meal_recipes'` (500) before touching a row: the m2m ride-along loop
    kept a hand-written section name the meals→recipes rework had removed,
    and nothing exercised the partial branch. Back up, delete one stock
    item, restore just that item by id → it is back, nothing else changes."""
    _, backup = _create_backup()
    victim = backup["stock_items"][0]
    victim_id = victim["id"]

    deleted = requests.delete(f"http://localhost:5170/api/stock-items/{victim_id}")
    assert deleted.status_code in (200, 204), deleted.text

    response = requests.post(
        RESTORE_URL,
        json={
            "backup": backup,
            "selection": {"stock_items": [victim_id]},
            "mode": "partial",
        },
    )
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["created"]["stock_items"] == 1, summary
    # Only the picked row (plus whatever rode along for it) was touched —
    # the groups/levels it points at already existed, so nothing was pulled in.
    assert summary["created"]["stock_groups"] == 0
    assert summary["created"]["stock_levels"] == 0

    restored = requests.get(
        "http://localhost:5170/api/stock-items",
        params={"filter": f"stock_item_id:eq:{victim_id}"},
    )
    assert restored.status_code == 200, restored.text
    assert len(restored.json()["items"]) == 1, restored.text


def test__restore_backup__fk_policy_maps_name_only_live_sections_and_columns():
    """Finalisation 18-R1 / D6 — the FK policy maps in `restore_shared`
    (`HARD_FK_PULL_IN`, `SOFT_FK_NULLABLE`, `REQUIRED_FKS`, `CHILD_AUTO_INCLUDE`)
    must only reference sections that are in `SECTIONS` and columns that exist
    on their tables. `meal_plan_entries.meal_id` + the `meal_recipes` rows
    outlived the meals→recipes rework for months; this pins the class, not
    the instance. The module already asserts this at import — calling it
    again here makes the failure a named test rather than a collection error."""
    from dora_api.features.data.restore_backup import validate_fk_maps

    validate_fk_maps()


def test__backup_sections__catalogue_matches_restore_shared(api):
    """Finalisation 18-R2 / 18-R3 — the Backup page renders its section
    picker, restore tree and report from `GET /api/data/backup/sections`,
    never from a hand-copied list (the copy named `product_barcodes` and
    lacked nine sections). Pin the endpoint to the one catalogue."""
    from dora_api.features.data.restore_shared import SECTIONS

    response = requests.get("http://localhost:5170/api/data/backup/sections")
    assert response.status_code == 200, response.text
    rows = response.json()["sections"]

    assert [r["key"] for r in rows] == [s.backup_key for s in SECTIONS]
    by_key = {r["key"]: r for r in rows}
    for s in SECTIONS:
        row = by_key[s.backup_key]
        assert row["label"] == s.label
        assert row["category"] == s.category
        assert row["default_on"] is s.default_on
        assert row["sensitive"] is s.sensitive
        assert row["pickable"] is (s.duplicate_key_fn is not None)
    # The two facts the stale SPA mirror got wrong.
    assert "barcodes" in by_key and "product_barcodes" not in by_key
    assert {"recipe_steps", "cuisines", "categories", "tools", "dietary_tags"} <= set(by_key)
    # A default-selection create built from the catalogue is accepted.
    default_keys = [r["key"] for r in rows if r["default_on"]]
    created = requests.post(LIBRARY_URL, json={"sections": default_keys})
    assert created.status_code == 200, created.text
    assert set(created.json()["sections"]) == set(default_keys)


def test__restore_backup__future_schema__is_rejected(api):
    response = requests.post(
        RESTORE_URL,
        json={"backup": {"schema_version": 9999}, "selection": {}, "mode": "all_skip_duplicates"},
    )
    assert response.status_code == 400


def test__restore_backup__unknown_mode__is_rejected(api):
    response = requests.post(
        RESTORE_URL,
        json={"backup": {"schema_version": 1}, "selection": {}, "mode": "bogus"},
    )
    assert response.status_code == 400


# ── Section toggles ────────────────────────────────────────────────────

def test__get_backup__without_sections_query__defaults_to_core_data(api):
    _, payload = _create_backup()
    # Core sections always present.
    assert "stock_items" in payload
    assert "recipes" in payload
    # Optional sections off by default.
    assert "app_settings" not in payload
    assert "users" not in payload
    assert "product_historic_offers" not in payload
    # The dump records what it carried so the restore step can be honest.
    assert "stock_items" in payload["sections"]
    assert "users" not in payload["sections"]


def test__get_backup__with_sections_query__narrows_dump(api):
    _, payload = _create_backup(sections=["stock_items", "stock_groups"])
    assert "stock_items" in payload
    assert "stock_groups" in payload
    assert "recipes" not in payload
    assert "shopping_lists" not in payload
    assert set(payload["sections"]) == {"stock_items", "stock_groups"}


def test__get_backup__with_optional_sections__includes_them(api):
    _, payload = _create_backup(
        sections=["app_settings", "users", "product_historic_offers"],
    )
    assert "app_settings" in payload
    assert "users" in payload
    assert "product_historic_offers" in payload


def test__get_backup__never_exports_password_hashes(api):
    _, payload = _create_backup(sections=["users"])
    for row in payload["users"]:
        assert "password_hash" not in row, "password_hash must never round-trip"


def test__get_backup__unknown_section__is_rejected(api):
    response = requests.post(
        LIBRARY_URL,
        json={"sections": ["stock_items", "nonsense"]},
    )
    assert response.status_code == 400


# ── Chunked uploads + staged inspect/restore ───────────────────────────

UPLOAD_START_URL = "http://localhost:5170/api/data/uploads/start"
UPLOAD_CHUNK_URL = "http://localhost:5170/api/data/uploads/chunk"
UPLOAD_FINISH_URL = "http://localhost:5170/api/data/uploads/finish"


def _upload_via_chunks(payload: dict, chunk_size: int = 64 * 1024) -> str:
    """Helper — drive a backup payload through the chunked-upload flow
    and return the resulting upload_id."""
    raw = json.dumps(payload).encode("utf-8")

    start = requests.post(UPLOAD_START_URL, json={"expected_size": len(raw)})
    assert start.status_code == 200, start.text
    upload_id = start.json()["upload_id"]

    for offset in range(0, len(raw), chunk_size):
        chunk = raw[offset:offset + chunk_size]
        response = requests.post(
            UPLOAD_CHUNK_URL,
            data={"upload_id": upload_id, "offset": str(offset)},
            files={"chunk": ("chunk.bin", chunk, "application/octet-stream")},
        )
        assert response.status_code == 200, response.text

    finish = requests.post(UPLOAD_FINISH_URL, json={"upload_id": upload_id})
    assert finish.status_code == 200, finish.text
    assert finish.json()["size"] == len(raw)
    return upload_id


def test__chunked_upload__inspect_via_upload_id__roundtrip(api):
    _, backup = _create_backup()
    upload_id = _upload_via_chunks(backup)

    response = requests.post(
        "http://localhost:5170/api/data/backup/inspect",
        json={"upload_id": upload_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema_version"] == 1
    assert body["entity_counts"]["stock_levels"] == len(backup["stock_levels"])
    # Sample rows surfaced for the SPA's tree view.
    assert "samples" in body
    assert body["samples"]["stock_levels"]["rows"]


def test__chunked_upload__chunk_offset_mismatch__is_400(api):
    start = requests.post(UPLOAD_START_URL, json={})
    upload_id = start.json()["upload_id"]
    # Send a chunk at the wrong offset.
    response = requests.post(
        UPLOAD_CHUNK_URL,
        data={"upload_id": upload_id, "offset": "99"},
        files={"chunk": ("c.bin", b"abc", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert response.json()["errors"]["received"] == [domain_err("0")]


def test__chunked_upload__abort_deletes_staged_file(api):
    start = requests.post(UPLOAD_START_URL, json={}).json()
    upload_id = start["upload_id"]
    response = requests.delete(f"http://localhost:5170/api/data/uploads/{upload_id}")
    assert response.status_code == 204
    # Re-aborting is harmless (DELETE is idempotent).
    response = requests.delete(f"http://localhost:5170/api/data/uploads/{upload_id}")
    assert response.status_code == 204


def test__restore_backup__via_upload_id__no_changes_on_roundtrip(api):
    _, backup = _create_backup()
    upload_id = _upload_via_chunks(backup)

    response = requests.post(
        RESTORE_URL,
        json={"upload_id": upload_id, "selection": {}, "mode": "all_skip_duplicates"},
    )
    assert response.status_code == 200, response.text
    summary = response.json()
    for detected in ("stock_groups", "stock_levels", "stock_items"):
        assert summary["created"][detected] == 0


def test__restore_backup__upload_id_consumed_on_use(api):
    _, backup = _create_backup()
    upload_id = _upload_via_chunks(backup)
    # First restore consumes the staged file…
    requests.post(
        RESTORE_URL,
        json={"upload_id": upload_id, "selection": {}, "mode": "all_skip_duplicates"},
    )
    # …so a second call referencing the same id is a 404 — the staged upload
    # is a resource that no longer exists (finalisation 18-R11; it was a 400
    # keyed on the message prefix).
    second = requests.post(
        RESTORE_URL,
        json={"upload_id": upload_id, "selection": {}, "mode": "all_skip_duplicates"},
    )
    assert second.status_code == 404


def test__restore_backup__rejects_both_inputs(api):
    response = requests.post(
        RESTORE_URL,
        json={
            "backup": {"schema_version": 1},
            "upload_id": "00000000-0000-0000-0000-000000000000",
            "selection": {},
            "mode": "all_skip_duplicates",
        },
    )
    assert response.status_code == 400


# ── Spreadsheet import (N3) ────────────────────────────────────────────

IMPORT_INSPECT_URL = "http://localhost:5170/api/data/import/spreadsheet/inspect"
IMPORT_COMMIT_URL = "http://localhost:5170/api/data/import/spreadsheet/commit"


def _stage_bytes(raw: bytes) -> str:
    """Push raw bytes through the chunked upload stack and return upload_id."""
    start = requests.post(UPLOAD_START_URL, json={"expected_size": len(raw)})
    upload_id = start.json()["upload_id"]
    requests.post(
        UPLOAD_CHUNK_URL,
        data={"upload_id": upload_id, "offset": "0"},
        files={"chunk": ("c.bin", raw, "application/octet-stream")},
    )
    requests.post(UPLOAD_FINISH_URL, json={"upload_id": upload_id})
    return upload_id


def test__spreadsheet_import__csv_happy_path__creates_rows(api):
    csv = (
        "Item,Status,Where,Group,Best before,Essential?\n"
        "TestImport-Alpha,Low,Pantry,Baking,2027-01-15,yes\n"
        "TestImport-Beta,Stocked,Pantry,,2026-12-31,\n"
        "TestImport-Gamma,Out of stock,,,,no\n"
    ).encode("utf-8")
    upload_id = _stage_bytes(csv)

    inspect = requests.post(IMPORT_INSPECT_URL, json={
        "upload_id": upload_id, "filename": "items.csv",
    })
    assert inspect.status_code == 200, inspect.text
    inspect_body = inspect.json()
    assert "items.csv" in inspect_body["sheets"]
    assert inspect_body["auto_mapping"]["items.csv"]["name"] == "Item"
    assert inspect_body["auto_mapping"]["items.csv"]["level"] == "Status"

    commit = requests.post(IMPORT_COMMIT_URL, json={
        "upload_id": upload_id,
        "filename": "items.csv",
        "sheet": "items.csv",
        "column_map": inspect_body["auto_mapping"]["items.csv"],
        "options": {
            "skip_duplicates": True,
            "create_missing_locations": True,
            "create_missing_groups": True,
            "halt_on_error": False,
        },
    })
    assert commit.status_code == 200, commit.text
    summary = commit.json()["summary"]
    assert summary["created"] == 3
    assert summary["errors"] == 0


def test__spreadsheet_import__bad_level_value__per_row_error(api):
    csv = (
        "Item,Status\n"
        "TestImport-BadLevelRow,not-a-real-level\n"
    ).encode("utf-8")
    upload_id = _stage_bytes(csv)

    inspect = requests.post(IMPORT_INSPECT_URL, json={
        "upload_id": upload_id, "filename": "x.csv",
    }).json()

    commit = requests.post(IMPORT_COMMIT_URL, json={
        "upload_id": upload_id,
        "filename": "x.csv",
        "sheet": "x.csv",
        "column_map": inspect["auto_mapping"]["x.csv"],
        "options": {
            "skip_duplicates": True,
            "create_missing_locations": False,
            "create_missing_groups": False,
            "halt_on_error": False,
        },
    })
    assert commit.status_code == 200, commit.text
    body = commit.json()
    assert body["summary"]["created"] == 0
    assert body["summary"]["errors"] == 1
    bad_row = body["rows"][0]
    assert bad_row["status"] == "error"
    assert bad_row["row_number"] == 2
    assert "isn't recognised" in (bad_row["reason"] or "")


def test__spreadsheet_import__blank_level_defaults_to_stocked(api):
    # 3-band collapse (DORA_VERIFY L879) — a mapped Level column with a blank
    # cell defaults the item to Stocked (was "Sufficient Stock" pre-2026-07-02),
    # and the three canonical labels land on their own bands. Asserts the
    # *created items' actual levels*, not just the row summary.
    csv = (
        "Item,Status\n"
        "TestImport-BlankLevel,\n"
        "TestImport-LevelStocked,Stocked\n"
        "TestImport-LevelLow,Low\n"
        "TestImport-LevelOut,Out of stock\n"
    ).encode("utf-8")
    upload_id = _stage_bytes(csv)
    inspect = requests.post(IMPORT_INSPECT_URL, json={
        "upload_id": upload_id, "filename": "levels.csv",
    }).json()

    commit = requests.post(IMPORT_COMMIT_URL, json={
        "upload_id": upload_id,
        "filename": "levels.csv",
        "sheet": "levels.csv",
        "column_map": inspect["auto_mapping"]["levels.csv"],
        "options": {
            "skip_duplicates": True,
            "create_missing_locations": False,
            "create_missing_groups": False,
            "halt_on_error": False,
        },
    })
    assert commit.status_code == 200, commit.text
    summary = commit.json()["summary"]
    assert summary["created"] == 4
    assert summary["errors"] == 0

    def _sequence_of(name: str) -> int:
        items = requests.get(
            f"http://localhost:5170/api/stock-items?filter=name:eq:{name}"
        ).json()["items"]
        assert len(items) == 1, name
        return items[0]["stock_level_sequence"]

    assert _sequence_of("TestImport-BlankLevel") == 0    # blank → Stocked
    assert _sequence_of("TestImport-LevelStocked") == 0
    assert _sequence_of("TestImport-LevelLow") == 1
    assert _sequence_of("TestImport-LevelOut") == 2


def test__spreadsheet_import__halt_on_error__rolls_everything_back(api):
    csv = (
        "Item,Status\n"
        "TestImport-Halt-Good,Low\n"
        "TestImport-Halt-Bad,not-a-real-level\n"
        "TestImport-Halt-AlsoGood,Low\n"
    ).encode("utf-8")
    upload_id = _stage_bytes(csv)
    inspect = requests.post(IMPORT_INSPECT_URL, json={
        "upload_id": upload_id, "filename": "h.csv",
    }).json()

    commit = requests.post(IMPORT_COMMIT_URL, json={
        "upload_id": upload_id,
        "filename": "h.csv",
        "sheet": "h.csv",
        "column_map": inspect["auto_mapping"]["h.csv"],
        "options": {
            "skip_duplicates": True,
            "create_missing_locations": False,
            "create_missing_groups": False,
            "halt_on_error": True,
        },
    })
    assert commit.status_code == 200, commit.text
    summary = commit.json()["summary"]
    assert summary["halted"] == 1
    assert summary["created"] == 0


def test__spreadsheet_import__commit_without_name_column__is_rejected(api):
    csv = b"Item,Status\nfoo,Low\n"
    upload_id = _stage_bytes(csv)
    requests.post(IMPORT_INSPECT_URL, json={
        "upload_id": upload_id, "filename": "n.csv",
    })

    response = requests.post(IMPORT_COMMIT_URL, json={
        "upload_id": upload_id,
        "filename": "n.csv",
        "sheet": "n.csv",
        "column_map": {"name": None, "level": "Status"},
        "options": {},
    })
    assert response.status_code == 400


# ── Import template download (FU-347 — BOM for Excel-on-Windows) ───────

def test__import_template__csv_download__starts_with_utf8_bom(api):
    """FU-347 — the downloaded template CSV must start with the UTF-8
    BOM so Excel-on-Windows opens it in UTF-8 instead of guessing
    ANSI/CP-1252. Without the BOM, any accented character in a future
    example row / header renders as mojibake in Excel."""
    response = requests.get(
        "http://localhost:5170/api/data/import/templates/stock_items.csv"
    )
    assert response.status_code == 200, response.text
    body = response.content
    assert body.startswith(b"\xef\xbb\xbf"), (
        "Template CSV must begin with the UTF-8 BOM (0xEF 0xBB 0xBF); "
        f"got first bytes {body[:8]!r}"
    )


def test__import_template__example_cells_line_up_with_headers(api):
    """FU-350 — the example row is now keyed by field name and projected
    through `headers` at write time. Reordering / renaming / adding a
    target field can no longer silently misalign example cells under the
    wrong headers. Contract: for the shipping stock_items template each
    non-empty example cell reads sensibly for its column (Rice under
    `name`, `In stock` under `level`, etc.)."""
    import csv as _csv
    response = requests.get(
        "http://localhost:5170/api/data/import/templates/stock_items.csv"
    )
    assert response.status_code == 200, response.text
    body = response.content
    if body.startswith(b"\xef\xbb\xbf"):
        body = body[3:]
    reader = _csv.reader(body.decode("utf-8").splitlines())
    rows = list(reader)
    assert len(rows) >= 2, f"Expected header + example row, got {rows!r}"
    header, example = rows[0], rows[1]
    assert len(header) == len(example), (
        f"Header ({len(header)} cells) and example ({len(example)} cells) "
        f"drifted apart: {header!r} vs {example!r}"
    )
    zipped = dict(zip(header, example))
    # Spot-check the fields that today's shipping template populates —
    # each cell reads sensibly for its column. If a future refactor
    # reorders TARGET_FIELDS or renames a column, the misalignment would
    # surface here (e.g. `expiry`'s example date landing under
    # `is_essential`) instead of shipping to users.
    assert zipped.get("name") == "Rice", f"name column got {zipped!r}"
    assert zipped.get("level") == "In stock", f"level column got {zipped!r}"
    assert zipped.get("location") == "Pantry", f"location column got {zipped!r}"
    assert zipped.get("group") == "Grains", f"group column got {zipped!r}"
    assert zipped.get("expiry") == "2027-01-01", f"expiry column got {zipped!r}"
    assert zipped.get("is_essential") == "no", f"is_essential column got {zipped!r}"


def test__import_template__csv_download__includes_hash_comment_row(api):
    """FU-349 (option A) — the downloaded template ships with an inline
    `#`-prefixed hint row explaining that the example values are
    illustrative, so users who never saw the FU know their install's
    actual level/location/group names may not match the placeholders.
    Emitting the row is the whole point of the option-A fix; without
    this assertion a future refactor could silently drop it and the
    user-facing hint would disappear."""
    response = requests.get(
        "http://localhost:5170/api/data/import/templates/stock_items.csv"
    )
    assert response.status_code == 200, response.text
    body = response.content
    # Strip the BOM to compare cleanly.
    if body.startswith(b"\xef\xbb\xbf"):
        body = body[3:]
    text = body.decode("utf-8")
    # FU-559 — parse via csv.reader before checking for the `#`. The comment
    # row contains a comma ("replace them, and use…"), so csv.writer quotes
    # the whole field — the *raw* line starts with `"`, not `#`. What matters
    # (and what `_strip_comment_rows` keys off on re-upload) is the parsed
    # first cell, which csv un-quotes back to `# …`. Checking the raw line
    # would wrongly fail on any comment row that happens to contain a comma.
    import csv as _csv
    rows = [row for row in _csv.reader(text.splitlines()) if row]
    assert any(str(row[0]).startswith("#") for row in rows), (
        "Template CSV must include a #-prefixed hint row explaining "
        f"that example values are illustrative; got: {rows!r}"
    )


def test__import_template__hash_comment_row__stripped_on_reupload(api):
    """FU-349 (option A) — round-trip: the `#` hint row we ship in the
    template must be filtered by the parser on re-upload so a user who
    doesn't delete it doesn't accidentally import a stock item named
    "# example values are illustrative…". Uses /inspect (not commit) so
    the test doesn't leave state behind — the `preview_rows` reflects
    exactly the rows the commit path would process."""
    response = requests.get(
        "http://localhost:5170/api/data/import/templates/stock_items.csv"
    )
    assert response.status_code == 200, response.text
    upload_id = _stage_bytes(response.content)

    inspect = requests.post(IMPORT_INSPECT_URL, json={
        "upload_id": upload_id, "filename": "stock_items.csv",
    })
    assert inspect.status_code == 200, inspect.text
    inspect_body = inspect.json()
    preview = inspect_body["preview_rows"]["stock_items.csv"]
    # Every previewed row's first cell must NOT start with `#`. The header
    # row is separated in the response envelope (via `sheets`), so preview
    # is data-only; a leaked `#` row here would be a real regression.
    for row in preview:
        first = row[0] if row else ""
        assert not str(first or "").startswith("#"), (
            f"Comment row leaked into preview_rows: {row!r}"
        )


def test__import_template__csv_download__body_after_bom_parses(api):
    """The BOM is only for Excel — server-side parsers (including our
    own upload path) must still be able to consume the file. Round-trip
    the downloaded template through the chunked-upload + inspect stack
    to prove the BOM doesn't wedge the parser."""
    response = requests.get(
        "http://localhost:5170/api/data/import/templates/stock_items.csv"
    )
    assert response.status_code == 200, response.text
    body = response.content
    # Sanity — BOM present + non-empty CSV payload after it.
    assert body[:3] == b"\xef\xbb\xbf"
    assert len(body) > 3

    upload_id = _stage_bytes(body)
    inspect = requests.post(IMPORT_INSPECT_URL, json={
        "upload_id": upload_id, "filename": "stock_items.csv",
    })
    assert inspect.status_code == 200, inspect.text
    inspect_body = inspect.json()
    # The parser strips the BOM before decoding, so the auto-mapper's
    # `name` column resolves cleanly instead of collating a `"﻿name"`
    # header that no target field can match.
    auto = inspect_body["auto_mapping"]["stock_items.csv"]
    assert auto["name"] is not None, (
        f"Auto-mapper couldn't identify the name column after BOM strip: {auto!r}"
    )
    # Belt-and-braces — the mapped header itself doesn't carry a
    # leading BOM character.
    assert not auto["name"].startswith("﻿"), (
        f"BOM leaked into the mapped name-column header: {auto['name']!r}"
    )


def test__import_templates__section_registry_is_symmetric():
    """FU-348 — the set of sections the commit handler accepts and the set
    of sections that ship a downloadable template must stay identical.
    FU-350 pinned one direction (a template with no commit path fails to
    boot); FU-348 adds the reverse (a commit-known section with no template
    fails to boot). Either drift would already crash the API at import via
    `_validate_import_templates`, so this is a fast, monkeypatch-free
    documentation of the invariant — if it fails, someone added a section
    to one registry without the other."""
    from dora_api.features.data.import_spreadsheet import (
        IMPORT_TEMPLATES_BY_SECTION,
        _COMMIT_KNOWN_SECTIONS,
    )
    assert set(_COMMIT_KNOWN_SECTIONS) == set(IMPORT_TEMPLATES_BY_SECTION), (
        "Importable sections and downloadable templates drifted apart. "
        f"commit-known={sorted(_COMMIT_KNOWN_SECTIONS)}, "
        f"templates={sorted(IMPORT_TEMPLATES_BY_SECTION)}. Every section the "
        "importer accepts must ship a template, and vice-versa."
    )


# ── Export & Print (N4) ────────────────────────────────────────────────

def _first_seeded_shopping_list_id() -> str:
    response = requests.get("http://localhost:5170/api/shopping-lists")
    assert response.status_code == 200, response.text
    summaries = response.json()
    assert summaries, "seed should provide at least one shopping list"
    return summaries[0]["shopping_list_id"]


def _first_seeded_recipe_id() -> str:
    response = requests.get("http://localhost:5170/api/recipes")
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert items, "the seed ships recipes"
    return items[0]["recipe_id"]


def test__shopping_list_export_csv__endpoint_removed(api):
    # UX-v2 (§12 Q1): shopping-list CSV export was removed app-wide — print
    # is the only list export. The whole /export route is gone, not just the
    # csv format.
    list_id = _first_seeded_shopping_list_id()
    response = requests.get(
        f"http://localhost:5170/api/shopping-lists/{list_id}/export?format=csv",
    )
    assert response.status_code == 404


def test__shopping_list_print_view__returns_html_with_list_name(api):
    list_id = _first_seeded_shopping_list_id()
    detail = requests.get(
        f"http://localhost:5170/api/shopping-lists/{list_id}",
    ).json()
    response = requests.get(
        f"http://localhost:5170/api/shopping-lists/{list_id}/print-view",
    )
    assert response.status_code == 200, response.text
    assert response.headers["Content-Type"].startswith("text/html")
    # display_name, not name — name is nullable now (UX-v2 self-labelled
    # lists) and the print view renders the resolved label.
    assert detail["display_name"] in response.text
    # @media print stylesheet is embedded inline.
    assert "@media print" in response.text


def test__recipe_export_csv__returns_csv_when_recipes_exist(api):
    recipe_id = _first_seeded_recipe_id()
    response = requests.get(
        f"http://localhost:5170/api/recipes/{recipe_id}/export?format=csv",
    )
    assert response.status_code == 200, response.text
    assert response.headers["Content-Type"].startswith("text/csv")
    header_line = response.text.splitlines()[0]
    for col in ("ingredient", "quantity", "unit", "notes", "location"):
        assert col in header_line


def test__recipe_print_view__returns_html_with_recipe_name(api):
    recipe_id = _first_seeded_recipe_id()
    recipe = requests.get(
        f"http://localhost:5170/api/recipes/{recipe_id}",
    ).json()
    response = requests.get(
        f"http://localhost:5170/api/recipes/{recipe_id}/print-view",
    )
    assert response.status_code == 200, response.text
    assert response.headers["Content-Type"].startswith("text/html")
    assert recipe["name"] in response.text


# ── Barcodes & QR (N5) ─────────────────────────────────────────────────

LOOKUP_URL = "http://localhost:5170/api/data/barcodes/lookup"
REGISTER_URL = "http://localhost:5170/api/data/barcodes"
PRODUCTS_URL = "http://localhost:5170/api/products"
STOCK_ITEMS_URL = "http://localhost:5170/api/stock-items"


def _first_seeded_stock_item_id() -> str:
    response = requests.get(STOCK_ITEMS_URL)
    assert response.status_code == 200, response.text
    items = response.json().get("items") or []
    assert items, "seed should provide at least one stock item"
    return items[0]["stock_item_id"]


def test__stock_item_qr__returns_png(api):
    item_id = _first_seeded_stock_item_id()
    response = requests.get(f"{STOCK_ITEMS_URL}/{item_id}/qr")
    assert response.status_code == 200, response.text
    assert response.headers["Content-Type"] == "image/png"
    # PNG magic bytes — sanity-check we're returning a real image.
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"


def test__stock_item_qr__bad_size__is_400(api):
    item_id = _first_seeded_stock_item_id()
    response = requests.get(f"{STOCK_ITEMS_URL}/{item_id}/qr?size=10")
    assert response.status_code == 400


def _first_product_id() -> str:
    products = requests.get(PRODUCTS_URL).json().get("items") or []
    assert products, "seed data has no products"
    return products[0]["product_id"]


# per-test product index so each barcode-register test gets a
# fresh unbarcoded Product. The new `one Product = one EAN` rule means
# any test that registers against `products[0]` blocks the next from
# doing the same. Tests increment this counter at call sites.
_PRODUCT_INDEX = [0]


def _next_unused_product_id(*, requires_link: bool = False) -> str:
    """Yield product_ids round-robin from the seed so each barcode test
    starts with a Product that has no barcode registered yet. Each call
    advances by one regardless of seed size; consumers must take the
    head of the list slice they need.

    `requires_link=True` skips forward until the next Product has a
    linked StockItem — used by the traversal test, which needs the
    `stock_item_via_product` lookup kind."""
    products = requests.get(PRODUCTS_URL).json().get("items") or []
    assert products, "seed data has no products"
    while True:
        idx = _PRODUCT_INDEX[0]
        _PRODUCT_INDEX[0] = idx + 1
        assert idx < len(products), (
            f"barcode tests need more seed products (asked for #{idx}, have "
            f"{len(products)}). Bump the seed or release a product."
        )
        candidate = products[idx]
        if requires_link and not candidate.get("linked_stock_item_id"):
            continue
        return candidate["product_id"]
    return products[idx]["product_id"]


def test__dora_link_lookup__resolves_stock_item(api):
    # A real-world barcode identifies a Product, not a stock item. The only
    # path that resolves directly to a stock item is Dora's own QR link.
    item_id = _first_seeded_stock_item_id()
    dora_lookup = requests.get(
        f"{LOOKUP_URL}?value=dora://stock-item/{item_id}",
    )
    assert dora_lookup.status_code == 200, dora_lookup.text
    body = dora_lookup.json()
    assert body["kind"] == "stock_item"
    assert body["id"] == item_id


def test__register_barcode__against_product__lookup_traverses_via_product(api):
    """FU-056 — registering against a Product that's linked to a StockItem
    yields the `stock_item_via_product` lookup kind (the catalogue case).
    `product_no_link` only fires when the Product has zero linked items."""
    # `requires_link=True` — this test is about the *linked* traversal,
    # so the picked Product must have a StockItem attached. Bare
    # round-robin was flaky: it landed on a linked Product when the
    # test ran in isolation but on an unlinked one once earlier tests
    # advanced the counter past the linked seed rows.
    product_id = _next_unused_product_id(requires_link=True)
    barcode = f"TEST-{uuid.uuid4().hex[:10]}"

    register = requests.post(REGISTER_URL, json={
        "product_id": product_id,
        "barcode": barcode,
    })
    assert register.status_code == 200, register.text
    body = register.json()
    assert body["barcode"] == barcode
    assert body["product_id"] == product_id
    assert body["stock_item_id"] is None
    barcode_id = body["barcode_id"]

    lookup = requests.get(f"{LOOKUP_URL}?value={barcode}")
    assert lookup.status_code == 200, lookup.text
    lookup_body = lookup.json()
    # `UNIQUE(StockItemProduct.product_id)` guarantees that any linked
    # Product reaches exactly one StockItem — so the only possible
    # outcomes are `stock_item_via_product` (linked, the seed shape)
    # or `product_no_link` (Product has no StockItem).
    assert lookup_body["kind"] == "stock_item_via_product", lookup_body
    assert lookup_body["product_id"] == product_id
    assert lookup_body["barcode_id"] == barcode_id


def test__register_barcode__same_barcode_twice__is_409(api):
    """Barcode UNIQUE constraint — same value can't be registered twice."""
    product_id = _next_unused_product_id()
    barcode = f"TEST-{uuid.uuid4().hex[:10]}"

    register_first = requests.post(REGISTER_URL, json={
        "product_id": product_id,
        "barcode": barcode,
    })
    assert register_first.status_code == 200, register_first.text

    register_dup = requests.post(REGISTER_URL, json={
        "product_id": product_id,
        "barcode": barcode,
    })
    assert register_dup.status_code == 409, register_dup.text


def test__register_barcode__direct_stock_item__lookup_resolves_to_stock_item(api):
    """FU-056 — registering directly against a stock item (no product)
    returns the `stock_item` kind on lookup. The 'lightweight install' path."""
    stock_item_id = requests.get(
        'http://localhost:5170/api/stock-items?limit=1'
    ).json()['items'][0]['stock_item_id']
    barcode = f"DIR-{uuid.uuid4().hex[:10]}"

    register = requests.post(REGISTER_URL, json={
        "stock_item_id": stock_item_id,
        "barcode": barcode,
    })
    assert register.status_code == 200, register.text
    body = register.json()
    assert body["stock_item_id"] == stock_item_id
    assert body["product_id"] is None

    lookup = requests.get(f"{LOOKUP_URL}?value={barcode}")
    assert lookup.status_code == 200, lookup.text
    lookup_body = lookup.json()
    assert lookup_body["kind"] == "stock_item"
    assert lookup_body["id"] == stock_item_id
    # The flat product_id field is None for direct-only registrations.
    assert lookup_body["product_id"] is None


def test__register_barcode__second_against_same_product__is_409(api):
    """FU-056 — one Product = one barcode (per-product UNIQUE)."""
    product_id = _next_unused_product_id()
    barcode_a = f"PROD-A-{uuid.uuid4().hex[:8]}"
    barcode_b = f"PROD-B-{uuid.uuid4().hex[:8]}"

    first = requests.post(REGISTER_URL, json={
        "product_id": product_id,
        "barcode": barcode_a,
    })
    assert first.status_code == 200, first.text

    second = requests.post(REGISTER_URL, json={
        "product_id": product_id,
        "barcode": barcode_b,
    })
    # The per-product UNIQUE constraint fires here (different barcode but
    # same product_id → can't have a second).
    assert second.status_code == 409, second.text


def test__register_barcode__neither_target__is_400(api):
    """FU-056 — model validator: at least one of product_id / stock_item_id
    must be set."""
    response = requests.post(REGISTER_URL, json={"barcode": "ORPHAN-12345"})
    assert response.status_code == 400, response.text


def test__delete_barcode__round_trip(api):
    """FU-056 — DELETE removes the registration; subsequent lookup is unknown."""
    stock_item_id = requests.get(
        'http://localhost:5170/api/stock-items?limit=1'
    ).json()['items'][0]['stock_item_id']
    barcode = f"DEL-{uuid.uuid4().hex[:10]}"

    register = requests.post(REGISTER_URL, json={
        "stock_item_id": stock_item_id,
        "barcode": barcode,
    })
    assert register.status_code == 200, register.text
    barcode_id = register.json()["barcode_id"]

    delete = requests.delete(f"{REGISTER_URL}/{barcode_id}")
    assert delete.status_code == 204, delete.text

    lookup = requests.get(f"{LOOKUP_URL}?value={barcode}")
    assert lookup.json()["kind"] == "unknown"


def test__barcode_lookup__unknown_value__is_unknown(api):
    lookup = requests.get(f"{LOOKUP_URL}?value=nothing-matches-this-12345")
    assert lookup.status_code == 200
    assert lookup.json()["kind"] == "unknown"


def test__barcode_lookup__missing_value__is_400(api):
    response = requests.get(LOOKUP_URL)
    assert response.status_code == 400


def test__qr_sheet__unknown_layout__is_400(api):
    response = requests.get(f"{STOCK_ITEMS_URL}/qr/sheet?layout=does-not-exist")
    assert response.status_code == 400


def test__qr_sheet__html_response(api):
    item_id = _first_seeded_stock_item_id()
    response = requests.get(
        f"{STOCK_ITEMS_URL}/qr/sheet?ids={item_id}&layout=a4-21up",
    )
    assert response.status_code == 200, response.text
    assert response.headers["Content-Type"].startswith("text/html")
    # The sheet embeds each QR as a data: URI rather than pointing back at
    # /api/stock-items/<id>/qr. The SPA fetches this page through the
    # authenticated client and opens it as a blob, where a same-origin
    # back-reference can't resolve — and an absolute one would be an
    # unauthenticated subresource, which is what broke "Print one".
    assert "src=\"data:image/png;base64," in response.text
    assert f"/api/stock-items/{item_id}/qr" not in response.text


# ── Stock-overview + meal-plan exports (post-N5 polish) ────────────────

def test__stock_overview_export_csv__returns_csv_with_header(api):
    response = requests.get(f"{STOCK_ITEMS_URL}/export?format=csv")
    assert response.status_code == 200, response.text
    assert response.headers["Content-Type"].startswith("text/csv")
    header = response.text.splitlines()[0]
    for col in (
        "location", "name", "level", "expiry", "is_essential",
        "is_open", "notes",
    ):
        assert col in header


def test__stock_overview_export__unknown_format__is_400(api):
    response = requests.get(f"{STOCK_ITEMS_URL}/export?format=pdf")
    assert response.status_code == 400


def test__stock_overview_print_view__returns_html(api):
    response = requests.get(f"{STOCK_ITEMS_URL}/print-view")
    assert response.status_code == 200, response.text
    assert response.headers["Content-Type"].startswith("text/html")
    assert "Stock overview" in response.text


# ── POST doors for large selections ────────────────────────────────────
# A filtered selection's ids used to travel only in the query string; at ~200
# uuids that overflows gunicorn's 8190-byte request line. The POST twins carry
# the same ids in a JSON body and must answer exactly like the GET door.

def _seeded_stock_items(count: int) -> list[dict]:
    response = requests.get(STOCK_ITEMS_URL)
    assert response.status_code == 200, response.text
    items = response.json().get("items") or []
    assert len(items) >= count, "seed should provide enough stock items"
    return items[:count]


def _selection_padded_past_the_request_line_cap(real_ids: list[str]) -> list[str]:
    # 400 uuids ≈ 15 KB of `ids=` — well past what a GET can carry. Unknown
    # ids are skipped, so the result still mirrors only the real selection.
    return real_ids + [str(uuid.uuid4()) for _ in range(400)]


def test__stock_overview_export_csv__post_selection__exports_only_those_items(api):
    picked, other = _seeded_stock_items(2)
    ids = _selection_padded_past_the_request_line_cap([picked["stock_item_id"]])

    response = requests.post(f"{STOCK_ITEMS_URL}/export?format=csv", json={"ids": ids})

    assert response.status_code == 200, response.text
    assert response.headers["Content-Type"].startswith("text/csv")
    assert "attachment" in response.headers["Content-Disposition"]
    rows = response.text.splitlines()
    assert len(rows) == 2  # header + the one real item
    assert picked["name"] in rows[1]
    assert other["name"] not in response.text


def test__stock_overview_export_csv__post_empty_selection__exports_header_only(api):
    response = requests.post(f"{STOCK_ITEMS_URL}/export?format=csv", json={"ids": []})

    assert response.status_code == 200, response.text
    assert len(response.text.splitlines()) == 1


def test__stock_overview_export__post_unknown_format__is_400(api):
    response = requests.post(f"{STOCK_ITEMS_URL}/export?format=pdf", json={"ids": []})
    assert response.status_code == 400


def test__stock_overview_export__post_over_the_id_cap__is_400(api):
    ids = [str(uuid.uuid4()) for _ in range(5001)]
    response = requests.post(f"{STOCK_ITEMS_URL}/export?format=csv", json={"ids": ids})
    assert response.status_code == 400


def test__stock_overview_export__post_without_ids__is_400(api):
    response = requests.post(f"{STOCK_ITEMS_URL}/export?format=csv", json={})
    assert response.status_code == 400


def test__stock_overview_print_view__post_selection__prints_only_those_items(api):
    picked, other = _seeded_stock_items(2)
    ids = _selection_padded_past_the_request_line_cap([picked["stock_item_id"]])

    response = requests.post(f"{STOCK_ITEMS_URL}/print-view", json={"ids": ids})

    assert response.status_code == 200, response.text
    assert response.headers["Content-Type"].startswith("text/html")
    assert "Stock overview" in response.text
    assert "1 item across" in response.text
    assert picked["name"] in response.text
    assert other["name"] not in response.text


def test__stock_overview_print_view__post_over_the_id_cap__is_400(api):
    ids = [str(uuid.uuid4()) for _ in range(5001)]
    response = requests.post(f"{STOCK_ITEMS_URL}/print-view", json={"ids": ids})
    assert response.status_code == 400


def test__meal_plan_export_csv__endpoint_removed__is_404(api):
    # meal-plan CSV export was removed (a plan is a calendar, not a
    # table); print-view → "Save as PDF" is the export path. The /export route
    # is gone, so it 404s.
    plans = requests.get("http://localhost:5170/api/meal-plans").json()["items"]
    assert plans, "the seed ships meal plans"
    plan_id = plans[0]["meal_plan_id"]
    response = requests.get(
        f"http://localhost:5170/api/meal-plans/{plan_id}/export?format=csv",
    )
    assert response.status_code == 404


def test__meal_plan_print_view__returns_html(api):
    plans = requests.get("http://localhost:5170/api/meal-plans").json()["items"]
    assert plans, "the seed ships meal plans"
    plan_id = plans[0]["meal_plan_id"]
    response = requests.get(
        f"http://localhost:5170/api/meal-plans/{plan_id}/print-view",
    )
    assert response.status_code == 200, response.text
    assert response.headers["Content-Type"].startswith("text/html")


def test__meal_plan_print_view__nameless_plan__titles_by_week_not_none(api):
    # C-2.E — the planner creates *nameless* week-plans, so an unnamed plan is
    # the normal case for anything built in the UI, not an edge case. The
    # template rendered `plan.name` raw, so Jinja printed the literal string
    # "None" as both the page <title> and the <h1> on every planner print.
    # Create the nameless plan explicitly: the seeded plans all carry a name,
    # so keying off seed data silently skips this.
    created = requests.post(
        "http://localhost:5170/api/meal-plans",
        json={"start_date": "2027-03-01", "entries": []},
    )
    assert created.status_code == 201, created.text
    plan_id = created.json()["meal_plan_id"]

    response = requests.get(
        f"http://localhost:5170/api/meal-plans/{plan_id}/print-view",
    )
    assert response.status_code == 200, response.text
    assert "None ·" not in response.text
    assert "<h1>None</h1>" not in response.text
    assert "Week of 1 Mar 2027" in response.text


def test__meal_plan_print_view__slot_columns_follow_household_vocabulary(api):
    # Owner report 2026-09-01: "Snack still showed up in the print page even
    # though I had deleted that meal slot." The slot columns were a hardcoded
    # ("Breakfast", "Lunch", "Dinner", "Snack") tuple in the exporter, so the
    # sheet ignored the household vocabulary in both directions — it printed a
    # deleted slot and would have omitted an added one. Columns now come from
    # the MealSlot table (R-003).
    items = requests.get("http://localhost:5170/api/recipes").json()["items"]
    assert items, "the seed ships recipes"

    # A slot the hardcoded tuple never knew about. Deleting one of the four is
    # the reported case, but adding a fifth exercises the same seam and does
    # not depend on the seed's slot list.
    slot_name = "Supper Club"
    created_slot = requests.post(
        "http://localhost:5170/api/meal-slots", json={"name": slot_name},
    )
    assert created_slot.status_code == 201, created_slot.text

    created = requests.post(
        "http://localhost:5170/api/meal-plans",
        json={
            "start_date": "2027-03-08",
            "entries": [{
                "recipe_id": items[0]["recipe_id"],
                "scheduled_for": "2027-03-08",
                "servings": 1,
                "slot": slot_name,
            }],
        },
    )
    assert created.status_code == 201, created.text
    plan_id = created.json()["meal_plan_id"]

    html = requests.get(
        f"http://localhost:5170/api/meal-plans/{plan_id}/print-view",
    ).text
    vocabulary = {
        s["name"] for s in requests.get("http://localhost:5170/api/meal-slots").json()
    }
    assert slot_name in vocabulary
    assert f"<th>{slot_name}</th>" in html
    # No column for a name the household does not have. "Snack" is the reported
    # one; assert the general rule over the whole retired tuple.
    for stale in {"Breakfast", "Lunch", "Dinner", "Snack"} - vocabulary:
        assert f"<th>{stale}</th>" not in html, stale


# ── Rendered-document defects (print/export audit, 2026-10-30) ────────
# Each test pins one defect an auditor found in the live app's print views
# and CSVs. Shapes come from the API, not the seed, where the seed may lack
# the case (a structured recipe, a cook batch, an unlinked ingredient).

API = "http://localhost:5170/api"


def _create_structured_recipe() -> str:
    """A structured recipe in two sections with a hint, a timer, a sub-step,
    an optional ingredient and an unlinked (raw-text only) ingredient."""
    stock_item_id = _first_seeded_stock_item_id()
    response = requests.post(f"{API}/recipes", json={
        "name": "Print Audit Lasagne",
        "servings": 1,
        "steps_mode": "structured",
        "instructions": "One-line summary only",
        "sections": [
            {"client_id": "s-sauce", "sequence": 0, "name": "Sauce"},
            {"client_id": "s-bake", "sequence": 1, "name": "Assembly"},
        ],
        "ingredients": [
            {"stock_item_id": stock_item_id, "quantity": 2.0, "unit": "tbsp",
             "section_client_id": "s-sauce", "client_id": "i1"},
            {"raw_text": "Crème fraîche", "quantity": 100.0, "unit": "g",
             "section_client_id": "s-bake", "client_id": "i2", "is_optional": True},
        ],
        "steps": [
            {"client_id": "st1", "sequence": 0, "text": "Brown the mince",
             "hint": "Keep the pan hot", "timer_minutes": 10,
             "section_client_id": "s-sauce"},
            {"client_id": "st1a", "parent_client_id": "st1", "sequence": 0,
             "text": "Drain the fat", "section_client_id": "s-sauce"},
            {"client_id": "st2", "sequence": 1, "text": "Layer and bake",
             "section_client_id": "s-bake"},
        ],
    })
    assert response.status_code == 201, response.text
    return response.json()["recipe_id"]


def test__print_and_csv__content_type__names_the_charset_once(api):
    # `mimetype="text/html; charset=utf-8"` made Flask append its own charset
    # too: "text/csv; charset=utf-8; charset=utf-8" on every export.
    list_id = _first_seeded_shopping_list_id()
    recipe_id = _create_structured_recipe()
    plan_id = requests.post(
        f"{API}/meal-plans", json={"start_date": "2027-03-01", "entries": []},
    ).json()["meal_plan_id"]
    for url in (
        f"{API}/shopping-lists/{list_id}/print-view",
        f"{API}/recipes/{recipe_id}/print-view",
        f"{API}/recipes/{recipe_id}/export?format=csv",
        f"{API}/meal-plans/{plan_id}/print-view",
        f"{STOCK_ITEMS_URL}/print-view",
        f"{STOCK_ITEMS_URL}/export?format=csv",
    ):
        response = requests.get(url)
        assert response.status_code == 200, (url, response.text)
        content_type = response.headers["Content-Type"]
        assert content_type.count("charset") == 1, (url, content_type)


def test__csv_exports__start_with_a_utf8_bom(api):
    # Excel on Windows read the BOM-less CSV as ANSI: "Crème" became "CrÃ¨me".
    recipe_id = _create_structured_recipe()
    for url, first_column in (
        (f"{API}/recipes/{recipe_id}/export?format=csv", "ingredient"),
        (f"{STOCK_ITEMS_URL}/export?format=csv", "location"),
    ):
        raw = requests.get(url).content
        assert raw.startswith(b"\xef\xbb\xbf"), raw[:10]
        assert raw.decode("utf-8-sig").splitlines()[0].split(",")[0] == first_column


def test__recipe_csv__unlinked_name_and_trimmed_quantities(api):
    import csv
    import io
    recipe_id = _create_structured_recipe()
    raw = requests.get(f"{API}/recipes/{recipe_id}/export?format=csv").content
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    by_unit = {row["unit"]: row for row in rows}
    # An unlinked row exported a blank name; quantities exported as "100.0".
    assert by_unit["g"]["ingredient"] == "Crème fraîche"
    assert by_unit["g"]["quantity"] == "100"
    assert by_unit["tbsp"]["quantity"] == "2"
    assert all(row["ingredient"] for row in rows), rows


def test__recipe_print_view__structured_recipe_prints_sections_steps_and_tags(api):
    recipe_id = _create_structured_recipe()
    html = requests.get(f"{API}/recipes/{recipe_id}/print-view").text
    # Steps, hint, timer and sub-step, not the one-line `instructions` blob.
    for text in ("Brown the mince", "Keep the pan hot", "Timer: 10 min",
                 "Drain the fat", "Layer and bake"):
        assert text in html, text
    assert "One-line summary only" not in html
    # Ingredients and steps grouped under their section headings, in order.
    assert html.count("<h3>Sauce</h3>") == 2
    assert html.count("<h3>Assembly</h3>") == 2
    assert html.index("<h3>Sauce</h3>") < html.index("<h3>Assembly</h3>")
    # The unlinked row by its pasted text (it printed "None"), tagged
    # optional, and quantities without float tails ("2.0 tbsp" / "100.0g").
    assert ">None<" not in html
    assert "Crème fraîche" in html
    assert "(optional)" in html
    assert "2 tbsp" in html and "100g" in html
    assert "2.0 tbsp" not in html and "100.0g" not in html
    # A real plural, not "serving(s)".
    assert "1 serving<" in html and "(s)" not in html


def test__recipe_print_view__image_mode_embeds_the_step_photos(api):
    png = (
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlE"
        "QVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    response = requests.post(f"{API}/recipes", json={
        "name": "Print Audit Photo Recipe",
        "steps_mode": "image",
        "instructions": "See the photos.",
        "step_images": [png, png],
    })
    assert response.status_code == 201, response.text
    recipe_id = response.json()["recipe_id"]
    html = requests.get(f"{API}/recipes/{recipe_id}/print-view").text
    # The sheet said "See the photos." and showed none.
    assert html.count('src="data:image/png;base64,') == 2
    assert "See the photos." not in html


def test__meal_plan_print_view__seven_days_batches_and_print_dates(api):
    recipes = requests.get(f"{API}/recipes").json()
    items = recipes.get("items") if isinstance(recipes, dict) else recipes
    if not items:
        return  # No seeded recipes on this install; nothing to schedule.
    slot = requests.get(f"{API}/meal-slots").json()[0]["name"]
    created = requests.post(f"{API}/meal-plans", json={
        "start_date": "2027-03-01",
        "entries": [
            {"recipe_id": items[0]["recipe_id"], "scheduled_for": day,
             "servings": 2, "slot": slot, "cook_key": "b1"}
            for day in ("2027-03-01", "2027-03-02", "2027-03-03")
        ],
    })
    assert created.status_code == 201, created.text
    html = requests.get(
        f"{API}/meal-plans/{created.json()['meal_plan_id']}/print-view",
    ).text
    # One cook and two leftovers, not three separate cooks.
    assert html.count("Cook (batch of 3)") == 1
    assert html.count("Leftovers") == 2
    # All seven days print, the empty ones included.
    assert html.count('class="day-header"') == 7
    assert "Sun, 7 Mar" in html  # en-AU, the seeded household locale
    # Household-style dates and real plurals, never ISO or "(s)".
    assert "starts 1 Mar 2027" in html
    assert "2027-03-01" not in html
    assert "(s)" not in html and "entr(y" not in html
    assert "2 servings" in html


def test__stock_overview_print_view__expiry_and_counts_read_naturally(api):
    item_id = _first_seeded_stock_item_id()
    patched = requests.patch(
        f"{STOCK_ITEMS_URL}/{item_id}", json={"expiry_date": "2026-12-29"},
    )
    assert patched.status_code in (200, 204), patched.text
    html = requests.get(f"{STOCK_ITEMS_URL}/print-view?ids={item_id}").text
    assert "29 Dec 2026" in html
    assert "2026-12-29" not in html
    assert "1 item across 1 location" in html
    assert "(s)" not in html


def test__stock_overview_csv__filename_uses_the_household_day(api):
    from dora_api.app import app
    from dora_api.features.app_settings.clock import household_today
    from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
    response = requests.get(f"{STOCK_ITEMS_URL}/export?format=csv")
    with app.app_context():
        today = household_today(SqlAlchemyRepository()).isoformat()
    disposition = response.headers["Content-Disposition"]
    assert f'filename="stock-overview-{today}.csv"' in disposition


def test__shopping_list_print_view__prices_and_totals_match_the_app(api):
    # The sheet priced each line from the selected offer's `price_now` alone
    # and summed its own total, so it disagreed with the list page (50.30 in
    # the app, $19.79 printed). It now prints the detail DTO's own figures.
    list_id = _first_seeded_shopping_list_id()
    detail = requests.get(f"{API}/shopping-lists/{list_id}").json()
    line = next(l for l in detail["lines"] if not l["deferred_by_budget"])
    patched = requests.patch(
        f"{API}/shopping-lists/{list_id}/lines/{line['line_id']}",
        json={"actual_unit_price": 3.25, "is_ticked": True},
    )
    assert patched.status_code in (200, 204), patched.text
    detail = requests.get(f"{API}/shopping-lists/{list_id}").json()
    html = requests.get(f"{API}/shopping-lists/{list_id}/print-view").text

    assert f"${detail['totals']['total_price']:.2f}" in html
    assert "$3.25" in html
    # A picked line prints ticked, matching the "picked up" count.
    ticked = detail["totals"]["ticked_count"]
    assert ticked >= 1
    assert html.count("✓</span>") == ticked
    assert f"<strong>{ticked}</strong> picked up" in html
    # The resolved store (the store ladder), not only the chosen offer's.
    for l in detail["lines"]:
        if l["resolved_store_name"] and not l["deferred_by_budget"]:
            assert l["resolved_store_name"] in html
    assert "item(s)" not in html


def test__shopping_list_print_view__set_aside_lines_leave_the_active_list(api):
    import dataclasses

    from dora_api.app import app
    from zoneinfo import ZoneInfo

    from dora_api.features.data.export_shared import PrintFormat
    from dora_api.features.data.export_shopping_list import _render_print_view
    from dora_api.features.shopping_lists.get_shopping_list_detail import \
        GetShoppingListDetailHandler
    from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

    list_id = _first_seeded_shopping_list_id()
    with app.test_request_context():
        detail = GetShoppingListDetailHandler(SqlAlchemyRepository()).handle(list_id)
        assert detail.lines, "seed list should have lines"
        deferred = dataclasses.replace(
            detail.lines[0], deferred_by_budget=True,
            stock_item_name="Zz Deferred Thing", estimated_unit_price=4.0,
        )
        detail = dataclasses.replace(detail, lines=[deferred, *detail.lines[1:]])
        html = _render_print_view(detail, PrintFormat("en-GB", "GBP", ZoneInfo("UTC")))
    assert html.index("Zz Deferred Thing") > html.index("Set aside to fit the budget")
    # The install currency, not a hard-coded "$".
    assert "£4.00" in html
    assert "$" not in html


# the library now owns "when was
# the last backup" via `MAX(Backup.created_at)`. The old test that
# stamped this column on every download lived here; deleted.


def test__restore_backup__RowPredatesADefaultedColumn__DefaultApplies(api):
    """An older backup has no key for a column added since. Inserting it as an
    explicit NULL overrode the server default and broke the NOT NULL."""
    _, backup = _create_backup()
    victim = backup["stock_items"][0]
    deleted = requests.delete(f"http://localhost:5170/api/stock-items/{victim['id']}")
    assert deleted.status_code in (200, 204), deleted.text
    del victim["is_open"]

    response = requests.post(RESTORE_URL, json={
        "backup": backup,
        "selection": {"stock_items": [victim["id"]]},
        "mode": "partial",
    })

    assert response.status_code == 200, response.text
    assert response.json()["created"]["stock_items"] == 1


def test__restore_backup__ParentSkippedAsDuplicate__ChildKeepsTheExistingParent(api):
    """A location that exists under the same name but a different id is
    skipped as a duplicate; the item pointing at the backup's id must be
    re-pointed at the location that stayed, not nulled."""
    _, backup = _create_backup()
    location = next(l for l in backup["stock_locations"] if l.get("parent_id") is None)
    template_item = backup["stock_items"][0]
    renamed_location_id = str(uuid.uuid4())
    new_item_id = str(uuid.uuid4())
    doc = {
        "schema_version": backup["schema_version"],
        "stock_locations": [{**location, "id": renamed_location_id}],
        "stock_items": [{
            **template_item,
            "id": new_item_id,
            "name": f"Restore remap {uuid.uuid4().hex[:8]}",
            "stock_location_id": renamed_location_id,
        }],
    }

    response = requests.post(RESTORE_URL, json={
        "backup": doc, "selection": {}, "mode": "all_skip_duplicates",
    })

    assert response.status_code == 200, response.text
    assert response.json()["created"]["stock_items"] == 1, response.text
    from sqlalchemy import text

    from dora_api.app import app, db
    from tests.support import uuid_bind
    with app.app_context(), db.engine.connect() as conn:
        stored = conn.execute(
            text('SELECT stock_location_id FROM "StockItem" WHERE id = :id'),
            {"id": uuid_bind(new_item_id)},
        ).scalar_one()
    assert str(uuid.UUID(bytes=stored) if isinstance(stored, bytes) else stored) == location["id"]


def test__restore_backup__MalformedUploadId__IsBadRequest(api):
    response = requests.post(RESTORE_URL, json={
        "upload_id": "../../etc/passwd", "selection": {}, "mode": "all_skip_duplicates",
    })

    assert response.status_code == 400, response.text


def test__inspect_backup__MalformedUploadId__IsBadRequest(api):
    response = requests.post(INSPECT_URL, json={"upload_id": "../secrets"})

    assert response.status_code == 400, response.text


def test__spreadsheet_import__ColumnMapOmitsOptionalTargets__ImportsWithDefaults(api):
    """Only `name` is required; an omitted target (not mapped to null, just
    absent) used to KeyError the commit into a 500."""
    upload_id = _stage_bytes(f"Item\nTestImport-NameOnly-{uuid.uuid4().hex[:6]}\n".encode("utf-8"))

    commit = requests.post(IMPORT_COMMIT_URL, json={
        "upload_id": upload_id,
        "filename": "items.csv",
        "sheet": "items.csv",
        "column_map": {"name": "Item"},
    })

    assert commit.status_code == 200, commit.text
    assert commit.json()["summary"]["created"] == 1


def test__restore_backup__RecipeSkippedAsDuplicate__ItsIngredientsAreNotMergedIntoTheExistingRecipe(api):
    """Only reference parents (locations, groups, vocab, items, products)
    re-point children on a duplicate skip. An aggregate root such as a recipe
    must not: a backup recipe with the same name but a new id would otherwise
    pour its ingredients into the recipe that stayed, duplicating them."""
    _, backup = _create_backup()
    recipe = next(r for r in backup["recipes"] if any(
        i["recipe_id"] == r["id"] for i in backup["recipe_ingredients"]
    ))
    ingredients = [i for i in backup["recipe_ingredients"] if i["recipe_id"] == recipe["id"]]
    renamed_recipe_id = str(uuid.uuid4())
    doc = {
        "schema_version": backup["schema_version"],
        "recipes": [{**recipe, "id": renamed_recipe_id}],
        "recipe_ingredients": [
            {**i, "id": str(uuid.uuid4()), "recipe_id": renamed_recipe_id} for i in ingredients
        ],
    }
    before = requests.get(f"http://localhost:5170/api/recipes/{recipe['id']}").json()

    response = requests.post(RESTORE_URL, json={
        "backup": doc, "selection": {}, "mode": "all_skip_duplicates",
    })

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"]["recipes"] == 0
    assert body["created"]["recipe_ingredients"] == 0, body
    after = requests.get(f"http://localhost:5170/api/recipes/{recipe['id']}").json()
    assert len(after["ingredients"]) == len(before["ingredients"])


def test__restore_backup__ProductLinkRemappedOntoAnExistingPair__IsSkippedNotAnError(api):
    """A product ↔ item link whose item and product both resolve (by name /
    product key) to rows that are already linked re-keys onto an existing
    pair after the remap; that is a skip, not a PK / UNIQUE(product_id)
    violation that rolls the whole restore back."""
    _, backup = _create_backup()
    link = backup["product_stock_item_links"][0]
    item = next(i for i in backup["stock_items"] if i["id"] == link["stock_item_id"])
    product = next(p for p in backup["saved_products"] if p["id"] == link["product_id"])
    new_item_id, new_product_id = str(uuid.uuid4()), str(uuid.uuid4())
    doc = {
        "schema_version": backup["schema_version"],
        "saved_products": [{**product, "id": new_product_id}],
        "stock_items": [{**item, "id": new_item_id}],
        "product_stock_item_links": [{"stock_item_id": new_item_id, "product_id": new_product_id}],
    }

    response = requests.post(RESTORE_URL, json={
        "backup": doc, "selection": {}, "mode": "all_skip_duplicates",
    })

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"]["product_stock_item_links"] == 0, body
    assert body["skipped"]["product_stock_item_links"] == 1, body
