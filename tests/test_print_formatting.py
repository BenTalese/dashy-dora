"""Formatting authorities behind the print views and CSVs (print/export audit,
2026-10-30) — pure unit tests, no DB, no app.

What's pinned:
  • `units.format_quantity` owns its precision (R-079): "2", not "2.0"
  • `locale_format` writes dates and money the way the SPA's `Intl` does for
    the household locale — one test per locale for en-AU, en-US and de-DE
  • `export_shared.PrintFormat` puts an instant on the household clock before
    spelling it (R-021), instead of the server OS's zone
"""
import os
import tempfile
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

# Hazard guard (as test_email_templates.py): `export_shared` imports the app
# module; nothing here opens a DB, but no import may resolve to the
# developer's real dev DB from `.env`.
os.environ["DORA_DB_PATH"] = os.path.join(
    tempfile.gettempdir(), "dora.print-format-tests.throwaway.db",
)

from dora_api.domain.locale_format import (format_date, format_datetime,  # noqa: E402
                                           format_day, format_locale_money)
from dora_api.domain.money import format_money  # noqa: E402
from dora_api.domain.units import format_quantity  # noqa: E402
from dora_api.features.data.export_shared import PrintFormat  # noqa: E402

NNBSP = " "   # Intl's narrow no-break space before am/pm
NBSP = " "


# ── Quantities (R-079) ─────────────────────────────────────────────────

def test__format_quantity__drops_a_float_tail():
    # The print views read "2.0 tbsp" / "100.0g" and the CSV "400.0".
    assert format_quantity(2.0, "tbsp") == "2 tbsp"
    assert format_quantity(100.0, "g") == "100g"
    assert format_quantity(400.0, None) == "400"


def test__format_quantity__rounds_float_artefacts_to_two_places():
    assert format_quantity(94 / 3, "tbsp") == "31.33 tbsp"
    assert format_quantity(0.1 + 0.2, "cup") == "0.3 cup"
    assert format_quantity(1 / 3, "cup") == "0.33 cup"


def test__format_quantity__keeps_values_that_need_no_rounding():
    assert format_quantity(0.25, "cup") == "0.25 cup"
    assert format_quantity(0.5, None) == "0.5"
    assert format_quantity(3, "cloves") == "3 cloves"


def test__format_quantity__passes_text_through_and_drops_non_finite():
    assert format_quantity("1/2", "cup") == "1/2 cup"
    assert format_quantity(float("nan"), "g") == "g"
    assert format_quantity(None, None) == ""


# ── Locale: en-AU (the shipping default) ───────────────────────────────

_AT = datetime(2026, 10, 30, 16, 50)


def test__locale__en_au__day_first_dates_and_symbol_first_money():
    assert format_date(date(2026, 11, 2), "en-AU") == "2 Nov 2026"
    assert format_datetime(_AT, "en-AU") == f"30 Oct 2026, 4:50{NNBSP}pm"
    assert format_day(date(2026, 11, 2), "en-AU") == "Mon, 2 Nov"
    assert format_money(7.99, "AUD", "en-AU") == "$7.99"
    assert format_money(1234.5, "AUD", "en-AU") == "$1,234.50"


# ── Locale: en-US ──────────────────────────────────────────────────────

def test__locale__en_us__month_first_dates_and_symbol_first_money():
    assert format_date(date(2026, 10, 30), "en-US") == "Oct 30, 2026"
    assert format_datetime(_AT, "en-US") == f"Oct 30, 2026, 4:50{NNBSP}PM"
    assert format_day(date(2026, 11, 2), "en-US") == "Mon, Nov 2"
    assert format_money(7.99, "USD", "en-US") == "$7.99"
    # Intl marks a foreign dollar: what the SPA shows an en-US household in AUD.
    assert format_money(7.99, "AUD", "en-US") == "A$7.99"


# ── Locale: de-DE ──────────────────────────────────────────────────────

def test__locale__de_de__numeric_dates_24_hour_and_symbol_after():
    assert format_date(date(2026, 10, 30), "de-DE") == "30.10.2026"
    assert format_datetime(_AT, "de-DE") == "30.10.2026, 16:50"
    assert format_money(7.99, "EUR", "de-DE") == f"7,99{NBSP}€"
    assert format_money(1234567.5, "EUR", "de-DE") == f"1.234.567,50{NBSP}€"


def test__locale__unknown_tag_falls_back_to_its_language_then_en_au():
    assert format_date(date(2026, 10, 30), "fr-BE") == format_date(date(2026, 10, 30), "fr-FR")
    assert format_date(date(2026, 10, 30), "xx-YY") == "30 Oct 2026"
    assert format_locale_money(2.5, "XYZ", "en-AU") == f"XYZ{NBSP}2.50"


def test__format_money__without_a_locale_keeps_the_plain_form():
    # The assistant's replies call it without a locale; unchanged.
    assert format_money(4.5, "AUD") == "$4.50"
    assert format_money(24.9, "SEK") == "SEK 24.90"


# ── Print format: household clock + locale ─────────────────────────────

def test__print_format__converts_an_instant_to_the_household_zone():
    # 05:50 UTC is 16:50 in Melbourne (AEDT) — and already the next day's
    # date in a zone a server in UTC would have printed as the 29th.
    fmt = PrintFormat("en-AU", "AUD", ZoneInfo("Australia/Melbourne"))
    instant = datetime(2026, 10, 30, 5, 50, tzinfo=timezone.utc)
    assert fmt.datetime(instant) == f"30 Oct 2026, 4:50{NNBSP}pm"
    late = datetime(2026, 10, 29, 22, 0, tzinfo=timezone.utc)
    assert fmt.date(late.astimezone(fmt.tz).date()) == "30 Oct 2026"


def test__print_format__money_and_dates_follow_the_locale():
    fmt = PrintFormat("de-DE", "EUR", ZoneInfo("Europe/Berlin"))
    assert fmt.money(7.99) == f"7,99{NBSP}€"
    assert fmt.date(date(2026, 12, 29)) == "29.12.2026"
    assert fmt.date(None) == ""
    assert fmt.money(None) == "–"
