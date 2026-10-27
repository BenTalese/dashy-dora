import logging
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from dora_api.domain.entities.product import Product
from dora_api.domain.entities.shopping_list import (SHOPPING_LIST_STATUS_DONE,
                                                    ShoppingList,
                                                    ShoppingListLine)
from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.infrastructure.api_response import (entity_existence_failure,
                                                  no_content, not_found)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import (field_of, get_request_body)
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


class LinkProductRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID


@dataclass(slots=True)
class LinkProductResponse:
    stock_item_not_found: bool = False
    product_not_found: bool = False
    already_linked: bool = False


class LinkProductToStockItemHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, stock_item_id: UUID, request: LinkProductRequest) -> LinkProductResponse:
        _StockItem = (
            self.repository
            .get(StockItem)
            .include(StockItem.Fields.PRODUCTS)
            .one(EntityField(StockItem, "id").eq(stock_item_id))
        )
        if not _StockItem:
            return LinkProductResponse(stock_item_not_found = True)

        _Product = self.repository.get(Product).by_id(request.product_id)
        if not _Product:
            return LinkProductResponse(product_not_found = True)

        # Idempotent: re-linking is a no-op rather than an error. Lets the
        # frontend retry without worrying about double-link errors.
        existing_ids = {p.id for p in (_StockItem.products or [])}
        if _Product.id in existing_ids:
            return LinkProductResponse(already_linked = True)

        _StockItem.products.append(_Product)

        # any standalone-product line on a
        # NOT-DONE list anchored on this product gets upgraded to
        # nest under a stock-item line for this item. Two paths:
        #   - the list already has a stock-item line for this item:
        #     fold the product anchor into that line (set its
        #     product_id, drop the orphan).
        #   - no stock-item line yet: convert the orphan in place by
        #     setting `stock_item_id` (still keeping `product_id`).
        # Either way the SPA gets a single nested row instead of two
        # disconnected rows next time it refreshes.
        orphan_lines = [
            line for line in self.repository.get(ShoppingListLine).all(
                EntityField(ShoppingListLine, "product_id").eq(_Product.id)
            )
            if line.stock_item_id is None  # a nested line is already fine
        ]
        # The parent lists and this item's plain lines on them, once each
        # rather than per orphan.
        list_ids = list({line.shopping_list_id for line in orphan_lines})
        open_list_ids = {
            lst.id for lst in (
                self.repository.get(ShoppingList).all(EntityField(ShoppingList, "id").in_(list_ids))
                if list_ids else []
            )
            if lst.status != SHOPPING_LIST_STATUS_DONE  # finished lists are history
        }
        stock_line_by_list = {
            line.shopping_list_id: line for line in (
                self.repository.get(ShoppingListLine).all(
                    EntityField(ShoppingListLine, "shopping_list_id").in_(list(open_list_ids))
                    & EntityField(ShoppingListLine, "stock_item_id").eq(_StockItem.id)
                    & EntityField(ShoppingListLine, "product_id").is_null()
                ) if open_list_ids else []
            )
        }
        for orphan in orphan_lines:
            if orphan.shopping_list_id not in open_list_ids:
                continue
            existing_stock_line = stock_line_by_list.get(orphan.shopping_list_id)
            if existing_stock_line is not None:
                # Fold: keep the stock line, set its product anchor,
                # drop the orphan.
                existing_stock_line.product_id = _Product.id
                self.repository.remove(orphan)
            else:
                # Convert in place — orphan keeps `product_id` and
                # gains `stock_item_id`, becoming a single nested row.
                orphan.stock_item_id = _StockItem.id

        self.repository.save_changes()
        return LinkProductResponse()


@STOCK_ITEM_ROUTER.route("<uuid:stock_item_id>/products", methods=["POST"])
@has_request_body(LinkProductRequest)
def link_product_to_stock_item(stock_item_id: UUID):
    _Handler = LinkProductToStockItemHandler(SqlAlchemyRepository())
    _Request: LinkProductRequest = get_request_body()
    _Response = _Handler.handle(stock_item_id, _Request)

    if _Response.stock_item_not_found:
        return not_found(StockItem.__name__, stock_item_id)
    if _Response.product_not_found:
        return entity_existence_failure(
            Product.__name__,
            field_of(LinkProductRequest, 'product_id'),
            _Request.product_id,
        )

    _LOGGER.info(
        "Linked product %s to stock item %s%s",
        _Request.product_id,
        stock_item_id,
        " (already linked)" if _Response.already_linked else "",
    )
    return no_content()
