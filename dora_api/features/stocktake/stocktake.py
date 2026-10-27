"""X1 — Stocktake / Focused Review backend.

  GET  /api/stocktake/queue?limit=50          — items needing a check
  POST /api/stock-items/<id>/check            — bump last_checked_at only
  POST /api/stock-items/<id>/snooze           — Push 3 days
  POST /api/stocktake/bulk-check              — body {ids}

(`POST /shopping-lists/<id>/review/complete` was deleted in finalisation
05-R7: the shopping-list review mode it served was retired in UX-v2, the SPA
had no caller, and it wrote `stock_level_id` with a raw UPDATE — no
`StockLevelChange`, no `ConsumptionEvent`, no auto-add — exactly the bypass
`bulk_operations.py` refuses.)

Round-19 (2026-07-04) reboots the queue engine for the new stocktake
design (`docs/04_proposals/PROPOSAL_STOCKTAKE_MODE.md`). Two shifts:

1.  **Engagement gate — one honest question.** An item enters the queue
    only when it shows a *current* sign the user manages it. The old
    flag-based signals (`is_essential`, `auto_add_when_low`) are dropped
    — a flag never forces a not-actually-kept item into the queue —
    and the two history signals gain a **60-day window** so an item
    touched a year ago no longer nags forever. Signals:
      • In stock right now (`stock_level.sequence < OUT`).
      • Ever opened (`opened_on` non-null).
      • Level adjusted in the last 60 days.
      • On a shopping list in the last 60 days (active list, or a
        closed list with `completed_at` inside the window).

2.  **Cadence bands + Auto self-tuning.** Per-item overdue is measured
    against a *resolved band* (Weekly/Fortnightly/Monthly, see
    `cadence.py`). Baseline = the global
    `AppSetting.stocktake_default_cadence_band`; Auto (on by default)
    overrides from movement history; Low/Out in the last 14 days bumps
    one band faster; Essential (`is_essential`) bumps one more.
    Change-level *implicitly* checks the item (already done in
    `update_stock_item.py`), so the grace-period baseline for a
    never-checked item is `COALESCE(last_checked_at,
    stock_level_last_updated)` — the "when did the user last touch
    this" timestamp. No 9999 sentinel.

    Push (snooze) filters out items whose `snoozed_until > now`;
    Mute is unchanged (`stocktake_alerts_are_enabled=False` still
    excludes).

Chunk 5 of `IMPL_PLAN_STOCK_SIGNAL_CONSOLIDATION.md` (**D-1**) split the two
halves of "what should I check?": **cadence decides membership, belief decides
order.** Everything above still governs who is in the queue; the *ordering*
moved out to `queue_ranking.py`. The queue is no longer "most-overdue first" —
it's least-certain first, with most-overdue as the fallback for items belief
knows nothing about and for users who have inference switched off.
"""
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import List
from uuid import UUID

from flask import request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from dora_api.persistence.aware import as_utc
from dora_api.app import db
from dora_api.domain.entities.shopping_list import (
    SHOPPING_LIST_STATUS_DONE,
)
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.stock_status import LOW_STOCK_SEQUENCE, OUT_OF_STOCK_SEQUENCE
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.features.routers import STOCK_ITEM_ROUTER, STOCKTAKE_ROUTER
from dora_api.features.stock_items.inference_overlay import (SURFACE_STOCK,
                                                             surface_enabled)
from dora_api.features.stock_items.pantry_belief import (PantryBelief,
                                                         gather_beliefs_for_items)
from dora_api.features.stocktake.queue_ranking import QueueRank, rank_queue
from dora_api.features.stocktake.cadence import (AUTO_HISTORY_WINDOW_DAYS,
                                                 LOW_OUT_BUMP_WINDOW_DAYS,
                                                 CadenceBand, ItemHistory,
                                                 parse_band, resolve_band)
from dora_api.infrastructure.api_response import bad_request, not_found, ok
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.session_user import current_user

