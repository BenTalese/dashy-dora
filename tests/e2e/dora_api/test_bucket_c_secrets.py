"""FU-333 Bucket C — encrypted-at-rest storage for SMTP password + VAPID
private key.

Covers the write path (PATCH /api/app-settings with plaintext → ciphertext
stored on the row, DTO returns only the `_configured` bool) and the read
path (resolver decrypts on demand; a rotated wrapping key surfaces as
"not configured" rather than a crash).

The wrapping key comes from `DORA_SECRET_ENCRYPTION_KEY`. The pytest
fixture sets a stable Fernet key for the session so the tests are
deterministic; individual tests that want to prove the rotation /
missing-key behaviour override it locally with `monkeypatch`.
"""
from __future__ import annotations

import base64

import pytest
import requests
from cryptography.fernet import Fernet

from dora_api.app import app
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.features.app_settings.operational_config import (
    resolved_operational_config,
)
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


BASE = "http://localhost:5170/api"
APP_SETTINGS = f"{BASE}/app-settings"


pytestmark = pytest.mark.usefixtures("secret_encryption_key")


@pytest.fixture(autouse=True)
def _clear_secrets(api):
    """Zero both secret columns before + after each test so nothing leaks
    between cases. Uses the write endpoint's explicit-clear semantics
    (empty string on a secret field wipes the ciphertext)."""
    resp = requests.patch(APP_SETTINGS, json={
        "smtp_password": "",
        "vapid_private_key": "",
    })
    assert resp.status_code == 200, resp.text
    try:
        yield
    finally:
        requests.patch(APP_SETTINGS, json={
            "smtp_password": "",
            "vapid_private_key": "",
        })


def _row_column(name: str) -> str:
    with app.app_context():
        setting = get_or_create_app_setting(SqlAlchemyRepository())
        return getattr(setting, name, "") or ""


def _resolved():
    with app.app_context():
        return resolved_operational_config()


# ── Write path ──────────────────────────────────────────────────────────

def test__patch_smtp_password__stores_ciphertext_not_plaintext():
    """The plaintext must never land in the ciphertext column verbatim —
    if it did, a DB dump would leak every SMTP password on the platform."""
    plaintext = "hunter2-real-smtp-password"
    resp = requests.patch(APP_SETTINGS, json={"smtp_password": plaintext})
    assert resp.status_code == 200, resp.text

    stored = _row_column("smtp_password_encrypted")
    assert stored, "expected ciphertext to be stored"
    assert plaintext not in stored


def test__patch_smtp_password__dto_returns_configured_bool_never_plaintext():
    """The read DTO must not carry the plaintext or the ciphertext — only
    a bool. Every admin session refreshing Settings would otherwise see
    the secret."""
    resp = requests.patch(APP_SETTINGS, json={"smtp_password": "s3cret"})
    body = resp.json()
    assert body["smtp_password_configured"] is True
    assert "smtp_password" not in body
    assert "smtp_password_encrypted" not in body


def test__patch_smtp_password_empty_string__clears_ciphertext():
    """Empty string is the explicit clear signal — an admin resets the
    field back to the default `dry-run` mode."""
    requests.patch(APP_SETTINGS, json={"smtp_password": "will-be-cleared"})
    assert _row_column("smtp_password_encrypted") != ""

    resp = requests.patch(APP_SETTINGS, json={"smtp_password": ""})
    assert resp.status_code == 200, resp.text
    assert _row_column("smtp_password_encrypted") == ""
    assert resp.json()["smtp_password_configured"] is False


def test__patch_smtp_password_omitted__leaves_stored_value_unchanged():
    """Partial-update semantics — patching other SMTP fields must not
    wipe the stored secret."""
    requests.patch(APP_SETTINGS, json={"smtp_password": "keep-me"})
    before = _row_column("smtp_password_encrypted")

    resp = requests.patch(APP_SETTINGS, json={"smtp_host": "smtp.new.example"})
    assert resp.status_code == 200, resp.text
    after = _row_column("smtp_password_encrypted")
    assert after == before


def test__patch_vapid_private_key__stores_ciphertext_not_plaintext():
    plaintext = "-----BEGIN VAPID PRIVATE KEY-----\nabcdef\n-----END VAPID PRIVATE KEY-----"
    resp = requests.patch(APP_SETTINGS, json={"vapid_private_key": plaintext})
    assert resp.status_code == 200, resp.text
    stored = _row_column("vapid_private_key_encrypted")
    assert stored
    assert "abcdef" not in stored
    assert resp.json()["vapid_private_key_configured"] is True


# ── Read path ───────────────────────────────────────────────────────────

def test__resolver__decrypts_smtp_password_round_trip():
    """A saved secret must decrypt back to the original plaintext on the
    read path — the email sender depends on this."""
    plaintext = "round-trip-password-🍕"
    resp = requests.patch(APP_SETTINGS, json={"smtp_password": plaintext})
    assert resp.status_code == 200, resp.text
    assert _resolved().smtp_password == plaintext


def test__resolver__decrypts_vapid_private_key_round_trip():
    plaintext = "vapid-private-key-blob"
    resp = requests.patch(APP_SETTINGS, json={"vapid_private_key": plaintext})
    assert resp.status_code == 200, resp.text
    assert _resolved().vapid_private_key == plaintext


def test__resolver__unset_secrets__return_empty_string():
    """Fresh install / cleared row → resolver returns empty. Callers
    interpret empty as `dry-run`, not a crash."""
    op = _resolved()
    assert op.smtp_password == ""
    assert op.vapid_private_key == ""


# ── Failure modes ───────────────────────────────────────────────────────

def test__resolver__ciphertext_undecodable__degrades_to_empty_with_warning(caplog):
    """If someone rotates DORA_SECRET_ENCRYPTION_KEY without re-entering
    the stored secrets, the ciphertext can't be decoded. The resolver
    logs a warning and returns empty (dry-run) — a hard crash would take
    email + push down install-wide until the admin knew to look."""
    # Save a real secret, then swap the wrapping key so the stored token
    # no longer decodes. We do this by overwriting the column directly
    # with a token encrypted under a *different* key — reproducing the
    # "operator rotated the wrapping key" scenario without racing the
    # `secret_encryption._fernet` lru_cache.
    other_key = Fernet.generate_key()
    stale_token = Fernet(other_key).encrypt(b"used-to-work").decode("ascii")
    with app.app_context():
        repo = SqlAlchemyRepository()
        setting = get_or_create_app_setting(repo)
        setting.smtp_password_encrypted = stale_token
        repo.save_changes()

    with caplog.at_level("WARNING"):
        result = _resolved().smtp_password
    assert result == ""
    assert any("smtp_password" in rec.message for rec in caplog.records)


def test__patch_secret__without_wrapping_key__returns_400(monkeypatch):
    """The wrapping key must be configured before secrets can be stored.
    Missing key → friendly 400 + no partial write, not a silent success."""
    # Point the encryption helper at an empty key. lru_cache means we also
    # need to clear it so the change is observed.
    from dora_api.infrastructure.security import secret_encryption
    secret_encryption._fernet.cache_clear()
    monkeypatch.setenv("DORA_SECRET_ENCRYPTION_KEY", "")

    try:
        resp = requests.patch(APP_SETTINGS, json={"smtp_password": "no-key-set"})
        assert resp.status_code == 400, resp.text
        assert "DORA_SECRET_ENCRYPTION_KEY" in resp.text
        # No partial write.
        assert _row_column("smtp_password_encrypted") == ""
    finally:
        secret_encryption._fernet.cache_clear()
