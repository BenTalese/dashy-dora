"""Which stock items are already on an active shopping list.

The rule the retired *Before you shop* card was built on (deleted 2026-09-08,
see `get_restock_radar.py`), lifted here unchanged so Restock radar can apply it
again (FU-897) without writing it a second time:

  * **active** means any list that is not `done` — a draft or a list being
    shopped. A done list is history; its lines say nothing about today.
  * **ticked lines count.** A ticked line means "in the trolley", which is the
    most dealt-with a thing can be. This is deliberately broader than
    `/shopping-lists/membership`, which only reports *unticked* lines because it
    answers a different question ("what will the cart button do if I press
    it?"), not "has somebody already dealt with this?".
  * product-only lines (no stock item) are not a stock item's membership.
"""
from typing import List
from uuid import UUID

from dora_api.domain.entities.shopping_list import (SHOPPING_LIST_STATUS_DONE,
                                                    ShoppingList,
                                                    ShoppingListLine)
from dora_api.infrastructure.ports import Repository
from dora_api.persistence.field import EntityField


def stock_items_on_active_lists(repository: Repository) -> set[UUID]:
    """Stock item ids with any line (ticked or not) on a list that isn't done."""
    active_lists: List[ShoppingList] = repository.get(ShoppingList).all(
        EntityField(ShoppingList, ShoppingList.Fields.STATUS)
        .ne(SHOPPING_LIST_STATUS_DONE)
    )
    if not active_lists:
        return set()
    lines: List[ShoppingListLine] = repository.get(ShoppingListLine).all(
        EntityField(ShoppingListLine, ShoppingListLine.Fields.SHOPPING_LIST_ID)
        .in_([l.id for l in active_lists])
    )
    return {l.stock_item_id for l in lines if l.stock_item_id is not None}
