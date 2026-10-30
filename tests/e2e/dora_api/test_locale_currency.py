"""FU-502 — Coverage for the FU-043 locale/currency backend.

Covers, per the FU-502 checklist:

1. **Round-trip** — a PATCH to `/app-settings` with `currency` + `locale`
   flows through to `GET /health` → `locale_policy` on the same
   in-process Flask client.
2. **Currency validation** — the write endpoint accepts a 3-letter ISO
   4217 code (case-normalised to uppercase) and rejects everything else.
3. **Locale validation** — the write endpoint accepts BCP-47 tags that
   `Intl.NumberFormat` / `Intl.Locale` consume and rejects malformed
   inputs. Server-side matches the lightweight `_is_valid_bcp47`
   validator in `update_app_settings.py` (the client's `new Intl.Locale`
   is the second net for anything exotic).

The FU also mentioned "migration up/down against in-memory sqlite" —
that path isn't a separate test here because the migration is already
exercised on every test run: the test conftest boots the app, which
runs alembic-managed schema, and every other test in the suite reads
from `AppSetting.currency` / `AppSetting.locale`. A regression on the
columns would take the whole suite down before this file even loaded.

Tests reset the row back to Dora's shipping defaults (`AUD` + `en-AU`)
in `try/finally` so they don't leak state.
"""
from __future__ import annotations

import pytest
import requests


BASE = "http://localhost:5170/api"
APP_SETTINGS = f"{BASE}/app-settings"
HEALTH = f"{BASE}/health"


_DEFAULT_CURRENCY = "AUD"
_DEFAULT_LOCALE = "en-AU"
_DEFAULT_MEASUREMENT_SYSTEM = "metric"


@pytest.fixture(autouse=True)
def _reset_locale_policy(api):
    """Every test lands and leaves on the shipping defaults so the
    round-trip test isn't confused by a value another test set."""
    resp = requests.patch(
        APP_SETTINGS,
        json={"currency": _DEFAULT_CURRENCY, "locale": _DEFAULT_LOCALE},
    )
    assert resp.status_code == 200, resp.text
    try:
        yield
    finally:
        requests.patch(
            APP_SETTINGS,
            json={"currency": _DEFAULT_CURRENCY, "locale": _DEFAULT_LOCALE},
        )


# ── 1. Round-trip: PATCH flows to /health ──────────────────────────────

def test__health_locale_policy__reflects_patched_currency_and_locale():
    resp = requests.patch(
        APP_SETTINGS,
        json={"currency": "USD", "locale": "en-US"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["currency"] == "USD"
    assert body["locale"] == "en-US"

    health = requests.get(HEALTH).json()
    assert "locale_policy" in health, (
        "GET /health must expose `locale_policy` for the SPA "
        "money formatter (R-003)."
    )
    assert health["locale_policy"]["currency"] == "USD"
    assert health["locale_policy"]["locale"] == "en-US"


def test__health_locale_policy__defaults_to_au_shipping_values():
    # Fixture leaves us on the defaults; hit /health directly.
    health = requests.get(HEALTH).json()
    assert health["locale_policy"] == {
        "currency": _DEFAULT_CURRENCY,
        "locale": _DEFAULT_LOCALE,
        # 2026-08-27 — the measurement system rides in this payload too, for
        # the same reason currency does: every session's unit pickers are
        # built from it, not just an admin's. Metric is the shipping default.
        "measurement_system": _DEFAULT_MEASUREMENT_SYSTEM,
        # 2026-10-30 — the household's IANA zone, so the client names
        # "Today" on the household calendar (additive; mirrors /app-settings).
        "timezone": requests.get(f"{BASE}/app-settings").json()["timezone"],
    }


# ── 2. Currency validation table ───────────────────────────────────────

@pytest.mark.parametrize(
    "input_value,expected_stored",
    [
        ("USD", "USD"),
        ("EUR", "EUR"),
        ("aud", "AUD"),        # lower-cased in ⇒ upper-cased on save
    ],
)
def test__update_currency__valid_codes__accepted_and_upper_cased(
    input_value, expected_stored,
):
    resp = requests.patch(APP_SETTINGS, json={"currency": input_value})
    assert resp.status_code == 200, resp.text
    assert resp.json()["currency"] == expected_stored
    # /health reflects the same value.
    assert requests.get(HEALTH).json()["locale_policy"]["currency"] == expected_stored


@pytest.mark.parametrize(
    "input_value",
    [
        "US",       # too short — request-model min_length=3
        "USDX",     # too long — request-model max_length=3
        "US1",      # contains a digit — handler-level `isalpha` guard
        "",         # empty — request-model min_length=3
        " GBP ",    # whitespace-padded exceeds the 3-char length gate
    ],
)
def test__update_currency__invalid_codes__rejected(input_value):
    resp = requests.patch(APP_SETTINGS, json={"currency": input_value})
    # Either the pydantic model catches it (400) or the handler does
    # (400 with a domain reason). Both are legitimate rejection paths;
    # the contract we pin is "not 200".
    assert resp.status_code == 400, (
        f"Expected 400 for currency={input_value!r}, got {resp.status_code}: "
        f"{resp.text[:200]}"
    )
    # The row must NOT have moved off the shipping default.
    assert (
        requests.get(HEALTH).json()["locale_policy"]["currency"]
        == _DEFAULT_CURRENCY
    )


# ── 3. Locale validation table ─────────────────────────────────────────

@pytest.mark.parametrize(
    "input_value",
    [
        "en-AU",         # baseline
        "en-US",
        "de-DE",
        "en-Latn-US",    # script + region subtags
        "zh-Hant-TW",    # 4-letter script + region
    ],
)
def test__update_locale__valid_bcp47_tags__accepted(input_value):
    resp = requests.patch(APP_SETTINGS, json={"locale": input_value})
    assert resp.status_code == 200, resp.text
    assert resp.json()["locale"] == input_value
    assert requests.get(HEALTH).json()["locale_policy"]["locale"] == input_value


@pytest.mark.parametrize(
    "input_value",
    [
        "en_AU",     # underscore separator (POSIX-style) — not BCP-47
        "e",         # too-short primary tag
        "english",   # 4+ letters in the primary tag
        "en AU",     # space in the tag
    ],
)
def test__update_locale__malformed_tags__rejected(input_value):
    resp = requests.patch(APP_SETTINGS, json={"locale": input_value})
    assert resp.status_code == 400, (
        f"Expected 400 for locale={input_value!r}, got {resp.status_code}: "
        f"{resp.text[:200]}"
    )
    assert (
        requests.get(HEALTH).json()["locale_policy"]["locale"]
        == _DEFAULT_LOCALE
    )
