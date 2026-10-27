"""Per-user alert interaction endpoints (C-9.1):

  POST   /api/alerts/<alert_id>/snooze      — body { days }  (default 7)
  POST   /api/alerts/<alert_id>/dismiss     — hide for the rest of this episode
  DELETE /api/alerts/<alert_id>/suppression — undo snooze/dismiss
  POST   /api/alerts/dismiss-all            — dismiss every active alert

There is no read state (owner 2026-10-15: *"What's the difference between
dismiss and mark as read? We only need dismiss right?"*). Read/unread and
read-all were removed with the `read_at` column.

Alerts are derived from live state, so we don't store them — we store the
user's *decisions* about them in `AlertInteraction`, keyed by the alert's
stable `<scope>:<id>:<kind>` key. The GET /alerts handler overlays these so
the badge, list, and (later) channels all agree (PROPOSAL_ALERTS §3.4).

`<alert_id>` is the scoped key; it contains ':' but no '/', so Flask's
default string converter matches it as a single path segment.
"""
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.alert_interaction import AlertInteraction
from dora_api.features.alerts import _ledger as ledger
from dora_api.features.alerts.get_alerts import GetAlertsHandler
from dora_api.features.routers import ALERT_ROUTER
from dora_api.infrastructure.api_response import no_content, unauthorized
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.session_user import current_user_id

_LOGGER = logging.getLogger(__name__)


class SnoozeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    days: int = Field(default=7, ge=1, le=365)


# Matches the `AlertInteraction.alert_key` column width (String(255) in
# table_mappings.py). A real key is `<scope>:<uuid>:<kind>` — comfortably
# under this — so anything longer names no alert. SQLite silently accepts an
# over-length write; Postgres raises `StringDataRightTruncation` (a 500). We
# reject it at the boundary instead: a non-existent alert is an idempotent
# no-op, same as `clear_suppression` on an unknown key.
_ALERT_KEY_MAX_LENGTH = 255


class AlertInteractionHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def _get_or_create(self, user_id: UUID, alert_key: str) -> AlertInteraction | None:
        if len(alert_key) > _ALERT_KEY_MAX_LENGTH:
            return None
        existing = ledger.interaction_for(self.repository, user_id, alert_key)
        if existing is not None:
            return existing
        interaction = AlertInteraction(
            user_id=user_id,
            alert_key=alert_key,
            created_at=datetime.now(timezone.utc),
        )
        self.repository.add(interaction)
        return interaction

    def snooze(self, user_id: UUID, alert_key: str, days: int) -> None:
        interaction = self._get_or_create(user_id, alert_key)
        if interaction is None:
            return
        interaction.snoozed_until = datetime.now(timezone.utc) + timedelta(days=days)
        interaction.dismissed_at = None
        self.repository.save_changes()

    def dismiss(self, user_id: UUID, alert_key: str) -> None:
        interaction = self._get_or_create(user_id, alert_key)
        if interaction is None:
            return
        interaction.dismissed_at = datetime.now(timezone.utc)
        self.repository.save_changes()

    def clear_suppression(self, user_id: UUID, alert_key: str) -> None:
        interaction = ledger.interaction_for(self.repository, user_id, alert_key)
        if interaction is not None:
            interaction.snoozed_until = None
            interaction.dismissed_at = None
            self.repository.save_changes()

    def dismiss_all(self, user_id: UUID) -> None:
        # Server-derived: dismiss exactly the user's current active set.
        alerts = GetAlertsHandler(self.repository).handle(user_id)
        now = datetime.now(timezone.utc)
        for alert in alerts.items:
            interaction = self._get_or_create(user_id, alert.alert_id)
            if interaction is not None:
                interaction.dismissed_at = now
        if alerts.items:
            self.repository.save_changes()


@ALERT_ROUTER.route("/dismiss-all", methods=["POST"])
def dismiss_all_alerts():
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()
    AlertInteractionHandler(SqlAlchemyRepository()).dismiss_all(user_id)
    return no_content()


@ALERT_ROUTER.route("/<alert_id>/snooze", methods=["POST"])
@has_request_body(SnoozeRequest)
def snooze_alert(alert_id: str):
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()
    _Request: SnoozeRequest = get_request_body()
    AlertInteractionHandler(SqlAlchemyRepository()).snooze(user_id, alert_id, _Request.days)
    _LOGGER.info("Alert %s snoozed %dd by %s", alert_id, _Request.days, user_id)
    return no_content()


@ALERT_ROUTER.route("/<alert_id>/dismiss", methods=["POST"])
def dismiss_alert(alert_id: str):
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()
    AlertInteractionHandler(SqlAlchemyRepository()).dismiss(user_id, alert_id)
    return no_content()


@ALERT_ROUTER.route("/<alert_id>/suppression", methods=["DELETE"])
def clear_alert_suppression(alert_id: str):
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()
    AlertInteractionHandler(SqlAlchemyRepository()).clear_suppression(user_id, alert_id)
    return no_content()
