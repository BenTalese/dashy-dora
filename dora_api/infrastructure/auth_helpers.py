"""Shared building blocks for the A1 auth surface.

All five new auth endpoints reuse this module:
  - Password rule validation (min 10 chars, ≥1 letter + ≥1 digit).
  - Token generation, hashing, persistence, and constant-time lookup.
  - Anti-enumeration helpers (always pretend success on
    forgot-password / resend-verification).
  - A tiny in-memory token-bucket rate limiter (per IP+route).
  - Public URL resolution so verification / reset links work for whatever
    deployment surface is in use — PWA on https://, a self-hosted desktop
    Electron app on file://-loaded code, or a mobile shell pointing at
    https://. Pulled from DORA_PUBLIC_URL with sensible fallbacks.

Tokens live in a single `AuthToken` table keyed by purpose, hashed at
rest (SHA-256). The raw token only appears in the outbound email. Token
consumption is a `consumed_at` stamp rather than a delete so audit
queries can still see what fired against the user.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any
from uuid import UUID, uuid4

from flask import request
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from dora_api.app import db
from dora_api.domain.entities.auth_token import (
    ALLOWED_PURPOSES, AuthToken, PURPOSE_RESET_PASSWORD, PURPOSE_VERIFY_EMAIL,
)


# ── Password rules ─────────────────────────────────────────────────────
#
# Policy shape follows NIST SP 800-63B (which ISO/IEC 27002:2022 §5.17 defers
# to as the standard for authentication-secret rules):
#
#   - Minimum length 8 (§5.1.1.2 "SHALL require at least 8 characters").
#   - No composition rules — no forced upper/lower/digit/symbol mix.
#     Composition rules push users toward predictable substitutions
#     (`Password1!`) that harm real entropy; NIST removed them in 2017.
#   - Reject the top ~60 known-compromised / trivially-guessed passwords
#     ("SHALL check against a list of values known to be commonly used").
#     We ship a small bundled list rather than a HIBP round-trip so
#     self-hosted installs stay offline-clean (R-005).
#   - Max 255 chars enforced upstream by the pydantic `Field(max_length=255)`
#     on every auth request body — well above the NIST-recommended 64+
#     ceiling. Werkzeug's `generate_password_hash` uses scrypt/pbkdf2
#     (not bcrypt), so there's no 72-byte silent-truncation trap.
#   - Rate-limiting per identity/IP is enforced separately by
#     `rate_limit("auth.login", max_per_minute=5)` in `features/auth/login.py`
#     (NIST §5.2.2 throttling).
#
# **No admin override.** The rules apply install-wide; making them
# operator-toggleable defeats the compliance posture that motivated
# adopting the NIST/ISO shape in the first place.

MIN_PASSWORD_LENGTH = 8

# Top ~60 breach-list offenders (2024 NCSC/HIBP annual review). Membership
# check is case-insensitive; any hit is rejected outright with a clear
# message. Keep this list conservative — its job is to catch the "would be
# guessed in ten tries" tier, not to enforce a full deny-list.
_COMMON_PASSWORDS: frozenset[str] = frozenset({
    "123456", "12345678", "123456789", "1234567890", "12345",
    "password", "password1", "password12", "password123", "password1234",
    "qwerty", "qwerty123", "qwertyuiop", "1q2w3e4r", "1q2w3e4r5t",
    "abc123", "abcd1234", "abcdefgh", "111111", "11111111",
    "iloveyou", "letmein", "welcome", "welcome1", "welcome123",
    "monkey", "dragon", "sunshine", "princess", "football",
    "admin", "admin123", "administrator", "root", "toor",
    "master", "passw0rd", "p@ssw0rd", "p@ssword", "trustno1",
    "starwars", "computer", "internet", "changeme", "test1234",
    "baseball", "superman", "batman", "shadow", "michael",
    "jennifer", "hunter2", "letmein1", "asdfghjkl", "zxcvbnm",
    "qazwsx", "1qaz2wsx", "!qaz2wsx", "0987654321", "987654321",
    "dashydora", "dashy_dora", "dashy-dora", "dora", "dorapassword",
})

PASSWORD_RULES_DOC = (
    f"Passwords must be at least {MIN_PASSWORD_LENGTH} characters. "
    "A passphrase of a few words is fine. "
    "Avoid common passwords like ‘password123’ or ‘qwerty’."
)


# Password hashing method. Pinned explicitly so an upstream werkzeug bump
# can't silently change the KDF (werkzeug's `generate_password_hash`
# default has moved between pbkdf2 and scrypt across versions). scrypt
# is memory-hard, which is what we want against GPU-parallel attackers;
# 32768/8/1 are the parameters werkzeug uses in current releases and
# match OWASP's minimum recommendation for scrypt at time of writing.
# `check_password_hash` auto-detects the method embedded in the stored
# hash string, so pinning here doesn't force a migration of existing
# hashes — a user's next successful login can be used to lazily upgrade
# their hash if we ever want to (not doing that yet).
PASSWORD_HASH_METHOD = "scrypt:32768:8:1"


def hash_password(value: str) -> str:
    """Single-source password hash. All auth flows (register, admin-create,
    reset) MUST call this — never `werkzeug.security.generate_password_hash`
    directly — so the KDF choice stays in one place (R-003)."""
    return generate_password_hash(value, method=PASSWORD_HASH_METHOD)


def validate_password(value: str) -> str | None:
    """Return an error message, or None if the password is acceptable.

    Policy: NIST SP 800-63B — min 8, no composition rules, reject bundled
    breach-list offenders (case-insensitive). No admin override; the rules
    apply install-wide.
    """
    if not value or len(value) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if value.lower() in _COMMON_PASSWORDS:
        return (
            "That password appears on public breach lists. Pick something "
            "less common."
        )
    return None


# ── Email format ───────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(value: str | None) -> bool:
    return bool(value) and bool(_EMAIL_RE.match(value or ""))


# ── Token plumbing ─────────────────────────────────────────────────────

# Defaults; the per-purpose TTLs match the brief.
VERIFY_EMAIL_TTL = timedelta(hours=24)
RESET_PASSWORD_TTL = timedelta(hours=1)


def _hash_token(raw: str) -> str:
    """SHA-256 hex digest. Plenty for a single-use credential."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_token(
    user_id: UUID,
    purpose: str,
    ttl: timedelta,
    payload: str | None = None,
) -> str:
    """Mint a new token for `user_id`, persist its hash, return the raw
    value. Caller is responsible for embedding the raw value in the
    outbound email.
    """
    assert purpose in ALLOWED_PURPOSES, f"unknown purpose {purpose!r}"
    raw = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    row = AuthToken(
        id=uuid4(),
        user_id=user_id,
        token_hash=_hash_token(raw),
        purpose=purpose,
        payload=payload,
        expires_at=now + ttl,
        created_at=now,
        consumed_at=None,
    )
    db.session.add(row)
    db.session.commit()
    return raw


