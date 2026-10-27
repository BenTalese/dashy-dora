from dataclasses import dataclass
from datetime import datetime

from dora_api.domain.entities.base_entity import BaseEntity


# Historic offers live in their own table rather than beside the current offer:
# mapping both onto one table made the current offer fail to update at times.


@dataclass
class ProductHistoricOffer(BaseEntity):
    offered_on: datetime
    price_now: float
    price_was: float
    # PROPOSAL_INGESTION_API §2.4 — provenance for every historic point.
    # Nullable for points pre-dating C-10 / direct `create_product`
    # writes; ingest records always carry it.
    source: str | None = None

    class Fields(BaseEntity.Fields):
        OFFERED_ON = "offered_on"
        PRICE_NOW = "price_now"
        PRICE_WAS = "price_was"
        SOURCE = "source"
