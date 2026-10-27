"""C-9.8 — Web Push sender (RFC 8030 + VAPID).

Wraps `pywebpush` so the rest of the codebase doesn't import a third-
party HTTP client. Mirrors `email_sender.py` shape: a single send_*
function, a dry-run mode when the install isn't configured, and the
config read in one place.

All three VAPID fields live on ``AppSetting`` (FU-333 Buckets B + C).
The private key is stored encrypted-at-rest with the Fernet helper
from FU-153 and decrypted on demand by the resolver. Admins edit
everything from Settings → Admin → System → Push.

When either half is missing the sender is in **dry-run** mode (logs
the push, returns success). This keeps an unconfigured install
bootable and lets developers test the surrounding plumbing without
generating keys.

Generate a key pair with `py-vapid`'s CLI (bundled with pywebpush):
    python -m py_vapid --gen --applicationServerKey
which prints the public key + writes `private_key.pem`.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from pywebpush import WebPushException, webpush

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _VapidConfig:
    public_key: str
    private_key: str
    subject: str
    dry_run: bool


_DRY_RUN_CONFIG = _VapidConfig(
    public_key="", private_key="", subject="mailto:admin@dora.local", dry_run=True,
)


def _config() -> _VapidConfig:
    """Read the resolved AppSetting-backed VAPID config. If the DB isn't
    available (a unit test importing this module without a Flask context)
    return a dry-run config so callers still no-op safely."""
    from dora_api.features.app_settings.operational_config import \
        resolved_operational_config
    try:
        op = resolved_operational_config()
    except Exception:
        return _DRY_RUN_CONFIG
    return _VapidConfig(
        public_key=op.vapid_public_key,
        private_key=op.vapid_private_key,
        subject=op.vapid_subject or "mailto:admin@dora.local",
        # Either half missing → can't sign / can't be subscribed to →
        # dry-run. The frontend toggle is independently gated on the
        # health flag, so this only matters if someone hand-edits a
        # subscription row.
        dry_run=not (op.vapid_public_key and op.vapid_private_key),
    )


def is_configured() -> bool:
    """True when both VAPID halves are set. Read by the health endpoint
    so the SPA's push toggle reflects whether real pushes can leave the
    box."""
    return not _config().dry_run


def vapid_public_key() -> str | None:
    """Public key the SPA needs for `pushManager.subscribe({applicationServerKey})`.
    Returns None when VAPID isn't configured (the SPA treats that as
    "push channel disabled")."""
    cfg = _config()
    return cfg.public_key or None


class PushGoneError(Exception):
    """The subscription endpoint is permanently gone (HTTP 404/410). The
    caller should delete the row — the browser unregistered or the
    user revoked permission. Distinct from a transient 5xx so the job
    can prune without retrying."""


def send_push(
    *,
    endpoint: str,
    p256dh: str,
    auth: str,
    payload: dict[str, Any],
) -> None:
    """Send a single push synchronously. Raises `PushGoneError` for
    permanent failures (so the caller can drop the subscription row),
    or `WebPushException` for transient errors. In dry-run mode this is
    a no-op apart from a log line."""
    cfg = _config()
    if cfg.dry_run:
        _LOGGER.info(
            "DRY-RUN push | endpoint=%s | payload=%s",
            endpoint, json.dumps(payload, default=str),
        )
        return
    try:
        webpush(
            subscription_info={
                "endpoint": endpoint,
                "keys": {"p256dh": p256dh, "auth": auth},
            },
            data=json.dumps(payload, default=str),
            vapid_private_key=cfg.private_key,
            vapid_claims={"sub": cfg.subject},
            # 24h TTL keeps a quiet device able to wake to an alert that
            # was queued while it was offline; longer than that and the
            # alert state is likely stale anyway.
            ttl=86400,
        )
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (404, 410):
            raise PushGoneError(endpoint) from exc
        raise
