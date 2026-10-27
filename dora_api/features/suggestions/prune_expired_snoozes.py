"""Periodic job that prunes elapsed snoozes from DoraSuggestionSuppression.

Wired in `startup.py` via APScheduler. Runs daily. Dismissed rows are
permanent (they're the user's "never remind me" decision until the
underlying condition changes) — only snoozed rows whose `snoozed_until`
has passed are eligible.

Historically this cleanup ran inline on every `GET /api/suggestions`
request, taking a write lock on the hot dashboard read path. Moved
out of the request path per FU-513 (2026-07-08): the read filter in
`suggestions._is_suppressed_now` already ignores expired snoozes, so
correctness never depended on inline pruning — the table just needs an
occasional sweep so it doesn't accrete stale rows.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import and_, delete

from dora_api.app import app, db
from dora_api.domain.entities.dora_suggestion_suppression import \
    SUPPRESSION_DECISION_SNOOZED

_LOGGER = logging.getLogger(__name__)


def prune_expired_snoozes() -> int:
    """Delete snoozed suppressions whose `snoozed_until` is in the past.
    Returns the count deleted. Wrapped in `app.app_context` so it can
    run from APScheduler threads outside an HTTP request. Never raises
    — a failure here must not take the API down."""
    now = datetime.now(timezone.utc)
    try:
        with app.app_context():
            table = db.metadata.tables["DoraSuggestionSuppression"]
            result = db.session.execute(
                delete(table).where(and_(
                    table.c.decision == SUPPRESSION_DECISION_SNOOZED,
                    table.c.snoozed_until.is_not(None),
                    table.c.snoozed_until <= now,
                )),
            )
            db.session.commit()
            deleted = result.rowcount or 0
            if deleted:
                _LOGGER.info(
                    "Pruned %d expired suggestion snooze(s) (cutoff=%s)",
                    deleted, now.isoformat(),
                )
            return deleted
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("Snooze prune failed: %s", exc)
        return 0
