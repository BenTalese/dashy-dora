"""Bearer-token auth lane for `POST /api/ingest` (C-10.1).

The ingestion endpoint is exempt from the session-cookie middleware: an
external producer can't carry a `dora_session` cookie. It instead sends
`Authorization: Bearer <key>` with a raw key minted on the admin "API
access" page; the key's SHA-256 hash lives in `IngestionSource`. This
module mirrors `auth_helpers._hash_token` (R-003 — one hashing path)
and gives `/api/ingest` a single place to validate the header.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from flask import request
from sqlalchemy import select

from dora_api.infrastructure.api_response import unauthorized
from dora_api.app import db
from dora_api.domain.entities.ingestion_source import IngestionSource


def hash_ingestion_key(raw: str) -> str:
    """SHA-256 hex digest. Mirrors `auth_helpers._hash_token`."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def mint_ingestion_key() -> str:
    """Generate a fresh raw key for a new IngestionSource. The caller
    persists the hash and returns the raw value to the admin exactly
    once."""
    return secrets.token_urlsafe(32)


def find_ingestion_source(raw_key: str) -> IngestionSource | None:
    """Return the enabled `IngestionSource` matching `raw_key`, or None
    if absent / disabled. Uses `hmac.compare_digest` on the hex digest
    so timing doesn't leak hash candidates.
    """
    if not raw_key:
        return None
    table = db.metadata.tables["IngestionSource"]
    candidate_hash = hash_ingestion_key(raw_key)
    rows = db.session.execute(
        select(table).where(table.c.enabled.is_(True))
    ).mappings().all()
    for row in rows:
        if hmac.compare_digest(row["key_hash"], candidate_hash):
            return db.session.get(IngestionSource, row["id"])
    return None


def extract_bearer_token() -> str | None:
    """Pull the raw token out of `Authorization: Bearer <key>`. Returns
    None on anything else (missing header, wrong scheme, empty value)."""
    header = request.headers.get("Authorization", "")
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def authenticate_ingestion_request():
    """The single front door check for every `/api/ingest/*` route.

    Returns `(source, None)` when the caller may proceed, or
    `(None, response)` with the response to return.

    **Authentication IS the gate.** An install-wide
    `companion_ingestion_enabled` toggle briefly sat here too and was removed
    the same day (owner call, migration `e7a2c4f9b361`): ingestion already
    requires a bearer key an admin minted, and every key is an
    `IngestionSource` with its own `enabled` flag. Not wanting ingestion means
    not minting a key, or disabling that source — per source, rather than
    install-wide. A second, coarser switch over the same door was redundant.

    Kept as a shared helper even without the flag, because it still collapses
    the identical four-line auth preamble across four routes (R-087).
    """
    raw_token = extract_bearer_token()
    source = find_ingestion_source(raw_token) if raw_token else None
    if source is None:
        return None, unauthorized("Bearer token missing or invalid.")

    return source, None


def stamp_used(source: IngestionSource) -> None:
    """Update `last_used_at` to now. Callers commit alongside their own
    write so the bump is atomic with the ingest result."""
    source.last_used_at = datetime.now(timezone.utc)