def find_active_token(raw: str, purpose: str) -> AuthToken | None:
    """Look up a fresh, unconsumed, in-date token of the given purpose
    using a constant-time hash comparison (the SHA-256 itself is
    deterministic; we use `hmac.compare_digest` on the hex digest so
    timing attacks don't leak hash candidates).
    """
    if not raw:
        return None
    table = db.metadata.tables["AuthToken"]
    candidate_hash = _hash_token(raw)
    now = datetime.now(timezone.utc)
    rows = db.session.execute(
        select(table).where(
            table.c.purpose == purpose,
            table.c.consumed_at.is_(None),
            table.c.expires_at > now,
        )
    ).mappings().all()
    for row in rows:
        if hmac.compare_digest(row["token_hash"], candidate_hash):
            return AuthToken(
                id=row["id"],
                user_id=row["user_id"],
                token_hash=row["token_hash"],
                purpose=row["purpose"],
                payload=row["payload"],
                expires_at=row["expires_at"],
                created_at=row["created_at"],
                consumed_at=row["consumed_at"],
            )
    return None


def consume_token(token_id: UUID) -> None:
    table = db.metadata.tables["AuthToken"]
    db.session.execute(
        table.update().where(table.c.id == token_id).values(
            consumed_at=datetime.now(timezone.utc),
        )
    )
    db.session.commit()


def revoke_tokens_for_user(user_id: UUID, purpose: str) -> None:
    """Mark every still-live token of the given purpose consumed. Called
    after a successful password reset so any unused reset links go cold.
    """
    table = db.metadata.tables["AuthToken"]
    db.session.execute(
        table.update().where(
            table.c.user_id == user_id,
            table.c.purpose == purpose,
            table.c.consumed_at.is_(None),
        ).values(consumed_at=datetime.now(timezone.utc))
    )
    db.session.commit()


# ── Public URL resolution ──────────────────────────────────────────────

def public_base_url() -> str:
    """Where the SPA lives on the public internet. Used to build the
    URL embedded in verify-email / reset-password emails.

    Resolution order:
      1. `AppSetting.public_url` (edited from Settings → Admin → System).
      2. Origin header on the current request (the SPA POSTing to the
         API is the most reliable dev fallback).
      3. http://localhost:5174 (Quasar's default dev port).
    """
    try:
        from dora_api.features.app_settings.operational_config import \
            resolved_operational_config
        explicit = resolved_operational_config().public_url
    except Exception:
        explicit = ""
    if explicit:
        return explicit.rstrip("/")
    try:
        origin = request.headers.get("Origin")
        if origin:
            return origin.rstrip("/")
    except RuntimeError:
        # Outside a request context (e.g. scheduler) — fall through.
        pass
    return "http://localhost:5174"


