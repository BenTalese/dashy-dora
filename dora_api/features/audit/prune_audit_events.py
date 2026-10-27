"""Nightly job that prunes AuditEvent rows older than the retention window.

Registered in `dora_api/jobs.py` like the other scheduled jobs (it lived under
`infrastructure/` until finalisation 19-R18; it is a feature job that reads an
AppSetting, so it sits beside the audit feature). No-op when the table is
empty and never raises (a failure here must not take the API down).
The retention window is `AppSetting.audit_retention_days` (default 365),
edited in Settings → Admin → System → Hosting (FU-333 Bucket B).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from dora_api.app import app, db
from dora_api.features.app_settings.operational_config import \
    resolved_operational_config

_LOGGER = logging.getLogger(__name__)


DEFAULT_RETENTION_DAYS = 365


def retention_days() -> int:
    """Resolve the retention window through the operational-config
    resolver so a Settings edit takes effect on the next nightly run."""
    try:
        return max(1, resolved_operational_config().audit_retention_days)
    except Exception:
        return DEFAULT_RETENTION_DAYS


def prune_audit_events() -> int:
    """Delete events older than the retention cut-off. Returns the count
    deleted. Wrapped in app.app_context so it can run from APScheduler
    threads outside an HTTP request."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days())
    try:
        with app.app_context():
            table = db.metadata.tables["AuditEvent"]
            result = db.session.execute(
                delete(table).where(table.c.occurred_at < cutoff),
            )
            db.session.commit()
            deleted = result.rowcount or 0
            if deleted:
                _LOGGER.info(
                    "Audit retention pruned %d event(s) older than %s",
                    deleted, cutoff.isoformat(),
                )
            return deleted
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("Audit retention prune failed: %s", exc)
        return 0
