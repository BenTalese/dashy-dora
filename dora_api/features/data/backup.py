"""Backup payload builder — shared by the library create endpoint.

Dumps every section listed in `SECTIONS` (restore_shared) column-by-column
to a single JSON document. Callers pass the set of section `backup_key`s
they want; the builder returns the ready-to-serialise payload + a
suggested filename.

Per-section `excluded_columns` (e.g. `password_hash` on User) are dropped
from the output and not restored either, so credentials never round-trip.

FU-342: the previous `GET /data/backup` download-only endpoint retired —
every backup now flows through the library
(`features/data/backup_library.py`). This module owns the *shape* of a
backup document; the library owns the *persistence* around it.
"""
import base64
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from dora_api.app import db
from dora_api.domain.entities.user import User
from dora_api.features.data.restore_shared import SECTIONS, SECTION_BY_BACKUP_KEY
from dora_api.infrastructure.ports import Repository


# Schema version for the on-disk format. Bump when the JSON shape changes in
# a way the restore endpoint can't tolerate.
BACKUP_SCHEMA_VERSION = 1


def resolve_selected_sections(
    requested: list[str] | None,
) -> tuple[frozenset[str] | None, str | None]:
    """Resolve a caller-supplied section list into a frozenset the builder
    can consume. `None` (or an empty list) falls back to every section
    flagged `default_on`. Returns `(sections, error)`; on error the sections
    slot is None and error carries a user-facing message."""
    if not requested:
        return frozenset(s.backup_key for s in SECTIONS if s.default_on), None
    unknown = set(requested) - set(SECTION_BY_BACKUP_KEY.keys())
    if unknown:
        return None, f"Unknown backup section(s): {', '.join(sorted(unknown))}."
    return frozenset(requested), None


def _encode_value(value: Any) -> Any:
    """Coerce SQLAlchemy row values into JSON-safe primitives. Bytes go to
    base64 so images round-trip without losing data."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return base64.b64encode(bytes(value)).decode("ascii")
    return value


def _dump_table(table_name: str, excluded_columns: frozenset[str]) -> list[dict[str, Any]]:
    table = db.metadata.tables[table_name]
    rows = db.session.execute(select(table)).all()
    column_names = [c.name for c in table.columns if c.name not in excluded_columns]
    indices = [i for i, c in enumerate(table.columns) if c.name not in excluded_columns]
    return [
        {column_names[k]: _encode_value(row[indices[k]]) for k in range(len(column_names))}
        for row in rows
    ]


@dataclass(slots=True)
class BackupResult:
    payload: dict[str, Any]
    filename: str
    exported_at: datetime


class GetBackupHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(
        self,
        exported_by_user_id: UUID | None,
        selected_keys: frozenset[str],
    ) -> BackupResult:
        username = "unknown"
        if exported_by_user_id is not None:
            user: User | None = self.repository.get(User).by_id(exported_by_user_id)
            if user is not None:
                username = user.username

        now_utc = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "schema_version": BACKUP_SCHEMA_VERSION,
            "exported_at": now_utc.isoformat(),
            "exported_by": username,
            # Honest record of which sections this backup carries — restore
            # can refuse to wipe non-included data on a future "replace, don't
            # merge" mode without re-deriving it from the entity list.
            "sections": sorted(selected_keys),
        }
        for section in SECTIONS:
            if section.backup_key not in selected_keys:
                continue
            payload[section.backup_key] = _dump_table(
                section.table_name, section.excluded_columns,
            )

        filename = f"dora-backup-{now_utc.date().isoformat()}.json"
        return BackupResult(payload=payload, filename=filename, exported_at=now_utc)
