"""FU-317 Chunk 3 — reconcile queue + per-entry verb endpoints.

Two endpoints on `MEAL_PLAN_ROUTER`:

    GET  /api/meal-plans/reconcile-queue
    POST /api/meal-plans/reconcile/<entry_id>

The queue lists past-day `MealPlanEntry`s whose *latest*
`MealPlanReconcileReceipt` state is `unresolved_*`. Cursor-paged,
oldest-first, no client-side derivation. Every mutation goes through
this handler — the Chunk-1 sweep only wrote initial receipts; user
resolutions (Cooked / Cooked adjusted / Cooked later / Didn't cook)
are Chunk 3's job.

State model (proposal §3.2 + §7.1):

- **Initial state** — set by the daily sweep (`reconcile_consumed_meals`):
  `unresolved_auto` (auto-drain ON; consumed_at already stamped + pool
  already decremented) or `unresolved_manual` (auto-drain OFF; entry +
  pool untouched).
- **Resolution verbs** (this file):
  - `cooked`             → resolved_confirmed
  - `cooked_adjusted`    → resolved_adjusted (actual_servings != planned)
  - `cooked_later`       → resolved_confirmed (cooked_on stamped)
  - `not_cooked`         → resolved_not_cooked
  - `skip`               → resolved_deferred (session hint; small side
                          effect, keeps the entry in the queue on next
                          visit — no consumed_at / pool change). FU-594:
                          this neutrality is enforced — skip leaves the
                          sweep's drain + consumed_at untouched, unlike
                          not_cooked which reverses them.

**Idempotence.** A repeat call with the same verb + same fields returns
200 without adding a receipt. A different verb writes a new corrective
receipt AND applies whatever pool / consumed_at delta lands the entry
in the new target state (matches `MealPlanSwapLedger` — never mutate
past history; write forward).

**Pool math.** Uses `features/recipes/pool.py:bump_pool` (Chunk 2's
one authority). No inline arithmetic; the floor-at-zero rule lives in
one SQL CASE WHEN. A `cook_fresh` entry is pool-neutral under every
verb — it was cooked on its day and never touched the pool.

Rate-limited 60/min per authenticated user via the shared `subject`
bucket introduced by FU-458 (matches `/assistant/act`). The queue GET
is unlimited — reads don't mutate.
"""
from __future__ import annotations

import base64
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from dora_api.app import db
from dora_api.domain.entities.meal_plan_reconcile_receipt import (
    STATE_RESOLVED_ADJUSTED, STATE_RESOLVED_CONFIRMED, STATE_RESOLVED_DEFERRED,
    STATE_RESOLVED_NOT_COOKED, STATE_UNRESOLVED_AUTO, STATE_UNRESOLVED_MANUAL)
from dora_api.features.app_settings.clock import household_today
from dora_api.features.recipes.pool import bump_pool
from dora_api.features.routers import MEAL_PLAN_ROUTER
from dora_api.infrastructure.api_response import (bad_request, not_found, ok,
                                                  unauthorized)
from dora_api.infrastructure.auth_helpers import (rate_limit,
                                                  rate_limit_remaining_seconds)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.persistence.aware import as_utc
from dora_api.persistence.uuid_key import uuid_bind, uuid_key
from dora_api.infrastructure.session_user import current_user_id
from dora_api.infrastructure.api_response import too_many_requests

_LOGGER = logging.getLogger(__name__)

# ── Rate-limit config (proposal §11 / impl-plan Chunk 3) ────────────────

_RECONCILE_PER_MINUTE = 60
_RATE_SCOPE_RECONCILE = "meal_plans.reconcile"

# ── Verb vocabulary ─────────────────────────────────────────────────────

VERB_COOKED = "cooked"
VERB_COOKED_ADJUSTED = "cooked_adjusted"
VERB_COOKED_LATER = "cooked_later"
VERB_NOT_COOKED = "not_cooked"
VERB_SKIP = "skip"
_ALLOWED_VERBS = frozenset({
    VERB_COOKED, VERB_COOKED_ADJUSTED, VERB_COOKED_LATER,
    VERB_NOT_COOKED, VERB_SKIP,
})

