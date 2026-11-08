"""Restock: a bought item goes to its Stocked level.

Ticking a line on an active list restocks its item and unticking puts the old
level back (UX v5 D1). `POST /finish` restocks only lines ticked before that
existed. One writer so the paths can't disagree about what buying means.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

from dora_api.domain.entities.shopping_list import ShoppingList, ShoppingListLine
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


def _restocked_sibling(
    repository: Repository, line: ShoppingListLine,
) -> ShoppingListLine | None:
    """Another line on the same list whose tick restocked the same item. A
    nested product line shares its parent's `stock_item_id`, so an item can be
    ticked twice on one list; the item has one pre-tick level, and every line
    ticked for it carries that same snapshot."""
    siblings = repository.get(ShoppingListLine).all(
        EntityField(ShoppingListLine, "shopping_list_id").eq(line.shopping_list_id)
        & EntityField(ShoppingListLine, "stock_item_id").eq(line.stock_item_id)
    )
    return next(
        (s for s in siblings if s.id != line.id and s.restocked_at is not None),
        None,
    )


def _utc_naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def _same_instant(a: datetime | None, b: datetime | None) -> bool:
    """The tick writes one `now` to both the item and the line, so an
    untouched item matches its line exactly. SQLite hands datetimes back naive
    (UTC) and Postgres aware, so both are compared as naive UTC."""
    if a is None or b is None:
        return False
    return _utc_naive(a) == _utc_naive(b)


def restock_line(repository: Repository, line: ShoppingListLine, *, now: datetime) -> None:
    """A tick on an active list: restock the line's item and record what its
    level was, so `restore_line` can put it back. When another line on the list
    already restocked the item, this one shares that snapshot instead of
    taking a second (which would record Stocked as the level to go back to).
    No-op for a product-only line or one already restocked. The caller owns
    the commit."""
    if line.stock_item_id is None or line.restocked_at is not None:
        return
    sibling = _restocked_sibling(repository, line)
    if sibling is not None:
        line.restock_from_level_id = sibling.restock_from_level_id
        line.restock_from_level_updated_at = sibling.restock_from_level_updated_at
        line.restocked_at = sibling.restocked_at
        return
    item: StockItem | None = (
        repository.get(StockItem)
        .include(StockItem.Fields.STOCK_LEVEL)
        .by_id(line.stock_item_id)
    )
    if item is None:
        return
    line.restock_from_level_id = item.stock_level.id if item.stock_level else None
    line.restock_from_level_updated_at = item.stock_level_last_updated
    line.restocked_at = now
    restock_stock_items(repository, [line.stock_item_id], now=now)


def restore_line(repository: Repository, line: ShoppingListLine) -> None:
    """An untick: put the item's level and timestamp back to what they were
    before the tick restocked it. Leaves the item alone when another ticked
    line on the list still holds the restock, or when the level has moved
    since the tick (a hand edit, another list's finish): undoing a tick must
    not undo something else. No-op when the tick didn't restock. The caller
    owns the commit."""
    if line.restocked_at is None:
        return
    if line.stock_item_id is not None and _restocked_sibling(repository, line) is None:
        item: StockItem | None = repository.get(StockItem).by_id(line.stock_item_id)
        if item is not None and _same_instant(item.stock_level_last_updated, line.restocked_at):
            level = (
                repository.get(StockLevel).by_id(line.restock_from_level_id)
                if line.restock_from_level_id is not None else None
            )
            item._stock_level_id = level.id if level else None
            item.stock_level = level
            if line.restock_from_level_updated_at is not None:
                item.stock_level_last_updated = line.restock_from_level_updated_at
    line.restocked_at = None
    line.restock_from_level_id = None
    line.restock_from_level_updated_at = None


def release_lines(repository: Repository, lines: Iterable[ShoppingListLine]) -> None:
    """Lines about to be deleted from an active list give their restock back,
    exactly as an untick would: a line removed from the list was not bought.
    A done list's lines are a receipt and keep theirs. The caller removes the
    lines and owns the commit."""
    for line in lines:
        if line.restocked_at is None:
            continue
        parent = repository.get(ShoppingList).by_id(line.shopping_list_id)
        if parent is not None and parent.is_active:
            restore_line(repository, line)
