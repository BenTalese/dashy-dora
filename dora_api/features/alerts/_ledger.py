"""Interaction-ledger reads shared by the alert endpoints and the delivery
jobs (push, daily brief, deals email): who has a device subscribed, one
user's ledger row for a key, and that user's whole ledger keyed by alert key."""
from __future__ import annotations

from uuid import UUID

from dora_api.domain.entities.alert_interaction import AlertInteraction
from dora_api.domain.entities.push_subscription import PushSubscription
from dora_api.infrastructure.ports import Repository
from dora_api.persistence.field import EntityField


def subscriptions_by_user(repository: Repository) -> dict[UUID, list[PushSubscription]]:
    grouped: dict[UUID, list[PushSubscription]] = {}
    for row in repository.get(PushSubscription).all():
        grouped.setdefault(row.user_id, []).append(row)
    return grouped


def interactions_by_key(repository: Repository, user_id: UUID) -> dict[str, AlertInteraction]:
    rows: list[AlertInteraction] = repository.get(AlertInteraction).all(
        EntityField(AlertInteraction, AlertInteraction.Fields.USER_ID).eq(user_id)
    )
    return {row.alert_key: row for row in rows}


def interaction_for(repository: Repository, user_id: UUID, alert_key: str) -> AlertInteraction | None:
    return repository.get(AlertInteraction).one(
        EntityField(AlertInteraction, AlertInteraction.Fields.USER_ID).eq(user_id)
        & EntityField(AlertInteraction, AlertInteraction.Fields.ALERT_KEY).eq(alert_key)
    )
