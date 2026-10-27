"""C-9.8 — Alerts web-push job.

Hourly tick. For each user with at least one active push subscription,
evaluates the canonical actionable set (`GetAlertsHandler` — R-003,
same source the in-app hub and email digest read), then pushes every
**newly-fired** alert (not present → present in the ledger, dedup'd via
`AlertInteraction.last_pushed_at`) to every browser the user has
subscribed.

Dedup: stale-flag cleanup at the top of each user's iteration resets
`last_pushed_at` for any key that's no longer in the user's known set,
so a later re-fire pushes fresh. This is now the only delivery channel
with a dedup column — the email digest and its `last_emailed_at`
sibling were cut at Step-0 Q4.

When a push fails permanently (HTTP 404/410 — browser unregistered or
permission revoked), the subscription row is deleted so we don't keep
retrying it forever.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from dora_api.app import app
from dora_api.domain.entities.alert_interaction import AlertInteraction
from dora_api.domain.entities.push_subscription import PushSubscription
from dora_api.features.alerts import _ledger as ledger
from dora_api.features.alerts.alert_kinds import TIER_ACTIONABLE
from dora_api.features.alerts.get_alerts import (AlertDto, AlertsDto,
                                                 GetAlertsHandler)
from dora_api.infrastructure.push_sender import (PushGoneError, is_configured,
                                                 send_push)
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)


def send_alerts_push(
    now: datetime | None = None,
    _send_push: Callable = send_push,
) -> int:
    """One scheduler tick. Returns the number of pushes sent (counted
    per (alert, device) — a user with 3 devices and 2 new alerts adds 6).

    `_send_push` is the test seam (defaults to the production sender).
    """
    now = now or datetime.now(timezone.utc)
    sent = 0
    try:
        with app.app_context():
            # Short-circuit when VAPID isn't configured. The dry-run path
            # in the sender would still update last_pushed_at — fine if
            # the user is testing locally; but the more honest behaviour
            # is to do nothing at all so an unconfigured install never
            # mutates ledger state from a job they didn't authorise.
            if not is_configured() and _send_push is send_push:
                return 0
            repository = SqlAlchemyRepository()
            subscriptions_by_user = ledger.subscriptions_by_user(repository)
            for user_id, subs in subscriptions_by_user.items():
                try:
                    sent += _process_user(repository, user_id, subs, now, _send_push)
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.warning(
                        "alerts_push: user %s failed: %s", user_id, exc,
                    )
            if sent:
                _LOGGER.info(
                    "alerts_push: delivered %d push(es) at %s",
                    sent, now.isoformat(),
                )
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("alerts_push: job failed: %s", exc)
    return sent


def _process_user(
    repository: SqlAlchemyRepository,
    user_id: UUID,
    subscriptions: list[PushSubscription],
    now: datetime,
    sender: Callable,
) -> int:
    alerts: AlertsDto = GetAlertsHandler(repository).handle(user_id=user_id)
    current_keys = {a.alert_id for a in alerts.items} | {
        a.alert_id for a in alerts.snoozed
    }

    interactions_by_key = ledger.interactions_by_key(repository, user_id)

    # Stale-flag cleanup: any prior push-stamp for a key the user no
    # longer has resets, so a future re-fire pushes fresh.
    dirty = False
    for key, row in interactions_by_key.items():
        if row.last_pushed_at is not None and key not in current_keys:
            row.last_pushed_at = None
            dirty = True

    # Only push **actionable** alerts (PROPOSAL_ALERTS §3.5: push is for
    # things that need a response; FYI nudges stay in the hub + digest
    # so a quiet device doesn't buzz for low-signal items). Skip the
    # ones we've already pushed this cycle.
    to_push: list[AlertDto] = [
        a for a in alerts.items
        if a.tier == TIER_ACTIONABLE
        and _not_yet_pushed(interactions_by_key.get(a.alert_id))
    ]

    if not to_push:
        if dirty:
            repository.save_changes()
        return 0

    # Fan out: one push per (alert × subscription). Dead subscriptions
    # get pruned mid-fan so a 404'd device doesn't waste cycles for
    # every alert in the same tick.
    sent_count = 0
    live_subs = list(subscriptions)
    for alert in to_push:
        payload = _payload_for(alert)
        dropped: list[PushSubscription] = []
        for sub in live_subs:
            try:
                sender(
                    endpoint=sub.endpoint,
                    p256dh=sub.p256dh,
                    auth=sub.auth,
                    payload=payload,
                )
                sub.last_seen_at = now
                sent_count += 1
            except PushGoneError:
                _LOGGER.info(
                    "alerts_push: pruning gone subscription %s (user=%s)",
                    sub.endpoint[:80], user_id,
                )
                repository.remove(sub)
                dropped.append(sub)
            except Exception as exc:  # noqa: BLE001
                # Transient (5xx, network) — leave the row alone and
                # retry on the next tick. Don't stamp last_pushed_at
                # for this device, but don't bail on the whole batch.
                _LOGGER.warning(
                    "alerts_push: send failed for user=%s endpoint=%s: %s",
                    user_id, sub.endpoint[:80], exc,
                )
        for d in dropped:
            live_subs.remove(d)
        # Stamp the ledger once per alert (not per device) — coarse
        # dedup keyed on the alert key, matching the email channel.
        row = interactions_by_key.get(alert.alert_id)
        if row is None:
            row = AlertInteraction(
                user_id=user_id,
                alert_key=alert.alert_id,
                created_at=now,
                last_pushed_at=now,
            )
            repository.add(row)
            interactions_by_key[alert.alert_id] = row
        else:
            row.last_pushed_at = now
        if not live_subs:
            # The user's last device is gone; nothing else to send this
            # tick. Future ticks will see no subscriptions and skip.
            break

    repository.save_changes()
    return sent_count


def _not_yet_pushed(row: AlertInteraction | None) -> bool:
    return row is None or row.last_pushed_at is None


def _payload_for(alert: AlertDto) -> dict[str, object]:
    """Push payload shape consumed by `web_app/public/push-sw.js`. Kept
    small (web-push body is size-constrained ~4KB) and stable — the SW
    pattern-matches on `kind` for icon routing."""
    return {
        "alert_id": alert.alert_id,
        "kind": alert.kind,
        "severity": alert.severity,
        "title": "Dashy Dora",
        "body": alert.message,
        "detail": alert.detail,
        "stock_item_id": str(alert.stock_item_id) if alert.stock_item_id else None,
        "target_id": alert.target_id,
        # The alerts page is gone (owner 2026-10-15); the SPA opens the bell
        # panel on `?alerts=open`. Hash route: the SPA runs in hash mode.
        "url": "/#/?alerts=open",
    }
