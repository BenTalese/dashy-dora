from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from dora_api.domain.entities.base_entity import BaseEntity


@dataclass
class PriceAlert(BaseEntity):
    """Per-user "tell me when this product hits this price" watch. It fires
    as the `price_drop` alert, once per offer that crosses the threshold (the
    alert's episode key), so the row carries no fired-at state."""
    user_id: UUID
    product_id: UUID
    threshold_unit_price: float
    created_at: datetime

    class Fields(BaseEntity.Fields):
        USER_ID = "user_id"
        PRODUCT_ID = "product_id"
        THRESHOLD_UNIT_PRICE = "threshold_unit_price"
        CREATED_AT = "created_at"
