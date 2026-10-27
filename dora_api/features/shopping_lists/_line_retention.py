"""What happens to shopping-list lines when their anchor is deleted (FU-883).

The rule has two halves, and only one of them can live in the schema:

- **Done lists are receipts and keep their lines.** The FKs are ON DELETE
  SET NULL, and `display_name_snapshot` (frozen at `POST /finish`) keeps the
  orphaned line readable.
- **Draft and shopping lists drop the line entirely.** A line you can no
  longer buy is noise on a list you are about to shop, and those lists carry
  no historic value.

A foreign key cannot express the second half — it can't branch on the parent
list's status — so deletion happens here, before the anchor row goes and the
database applies SET NULL to whatever is left.

Callers: `stock_items.delete_stock_item`, and product delete when batch C
lands. Both pass exactly one of the two ids.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select

from dora_api.domain.entities.product import Product
from dora_api.domain.entities.shopping_list import (
    SHOPPING_LIST_STATUS_DONE, ShoppingList, ShoppingListLine)
from dora_api.domain.entities.stock_item import StockItem
from dora_api.infrastructure.ports import Repository


def prepare_lines_for_anchor_delete(
    repository: Repository,
    *,
    stock_item_id: UUID | None = None,
    product_id: UUID | None = None,
) -> int:
    """Get every line referencing this anchor into a state where losing it is
    safe, then report how many were deleted.

    Two steps, in order:

    1. **Delete** the lines on draft/shopping lists.
    2. **Snapshot** any surviving (done-list) line that still has no name.

    Step 2 is a backstop, not a duplicate of the finish-time snapshot. A list
    can reach `done` without passing through `POST /finish` — the dev seed
    writes finished lists directly, and a restore does too — and such a line
    has no name to fall back on. Nulling its last anchor would then violate
    `ck_shopping_list_line_anchor` and fail the whole delete with a 500. This
    is the last moment the name is still reachable, so it is the right place
    to guarantee the invariant rather than trusting every writer to have done
    it. Finish-time stamping still matters: it captures the name as it was at
    purchase, where this captures it as it is now.

    Does not commit — the caller's `save_changes()` covers this and the anchor
    delete in one transaction, so a failure can't leave the lines deleted but
    the anchor standing.
    """
    if (stock_item_id is None) == (product_id is None):
        raise ValueError("Pass exactly one of stock_item_id / product_id.")

    session = repository.session
    anchor = (
        ShoppingListLine.stock_item_id == stock_item_id
        if stock_item_id is not None
        else ShoppingListLine.product_id == product_id
    )
    active_list_ids = select(ShoppingList.id).where(
        ShoppingList.status != SHOPPING_LIST_STATUS_DONE
    )

    result = session.execute(
        delete(ShoppingListLine).where(
            anchor & ShoppingListLine.shopping_list_id.in_(active_list_ids)
        )
    )
    deleted = result.rowcount or 0

    survivors = list(session.execute(
        select(ShoppingListLine).where(
            anchor & (ShoppingListLine.display_name_snapshot.is_(None))
        )
    ).scalars())
    snapshot_line_display_names(repository, survivors)

    return deleted


def snapshot_line_display_names(repository: Repository, lines) -> None:
    """Freeze each line's display name so it survives losing its anchor.

    Called from `POST /finish`, which is the enforced sole path to `done` and
    already the moment prices are frozen. Applied to **every** line on the
    list, not just the ticked ones: unticked lines stay on a finished list
    too, and they are just as orphanable.

    Idempotent — a line that already carries a snapshot is left alone, so a
    re-finish (or a line finished before this shipped and backfilled since)
    never overwrites the name that was true at purchase time.

    Precedence matches the detail DTO: the stock item names the line when
    there is one, else the product.
    """
    pending = [ln for ln in lines if ln.display_name_snapshot is None]
    if not pending:
        return

    session = repository.session

    stock_item_ids = {ln.stock_item_id for ln in pending if ln.stock_item_id}
    names_by_stock_item: dict[UUID, str] = {}
    if stock_item_ids:
        names_by_stock_item = dict(session.execute(
            select(StockItem.id, StockItem.name).where(
                StockItem.id.in_(stock_item_ids)
            )
        ).all())

    product_ids = {
        ln.product_id for ln in pending
        if ln.product_id and not ln.stock_item_id
    }
    names_by_product: dict[UUID, str] = {}
    if product_ids:
        names_by_product = dict(session.execute(
            select(Product.id, Product.name).where(Product.id.in_(product_ids))
        ).all())

    for line in pending:
        name = None
        if line.stock_item_id:
            name = names_by_stock_item.get(line.stock_item_id)
        if name is None and line.product_id:
            name = names_by_product.get(line.product_id)
        if name is not None:
            line.display_name_snapshot = name[:255]
