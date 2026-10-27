import logging
from dataclasses import dataclass
from uuid import UUID

from flask import request

from dora_api.domain.entities.stock_level import StockLevel
from dora_api.features.routers import STOCK_LEVEL_ROUTER
from dora_api.infrastructure.api_response import bad_request, paginated
from dora_api.infrastructure.query_options import (InvalidQueryParameter,
                                                   parse_query_options)
from dora_api.persistence.field import EntityField
from dora_api.persistence.page import Page
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StockLevelDto:
    name: str
    sequence: int
    stock_level_id: UUID

    @classmethod
    def from_entity(cls, stock_level: StockLevel) -> 'StockLevelDto':
        return StockLevelDto(
            name = stock_level.name,
            sequence = stock_level.sequence,
            stock_level_id = stock_level.id
        )


_FIELD_MAP: dict[str, EntityField] = {
    "stock_level_id": EntityField(StockLevel, "id"),
}


class GetStockLevelsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, options) -> Page[StockLevelDto]:
        return self.repository.get(StockLevel).paginate(
            options, StockLevelDto.from_entity, field_map=_FIELD_MAP
        )


@STOCK_LEVEL_ROUTER.route("")
def get_stock_levels():
    try:
        _Options = parse_query_options(request.args)
        _Page = GetStockLevelsHandler(SqlAlchemyRepository()).handle(_Options)
    except InvalidQueryParameter as exc:
        return bad_request(str(exc))
    _LOGGER.info(f"Retrieved {len(_Page.items)} of {_Page.total} stock levels.")
    return paginated(_Page.items, _Page.total, _Page.page, _Page.limit)
