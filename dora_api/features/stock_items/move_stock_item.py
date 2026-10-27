"""PATCH /api/stock-items/<id>/move — change a stock item's location.

Separate endpoint (rather than reusing the generic update) so the UI's
"Move" flow can call something narrow and obviously-named, and so we can
log moves distinctly from other edits.
"""
import logging
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_location import StockLocation
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  no_content, not_found)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


class MoveStockItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # None = unassigned (parks the item until the user files it).
    destination_location_id: UUID | None = None


@dataclass(slots=True)
class MoveStockItemResponse:
    stock_item_not_found: bool = False
    destination_not_found: bool = False


class MoveStockItemHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: MoveStockItemRequest, stock_item_id: UUID) -> MoveStockItemResponse:
        item: StockItem | None = self.repository.get(StockItem).by_id(stock_item_id)
        if item is None:
            return MoveStockItemResponse(stock_item_not_found=True)

        if request.destination_location_id is None:
            item.stock_location = None
            self.repository.save_changes()
            return MoveStockItemResponse()

        destination: StockLocation | None = (
            self.repository.get(StockLocation).by_id(request.destination_location_id)
        )
        if destination is None:
            return MoveStockItemResponse(destination_not_found=True)

        item.stock_location = destination
        self.repository.save_changes()
        return MoveStockItemResponse()


@STOCK_ITEM_ROUTER.route("/<uuid:stock_item_id>/move", methods=["PATCH"])
@has_request_body(MoveStockItemRequest)
def move_stock_item(stock_item_id: UUID):
    _Handler = MoveStockItemHandler(SqlAlchemyRepository())
    _Request: MoveStockItemRequest = get_request_body()
    _Response = _Handler.handle(_Request, stock_item_id)

    if _Response.stock_item_not_found:
        return not_found("StockItem", stock_item_id)
    if _Response.destination_not_found:
        return business_rule_violation("Destination location was not found.")

    _LOGGER.info(
        f"Moved stock item {stock_item_id} -> {_Request.destination_location_id}"
    )
    return no_content()
