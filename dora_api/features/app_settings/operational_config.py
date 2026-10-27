"""FU-333 Buckets B + C — resolver for the operational config that was
formerly carried by ``DORA_*`` env vars.

Every field is a straight ``AppSetting`` projection. The Bucket-B
deprecation window (env fallbacks) was dropped 2026-07-06 pre-release
— nothing to preserve. Bucket-C secrets (SMTP password, VAPID private
key) are Fernet ciphertext on the row and decrypted on demand here.

Bootstrap-only env vars (``DORA_SECRET_KEY``, ``DORA_SECRET_ENCRYPTION_KEY``,
``DORA_ENV``, ``DORA_SECURE_COOKIES``, ``DORA_SPA_DIR``,
``DORA_SKIP_PROD_VALIDATION``, ``DORA_ALLOW_DESTRUCTIVE``) are *not* handled
here — they're read before the DB is reachable, so they must stay in env by
design. The desktop bundle auto-generates the two remaining keys on first
boot (see ``desktop_app.py _bootstrap_keys``).

Why a resolver at all (rather than each site reading ``AppSetting`` directly):
several call sites are hot paths (``email_sender``, ``push_sender``,
``tts_synthesize``) where a repository round-trip per send is wasted work,
and the Bucket-C secrets need one decrypt path. The resolver builds a small
immutable dataclass per call so the call site gets typed field access
without repeatedly hitting the DB.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.infrastructure.security.secret_encryption import (
    EncryptionFailed,
    EncryptionUnavailable,
    decrypt,
)
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OperationalConfig:
    """Resolved operational config. See module docstring."""
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from: str
    smtp_use_tls: bool
    vapid_public_key: str
    vapid_private_key: str
    vapid_subject: str
    piper_bin: str
    piper_bundled_voice_dir: str
    email_enabled: bool
    audit_retention_days: int
    public_url: str


def _decrypt_or_empty(ciphertext: str, *, field: str) -> str:
    """Decrypt a Bucket-C ciphertext column. Empty → empty (unconfigured).
    Encryption-unavailable or corrupted ciphertext → empty + a warning log,
    so the caller degrades to dry-run rather than crashing (the admin fixes
    it in Settings). A hard fail would take email + push down install-wide
    over a rotated key, which is worse UX than a friendly dry-run."""
    if not ciphertext:
        return ""
    try:
        return decrypt(ciphertext.encode("ascii"))
    except EncryptionUnavailable:
        _LOGGER.warning(
            "Cannot decrypt %s: DORA_SECRET_ENCRYPTION_KEY is unset. "
            "Configure the key or re-enter the secret in Settings.", field,
        )
        return ""
    except EncryptionFailed:
        _LOGGER.warning(
            "Stored %s ciphertext no longer decodes (key rotated?). "
            "Re-enter the secret in Settings.", field,
        )
        return ""


def resolved_operational_config() -> OperationalConfig:
    """Read the singleton ``AppSetting`` row + decrypt Bucket-C secrets.
    Callers treat the returned dataclass as immutable for the duration of
    one request/job. A background job that spans hours should call this
    again per work unit rather than caching across the whole process
    (admin-driven config changes should take effect on the next request)."""
    row = get_or_create_app_setting(SqlAlchemyRepository())
    return OperationalConfig(
        smtp_host=(row.smtp_host or "").strip(),
        smtp_port=int(row.smtp_port or 587),
        smtp_username=(row.smtp_username or "").strip(),
        smtp_password=_decrypt_or_empty(
            (row.smtp_password_encrypted or "").strip(),
            field="smtp_password",
        ),
        smtp_from=(row.smtp_from or "").strip(),
        smtp_use_tls=bool(row.smtp_use_tls),
        vapid_public_key=(row.vapid_public_key or "").strip(),
        vapid_private_key=_decrypt_or_empty(
            (row.vapid_private_key_encrypted or "").strip(),
            field="vapid_private_key",
        ),
        vapid_subject=(row.vapid_subject or "").strip() or "mailto:admin@dora.local",
        piper_bin=(row.piper_bin or "").strip(),
        piper_bundled_voice_dir=(row.piper_bundled_voice_dir or "").strip(),
        email_enabled=bool(row.email_enabled),
        audit_retention_days=int(row.audit_retention_days or 365),
        public_url=(row.public_url or "").strip(),
    )
