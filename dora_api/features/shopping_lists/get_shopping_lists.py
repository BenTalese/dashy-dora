"""GET /api/shopping-lists — overview of every shopping list.

Each entry includes the line count, a "ticked / total" progress, the
server-owned `display_name` / `effective_date`, and exactly one entry is
flagged `is_next_up` (the list the UI should land on / mark "next"). The
ordering, naming-fallback and next-up rules are domain rules (R-003) — they
live here once, not in TS. Detail (with full lines + selected products)
lives on GET /api/shopping-lists/<id>.
"""
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import List
from uuid import UUID

from sqlalchemy import func, select

from dora_api.domain.entities.shopping_list import (ShoppingList,
                                                    ShoppingListLine)
from dora_api.features.routers import SHOPPING_LIST_ROUTER
from dora_api.infrastructure.api_response import ok
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ShoppingListSummaryDto:
    shopping_list_id: UUID
    # The user's custom name (None when the list self-labels from dates) and
    # the resolved label the UI should render. Kept separate so "rename"
    # inputs can prefill the custom name only.
    name: str | None
    display_name: str
    status: str
    created_at: datetime
    completed_at: datetime | None
    planned_shop_date: date | None
    # finalised shop date > planned shop date > created — the list's position
    # in time. The response is sorted ascending by this (past first), so the
    # rail/dropdown can render in order without re-deriving the rule.
    effective_date: date
    is_next_up: bool
    line_count: int
    ticked_count: int


class GetShoppingListsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self) -> List[ShoppingListSummaryDto]:
        # Two cheap queries are simpler than a join + group_by here, and the
        # list count is small (dozens at most). We aggregate line counts in
        # Python after a single grouped query.
        session = self.repository.session
        lists: List[ShoppingList] = self.repository.get(ShoppingList).all()

        counts: dict[UUID, tuple[int, int]] = {}
        # `(shopping_list_id, ticked) -> count` rolled up in one query.
        # Lines set aside by the budget aren't part of this shop, so they
        # aren't counted — the same rule as the detail's `totals.line_count`
        # (FU-966: the rail said 7 where the list's own card said 6).
        rows = session.execute(
            select(
                ShoppingListLine.shopping_list_id,
                ShoppingListLine.is_ticked,
                func.count(),
            )
            .where(ShoppingListLine.deferred_by_budget.is_(False))
            .group_by(ShoppingListLine.shopping_list_id, ShoppingListLine.is_ticked)
        ).all()
        for list_id, is_ticked, count in rows:
            total, ticked = counts.get(list_id, (0, 0))
            total += count
            if is_ticked:
                ticked += count
            counts[list_id] = (total, ticked)

        next_up_id = _next_up_list_id(lists)
        out: List[ShoppingListSummaryDto] = []
        for lst in lists:
            total, ticked = counts.get(lst.id, (0, 0))
            out.append(ShoppingListSummaryDto(
                shopping_list_id = lst.id,
                name = lst.name,
                display_name = lst.display_name,
                status = lst.status,
                created_at = lst.created_at,
                completed_at = lst.completed_at,
                planned_shop_date = lst.planned_shop_date,
                effective_date = lst.effective_date,
                is_next_up = lst.id == next_up_id,
                line_count = total,
                ticked_count = ticked,
            ))
        # One time-ordered continuum (UX-v2), **newest first** (2026-08-28
        # owner call): your drafts and the shop you're on are at the top, and
        # finished lists trail off below them. It ran oldest-first until then,
        # which put a wall of history above the only lists you can still act on
        # — and got worse the longer the household used Dora. Done and active
        # are still interleaved by effective date rather than grouped by status,
        # so the rail stays one timeline. The rail and the mobile dropdown
        # render this order verbatim; `_next_up_list_id` picks with min/max and
        # is unaffected by the sort direction.
        out.sort(key=lambda s: (s.effective_date, s.created_at), reverse=True)
        return out


def _next_up_list_id(lists: List[ShoppingList]) -> UUID | None:
    """The list the UI should land on / flag as "next up" (UX-v2 §3.3):
    1. a live shop always wins (earliest if several are mid-shop);
    2. else the pending list whose effective date comes first on/after the
       most recent completed list ("first date-wise after the last completed");
    3. else (only overdue pending lists) the earliest pending one;
    4. else (everything done) the most recently completed.
    """
    if not lists:
        return None

    def time_key(lst: ShoppingList):
        return (lst.effective_date, lst.created_at)

    shopping = [l for l in lists if l.is_shopping]
    if shopping:
        return min(shopping, key=time_key).id

    pending = [l for l in lists if not l.is_done]
    done = [l for l in lists if l.is_done]
    if pending:
        if done:
            last_completed = max(
                (d.completed_at for d in done if d.completed_at),
                default=None,
            )
            if last_completed is not None:
                after = [
                    l for l in pending
                    if l.effective_date >= last_completed.date()
                ]
                if after:
                    return min(after, key=time_key).id
        return min(pending, key=time_key).id

    return max(done, key=lambda l: l.completed_at or l.created_at).id


@SHOPPING_LIST_ROUTER.route("", methods=["GET"])
def get_shopping_lists():
    _Summaries = GetShoppingListsHandler(SqlAlchemyRepository()).handle()
    _LOGGER.debug("Returned %d shopping list summaries", len(_Summaries))
    return ok(_Summaries)
