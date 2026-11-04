"""FU-333 Bucket B + C — operational config resolver.

The Bucket-B env-fallback lane was dropped 2026-07-06 (FU-467), so this
suite now covers the AppSetting-only semantics: whatever the admin
persists in Settings → Admin → System is what the resolver returns.
The Bucket-C secrets (SMTP password, VAPID private key) are separately
covered — the resolver only reads their ciphertext columns here; the
encrypt-on-write path lives in ``test_bucket_c_secrets.py``.

Each test PATCHes the row through the admin endpoint (the same path the
SPA uses), then calls the resolver under ``app.app_context()`` and
asserts the projection. A ``try/finally`` resets the row to the seeded
default so no state leaks between tests in the module.
"""
from __future__ import annotations

import pytest
import requests

from dora_api.app import app
from dora_api.features.app_settings.operational_config import (
    resolved_operational_config,
)


BASE = "http://localhost:5170/api"
APP_SETTINGS = f"{BASE}/app-settings"


# Seeded defaults per ``dora_api/domain/entities/app_setting.py`` — used
# by _reset_all() to leave a clean row between tests.
_STRING_RESETS = {
    "smtp_host": "",
    "smtp_username": "",
    "smtp_from": "",
    "vapid_public_key": "",
    "vapid_subject": "mailto:admin@dora.local",
    "piper_bin": "",
    "piper_bundled_voice_dir": "",
    "public_url": "",
}
_INT_RESETS = {
    "smtp_port": 587,
    "audit_retention_days": 365,
}
_BOOL_RESETS = {
    "smtp_use_tls": True,
}


def _reset_all() -> None:
    payload: dict = {}
    payload.update(_STRING_RESETS)
    payload.update(_INT_RESETS)
    payload.update(_BOOL_RESETS)
    resp = requests.patch(APP_SETTINGS, json=payload)
    assert resp.status_code == 200, resp.text


@pytest.fixture(autouse=True)
def _clean_state(api):
    _reset_all()
    try:
        yield
    finally:
        _reset_all()


def _resolved():
    with app.app_context():
        return resolved_operational_config()


# ── String fields: row value flows through; seeded defaults when blank ──

@pytest.mark.parametrize(
    "field,row_value,seeded_default",
    [
        ("smtp_host", "smtp.example.com", ""),
        ("smtp_username", "dora@example.com", ""),
        ("smtp_from", "no-reply@example.com", ""),
        ("vapid_public_key", "BASE64URL-PUBLIC-KEY", ""),
        ("vapid_subject", "mailto:ops@example.com", "mailto:admin@dora.local"),
        ("piper_bin", "/usr/local/bin/piper", ""),
        ("piper_bundled_voice_dir", "/opt/dora/voices", ""),
        ("public_url", "https://dora.example.com", ""),
    ],
)
def test__resolver__string_field__projects_row_and_falls_back_to_seeded_default(
    field, row_value, seeded_default,
):
    # Row set → resolver returns row value (stripped).
    resp = requests.patch(APP_SETTINGS, json={field: row_value})
    assert resp.status_code == 200, resp.text
    assert getattr(_resolved(), field) == row_value

    # Row cleared to empty → resolver returns the seeded default. For
    # `vapid_subject` the default is `mailto:admin@dora.local`, for
    # everything else it's the empty string.
    resp = requests.patch(APP_SETTINGS, json={field: ""})
    assert resp.status_code == 200, resp.text
    assert getattr(_resolved(), field) == seeded_default


def test__resolver__whitespace_only_row_string__resolves_to_default():
    """Whitespace-only strings are stripped by the resolver, so an admin
    accidentally saving `"  "` doesn't leak into an outbound SMTP `EHLO`.
    Same posture as if the field were unset."""
    resp = requests.patch(APP_SETTINGS, json={"smtp_host": "   "})
    assert resp.status_code == 200, resp.text
    assert _resolved().smtp_host == ""


# ── Numeric fields: row value flows through ─────────────────────────────

def test__resolver__smtp_port__projects_row():
    resp = requests.patch(APP_SETTINGS, json={"smtp_port": 2525})
    assert resp.status_code == 200, resp.text
    assert _resolved().smtp_port == 2525


def test__resolver__audit_retention_days__projects_row():
    resp = requests.patch(APP_SETTINGS, json={"audit_retention_days": 30})
    assert resp.status_code == 200, resp.text
    assert _resolved().audit_retention_days == 30


# ── Bool fields: row is authoritative (NOT NULL column) ─────────────────

def test__app_settings__email_enabled_is_gone():
    # FU-906: the install-wide "email enabled" switch gated nothing (mail
    # sends whenever an SMTP username is set), so it was deleted. A PATCH that
    # still names it is refused rather than silently accepted.
    assert "email_enabled" not in requests.get(APP_SETTINGS).json()
    resp = requests.patch(APP_SETTINGS, json={"email_enabled": True})
    assert 400 <= resp.status_code < 500, resp.text


def test__resolver__smtp_use_tls__projects_row():
    resp = requests.patch(APP_SETTINGS, json={"smtp_use_tls": False})
    assert resp.status_code == 200, resp.text
    assert _resolved().smtp_use_tls is False

    resp = requests.patch(APP_SETTINGS, json={"smtp_use_tls": True})
    assert resp.status_code == 200, resp.text
    assert _resolved().smtp_use_tls is True


# ── Health endpoint uses the resolver for `email_smtp_configured` ───────

def test__health__email_smtp_configured__derived_from_appsetting():
    """Prove the resolver flows through the /health endpoint — an admin
    flipping SMTP username in Settings sees the SPA's R-014 gating flip
    without a restart."""
    health = requests.get(f"{BASE}/health").json()
    assert health["features"]["email_smtp_configured"] is False

    resp = requests.patch(APP_SETTINGS, json={"smtp_username": "operator@example"})
    assert resp.status_code == 200, resp.text
    health = requests.get(f"{BASE}/health").json()
    assert health["features"]["email_smtp_configured"] is True
