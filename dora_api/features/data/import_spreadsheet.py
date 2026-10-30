"""Spreadsheet import — Data → Import → Spreadsheet.

Two endpoints:
  POST /api/data/import/spreadsheet/inspect
      Body: {"upload_id": "<staged-uuid>"}
      Returns: { sheets, preview_rows, detected_columns, auto_mapping }
  POST /api/data/import/spreadsheet/commit
      Body: { upload_id, sheet, column_map, options }
      Returns: { summary: {created, skipped, errors}, rows: [...] }

The user uploads via the existing chunked-upload stack
(POST /api/data/uploads/*) and passes the resulting `upload_id` to both
endpoints. Inspect leaves the staged file in place; commit consumes it.

Supported formats: .xlsx (via openpyxl) and .csv (stdlib `csv` module).
Detection is by extension fallback to magic bytes; the SPA passes the
filename so we know which path to take.

Mapping is opinionated:
  required: name
  optional: level, location, group, expiry, is_essential
The frontend's column-mapping UI sets which spreadsheet column feeds
each target. `is_essential` maps directly to StockItem.is_essential.

Row-level errors carry the row number, the offending value, and a
human-readable reason. Halt-on-error aborts the whole transaction;
otherwise the valid rows still land and the errors are surfaced row-by-
row in the response.
"""
import csv
import io
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from flask import Response, request
from pydantic import BaseModel, ConfigDict, Field

from dora_api.app import db
from dora_api.domain.entities.stock_group import StockGroup
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_level import StockLevel
from dora_api.domain.entities.stock_location import LOCATION_KIND_ZONE, StockLocation
from dora_api.domain.stock_status import StockStatus, level_for_status
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.features.auth.admin_gate import require_admin
from dora_api.features.data._errors import DataError, invalid, respond_to, rolled_back, upload_missing
from dora_api.features.data.uploads import staged_path
from dora_api.features.routers import DATA_ROUTER
from dora_api.infrastructure.api_response import not_found, ok
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


# Target fields with their synonyms for auto-mapping. Lowercased,
# trimmed, punctuation stripped before matching.
TARGET_FIELDS: tuple[str, ...] = (
    "name", "level", "location", "group", "expiry", "is_essential",
)
COLUMN_SYNONYMS: dict[str, tuple[str, ...]] = {
    "name": ("name", "item", "itemname", "product", "productname", "title"),
    "level": ("level", "stocklevel", "stock", "status", "quantity"),
    "location": ("location", "where", "place", "shelf", "pantry", "spot"),
    "group": ("group", "category", "tag", "type", "kind"),
    "expiry": ("expiry", "bestbefore", "useby", "expires", "expiration", "expirydate"),
    "is_essential": ("isessential", "essential", "essentials", "flagged", "important", "starred"),
}

# How many rows to ship back in the preview from /inspect.
PREVIEW_ROW_COUNT = 5


def _normalise_header(value: str) -> str:
    """Lowercase + strip whitespace and punctuation for fuzzy column matching."""
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _is_truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    s = str(value).strip().lower()
    return s in {"y", "yes", "true", "1", "t", "on", "x", "✓"}


def _coerce_to_date(value: Any, day_first: bool = True) -> date | None:
    """Accept date / datetime / ISO string / common locale strings. Returns
    None for empty cells; raises ValueError for unparseable non-empty values.
    """
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        # ISO first; then slash / dash dates in the *install's* day-month
        # order (`AppSetting.locale`, the one authority — finalisation 18-R12:
        # `03/04/2027` is 3 April on `en-AU` and 4 March on `en-US`), with the
        # other order as a last resort for the unambiguous cases.
        regional = ("%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y") if day_first else ("%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y")
        for fmt in ("%Y-%m-%d", *regional):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
    raise ValueError(f"Could not parse '{value}' as a date.")


