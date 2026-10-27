import logging
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.stock_location import StockLocation
from dora_api.domain.types import EMPTY_UUID
from dora_api.features.routers import STOCK_LOCATION_ROUTER
from dora_api.features.stock_locations.get_stock_locations import \
    get_stock_locations
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  created)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


class CreateStockLocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length = 1)


@dataclass(slots=True)
class CreateStockLocationResponse:
    new_stock_location_id: UUID = EMPTY_UUID
    stock_location_already_exists: bool = False


class CreateStockLocationHandler:

    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: CreateStockLocationRequest) -> CreateStockLocationResponse:
        _StockLocationName = EntityField(StockLocation, StockLocation.Fields.NAME)
        _ExistingStockLocation: StockLocation | None = (
            self.repository
            .get(StockLocation)
            .one(_StockLocationName.eq(request.name))
        )

        if _ExistingStockLocation:
            return CreateStockLocationResponse(stock_location_already_exists=True)

        _NewStockLocation = StockLocation(
            name = request.name
        )

        self.repository.add(_NewStockLocation)
        self.repository.save_changes()

        return CreateStockLocationResponse(new_stock_location_id=_NewStockLocation.id)


@STOCK_LOCATION_ROUTER.route("", methods=["POST"])
@has_request_body(CreateStockLocationRequest)
def create_stock_location():
    _LOGGER.info("Received request to create stock location.")
    _Handler = CreateStockLocationHandler(SqlAlchemyRepository())
    _Request: CreateStockLocationRequest = get_request_body()
    _Response = _Handler.handle(_Request)

    if _Response.stock_location_already_exists:
        _LOGGER.warning(f"Stock location already exists with name: {_Request.name}")
        return business_rule_violation(f"A stock location with the name '{_Request.name}' already exists.")

    _LOGGER.info(f"Successfully created stock location with ID: {_Response.new_stock_location_id}")
    from dora_api.features.stock_locations.get_stock_locations import \
        GetStockLocationsHandler
    _Dto = GetStockLocationsHandler(SqlAlchemyRepository()).handle_by_id(
        _Response.new_stock_location_id
    )
    return created(
        _Response.new_stock_location_id,
        f"{STOCK_LOCATION_ROUTER.name}.{get_stock_locations.__name__}",
        "stock_location_id",
        body = _Dto,
    )