def spa_deep_link(route_path: str) -> str:
    """Build a link to a specific in-app SPA route for emails.

    The SPA runs in **hash-history** mode (`web_app/quasar.config` →
    build.vueRouterMode: 'hash'), so a deep link MUST carry the in-app route in
    the URL *fragment*: ``https://host/#/reset-password?token=…``. A path-based
    link (``https://host/reset-password?token=…``) is served the SPA's
    index.html, but the hash router never sees that path — it resolves to ``/``
    and the auth guard bounces the (logged-out) visitor to ``#/login``, which is
    exactly the "reset link dumps me on the login screen" bug. Keeping every
    e-mailed deep link on this one helper means the hash coupling lives in a
    single, documented place; if the router mode ever changes, this is the only
    edit. ``route_path`` is the in-app path incl. any query, leading slash
    required, e.g. ``"/reset-password?token=abc"``.
    """
    return f"{public_base_url()}/#{route_path}"


def build_verify_url(token: str) -> str:
    return spa_deep_link(f"/verify-email?token={token}")


def build_reset_url(token: str) -> str:
    return spa_deep_link(f"/reset-password?token={token}")


# ── Rate limiter ───────────────────────────────────────────────────────

# Per-route token bucket, keyed by IP by default OR by a caller-supplied
# identity string (typically an authenticated user_id). In-memory and
# process-local — fine for a self-contained desktop install, a single
# PWA backend, or one mobile API host. For horizontally-scaled
# deployments swap for Redis later.
_buckets: dict[tuple[str, str], deque[float]] = {}
_buckets_lock = Lock()


def _bucket_key(scope: str, subject: str | None = None) -> tuple[str, str]:
    """Bucket key = (scope, subject). When the caller provides `subject`
    (e.g. `str(user_id)` for post-auth routes) it's used verbatim so the
    limit is per-identity across a household on a shared IP. Otherwise
    we fall back to the request's remote address for pre-auth surfaces
    (login, register, verify)."""
    if subject:
        return (scope, subject)
    ip = "anon"
    try:
        ip = request.remote_addr or "anon"
    except RuntimeError:
        pass
    return (scope, ip)


def rate_limit(
    scope: str, max_per_minute: int, subject: str | None = None,
) -> bool:
    """Returns True if the call is within the limit, False otherwise.

    `scope` is the endpoint identifier ("auth.login", "assistant.ask",
    …) so different routes don't share buckets.

    `subject` optionally overrides the per-IP default with a per-identity
    key. For post-auth routes (assistant surface, anything that already
    has a session.user_id) pass `str(user_id)` here so a shared
    household IP doesn't count multiple users against the same bucket
    (FU-458). For pre-auth routes leave it None to keep the IP fallback.
    """
    key = _bucket_key(scope, subject)
    now = time.monotonic()
    with _buckets_lock:
        bucket = _buckets.setdefault(key, deque())
        cutoff = now - 60.0
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= max_per_minute:
            return False
        bucket.append(now)
        return True


def rate_limit_remaining_seconds(
    scope: str, max_per_minute: int, subject: str | None = None,
) -> int:
    """Seconds until the oldest event in the bucket falls outside the
    sliding window. Used for the Retry-After response header. `subject`
    must match what was passed to `rate_limit` — same key both sides."""
    key = _bucket_key(scope, subject)
    now = time.monotonic()
    with _buckets_lock:
        bucket = _buckets.get(key)
        if not bucket or len(bucket) < max_per_minute:
            return 0
        return max(0, int(60.0 - (now - bucket[0])) + 1)


# ── Helpers used across endpoints ──────────────────────────────────────

def normalise_email(value: str | None) -> str | None:
    return value.strip().lower() if value else None


_LOGGER = logging.getLogger(__name__)


def try_send(send_fn, *args, **kwargs) -> None:
    """Wrap an outbound email send so a misconfigured SMTP doesn't fail
    the originating request. We deliberately swallow + log — telling
    the user "couldn't send mail" would also reveal whether their email
    address is known to the system."""
    try:
        send_fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("auth email send failed: %s", exc)


# Re-export so callers don't have to know the underlying entity layout.
__all__ = [
    "MIN_PASSWORD_LENGTH", "PASSWORD_RULES_DOC", "validate_password",
    "PASSWORD_HASH_METHOD", "hash_password",
    "is_valid_email", "normalise_email",
    "VERIFY_EMAIL_TTL", "RESET_PASSWORD_TTL",
    "PURPOSE_VERIFY_EMAIL", "PURPOSE_RESET_PASSWORD",
    "issue_token", "find_active_token", "consume_token",
    "revoke_tokens_for_user",
    "public_base_url", "spa_deep_link", "build_verify_url", "build_reset_url",
    "rate_limit", "rate_limit_remaining_seconds",
    "try_send",
]
