import logging
from dataclasses import dataclass
from uuid import UUID

from flask import request

from dora_api.domain.entities.stock_location import StockLocation
from dora_api.features.routers import STOCK_LOCATION_ROUTER
from dora_api.infrastructure.api_response import bad_request, paginated
from dora_api.infrastructure.query_options import (InvalidQueryParameter,
                                                   parse_query_options)
from dora_api.persistence.field import EntityField
from dora_api.persistence.page import Page
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StockLocationDto:
    name: str
    stock_location_id: UUID

    @classmethod
    def from_entity(cls, stock_location: StockLocation) -> 'StockLocationDto':
        return StockLocationDto(
            name = stock_location.name,
            stock_location_id = stock_location.id
        )


_FIELD_MAP: dict[str, EntityField] = {
    "stock_location_id": EntityField(StockLocation, "id"),
}


class GetStockLocationsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, options) -> Page[StockLocationDto]:
        return self.repository.get(StockLocation).paginate(
            options, StockLocationDto.from_entity, field_map=_FIELD_MAP
        )

    def handle_by_id(self, stock_location_id: UUID) -> StockLocationDto | None:
        entity = self.repository.get(StockLocation).by_id(stock_location_id)
        return StockLocationDto.from_entity(entity) if entity else None


@STOCK_LOCATION_ROUTER.route("")
def get_stock_locations():
    try:
        _Options = parse_query_options(request.args)
        _Page = GetStockLocationsHandler(SqlAlchemyRepository()).handle(_Options)
    except InvalidQueryParameter as exc:
        return bad_request(str(exc))
    _LOGGER.info(f"Retrieved {len(_Page.items)} of {_Page.total} stock locations.")
    return paginated(_Page.items, _Page.total, _Page.page, _Page.limit)