_LOGGER = logging.getLogger(__name__)


# ── Windows ────────────────────────────────────────────────────────────
# History-signal windows for the engagement gate + Auto's Low/Out bump.
# All in one place so the queue, the tests, and any future assistant
# tool resolve to the same numbers (R-003).
# The two cadence windows are *imported*, not re-declared — `cadence.py` owns
# them because it owns the decision they feed (D1/D2 in
# `IMPL_PLAN_STOCK_SIGNAL_CONSOLIDATION.md`; the old local copy of the 90-day
# one even carried a comment admitting it was a mirror).
# Public because Chunk 6's Sweep phase dates each drop-out as
# "last activity + this window" — deriving the departure from the same number
# the gate expires on is what stops the two disagreeing (`sweep.py`).
ENGAGEMENT_WINDOW_DAYS = 60

# Push (snooze) window — fixed 3 days per §5 (open-decision resolved).
_SNOOZE_DAYS = 3


# ── Queue DTO ──────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class StocktakeQueueItemDto:
    stock_item_id: UUID
    name: str
    stock_level_name: str | None
    stock_location_name: str | None
    # Resolved band the runner shows next to the item ("checked every
    # week / fortnight / month"). Server-owned (R-003) — the SPA never
    # re-derives a band.
    cadence_band: str
    # Effective cadence in days (matches `cadence_band` — sent for
    # convenience so the SPA doesn't need to map the string itself).
    cadence_days: int
    last_checked_at: str | None
    overdue_days: int
    # Owner call 2026-08-20: the Stocktake button's glow was removed as
    # noise (D-14) and reinstated **gated on essentials** — "glow only if
    # something I flagged as mattering is due". The queue already resolves
    # `is_essential` when it picks a cadence band, so the flag rides the DTO
    # rather than the client fetching stock items to look it up (R-003).
    is_essential: bool
    # ── Chunk 5 / D-1 — why this item is where it is in the list ──────
    # `check_rank` is 'uncertain' | 'overdue' | 'confident' (see
    # `queue_ranking.py`). The runner shows the belief's own words when the
    # rank is belief-derived, so the order is explicable rather than a
    # mystery reshuffle — D-1 forbids a toggle, which makes explaining it in
    # place the only honest option left.
    # All four are `None`/'overdue' when the user has stock inference off.
    check_rank: str
    belief_band: str | None
    belief_confidence: str | None
    belief_reason: str | None


# ── Overdue baseline ───────────────────────────────────────────────────

def _overdue_baseline(item: StockItem) -> datetime | None:
    """The timestamp we measure overdue from.

    `COALESCE(last_checked_at, stock_level_last_updated)` — "when did
    the user last touch this?" Change-level bumps `last_checked_at`
    (see `update_stock_item.py`), so any item the user has ever
    touched has a `last_checked_at`; only a truly never-touched item
    falls back to `stock_level_last_updated` (which equals its
    creation moment, since a StockItem is always created with a
    level).

    Replaces the old 9999-sentinel behaviour: brand-new items now
    have a natural grace period equal to one cadence band, not "top
    of the queue on turn zero".
    """
    if item.last_checked_at is not None:
        return item.last_checked_at
    return item.stock_level_last_updated


def _compute_overdue_days(
    item: StockItem, band_days: int, now: datetime,
) -> int:
    """Days past the resolved band since the overdue baseline. 0 if
    the item is not yet due; `_overdue_baseline` returning None (a
    genuinely-orphan row with no level) also reads as 0 — the item
    just doesn't surface, which is the safe fallback."""
    baseline = _overdue_baseline(item)
    if baseline is None:
        return 0
    elapsed = (now.date() - baseline.date()).days
    return max(0, elapsed - band_days)


