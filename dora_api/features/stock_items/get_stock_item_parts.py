"""Slices of the stock-item detail that other surfaces need on their own.

The recipe page (substitutes per missing ingredient), cook mode's swap picker,
the price-entry dialogs and the recipe ingredient editor each read one feed of
the item. They used to pull the whole detail DTO (nine feeds, about fifteen
queries) per call; these serve the one slice through the same builders the
detail handler uses (finalisation 06-R10).

  GET /api/stock-items/<id>/substitutes          — {items: [SubstituteDto]}
  GET /api/stock-items/<id>/price-entry-prefill  — {prefill: PriceEntryPrefillDto | null}
  GET /api/stock-items/<id>/buy-choices          — {preferred_buys: [...], products: [...]}
"""
from uuid import UUID

from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.features.stock_items.get_stock_item_detail import (
    build_linked_products, build_preferred_buys, build_price_entry_prefill,
    build_substitutes, load_stock_item_with_products,
)
from dora_api.infrastructure.api_response import not_found, ok
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


@STOCK_ITEM_ROUTER.route("<uuid:stock_item_id>/substitutes", methods=["GET"])
def get_stock_item_substitutes(stock_item_id: UUID):
    repo = SqlAlchemyRepository()
    if not repo.get(StockItem).exists(stock_item_id):
        return not_found(StockItem.__name__, stock_item_id)
    return ok({"items": build_substitutes(repo, stock_item_id)})


@STOCK_ITEM_ROUTER.route("<uuid:stock_item_id>/price-entry-prefill", methods=["GET"])
def get_stock_item_price_entry_prefill(stock_item_id: UUID):
    repo = SqlAlchemyRepository()
    if not repo.get(StockItem).exists(stock_item_id):
        return not_found(StockItem.__name__, stock_item_id)
    return ok({"prefill": build_price_entry_prefill(repo, stock_item_id)})


@STOCK_ITEM_ROUTER.route("<uuid:stock_item_id>/buy-choices", methods=["GET"])
def get_stock_item_buy_choices(stock_item_id: UUID):
    repo = SqlAlchemyRepository()
    stock_item = load_stock_item_with_products(repo, stock_item_id)
    if stock_item is None:
        return not_found(StockItem.__name__, stock_item_id)
    return ok({
        "preferred_buys": build_preferred_buys(repo, stock_item_id),
        "products": build_linked_products(stock_item),
    })
