"""The three-phase stocktake session.

  GET  /api/stocktake/session            — Review + Walk + Sweep, in one read
  POST /api/stocktake/session/complete   — stamp the user's session watermark

Chunk 6 / **D-4** of `docs/04_proposals/IMPL_PLAN_STOCK_SIGNAL_CONSOLIDATION.md`.
**Shrink → work → tidy:**

| Phase | Posture | Content |
|---|---|---|
| **Review** | desk | Items Dora is confident about. Agreeing is one tap. |
| **Walk** | pantry | The uncertain ones, least-certain first. |
| **Sweep** | housekeeping | Items that just dropped out of rotation. |

**Why Review comes first.** Its items are derived from *logged evidence* —
purchases and cooks — so you don't need to be standing in the pantry to agree
with them. The uncertain ones need eyes on a shelf. Splitting the two means you
walk in with a shorter list, and the two halves stop competing for one posture.

**Why this is a separate endpoint from `/queue`.** `/queue` is polled by the
stock overview on every load, for a count and a set of ids. The session needs
belief wording, a Sweep pass over the *un*engaged items, and the user's
watermark — none of which the overview should pay for on a page load. They share
every rule module (`resolve_overdue_map`, `queue_ranking`, `sweep`), so there is
still one definition of who is due and in what order (R-003); this is a second
*view*, not a second engine.

**Belief off ⇒ no Review phase**, per D-4's edge cases: that user opted out of
Dora's guesses, and opening their stocktake with a screen of Dora's reasoning
would contradict the toggle. `queue_ranking` already returns everything as
`overdue` for them, so the split falls out for free — Review is empty and the
client skips it silently, exactly as it does for the (very common, early on)
case of a household with no confident items yet.
"""
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import List
from uuid import UUID

from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_location import StockLocation
from dora_api.domain.location_breadcrumb import build_breadcrumb
from dora_api.features.routers import STOCKTAKE_ROUTER
from dora_api.features.stock_items.pantry_belief import PantryBelief
from dora_api.features.stocktake.queue_ranking import RANK_CONFIDENT
from dora_api.features.stocktake.stocktake import (ENGAGEMENT_WINDOW_DAYS,
                                                   ranked_overdue,
                                                   resolve_unengaged_items)
from dora_api.features.stocktake.sweep import resolve_newly_swept
from dora_api.infrastructure.api_response import ok, unauthorized
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.session_user import current_user

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SessionItemDto:
    """A Review or Walk row. Same shape for both so the client renders one
    row component twice — the phase decides the *affordances*, not the data."""
    stock_item_id: UUID
    name: str
    stock_level_id: UUID | None
    stock_level_name: str | None
    stock_location_name: str | None
    # Owner feedback 2026-09-01: *"Top shelf"* on its own is useless when the
    # job is to go and find the thing. The walk shows the whole path, so the
    # full breadcrumb travels with the row rather than the leaf name alone.
    stock_location_breadcrumb: List[str]
    cadence_band: str
    overdue_days: int
    is_essential: bool
    check_rank: str
    # Belief's own words. Present on every Review row by definition (a row is
    # only in Review because belief is confident about it) and on Walk rows
    # when there's an inference to show.
    belief_band: str | None
    belief_confidence: str | None
    belief_reason: str | None


@dataclass(frozen=True, slots=True)
class SweptItemDto:
    """A Sweep row: what left rotation, when, and off the back of what."""
    stock_item_id: UUID
    name: str
    stock_level_name: str | None
    stock_location_name: str | None
    stock_location_breadcrumb: List[str]
    # ISO instants. `last_activity_at` is shown because "Dora's stopped
    # tracking this" is only fair if the user can see what it's based on.
    dropped_out_at: str
    last_activity_at: str


def _item_dto(
    item: StockItem,
    *,
    rank: str,
    band_value: str,
    overdue_days: int,
    belief: PantryBelief | None,
    locations_by_id: dict[UUID, StockLocation],
) -> SessionItemDto:
    return SessionItemDto(
        stock_item_id=item.id,
        name=item.name,
        stock_level_id=item._stock_level_id,
        stock_level_name=item.stock_level.name if item.stock_level else None,
        stock_location_name=(
            item.stock_location.name if item.stock_location else None
        ),
        stock_location_breadcrumb=build_breadcrumb(
            item.stock_location, locations_by_id,
        ),
        cadence_band=band_value,
        overdue_days=overdue_days,
        is_essential=bool(item.is_essential),
        check_rank=rank,
        belief_band=belief.believed_band if belief else None,
        belief_confidence=belief.confidence_band if belief else None,
        belief_reason=belief.reason if belief else None,
    )