# Verb → target receipt state.
_VERB_TO_STATE = {
    VERB_COOKED: STATE_RESOLVED_CONFIRMED,
    VERB_COOKED_ADJUSTED: STATE_RESOLVED_ADJUSTED,
    VERB_COOKED_LATER: STATE_RESOLVED_CONFIRMED,
    VERB_NOT_COOKED: STATE_RESOLVED_NOT_COOKED,
    VERB_SKIP: STATE_RESOLVED_DEFERRED,
}

# Which verbs count as "cooked" for pool + consumed_at purposes.
_COOKED_VERBS = frozenset({VERB_COOKED, VERB_COOKED_ADJUSTED, VERB_COOKED_LATER})

# Which verbs should keep the entry in the queue on the next visit.
_DEFERRING_VERBS = frozenset({VERB_SKIP})

# States that count as "unresolved" for the queue filter.
_UNRESOLVED_STATES = (STATE_UNRESOLVED_AUTO, STATE_UNRESOLVED_MANUAL,
                      STATE_RESOLVED_DEFERRED)


def _auto_drain_enabled() -> bool:
    """Read the install-wide `auto_drain_past_meals` posture. In auto mode Dora
    silently drains past-day meals, so an `unresolved_auto` receipt is *not*
    pending work — it's just a line in the log. Defaults True (matches the sweep
    + the AppSetting entity). Wrapped so a read hiccup can't 500 a queue GET."""
    from dora_api.features.app_settings.access import get_or_create_app_setting
    try:
        setting = get_or_create_app_setting(SqlAlchemyRepository())
        return bool(getattr(setting, "auto_drain_past_meals", True))
    except Exception:
        return True


def _pending_states(auto_drain: bool) -> tuple[str, ...]:
    """The receipt states that count as "needs your attention" — the one
    authority (R-003) behind the runner queue, the dashboard chip count, and the
    overdue nudge. In **auto** mode `unresolved_auto` drops out: Dora already
    drained those, so they surface only in the read-only log, and dropping them
    empties all three pending surfaces — auto mode stops nagging (owner call).
    **Manual** mode keeps the full set (there the user must confirm each)."""
    if auto_drain:
        return (STATE_UNRESOLVED_MANUAL, STATE_RESOLVED_DEFERRED)
    return _UNRESOLVED_STATES


# ── Session helpers ─────────────────────────────────────────────────────


def _rate_limit_subject() -> Optional[str]:
    uid = current_user_id()
    return str(uid) if uid is not None else None


# ── Queue endpoint ──────────────────────────────────────────────────────
#
# The JSON shape returned is:
#   {
#     "entries": [
#       {
#         "entry_id": "<uuid>",
#         "scheduled_for": "YYYY-MM-DD",
#         "slot": "Dinner",
#         "planned_servings": 2,
#         "recipe": { "id": "<uuid>", "name": "..." },
#         "receipt": {
#           "state": "unresolved_auto" | "unresolved_manual" | "resolved_deferred",
#           "original_servings": 2,
#           "actual_servings": null,
#           "cooked_on": null,
#           "created_at": "<iso>"
#         }
#       },
#       ...
#     ],
#     "next_cursor": null | "<opaque>",
#     "total": <int>          # exact count across all pages
#   }
#


_DEFAULT_LIMIT = 30
_MAX_LIMIT = 100

# ── Overdue-signal thresholds (proposal §11 D1) ─────────────────────────
# Both the `meal_reconcile_overdue` alert kind AND the
# `reconcile_meals_pending` suggestion kind (Chunk 4) fire off this same
# signal — one authority for "the reconcile queue has been unattended
# long enough to nudge". Threshold locked by the impl-plan.
RECONCILE_OVERDUE_MIN_COUNT = 3
RECONCILE_OVERDUE_MIN_DAYS_BACK = 4


@dataclass(frozen=True, slots=True)
class ReconcileOverdueSignal:
    fires: bool
    unresolved_count: int
    oldest_days_back: int  # 0 if queue empty


