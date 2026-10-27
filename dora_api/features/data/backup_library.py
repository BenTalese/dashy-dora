"""Backup library endpoints (FU-342).

Replaces the previous `GET /data/backup` download-only fast-path. Every
backup now generates a persistent row + a file on disk; the library
lists / downloads / restores / deletes past backups.

Five endpoints (all admin-gated via `require_admin` — FU-341 / FU-198):

    POST   /api/data/backups              → generate + persist; return the new row
    GET    /api/data/backups              → paginated list, newest first
    GET    /api/data/backups/<id>/download → stream the saved file
    POST   /api/data/backups/<id>/restore  → restore from the saved file
    DELETE /api/data/backups/<id>         → drop the row + the file

The restore endpoint routes to the existing
`features/data/restore_backup.RestoreBackupHandler`, threading the
library's stored path through the same code the "restore an external
file" flow uses. That path also stays reachable (upload → inspect →
commit); the library adds a "no-upload" fast lane for backups Dora
generated herself.

Retention: on every create, prune backups older than the newest N
(`AppSetting.backup_retention_count`, default 5). Prune drops the row
*and* the file so the disk doesn't leak.

Storage path: `AppSetting.backup_storage_path`; empty ⇒
`<data-dir>/backups`. Resolved via `DORA_CONFIG.get_backups_dir()` so
container volumes / NAS mounts work with a single admin toggle.
"""
import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from flask import Response, request, send_file
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from dora_api.app import db
from dora_api.domain.entities.backup import (
    Backup,
    STATUS_READY,
    TRIGGER_MANUAL,
)
from dora_api.domain.entities.user import User
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.features.auth.admin_gate import require_admin
from dora_api.features.data.backup import (
    GetBackupHandler,
    resolve_selected_sections,
)
from dora_api.features.data.restore_shared import SECTIONS
from dora_api.features.data.restore_backup import RestoreBackupHandler, RestoreBackupRequest
from dora_api.features.routers import DATA_ROUTER
from dora_api.infrastructure.api_response import (
    bad_request,
    internal_server_error,
    no_content,
    not_found,
    ok,
    paginated,
)
from dora_api.infrastructure.configuration_manager import DORA_CONFIG
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)


# ── Request/response shapes ────────────────────────────────────────────

class CreateBackupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Empty / omitted list ⇒ every `default_on` section (matches the old
    # query-string default). Unknown keys → 400 with the offenders named.
    sections: list[str] | None = Field(default=None)


@dataclass(slots=True)
class BackupRowDto:
    backup_id: str
    created_at: str
    created_by_user_id: str | None
    created_by_username: str | None
    size_bytes: int
    sections: list[str]
    sha256: str
    status: str
    trigger_kind: str


def _row_to_dto(row: Backup, username_by_id: dict[UUID, str]) -> dict:
    try:
        section_list = json.loads(row.sections) if row.sections else []
        if not isinstance(section_list, list):
            section_list = []
    except (ValueError, TypeError):
        section_list = []
    return {
        "backup_id": str(row.id),
        "created_at": row.created_at.isoformat() if row.created_at is not None else None,
        "created_by_user_id": (
            str(row.created_by_user_id) if row.created_by_user_id is not None else None
        ),
        "created_by_username": (
            username_by_id.get(row.created_by_user_id)
            if row.created_by_user_id is not None else None
        ),
        "size_bytes": int(row.size_bytes),
        "sections": section_list,
        "sha256": row.sha256,
        "status": row.status,
        "trigger_kind": row.trigger_kind,
    }


# ── Path helpers ───────────────────────────────────────────────────────

def _backups_dir() -> Path:
    """Resolve the storage location honouring the AppSetting override."""
    settings = get_or_create_app_setting(SqlAlchemyRepository())
    return DORA_CONFIG.get_backups_dir(settings.backup_storage_path or None)


def _storage_path_for(backup_id: UUID, exported_at: datetime) -> Path:
    """Filename shape: `<date>-<id-prefix>.json`. Date first so `ls` and
    `find` naturally sort chronological; short id suffix disambiguates
    same-day backups without exposing the whole UUID in the filename."""
    date_str = exported_at.date().isoformat()
    id_prefix = str(backup_id).split("-", 1)[0]
    return _backups_dir() / f"dora-backup-{date_str}-{id_prefix}.json"


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _enforce_retention(repository: SqlAlchemyRepository) -> list[Backup]:
    """Drop rows + files older than the newest N (per AppSetting).
    Returns the list of removed rows (for logging). Called after a
    successful create so the library never grows past the cap."""
    settings = get_or_create_app_setting(repository)
    cap = max(1, int(settings.backup_retention_count))
    rows = repository.get(Backup).all()
    rows_sorted = sorted(rows, key=lambda r: r.created_at, reverse=True)
    stale = rows_sorted[cap:]
    for row in stale:
        _unlink_quiet(row.storage_path)
        repository.remove(row)
    if stale:
        repository.save_changes()
    return stale


def _unlink_quiet(path_str: str) -> None:
    """Best-effort file removal — log but don't raise. A missing file
    isn't an error; a permission denial gets logged so the operator can
    fix mounts / permissions without a 500."""
    if not path_str:
        return
    try:
        Path(path_str).unlink(missing_ok=True)
    except OSError as exc:
        _LOGGER.warning(
            "Backup file unlink failed for %s: %s", path_str, exc
        )


# ── Endpoints ──────────────────────────────────────────────────────────

@DATA_ROUTER.route("/backups", methods=["POST"])
@has_request_body(CreateBackupRequest)
def create_backup():
    user_id, err = require_admin()
    if err is not None:
        return err

    _Request: CreateBackupRequest = get_request_body()
    selected, section_err = resolve_selected_sections(_Request.sections)
    if section_err is not None:
        return bad_request(section_err)

    # Build the payload via the existing handler (fresh dump each call —
    # matches user expectation "backup now == right now, not yesterday").
    result = GetBackupHandler(SqlAlchemyRepository()).handle(user_id, selected)

    # Write the file with a unique id so parallel admin calls don't
    # clobber. `mkdir` inside get_backups_dir() ensures the parent exists.
    backup_id = uuid4()
    path = _storage_path_for(backup_id, result.exported_at)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result.payload, f, ensure_ascii=False)
    except OSError as exc:
        _LOGGER.exception("Failed to write backup file at %s", path)
        return internal_server_error(f"Could not write backup file: {exc}")

    size_bytes = path.stat().st_size
    sha256 = _sha256_of(path)

    row = Backup(
        created_at=result.exported_at,
        created_by_user_id=user_id,
        size_bytes=size_bytes,
        sections=json.dumps(sorted(selected)),
        sha256=sha256,
        status=STATUS_READY,
        trigger_kind=TRIGGER_MANUAL,
        storage_path=str(path),
    )
    repository = SqlAlchemyRepository()
    repository.add(row)
    repository.save_changes()

    dropped = _enforce_retention(repository)
    if dropped:
        _LOGGER.info(
            "Backup retention pruned %d row(s): %s",
            len(dropped), [str(r.id) for r in dropped],
        )

    # username lookup for the response row
    username_by_id: dict[UUID, str] = {}
    if user_id is not None:
        me = repository.get(User).by_id(user_id)
        if me is not None:
            username_by_id[user_id] = me.username

    return ok(_row_to_dto(row, username_by_id))


@dataclass(frozen=True, slots=True)
class BackupSectionDto:
    """One entry of the section catalogue the Backup page builds its
    create-dialog, restore tree and report from. Mirrors `restore_shared.
    Section` minus the server-only parts (table name, key function,
    excluded columns)."""
    key: str
    label: str
    category: str
    default_on: bool
    sensitive: bool
    pickable: bool


@DATA_ROUTER.route("/backup/sections", methods=["GET"])
def list_backup_sections():
    """The section catalogue, straight from `restore_shared.SECTIONS`.

    The SPA used to carry a hand-copied mirror of this list and the two
    drifted: it named `product_barcodes` (the server key is `barcodes`), so
    every *New backup* with the default selection was refused with
    "Unknown backup section(s)", and it lacked the nine recipe vocabulary /
    step / link sections, so a backup made from the page silently omitted
    recipe steps, tools, tags, cuisines and categories (finalisation
    18-R2 / 18-R3). One source now; the page renders whatever this returns.
    """
    _, err = require_admin()
    if err is not None:
        return err
    return ok({
        "sections": [
            asdict(BackupSectionDto(
                key=s.backup_key,
                label=s.label,
                category=s.category,
                default_on=s.default_on,
                sensitive=s.sensitive,
                pickable=s.pickable,
            ))
            for s in SECTIONS
        ],
    })


