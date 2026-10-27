"""Per-user alert preferences (C-9.2):

  GET   /api/alerts/prefs   — this user's per-kind prefs (stored rows merged
                              with the defaults, so the UI sees every kind)
  PATCH /api/alerts/prefs   — upsert one kind's pref { kind, enabled }

Preferences are per-user: how quiet or noisy alerts are is inherently personal,
even in a single-household install (PROPOSAL_ALERTS §9 — read/quiet state, NOT
tenancy). The evaluator (`get_alerts.py`) applies them — a disabled kind is
omitted from that user's set, counts, row outlines and channels. Absent row =
enabled.

An on/off switch is the *whole* model (Step-0 Q2): the feedback ask was "as
quiet or noisy as they want" (L441), which on/off satisfies. The per-user
`tier_override` that used to sit beside it is gone — see `alert_preference.py`.
"""
import logging
from dataclasses import dataclass
from typing import List
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from dora_api.domain.entities.alert_preference import AlertPreference
from dora_api.features.alerts.alert_kinds import (KNOWN_KINDS, is_known_kind,
                                                  severity_for, tier_for)
from dora_api.features.app_settings.access import (get_or_create_app_setting,
                                                  money_features_enabled)
from dora_api.features.routers import ALERT_ROUTER
from dora_api.infrastructure.api_response import bad_request, ok, unauthorized
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.session_user import current_user_id

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AlertPrefDto:
    kind: str
    enabled: bool
    severity: str
    tier: str
    # False when this install can't raise the kind at all, so Settings hides
    # its toggle: a price watch needs money features, and the reconcile nudge
    # is for households that confirm past meals by hand.
    available: bool


@dataclass(frozen=True, slots=True)
class AlertPrefsDto:
    prefs: List[AlertPrefDto]


class UpdateAlertPrefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    enabled: bool | None = None


class AlertPrefsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def _rows(self, user_id: UUID) -> dict[str, AlertPreference]:
        rows: List[AlertPreference] = self.repository.get(AlertPreference).all(
            EntityField(AlertPreference, AlertPreference.Fields.USER_ID).eq(user_id)
        )
        return {row.kind: row for row in rows}

    def _unavailable_kinds(self) -> frozenset[str]:
        unavailable: set[str] = set()
        if not money_features_enabled(self.repository):
            unavailable.add("price_drop")
        if get_or_create_app_setting(self.repository).auto_drain_past_meals:
            unavailable.add("meal_reconcile_overdue")
        return frozenset(unavailable)

    def get_prefs(self, user_id: UUID) -> AlertPrefsDto:
        stored = self._rows(user_id)
        unavailable = self._unavailable_kinds()
        prefs: List[AlertPrefDto] = []
        for kind in sorted(KNOWN_KINDS):
            row = stored.get(kind)
            prefs.append(AlertPrefDto(
                kind=kind,
                enabled=row.enabled if row is not None else True,
                severity=severity_for(kind),
                tier=tier_for(kind),
                available=kind not in unavailable,
            ))
        return AlertPrefsDto(prefs=prefs)

    def update_pref(self, user_id: UUID, request: UpdateAlertPrefRequest) -> None:
        existing = self.repository.get(AlertPreference).one(
            EntityField(AlertPreference, AlertPreference.Fields.USER_ID).eq(user_id)
            & EntityField(AlertPreference, AlertPreference.Fields.KIND).eq(request.kind)
        )
        if existing is None:
            existing = AlertPreference(user_id=user_id, kind=request.kind)
            self.repository.add(existing)
        set_fields = request.model_fields_set
        if "enabled" in set_fields and request.enabled is not None:
            existing.enabled = request.enabled
        self.repository.save_changes()


@ALERT_ROUTER.route("/prefs", methods=["GET"])
def get_alert_prefs():
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()
    return ok(AlertPrefsHandler(SqlAlchemyRepository()).get_prefs(user_id))


@ALERT_ROUTER.route("/prefs", methods=["PATCH"])
@has_request_body(UpdateAlertPrefRequest)
def update_alert_pref():
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()
    request: UpdateAlertPrefRequest = get_request_body()
    # R-010 — validate against the known vocabulary on write, not just read.
    if not is_known_kind(request.kind):
        return bad_request(f"Unknown alert kind '{request.kind}'.")
    handler = AlertPrefsHandler(SqlAlchemyRepository())
    handler.update_pref(user_id, request)
    _LOGGER.info("Alert pref updated: kind=%s by %s", request.kind, user_id)
    return ok(handler.get_prefs(user_id))
