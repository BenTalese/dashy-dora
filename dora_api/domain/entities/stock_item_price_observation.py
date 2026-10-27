from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from dora_api.domain.entities.base_entity import BaseEntity


@dataclass
class StockItemPriceObservation(BaseEntity):
    """A single "what this cost me" price point on a stock item — the everyday
    price-history substrate (PROPOSAL_PRODUCTS_AS_OVERLAY §3.2 / FU-227 chunk 2).

    **Folded shape (A1 ratified 2026-06-22):** the user logs the TOTAL price
    they paid + the TOTAL measure they got + the unit. Per-unit cost is
    derived server-side (``get_stock_item_unit_cost_with_unit_at``); the client never
    divides (R-003). Count is *not* stored — it's a UI input that contributes
    to ``total_measure`` and ``total_price`` at entry time (cleaner canonical
    truth; no "two 12-packs vs one 24-pack" ambiguity — see plan §6a).

    **Provenance via FK, not enum (A4 revised):** when harvested from a
    completed shopping line, ``shopping_list_line_id`` points at that line
    (ON DELETE SET NULL — provenance only, not a sync link per LC-4). When
    typed manually, the FK is null. Partial UNIQUE on the FK (per LC-1)
    makes harvest idempotent under finish-button double-taps. The old
    ``source`` enum field is gone — the FK carries strictly more info.

    **Optional store_id (A2):** populated when the user picks a store on the
    shelf-price widget, or carried over from a shopping list's store at
    harvest. Lets the widget surface "Last seen at Coles" without a separate
    `usual_store` lookup. ON DELETE SET NULL.

    Gated by the money/spend feature at the surfaces (the UI), not by
    Products. Ingestion **never** writes observations (chunk 7 — observations
    are an in-app user-input substrate only).
    """
    stock_item_id: UUID
    total_price: float          # what the user paid in total
    total_measure: float        # how much they got, in `unit`
    unit: str                   # member of the supported list (domain/units.py)
    observed_at: datetime
    store_id: UUID | None
    shopping_list_line_id: UUID | None
    created_at: datetime
    # Multipack count (FU-227 follow-up). ``total_measure`` keeps the existing
    # convention of being the TOTAL the user got — for a "$4.20 for 4 × 125g"
    # purchase that's `500.0`. ``pack_count`` captures the "4" so the obs
    # list can render "4 × 125g" instead of "500g flat" without losing the
    # multipack context. None ⇒ single pack / free-weight (the common case).
    # Per-unit cost, baseline and sidecar read only total_price /
    # total_measure. The one reader of pack_count is recipe costing, which
    # needs the price of one item to bill a bare "3 eggs" (FU-856).
    pack_count: int | None = None

    class Fields(BaseEntity.Fields):
        STOCK_ITEM_ID = "stock_item_id"
        TOTAL_PRICE = "total_price"
        TOTAL_MEASURE = "total_measure"
        UNIT = "unit"
        OBSERVED_AT = "observed_at"
        STORE_ID = "store_id"
        SHOPPING_LIST_LINE_ID = "shopping_list_line_id"
        CREATED_AT = "created_at"
        PACK_COUNT = "pack_count"
