"""Simple-mode buying: one tap and the item is bought.

Simple mode is a view over the same list flow mode uses, without the
lifecycle: no Start shopping, no Finish. Ticking a line there means "I bought
this", so the item restocks and the line leaves the list in one request.

  POST /api/shopping-lists/<id>/lines/<lid>/buy  restock + remove the line
  POST /api/shopping-lists/<id>/lines/unbuy      undo a buy from its echo

The buy response carries everything the undo needs (the line's fields and the
item's level before the restock), so the undo puts both back exactly.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.shopping_list import ShoppingList, ShoppingListLine
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_level import StockLevel
from dora_api.features.routers import SHOPPING_LIST_ROUTER
from dora_api.features.shopping_lists._restock import restock_stock_items
from dora_api.features.shopping_lists.manage_shopping_list_lines import \
    LIST_DONE_REFUSAL
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  no_content, not_found, ok)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)


class BoughtLine(BaseModel):
    """The echo of a bought line: the undo request body, verbatim."""
    model_config = ConfigDict(extra="forbid")
    stock_item_id: UUID | None = None
    product_id: UUID | None = None
    quantity: int | None = Field(default=None, ge=1)
    selected_product_id: UUID | None = None
    preferred_buy_id: UUID | None = None
    planned_store_id: UUID | None = None
    sequence: int = 0
    is_auto_added: bool = False
    added_at: datetime | None = None
    previous_stock_level_id: UUID | None = None
    previous_stock_level_last_updated: datetime | None = None


# ───── Buy ────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class BuyLineResponse:
    line_not_found: bool = False
    list_done: bool = False
    bought: BoughtLine | None = None


class BuyLineHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, shopping_list_id: UUID, line_id: UUID) -> BuyLineResponse:
        line: ShoppingListLine | None = self.repository.get(ShoppingListLine).by_id(line_id)
        # Path params arrive as str; compare as strings (see DeleteLineHandler).
        if line is None or str(line.shopping_list_id) != str(shopping_list_id):
            return BuyLineResponse(line_not_found=True)
        lst: ShoppingList | None = self.repository.get(ShoppingList).by_id(shopping_list_id)
        if lst is None or lst.is_done:
            return BuyLineResponse(list_done=True)

        previous_level_id = None
        previous_updated = None
        if line.stock_item_id is not None:
            item: StockItem | None = (
                self.repository.get(StockItem)
                .include(StockItem.Fields.STOCK_LEVEL)
                .by_id(line.stock_item_id)
            )
            if item is not None:
                previous_level_id = item.stock_level.id if item.stock_level else None
                previous_updated = item.stock_level_last_updated

        bought = BoughtLine(
            stock_item_id=line.stock_item_id,
            product_id=line.product_id,
            quantity=line.quantity,
            selected_product_id=line.selected_product_id,
            preferred_buy_id=line.preferred_buy_id,
            planned_store_id=line.planned_store_id,
            sequence=line.sequence,
            is_auto_added=line.is_auto_added,
            added_at=line.added_at,
            previous_stock_level_id=previous_level_id,
            previous_stock_level_last_updated=previous_updated,
        )

        restock_stock_items(
            self.repository, [line.stock_item_id], now=datetime.now(timezone.utc),
        )
        self.repository.remove(line)
        self.repository.save_changes()
        return BuyLineResponse(bought=bought)


@SHOPPING_LIST_ROUTER.route(
    "/<uuid:shopping_list_id>/lines/<uuid:line_id>/buy", methods=["POST"],
)
def buy_line(shopping_list_id: UUID, line_id: UUID):
    _Response = BuyLineHandler(SqlAlchemyRepository()).handle(shopping_list_id, line_id)
    if _Response.line_not_found:
        return not_found("ShoppingListLine", line_id)
    if _Response.list_done:
        return business_rule_violation(LIST_DONE_REFUSAL)
    _LOGGER.info(f"Bought line {line_id} on list {shopping_list_id}")
    return ok({"bought": _Response.bought.model_dump(mode="json")})


# ───── Undo a buy ─────────────────────────────────────────────────────────

@dataclass(slots=True)
class UnbuyLineResponse:
    list_not_found: bool = False
    list_done: bool = False


class UnbuyLineHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: BoughtLine, shopping_list_id: UUID) -> UnbuyLineResponse:
        lst: ShoppingList | None = self.repository.get(ShoppingList).by_id(shopping_list_id)
        if lst is None:
            return UnbuyLineResponse(list_not_found=True)
        if lst.is_done:
            return UnbuyLineResponse(list_done=True)

        # Put the level back first. An item deleted since the buy has nothing
        # to restore and no line to come back to.
        if request.stock_item_id is not None:
            item: StockItem | None = self.repository.get(StockItem).by_id(request.stock_item_id)
            if item is None:
                return UnbuyLineResponse()
            level = (
                self.repository.get(StockLevel).by_id(request.previous_stock_level_id)
                if request.previous_stock_level_id is not None else None
            )
            item._stock_level_id = level.id if level else None
            item.stock_level = level
            if request.previous_stock_level_last_updated is not None:
                item.stock_level_last_updated = request.previous_stock_level_last_updated

        # The same anchor re-added since the buy (another device, a cart tap)
        # already holds the line; a second copy would be a duplicate.
        siblings = self.repository.get(ShoppingListLine).all(
            EntityField(ShoppingListLine, "shopping_list_id").eq(shopping_list_id)
        )
        already_back = any(
            s.stock_item_id == request.stock_item_id and s.product_id == request.product_id
            for s in siblings
        )
        if not already_back:
            self.repository.add(ShoppingListLine(
                shopping_list_id=shopping_list_id,
                stock_item_id=request.stock_item_id,
                product_id=request.product_id,
                quantity=request.quantity,
                selected_product_id=request.selected_product_id,
                preferred_buy_id=request.preferred_buy_id,
                planned_store_id=request.planned_store_id,
                sequence=request.sequence,
                is_auto_added=request.is_auto_added,
                added_at=request.added_at or datetime.now(timezone.utc),
            ))
        self.repository.save_changes()
        return UnbuyLineResponse()


@SHOPPING_LIST_ROUTER.route("/<uuid:shopping_list_id>/lines/unbuy", methods=["POST"])
@has_request_body(BoughtLine)
def unbuy_line(shopping_list_id: UUID):
    _Request: BoughtLine = get_request_body()
    _Response = UnbuyLineHandler(SqlAlchemyRepository()).handle(_Request, shopping_list_id)
    if _Response.list_not_found:
        return not_found("ShoppingList", shopping_list_id)
    if _Response.list_done:
        return business_rule_violation(LIST_DONE_REFUSAL)
    _LOGGER.info(f"Undid a buy on list {shopping_list_id} (stock_item={_Request.stock_item_id})")
    return no_content()