def reconcile_overdue_signal(today: date) -> ReconcileOverdueSignal:
    """One authority for the overdue-nudge decision. Reads current queue
    state (unresolved-latest-receipt past-day entries) and returns
    (fires, count, oldest_days_back). Fires iff
    `unresolved_count ≥ RECONCILE_OVERDUE_MIN_COUNT` AND
    `oldest_days_back ≥ RECONCILE_OVERDUE_MIN_DAYS_BACK`.

    R-003: alert + suggestion both call this; they never re-derive the
    threshold. Change the constants above and both surfaces move
    together.

    Mode-aware (owner 2026-08-13): in auto-drain mode `unresolved_auto` isn't
    pending (Dora handled it), so it's excluded from the count here too — which
    is what stops the overdue alert + suggestion firing in auto mode.
    """
    row = db.session.execute(
        text(
            'SELECT COUNT(*) AS n, MIN(mpe.scheduled_for) AS oldest '
            + _ENTRY_RECEIPTS
            + _latest_receipt_where(_pending_states(_auto_drain_enabled()))
        ),
        {"today": today},
    ).first()
    if row is None:
        return ReconcileOverdueSignal(fires=False, unresolved_count=0, oldest_days_back=0)
    count = int(row[0] or 0)
    oldest = row[1]
    if count == 0 or oldest is None:
        return ReconcileOverdueSignal(fires=False, unresolved_count=0, oldest_days_back=0)
    if isinstance(oldest, str):
        oldest = date.fromisoformat(oldest)
    days_back = (today - oldest).days
    fires = (
        count >= RECONCILE_OVERDUE_MIN_COUNT
        and days_back >= RECONCILE_OVERDUE_MIN_DAYS_BACK
    )
    return ReconcileOverdueSignal(
        fires=fires, unresolved_count=count, oldest_days_back=days_back,
    )


def _encode_cursor(scheduled_for, entry_id) -> str:
    """Keyset cursor on the page order `(scheduled_for, id)`: the last row's
    day AND id, so a day that straddles a page boundary resumes at the next
    entry of that day instead of skipping the rest of it.

    R-005 portability: the raw-SQL row hands `scheduled_for` back as a
    `date` on Postgres but a `str` ("YYYY-MM-DD") on SQLite. Without this
    coercion `.isoformat()` raised AttributeError on SQLite → 500 the
    moment the queue paginated (>limit unresolved entries). Same divergence
    `uuid_key` handles for UUIDs."""
    if isinstance(scheduled_for, str):
        scheduled_for = date.fromisoformat(scheduled_for[:10])
    raw = f"{scheduled_for.isoformat()}|{uuid_key(entry_id)}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> Optional[tuple[date, Optional[UUID]]]:
    """`(day, entry id)`; the id is None for a date-only cursor minted before
    the keyset change, which then pages by day alone as it used to."""
    try:
        day_text, _, id_text = base64.urlsafe_b64decode(cursor.encode()).decode().partition("|")
        return date.fromisoformat(day_text), (UUID(id_text) if id_text else None)
    except (ValueError, TypeError):
        return None


# ── Latest-receipt queries ──────────────────────────────────────────────
# Every reconcile read is "past-day entries, judged by their latest receipt".
# The latest-per-entry pick is a `NOT EXISTS` subquery rather than a window
# function, which SQLite before 3.25 lacks (Postgres accepts the same shape).
# FU-529: "newer" uses the same (created_at, id) order as `_latest_receipt`,
# so the pick is deterministic when two receipts share a created_at.

_ENTRY_RECEIPTS = (
    'FROM "MealPlanEntry" mpe '
    'JOIN "MealPlanReconcileReceipt" r ON r.meal_plan_entry_id = mpe.id '
)

_IS_LATEST_RECEIPT = (
    'NOT EXISTS ('
    '    SELECT 1 FROM "MealPlanReconcileReceipt" r2 '
    '    WHERE r2.meal_plan_entry_id = mpe.id '
    '      AND (r2.created_at > r.created_at '
    '           OR (r2.created_at = r.created_at AND r2.id > r.id))'
    ') '
)

_ROW_COLUMNS = (
    'SELECT mpe.id AS entry_id, mpe.scheduled_for, mpe.slot, mpe.servings, '
    '       mpe.recipe_id, rec.name AS recipe_name, '
    '       r.state, r.original_servings, r.actual_servings, r.cooked_on, '
    '       r.created_at '
)


def _latest_receipt_where(pending_states: tuple[str, ...] | None) -> str:
    """Past-day entries by their latest receipt; `pending_states` narrows to the
    queue (mode-aware, see `_pending_states`), None keeps every outcome (the log).
    The states are module constants, never request input."""
    clauses = [_IS_LATEST_RECEIPT, 'mpe.scheduled_for < :today ']
    if pending_states is not None:
        states_in = ", ".join(f"'{state}'" for state in pending_states)
        clauses.insert(0, f'r.state IN ({states_in}) ')
    return 'WHERE ' + ' AND '.join(clauses)


