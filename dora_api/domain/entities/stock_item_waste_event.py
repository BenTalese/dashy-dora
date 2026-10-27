from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from dora_api.domain.entities.base_entity import BaseEntity


# Sentinel reasons — plain str so SQLAlchemy stores varchar, matching the
# SHOPPING_LIST_STATUS_* sentinels on ShoppingList. Anything outside this set is
# rejected at the request layer (the entity itself stays permissive so a
# future reason added in a newer install doesn't blow up an older API).
WASTE_REASON_EXPIRED = "expired"
WASTE_REASON_SPOILED = "spoiled"
WASTE_REASON_DID_NOT_LIKE = "did_not_like"
WASTE_REASON_OVERBOUGHT = "overbought"
WASTE_REASON_OTHER = "other"

WASTE_REASON_VALUES = {
    WASTE_REASON_EXPIRED,
    WASTE_REASON_SPOILED,
    WASTE_REASON_DID_NOT_LIKE,
    WASTE_REASON_OVERBOUGHT,
    WASTE_REASON_OTHER,
}


@dataclass
class StockItemWasteEvent(BaseEntity):
    """C-waste — append-only log of food the household discarded.

    The capture flow is a single tile-tap from the StockItemRow expiry
    dropdown (PROPOSAL_WASTE_MINIMISATION §5): reason only, no value,
    no quantity, no note. The signal exists so the future Dora Score
    can read it; the surface is deliberately tiny.

    `stock_item_name` is denormalised so insights survive a stock item
    being renamed or deleted. The FK is SET NULL on delete; we keep the
    history rather than cascade-deleting it.
    """
    stock_item_id: UUID | None
    stock_item_name: str
    reason: str
    occurred_at: datetime

    class Fields(BaseEntity.Fields):
        STOCK_ITEM_ID = "stock_item_id"
        STOCK_ITEM_NAME = "stock_item_name"
        REASON = "reason"
        OCCURRED_AT = "occurred_at"
