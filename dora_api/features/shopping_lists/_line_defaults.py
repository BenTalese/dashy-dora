"""What a new shopping-list line starts with, before the user touches it.

Every path that writes a fresh line for a stock item comes through here: the
row-level add, quick-add, auto-generate and the low-stock trigger. They used to
set these fields (or not) one by one, which is how quick-add ended up the only
path that never prefilled the item's usual store.

The rule is "what you chose last time" (owner, 2026-09-27: *"if I last bought
Vitasoy oat milky for milk I'd expect that to be there when I add milk
again"*). The most recent earlier line for the same item is the memory: its
preferred buy and its picked offer carry over, provided they still exist. A
line where the user had cleared the choice carries nothing, so clearing it is
remembered too.

R-003: one place decides a new line's defaults, not one per add path.
"""
from typing import Dict, List

from dora_api.domain.entities.preferred_buy import PreferredBuy
from dora_api.domain.entities.product import Product
from dora_api.domain.entities.shopping_list import ShoppingListLine
from dora_api.domain.entities.stock_item import StockItem
from dora_api.persistence.field import EntityField
from dora_api.infrastructure.ports import Repository


def apply_line_defaults(repository: Repository, lines: List[ShoppingListLine]) -> None:
    """Prefill planned store, preferred buy and picked offer on new lines.

    Call before the lines are added to the repository. A field the caller has
    already set is never overwritten; a caller that knows the store says so.

    Store precedence: the remembered offer's store (picking an offer *is*
    picking where you buy it), else the item's usual store.
    """
    targets = [l for l in lines if l.stock_item_id is not None]
    if not targets:
        return
    item_ids = list({l.stock_item_id for l in targets})

    items: Dict = {
        s.id: s
        for s in repository.get(StockItem).all(EntityField(StockItem, "id").in_(item_ids))
    }

    latest: Dict = {}
    for prior in repository.get(ShoppingListLine).all(
        EntityField(ShoppingListLine, ShoppingListLine.Fields.STOCK_ITEM_ID).in_(item_ids)
    ):
        if prior.added_at is None:
            continue
        current = latest.get(prior.stock_item_id)
        if current is None or prior.added_at > current.added_at:
            latest[prior.stock_item_id] = prior

    live_preferred_buys = {
        pb.id
        for pb in repository.get(PreferredBuy).all(
            EntityField(PreferredBuy, PreferredBuy.Fields.STOCK_ITEM_ID).in_(item_ids)
        )
    }
    # A line's `selected_product_id` is always a currently linked product:
    # unlinking clears it on every line of the item at the source
    # (`unlink_product_from_stock_item`). So the remembered id needs no link
    # check here — only the product itself, for its store.
    # A caller may arrive with its own pick (a recipe ingredient's product);
    # its store is loaded alongside the remembered ones.
    product_ids = list({
        p.selected_product_id for p in [*latest.values(), *targets] if p.selected_product_id
    })
    # R-032 — the store is read off the FK column (`_store_id`), not the
    # noload `store` relationship: a Product already in the session (e.g. the
    # caller's own pick) comes back from the identity map without it, even
    # with `.include(STORE)`.
    products: Dict = {}
    if product_ids:
        products = {
            p.id: p
            for p in repository.get(Product).all(EntityField(Product, "id").in_(product_ids))
        }

    for line in targets:
        item = items.get(line.stock_item_id)
        prior = latest.get(line.stock_item_id)
        if prior is not None:
            if line.preferred_buy_id is None and prior.preferred_buy_id in live_preferred_buys:
                line.preferred_buy_id = prior.preferred_buy_id
            product = products.get(prior.selected_product_id)
            if line.selected_product_id is None and product is not None:
                line.selected_product_id = product.id
                if line.planned_store_id is None:
                    line.planned_store_id = product._store_id
        picked = products.get(line.selected_product_id)
        if line.planned_store_id is None and picked is not None:
            line.planned_store_id = picked._store_id
        if line.planned_store_id is None and item is not None:
            line.planned_store_id = item.usual_store_id
