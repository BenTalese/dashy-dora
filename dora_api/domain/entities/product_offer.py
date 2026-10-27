from dataclasses import dataclass
from datetime import datetime

from dora_api.domain.entities.base_entity import BaseEntity


@dataclass
class ProductOffer(BaseEntity):
    offered_on: datetime
    price_now: float
    price_was: float

    class Fields(BaseEntity.Fields):
        OFFERED_ON = "offered_on"
        PRICE_NOW = "price_now"
        PRICE_WAS = "price_was"
