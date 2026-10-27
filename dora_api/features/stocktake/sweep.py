"""The Sweep phase's rule: which items *newly* dropped out of rotation.

Chunk 6 / **D-4** of `docs/04_proposals/IMPL_PLAN_STOCK_SIGNAL_CONSOLIDATION.md`.

The engagement gate (`stocktake._is_engaged`) quietly excludes any item showing
no current sign you keep it. That's correct and it is *most* of what makes the
queue tolerable — the tin you stopped buying two years ago is **supposed** to be
invisible. So the Sweep phase must not be "here is everything excluded": that
list is long, boring, permanent, and re-nagging you about it every session is
precisely the behaviour this plan exists to remove.

What's worth a glance is the **event**: something you *were* tracking has just
stopped being tracked. A handful per session at most, and it decays to zero for a
stable pantry.

**How "newly" is decided without storing history.** The gate's two time-windowed
signals both expire on a known schedule: an item falls out
`_ENGAGEMENT_WINDOW_DAYS` after its last level change or last shopping-list
appearance, whichever is later. So the drop-out moment is computable from the
events themselves:

    dropped_out_at = latest_engagement_event + ENGAGEMENT_WINDOW

and an item is *newly* excluded when that instant is **after the user's last
session** and not in the future. No schema history, no nightly job, and the
answer can't drift from the gate because it's derived from the same two events
the gate reads.

**Deliberate exclusions from the Sweep:**

* **Items with no engagement events at all.** Never tracked, rather than newly
  untracked — surfacing those is the "here's everything" failure mode above.
* **Items still engaged.** Obviously; the gate answers this and we re-ask it
  rather than inferring from timestamps.
* **Everything, on a user's first ever session** (`last_session_at is None`).
  Otherwise the phase's debut would dump every long-dead item into it, teaching
  the user in one shot that this screen is noise.

**Copy note carried from D-4:** never "dead items" — it judges something the
user may still care about. The phrasing is *"Dora's stopped tracking these"*.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select

from dora_api.persistence.aware import as_utc
from dora_api.app import db
from dora_api.domain.entities.shopping_list import SHOPPING_LIST_STATUS_DONE
from dora_api.domain.entities.stock_item import StockItem


@dataclass(frozen=True, slots=True)
class SweptItem:
    """One item that has just left rotation, with the evidence for why."""
    item: StockItem
    dropped_out_at: datetime
    # The event the drop-out was measured from — the last time anything
    # happened to this item. Shown to the user, because "stopped tracking" is
    # only fair if you can see what it's based on.
    last_activity_at: datetime


def _latest_activity_by_item(item_ids: list[UUID]) -> dict[UUID, datetime]:
    """`{item_id: most recent engagement event}` — two aggregate queries,
    regardless of pantry size.

    Deliberately **unwindowed**, unlike the gate's own queries: the gate only
    cares whether an event is inside the last 60 days, but a drop-out that
    happened yesterday was caused by an event ~60 days ago, which the gate's
    window has already discarded.
    """
    if not item_ids:
        return {}

    # R-005 carve-out: two MAX aggregates across tables the port can't join.
    slc = db.metadata.tables["StockLevelChange"]
    line = db.metadata.tables["ShoppingListLine"]
    lst = db.metadata.tables["ShoppingList"]

    latest: dict[UUID, datetime] = {}

    change_rows = db.session.execute(
        select(slc.c.stock_item_id, func.max(slc.c.changed_at))
        .where(slc.c.stock_item_id.in_(item_ids))
        .group_by(slc.c.stock_item_id)
    ).all()
    for item_id, changed_at in change_rows:
        stamp = as_utc(changed_at)
        if stamp is not None:
            latest[item_id] = stamp

    # Shopping-list appearances. An *active* list is a live signal with no
    # timestamp to expire, so an item on one can't have dropped out — it is
    # filtered by the engagement gate before it ever reaches here. Only closed
    # lists carry a date worth measuring from.
    list_rows = db.session.execute(
        select(line.c.stock_item_id, func.max(lst.c.completed_at))
        .select_from(line.join(lst, line.c.shopping_list_id == lst.c.id))
        .where(
            line.c.stock_item_id.in_(item_ids),
            lst.c.status == SHOPPING_LIST_STATUS_DONE,
            lst.c.completed_at.isnot(None),
        )
        .group_by(line.c.stock_item_id)
    ).all()
    for item_id, completed_at in list_rows:
        stamp = as_utc(completed_at)
        if stamp is None:
            continue
        current = latest.get(item_id)
        if current is None or stamp > current:
            latest[item_id] = stamp

    return latest


def resolve_newly_swept(
    unengaged_items: list[StockItem],
    *,
    last_session_at: datetime | None,
    engagement_window_days: int,
    now: datetime | None = None,
) -> list[SweptItem]:
    """The Sweep list, newest drop-out first.

    `unengaged_items` is the caller's already-filtered set of items failing the
    engagement gate — the gate stays the single authority on *whether* an item
    is out (R-003); this module only dates the departure.

    `last_session_at is None` ⇒ empty. See the module docstring.
    """
    if last_session_at is None or not unengaged_items:
        return []

    # `last_session_at` comes off `User.stocktake_last_session_at`, which SQLite
    # hands back naive — the same trap as FU-526. Every comparison below is
    # against tz-aware values, so a bare `<=` raised TypeError and 500'd
    # GET /api/stocktake/session for any user who had ever completed a run.
    # It went unnoticed because nothing seeded a past session: the field was
    # None on every dev and test user, and None short-circuits above. The
    # 2026-08-27 Sweep fixture (which sets it) is what surfaced it.
    last_session_ = as_utc(last_session_at)
    assert last_session_ is not None  # non-None checked above; narrows the type
    now_ = as_utc(now) or datetime.now(UTC)
    window = timedelta(days=engagement_window_days)
    latest = _latest_activity_by_item([item.id for item in unengaged_items])

    swept: list[SweptItem] = []
    for item in unengaged_items:
        last_activity = latest.get(item.id)
        if last_activity is None:
            continue  # never tracked, not newly untracked
        dropped_out_at = last_activity + window
        if dropped_out_at <= last_session_ or dropped_out_at > now_:
            continue
        swept.append(SweptItem(
            item=item,
            dropped_out_at=dropped_out_at,
            last_activity_at=last_activity,
        ))

    # Newest departure first: the most recent change is the one the user is
    # most likely to recognise and have an opinion about.
    swept.sort(key=lambda s: (-s.dropped_out_at.timestamp(), s.item.name.lower()))
    return swept
