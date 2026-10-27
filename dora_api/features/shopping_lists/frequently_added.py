"""GET /api/shopping-lists/frequently-added — stock items by how often they've
been added to a shopping list, most first.

Used by QuickAddSheet to rank "stuff you usually buy" ahead of the rest before
the user starts typing. The ranking rule lives in `_frequently_added`
(shared with the auto-generate dialog, R-003); this endpoint hands the SPA the
ordered ids and nothing else — the sheet already holds every stock item from
the store, and the `name` / `stock_level_id` / `add_count` fields it used to
carry had no reader (`stock_level_id` was also always None: the handler read
the `noload` relationship — finalisation 03-R6 / 03-R14, R-032 / R-057).
"""
import logging
from dataclasses import dataclass
from typing import List
from uuid import UUID

from flask import request

from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.routers import SHOPPING_LIST_ROUTER
from dora_api.features.shopping_lists._frequently_added import rank_frequently_added_ids
from dora_api.infrastructure.api_response import ok
from dora_api.infrastructure.ports import Repository
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FrequentlyAddedDto:
    stock_item_id: UUID


class GetFrequentlyAddedHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, limit: int) -> List[FrequentlyAddedDto]:
        ranked = rank_frequently_added_ids(self.repository.session, limit)
        if not ranked:
            return []
        # Lines outlive their item only transiently (cascade), but be honest:
        # rank only ids that still name a stock item.
        live = {
            item.id for item in self.repository.get(StockItem).all(
                EntityField(StockItem, "id").in_(ranked)
            )
        }
        return [FrequentlyAddedDto(stock_item_id=i) for i in ranked if i in live]


@SHOPPING_LIST_ROUTER.route("/frequently-added", methods=["GET"])
def get_frequently_added():
    try:
        _Limit = int(request.args.get("limit", "12"))
    except (TypeError, ValueError):
        _Limit = 12
    _Limit = max(1, min(_Limit, 50))
    _Results = GetFrequentlyAddedHandler(SqlAlchemyRepository()).handle(_Limit)
    _LOGGER.debug("Frequently-added returned %d items (limit %d)", len(_Results), _Limit)
    return ok(_Results)