# ── Engagement gate ────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class _EngagementSignals:
    """Bulk pre-computed signals for the engagement gate + Auto tuner.
    Assembling per-item would explode into N+M queries on a big
    pantry."""
    items_with_recent_level_change: set[UUID]
    items_on_recent_list: set[UUID]
    # Per-item trailing-90d list of change timestamps for the Auto
    # self-tuner (`cadence.py::auto_band_from_history`).
    change_timestamps_by_item: dict[UUID, list[datetime]]
    # Per-item flag: any StockLevelChange in the last
    # LOW_OUT_BUMP_WINDOW_DAYS whose target level's sequence is ≥
    # LOW_STOCK. Bumps one band faster.
    items_hit_low_or_out_recently: set[UUID]


def _gather_engagement_signals(
    item_ids: list[UUID],
    now: datetime,
) -> _EngagementSignals:
    empty = _EngagementSignals(set(), set(), {}, set())
    if not item_ids:
        return empty

    # R-005 carve-out: event aggregates across four tables the repository
    # port can't join.
    slc_table = db.metadata.tables["StockLevelChange"]
    sl_table = db.metadata.tables["StockLevel"]
    line_table = db.metadata.tables["ShoppingListLine"]
    list_table = db.metadata.tables["ShoppingList"]

    engagement_cutoff = now - timedelta(days=ENGAGEMENT_WINDOW_DAYS)
    auto_history_cutoff = now - timedelta(days=AUTO_HISTORY_WINDOW_DAYS)
    low_out_cutoff = now - timedelta(days=LOW_OUT_BUMP_WINDOW_DAYS)

    # Level-change rows for the trailing Auto-history window (which is
    # a superset of the engagement window, so one query covers both).
    # Join levels to know each change's sequence for the Low/Out bump.
    change_rows = db.session.execute(
        select(
            slc_table.c.stock_item_id,
            slc_table.c.changed_at,
            sl_table.c.sequence,
        )
        .select_from(
            slc_table.outerjoin(
                sl_table, slc_table.c.stock_level_id == sl_table.c.id,
            )
        )
        .where(
            slc_table.c.stock_item_id.in_(item_ids),
            slc_table.c.changed_at >= auto_history_cutoff,
        )
    ).all()

    change_timestamps_by_item: dict[UUID, list[datetime]] = {}
    items_with_recent_level_change: set[UUID] = set()
    items_hit_low_or_out_recently: set[UUID] = set()
    for stock_item_id, changed_at, seq in change_rows:
        # SQLite's `DateTime(timezone=True)` round-trips as naive; every
        # write here uses `datetime.now(UTC)`, so re-attaching UTC is the
        # honest way to compare against the tz-aware cutoffs.
        changed_at = as_utc(changed_at)
        change_timestamps_by_item.setdefault(stock_item_id, []).append(changed_at)
        if changed_at >= engagement_cutoff:
            items_with_recent_level_change.add(stock_item_id)
        if (
            seq is not None
            and seq >= LOW_STOCK_SEQUENCE
            and changed_at >= low_out_cutoff
        ):
            items_hit_low_or_out_recently.add(stock_item_id)

    # Shopping-list membership within the engagement window. Active
    # lists (status ≠ 'done') always qualify; closed lists count if
    # their completed_at is within the window. This is what makes
    # "on a list once 5 months ago" stop nagging.
    list_rows = db.session.execute(
        select(line_table.c.stock_item_id)
        .select_from(
            line_table.join(
                list_table,
                line_table.c.shopping_list_id == list_table.c.id,
            )
        )
        .where(
            line_table.c.stock_item_id.in_(item_ids),
            (
                (list_table.c.status != SHOPPING_LIST_STATUS_DONE)
                | (list_table.c.completed_at >= engagement_cutoff)
            ),
        )
        .distinct()
    ).all()
    items_on_recent_list = {row[0] for row in list_rows}

    return _EngagementSignals(
        items_with_recent_level_change=items_with_recent_level_change,
        items_on_recent_list=items_on_recent_list,
        change_timestamps_by_item=change_timestamps_by_item,
        items_hit_low_or_out_recently=items_hit_low_or_out_recently,
    )