def _receipt_rows(
    today: date,
    cursor: Optional[str],
    limit: int,
    *,
    pending_states: tuple[str, ...] | None,
    newest_first: bool,
) -> tuple[list[dict], Optional[str]]:
    """Cursor-paged rows, one per entry, keyset on `(scheduled_for, id)`. The
    queue reads oldest-first and resumes after the last page's last row; the
    read-only log (owner 2026-08-13) reads newest-first and resumes before it."""
    params: dict = {"today": today, "limit": limit + 1}
    cursor_clause = ""
    decoded = _decode_cursor(cursor) if cursor else None
    if decoded is not None:
        cursor_date, cursor_id = decoded
        params["cursor_date"] = cursor_date
        after = "<" if newest_first else ">"
        if cursor_id is None:
            cursor_clause = f"AND mpe.scheduled_for {after} :cursor_date "
        else:
            params["cursor_id"] = _bind(cursor_id)
            cursor_clause = (
                f"AND (mpe.scheduled_for {after} :cursor_date "
                f"OR (mpe.scheduled_for = :cursor_date AND mpe.id {after} :cursor_id)) "
            )
    direction = "DESC" if newest_first else "ASC"
    query = text(
        _ROW_COLUMNS
        + _ENTRY_RECEIPTS
        + 'JOIN "Recipe" rec ON rec.id = mpe.recipe_id '
        + _latest_receipt_where(pending_states)
        + cursor_clause
        + f'ORDER BY mpe.scheduled_for {direction}, mpe.id {direction} '
        + 'LIMIT :limit'
    )
    rows_list = list(db.session.execute(query, params).mappings().all())
    next_cursor: Optional[str] = None
    if len(rows_list) > limit:
        last = rows_list[limit - 1]
        next_cursor = _encode_cursor(last["scheduled_for"], last["entry_id"])
        rows_list = rows_list[:limit]
    return rows_list, next_cursor


def _receipt_count(today: date, pending_states: tuple[str, ...] | None) -> int:
    """Exact total for the same filter: the dashboard chip, the meal-plans header
    nudge and the log's total. In auto mode the pending count drops to 0 once the
    auto-drained entries are excluded, which hides the chip with no client change."""
    query = text('SELECT COUNT(*) ' + _ENTRY_RECEIPTS + _latest_receipt_where(pending_states))
    return int(db.session.execute(query, {"today": today}).scalar_one())


def _row_to_dict(row) -> dict:
    scheduled = row["scheduled_for"]
    cooked_on = row["cooked_on"]
    created_at = row["created_at"]
    return {
        "entry_id": uuid_key(row["entry_id"]),
        "scheduled_for": scheduled.isoformat() if isinstance(scheduled, date) else str(scheduled),
        "slot": row["slot"],
        "planned_servings": int(row["servings"] or 0),
        "recipe": {
            "id": uuid_key(row["recipe_id"]),
            "name": row["recipe_name"],
        },
        "receipt": {
            "state": row["state"],
            "original_servings": int(row["original_servings"]),
            "actual_servings": (int(row["actual_servings"]) if row["actual_servings"] is not None else None),
            "cooked_on": (cooked_on.isoformat() if isinstance(cooked_on, date) else (str(cooked_on) if cooked_on else None)),
            "created_at": (created_at.isoformat() if isinstance(created_at, datetime) else str(created_at)),
        },
    }


