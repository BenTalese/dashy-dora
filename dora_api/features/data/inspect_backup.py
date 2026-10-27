"""POST /api/data/backup/inspect — preview a backup file.

Two input paths:
  - JSON body containing `{"upload_id": "<uuid>"}` references a file
    previously staged via /api/data/uploads/*. The endpoint
    stream-parses the staged file with ijson so peak RAM stays bounded
    regardless of file size.
  - JSON body containing a backup document directly (small files, tests).

Multipart uploads here are no longer the canonical path — the SPA always
chunked-uploads via /uploads/* now — but they're kept as a fallback for
curl-style ad-hoc inspection.

The response carries per-section row counts, the duplicate-flagged
names, AND a per-section sample of up to PREVIEW_ROW_LIMIT row labels so
the SPA can render the tree without re-downloading the file. Sections
that overflow the limit set `truncated: true`.
"""
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Iterator

import ijson
from flask import request
from sqlalchemy import select

from dora_api.app import db
from dora_api.features.auth.admin_gate import require_admin
from dora_api.features.data.backup import BACKUP_SCHEMA_VERSION
from dora_api.features.data._errors import DataError, invalid, respond_to, upload_missing
from dora_api.features.data.restore_shared import (
    DUPLICATE_KEY_BY_BACKUP_KEY,
    TABLE_NAME_BY_BACKUP_KEY,
)
from dora_api.features.data.uploads import staged_path
from dora_api.features.routers import DATA_ROUTER
from dora_api.infrastructure.api_response import bad_request, ok

_LOGGER = logging.getLogger(__name__)


# Per-section row-label preview cap. Keeps the inspect response small
# enough for the SPA to load without a second download even when the
# backup is huge.
PREVIEW_ROW_LIMIT = 500

# Direct-upload (non-staged) cap. The chunked path goes through
# /api/data/uploads/* and has its own (2 GB) cap.
DIRECT_UPLOAD_MAX_BYTES = 500 * 1024 * 1024
CHUNK_BYTES = 8 * 1024 * 1024


def _stream_upload_to_tempfile(upload) -> tuple[str | None, str | None]:
    """Drain a Werkzeug FileStorage into a temp file. Used by the
    multipart fallback path; the chunked-upload path stages directly to
    `data/uploads/` and skips this entirely.
    """
    fd, path = tempfile.mkstemp(prefix="dora-backup-", suffix=".json")
    written = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = upload.stream.read(CHUNK_BYTES)
                if not chunk:
                    break
                written += len(chunk)
                if written > DIRECT_UPLOAD_MAX_BYTES:
                    return None, (
                        f"Backup file is larger than the "
                        f"{DIRECT_UPLOAD_MAX_BYTES // (1024 * 1024)} MB direct-upload limit. "
                        f"Use the chunked upload path for larger files."
                    )
                out.write(chunk)
        return path, None
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


def _resolve_file_path() -> tuple[Path | None, DataError | None, bool]:
    """Returns (path_on_disk, error, owns_path).

    `owns_path` indicates whether the caller should unlink the file
    after parsing (True for multipart temp files, False for staged
    uploads we leave around for /restore).

    If the request body is a backup document directly (no `upload_id`,
    no multipart), returns (None, None, False) — the inline-JSON path
    is handled separately below.
    """
    # Path 1: chunked-stage reference.
    body = request.get_json(silent=True)
    if isinstance(body, dict) and isinstance(body.get("upload_id"), str):
        upload_id = body["upload_id"]
        path = staged_path(upload_id)
        if not path.exists():
            return None, upload_missing(upload_id), False
        return path, None, False

    # Path 2: multipart fallback.
    if request.files:
        upload = next(iter(request.files.values()), None)
        if upload is None:
            return None, invalid("No file in upload."), False
        tmp, err = _stream_upload_to_tempfile(upload)
        if err is not None:
            return None, invalid(err), False
        return Path(tmp), None, True

    # Path 3: inline JSON.
    return None, None, False


def _stream_metadata(path: Path) -> dict[str, Any]:
    """Pull schema_version, exported_at, exported_by, sections out of the
    file using ijson's prefix-targeted parse — never instantiates the
    whole document.
    """
    meta: dict[str, Any] = {}
    with open(path, "rb") as fh:
        for prefix, event, value in ijson.parse(fh):
            if prefix == "schema_version" and event == "number":
                meta["schema_version"] = value
            elif prefix == "exported_at" and event == "string":
                meta["exported_at"] = value
            elif prefix == "exported_by" and event == "string":
                meta["exported_by"] = value
            elif prefix == "sections.item" and event == "string":
                meta.setdefault("sections", []).append(value)
            elif prefix == "sections" and event == "end_array":
                # We have everything we need from the metadata block once
                # `sections` closes. Real data sections live after.
                break
    return meta


def _iter_section_rows(path: Path, section: str) -> Iterator[dict[str, Any]]:
    """Yield each row dict of a section without buffering the whole list."""
    with open(path, "rb") as fh:
        yield from ijson.items(fh, f"{section}.item")


def _build_existing_duplicate_keys(backup_key: str) -> set:
    table = db.metadata.tables[TABLE_NAME_BY_BACKUP_KEY[backup_key]]
    rows = db.session.execute(select(table)).all()
    column_names = [c.name for c in table.columns]
    key_fn = DUPLICATE_KEY_BY_BACKUP_KEY[backup_key]
    return {
        key_fn({col: row[idx] for idx, col in enumerate(column_names)})
        for row in rows
    }


