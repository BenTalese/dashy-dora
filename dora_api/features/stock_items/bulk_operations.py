"""Bulk stock-item operations.

Separated from the single-item files (`move_stock_item.py`,
`update_stock_item.py`) so those stay narrow, mirroring the split already
made for shopping lists in `shopping_lists/bulk_operations.py`.

Endpoints:

  POST /api/stock-items/bulk-move
      Move a set of items to one location (or unassign them).

  POST /api/stock-items/bulk-set-level
      Put a set of items on one stock level. Backs the overview's
      "Mark restocked" bulk action.

Why these exist (2026-08-22 owner feedback: "bulk actions seem to be
performed one item at a time and it can be slow"): the SPA was issuing one
HTTP request per selected item, sequentially awaited. On a 40-item
selection that is 40 round-trips of latency before the first bit of
feedback. The win here is round-trips, not query count.

`bulk-set-level` deliberately loops `UpdateStockItemHandler` rather than
writing the levels itself. A level change is not a column write: it stamps
`stock_level_last_updated` + `last_checked_at`, appends a `StockLevelChange`
history row, may record a `ConsumptionEvent`, and may fire the auto-add
hook. Reimplementing that here would be a second copy of a rule that
already has an owner (R-003), and the copies would drift the first time
either side changed. One commit per item is the price; the caller still
only pays for one round-trip.
"""
import logging
from dataclasses import dataclass, field
from typing import List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_location import StockLocation
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.features.stock_items.update_stock_item import (
    UpdateStockItemHandler, UpdateStockItemRequest,
)
from dora_api.infrastructure.api_response import (business_rule_violation, ok)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)

# Same ceiling the stocktake bulk-check uses. A selection larger than this
# is a "select all" on a pantry big enough that the client should be
# chunking anyway, and an unbounded id list is an easy way to hold a
# request open for minutes.
_MAX_IDS = 500


# ───── Bulk move ──────────────────────────────────────────────────────────

class BulkMoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stock_item_ids: List[UUID] = Field(min_length=1, max_length=_MAX_IDS)
    # None = unassigned, matching the single-item move endpoint.
    destination_location_id: UUID | None = None


@dataclass(slots=True)
class BulkMoveResponse:
    destination_not_found: bool = False
    moved_count: int = 0
    # Ids the caller asked for that no longer exist. Not an error — a
    # concurrent delete shouldn't fail the other 39 moves — but reported
    # so the client can say so.
    missing_ids: List[UUID] = field(default_factory=list)


class BulkMoveHandler:
    """Unlike `bulk-set-level`, this one writes directly rather than looping
    the single-item handler: a move is a single FK assignment with no
    history rows, no timestamps and no hooks, so there is no rule here to
    duplicate. Two queries and one commit for the whole set.
    """

    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: BulkMoveRequest) -> BulkMoveResponse:
        destination: StockLocation | None = None
        if request.destination_location_id is not None:
            destination = (
                self.repository.get(StockLocation)
                .by_id(request.destination_location_id)
            )
            if destination is None:
                return BulkMoveResponse(destination_not_found=True)

        items: List[StockItem] = self.repository.get(StockItem).all(
            EntityField(StockItem, StockItem.Fields.ID)
            .in_([str(i) for i in request.stock_item_ids])
        )
        found_ids = {str(i.id) for i in items}
        missing = [i for i in request.stock_item_ids if str(i) not in found_ids]

        for item in items:
            if destination is None:
                # Same `lazy="noload"` trap the single-item move and
                # `update_stock_item` document: clearing via the
                # relationship alone doesn't always dirty the FK column.
                item._stock_location_id = None
                item.stock_location = None
            else:
                item.stock_location = destination
        if items:
            self.repository.save_changes()
        return BulkMoveResponse(moved_count=len(items), missing_ids=missing)


@STOCK_ITEM_ROUTER.route("/bulk-move", methods=["POST"])
@has_request_body(BulkMoveRequest)
def bulk_move_stock_items():
    _Request: BulkMoveRequest = get_request_body()
    _Response = BulkMoveHandler(SqlAlchemyRepository()).handle(_Request)
    if _Response.destination_not_found:
        return business_rule_violation("Destination location was not found.")
    _LOGGER.info(
        f"Bulk-moved {_Response.moved_count} of {len(_Request.stock_item_ids)} "
        f"stock item(s) -> {_Request.destination_location_id}"
    )
    return ok({
        "moved_count": _Response.moved_count,
        "missing_ids": [str(i) for i in _Response.missing_ids],
    })


# ───── Bulk set level ─────────────────────────────────────────────────────

class BulkSetLevelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stock_item_ids: List[UUID] = Field(min_length=1, max_length=_MAX_IDS)
    stock_level_id: UUID


@dataclass(slots=True)
class BulkSetLevelResponse:
    stock_level_not_found: bool = False
    updated_count: int = 0
    failed_ids: List[UUID] = field(default_factory=list)


class BulkSetLevelHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: BulkSetLevelRequest) -> BulkSetLevelResponse:
        inner = UpdateStockItemHandler(self.repository)
        updated = 0
        failed: List[UUID] = []
        for stock_item_id in request.stock_item_ids:
            response = inner.handle(
                UpdateStockItemRequest(stock_level_id=request.stock_level_id),
                stock_item_id,
            )
            # A bad level id is the same answer for every item in the set,
            # so fail the whole request rather than reporting it 40 times.
            if response.stock_level_not_found:
                return BulkSetLevelResponse(stock_level_not_found=True)
            if response.stock_item_not_found:
                failed.append(stock_item_id)
                continue
            updated += 1
        return BulkSetLevelResponse(updated_count=updated, failed_ids=failed)


@STOCK_ITEM_ROUTER.route("/bulk-set-level", methods=["POST"])
@has_request_body(BulkSetLevelRequest)
def bulk_set_stock_level():
    _Request: BulkSetLevelRequest = get_request_body()
    _Response = BulkSetLevelHandler(SqlAlchemyRepository()).handle(_Request)
    if _Response.stock_level_not_found:
        return business_rule_violation("Stock level was not found.")
    _LOGGER.info(
        f"Bulk-set level {_Request.stock_level_id} on "
        f"{_Response.updated_count} of {len(_Request.stock_item_ids)} stock item(s)"
    )
    return ok({
        "updated_count": _Response.updated_count,
        "failed_ids": [str(i) for i in _Response.failed_ids],
    })
