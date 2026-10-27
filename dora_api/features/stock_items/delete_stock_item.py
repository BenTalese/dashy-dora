from dataclasses import dataclass, field
from http.client import UNPROCESSABLE_ENTITY
import logging
from uuid import UUID

from flask import Response, jsonify
from sqlalchemy import select

from dora_api.domain.entities.recipe import Recipe
from dora_api.domain.entities.recipe_ingredient import RecipeIngredient
from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.features.shopping_lists._line_retention import \
    prepare_lines_for_anchor_delete
from dora_api.infrastructure.api_response import no_content, not_found
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class BlockingRecipe:
    recipe_id: UUID
    name: str


@dataclass(slots=True)
class DeleteStockItemResponse:
    stock_item_not_found: bool = False
    blocked_by_recipes: list[BlockingRecipe] = field(default_factory=list)


class DeleteStockItemHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, stock_item_id: UUID) -> DeleteStockItemResponse:
        _StockItem = self.repository.get(StockItem).by_id(stock_item_id)

        if not _StockItem:
            return DeleteStockItemResponse(stock_item_not_found = True)

        # refuse deletion when the item is still an ingredient on any
        # recipe. Every other FK to StockItem is either CASCADE (templates,
        # product joins, level-change history, legacy substitutes, price
        # observations) or SET NULL (waste events, and shopping-list lines
        # since FU-883), so RecipeIngredient is the only blocker — and the
        # one the user actually wants to know about, since they have to act
        # in a different page to clear it.
        # Same query shape as get_stock_item_detail.linked_recipes.
        _Session = self.repository.session
        _IngredientRecipeIds = list(_Session.execute(
            select(RecipeIngredient._recipe_id)
            .where(RecipeIngredient._stock_item_id == stock_item_id)
            .distinct()
        ).scalars())
        if _IngredientRecipeIds:
            _Recipes = list(_Session.execute(
                select(Recipe).where(Recipe.id.in_(_IngredientRecipeIds))
            ).scalars())
            _Recipes.sort(key=lambda r: r.name.lower())
            return DeleteStockItemResponse(
                blocked_by_recipes=[
                    BlockingRecipe(recipe_id=r.id, name=r.name) for r in _Recipes
                ]
            )

        # FU-883 — lines on draft/shopping lists go with the item; lines on
        # done lists survive as history (SET NULL + a name snapshot, which
        # this also backfills for any line that never went through /finish).
        # Runs before the delete so both land in one transaction.
        prepare_lines_for_anchor_delete(self.repository, stock_item_id=stock_item_id)

        self.repository.remove(_StockItem)
        self.repository.save_changes()

        return DeleteStockItemResponse()


def _blocked_by_recipes_response(blocked_by: list[BlockingRecipe]) -> Response:
    """B4 conflict response: 422 with a structured `blocked_by_recipes` list
    the frontend uses to render a "Used by N recipes" dialog. The `errors`
    string is the human fallback for clients (or our own toasts) that don't
    know the extension field."""
    names = ", ".join(b.name for b in blocked_by)
    message = (
        f"Used by {len(blocked_by)} recipe(s): {names}. "
        "Remove this ingredient from those recipes first."
    )
    response = jsonify({
        "detail": "See errors property for more details.",
        "errors": {"": [message]},
        "status": UNPROCESSABLE_ENTITY,
        "title": "Stock item is in use.",
        "type": "https://datatracker.ietf.org/doc/html/rfc4918#section-11.2",
        "blocked_by_recipes": [
            {"recipe_id": str(b.recipe_id), "name": b.name} for b in blocked_by
        ],
    })
    response.content_type = 'application/problem+json'
    response.status_code = UNPROCESSABLE_ENTITY
    return response


@STOCK_ITEM_ROUTER.route("<uuid:stock_item_id>", methods=["DELETE"])
def delete_stock_item(stock_item_id: UUID):
    _LOGGER.info("Received request to delete stock item.")
    _Handler: DeleteStockItemHandler = DeleteStockItemHandler(SqlAlchemyRepository())
    _Response = _Handler.handle(stock_item_id)

    if _Response.stock_item_not_found:
        _LOGGER.warning(f"Stock item not found with ID: {stock_item_id}")
        return not_found(StockItem.__name__, stock_item_id)

    if _Response.blocked_by_recipes:
        _LOGGER.info(
            f"Refused delete of stock item {stock_item_id}: still used by "
            f"{len(_Response.blocked_by_recipes)} recipe(s)."
        )
        return _blocked_by_recipes_response(_Response.blocked_by_recipes)

    _LOGGER.info(f"Successfully deleted stock item with ID {stock_item_id}.")
    return no_content()
