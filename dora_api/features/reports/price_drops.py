"""GET /api/reports/price-drops?limit=N: tracked products whose current offer
is a genuine new all-time low against their historic offers."""

from dataclasses import asdict, dataclass
from typing import Dict
from uuid import UUID

from flask import request
from sqlalchemy import select

from dora_api.persistence.aware import as_utc
from dora_api.domain.entities.product import Product
from dora_api.domain.entities.product_historic_offer import ProductHistoricOffer
from dora_api.features.routers import REPORTS_ROUTER
from dora_api.infrastructure.api_response import ok
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.features.products.product_links import (
    has_image_by_product, linked_stock_items)


# R-005 carve-out: multi-table aggregates are Core `select()` over the mapped
# classes, not repository walks (the documented reports pattern).

# ───── 7. Price drops (new-low) ───────────────────────────────────────────

@dataclass(slots=True)
class PriceDropRow:
    product_id: UUID
    name: str
    store_id: UUID | None
    store_name: str
    has_image: bool
    price_now: float
    previous_low: float
    drop_amount: float
    drop_percent: int
    linked_stock_item_id: UUID | None
    linked_stock_item_name: str | None


class PriceDropsHandler:
    """Active products whose current offer is strictly below every prior
    historic price on record — Honesty (§2.4): the claim "new low" must be
    true, not "cheapest right now". Ranked by drop percent, sliced server-side
    (state-ownership §8.2)."""

    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, limit: int) -> list[PriceDropRow]:
        products = (
            self.repository
            .get(Product)
            .include(Product.Fields.CURRENT_OFFER)
            .include(Product.Fields.STORE)
            .all()
        )
        active = [p for p in products if p.is_active and p.current_offer is not None]
        if not active:
            return []

        product_ids = [p.id for p in active]
        # "Prior" means observed before the current offer. Every offer path
        # (ingest, create, edit) appends the current price to the history as
        # well, so a low taken over all of it always included the current
        # price and no product could ever read as a new low.
        current_since = {p.id: as_utc(p.current_offer.offered_on) for p in active}
        session = self.repository.session
        historic_rows = session.execute(
            select(
                ProductHistoricOffer._product_id,  # noqa: SLF001
                ProductHistoricOffer.price_now,
                ProductHistoricOffer.offered_on,
            ).where(ProductHistoricOffer._product_id.in_(product_ids))
        ).all()
        prev_low_by_product: Dict[UUID, float] = {}
        for pid, price_now, offered_on in historic_rows:
            if price_now is None or offered_on is None:
                continue
            since = current_since.get(pid)
            if since is not None and as_utc(offered_on) >= since:
                continue
            price = float(price_now)
            existing = prev_low_by_product.get(pid)
            if existing is None or price < existing:
                prev_low_by_product[pid] = price

        rows: list[PriceDropRow] = []
        for product in active:
            prev_low = prev_low_by_product.get(product.id)
            # No prior history → the current price can't be a "new low" —
            # it's the only price we've seen. Skip.
            if prev_low is None or prev_low <= 0:
                continue
            current = float(product.current_offer.price_now)
            if current <= 0 or current >= prev_low:
                continue
            drop_amount = round(prev_low - current, 2)
            drop_percent = int(round((prev_low - current) / prev_low * 100))
            rows.append(PriceDropRow(
                product_id=product.id,
                name=product.name,
                store_id=product.store.id if product.store else None,
                store_name=product.store.name if product.store else "Unknown",
                has_image=False,
                price_now=current,
                previous_low=round(prev_low, 2),
                drop_amount=drop_amount,
                drop_percent=drop_percent,
                linked_stock_item_id=None,
                linked_stock_item_name=None,
            ))
        rows.sort(key=lambda r: (r.drop_percent, r.drop_amount), reverse=True)
        rows = rows[:limit]

        # Stamp has_image + linked_stock_item_* against the sliced set only,
        # so we never load the deferred image blob for the unsliced tail.
        sliced_ids = [r.product_id for r in rows]
        has_image = has_image_by_product(self.repository, sliced_ids)
        links = linked_stock_items(self.repository, sliced_ids)
        for row in rows:
            row.has_image = has_image.get(row.product_id, False)
            link = links.get(row.product_id)
            if link is not None:
                row.linked_stock_item_id = link.stock_item_id
                row.linked_stock_item_name = link.name
        return rows


@REPORTS_ROUTER.route("/price-drops", methods=["GET"])
def price_drops():
    try:
        _Limit = max(1, min(int(request.args.get("limit", "5")), 20))
    except (TypeError, ValueError):
        _Limit = 5
    _Rows = PriceDropsHandler(SqlAlchemyRepository()).handle(_Limit)
    return ok({"rows": [asdict(r) for r in _Rows]})
