import logging
from dataclasses import dataclass
from typing import List
from uuid import UUID

from dora_api.domain.entities.recipe_ingredient import RecipeIngredient
from dora_api.domain.entities.shopping_list import ShoppingListLine
from dora_api.domain.entities.shopping_list_template import ShoppingListTemplateLine
from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.infrastructure.api_response import no_content, not_found
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class UnlinkProductResponse:
    stock_item_not_found: bool = False
    link_not_found: bool = False


class UnlinkProductFromStockItemHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, stock_item_id: UUID, product_id: UUID) -> UnlinkProductResponse:
        _StockItem = (
            self.repository
            .get(StockItem)
            .include(StockItem.Fields.PRODUCTS)
            .one(EntityField(StockItem, "id").eq(stock_item_id))
        )
        if not _StockItem:
            return UnlinkProductResponse(stock_item_not_found = True)

        # Find the linked product on the in-memory collection and remove it.
        # SQLAlchemy turns the removal into a DELETE on the m2m table.
        _Match = next((p for p in (_StockItem.products or []) if p.id == product_id), None)
        if _Match is None:
            return UnlinkProductResponse(link_not_found = True)

        _StockItem.products.remove(_Match)

        # Any live shopping-list line pointing at this product as its chosen
        # offer is now pointing at something that is no longer on the menu, so
        # the selection is cleared here — at the moment the fact changes.
        #
        # This is what "Refresh deals" used to do, on demand, from a toolbar
        # button (removed 2026-09-17). Two things were wrong with that: the
        # button's name promised fresh prices it never fetched, and a user had
        # to know to press it. The detail read has always resolved each line's
        # offer from the *currently linked* products and fallen back to the
        # cheapest, so the list was never actually showing a dead deal — the
        # stale column was invisible bookkeeping. Cleaning it at the source
        # means it also can't come back to life if the same product is linked
        # again later, which the button could not have prevented either.
        _Lines: List[ShoppingListLine] = self.repository.get(ShoppingListLine).all(
            EntityField(ShoppingListLine, "selected_product_id").eq(product_id)
            & EntityField(ShoppingListLine, "stock_item_id").eq(stock_item_id)
        )
        for line in _Lines:
            line.selected_product_id = None
        # Template lines carry the same choice, and the same rule holds.
        _TemplateLines: List[ShoppingListTemplateLine] = self.repository.get(ShoppingListTemplateLine).all(
            EntityField(ShoppingListTemplateLine, ShoppingListTemplateLine.Fields.SELECTED_PRODUCT_ID).eq(product_id)
            & EntityField(ShoppingListTemplateLine, ShoppingListTemplateLine.Fields.STOCK_ITEM_ID).eq(stock_item_id)
        )
        for template_line in _TemplateLines:
            template_line.selected_product_id = None
        # So do recipe ingredients. A product links to exactly one stock item
        # (`uq_stock_item_product_product_id`), so the product id alone is enough.
        _Ingredients: List[RecipeIngredient] = self.repository.get(RecipeIngredient).all(
            EntityField(RecipeIngredient, RecipeIngredient.Fields.SELECTED_PRODUCT_ID).eq(product_id)
        )
        for ingredient in _Ingredients:
            ingredient.selected_product_id = None

        self.repository.save_changes()
        return UnlinkProductResponse()


@STOCK_ITEM_ROUTER.route("<uuid:stock_item_id>/products/<uuid:product_id>", methods=["DELETE"])
def unlink_product_from_stock_item(stock_item_id: UUID, product_id: UUID):
    # The `uuid` converter hands both ids over as UUIDs (R-033).
    _Handler = UnlinkProductFromStockItemHandler(SqlAlchemyRepository())
    _Response = _Handler.handle(stock_item_id, product_id)

    if _Response.stock_item_not_found:
        return not_found(StockItem.__name__, stock_item_id)
    if _Response.link_not_found:
        # 204 is also reasonable for "no link to delete" but we surface 404
        # so a stale client can tell the difference between "link removed"
        # and "link never existed".
        return not_found("StockItemProduct link", product_id)

    _LOGGER.info("Unlinked product %s from stock item %s", product_id, stock_item_id)
    return no_content()