@MEAL_PLAN_ROUTER.route("/reconcile-queue", methods=["GET"])
def get_reconcile_queue():
    from flask import request as _flask_request
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()

    try:
        limit = int(_flask_request.args.get("limit", _DEFAULT_LIMIT))
    except ValueError:
        return bad_request("`limit` must be an integer.")
    limit = max(1, min(limit, _MAX_LIMIT))
    cursor = _flask_request.args.get("cursor")

    today = household_today(SqlAlchemyRepository())

    # `include_resolved=true` → the read-only reconcile **log** (every past-day
    # meal with a receipt, whatever its outcome, newest-first). This is the view
    # auto mode shows instead of the confirm-each runner (owner 2026-08-13;
    # finishes the deferred FU-317 Chunk 5 history seam). Without it → the
    # pending **queue** (mode-aware: `unresolved_auto` isn't pending in auto mode).
    if _flask_request.args.get("include_resolved") == "true":
        rows, next_cursor = _receipt_rows(today, cursor, limit, pending_states=None, newest_first=True)
        total = _receipt_count(today, None)
    else:
        pending_states = _pending_states(_auto_drain_enabled())
        rows, next_cursor = _receipt_rows(
            today, cursor, limit, pending_states=pending_states, newest_first=False,
        )
        total = _receipt_count(today, pending_states)

    return ok({
        "entries": [_row_to_dict(r) for r in rows],
        "next_cursor": next_cursor,
        "total": total,
    })


# ── Verb endpoint ───────────────────────────────────────────────────────

class ReconcileVerbRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verb: str
    # Required for `cooked_adjusted`; ignored otherwise. Bounded to catch
    # fat-finger input (same pattern as `AdjustRecipeMealsRequest.delta`).
    actual_servings: int | None = Field(default=None, ge=0, le=999)
    # Required for `cooked_later`; ignored otherwise. ISO date on the wire.
    cooked_on: date | None = None
    # Optional user note (persisted on the receipt for the history view).
    note: str | None = Field(default=None, max_length=500)


def _bind(value) -> bytes | str:
    return uuid_bind(value, db.engine.dialect.name)


def _latest_receipt(entry_id) -> Optional[dict]:
    row = db.session.execute(
        text(
            'SELECT state, original_servings, actual_servings, cooked_on, created_at '
            'FROM "MealPlanReconcileReceipt" '
            'WHERE meal_plan_entry_id = :eid '
            # FU-529: `id` is the deterministic tie-break so "latest" is
            # unambiguous when two receipts share a created_at (portable on
            # SQLite BINARY(16) + Postgres uuid). The monotonic clamp in
            # `submit_verb` keeps created_at itself causally ordered.
            'ORDER BY created_at DESC, id DESC LIMIT 1'
        ),
        {"eid": _bind(entry_id)},
    ).mappings().first()
    return dict(row) if row else None


def _load_entry(entry_id: UUID) -> Optional[dict]:
    """Return the entry + its recipe id in one round-trip."""
    row = db.session.execute(
        text(
            'SELECT id, recipe_id, servings, consumed_at, cook_fresh '
            'FROM "MealPlanEntry" WHERE id = :eid'
        ),
        {"eid": _bind(entry_id)},
    ).mappings().first()
    return dict(row) if row else None


def _effective_drained(latest: Optional[dict], entry_planned_servings: int,
                       entry_consumed_at) -> int:
    """How many servings the recipe pool currently reflects as drained
    for this entry. Determined by the latest receipt's state (if any)
    or by `consumed_at` for entries that predate any receipt (edge case
    — the sweep should have written one)."""
    if latest is None:
        return entry_planned_servings if entry_consumed_at is not None else 0
    state = latest["state"]
    if state in (STATE_RESOLVED_CONFIRMED,):
        return entry_planned_servings
    if state == STATE_RESOLVED_ADJUSTED:
        return int(latest["actual_servings"] or 0)
    if state == STATE_RESOLVED_NOT_COOKED:
        return 0
    if state == STATE_RESOLVED_DEFERRED:
        # FU-594 — "Skip for now" is neutral: it never changes the pool, so a
        # deferred entry still carries whatever drain the sweep left it with.
        # `consumed_at` tracks that (auto-drain stamped it, manual didn't), so
        # the *next* verb after a skip recomputes its delta from the true drain
        # instead of treating a deferred entry as un-drained (which would make
        # a following `cooked` drain a second time).
        return entry_planned_servings if entry_consumed_at is not None else 0
    if state == STATE_UNRESOLVED_AUTO:
        # Sweep drained on auto-drain-ON.
        return entry_planned_servings
    # STATE_UNRESOLVED_MANUAL — sweep left everything untouched.
    return 0


def _target_drained(verb: str, entry_planned_servings: int,
                    actual_servings: Optional[int]) -> int:
    if verb == VERB_COOKED or verb == VERB_COOKED_LATER:
        return entry_planned_servings
    if verb == VERB_COOKED_ADJUSTED:
        return int(actual_servings or 0)
    # not_cooked → no drain. (skip never reaches here — the caller treats it as
    # pool-neutral, FU-594.)
    return 0


