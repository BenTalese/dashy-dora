import logging
from dataclasses import dataclass
from uuid import UUID

from dora_api.domain.entities.stock_location import StockLocation
from dora_api.features.routers import STOCK_LOCATION_ROUTER
from dora_api.infrastructure.api_response import no_content, not_found
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DeleteStockLocationResponse:
    stock_location_not_found: bool = False


class DeleteStockLocationHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, stock_location_id: UUID) -> DeleteStockLocationResponse:
        _StockLocation = self.repository.get(StockLocation).by_id(stock_location_id)

        if not _StockLocation:
            return DeleteStockLocationResponse(stock_location_not_found = True)

        self.repository.remove(_StockLocation)
        self.repository.save_changes()

        return DeleteStockLocationResponse()


@STOCK_LOCATION_ROUTER.route("<uuid:stock_location_id>", methods=["DELETE"])
def delete_stock_location(stock_location_id: UUID):
    _LOGGER.info("Received request to delete stock location.")
    _Handler: DeleteStockLocationHandler = DeleteStockLocationHandler(SqlAlchemyRepository())
    _Response = _Handler.handle(stock_location_id)

    if _Response.stock_location_not_found:
        _LOGGER.warning(f"Stock location not found with ID: {stock_location_id}")
        return not_found(StockLocation.__name__, stock_location_id)

    _LOGGER.info(f"Successfully deleted stock location with ID {stock_location_id}.")
    return no_content()
