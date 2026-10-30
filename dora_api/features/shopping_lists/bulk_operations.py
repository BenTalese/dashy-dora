"""Bulk-line and reorder endpoints.

Separated from `manage_shopping_list_lines.py` so the single-line CRUD
flow stays narrow and these wider-blast-radius operations live together.

Endpoints:

  POST /api/shopping-lists/<id>/lines/bulk-add
      Add a set of stock items to one list in one round-trip. Backs the
      stock overview's "Add to list…" bulk action.

  POST /api/shopping-lists/<id>/lines/bulk-remove-by-stock-item
      The inverse — remove every line anchored on one of the given stock
      items. Backs the overview's "Remove from list" bulk action.

  POST /api/shopping-lists/<id>/lines/reorder
      Persist a new line order. The request body lists line_ids in the
      desired order; the handler writes the `sequence` column accordingly.
"""
import logging
from dataclasses import dataclass, field
from typing import List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.shopping_list import ShoppingList, ShoppingListLine
from dora_api.features.routers import SHOPPING_LIST_ROUTER
from dora_api.features.shopping_lists.manage_shopping_list_lines import (
    AddLineHandler, AddLineRequest, RemoveLineByStockItemHandler)
from dora_api.infrastructure.api_response import (bad_request, no_content,
                                                  not_found, ok)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


# ───── Bulk add / bulk remove by stock item ───────────────────────────────
#
# 2026-08-22 owner feedback ("bulk actions seem to be performed one item at a
# time and it can be slow"). The stock overview's "Add to list…" and "Remove
# from list" bulk actions both looped the single-line endpoints from the
# browser, and the add path additionally refreshed the whole shopping-list
# store on every iteration. These two collapse the loop to one round-trip.
#
# Both orchestrate the existing single-line handlers rather than writing
# their own SQL — `AddLineHandler` de-dupes, resolves products and assigns
# sequences, and `RemoveLineByStockItemHandler` cascades nested product
# lines. Neither rule wants a second copy (R-003).

class BulkAddLinesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stock_item_ids: List[UUID] = Field(min_length=1, max_length=500)


@dataclass(slots=True)
class BulkAddLinesResponse:
    list_not_found: bool = False
    added: int = 0
    already_on_list: int = 0
    failed_ids: List[UUID] = field(default_factory=list)


class BulkAddLinesHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: BulkAddLinesRequest, shopping_list_id: UUID) -> BulkAddLinesResponse:
        inner = AddLineHandler(self.repository)
        response = BulkAddLinesResponse()
        for stock_item_id in request.stock_item_ids:
            result = inner.handle(
                AddLineRequest(stock_item_id=stock_item_id), shopping_list_id, commit=False,
            )
            # A missing list is the same answer for the whole set — bail
            # rather than reporting it once per item.
            if result.list_not_found:
                return BulkAddLinesResponse(list_not_found=True)
            if result.already_on_list:
                response.already_on_list += 1
            elif result.line_id is not None:
                response.added += 1
            else:
                response.failed_ids.append(stock_item_id)
        self.repository.save_changes()
        return response


@SHOPPING_LIST_ROUTER.route("/<uuid:shopping_list_id>/lines/bulk-add", methods=["POST"])
@has_request_body(BulkAddLinesRequest)
def bulk_add_lines(shopping_list_id: UUID):
    _Request: BulkAddLinesRequest = get_request_body()
    _Response = BulkAddLinesHandler(SqlAlchemyRepository()).handle(_Request, shopping_list_id)
    if _Response.list_not_found:
        return not_found("ShoppingList", shopping_list_id)
    _LOGGER.info(
        f"Bulk-add on list {shopping_list_id}: added {_Response.added}, "
        f"already-on {_Response.already_on_list}, "
        f"failed {len(_Response.failed_ids)} of {len(_Request.stock_item_ids)}"
    )
    return ok({
        "added": _Response.added,
        "already_on_list": _Response.already_on_list,
        "failed_ids": [str(i) for i in _Response.failed_ids],
    })


class BulkRemoveByStockItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stock_item_ids: List[UUID] = Field(min_length=1, max_length=500)


