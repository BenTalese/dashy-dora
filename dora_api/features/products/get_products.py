import logging
from dataclasses import dataclass
from uuid import UUID

from flask import request

from dora_api.domain.entities.product import Product
from dora_api.domain.product_offer import discount_percent
from dora_api.features.products.product_links import (has_image_by_product,
                                                      linked_stock_items)
from dora_api.features.routers import PRODUCT_ROUTER
from dora_api.infrastructure.api_response import bad_request, ok, paginated
from dora_api.infrastructure.query_options import (InvalidQueryParameter,
                                                   parse_query_options)
from dora_api.persistence.field import EntityField
from dora_api.persistence.page import Page
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


# Non-frozen so we can stamp `linked_stock_item_*` on after the page comes
# back. Cheaper than re-running pagination through a richer entity load,
# and keeps `from_entity` honest about what's straight from the Product row.
@dataclass(slots=True)
class ProductDto:
    brand: str | None
    # bytes never travel in list/detail JSON. SPA fetches via
    # `GET /products/<id>/image`. Mirrors stock-item / recipe pattern.
    has_image: bool
    is_active: bool
    # OD-2 — hand-entered. The SPA marks these so a user can tell at a glance
    # which prices Dora maintains and which are their own.
    is_custom: bool
    is_available: bool
    store_id: UUID
    store_name: str
    # `merchant_stockcode` is the producer's SKU, kept
    # verbatim per the rename runbook.
    merchant_stockcode: str | None
    name: str
    pack_count: int | None
    price_now: float
    price_was: float
    product_id: UUID
    size: str
    size_unit: str
    size_value: float
    web_url: str | None
    # Stamped in `GetProductsHandler.handle` after pagination. A product is
    # one stock item's responsibility (StockItemProduct's PK is (stock_item,
    # product)), but we keep it nullable for orphan products and for the
    # "unlinked" state.
    linked_stock_item_id: UUID | None = None
    linked_stock_item_name: str | None = None

    @classmethod
    def from_entity(cls, product: Product) -> 'ProductDto':
        # `has_image` is stamped in bulk by `stamp_has_image` so we don't
        # trigger the deferred image-blob load per row (N+1).
        return ProductDto(
            brand = product.brand,
            has_image = False,
            is_active = product.is_active,
            is_custom = product.is_custom,
            is_available = product.is_available,
            store_id = product.store.id,
            store_name = product.store.name,
            merchant_stockcode = product.merchant_stockcode,
            name = product.name,
            pack_count = product.pack_count,
            price_now = product.current_offer.price_now,
            price_was = product.current_offer.price_was,
            product_id = product.id,
            size = product.size,
            size_unit = product.size_unit,
            size_value = product.size_value,
            web_url = product.web_url,
        )


_FIELD_MAP: dict[str, EntityField] = {
    "product_id": EntityField(Product, "id"),
    "store_id": EntityField(Product, "_store_id"),
}


def stamp_has_image(repository, dtos: list[ProductDto]) -> None:
    """FU-014 — bulk-derive `has_image` from a single `image IS NOT NULL`
    pass that never touches the deferred image blob. Mirrors the
    stock-item / recipe pattern.
    """
    flag_by_id = has_image_by_product(repository, [p.product_id for p in dtos])
    for dto in dtos:
        dto.has_image = flag_by_id.get(dto.product_id, False)


def stamp_linked_stock_items(repository, dtos: list[ProductDto]) -> None:
    """Stamp `linked_stock_item_*` on each DTO in place via the m2m join.

    Shared by the products list and the deals-email pool so the enrichment
    lives in one place; the join itself is `product_links.linked_stock_items`
    (also read by the price_drop alert).
    """
    links = linked_stock_items(repository, [p.product_id for p in dtos])
    for dto in dtos:
        link = links.get(dto.product_id)
        if link is None:
            continue
        dto.linked_stock_item_id = link.stock_item_id
        dto.linked_stock_item_name = link.name


class GetProductsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, options) -> Page[ProductDto]:
        page = (
            self.repository
            .get(Product)
            .include(Product.Fields.CURRENT_OFFER)
            .include(Product.Fields.STORE)
            .paginate(options, ProductDto.from_entity, field_map=_FIELD_MAP)
        )
        stamp_has_image(self.repository, page.items)
        stamp_linked_stock_items(self.repository, page.items)
        return page


class GetBestDealsHandler:
    """Top-N active products currently on special, ranked by discount %, with
    the one `discount_percent` rule (R-003). The weekly deals email's pool."""
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, limit: int) -> list[ProductDto]:
        products = (
            self.repository
            .get(Product)
            .include(Product.Fields.CURRENT_OFFER)
            .include(Product.Fields.STORE)
            .all()
        )
        scored: list[tuple[int, Product]] = []
        for product in products:
            offer = product.current_offer
            if not product.is_active or offer is None:
                continue
            pct = discount_percent(offer.price_now, offer.price_was)
            if pct is None:
                continue
            scored.append((pct, product))
        # Highest discount first; matches the client's old discount-% sort.
        scored.sort(key=lambda t: t[0], reverse=True)
        dtos = [ProductDto.from_entity(p) for _, p in scored[:limit]]
        stamp_has_image(self.repository, dtos)
        stamp_linked_stock_items(self.repository, dtos)
        return dtos


@PRODUCT_ROUTER.route("")
def get_products():
    try:
        _Options = parse_query_options(request.args)
        _Page = GetProductsHandler(SqlAlchemyRepository()).handle(_Options)
    except InvalidQueryParameter as exc:
        return bad_request(str(exc))
    _LOGGER.info(f"Retrieved {len(_Page.items)} of {_Page.total} products.")
    return paginated(_Page.items, _Page.total, _Page.page, _Page.limit)
