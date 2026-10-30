"""POST /api/data/backup/restore — apply a (possibly partial) backup.

Round 2 of N2. Wraps the whole apply in a single SQLAlchemy transaction;
any error rolls back. Returns a structured summary of what landed, what
was skipped, and any FK-resolution warnings.

Two modes:
  - "all_skip_duplicates": import every row whose duplicate-key doesn't
    collide with an existing row.
  - "partial": import only the IDs the user selected. Hard-FK targets
    (locations, groups, recipe collections, parent locations, stock levels)
    are pulled in transparently. Soft-FK columns to missing targets are
    nulled with a warning. Required-FK rows whose target is missing are
    skipped with a warning.

Existing PKs are always skipped — we never overwrite. The user's expected
shape on an existing row is "don't touch it"; rename-on-collide is out of
scope and would surprise everyone.
"""
import json
import logging
import os
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import insert, select

from dora_api.app import db
from dora_api.features.auth.admin_gate import require_admin
from dora_api.features.data.backup import BACKUP_SCHEMA_VERSION
from dora_api.features.data.uploads import staged_path
from dora_api.features.data._errors import DataError, invalid, respond_to, rolled_back, upload_missing
from dora_api.features.data.restore_shared import (
    BACKUP_KEY_BY_TABLE_NAME,
    CHILD_AUTO_INCLUDE,
    DUPLICATE_KEY_BY_BACKUP_KEY,
    HARD_FK_PULL_IN,
    REMAP_ON_DUPLICATE,
    REQUIRED_FKS,
    RESTORE_ORDER,
    SECTION_BY_BACKUP_KEY,
    SOFT_FK_NULLABLE,
    TABLE_NAME_BY_BACKUP_KEY,
    composite_key,
    decode_value,
    primary_key_columns,
)
from dora_api.features.routers import DATA_ROUTER
from dora_api.infrastructure.api_response import ok
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body

_LOGGER = logging.getLogger(__name__)


MODE_ALL_SKIP_DUPLICATES = "all_skip_duplicates"
MODE_PARTIAL = "partial"
ALLOWED_MODES = (MODE_ALL_SKIP_DUPLICATES, MODE_PARTIAL)


def _join_table_sections() -> list[str]:
    """Backup keys of the pure join (m2m) tables — every section whose table
    has a composite primary key. Read off the live metadata so the list can
    never name a section the catalogue no longer has."""
    return [
        key for key, table_name in TABLE_NAME_BY_BACKUP_KEY.items()
        if len(primary_key_columns(db.metadata.tables[table_name])) > 1
    ]


def _is_blank_key(dup_key: Any) -> bool:
    """A duplicate key built from an empty name (e.g. the planner's nameless
    meal plans) collides with every other nameless row, so it identifies no
    single row to re-point children at."""
    return dup_key == "" or (isinstance(dup_key, tuple) and "" in dup_key)


def validate_fk_maps() -> None:
    """Fail at import, not at restore time, if an FK-policy map in
    `restore_shared` names a section or a column that no longer exists.

    The maps are the *policy* layer (which FKs pull parents in, which are
    nulled, which skip the row); the schema is the *plumbing*. They drift
    apart silently — `meal_plan_entries.meal_id` and the two `meal_recipes`
    rows outlived the meals→recipes rework for months — and a stale key
    is inert at best (a check that never fires) and a 500 at worst
    (finalisation 18-R1). Same shape as `import_spreadsheet.
    _validate_import_templates`.
    """
    def _check(section: str, column: str | None, where: str) -> None:
        table_name = TABLE_NAME_BY_BACKUP_KEY.get(section)
        if table_name is None:
            raise ValueError(
                f"restore_shared.{where} names section '{section}', which is not in SECTIONS."
            )
        if column is not None and column not in db.metadata.tables[table_name].columns:
            raise ValueError(
                f"restore_shared.{where} names column '{section}.{column}', "
                f"which does not exist on table '{table_name}'."
            )

    for (section, column), target in HARD_FK_PULL_IN.items():
        _check(section, column, "HARD_FK_PULL_IN")
        _check(target, None, "HARD_FK_PULL_IN (target)")
    for section, column in SOFT_FK_NULLABLE:
        _check(section, column, "SOFT_FK_NULLABLE")
    for section, column in REQUIRED_FKS:
        _check(section, column, "REQUIRED_FKS")
    for parent, child, child_fk in CHILD_AUTO_INCLUDE:
        _check(parent, None, "CHILD_AUTO_INCLUDE (parent)")
        _check(child, child_fk, "CHILD_AUTO_INCLUDE (child)")