@dataclass(slots=True)
class BulkRemoveByStockItemResponse:
    list_not_found: bool = False
    removed_count: int = 0


class BulkRemoveByStockItemHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(
        self, request: BulkRemoveByStockItemRequest, shopping_list_id: UUID,
    ) -> BulkRemoveByStockItemResponse:
        inner = RemoveLineByStockItemHandler(self.repository)
        removed = 0
        for stock_item_id in request.stock_item_ids:
            result = inner.handle(shopping_list_id, stock_item_id, commit=False)
            if result.list_not_found:
                return BulkRemoveByStockItemResponse(list_not_found=True)
            if result.removed:
                removed += 1
        self.repository.save_changes()
        return BulkRemoveByStockItemResponse(removed_count=removed)


@SHOPPING_LIST_ROUTER.route(
    "/<uuid:shopping_list_id>/lines/bulk-remove-by-stock-item", methods=["POST"],
)
@has_request_body(BulkRemoveByStockItemRequest)
def bulk_remove_lines_by_stock_item(shopping_list_id: UUID):
    _Request: BulkRemoveByStockItemRequest = get_request_body()
    _Response = BulkRemoveByStockItemHandler(SqlAlchemyRepository()).handle(
        _Request, shopping_list_id,
    )
    if _Response.list_not_found:
        return not_found("ShoppingList", shopping_list_id)
    _LOGGER.info(
        f"Bulk cart-remove on list {shopping_list_id}: removed "
        f"{_Response.removed_count} of {len(_Request.stock_item_ids)} requested"
    )
    return ok({"removed_count": _Response.removed_count})


# ───── Reorder ────────────────────────────────────────────────────────────

class ReorderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Line ids in the desired display order, top-to-bottom. Missing lines
    # (any line on the list not in this list) keep their existing sequence
    # and end up after the reordered ones.
    line_ids: List[UUID]


@dataclass(slots=True)
class ReorderResponse:
    list_not_found: bool = False
    mismatched: List[UUID] = field(default_factory=list)
    reordered_count: int = 0


class ReorderHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: ReorderRequest, shopping_list_id: UUID) -> ReorderResponse:
        if not self.repository.get(ShoppingList).exists(shopping_list_id):
            return ReorderResponse(list_not_found=True)
        # A repeated id keeps its first position (and counts once).
        line_ids = list(dict.fromkeys(request.line_ids))
        # Pull every line on the list so we can both validate the request
        # and assign sequences in a single pass.
        all_lines: List[ShoppingListLine] = self.repository.get(ShoppingListLine).all(
            EntityField(ShoppingListLine, "shopping_list_id").eq(shopping_list_id)
        )
        by_id = {l.id: l for l in all_lines}
        mismatched = [lid for lid in line_ids if lid not in by_id]
        if mismatched:
            return ReorderResponse(mismatched=mismatched)

        # Assign new sequences in the order the caller specified. Lines
        # not mentioned keep going after, preserving their relative order.
        next_seq = 0
        seen: set[UUID] = set()
        for lid in line_ids:
            line = by_id[lid]
            line.sequence = next_seq
            next_seq += 1
            seen.add(lid)

        leftovers = sorted(
            (l for l in all_lines if l.id not in seen),
            key=lambda l: l.sequence,
        )
        for line in leftovers:
            line.sequence = next_seq
            next_seq += 1

        self.repository.save_changes()
        return ReorderResponse(reordered_count=len(line_ids))


@SHOPPING_LIST_ROUTER.route("/<uuid:shopping_list_id>/lines/reorder", methods=["POST"])
@has_request_body(ReorderRequest)
def reorder_lines(shopping_list_id: UUID):
    _Request: ReorderRequest = get_request_body()
    _Response = ReorderHandler(SqlAlchemyRepository()).handle(_Request, shopping_list_id)
    if _Response.list_not_found:
        return not_found("ShoppingList", shopping_list_id)
    if _Response.mismatched:
        return bad_request(
            "Some line ids don't belong to this list.",
            detail=", ".join(str(lid) for lid in _Response.mismatched),
        )
    _LOGGER.info(
        f"Reordered {_Response.reordered_count} line(s) on list {shopping_list_id}"
    )
    return no_content()