def _is_idempotent(latest: Optional[dict], target_state: str,
                   actual_servings: Optional[int],
                   cooked_on: Optional[date]) -> bool:
    """A verb is a no-op iff the latest receipt already reflects the
    same target state + the same key fields (actual_servings for
    adjusted, cooked_on for later)."""
    if latest is None or latest["state"] != target_state:
        return False
    if target_state == STATE_RESOLVED_ADJUSTED:
        return int(latest["actual_servings"] or 0) == int(actual_servings or 0)
    # For confirmed/deferred/not_cooked, cooked_on is the only extra field
    # that can differ. `cooked_later` writes STATE_RESOLVED_CONFIRMED with
    # a cooked_on; `cooked` writes it without. Both idempotent iff cooked_on
    # matches.
    left = latest["cooked_on"]
    left_iso = left.isoformat() if isinstance(left, date) else (str(left) if left else None)
    right_iso = cooked_on.isoformat() if cooked_on else None
    return left_iso == right_iso


@MEAL_PLAN_ROUTER.route("/reconcile/<uuid:entry_id>", methods=["POST"])
@has_request_body(ReconcileVerbRequest)
def submit_verb(entry_id: UUID):
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()

    subject = _rate_limit_subject()
    if not rate_limit(_RATE_SCOPE_RECONCILE, _RECONCILE_PER_MINUTE, subject=subject):
        return too_many_requests(rate_limit_remaining_seconds(
            _RATE_SCOPE_RECONCILE, _RECONCILE_PER_MINUTE, subject=subject,
        ))

    req: ReconcileVerbRequest = get_request_body()
    verb = req.verb
    if verb not in _ALLOWED_VERBS:
        return bad_request(
            f"Unknown verb '{verb}'. Allowed: {sorted(_ALLOWED_VERBS)}.",
        )
    if verb == VERB_COOKED_ADJUSTED and req.actual_servings is None:
        return bad_request("`actual_servings` is required for `cooked_adjusted`.")
    if verb == VERB_COOKED_LATER and req.cooked_on is None:
        return bad_request("`cooked_on` is required for `cooked_later`.")

    now = datetime.now(UTC)

    # Everything below runs on the ORM session so `db.session.commit()` at
    # the end commits pool math + receipt insert + consumed_at flip
    # atomically.
    entry = _load_entry(entry_id)
    if entry is None:
        return not_found("MealPlanEntry", entry_id)

    latest = _latest_receipt(entry["id"])
    target_state = _VERB_TO_STATE[verb]

    # Idempotence — same-verb replay is a 200 no-op.
    if _is_idempotent(latest, target_state, req.actual_servings, req.cooked_on):
        current_pool = _read_pool(entry["recipe_id"])
        return ok(_verb_payload(
            entry_id=entry["id"],
            receipt=latest,
            new_pool=current_pool,
            idempotent=True,
        ))

    # FU-529 — monotonic guard: a correction must never sort *older* than the
    # receipt it supersedes, even if the wall clock stepped backwards between
    # the auto-sweep receipt and this action (the observed idempotence flake,
    # suspected Windows time-sync). Clamp created_at to just after the latest
    # existing receipt so "latest by (created_at, id)" reliably means "most
    # recently decided" and a same-verb replay stays a no-op.
    # NOTE: `_latest_receipt` runs raw SQL, so created_at comes back as a str on
    # SQLite and a datetime on Postgres — handle both.
    prev_created = latest.get("created_at") if latest else None
    if isinstance(prev_created, str):
        try:
            prev_created = datetime.fromisoformat(prev_created)
        except ValueError:
            prev_created = None
    if isinstance(prev_created, datetime):
        prev_created = as_utc(prev_created)
        if prev_created >= now:
            now = prev_created + timedelta(microseconds=1)

    # Compute pool delta.
    # FU-594 — "Skip for now" is neutral: it re-queues the entry (writes a
    # resolved_deferred receipt below) without changing the pool or consumed_at,
    # leaving it exactly as the sweep left it. Its target drain therefore equals
    # its current drain → delta 0. Every other verb recomputes the target.
    planned = int(entry["servings"] or 0)
    current_drained = _effective_drained(latest, planned, entry["consumed_at"])
    if verb in _DEFERRING_VERBS:
        target_drained = current_drained
    else:
        target_drained = _target_drained(verb, planned, req.actual_servings)
    # Owner 2026-09-04 — a meal marked cooked-fresh never entered the pool and
    # the sweep never drained it (`reconcile_consumed_meals`), so every verb is
    # pool-neutral on it: nothing to reverse for "didn't cook", nothing to take
    # for "cooked". Zeroing both sides here rather than teaching each helper the
    # flag keeps the drain rules one story — this is the exception, stated once.
    if bool(entry["cook_fresh"]):
        current_drained = target_drained = 0
    pool_delta = current_drained - target_drained  # positive = pool goes UP

    if pool_delta != 0:
        new_pool = bump_pool(entry["recipe_id"], pool_delta)
    else:
        new_pool = _read_pool(entry["recipe_id"])

    # Sync consumed_at: cooked verbs stamp now (if not already); not_cooked
    # clears it. Skip is intentionally absent — it leaves consumed_at exactly as
    # the sweep set it (FU-594, neutral).
    if verb in _COOKED_VERBS and entry["consumed_at"] is None:
        db.session.execute(
            text('UPDATE "MealPlanEntry" SET consumed_at = :now WHERE id = :eid'),
            {"now": now, "eid": _bind(entry["id"])},
        )
    elif verb == VERB_NOT_COOKED and entry["consumed_at"] is not None:
        db.session.execute(
            text('UPDATE "MealPlanEntry" SET consumed_at = NULL WHERE id = :eid'),
            {"eid": _bind(entry["id"])},
        )

    # Write the corrective receipt (append-only — never mutates the past).
    new_receipt_id = uuid.uuid4()
    actual_for_row = (
        req.actual_servings if verb == VERB_COOKED_ADJUSTED else None
    )
    cooked_on_for_row = req.cooked_on if verb == VERB_COOKED_LATER else None
    db.session.execute(
        text(
            'INSERT INTO "MealPlanReconcileReceipt" '
            '(id, meal_plan_entry_id, state, original_servings, actual_servings, '
            ' cooked_on, resolved_by_user_id, resolved_at, note, created_at) '
            'VALUES (:id, :eid, :state, :orig, :actual, :cooked_on, :uid, :now, :note, :now)'
        ),
        {
            "id": _bind(new_receipt_id),
            "eid": _bind(entry["id"]),
            "state": target_state,
            "orig": int(entry["servings"] or 0),
            "actual": actual_for_row,
            "cooked_on": cooked_on_for_row,
            "uid": _bind(user_id),
            "now": now,
            "note": req.note,
        },
    )

    db.session.commit()

    new_receipt = {
        "state": target_state,
        "original_servings": int(entry["servings"] or 0),
        "actual_servings": actual_for_row,
        "cooked_on": cooked_on_for_row,
        "created_at": now,
    }
    _LOGGER.info(
        "Reconciled entry %s → %s (pool delta %+d, new pool %d)",
        entry_id, target_state, pool_delta, new_pool,
    )
    return ok(_verb_payload(
        entry_id=entry["id"],
        receipt=new_receipt,
        new_pool=new_pool,
        idempotent=False,
    ))


def _read_pool(recipe_id) -> int:
    row = db.session.execute(
        text('SELECT available_meals FROM "Recipe" WHERE id = :rid'),
        {"rid": _bind(recipe_id)},
    ).first()
    return int(row[0]) if row and row[0] is not None else 0


def _verb_payload(*, entry_id, receipt, new_pool: int, idempotent: bool) -> dict:
    r_state = receipt["state"]
    r_orig = int(receipt["original_servings"])
    r_actual = receipt.get("actual_servings")
    r_cooked_on = receipt.get("cooked_on")
    r_created = receipt.get("created_at")
    return {
        "entry_id": uuid_key(entry_id),
        "new_pool": new_pool,
        "idempotent": idempotent,
        "receipt": {
            "state": r_state,
            "original_servings": r_orig,
            "actual_servings": (int(r_actual) if r_actual is not None else None),
            "cooked_on": (r_cooked_on.isoformat() if isinstance(r_cooked_on, date) else r_cooked_on),
            "created_at": (r_created.isoformat() if isinstance(r_created, datetime) else r_created),
        },
    }