@DATA_ROUTER.route("/backups", methods=["GET"])
def list_backups():
    _, err = require_admin()
    if err is not None:
        return err

    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        return bad_request("page must be an integer.")
    try:
        size = int(request.args.get("size", "50"))
    except ValueError:
        return bad_request("size must be an integer.")
    if page < 1 or size < 1 or size > 200:
        return bad_request("page ≥ 1, 1 ≤ size ≤ 200.")

    repository = SqlAlchemyRepository()
    all_rows = repository.get(Backup).all()
    all_sorted = sorted(all_rows, key=lambda r: r.created_at, reverse=True)
    total = len(all_sorted)
    start = (page - 1) * size
    page_rows = all_sorted[start:start + size]

    # Bulk-fetch usernames for the visible page in one query.
    actor_ids = {r.created_by_user_id for r in page_rows if r.created_by_user_id is not None}
    username_by_id: dict[UUID, str] = {}
    if actor_ids:
        user_table = db.metadata.tables["User"]
        rows = db.session.execute(
            select(user_table.c.id, user_table.c.username).where(
                user_table.c.id.in_(list(actor_ids)),
            )
        ).all()
        for uid, uname in rows:
            username_by_id[uid] = uname

    items = [_row_to_dto(r, username_by_id) for r in page_rows]
    return paginated(items, total, page, size)


@DATA_ROUTER.route("/backups/<uuid:backup_id>/download", methods=["GET"])
def download_backup(backup_id: UUID):
    _, err = require_admin()
    if err is not None:
        return err

    row = _resolve_backup(backup_id)
    if isinstance(row, Response):
        return row

    path = Path(row.storage_path)
    if not path.exists():
        return not_found("Backup file", backup_id)

    filename = f"dora-backup-{row.created_at.date().isoformat()}.json"
    return send_file(
        path,
        mimetype="application/json",
        as_attachment=True,
        download_name=filename,
    )


@DATA_ROUTER.route("/backups/<uuid:backup_id>/restore", methods=["POST"])
def restore_saved_backup(backup_id: UUID):
    _, err = require_admin()
    if err is not None:
        return err

    row = _resolve_backup(backup_id)
    if isinstance(row, Response):
        return row

    path = Path(row.storage_path)
    if not path.exists():
        return not_found("Backup file", backup_id)

    # Route through the existing restore handler. Its request shape
    # accepts either `upload_id` (external-file path) OR a document body;
    # library files bypass /uploads staging by pointing directly at the
    # saved path. `mode='all_skip_duplicates'` matches the external-file
    # default and keeps this endpoint one-click safe.
    body = _read_json(path)
    if isinstance(body, Response):
        return body

    restore_request = RestoreBackupRequest(
        mode="all_skip_duplicates",
        backup=body,
    )
    _Result = RestoreBackupHandler().handle(restore_request)
    if isinstance(_Result, str):
        _LOGGER.warning("Library restore failed: %s", _Result)
        if _Result.startswith("Restore failed and was rolled back"):
            return internal_server_error(_Result)
        return bad_request(_Result)

    return ok(_Result.model_dump())


@DATA_ROUTER.route("/backups/<uuid:backup_id>", methods=["DELETE"])
def delete_backup(backup_id: UUID):
    _, err = require_admin()
    if err is not None:
        return err

    row = _resolve_backup(backup_id)
    if isinstance(row, Response):
        return row

    _unlink_quiet(row.storage_path)
    repository = SqlAlchemyRepository()
    row = repository.get(Backup).by_id(row.id)
    if row is None:
        return not_found("Backup", backup_id)
    repository.remove(row)
    repository.save_changes()
    _LOGGER.info("Deleted backup %s", backup_id)
    return no_content()


# ── Internal helpers ───────────────────────────────────────────────────

def _resolve_backup(backup_id: UUID) -> Backup | Response:
    # R-033: callers now pass a real UUID (routes use the uuid converter, FU-544).
    row = SqlAlchemyRepository().get(Backup).by_id(backup_id)
    if row is None:
        return not_found("Backup", backup_id)
    return row


def _read_json(path: Path) -> dict | Response:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as exc:
        return internal_server_error(f"Could not read backup file: {exc}")