@STOCKTAKE_ROUTER.route("/session", methods=["GET"])
def get_stocktake_session():
    repo = SqlAlchemyRepository()
    user = current_user(repo)
    if user is None:
        return unauthorized()

    items: List[StockItem] = (
        repo.get(StockItem)
        .include("stock_level")
        .include("stock_location")
        .all()
    )
    now = datetime.now(UTC)
    # One read of the location tree feeds every breadcrumb below — the parent
    # chain can't be walked from an eagerly-loaded child alone.
    locations_by_id: dict[UUID, StockLocation] = {
        loc.id: loc for loc in repo.get(StockLocation).all()
    }

    # ── Review + Walk: the overdue set, ranked ──────────────────────────
    overdue = ranked_overdue(repo, user, items, now)
    band_by_item = overdue.band_by_item
    days_by_item = overdue.days_by_item
    belief_ranked = overdue.belief_ranked
    ranked = overdue.ranked

    review: List[SessionItemDto] = []
    walk: List[SessionItemDto] = []
    for item, verdict in ranked:
        dto = _item_dto(
            item,
            rank=verdict.rank,
            band_value=band_by_item[item.id].value,
            overdue_days=days_by_item[item.id],
            belief=verdict.belief,
            locations_by_id=locations_by_id,
        )
        # The split is the rank, not a second judgement. Chunk 5 already
        # decided what "Dora is confident about this" means; re-deciding it
        # here is how the two would drift.
        (review if verdict.rank == RANK_CONFIDENT else walk).append(dto)

    # ── Sweep: what just left rotation ──────────────────────────────────
    swept = resolve_newly_swept(
        resolve_unengaged_items(items, now),
        last_session_at=user.stocktake_last_session_at,
        engagement_window_days=ENGAGEMENT_WINDOW_DAYS,
        now=now,
    )
    sweep = [
        SweptItemDto(
            stock_item_id=s.item.id,
            name=s.item.name,
            stock_level_name=(
                s.item.stock_level.name if s.item.stock_level else None
            ),
            stock_location_name=(
                s.item.stock_location.name if s.item.stock_location else None
            ),
            stock_location_breadcrumb=build_breadcrumb(
                s.item.stock_location, locations_by_id,
            ),
            dropped_out_at=s.dropped_out_at.isoformat(),
            last_activity_at=s.last_activity_at.isoformat(),
        )
        for s in swept
    ]

    _LOGGER.debug(
        "stocktake session: review=%d walk=%d sweep=%d",
        len(review), len(walk), len(sweep),
    )
    return ok({
        "review": review,
        "walk": walk,
        "sweep": sweep,
        "ranked_by": "belief" if belief_ranked else "cadence",
        "last_session_at": (
            user.stocktake_last_session_at.isoformat()
            if user.stocktake_last_session_at is not None else None
        ),
    })


@STOCKTAKE_ROUTER.route("/session/complete", methods=["POST"])
def complete_stocktake_session():
    """Move the user's Sweep watermark to now.

    Called when the runner reaches its summary screen — **not** per phase and
    not on abandon. Stamping mid-session would mean a run you backed out of
    silently swallowed a set of drop-outs you never saw, and the Sweep list is
    the one thing here that can't be recovered later: once the watermark passes
    a departure, that item is indistinguishable from the long-dead ones.

    Idempotent, and deliberately makes no claim about any *item* — the checks
    the user actually performed were each written by `/check` or `/bulk-check`
    as they happened. This only records "you looked".
    """
    repo = SqlAlchemyRepository()
    user = current_user(repo)
    if user is None:
        return unauthorized()
    user.stocktake_last_session_at = datetime.now(UTC)
    repo.save_changes()
    return ok({"last_session_at": user.stocktake_last_session_at.isoformat()})
