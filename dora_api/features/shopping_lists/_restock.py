"""Restock: a bought item goes to its Stocked level.

Shared by the two ways a shop says "I bought this": `POST /finish` (flow
mode, every ticked line at once) and `POST /lines/<id>/buy` (simple mode, one
line at a time). One writer so the two can't disagree about what buying means.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable
from uuid import UUID

from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_level import StockLevel
from dora_api.domain.stock_status import StockStatus, level_for_status
from dora_api.infrastructure.ports import Repository
from dora_api.persistence.field import EntityField


def restock_stock_items(
    repository: Repository, stock_item_ids: Iterable[UUID], *, now: datetime,
) -> int:
    """Set each item's level to Stocked, resolved by status identity, not name.
    Returns how many items were updated. The caller owns the commit."""
    ids = [i for i in stock_item_ids if i is not None]
    if not ids:
        return 0
    stocked = level_for_status(repository.get(StockLevel).all(), StockStatus.STOCKED)
    if stocked is None:
        return 0
    items = repository.get(StockItem).all(EntityField(StockItem, "id").in_(ids))
    for item in items:
        # Set the FK column too: the relationship is lazy="noload", and
        # assigning only the relationship doesn't always dirty the column
        # (same guard as update_stock_item).
        item._stock_level_id = stocked.id
        item.stock_level = stocked
        item.stock_level_last_updated = now
    return len(items)