def _is_engaged(item: StockItem, signals: _EngagementSignals) -> bool:
    """The single question: *do you actually keep this item?*

    Any one of four in-play signs is enough. Flag columns
    (`is_essential` / `auto_add_when_low`) are **not** signals here —
    they cover how an in-play item is treated, not whether the item
    is in play at all. See §2 of the brief.
    """
    if (
        item.stock_level is not None
        and item.stock_level.sequence < OUT_OF_STOCK_SEQUENCE
    ):
        return True
    if item.opened_on is not None:
        return True
    if item.id in signals.items_with_recent_level_change:
        return True
    if item.id in signals.items_on_recent_list:
        return True
    return False


def resolve_unengaged_items(
    items: list[StockItem],
    now: datetime | None = None,
) -> list[StockItem]:
    """Items currently failing the engagement gate — the Sweep phase's pool.

    The mirror image of `resolve_overdue_map`, and deliberately built on the
    same `_is_engaged` call rather than a second set of conditions: "out of
    rotation" has to mean exactly "not in rotation", or the Sweep would announce
    departures the queue doesn't believe in (Chunk 6 / D-4).

    **Muted items are excluded.** Mute already says "don't nag me about
    stocktake for this one", so telling its owner that Dora has stopped
    tracking it is both redundant and slightly insulting — they said so first.
    """
    if not items:
        return []
    now_ = now or datetime.now(UTC)
    signals = _gather_engagement_signals([item.id for item in items], now_)
    return [
        item for item in items
        if item.stocktake_alerts_are_enabled and not _is_engaged(item, signals)
    ]


# ── Shared overdue resolver ────────────────────────────────────────────
# The single authority for "is this item currently overdue for a
# stocktake, and by how much?" — used by the queue endpoint below AND
# by the alerts feed (`alerts/get_alerts.py`) so the bell + the runner
# never surface different sets of items (R-003). Filters for mute +
# push (snooze) + engagement gate in one pass, so callers get only
# the items they should actually surface.


@dataclass(frozen=True, slots=True)
class OverdueInfo:
    band: CadenceBand
    days: int  # whole days past the resolved band's window; always ≥ 1.


def resolve_overdue_map(
    items: list[StockItem],
    now: datetime | None = None,
) -> dict[UUID, OverdueInfo]:
    """Return `{stock_item_id: OverdueInfo}` for every item that is
    currently overdue for a stocktake — with mute, push (snooze) and
    the engagement gate already applied, and the cadence band already
    resolved (global default → Auto → Low/Out bump → Essential bump).

    Bulk-fetches all engagement signals in two queries regardless of
    input size, so the whole map costs the same as one queue endpoint
    call — safe to invoke from the alerts feed on every request.

    Pass `items` with `stock_level` loaded (the engagement gate needs
    the sequence). Repo access + AppSetting read happen inside — the
    caller doesn't need to thread them in.
    """
    now_ = now or datetime.now(UTC)
    if not items:
        return {}
    repo = SqlAlchemyRepository()
    app_setting = get_or_create_app_setting(repo)
    # 2026-08-20 — install-wide master switch. Off ⇒ nothing is ever overdue.
    # Enforced here rather than at each caller because this is the single
    # overdue authority (R-003): the queue endpoint, the Stock-overview count
    # and the alerts bell all read it, and each of them checking the flag for
    # itself is how the bell ends up nagging about a hidden surface.
    if not bool(getattr(app_setting, "stocktake_enabled", True)):
        return {}
    default_band = parse_band(
        getattr(app_setting, "stocktake_default_cadence_band", None)
    )
    auto_enabled = bool(
        getattr(app_setting, "stocktake_auto_tuning_enabled", True)
    )
    signals = _gather_engagement_signals([item.id for item in items], now_)
    result: dict[UUID, OverdueInfo] = {}
    for item in items:
        if not item.stocktake_alerts_are_enabled:
            continue
        if item.snoozed_until is not None:
            # SQLite hands back naive datetimes; `now_` is tz-aware, so a bare
            # `>` raised TypeError → GET /api/stocktake/queue (and the alerts
            # bell, which shares this map) 500'd for as long as any snooze was
            # active (FU-526). Coerce to aware-UTC before comparing.
            if as_utc(item.snoozed_until) > now_:
                continue
        if not _is_engaged(item, signals):
            continue
        history = ItemHistory(
            change_timestamps=tuple(
                signals.change_timestamps_by_item.get(item.id, ())
            ),
            hit_low_or_out_recently=item.id in signals.items_hit_low_or_out_recently,
            is_essential=bool(item.is_essential),
        )
        band = resolve_band(
            default_band=default_band,
            auto_enabled=auto_enabled,
            history=history,
            now=now_,
        )
        days = _compute_overdue_days(item, band.days, now_)
        if days <= 0:
            continue
        result[item.id] = OverdueInfo(band=band, days=days)
    return result


