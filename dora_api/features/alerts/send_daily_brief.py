"""Daily-brief push job (owner call, 2026-08-17).

One push per opted-in user per day, at `DAILY_BRIEF_HOUR` **household-local**,
summarising tomorrow's meals and any shopping day that's due. The content is
assembled by `features/meal_plans/daily_brief.py`; this module owns only
*when* and *whether* it goes out.

Three deliberate differences from `send_alerts_push.py`, which pushes each
newly-fired alert as it fires:

  * **It's a digest, not a feed.** One notification carrying several facts,
    at a predictable hour — not N notifications whenever the evaluator
    changes its mind. That's the whole point: per-alert push is fine for
    "your milk expired", and wrong for "here's your evening".
  * **The hour is fixed, not configured.** Evening is the only hour where
    the brief is actionable (you can still defrost something or fill a gap in
    the plan), so making it a setting would add a control whose only sensible
    value is the default (Charter P1 Effortless).
  * **Silence is a feature.** A brief with nothing in it does not fire. A
    notification that arrives every day regardless is one you learn to swipe
    away without reading, which costs us the days it *did* matter.

Scheduled hourly and self-gated on the household clock rather than pinned to a
cron hour, because the scheduler is built once at startup from the *server's*
timezone while the household timezone is an AppSetting the user can change at
runtime (R-021). Self-gating means a timezone change takes effect that evening
instead of at the next restart.

Dedup rides the existing `AlertInteraction` ledger under a date-discriminated
key, the same trick `no_planned_meals` uses with its ISO-week label: one row
per (user, date), so an extra scheduler tick inside the brief hour — a restart,
a clock adjustment, a slow previous run — can't double-send.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, List
from uuid import UUID

from dora_api.app import app
from dora_api.domain.entities.alert_interaction import AlertInteraction
from dora_api.domain.entities.push_subscription import PushSubscription
from dora_api.domain.entities.user import User
from dora_api.features.meal_plans.daily_brief import (BuildDailyBriefHandler,
                                                      is_brief_hour)
from dora_api.features.app_settings.clock import household_timezone
from dora_api.infrastructure.push_sender import (PushGoneError, is_configured,
                                                 send_push)
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.features.alerts import _ledger as ledger

_LOGGER = logging.getLogger(__name__)


# 19:00 household-local. Late enough that the day's cooking is settled and the
# plan reflects reality; early enough to still act on it — defrost something,
# fill a gap, remember tomorrow is the shop. A morning brief was considered
# and rejected: by 9am it's too late to take the chicken out.
DAILY_BRIEF_HOUR = 19


def send_daily_brief(
    now: datetime | None = None,
    _send_push: Callable = send_push,
) -> int:
    """One scheduler tick. Returns the number of pushes sent, counted per
    device (a user with two phones and one brief adds 2).

    `now` and `_send_push` are the test seams — `now` is interpreted in the
    household timezone, so a test can drive the hour gate without freezing the
    system clock.
    """
    now = now or datetime.now(timezone.utc)
    sent = 0
    try:
        with app.app_context():
            # Same short-circuit as the alerts push job: with no VAPID
            # configured the sender is a dry-run logger, and stamping the
            # ledger from a job the install never authorised would suppress
            # the real brief once VAPID *is* set up.
            if not is_configured() and _send_push is send_push:
                return 0

            repository = SqlAlchemyRepository()
            local_now = now.astimezone(household_timezone(repository))
            if not is_brief_hour(local_now.hour, DAILY_BRIEF_HOUR):
                return 0
            # Already the household-local date, by construction — converting
            # `now` into that zone is exactly what `household_today` does.
            today = local_now.date()

            subscriptions_by_user = ledger.subscriptions_by_user(repository)
            for user in _opted_in_users(repository):
                subs = subscriptions_by_user.get(user.id)
                if not subs:
                    # Opted in but no device subscribed. Nothing to do, and
                    # nothing to stamp — the moment they subscribe, that
                    # evening's brief should still fire.
                    continue
                try:
                    sent += _process_user(
                        repository, user.id, subs, today, now, _send_push,
                    )
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.warning("daily_brief: user %s failed: %s", user.id, exc)
            if sent:
                _LOGGER.info(
                    "daily_brief: delivered %d push(es) at %s",
                    sent, local_now.isoformat(),
                )
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("daily_brief: job failed: %s", exc)
    return sent


def _opted_in_users(repository: SqlAlchemyRepository) -> List[User]:
    """Active users who asked for the brief. Deactivated accounts are excluded
    for the same reason they can't log in — a parked account shouldn't keep
    buzzing someone's phone."""
    return list(repository.get(User).all(
        EntityField(User, User.Fields.DAILY_BRIEF_ENABLED).eq(True)
        & EntityField(User, User.Fields.IS_ACTIVE).eq(True)
    ))


def brief_ledger_key(today) -> str:
    """`AlertInteraction.alert_key` for a given household date. Date-scoped so
    yesterday's row never suppresses today's brief, and so the ledger reads
    as an audit trail of which evenings actually sent."""
    return f"meal:daily_brief:{today.isoformat()}"


def _process_user(
    repository: SqlAlchemyRepository,
    user_id: UUID,
    subscriptions: list[PushSubscription],
    today,
    now: datetime,
    sender: Callable,
) -> int:
    key = brief_ledger_key(today)
    existing = ledger.interaction_for(repository, user_id, key)
    if existing is not None and existing.last_pushed_at is not None:
        return 0

    brief = BuildDailyBriefHandler(repository).handle(user_id=user_id, today=today)
    if brief.is_empty:
        # Nothing to say. Deliberately does NOT stamp the ledger — if the
        # user adds tomorrow's dinner at 19:20 the brief has genuinely
        # changed, and the next tick within the hour should send it.
        return 0

    payload = {
        "alert_id": key,
        "kind": "daily_brief",
        "severity": "low",
        "title": brief.title,
        "body": brief.body,
        "detail": None,
        "stock_item_id": None,
        "target_id": None,
        "url": brief.url,
    }

    sent_count = 0
    for sub in list(subscriptions):
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
                "daily_brief: pruning gone subscription %s (user=%s)",
                sub.endpoint[:80], user_id,
            )
            repository.remove(sub)
        except Exception as exc:  # noqa: BLE001
            # Transient — leave the row and retry on the next tick. Only
            # stamp the ledger if at least one device took it, so a total
            # send failure re-attempts rather than silently burning the day.
            _LOGGER.warning(
                "daily_brief: send failed for user=%s endpoint=%s: %s",
                user_id, sub.endpoint[:80], exc,
            )

    if sent_count > 0:
        if existing is None:
            repository.add(AlertInteraction(
                user_id=user_id,
                alert_key=key,
                created_at=now,
                last_pushed_at=now,
            ))
        else:
            existing.last_pushed_at = now
    repository.save_changes()
    return sent_count
