"""GET /api/dashboard/restock-radar — what recently went low or out.

Owner feedback, 2026-09-04: *"Restock radar looks like it could be useful. I
don't know how it works under the hood, but I think showing a list of most
recently out of stock and a list of most recently low (one on left, one on
right) could be good."*

What it used to show was `/reports/keeps-running-out` — a genuinely clever
signal (how often an item was *already out* at the moment somebody added it to
a list, i.e. "you ran out before you got round to restocking it"), and the
reports review rated it the most insightful thing on either surface. But it is
a **history** signal: it ranks by a lifetime count, so the card looked
identical week after week and the "radar" never swept. It also needs months of
list history before it says anything, which is why a young install saw only the
empty state.

This is the present tense of the same idea: the things that changed band most
recently, which is what a radar is for. `keeps-running-out` itself was cut
from the reports page on 2026-09-27 and deleted.

`stock_level_last_updated` is the clock, not a `ConsumptionEvent` scan: the
question is "when did this item become out", and that column *is* when its band
last changed. An event scan would additionally need deduping per item and
reconciling against the current level, to arrive at the same answer more
expensively.

Only items **currently** in the band are listed. "Recently went out" about
something you have since restocked is not a restock cue, it is a diary entry.

## Owner batch, 2026-09-08 — this card absorbed "Before you shop"

Two of that batch's items were about the same thing. He first asked *Before you
shop* to grow a level indicator, a "recently low or out" heading and
recency-with-a-cutoff ordering — and then, further down the same list,
concluded: *"There's a lot of crossover between before you shop and restock
radar. I'm inclined to axe before you shop and chuck 'planned' as a chip on the
rows for restock radar."* Later points win, so `get_before_you_shop.py` is
deleted and its two surviving ideas landed here:

  **one list, not two.** Out and Low were two columns ordered by recency
  *within* a column, so the single most recent change wasn't necessarily at the
  top of the card. One list ordered purely by recency answers "what changed
  lately" — and the band, which the columns were carrying, is now carried by
  the level dot at the head of each row (`StockLevelDot`, the same indicator the
  stock pages use) rather than by which column you're reading.

  **`is_planned`**, the one thing *Before you shop* knew that nothing else did:
  the upcoming plan wants this item. That came from `gather_planned_demand` and
  it still does — the same signal the stock-item page's planned-demand card and
  the planner read (R-003), not a second derivation of it.

`MAX_AGE_DAYS` is the other half of the same feedback: *"Don't show stuff that
has been low/out for a long time."* An item that went out in March is not a
restock cue either — it is something the household has decided to live without,
and it sat at the bottom of this card forever crowding out the things that
actually changed this week. Thirty days is one shopping month: long enough that
a fortnightly shopper still sees last cycle's misses, short enough that the
list turns over. The item stays *visible* — on the stock page, filtered by
level, which is the surface that owns "everything you're out of". This card
only claims to be the recent ones, and its empty copy now says so rather than
claiming everything is stocked.

The list-membership filter *Before you shop* also applied ("only show what
isn't already on a list") deliberately did **not** come across — see
`DORA_FOLLOWUPS.md` FU-897. Each row carries `AddToListButton`, which already
shows its own on-a-list state, so the fact is on screen; using it to *hide*
rows is a separate call the owner hasn't made.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List
from uuid import UUID

from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.stock_status import (LOW_STOCK_SEQUENCE,
                                          OUT_OF_STOCK_SEQUENCE)
from dora_api.features.routers import DASHBOARD_ROUTER
from dora_api.features.stock_items._level_access import resolve_levels_by_item
from dora_api.features.stock_items.planned_demand import gather_planned_demand
from dora_api.infrastructure.api_response import ok
from dora_api.infrastructure.ports import Repository
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)

# One list now, so one cap. Five was per-column; six rows of one list is about
# the same card height and reads as a ranking rather than two short tables.
MAX_ROWS = 6

# How stale a band change can be and still count as "recently". See the module
# docstring — this is the owner's *"don't show stuff that has been low/out for a
# long time"*, and 30 days is one shopping month.
MAX_AGE_DAYS = 30


@dataclass(frozen=True, slots=True)
class RestockRow:
    stock_item_id: UUID
    name: str
    # When the item's band last changed — what "recently" is ordered on. The
    # SPA renders it relative ("2 days ago"); the server sends the instant.
    changed_at: datetime
    is_essential: bool
    # The recorded level, so the row can render the app's own level indicator
    # (`StockLevelDot` takes a sequence) instead of the words "out" / "low".
    # `band` stays alongside it because the SPA sorts nothing but does colour
    # the essential/planned chips on it, and re-deriving "is this the out rung?"
    # from a sequence in the client would be the domain rule written twice.
    level_sequence: int
    level_name: str
    band: str  # 'low' | 'out'
    # Does the coming fortnight's plan want this item? The one thing the
    # retired "Before you shop" card knew that no other surface did — straight
    # from `gather_planned_demand`, never re-derived (R-003).
    is_planned: bool = False


@dataclass(frozen=True, slots=True)
class RestockRadarDto:
    rows: List[RestockRow] = field(default_factory=list)
    # The cutoff the rows were filtered by, so the card's empty copy can name
    # the window ("nothing in the last 30 days") rather than hardcoding a
    # number this module owns (R-003 / D-006).
    window_days: int = MAX_AGE_DAYS


class GetRestockRadarHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self) -> RestockRadarDto:
        items: List[StockItem] = self.repository.get(StockItem).all()
        if not items:
            return RestockRadarDto()

        # Through the shared resolver, not `item.stock_level`: that
        # relationship is `lazy="noload"` and reading it returns None, which
        # reads as "no level recorded" — the trap `_level_access.py` closes.
        levels = resolve_levels_by_item(self.repository, items)

        # Naive UTC, matching `stock_level_last_updated`'s stored form.
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            days=MAX_AGE_DAYS,
        )

        # `recorded_by_item` is what lets `gather_planned_demand` grade urgency;
        # we don't read the urgency here (every row is already low or out, so it
        # would be non-none by construction and tell us nothing), but passing
        # the levels costs nothing and keeps the call honest.
        # `resolve_levels_by_item` maps an unlevelled item to None (a deleted
        # level nulls the FK) — skip it here as `get_planned_demand` does,
        # instead of 500-ing the whole card (finalisation 08-R1).
        recorded_by_item = {
            item_id: level.sequence
            for item_id, level in levels.items()
            if level is not None
        }
        demand = gather_planned_demand(
            self.repository, recorded_by_item=recorded_by_item,
        )

        rows: List[RestockRow] = []
        for item in items:
            level = levels.get(item.id)
            if level is None or item.stock_level_last_updated is None:
                continue
            # `>=` on out, `==` on low: out is the terminal band and anything
            # beyond it is still out, while low is a single rung. Same
            # asymmetry `stock_status.is_out_of_stock` / `is_low_stock` use.
            if level.sequence >= OUT_OF_STOCK_SEQUENCE:
                band = "out"
            elif level.sequence == LOW_STOCK_SEQUENCE:
                band = "low"
            else:
                continue
            if item.stock_level_last_updated < cutoff:
                continue
            planned = demand.get(item.id)
            rows.append(RestockRow(
                stock_item_id=item.id,
                name=item.name,
                changed_at=item.stock_level_last_updated,
                is_essential=bool(item.is_essential),
                level_sequence=level.sequence,
                level_name=level.name,
                band=band,
                # `needed_meals` rather than mere presence: an item whose every
                # planned meal is already covered by a cooked batch is not
                # something the plan still needs you to buy.
                is_planned=planned is not None and planned.needed_meals > 0,
            ))

        # Purely by recency — the card's whole claim. Two passes rather than one
        # `reverse=True` on a tuple key: reversing would also flip the name
        # tie-break to Z-A. Python's sort is stable, so ordering by name first
        # and then by recency leaves same-instant rows in A-Z, which is what
        # stops two items levelled in the same write reshuffling between loads.
        rows.sort(key=lambda r: r.name.lower())
        rows.sort(key=lambda r: r.changed_at, reverse=True)
        return RestockRadarDto(rows=rows[:MAX_ROWS])


@DASHBOARD_ROUTER.route("/restock-radar", methods=["GET"])
def get_restock_radar():
    _Result = GetRestockRadarHandler(SqlAlchemyRepository()).handle()
    _LOGGER.debug(
        "Restock radar: %d rows within %d days (%d planned)",
        len(_Result.rows), _Result.window_days,
        sum(1 for r in _Result.rows if r.is_planned),
    )
    return ok(_Result)