# ── Queue endpoint ─────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class RankedOverdue:
    """The overdue set in check order, shared by `/queue` and `/session`
    (finalisation 05-R10)."""
    ranked: list[tuple[StockItem, QueueRank]]
    band_by_item: dict[UUID, CadenceBand]
    days_by_item: dict[UUID, int]
    belief_ranked: bool


def ranked_overdue(repo, user, items: list[StockItem], now: datetime) -> RankedOverdue:
    """D-1 ordering (Chunk 5): belief ranks the queue when the user has stock
    inference on; cadence is the floor and the fallback. Beliefs are gathered
    for the **overdue set only** — the items that aren't due can't be
    reordered, and `/queue` is polled on every overview load."""
    overdue_map = resolve_overdue_map(items, now)
    overdue: list[tuple[int, CadenceBand, StockItem]] = [
        (info.days, info.band, item)
        for item in items
        if (info := overdue_map.get(item.id)) is not None
    ]
    beliefs: dict[UUID, PantryBelief] = {}
    belief_ranked = surface_enabled(user, SURFACE_STOCK)
    if belief_ranked and overdue:
        beliefs = gather_beliefs_for_items(repo, [item for _, _, item in overdue])
    return RankedOverdue(
        ranked=rank_queue([(days, item) for days, _, item in overdue], beliefs),
        band_by_item={item.id: band for _, band, item in overdue},
        days_by_item={item.id: days for days, _, item in overdue},
        belief_ranked=belief_ranked,
    )


@STOCKTAKE_ROUTER.route("/queue", methods=["GET"])
def get_stocktake_queue():
    try:
        limit = int(request.args.get("limit", "50"))
    except ValueError:
        return bad_request("limit must be an integer.")
    if limit < 1 or limit > 500:
        return bad_request("limit must be between 1 and 500.")

    repo = SqlAlchemyRepository()
    items = (
        repo.get(StockItem)
        .include("stock_level")
        .include("stock_location")
        .all()
    )
    overdue = ranked_overdue(repo, current_user(repo), items, datetime.now(UTC))
    ranked = overdue.ranked
    band_by_item = overdue.band_by_item
    days_by_item = overdue.days_by_item
    belief_ranked = overdue.belief_ranked
    total = len(ranked)
    # Counted over the WHOLE overdue set, not the page: the caller uses this
    # to decide whether the Stocktake button glows, and a household with more
    # than `limit` overdue items would otherwise stop glowing exactly when it
    # matters most.
    essential_total = sum(1 for item, _ in ranked if item.is_essential)
    page = ranked[:limit]

    dtos: List[StocktakeQueueItemDto] = []
    for item, verdict in page:
        band = band_by_item[item.id]
        days = days_by_item[item.id]
        belief = verdict.belief
        dtos.append(StocktakeQueueItemDto(
            stock_item_id=item.id,
            name=item.name,
            stock_level_name=item.stock_level.name if item.stock_level else None,
            stock_location_name=(
                item.stock_location.name if item.stock_location else None
            ),
            cadence_band=band.value,
            cadence_days=band.days,
            last_checked_at=(
                item.last_checked_at.isoformat()
                if item.last_checked_at is not None else None
            ),
            overdue_days=days,
            is_essential=bool(item.is_essential),
            check_rank=verdict.rank,
            belief_band=belief.believed_band if belief else None,
            belief_confidence=belief.confidence_band if belief else None,
            belief_reason=belief.reason if belief else None,
        ))
    return ok({
        "items": dtos,
        "total": total,
        "essential_total": essential_total,
        # Which engine ordered the list. The runner words its own "how this
        # works" copy off this rather than guessing from the rows — with
        # inference off every row is `overdue`, which is indistinguishable
        # from "inference on, but nothing has evidence yet", and those two
        # deserve different explanations.
        "ranked_by": "belief" if belief_ranked else "cadence",
    })