def _row_label(row: dict[str, Any]) -> str:
    return str(row.get("name") or row.get("id") or "<unknown>")


def _inspect_streamed(path: Path) -> tuple[dict | None, str | None]:
    meta = _stream_metadata(path)
    version = meta.get("schema_version")
    if not isinstance(version, int):
        return None, "Backup is missing 'schema_version'."
    if version > BACKUP_SCHEMA_VERSION:
        return None, (
            f"Backup schema_version {version} is newer than this server supports "
            f"({BACKUP_SCHEMA_VERSION})."
        )

    entity_counts: dict[str, int] = {}
    duplicates: dict[str, list[str]] = {}
    samples: dict[str, dict[str, Any]] = {}

    for backup_key in TABLE_NAME_BY_BACKUP_KEY:
        existing_keys: set | None = None
        if backup_key in DUPLICATE_KEY_BY_BACKUP_KEY:
            existing_keys = _build_existing_duplicate_keys(backup_key)
            key_fn = DUPLICATE_KEY_BY_BACKUP_KEY[backup_key]
        else:
            key_fn = None

        count = 0
        dup_names: list[str] = []
        sample_rows: list[dict[str, Any]] = []

        for row in _iter_section_rows(path, backup_key):
            count += 1
            if len(sample_rows) < PREVIEW_ROW_LIMIT:
                sample_rows.append({
                    "id": str(row.get("id")) if row.get("id") is not None else f"row-{count}",
                    "name": _row_label(row),
                })
            if existing_keys is not None and key_fn is not None:
                if key_fn(row) in existing_keys:
                    dup_names.append(_row_label(row))

        entity_counts[backup_key] = count
        if dup_names:
            duplicates[backup_key] = dup_names
        samples[backup_key] = {
            "rows": sample_rows,
            "truncated": count > PREVIEW_ROW_LIMIT,
        }

    return {
        "schema_version": version,
        "exported_at": meta.get("exported_at"),
        "exported_by": meta.get("exported_by"),
        "sections": meta.get("sections", []),
        "entity_counts": entity_counts,
        "duplicates": duplicates,
        "samples": samples,
    }, None


def _inspect_inline(payload: dict) -> tuple[dict | None, str | None]:
    """Fallback path for callers that POSTed the doc directly. Memory-bound
    by definition — kept for backward compatibility with the early SPA and
    for tests.
    """
    version = payload.get("schema_version")
    if not isinstance(version, int):
        return None, "Backup is missing 'schema_version'."
    if version > BACKUP_SCHEMA_VERSION:
        return None, (
            f"Backup schema_version {version} is newer than this server supports "
            f"({BACKUP_SCHEMA_VERSION})."
        )

    entity_counts: dict[str, int] = {}
    duplicates: dict[str, list[str]] = {}
    samples: dict[str, dict[str, Any]] = {}

    for backup_key in TABLE_NAME_BY_BACKUP_KEY:
        rows = payload.get(backup_key, [])
        if not isinstance(rows, list):
            return None, f"Section '{backup_key}' must be a list."
        entity_counts[backup_key] = len(rows)

        sample_rows = [
            {
                "id": str(row.get("id")) if row.get("id") is not None else f"row-{i}",
                "name": _row_label(row),
            }
            for i, row in enumerate(rows[:PREVIEW_ROW_LIMIT])
        ]
        samples[backup_key] = {
            "rows": sample_rows,
            "truncated": len(rows) > PREVIEW_ROW_LIMIT,
        }

        if backup_key not in DUPLICATE_KEY_BY_BACKUP_KEY:
            continue
        existing_keys = _build_existing_duplicate_keys(backup_key)
        key_fn = DUPLICATE_KEY_BY_BACKUP_KEY[backup_key]
        dup_names = [_row_label(r) for r in rows if key_fn(r) in existing_keys]
        if dup_names:
            duplicates[backup_key] = dup_names

    return {
        "schema_version": version,
        "exported_at": payload.get("exported_at"),
        "exported_by": payload.get("exported_by"),
        "sections": payload.get("sections", []),
        "entity_counts": entity_counts,
        "duplicates": duplicates,
        "samples": samples,
    }, None


@DATA_ROUTER.route("/backup/inspect", methods=["POST"])
def inspect_backup():
    # inspect reads uploaded backup contents,
    # including any user rows the file would carry into a restore.
    # Same admin gate as the restore endpoint itself.
    _, admin_err = require_admin()
    if admin_err is not None:
        return admin_err
    path, err, owns_path = _resolve_file_path()
    if err is not None:
        _LOGGER.warning("inspect_backup rejected upload: %s", err.detail)
        return respond_to(err)

    try:
        if path is not None:
            result, err = _inspect_streamed(path)
        else:
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                return bad_request(
                    "Body must be {\"upload_id\": ...}, a backup document, or a "
                    "multipart upload."
                )
            result, err = _inspect_inline(body)

        if err is not None:
            return bad_request(err)
        return ok(result)
    finally:
        if owns_path and path is not None:
            try:
                os.unlink(path)
            except OSError:
                pass
