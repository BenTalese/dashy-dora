import logging
from dataclasses import dataclass
from uuid import UUID

from dora_api.app import db
from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.features.substitutes.canonical import canonical_pair
from dora_api.infrastructure.api_response import no_content, not_found
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RemoveSubstituteResponse:
    stock_item_not_found: bool = False
    link_not_found: bool = False


class RemoveSubstituteHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, stock_item_id: UUID, substitute_id: UUID) -> RemoveSubstituteResponse:
        if not self.repository.get(StockItem).exists(stock_item_id):
            return RemoveSubstituteResponse(stock_item_not_found=True)

        if stock_item_id == substitute_id:
            return RemoveSubstituteResponse(link_not_found=True)
        a_id, b_id = canonical_pair(stock_item_id, substitute_id)
        _Assoc = db.metadata.tables["StockItemSubstitute"]
        _Result = db.session.execute(
            _Assoc.delete().where(
                (_Assoc.c.stock_item_a_id == a_id)
                & (_Assoc.c.stock_item_b_id == b_id)
            )
        )
        if _Result.rowcount == 0:
            return RemoveSubstituteResponse(link_not_found=True)

        self.repository.save_changes()
        return RemoveSubstituteResponse()


@STOCK_ITEM_ROUTER.route("<uuid:stock_item_id>/substitutes/<uuid:substitute_id>", methods=["DELETE"])
def remove_substitute(stock_item_id: UUID, substitute_id: UUID):
    _Handler = RemoveSubstituteHandler(SqlAlchemyRepository())
    _Response = _Handler.handle(stock_item_id, substitute_id)

    if _Response.stock_item_not_found:
        return not_found(StockItem.__name__, stock_item_id)
    if _Response.link_not_found:
        return not_found("StockItemSubstitute link", substitute_id)

    _LOGGER.info("Removed substitute %s from stock item %s", substitute_id, stock_item_id)
    return no_content()
