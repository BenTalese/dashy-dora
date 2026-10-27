"""Weekly deals email job — *when* and *whether* it goes out (FU-789).

Built 2026-08-29. Until then this feature was a settings toggle, four database
columns, an admin column and a health flag with **nothing behind them** — no
job, no sender, no template — so subscribing set a boolean nothing read.
`startup.py` had even been siting the audit sweep "well clear of any
deals-email schedule" for a schedule that was never registered.

Shaped after `alerts/send_daily_brief.py`, for the same reasons and with the
same seams:

  * **Registered hourly, self-gated on the household clock.** The scheduler is
    built once at startup from the *server's* timezone, while the household
    timezone is an AppSetting the user can change at runtime (R-021). Gating
    inside the job means a timezone change takes effect that week rather than
    at the next restart.
  * **Dedup rides the `AlertInteraction` ledger**, under a week-scoped key —
    the same trick the daily brief uses with its date-scoped one. One row per
    (user, ISO week), so a restart, a slow previous run or a clock adjustment
    inside the send hour cannot mail the same deals twice. Reusing that table
    rather than adding one keeps this feature migration-free.
  * **Nothing to say ⇒ nothing sent, and nothing stamped.** A week with no
    active specials does not send an empty mail, and does not burn the ledger
    row either — if the companion tool pushes data at 07:20 the mail should
    still go out on the next tick within the hour.

The gate chain, outermost first: SMTP configured → the household send hour → per-user opt-in, active
account and a *verified* address → this user's chosen weekday → a non-empty
digest.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, List

from dora_api.app import app
from dora_api.domain.entities.alert_interaction import AlertInteraction
from dora_api.domain.entities.user import User
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.features.app_settings.clock import household_timezone
from dora_api.features.deals.deals_digest import (DealsDigest, build_digest,
                                                  deals_ledger_key,
                                                  is_deals_hour, is_send_day,
                                                  subject_line)
from dora_api.features.products.get_products import GetBestDealsHandler
from dora_api.infrastructure.auth_helpers import spa_deep_link
from dora_api.infrastructure.email_sender import (email_sender_configured,
                                                  render_template, send_email)
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.features.alerts import _ledger as ledger

_LOGGER = logging.getLogger(__name__)


# The ranked pool the two formats draw from. Deliberately larger than either
# format's cap so the compact list has its full 20 available, and so a couple
# of products failing the re-check in `build_deal_lines` doesn't shorten the
# mail. `GetBestDealsHandler` caps at whatever we ask for; the HTTP endpoint's
# own max of 20 is a URL-parameter guard, not a domain limit, so it does not
# apply here.
DEAL_POOL_SIZE = 40


# SPA routes the mail links to; pinned against `routes.ts` by the deals tests.
DEALS_ROUTE = "/my-products"
UNSUBSCRIBE_ROUTE = "/settings/notifications"


def send_deals_email(
    now: datetime | None = None,
    _send_email: Callable = send_email,
) -> int:
    """One scheduler tick. Returns the number of emails sent.

    `now` and `_send_email` are the test seams — `now` is interpreted in the
    household timezone so a test can drive the hour and weekday gates without
    touching the system clock.
    """
    now = now or datetime.now(timezone.utc)
    sent = 0
    try:
        with app.app_context():
            # Same short-circuit as the push jobs' VAPID check: with no SMTP
            # username the sender is a dry-run logger, and stamping the ledger
            # from a send the install never actually made would suppress the
            # real mail once SMTP *is* configured.
            if not email_sender_configured() and _send_email is send_email:
                return 0

            repository = SqlAlchemyRepository()
            setting = get_or_create_app_setting(repository)
            local_now = now.astimezone(household_timezone(repository))
            if not is_deals_hour(local_now.hour):
                return 0
            today = local_now.date()

            recipients = [
                user for user in _opted_in_users(repository)
                if is_send_day(today, user.send_deals_on_day or 0)
            ]
            if not recipients:
                return 0

            # One ranked pool per tick, shared across recipients — the deals
            # are install-wide facts, and re-running the scan per user would
            # walk every product N times to produce the same list.
            currency = getattr(setting, "currency", None) or "AUD"
            product_dtos = GetBestDealsHandler(repository).handle(DEAL_POOL_SIZE)

            deals_url = spa_deep_link(DEALS_ROUTE)
            unsubscribe_url = spa_deep_link(UNSUBSCRIBE_ROUTE)

            for user in recipients:
                try:
                    sent += _process_user(
                        repository, user, product_dtos, currency, today, now,
                        deals_url, unsubscribe_url, _send_email,
                    )
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.warning("deals_email: user %s failed: %s", user.id, exc)
            if sent:
                _LOGGER.info(
                    "deals_email: delivered %d email(s) at %s",
                    sent, local_now.isoformat(),
                )
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("deals_email: job failed: %s", exc)
    return sent


def _opted_in_users(repository: SqlAlchemyRepository) -> List[User]:
    """Active subscribers with a verified address.

    `email_verified` is a real gate, not belt-and-braces. This is the only mail
    Dora sends *repeatedly and unprompted*; every other one is a reply to
    something the recipient just did. An unverified address is one nobody has
    proved they own, and mailing it weekly is precisely the harm verification
    exists to prevent — so an unverified subscriber is skipped, loudly, rather
    than mailed. Settings → Notifications tells them why, so the skip is
    visible from the surface that set the preference rather than only in a log
    nobody reads.
    """
    users: List[User] = list(repository.get(User).all(
        EntityField(User, User.Fields.DEALS_EMAIL_ENABLED).eq(True)
        & EntityField(User, User.Fields.IS_ACTIVE).eq(True)
    ))
    ready: List[User] = []
    for user in users:
        if not (user.email or "").strip():
            continue
        if not user.email_verified:
            _LOGGER.info(
                "deals_email: skipping user %s — address not verified", user.id,
            )
            continue
        ready.append(user)
    return ready


def _process_user(
    repository: SqlAlchemyRepository,
    user: User,
    product_dtos,
    currency: str,
    today,
    now: datetime,
    deals_url: str,
    unsubscribe_url: str,
    sender: Callable,
) -> int:
    key = deals_ledger_key(today)
    existing = ledger.interaction_for(repository, user.id, key)
    if existing is not None and existing.last_pushed_at is not None:
        return 0

    digest = build_digest(
        product_dtos, currency, compact=bool(user.deals_email_compact),
    )
    if digest.is_empty:
        # No specials running. Deliberately does not stamp — see the module
        # docstring; data can land later in the same hour.
        return 0

    subject = subject_line(digest)
    sender(
        to=user.email,
        subject=subject,
        html_body=render_template(
            "weekly_deals.html",
            subject=subject,
            display_name=user.username,
            lines=digest.lines,
            compact=bool(user.deals_email_compact),
            deals_url=deals_url,
            unsubscribe_url=unsubscribe_url,
        ),
        text_body=_text_body(digest, unsubscribe_url),
    )

    if existing is None:
        repository.add(AlertInteraction(
            user_id=user.id,
            alert_key=key,
            created_at=now,
            last_pushed_at=now,
        ))
    else:
        existing.last_pushed_at = now
    repository.save_changes()
    return 1


def _text_body(digest: DealsDigest, unsubscribe_url: str) -> str:
    """The plain-text alternative. Always sent — a text/plain part is what
    keeps the mail out of a spam folder and readable in a text client, and
    building it from the same `DealLine`s means it cannot disagree with the
    HTML about a price."""
    rows = [
        f"- {line.name} ({line.size}): {line.price_now} "
        f"was {line.price_was}, {line.discount_percent}% off at {line.store_name}"
        for line in digest.lines
    ]
    return (
        "This week's deals from your Dora install:\n\n"
        + "\n".join(rows)
        + f"\n\nTurn this email off: {unsubscribe_url}\n"
    )