def _read_sheets(path: str, filename: str) -> dict[str, list[list[Any]]]:
    """Returns {sheet_name: [row_0, row_1, ...]} for any supported format.
    Row 0 is the header row. Cells preserve their original Python types
    (openpyxl returns datetime/int/etc.; csv returns strings).
    """
    lower = filename.lower()
    if lower.endswith(".csv"):
        # CSVs are single-sheet; we synthesise one named after the file.
        with open(path, "rb") as raw:
            data = raw.read()
        # UTF-8 with BOM is common from Excel; sniff and strip.
        if data.startswith(b"\xef\xbb\xbf"):
            data = data[3:]
        text = data.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = _strip_comment_rows([row for row in reader])
        sheet_name = os.path.basename(filename) or "csv"
        return {sheet_name: rows}

    if lower.endswith(".xlsx"):
        # Importing here so installs without openpyxl don't blow up the
        # whole api on module import (only matters if you actually try to
        # import a spreadsheet).
        from openpyxl import load_workbook
        wb = load_workbook(filename=path, read_only=True, data_only=True)
        try:
            out: dict[str, list[list[Any]]] = {}
            for sheet in wb.sheetnames:
                ws = wb[sheet]
                rows: list[list[Any]] = []
                for row in ws.iter_rows(values_only=True):
                    rows.append(list(row))
                out[sheet] = _strip_comment_rows(rows)
            return out
        finally:
            wb.close()

    raise ValueError(
        f"Unsupported file type for spreadsheet import: '{filename}'. "
        "Supported: .xlsx, .csv."
    )


def _strip_comment_rows(rows: list[list[Any]]) -> list[list[Any]]:
    """FU-349 — drop rows whose first cell begins with ``#``.

    The downloaded templates include one or more `#`-prefixed rows that
    explain the illustrative example values (see `ImportTemplate.
    comment_rows`). If the user re-uploads the file without deleting the
    hint row, the parser must not treat it as a data row — otherwise the
    commit path would try to import "example values are illustrative…"
    as a stock item name.

    Row 0 is preserved unconditionally: it's the header row, and a user
    who deleted headers and put a `#` line at the top would want us to
    surface the failure honestly rather than silently reshape the sheet.
    """
    if not rows:
        return rows
    kept: list[list[Any]] = [rows[0]]
    for row in rows[1:]:
        if _is_comment_row(row):
            continue
        kept.append(row)
    return kept


def _is_comment_row(row: list[Any]) -> bool:
    if not row:
        return False
    first = row[0]
    if first is None:
        return False
    return str(first).strip().startswith("#")


def _build_auto_mapping(headers: list[str]) -> dict[str, str | None]:
    """Pick the most-likely spreadsheet column for each target field."""
    normalised = [(_normalise_header(h or ""), h) for h in headers]
    mapping: dict[str, str | None] = {field: None for field in TARGET_FIELDS}
    used: set[str] = set()
    for target in TARGET_FIELDS:
        for synonym in COLUMN_SYNONYMS[target]:
            for norm, original in normalised:
                if not norm or original in used:
                    continue
                if norm == synonym:
                    mapping[target] = original
                    used.add(original)
                    break
            if mapping[target] is not None:
                break
        if mapping[target] is not None:
            continue
        # Fall back to substring match if no exact synonym landed.
        for synonym in COLUMN_SYNONYMS[target]:
            for norm, original in normalised:
                if not norm or original in used:
                    continue
                if synonym in norm:
                    mapping[target] = original
                    used.add(original)
                    break
            if mapping[target] is not None:
                break
    return mapping


# ── Inspect ────────────────────────────────────────────────────────────

class InspectSpreadsheetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # A UUID, validated here: `staged_path` joins it into a filesystem path.
    upload_id: UUID
    filename: str = Field(min_length=1)


@dataclass(slots=True)
class InspectSpreadsheetResponse:
    sheets: list[str]
    preview_rows: dict[str, list[list[Any]]]
    detected_columns: dict[str, list[str]]
    auto_mapping: dict[str, dict[str, str | None]]
    target_fields: list[str]
    warnings: list[str] = field(default_factory=list)