# ── /check (single) ────────────────────────────────────────────────────

@STOCK_ITEM_ROUTER.route("/<uuid:stock_item_id>/check", methods=["POST"])
def mark_stock_item_checked(stock_item_id: UUID):
    """Confirm the current level is still correct. Bumps last_checked_at
    AND clears any active Push snooze (a Check is a stronger claim than
    a Push — the user just looked). Does NOT touch stock_level_last_
    updated. Idempotent."""
    repo = SqlAlchemyRepository()
    item = repo.get(StockItem).by_id(stock_item_id)
    if item is None:
        return not_found("StockItem", stock_item_id)
    item.last_checked_at = datetime.now(UTC)
    item.snoozed_until = None
    repo.save_changes()
    _LOGGER.debug("Stocktake check: %s", stock_item_id)
    return ok({
        "stock_item_id": str(stock_item_id),
        "last_checked_at": item.last_checked_at.isoformat(),
    })


# ── /snooze (single) — Push 3 days ────────────────────────────────────

@STOCK_ITEM_ROUTER.route("/<uuid:stock_item_id>/snooze", methods=["POST"])
def snooze_stock_item(stock_item_id: UUID):
    """PROPOSAL_STOCKTAKE_MODE §5 — the honest defer. Hides the item
    from the queue for the fixed 3-day window. Deliberately does NOT
    bump last_checked_at — Push makes no claim the stock is right, so
    a Push must not corrupt the "when was this last verified" audit."""
    repo = SqlAlchemyRepository()
    item = repo.get(StockItem).by_id(stock_item_id)
    if item is None:
        return not_found("StockItem", stock_item_id)
    item.snoozed_until = datetime.now(UTC) + timedelta(days=_SNOOZE_DAYS)
    repo.save_changes()
    _LOGGER.debug(
        "Stocktake snooze: %s until %s", stock_item_id, item.snoozed_until,
    )
    return ok({
        "stock_item_id": str(stock_item_id),
        "snoozed_until": item.snoozed_until.isoformat(),
    })


# ── /bulk-check ────────────────────────────────────────────────────────

class BulkCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[UUID] = Field(min_length=1, max_length=500)


@STOCKTAKE_ROUTER.route("/bulk-check", methods=["POST"])
@has_request_body(BulkCheckRequest)
def bulk_check():
    body: BulkCheckRequest = get_request_body()
    repo = SqlAlchemyRepository()
    table = db.metadata.tables["StockItem"]
    now = datetime.now(UTC)
    # Bulk-check also clears any active snoozes, mirroring the
    # single-item /check path — a Check is stronger than a Push.
    # R-005 carve-out: a set-based UPDATE of two stamp columns that carry no
    # rule (no level change, no event), committed through the repository.
    result = repo.session.execute(
        table.update()
        .where(table.c.id.in_(body.ids))
        .values(last_checked_at=now, snoozed_until=None)
    )
    repo.save_changes()
    return ok({"checked": int(result.rowcount or 0)})
