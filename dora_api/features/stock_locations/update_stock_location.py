import logging
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.stock_location import StockLocation
from dora_api.features.routers import STOCK_LOCATION_ROUTER
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  no_content, not_found)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


class UpdateStockLocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default = None, min_length = 1)


@dataclass(slots=True)
class UpdateStockLocationResponse:
    stock_location_already_exists: bool = False
    stock_location_not_found: bool = False


class UpdateStockLocationHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: UpdateStockLocationRequest, stock_location_id: UUID) -> UpdateStockLocationResponse:
        # Get existing stock location
        _StockLocation: StockLocation | None = self.repository.get(StockLocation).by_id(stock_location_id)
        if not _StockLocation:
            return UpdateStockLocationResponse(stock_location_not_found=True)

        # Update name
        if "name" in request.model_fields_set and request.name is not None:
            _StockLocationName = EntityField(StockLocation, StockLocation.Fields.NAME)
            _SameNameStockLocation: StockLocation | None = (
                self.repository
                .get(StockLocation)
                .one(_StockLocationName.eq(request.name))
            )

            # str(...) both sides — raw str path param vs UUID id (FU-528
            # family): a bare `!=` made renaming a location to its own name 422.
            if _SameNameStockLocation and str(_SameNameStockLocation.id) != str(stock_location_id):
                return UpdateStockLocationResponse(stock_location_already_exists=True)

            _StockLocation.name = request.name

        self.repository.save_changes()
        return UpdateStockLocationResponse()


@STOCK_LOCATION_ROUTER.route("<uuid:stock_location_id>", methods=["PATCH"])
@has_request_body(UpdateStockLocationRequest)
def update_stock_location(stock_location_id: UUID):
    _LOGGER.info("Received request to update stock location.")
    _Handler = UpdateStockLocationHandler(SqlAlchemyRepository())
    _Request: UpdateStockLocationRequest = get_request_body()
    _Response = _Handler.handle(_Request, stock_location_id)

    if _Response.stock_location_not_found:
        _LOGGER.warning(f"Stock location not found with ID: {stock_location_id}")
        return not_found(StockLocation.__name__, stock_location_id)

    if _Response.stock_location_already_exists:
        _LOGGER.warning(f"Stock location already exists with name: {_Request.name}")
        return business_rule_violation(f"A stock location with the name '{_Request.name}' already exists.")

    _LOGGER.info(f"Successfully updated stock location with ID: {stock_location_id}")
    return no_content()
