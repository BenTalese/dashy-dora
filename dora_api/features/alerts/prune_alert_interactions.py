"""Nightly prune of alert interactions that can never match again (FU-916).

Alert keys carry their episode (R-093: an expiry date, a level change, a shop
date), so every snooze or dismiss of a finished episode leaves a row no future
alert will ever have the key of. Harmless to correctness, unbounded over
years. A row goes when its key is no longer raised by the current state for
its user and it is older than the longest discard window, so nothing a user
could still see is touched.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from dora_api.app import app
from dora_api.domain.entities.alert_interaction import AlertInteraction
from dora_api.domain.entities.user import ALERT_DISCARD_DAY_OPTIONS
from dora_api.features.alerts.get_alerts import GetAlertsHandler
from dora_api.features.app_settings.clock import household_today
from dora_api.infrastructure.ports import Repository
from dora_api.persistence.aware import as_utc
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)

KEEP_DAYS = max(ALERT_DISCARD_DAY_OPTIONS)


def prune_finished_interactions(repository: Repository, now: datetime) -> int:
    cutoff = now - timedelta(days=KEEP_DAYS)
    rows: list[AlertInteraction] = repository.get(AlertInteraction).all()
    stale = [r for r in rows if as_utc(r.created_at) < cutoff]
    if not stale:
        return 0
    handler = GetAlertsHandler(repository)
    today = household_today(repository)
    live_by_user: dict = {}
    removed = 0
    for row in stale:
        if row.user_id not in live_by_user:
            live_by_user[row.user_id] = {a.alert_id for a in handler.raw_alerts(row.user_id, today)}
        if row.alert_key not in live_by_user[row.user_id]:
            repository.remove(row)
            removed += 1
    if removed:
        repository.save_changes()
    return removed


def prune_alert_interactions() -> int:
    """The scheduled entry point. Never raises: a failed sweep waits a day."""
    try:
        with app.app_context():
            removed = prune_finished_interactions(SqlAlchemyRepository(), datetime.now(timezone.utc))
            if removed:
                _LOGGER.info("Pruned %d finished alert interaction(s)", removed)
            return removed
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("Alert interaction prune failed: %s", exc)
        return 0