validate_fk_maps()


class RestoreBackupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Exactly one of these must be set. `backup` carries the document
    # inline (small files, tests). `upload_id` references a file staged
    # via /api/data/uploads/* — the canonical path for the SPA now that
    # chunked-resumable uploads are the default.
    backup: dict[str, Any] | None = None
    # A UUID, validated here: `staged_path` joins it into a filesystem path.
    upload_id: UUID | None = None
    # Per-section list of selected IDs (or composite PK tuples encoded as
    # comma-joined strings for the m2m tables). Only consulted in "partial".
    selection: dict[str, list[str]] = Field(default_factory=dict)
    mode: str = MODE_ALL_SKIP_DUPLICATES


class RestoreSummary(BaseModel):
    created: dict[str, int]
    skipped: dict[str, int]
    warnings: list[str]


class RestoreBackupHandler:
    def handle(self, request: RestoreBackupRequest) -> RestoreSummary | DataError:
        # ── Resolve the backup document ───────────────────────────────
        backup, err = self._resolve_backup(request)
        if err is not None:
            return err

        # ── Validate envelope ─────────────────────────────────────────
        version = backup.get("schema_version")
        if not isinstance(version, int):
            return invalid("Backup is missing 'schema_version'.")
        if version > BACKUP_SCHEMA_VERSION:
            return invalid(
                f"Backup schema_version {version} is newer than this server "
                f"supports ({BACKUP_SCHEMA_VERSION})."
            )
        if request.mode not in ALLOWED_MODES:
            return invalid(f"Unknown mode '{request.mode}'.")

        # ── Index backup rows by (key, id) ────────────────────────────
        rows_by_key: dict[str, list[dict[str, Any]]] = {}
        rows_by_id: dict[str, dict[Any, dict[str, Any]]] = {}
        for backup_key, table_name in TABLE_NAME_BY_BACKUP_KEY.items():
            section = backup.get(backup_key, [])
            if not isinstance(section, list):
                return invalid(f"Section '{backup_key}' must be a list.")
            rows_by_key[backup_key] = section
            table = db.metadata.tables[table_name]
            pk_cols = primary_key_columns(table)
            rows_by_id[backup_key] = {
                composite_key(row, pk_cols): row for row in section
            }

        # ── Existing DB state for duplicate + FK checks ───────────────
        existing_pks: dict[str, set] = {}
        # duplicate key → the existing row's PK, or None when several existing
        # rows share the key (no single row to point a child at).
        existing_dup_keys: dict[str, dict[Any, str | None]] = {}
        for backup_key, table_name in TABLE_NAME_BY_BACKUP_KEY.items():
            table = db.metadata.tables[table_name]
            pk_cols = primary_key_columns(table)
            # Only the PK columns for presence — every section's whole table
            # used to be loaded, historic offers included, whether or not the
            # backup carried a row for it (finalisation 18-R28). Full rows are
            # read only for the sections that compute a duplicate key.
            pk_rows = db.session.execute(
                select(*[table.c[name] for name in pk_cols])
            ).all()
            existing_pks[backup_key] = {
                composite_key(dict(zip(pk_cols, r)), pk_cols) for r in pk_rows
            }
            if backup_key in DUPLICATE_KEY_BY_BACKUP_KEY:
                key_fn = DUPLICATE_KEY_BY_BACKUP_KEY[backup_key]
                column_names = [c.name for c in table.columns]
                existing_rows = db.session.execute(select(table)).all()
                by_dup_key: dict[Any, str | None] = {}
                for r in existing_rows:
                    existing_row = {col: r[idx] for idx, col in enumerate(column_names)}
                    dup_key = key_fn(existing_row)
                    existing_pk = composite_key(existing_row, pk_cols)
                    by_dup_key[dup_key] = (
                        None if dup_key in by_dup_key or len(existing_pk) != 1
                        else existing_pk[0]
                    )
                existing_dup_keys[backup_key] = by_dup_key

        # ── Build the selection set per section ───────────────────────
        # In "all_skip_duplicates" mode the selection is "everything";
        # in "partial" it starts from the user's picks and is expanded.
        selected: dict[str, set] = {k: set() for k in TABLE_NAME_BY_BACKUP_KEY}

        if request.mode == MODE_ALL_SKIP_DUPLICATES:
            for backup_key, section in rows_by_key.items():
                table = db.metadata.tables[TABLE_NAME_BY_BACKUP_KEY[backup_key]]
                pk_cols = primary_key_columns(table)
                for row in section:
                    selected[backup_key].add(composite_key(row, pk_cols))
        else:
            for backup_key, ids in request.selection.items():
                if backup_key not in selected:
                    return invalid(f"Unknown selection section '{backup_key}'.")
                # IDs come from the SPA as strings; m2m composite IDs come
                # as "<id>|<id>" so we round-trip the same string here.
                for raw_id in ids:
                    selected[backup_key].add((raw_id,) if "|" not in raw_id else tuple(raw_id.split("|")))

            # Children of selected parents ride along.
            for parent_key, child_key, child_fk_col in CHILD_AUTO_INCLUDE:
                # Each parent_pk is single-column for the tables in this map.
                selected_parent_ids = {pk[0] for pk in selected[parent_key]}
                child_table = db.metadata.tables[TABLE_NAME_BY_BACKUP_KEY[child_key]]
                child_pk_cols = primary_key_columns(child_table)
                for row in rows_by_key[child_key]:
                    if str(row.get(child_fk_col)) in selected_parent_ids:
                        selected[child_key].add(composite_key(row, child_pk_cols))

            # Hard-FK pull-in: locations, groups, recipe collections, levels,
            # location parents. Run to fixed point so a deeply nested
            # location subtree fully expands.
            changed = True
            while changed:
                changed = False
                for (src_key, fk_col), target_key in HARD_FK_PULL_IN.items():
                    target_table = db.metadata.tables[TABLE_NAME_BY_BACKUP_KEY[target_key]]
                    target_pk_cols = primary_key_columns(target_table)
                    for src_pk in list(selected[src_key]):
                        src_row = rows_by_id[src_key].get(src_pk)
                        if src_row is None:
                            continue
                        fk_value = src_row.get(fk_col)
                        if not fk_value:
                            continue
                        target_pk = (str(fk_value),)
                        if target_pk in selected[target_key]:
                            continue
                        # Already in DB? Nothing to do.
                        if target_pk in existing_pks[target_key]:
                            continue
                        # Only pull in if the backup actually carries it.
                        if rows_by_id[target_key].get(target_pk) is None:
                            continue
                        selected[target_key].add(target_pk)
                        changed = True

            # m2m join rows where both endpoints land (in DB or in selection)
            # ride along automatically. Derived from the catalogue rather than
            # listed by hand: the hand-written tuple kept `meal_recipes` after
            # the meals→recipes rework removed that section, so every partial
            # restore raised `KeyError` here before touching a row
            # (finalisation 18-R1).
            for backup_key in _join_table_sections():
                table = db.metadata.tables[TABLE_NAME_BY_BACKUP_KEY[backup_key]]
                pk_cols = primary_key_columns(table)
                for row in rows_by_key[backup_key]:
                    pk = composite_key(row, pk_cols)
                    # Both endpoint targets must be either pre-existing or in selection.
                    endpoints_ok = True
                    for col in pk_cols:
                        target_key = self._resolve_fk_target(backup_key, col)
                        if target_key is None:
                            continue
                        target_pk = (str(row.get(col)),)
                        if (
                            target_pk not in existing_pks.get(target_key, set())
                            and target_pk not in selected[target_key]
                        ):
                            endpoints_ok = False
                            break
                    if endpoints_ok:
                        selected[backup_key].add(pk)

        # ── Apply in dependency order ─────────────────────────────────
        created: dict[str, int] = {}
        skipped: dict[str, int] = {}
        warnings: list[str] = []

        # FK-target tracker: union of pre-existing PKs and freshly-inserted
        # ones. Lets a later row find an earlier sibling without round-tripping.
        present_pks: dict[str, set] = {k: set(v) for k, v in existing_pks.items()}
        # Backup PK → existing PK for rows skipped as duplicates (same name,
        # different id), so their children re-point at the row that stayed
        # instead of having the FK nulled or the row dropped.
        remapped_pks: dict[str, dict[str, str]] = {k: {} for k in TABLE_NAME_BY_BACKUP_KEY}

        try:
            for backup_key in RESTORE_ORDER:
                table = db.metadata.tables[TABLE_NAME_BY_BACKUP_KEY[backup_key]]
                pk_cols = primary_key_columns(table)
                created[backup_key] = 0
                skipped[backup_key] = 0

                for row in rows_by_key[backup_key]:
                    pk = composite_key(row, pk_cols)

                    if pk not in selected[backup_key]:
                        continue
                    if pk in present_pks[backup_key]:
                        skipped[backup_key] += 1
                        continue
                    if backup_key in DUPLICATE_KEY_BY_BACKUP_KEY:
                        key_fn = DUPLICATE_KEY_BY_BACKUP_KEY[backup_key]
                        dup_key = key_fn(row)
                        if dup_key in existing_dup_keys[backup_key]:
                            existing_pk = existing_dup_keys[backup_key][dup_key]
                            if (
                                backup_key in REMAP_ON_DUPLICATE
                                and existing_pk is not None
                                and not _is_blank_key(dup_key)
                            ):
                                remapped_pks[backup_key][pk[0]] = existing_pk
                            skipped[backup_key] += 1
                            continue

                    decoded, row_warnings, skip_row = self._decode_row(
                        backup_key, table, row, present_pks, remapped_pks
                    )
                    warnings.extend(row_warnings)
                    if skip_row:
                        skipped[backup_key] += 1
                        continue

                    # A join row's PK is its FKs, so a remap can turn it into a
                    # pair that already exists — re-key it after decoding and
                    # skip the collision instead of tripping the PK.
                    decoded_pk = composite_key(decoded, pk_cols)
                    if decoded_pk != pk and decoded_pk in present_pks[backup_key]:
                        skipped[backup_key] += 1
                        continue
                    if backup_key == "product_stock_item_links" and self._product_already_linked(
                        table, decoded, present_pks[backup_key]
                    ):
                        # UNIQUE(product_id): the remapped product is linked to
                        # another item already.
                        skipped[backup_key] += 1
                        continue

                    db.session.execute(insert(table).values(**decoded))
                    present_pks[backup_key].add(decoded_pk)
                    created[backup_key] += 1

            db.session.commit()
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            _LOGGER.exception("Restore failed; rolled back.")
            return rolled_back("Restore", exc)

        return RestoreSummary(created=created, skipped=skipped, warnings=warnings)

    @staticmethod
    def _resolve_backup(req: RestoreBackupRequest) -> tuple[dict | None, DataError | None]:
        """Pull the backup document out of either the inline body or a
        staged upload. Consumes (unlinks) the staged file on success so
        the upload area doesn't accumulate one stale .bin per restore.
        """
        if req.backup is not None and req.upload_id is not None:
            return None, invalid("Provide exactly one of 'backup' or 'upload_id'.")
        if req.backup is not None:
            return req.backup, None
        if req.upload_id is None:
            return None, invalid("Either 'backup' or 'upload_id' is required.")
        path = staged_path(str(req.upload_id))
        if not path.exists():
            return None, upload_missing(str(req.upload_id))
        try:
            with open(path, "rb") as fh:
                doc = json.load(fh)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return None, invalid(f"Could not parse staged upload as JSON ({exc}).")
        if not isinstance(doc, dict):
            return None, invalid("Staged upload is not a JSON object.")
        # Consume — the upload was successfully loaded; subsequent calls
        # with the same id will 404 (which is the intent).
        try:
            os.unlink(path)
        except OSError:
            pass
        return doc, None

    @staticmethod
    def _resolve_fk_target(backup_key: str, column: str) -> str | None:
        # Read the FK target from the SQLAlchemy table definition. Returns
        # the backup_key of the target table, or None for non-FK columns.
        table = db.metadata.tables[TABLE_NAME_BY_BACKUP_KEY[backup_key]]
        col = table.columns.get(column)
        if col is None or not col.foreign_keys:
            return None
        target_table_name = next(iter(col.foreign_keys)).column.table.name
        return BACKUP_KEY_BY_TABLE_NAME.get(target_table_name)

    @staticmethod
    def _product_already_linked(table, decoded: dict[str, Any], present: set) -> bool:
        product_id = str(decoded.get("product_id"))
        return any(pk[1] == product_id for pk in present if len(pk) == 2)

    def _decode_row(
        self,
        backup_key: str,
        table,
        row: dict[str, Any],
        present_pks: dict[str, set],
        remapped_pks: dict[str, dict[str, str]],
    ) -> tuple[dict[str, Any], list[str], bool]:
        """Returns (decoded_row, warnings, skip_row)."""
        decoded: dict[str, Any] = {}
        warnings: list[str] = []
        excluded = SECTION_BY_BACKUP_KEY[backup_key].excluded_columns
        for col in table.columns:
            if col.name in excluded:
                # Never restore excluded columns (e.g. password hashes), even
                # if a malformed backup somehow carries them.
                continue
            if col.name not in row:
                # An older backup predates this column: leave it out of the
                # INSERT so its server/column default applies, rather than an
                # explicit NULL that a NOT NULL default column rejects.
                continue
            raw = row.get(col.name)
            value = decode_value(raw, col.type)

            # FK resolution
            target_key = self._resolve_fk_target(backup_key, col.name)
            if target_key is not None and value is not None:
                remapped = remapped_pks.get(target_key, {}).get(str(value))
                if remapped is not None:
                    value = decode_value(remapped, col.type)
                target_pk = (str(value),)
                if target_pk not in present_pks.get(target_key, set()):
                    # Target missing.
                    if (backup_key, col.name) in SOFT_FK_NULLABLE:
                        warnings.append(
                            f"{backup_key}.{col.name}: target {value} not present; "
                            f"set to null."
                        )
                        value = None
                    elif (backup_key, col.name) in REQUIRED_FKS:
                        warnings.append(
                            f"{backup_key} row {row.get('id') or '<m2m>'} skipped: "
                            f"required {col.name}={value} not present."
                        )
                        return decoded, warnings, True
                    elif col.nullable:
                        warnings.append(
                            f"{backup_key}.{col.name}: target {value} not present; "
                            f"set to null."
                        )
                        value = None
                    else:
                        warnings.append(
                            f"{backup_key} row {row.get('id') or '<m2m>'} skipped: "
                            f"{col.name}={value} not present."
                        )
                        return decoded, warnings, True

            decoded[col.name] = value
        return decoded, warnings, False


@DATA_ROUTER.route("/backup/restore", methods=["POST"])
@has_request_body(RestoreBackupRequest)
def restore_backup():
    # restore inserts arbitrary rows across every
    # table (users, app_settings, historic offers). Any authenticated
    # caller could invoke it before; the gate closes that HIGH-severity
    # hole.
    _, err = require_admin()
    if err is not None:
        return err
    _Request: RestoreBackupRequest = get_request_body()
    _Result = RestoreBackupHandler().handle(_Request)
    if isinstance(_Result, DataError):
        _LOGGER.warning("Restore validation failed: %s", _Result.detail)
        return respond_to(_Result)
    summary = _Result.model_dump()
    _LOGGER.info(
        "Restore complete: created=%s skipped=%s warnings=%d",
        summary["created"], summary["skipped"], len(summary["warnings"]),
    )
    return ok(summary)
