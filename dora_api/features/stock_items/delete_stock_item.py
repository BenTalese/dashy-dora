from dataclasses import dataclass
import logging
from uuid import UUID

from dora_api.domain.entities.recipe_ingredient import RecipeIngredient
from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.features.shopping_lists._line_retention import \
    prepare_lines_for_anchor_delete
from dora_api.infrastructure.api_response import no_content, not_found
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DeleteStockItemResponse:
    stock_item_not_found: bool = False


class DeleteStockItemHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, stock_item_id: UUID) -> DeleteStockItemResponse:
        _StockItem = self.repository.get(StockItem).by_id(stock_item_id)

        if not _StockItem:
            return DeleteStockItemResponse(stock_item_not_found = True)

        # Recipe ingredients on this item become free text rather than
        # blocking the delete (owner, 2026-11-10). The row keeps its quantity,
        # unit, notes and step links; its anchor moves to `raw_text`, which the
        # `recipe_ingredient_anchor` CHECK accepts on its own. The item's
        # buys and products go with it, so the choice fields are cleared too.
        # Flushed before the delete: the FK is ON DELETE RESTRICT.
        _Ingredients: list[RecipeIngredient] = (
            self.repository.get(RecipeIngredient)
            .all(EntityField(RecipeIngredient, "_stock_item_id").eq(stock_item_id))
        )
        for _Ingredient in _Ingredients:
            _Ingredient.raw_text = _Ingredient.raw_text or _Ingredient.label or _StockItem.name
            # The FK column, not `stock_item`: that relationship is `noload`,
            # so it already reads None and assigning None changes nothing.
            _Ingredient._stock_item_id = None
            _Ingredient.label = None
            _Ingredient.preferred_buy_id = None
            _Ingredient.selected_product_id = None
        self.repository.flush()

        # FU-883 — lines on draft/shopping lists go with the item; lines on
        # done lists survive as history (SET NULL + a name snapshot, which
        # this also backfills for any line that never went through /finish).
        # Runs before the delete so both land in one transaction.
        prepare_lines_for_anchor_delete(self.repository, stock_item_id=stock_item_id)

        self.repository.remove(_StockItem)
        self.repository.save_changes()

        return DeleteStockItemResponse()


@STOCK_ITEM_ROUTER.route("<uuid:stock_item_id>", methods=["DELETE"])
def delete_stock_item(stock_item_id: UUID):
    _LOGGER.info("Received request to delete stock item.")
    _Handler: DeleteStockItemHandler = DeleteStockItemHandler(SqlAlchemyRepository())
    _Response = _Handler.handle(stock_item_id)

    if _Response.stock_item_not_found:
        _LOGGER.warning(f"Stock item not found with ID: {stock_item_id}")
        return not_found(StockItem.__name__, stock_item_id)

    _LOGGER.info(f"Successfully deleted stock item with ID {stock_item_id}.")
    return no_content()
