"""Bulk product reads shared by the product list, reports and alerts: the
linked stock item (the `StockItemProduct` join) and whether a product has an
image.

`StockItemProduct.UNIQUE(product_id)` means a product links to at most one
stock item, so the answer is a plain mapping. One bulk pass over the join,
then a single StockItem fetch for the names — the shape the products list has
always used, lifted here so the alerts feed (price_drop's add-to-list) reads
the same link rather than a fourth copy of the query (R-003).
"""
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select

from dora_api.app import db
from dora_api.domain.entities.stock_item import StockItem
from dora_api.persistence.field import EntityField


@dataclass(frozen=True)
class LinkedStockItem:
    stock_item_id: UUID
    name: str | None


def linked_stock_items(repository, product_ids: list[UUID]) -> dict[UUID, LinkedStockItem]:
    """`{product_id: LinkedStockItem}` for every product in `product_ids` that
    is linked; unlinked products are absent."""
    if not product_ids:
        return {}
    assoc = db.metadata.tables["StockItemProduct"]
    rows = repository.session.execute(
        select(assoc.c.product_id, assoc.c.stock_item_id)
        .where(assoc.c.product_id.in_(product_ids))
    ).all()
    product_to_stock: dict[UUID, UUID] = {row[0]: row[1] for row in rows}
    stock_ids = list(set(product_to_stock.values()))
    names: dict[UUID, str] = {}
    if stock_ids:
        items = repository.get(StockItem).all(
            EntityField(StockItem, "id").in_(stock_ids)
        )
        names = {s.id: s.name for s in items}
    return {
        pid: LinkedStockItem(stock_item_id = sid, name = names.get(sid))
        for pid, sid in product_to_stock.items()
    }


def has_image_by_product(repository, product_ids: list[UUID]) -> dict[UUID, bool]:
    """`{product_id: has_image}` from one `image IS NOT NULL` pass that never
    loads the deferred image blob (FU-014)."""
    if not product_ids:
        return {}
    product_table = db.metadata.tables["Product"]
    rows = repository.session.execute(
        select(product_table.c.id, product_table.c.image.isnot(None))
        .where(product_table.c.id.in_(product_ids))
    ).all()
    return {row[0]: bool(row[1]) for row in rows}
