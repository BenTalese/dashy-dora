"""Helpers shared by every CSV / print-view export endpoint."""
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from dora_api.domain import locale_format
from dora_api.domain.money import format_money
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.features.app_settings.clock import household_today, resolve_timezone
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


def slugify(value: str) -> str:
    """Filesystem-safe slug. Lowercase, ASCII-only letters/digits/dashes."""
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value or "").strip("-").lower()
    return text or "untitled"


# Leading characters a spreadsheet app reads as a formula (or as the start of
# one, after it strips a tab / CR). A household member's free-text "notes"
# could otherwise run `=HYPERLINK(...)` / DDE in whoever opens the export.
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe_cell(value: object) -> object:
    """OWASP CSV-injection mitigation: prefix a formula-looking text cell with
    a single quote so Excel / Sheets / LibreOffice show it as text. Non-text
    cells (a negative quantity) pass through untouched."""
    if isinstance(value, str) and value.startswith(_CSV_FORMULA_PREFIXES):
        return "'" + value
    return value


def csv_safe_row(cells: list[object]) -> list[object]:
    return [csv_safe_cell(cell) for cell in cells]


def export_filename(prefix: str, list_name: str, extension: str) -> str:
    # R-021 — the date stamp on a download is the household's calendar day
    # ("recipe-bolognese-2026-06-29.csv"), not the server's.
    today = household_today(SqlAlchemyRepository()).isoformat()
    return f"{prefix}-{slugify(list_name)}-{today}.{extension}"


# Excel on Windows opens a BOM-less CSV as the ANSI code page, so "Crème"
# became "CrÃ¨me". Every CSV download is prefixed with this (the import
# template already was); any UTF-8 reader skips it (`utf-8-sig`).
CSV_BOM = "\ufeff"


# ── Print dates and money (R-021 which day, D-006 how it reads) ────────
# Every print view spells dates and money through here, in the household's
# locale and on the household's clock: "30 Oct 2026, 4:50 pm" (en-AU),
# "Oct 30, 2026, 4:50 PM" (en-US), "30.10.2026, 16:50" (de-DE). They used to
# print the server OS's local time in ISO ("2026-10-30 16:44"). The patterns
# are `domain.locale_format`'s, which mirror the SPA's `Intl` output.

def format_print_date(value: date | None, locale: str | None) -> str:
    """A calendar date in the locale's medium form; empty for None."""
    return "" if value is None else locale_format.format_date(value, locale)


def format_print_day(value: date, locale: str | None) -> str:
    """A day heading inside a dated sheet: "Mon, 2 Nov" (en-AU)."""
    return locale_format.format_day(value, locale)


def format_print_datetime(value: datetime, locale: str | None, tz: ZoneInfo) -> str:
    """An instant on the household clock, in the locale's medium date + short
    time. A naive value is taken as UTC (how the app stores instants)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return locale_format.format_datetime(value.astimezone(tz), locale)


@dataclass(frozen=True)
class PrintFormat:
    """The household's locale, currency and clock, read once per print view
    (one AppSetting fetch) and handed to the template as its formatters."""
    locale: str
    currency: str
    tz: ZoneInfo

    def date(self, value: date | None) -> str:
        return format_print_date(value, self.locale)

    def day(self, value: date) -> str:
        return format_print_day(value, self.locale)

    def datetime(self, value: datetime) -> str:
        return format_print_datetime(value, self.locale, self.tz)

    def money(self, amount: float | None) -> str:
        return format_money(amount, self.currency, self.locale)

    def generated_at(self) -> str:
        """The "Generated …" stamp every print view carries."""
        return self.datetime(datetime.now(timezone.utc))


def print_format(repository: SqlAlchemyRepository) -> PrintFormat:
    setting = get_or_create_app_setting(repository)
    return PrintFormat(
        locale=(setting.locale or "").strip() or locale_format.DEFAULT_LOCALE,
        currency=(setting.currency or "").strip() or "AUD",
        tz=resolve_timezone(setting.timezone),
    )


# Print-view stylesheet shared across every server-rendered print page.
# Centralised so a polish pass on print rules lands everywhere at once.
PRINT_CSS = """
<style>
  :root { color-scheme: light; }
  html, body {
    margin: 0;
    padding: 0;
    background: #fff;
    color: #222;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica,
                 Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
    font-size: 14px;
    line-height: 1.45;
  }
  .page {
    max-width: 720px;
    margin: 0 auto;
    padding: 32px 24px 64px;
  }
  h1 { font-size: 22px; margin: 0 0 4px; }
  h2 { font-size: 16px; margin: 24px 0 8px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
  .meta { color: #666; font-size: 12px; margin-bottom: 16px; }
  .totals {
    display: flex; gap: 16px; flex-wrap: wrap;
    background: #f4f4f4; border-radius: 6px; padding: 10px 14px; margin-bottom: 16px;
    font-size: 13px;
  }
  .totals strong { color: #111; }
  table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  td, th { padding: 8px 4px; text-align: left; vertical-align: top; }
  td.qty, th.qty, td.price, th.price { text-align: right; white-space: nowrap; }
  td.box { width: 22px; }
  .checkbox {
    display: inline-block; width: 18px; height: 18px;
    border: 1.5px solid #444; border-radius: 3px;
    text-align: center; line-height: 16px; font-size: 13px; font-weight: 700;
  }
  .picked .item-name { text-decoration: line-through; color: #666; }
  .item-name { font-weight: 600; }
  .item-store, .item-notes { color: #666; font-size: 12px; }
  .ingredient { padding: 6px 0; border-bottom: 1px dashed #ddd; }
  .ingredient:last-child { border-bottom: none; }
  .instructions { white-space: pre-wrap; margin-top: 8px; }
  h3 { font-size: 14px; margin: 16px 0 4px; }
  ol.steps { padding-left: 22px; margin: 8px 0; }
  ol.steps li { margin: 0 0 10px; }
  ol.steps ol { padding-left: 18px; margin: 6px 0 0; }
  .step-hint, .step-timer { color: #666; font-size: 12px; }
  .optional-tag { color: #666; font-size: 12px; font-style: italic; }
  .step-image { display: block; max-width: 100%; margin: 0 0 12px; border-radius: 4px; }
  .recipe-meta-chip {
    display: inline-block; background: #f4f4f4; border-radius: 4px;
    padding: 2px 8px; margin-right: 6px; font-size: 12px; color: #444;
  }
  .toolbar {
    position: fixed; top: 12px; right: 12px;
    background: #222; color: #fff; padding: 8px 14px; border-radius: 999px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.2); cursor: pointer; font-size: 13px;
    user-select: none;
  }
  @media print {
    .toolbar { display: none; }
    .page { max-width: none; padding: 12px 16px; }
    h2 { page-break-after: avoid; }
    tr, .ingredient, ol.steps li, .step-image { page-break-inside: avoid; }
    body { font-size: 12px; }
  }
</style>
"""

# A tiny "Print this page" floating button so the user doesn't need to know
# Ctrl/Cmd-P. Hidden in print output via @media print.
PRINT_TOOLBAR = (
    '<button class="toolbar" onclick="window.print()">Print / Save as PDF</button>'
)
