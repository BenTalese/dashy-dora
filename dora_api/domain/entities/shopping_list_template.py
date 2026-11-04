"""Templates for shopping lists.

A template is a saved list shape that can be instantiated into a fresh
shopping list (or merged into an existing one). Templates carry no
ticked/archived/primary state — they're just a name + a set of stock
items with default quantities.

A line can carry the same "which one" choice a shopping-list line does: a
picked offer (`selected_product_id`, products installs) or a preferred buy
(`preferred_buy_id`, everyone else). Both are copied onto the new list at
instantiate time, provided they still apply to the item then.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from uuid import UUID

from dora_api.domain.entities.base_entity import BaseEntity


@dataclass
class ShoppingListTemplateLine(BaseEntity):
    template_id: UUID
    # Anchored by a stock item or, for a product-only line, a product.
    stock_item_id: UUID | None = None
    product_id: UUID | None = None
    quantity: int | None = 1
    sequence: int = 0
    selected_product_id: UUID | None = None
    preferred_buy_id: UUID | None = None

    class Fields(BaseEntity.Fields):
        TEMPLATE_ID = "template_id"
        STOCK_ITEM_ID = "stock_item_id"
        PRODUCT_ID = "product_id"
        QUANTITY = "quantity"
        SEQUENCE = "sequence"
        SELECTED_PRODUCT_ID = "selected_product_id"
        PREFERRED_BUY_ID = "preferred_buy_id"


@dataclass
class ShoppingListTemplate(BaseEntity):
    name: str
    created_at: datetime
    updated_at: datetime
    lines: List[ShoppingListTemplateLine] = field(default_factory=list)

    class Fields(BaseEntity.Fields):
        NAME = "name"
        CREATED_AT = "created_at"
        UPDATED_AT = "updated_at"
        LINES = "lines"