class InspectSpreadsheetHandler:
    def handle(self, request: InspectSpreadsheetRequest) -> InspectSpreadsheetResponse | DataError:
        path = staged_path(str(request.upload_id))
        if not path.exists():
            return upload_missing(str(request.upload_id))
        try:
            sheets = _read_sheets(str(path), request.filename)
        except ValueError as exc:
            return invalid(str(exc))
        except Exception as exc:  # noqa: BLE001
            _LOGGER.exception("Failed to read spreadsheet.")
            return invalid(f"Could not read spreadsheet: {exc}")

        sheet_names = list(sheets.keys())
        preview_rows: dict[str, list[list[Any]]] = {}
        detected_columns: dict[str, list[str]] = {}
        auto_mapping: dict[str, dict[str, str | None]] = {}
        warnings: list[str] = []

        for name in sheet_names:
            rows = sheets[name]
            if not rows:
                detected_columns[name] = []
                preview_rows[name] = []
                auto_mapping[name] = {f: None for f in TARGET_FIELDS}
                warnings.append(f"Sheet '{name}' is empty.")
                continue

            header = [str(h) if h is not None else "" for h in rows[0]]
            detected_columns[name] = header

            # JSON-serialise dates/datetimes/bytes etc.; cells we can't
            # represent cleanly fall back to str().
            sample = []
            for row in rows[1:1 + PREVIEW_ROW_COUNT]:
                cells = []
                for value in row:
                    if isinstance(value, (date, datetime)):
                        cells.append(value.isoformat())
                    elif isinstance(value, bytes):
                        cells.append(value.decode("utf-8", errors="replace"))
                    elif value is None or isinstance(value, (str, int, float, bool)):
                        cells.append(value)
                    else:
                        cells.append(str(value))
                sample.append(cells)
            preview_rows[name] = sample

            mapping = _build_auto_mapping(header)
            auto_mapping[name] = mapping
            if mapping["name"] is None:
                warnings.append(
                    f"Sheet '{name}': couldn't auto-detect a Name column. "
                    f"Pick one manually."
                )

        return InspectSpreadsheetResponse(
            sheets=sheet_names,
            preview_rows=preview_rows,
            detected_columns=detected_columns,
            auto_mapping=auto_mapping,
            target_fields=list(TARGET_FIELDS),
            warnings=warnings,
        )


@DATA_ROUTER.route("/import/spreadsheet/inspect", methods=["POST"])
@has_request_body(InspectSpreadsheetRequest)
def inspect_spreadsheet():
    # import inserts arbitrary stock rows across
    # the install. Same admin gate as backup restore.
    _, err = require_admin()
    if err is not None:
        return err
    _Request: InspectSpreadsheetRequest = get_request_body()
    _Result = InspectSpreadsheetHandler().handle(_Request)
    if isinstance(_Result, DataError):
        return respond_to(_Result)
    # `field`s on the dataclass don't serialise via jsonify directly; convert.
    return ok({
        "sheets": _Result.sheets,
        "preview_rows": _Result.preview_rows,
        "detected_columns": _Result.detected_columns,
        "auto_mapping": _Result.auto_mapping,
        "target_fields": _Result.target_fields,
        "warnings": _Result.warnings,
    })


# ── Commit ─────────────────────────────────────────────────────────────

class ImportOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skip_duplicates: bool = True
    create_missing_locations: bool = False
    create_missing_groups: bool = False
    halt_on_error: bool = False


class CommitSpreadsheetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # A UUID, validated here: `staged_path` joins it into a filesystem path.
    upload_id: UUID
    filename: str = Field(min_length=1)
    sheet: str = Field(min_length=1)
    column_map: dict[str, str | None]
    options: ImportOptions = Field(default_factory=ImportOptions)


@dataclass(slots=True)
class RowReport:
    row_number: int
    status: str           # "created" | "skipped_duplicate" | "error"
    name: str
    reason: str | None = None


@dataclass(slots=True)
class CommitSpreadsheetResponse:
    summary: dict[str, int]
    rows: list[RowReport]


class CommitSpreadsheetHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: CommitSpreadsheetRequest) -> CommitSpreadsheetResponse | DataError:
        path = staged_path(str(request.upload_id))
        if not path.exists():
            return upload_missing(str(request.upload_id))

        # ── Read spreadsheet ─────────────────────────────────────────
        try:
            sheets = _read_sheets(str(path), request.filename)
        except ValueError as exc:
            return invalid(str(exc))
        except Exception as exc:  # noqa: BLE001
            _LOGGER.exception("Failed to read spreadsheet on commit.")
            return invalid(f"Could not read spreadsheet: {exc}")

        if request.sheet not in sheets:
            return invalid(f"Sheet '{request.sheet}' is not in the uploaded file.")

        rows = sheets[request.sheet]
        if not rows:
            return invalid(f"Sheet '{request.sheet}' is empty.")

        # 2026-08-20 — same install-wide default `create_stock_item` uses, read
        # once for the whole import rather than per row (R-003: one authority
        # for "does a new item join the stocktake rotation").
        setting = get_or_create_app_setting(self.repository)
        # Day/month order for slash dates follows the install locale (18-R12).
        day_first = not (setting.locale or "").lower().startswith("en-us")
        stocktake_opt_in = bool(getattr(
            setting,
            "stocktake_new_items_opt_in",
            True,
        ))

        header = [str(h) if h is not None else "" for h in rows[0]]
        # name is mandatory; if the user mapped no Name column we can't
        # do anything useful — fail before touching the DB.
        if not request.column_map.get("name"):
            return invalid("A column must be mapped to 'name' before importing.")
        for col_name in request.column_map.values():
            if col_name is None:
                continue
            if col_name not in header:
                return invalid(f"Column '{col_name}' is not in sheet '{request.sheet}'.")

        # Every target but `name` is optional: an unmapped one is simply absent
        # from `column_map`, so the reads below use `.get` (None = unmapped).
        col_index: dict[str, int | None] = {
            target: (header.index(col) if col is not None and col in header else None)
            for target, col in request.column_map.items()
        }

        # ── Index existing entities for FK + duplicate resolution ────
        # Names only — the ids were never read (finalisation 18-R24).
        existing_item_names: set[str] = {
            (it.name or "").strip().lower() for it in self.repository.get(StockItem).all()
        }
        existing_groups = self.repository.get(StockGroup).all()
        existing_group_names: dict[str, StockGroup] = {
            (g.name or "").strip().lower(): g for g in existing_groups
        }
        existing_locations = self.repository.get(StockLocation).all()
        existing_location_names: dict[str, StockLocation] = {
            (loc.name or "").strip().lower(): loc for loc in existing_locations
        }
        existing_levels = self.repository.get(StockLevel).all()
        level_choices = sorted({lvl.name for lvl in existing_levels})

        # ── Iterate body rows ────────────────────────────────────────
        reports: list[RowReport] = []
        created = 0
        skipped = 0
        errors = 0

        try:
            for offset, row in enumerate(rows[1:], start=2):  # 1-based, header = row 1
                row_name_raw = (
                    row[col_index["name"]]
                    if col_index["name"] is not None and col_index["name"] < len(row)
                    else None
                )
                row_name = (str(row_name_raw).strip() if row_name_raw is not None else "")

                if not row_name:
                    # Don't error on entirely blank rows — common at end of
                    # CSV. Skip silently. But if any other mapped column has
                    # data, surface it as a real error.
                    if all(
                        (v is None or str(v).strip() == "")
                        for v in row
                    ):
                        continue
                    reports.append(RowReport(
                        row_number=offset, status="error",
                        name="", reason="Missing 'name' value.",
                    ))
                    errors += 1
                    if request.options.halt_on_error:
                        raise _HaltOnError()
                    continue

                # Duplicate check.
                if row_name.lower() in existing_item_names and request.options.skip_duplicates:
                    reports.append(RowReport(
                        row_number=offset, status="skipped_duplicate", name=row_name,
                    ))
                    skipped += 1
                    continue

                # Resolve foreign keys.
                try:
                    stock_level = self._resolve_level(
                        row, col_index.get("level"), existing_levels, level_choices,
                    )
                    stock_location = self._resolve_location(
                        row, col_index.get("location"),
                        existing_location_names, request.options.create_missing_locations,
                    )
                    stock_group = self._resolve_group(
                        row, col_index.get("group"),
                        existing_group_names, request.options.create_missing_groups,
                    )
                    expiry_idx = col_index.get("expiry")
                    expiry = (
                        _coerce_to_date(row[expiry_idx], day_first=day_first)
                        if expiry_idx is not None and expiry_idx < len(row)
                        else None
                    )
                    essential_idx = col_index.get("is_essential")
                    is_essential = (
                        _is_truthy(row[essential_idx])
                        if essential_idx is not None and essential_idx < len(row)
                        else False
                    )
                except _RowError as exc:
                    reports.append(RowReport(
                        row_number=offset, status="error",
                        name=row_name, reason=exc.reason,
                    ))
                    errors += 1
                    if request.options.halt_on_error:
                        raise _HaltOnError()
                    continue

                # Through the repository like `create_stock_item` (R-005;
                # finalisation 18-R20 — this was a raw table insert), with the
                # UTC stamp every other writer uses (18-R4; it was naive local).
                self.repository.add(StockItem(
                    name=row_name,
                    notes=None,
                    stock_group=stock_group,
                    stock_level=stock_level,
                    stock_level_last_updated=datetime.now(timezone.utc),
                    stock_location=stock_location,
                    # Matches the hand-created default (2026-08-17, now the
                    # install-wide `stocktake_new_items_opt_in` setting) — an
                    # imported item is still one the user chose to track.
                    stocktake_alerts_are_enabled=stocktake_opt_in,
                    expiry_date=expiry,
                    is_essential=is_essential,
                    is_open=False,
                ))
                existing_item_names.add(row_name.lower())  # downstream dup checks
                reports.append(RowReport(
                    row_number=offset, status="created", name=row_name,
                ))
                created += 1

            self.repository.save_changes()
        except _HaltOnError:
            db.session.rollback()
            return CommitSpreadsheetResponse(
                summary={"created": 0, "skipped": 0, "errors": errors, "halted": 1},
                rows=reports,
            )
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            _LOGGER.exception("Spreadsheet import failed; rolled back.")
            return rolled_back("Import", exc)

        # Successful commit — consume the staged file so the upload area
        # doesn't accumulate.
        try:
            path.unlink()
        except OSError:
            pass

        return CommitSpreadsheetResponse(
            summary={"created": created, "skipped": skipped, "errors": errors, "halted": 0},
            rows=reports,
        )

    @staticmethod
    def _resolve_level(
        row: list[Any], idx: int | None,
        existing_levels: list[StockLevel], choices: list[str],
    ) -> StockLevel | None:
        # Pick a sensible default — the Stocked level (resolved by status
        # identity, not name) is the "you have it" starting point; users can
        # edit individual items post-import.
        stocked = level_for_status(existing_levels, StockStatus.STOCKED)
        default = stocked or (existing_levels[0] if existing_levels else None)
        if idx is None or idx >= len(row):
            return default
        raw = row[idx]
        if raw is None or str(raw).strip() == "":
            return default
        needle = str(raw).strip().lower()
        # Case-insensitive substring match; "low" matches "Low Stock", etc.
        matches = [lvl for lvl in existing_levels if needle in lvl.name.lower()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            # Prefer an exact (case-insensitive) match if one is in the set.
            exact = [lvl for lvl in matches if lvl.name.lower() == needle]
            if exact:
                return exact[0]
            raise _RowError(
                f"Stock level '{raw}' is ambiguous; matches multiple of "
                f"{', '.join(lvl.name for lvl in matches)}."
            )
        raise _RowError(
            f"Stock level '{raw}' isn't recognised. Valid options: "
            f"{', '.join(choices)}."
        )

    def _resolve_location(
        self, row: list[Any], idx: int | None,
        existing: dict[str, Any], allow_create: bool,
    ):
        if idx is None or idx >= len(row):
            return None
        raw = row[idx]
        if raw is None or str(raw).strip() == "":
            return None
        key = str(raw).strip().lower()
        if key in existing:
            return existing[key]
        if not allow_create:
            raise _RowError(
                f"Location '{raw}' doesn't exist. Tick 'Create missing locations' "
                f"to add it on the fly."
            )
        # Auto-create as a zone (the simplest level of the hierarchy).
        location = StockLocation(name=str(raw).strip(), kind=LOCATION_KIND_ZONE, parent_id=None, sequence=0)
        self.repository.add(location)
        existing[key] = location
        return location

    def _resolve_group(
        self, row: list[Any], idx: int | None,
        existing: dict[str, Any], allow_create: bool,
    ):
        if idx is None or idx >= len(row):
            return None
        raw = row[idx]
        if raw is None or str(raw).strip() == "":
            return None
        key = str(raw).strip().lower()
        if key in existing:
            return existing[key]
        if not allow_create:
            raise _RowError(
                f"Group '{raw}' doesn't exist. Tick 'Create missing groups' "
                f"to add it on the fly."
            )
        group = StockGroup(name=str(raw).strip())
        self.repository.add(group)
        existing[key] = group
        return group


class _RowError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class _HaltOnError(Exception):
    pass


@DATA_ROUTER.route("/import/spreadsheet/commit", methods=["POST"])
@has_request_body(CommitSpreadsheetRequest)
def commit_spreadsheet():
    _, err = require_admin()
    if err is not None:
        return err
    _Request: CommitSpreadsheetRequest = get_request_body()
    _Result = CommitSpreadsheetHandler(SqlAlchemyRepository()).handle(_Request)
    if isinstance(_Result, DataError):
        return respond_to(_Result)
    return ok({
        "summary": _Result.summary,
        "rows": [
            {
                "row_number": r.row_number,
                "status": r.status,
                "name": r.name,
                "reason": r.reason,
            }
            for r in _Result.rows
        ],
    })


# ── Templates (FU-343) ─────────────────────────────────────────────────
#
# Downloadable per-section CSV templates so users don't have to guess the
# schema. Headers come straight from `TARGET_FIELDS` above (the same
# source of truth the auto-mapping + commit paths read) so a template
# can never drift from what the importer accepts. CSV-only for now;
# `.xlsx` with dropdown validation is a deferred follow-on (see FU-343
# discussion — ship CSV first, revisit if users ask).
#
# Only stock_items is a real "section" today. The endpoint is scoped as
# a section index so the frontend affordance stays the same shape when
# more sections land later (recipes, shopping lists, etc.).


@dataclass(slots=True)
class ImportTemplate:
    section: str
    label: str
    caption: str
    headers: tuple[str, ...]
    # FU-350 — one-line example row keyed by field name (was a positional
    # `tuple[str, ...]`). Keying by name means reordering `TARGET_FIELDS`
    # or renaming a column can't silently misalign the example cells
    # under the wrong headers — the CSV writer projects `example` through
    # `headers` at emit time (see `download_import_template` below).
    # Missing keys emit as an empty cell (optional fields may be blank).
    # Cross-checked at module load — see `_validate_import_templates`.
    example: dict[str, str]
    # FU-349 — additional rows written after the example, each prefixed
    # with `#` so `_read_sheets` treats them as comments and strips them
    # on re-upload. Used to warn users that the illustrative
    # level/location/group names may not match their install.
    comment_rows: tuple[tuple[str, ...], ...] = ()


# FU-349 (option A) — comment rows travel with the downloaded template so
# a user opening the CSV in Excel/Numbers can read *why* the example row's
# level/location/group names may not match their install (the seeded
# StockLevel / StockLocation / StockGroup rows are user-editable, so the
# defaults "In stock" / "Pantry" / "Grains" are illustrative, not truth).
# The parser (`_read_sheets` → `_strip_comment_rows`) skips any row whose
# first cell begins with `#`, so this row round-trips harmlessly if the
# user re-uploads the same file without deleting it.
_COMMENT_ROW_STOCK_ITEMS: tuple[str, ...] = (
    "# example values are illustrative — replace them, "
    "and use your own level/location/group names (see Settings → Kitchen setup).",
)


IMPORT_TEMPLATES: tuple[ImportTemplate, ...] = (
    ImportTemplate(
        section="stock_items",
        label="Stock items",
        caption="One row per pantry item. Only `name` is required; the rest are optional.",
        headers=TARGET_FIELDS,
        # Example values are illustrative — the level / location / group
        # matchers are name-based, so any string that resembles an existing
        # entity is a valid starting point for a real import. The user-
        # facing "these are placeholders" hint travels next to the row in
        # the CSV as a `#`-prefixed comment line (see FU-349 /
        # `_COMMENT_ROW_STOCK_ITEMS`); the parser strips comment rows
        # before commit.
        # FU-350 — keyed by field name (was positional). Reordering
        # `TARGET_FIELDS` or adding a seventh field can no longer silently
        # misalign the example row.
        example={
            "name": "Rice",
            "level": "In stock",
            "location": "Pantry",
            "group": "Grains",
            "expiry": "2027-01-01",
            "is_essential": "no",
        },
        comment_rows=(_COMMENT_ROW_STOCK_ITEMS,),
    ),
)

IMPORT_TEMPLATES_BY_SECTION: dict[str, ImportTemplate] = {t.section: t for t in IMPORT_TEMPLATES}


# FU-350 — sections the commit handler currently knows how to process,
# mapped to the header tuple it expects for each. Today `stock_items` is
# the only real target and its expected headers are `TARGET_FIELDS`.
# When a second section handler lands (recipes, shopping lists, …),
# whoever wires it MUST add its `(section, expected_headers)` pair here.
# `_validate_import_templates` then enforces the invariant both ways:
# a template with no commit path fails to boot (FU-350), AND a
# commit-known section with no template fails to boot (FU-348) — so the
# set of importable sections and the set of downloadable templates can
# never drift apart. Keeping the map explicit (not derived from a
# dispatch table that doesn't exist yet) means adding a second section
# is one clearly-marked line, not a spelunk through the handler.
_COMMIT_KNOWN_SECTIONS: dict[str, tuple[str, ...]] = {
    "stock_items": TARGET_FIELDS,
}


def _validate_import_templates() -> None:
    """FU-350 + FU-348 — fail at module load, not at user download time.

    Four drift risks the FU-343 shipping shape carried:
      1. `example` cells were positional; a reordered / renamed / added
         target field would silently misalign the example under the
         wrong headers. Now dict-keyed, so any stale key or missing
         column raises here instead of shipping a broken CSV. (FU-350)
      2. Header tuples could diverge from the source of truth
         (`TARGET_FIELDS` for stock_items, and whichever tuple owns
         each future section). Enforced via `_COMMIT_KNOWN_SECTIONS`.
         (FU-350)
      3. A template could ship for a section the commit handler
         doesn't understand — download works, upload silently fails.
         Enforced via the section-in-`_COMMIT_KNOWN_SECTIONS` check
         below. (FU-350)
      4. The reverse: a section the commit handler *can* process ships
         with no template — the "Download template" button silently
         misses it, so users have to guess that section's schema.
         Enforced via the `_COMMIT_KNOWN_SECTIONS` ⊆ templates check at
         the end. Together with (3) this pins a two-way symmetry:
         importable section ⇔ downloadable template. (FU-348)
    """
    seen_sections: set[str] = set()
    for t in IMPORT_TEMPLATES:
        if t.section in seen_sections:
            raise ValueError(
                f"Duplicate ImportTemplate for section '{t.section}'."
            )
        seen_sections.add(t.section)

        if t.section not in _COMMIT_KNOWN_SECTIONS:
            raise ValueError(
                f"ImportTemplate section '{t.section}' has no matching "
                f"entry in `_COMMIT_KNOWN_SECTIONS` — the commit handler "
                f"doesn't know how to process it. Add a "
                f"'{t.section}': <expected_headers> entry there before "
                f"registering a template."
            )

        expected_headers = _COMMIT_KNOWN_SECTIONS[t.section]
        if set(t.headers) != set(expected_headers):
            raise ValueError(
                f"ImportTemplate('{t.section}').headers {set(t.headers)} "
                f"drifted from the commit handler's expected headers "
                f"{set(expected_headers)}."
            )

        example_keys = set(t.example.keys())
        header_set = set(t.headers)
        stale_keys = example_keys - header_set
        if stale_keys:
            raise ValueError(
                f"ImportTemplate('{t.section}').example has keys "
                f"{sorted(stale_keys)} that aren't in .headers — "
                f"they'd silently disappear from the emitted CSV."
            )

    # FU-348 — the reverse-direction symmetry check. The loop above proves
    # every *template* has a commit path; this proves every *commit-known
    # section* has a template, so the "Download template" index can't
    # silently miss a section the importer actually accepts. When a second
    # section (recipes, shopping lists, …) is added to
    # `_COMMIT_KNOWN_SECTIONS` without a matching `ImportTemplate`, the API
    # fails to boot here with a readable message rather than shipping a
    # download index that omits it.
    missing_templates = set(_COMMIT_KNOWN_SECTIONS) - seen_sections
    if missing_templates:
        raise ValueError(
            f"Commit handler knows sections {sorted(missing_templates)} "
            f"with no matching ImportTemplate — the 'Download template' "
            f"index would silently miss them. Register an ImportTemplate "
            f"in IMPORT_TEMPLATES for each before shipping."
        )


_validate_import_templates()


@DATA_ROUTER.route("/import/templates", methods=["GET"])
def list_import_templates():
    # Same admin gate as the rest of import (see FU-341 / FU-198): only
    # admins can invoke the importer, so only admins need the template
    # index. Non-admins hitting this get a plain 403 rather than an
    # index that hints at endpoints they can't use.
    _, err = require_admin()
    if err is not None:
        return err
    return ok({
        "sections": [
            {
                "section": t.section,
                "label": t.label,
                "caption": t.caption,
                "headers": list(t.headers),
            }
            for t in IMPORT_TEMPLATES
        ],
    })


@DATA_ROUTER.route("/import/templates/<section>.csv", methods=["GET"])
def download_import_template(section: str):
    _, err = require_admin()
    if err is not None:
        return err
    template = IMPORT_TEMPLATES_BY_SECTION.get(section)
    if template is None:
        return not_found("Import template", section)

    # Build the CSV in memory — headers row + one example row so the shape
    # is obvious, then any `#`-prefixed comment rows so users see the
    # "these placeholders may not match your install" hint (FU-349, opt A).
    # StringIO + csv.writer keeps escaping honest for names containing
    # commas / quotes even in the illustrative row.
    #
    # FU-350 — the example row is emitted by projecting the dict-keyed
    # `example` through `headers` at write time. Reordering `TARGET_FIELDS`
    # or adding a column reorders / grows the emitted row automatically;
    # missing keys emit as empty cells rather than misaligning under the
    # wrong header. Module-load validation (`_validate_import_templates`)
    # has already guaranteed no stale keys and no drift from the commit
    # handler's expected headers.
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(template.headers)
    writer.writerow([template.example.get(h, "") for h in template.headers])
    for comment_row in template.comment_rows:
        writer.writerow(comment_row)
    # prepend a UTF-8 BOM so Excel-on-Windows opens the file in
    # UTF-8 by default (without BOM it guesses ANSI/CP-1252 and any
    # accented character in an example row / template header renders as
    # mojibake). The upload-side sniffer strips the BOM back off before
    # parsing (see `_parse_csv` above), so the round-trip is symmetric.
    body = "﻿".encode("utf-8") + buf.getvalue().encode("utf-8")

    response = Response(body, mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="dora-import-{template.section}.csv"'
    )
    return response
