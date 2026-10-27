"""GET /api/shopping-lists/membership — which stock items are on which active lists.

Used by the stock overview to colour the cart button per row (already on the
quick-add target, on another list, on multiple unticked lists, etc) without
loading every list's lines client-side.

Chunk 2: the "quick-add target" is inferred from DRAFT count (resolver);
the user never marks a list as their main one. `quick_add_target_list_id`
is non-null only when
exactly one DRAFT exists.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List
from uuid import UUID

from dora_api.domain.entities.shopping_list import (SHOPPING_LIST_STATUS_DONE,
                                                    ShoppingList,
                                                    ShoppingListLine)
from dora_api.features.routers import SHOPPING_LIST_ROUTER
from dora_api.features.shopping_lists.quick_add_target_resolver import \
    resolve_quick_add_target
from dora_api.infrastructure.api_response import ok
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StockItemMembershipDto:
    stock_item_id: UUID
    # List IDs the item appears on, AND is still unticked. Ticked items
    # are excluded — they're effectively "done" from a quick-action POV.
    unticked_list_ids: List[UUID] = field(default_factory=list)
    # True if the item is unticked on the (inferred) quick-add target list.
    on_quick_add_target: bool = False


@dataclass(frozen=True, slots=True)
class ActiveListInfoDto:
    """Lightweight summary of an active list — surfaced alongside the
    per-item membership map so the cart-button remove flow can show
    human-readable list names without an extra round-trip."""
    shopping_list_id: UUID
    name: str
    status: str


@dataclass(frozen=True, slots=True)
class MembershipDto:
    quick_add_target_list_id: UUID | None
    items: List[StockItemMembershipDto] = field(default_factory=list)
    active_lists: List[ActiveListInfoDto] = field(default_factory=list)


class GetMembershipHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self) -> MembershipDto:
        # Active (non-archived) lists only — archived lists shouldn't paint
        # the cart button.
        active_lists: List[ShoppingList] = self.repository.get(ShoppingList).all(
            EntityField(ShoppingList, ShoppingList.Fields.STATUS).ne(SHOPPING_LIST_STATUS_DONE)
        )
        outcome = resolve_quick_add_target(active_lists)
        quick_add_target_id = outcome.target_list_id if outcome.kind == "single" else None
        active_ids = {l.id for l in active_lists}

        if not active_ids:
            return MembershipDto(items=[], quick_add_target_list_id=quick_add_target_id)

        # Unticked lines on the active lists — filtered at the query, not
        # after loading every unticked line ever (finalisation 03-R4).
        unticked_lines: List[ShoppingListLine] = self.repository.get(ShoppingListLine).all(
            EntityField(ShoppingListLine, ShoppingListLine.Fields.IS_TICKED).eq(False)
            & EntityField(ShoppingListLine, ShoppingListLine.Fields.SHOPPING_LIST_ID).in_(list(active_ids))
        )

        per_item: Dict[UUID, List[UUID]] = {}
        for line in unticked_lines:
            # A product-only line (stock_item_id NULL) is not a stock item's
            # membership; bucketing it under None serialised a DTO that lied
            # about its type.
            if line.stock_item_id is None:
                continue
            per_item.setdefault(line.stock_item_id, []).append(line.shopping_list_id)

        items = [
            StockItemMembershipDto(
                stock_item_id = stock_item_id,
                unticked_list_ids = list_ids,
                on_quick_add_target = (
                    quick_add_target_id is not None and quick_add_target_id in list_ids
                ),
            )
            for stock_item_id, list_ids in per_item.items()
        ]
        active_list_infos = [
            ActiveListInfoDto(
                shopping_list_id = l.id,
                # The resolved label (custom name or date fallback) — this
                # DTO exists to render pickers/toasts, never to edit names.
                name = l.display_name,
                status = l.status,
            )
            for l in active_lists
        ]
        return MembershipDto(
            quick_add_target_list_id=quick_add_target_id,
            items=items,
            active_lists=active_list_infos,
        )


@SHOPPING_LIST_ROUTER.route("/membership", methods=["GET"])
def get_membership():
    _Result = GetMembershipHandler(SqlAlchemyRepository()).handle()
    _LOGGER.debug(
        "Membership: quick_add_target=%s, %d items on at least one active list",
        _Result.quick_add_target_list_id, len(_Result.items),
    )
    return ok(_Result)
