"""P2-04 — Dora Suggestion endpoints.

  GET  /api/suggestions                — current proposals (filtered by
                                          suppressions)
  POST /api/suggestions/dismiss        — body { kind, dedup_key }
  POST /api/suggestions/snooze         — body { kind, dedup_key, hours }
  POST /api/suggestions/unsuppress    — body { kind, dedup_key }  — undo

The endpoint deliberately doesn't expose an "accept" action: accepting
runs an existing domain endpoint (open the route, add to list, mark Out
of Stock, …) and the next /api/suggestions call observes that the
underlying condition is no longer true. This keeps mutation paths
auditable and centralised in their feature handlers, with no
"suggestion-says-do-this" indirection.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.persistence.aware import as_utc
from dora_api.domain.entities.dora_suggestion_suppression import (
    DoraSuggestionSuppression, SUPPRESSION_DECISION_DISMISSED,
    SUPPRESSION_DECISION_SNOOZED,
)
from dora_api.features.routers import SUGGESTIONS_ROUTER
from dora_api.features.suggestions.generators import generate_all, Suggestion
from dora_api.infrastructure.api_response import no_content, ok
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.session_user import current_user_id

_LOGGER = logging.getLogger(__name__)


# Cap the surfaced count — the dashboard card + chat panel are designed
# for a glance, not a queue. The full firehose is available via
# /api/waste, /api/budget, etc.
_MAX_SUGGESTIONS = 8

# Severity → sort weight. Higher numbers mean more urgent.
_SEVERITY_RANK = {"high": 2, "medium": 1, "low": 0}


def _select_for_display(suggestions: list[Suggestion], limit: int) -> list[Suggestion]:
    """Rank + truncate to `limit`, with per-kind fairness (FU-593).

    A plain severity-desc truncation lets one noisy category monopolise the
    whole cap: on a busy pantry `use_soon` alone emits 8+ HIGH cards, so a
    low-severity-but-distinct nudge (e.g. `reconcile_meals_pending`) was
    dropped entirely — silently, exactly when the kitchen is busiest and
    reconciling matters most. So we guarantee **every firing kind at least
    one slot** before any kind takes a second, then fill the remaining slots
    by severity. Within that, severity ordering is preserved (a HIGH card
    still outranks a LOW one for the shared slots, and each kind's own
    representative is its highest-severity card).
    """
    ranked = sorted(
        suggestions,
        key=lambda s: (-_SEVERITY_RANK.get(s.severity, 0), s.title.lower()),
    )
    if len(ranked) <= limit:
        return ranked

    # First pass over the severity-ordered list: each kind's first (=
    # highest-severity) card is reserved; the rest queue behind it.
    first_of_kind: list[Suggestion] = []
    rest: list[Suggestion] = []
    seen_kinds: set[str] = set()
    for sugg in ranked:
        if sugg.kind not in seen_kinds:
            seen_kinds.add(sugg.kind)
            first_of_kind.append(sugg)
        else:
            rest.append(sugg)

    selected = first_of_kind[:limit]
    remaining = limit - len(selected)
    if remaining > 0:
        selected.extend(rest[:remaining])

    # Re-order the final selection for display (severity desc, then title).
    selected.sort(
        key=lambda s: (-_SEVERITY_RANK.get(s.severity, 0), s.title.lower()),
    )
    return selected


def _is_suppressed_now(suppression: DoraSuggestionSuppression, now: datetime) -> bool:
    if suppression.decision == SUPPRESSION_DECISION_DISMISSED:
        return True
    if suppression.decision == SUPPRESSION_DECISION_SNOOZED:
        until = suppression.snoozed_until
        if until is None:
            return True
        # SQLite drops tzinfo on read; `as_utc` so the comparison against
        # tz-aware `now` doesn't raise.
        return as_utc(until) > now
    return False


# ── GET /api/suggestions ────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class SuggestionDto:
    kind: str
    dedup_key: str
    severity: str
    title: str
    body: str
    reason: str
    primary_action: dict[str, str] | None
    payload: dict[str, Any]


class GetSuggestionsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, user_id: UUID | None) -> list[SuggestionDto]:
        suggestions: list[Suggestion] = generate_all(self.repository, user_id)
        if not suggestions:
            return []

        # Active suppressions for the (kind, dedup_key)s we just
        # generated. We fetch the whole table and filter in Python — the
        # row count is bounded by user decisions and a composite index
        # exists on (kind, dedup_key) for the lookup pattern.
        # Expired snoozes are ignored by `_is_suppressed_now`; a daily
        # APScheduler job (`prune_expired_snoozes`) sweeps them out of
        # the table so this read path is write-free. FU-513, 2026-07-08:
        # the previous inline delete-and-commit here took a write lock
        # on every dashboard load, which is unacceptable under contention
        # and violates the "GETs don't mutate" contract downstream tooling
        # (browser caches, retry logic) relies on.
        now = datetime.now(timezone.utc)
        suppressions = self.repository.get(DoraSuggestionSuppression).all()
        active_suppressions = {
            (s.kind, s.dedup_key)
            for s in suppressions
            if _is_suppressed_now(s, now)
        }

        filtered = [
            sugg for sugg in suggestions
            if (sugg.kind, sugg.dedup_key) not in active_suppressions
        ]
        selected = _select_for_display(filtered, _MAX_SUGGESTIONS)

        return [
            SuggestionDto(
                kind=s.kind,
                dedup_key=s.dedup_key,
                severity=s.severity,
                title=s.title,
                body=s.body,
                reason=s.reason,
                primary_action=s.primary_action,
                payload=s.payload,
            )
            for s in selected
        ]


@SUGGESTIONS_ROUTER.route("", methods=["GET"])
def get_suggestions():
    user_id = current_user_id()
    rows = GetSuggestionsHandler(SqlAlchemyRepository()).handle(user_id)
    _LOGGER.debug("Generated %d suggestions for user=%s", len(rows), user_id)
    return ok({"suggestions": rows, "count": len(rows)})


# ── POST /api/suggestions/dismiss ───────────────────────────────────────

class DismissSuggestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(min_length=1, max_length=64)
    dedup_key: str = Field(min_length=1, max_length=255)


@SUGGESTIONS_ROUTER.route("/dismiss", methods=["POST"])
@has_request_body(DismissSuggestionRequest)
def dismiss_suggestion():
    body: DismissSuggestionRequest = get_request_body()
    repo = SqlAlchemyRepository()
    # If the user previously snoozed the same key, replace that row with
    # a dismiss — dismissing is a strictly stronger signal.
    existing = repo.get(DoraSuggestionSuppression).one(
        EntityField(DoraSuggestionSuppression, DoraSuggestionSuppression.Fields.KIND).eq(body.kind)
        & EntityField(DoraSuggestionSuppression, DoraSuggestionSuppression.Fields.DEDUP_KEY).eq(body.dedup_key)
    )
    if existing is not None:
        existing.decision = SUPPRESSION_DECISION_DISMISSED
        existing.snoozed_until = None
    else:
        repo.add(DoraSuggestionSuppression(
            kind=body.kind,
            dedup_key=body.dedup_key,
            decision=SUPPRESSION_DECISION_DISMISSED,
            snoozed_until=None,
            created_at=datetime.now(timezone.utc),
        ))
    repo.save_changes()
    return no_content()


# ── POST /api/suggestions/snooze ────────────────────────────────────────

class SnoozeSuggestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(min_length=1, max_length=64)
    dedup_key: str = Field(min_length=1, max_length=255)
    # Hours rather than a wall-clock until so the SPA doesn't have to
    # think about timezones. Clamped to a week — long-term snoozes
    # should be a dismiss in practice.
    hours: int = Field(ge=1, le=24 * 7)


@SUGGESTIONS_ROUTER.route("/snooze", methods=["POST"])
@has_request_body(SnoozeSuggestionRequest)
def snooze_suggestion():
    body: SnoozeSuggestionRequest = get_request_body()
    repo = SqlAlchemyRepository()
    until = datetime.now(timezone.utc) + timedelta(hours=body.hours)
    existing = repo.get(DoraSuggestionSuppression).one(
        EntityField(DoraSuggestionSuppression, DoraSuggestionSuppression.Fields.KIND).eq(body.kind)
        & EntityField(DoraSuggestionSuppression, DoraSuggestionSuppression.Fields.DEDUP_KEY).eq(body.dedup_key)
    )
    if existing is not None:
        # Don't downgrade a dismiss to a snooze. A user who already said
        # "never" presumably doesn't want a snooze to revive the prompt.
        if existing.decision == SUPPRESSION_DECISION_DISMISSED:
            return no_content()
        existing.decision = SUPPRESSION_DECISION_SNOOZED
        existing.snoozed_until = until
    else:
        repo.add(DoraSuggestionSuppression(
            kind=body.kind,
            dedup_key=body.dedup_key,
            decision=SUPPRESSION_DECISION_SNOOZED,
            snoozed_until=until,
            created_at=datetime.now(timezone.utc),
        ))
    repo.save_changes()
    return no_content()


# ── DELETE /api/suggestions/suppression ─────────────────────────────────
# Undo a previous dismiss/snooze. Powers "actually, please remind me
# again" from Settings (or the chat) — not surfaced inline on the card.

class UnsuppressSuggestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(min_length=1, max_length=64)
    dedup_key: str = Field(min_length=1, max_length=255)


@SUGGESTIONS_ROUTER.route("/unsuppress", methods=["POST"])
@has_request_body(UnsuppressSuggestionRequest)
def remove_suppression():
    body: UnsuppressSuggestionRequest = get_request_body()
    repo = SqlAlchemyRepository()
    existing = repo.get(DoraSuggestionSuppression).one(
        EntityField(DoraSuggestionSuppression, DoraSuggestionSuppression.Fields.KIND).eq(body.kind)
        & EntityField(DoraSuggestionSuppression, DoraSuggestionSuppression.Fields.DEDUP_KEY).eq(body.dedup_key)
    )
    if existing is None:
        # Idempotent — no row, no error.
        return no_content()
    repo.remove(existing)
    repo.save_changes()
    return no_content()
