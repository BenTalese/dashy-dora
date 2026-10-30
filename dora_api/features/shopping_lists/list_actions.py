"""Bigger-than-CRUD actions on shopping lists.

Bundled together because they share assumptions ("act on a list", "skip
ticked items where it matters", "pick a default merchant offer"). Splitting
each into its own file would just spread the same imports five ways.

Endpoints:

  POST /api/shopping-lists/<id>/move-unticked-to/<target_id>
      Move every unticked line from the source list onto a target list.
      The source list keeps its ticked lines. Duplicates on the target
      list are skipped (the per-list "unique stock item" invariant).

  (`/refresh-deals` was removed 2026-09-17. It re-validated each line's
   `selected_product_id` and cleared the ones whose product was no longer
   linked — but the detail read already resolves every line's offer from the
   currently linked products and falls back to the cheapest, so the list was
   never showing a dead deal and the endpoint only tidied a column nobody
   read. The tidy now happens where the fact changes, in
   `stock_items/unlink_product_from_stock_item.py`.)

  POST /api/shopping-lists/<id>/clear
      Deletes every line on the list. The list itself stays.

(X5 auto-generate moved to its own module — see auto_generate.py.)
"""
import logging
from dataclasses import dataclass
from typing import List
from uuid import UUID

from dora_api.domain.entities.shopping_list import (ShoppingList,
                                                    ShoppingListLine)
from dora_api.features.routers import SHOPPING_LIST_ROUTER
from dora_api.features.shopping_lists._line_anchor import line_anchor_key
from dora_api.infrastructure.api_response import (business_rule_violation, ok,
                                                  not_found)
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


# ───── Move lines → existing list ─────────────────────────────────────────

@dataclass(slots=True)
class MoveLinesResponse:
    source_not_found: bool = False
    target_not_found: bool = False
    same_list: bool = False
    target_archived: bool = False
    moved_count: int = 0
    skipped_duplicates: int = 0


class MoveLinesHandler:
    """Moves every unticked line from one list onto another: the finish
    flow's offer to carry the leftovers forward. (The bulk-select bar's
    "move exactly these" caller went with the bar; finalisation 03-R23.)"""
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, source_id: UUID, target_id: UUID) -> MoveLinesResponse:
        if source_id == target_id:
            return MoveLinesResponse(same_list=True)

        source = self.repository.get(ShoppingList).by_id(source_id)
        if source is None:
            return MoveLinesResponse(source_not_found=True)
        target = self.repository.get(ShoppingList).by_id(target_id)
        if target is None:
            return MoveLinesResponse(target_not_found=True)
        if target.is_done:
            return MoveLinesResponse(target_archived=True)

        movable: List[ShoppingListLine] = self.repository.get(ShoppingListLine).all(
            EntityField(ShoppingListLine, "shopping_list_id").eq(source_id)
            & EntityField(ShoppingListLine, ShoppingListLine.Fields.IS_TICKED).eq(False)
        )
        target_lines: List[ShoppingListLine] = self.repository.get(ShoppingListLine).all(
            EntityField(ShoppingListLine, "shopping_list_id").eq(target_id)
        )
        # Dedupe on the line's *anchor* — (stock_item_id, product_id) — not
        # `stock_item_id` alone: a product-only line has a NULL item id, so
        # keying on it made every product-only line "a duplicate" of any
        # other and the first one moved blocked the rest (finalisation 03-R3).
        target_anchors = {line_anchor_key(l) for l in target_lines}
        next_sequence = (max((l.sequence for l in target_lines), default=-1)) + 1

        moved = 0
        skipped = 0
        for line in movable:
            anchor = line_anchor_key(line)
            if anchor in target_anchors:
                # Don't merge quantities here — that's a separate UX
                # decision; the unique-per-line invariant wins for now.
                # Source line stays put.
                skipped += 1
                continue
            line.shopping_list_id = target_id
            line.sequence = next_sequence
            # A line set aside by the budget is a leftover like any other
            # (owner, 2026-10-30, FU-958): it arrives on the next list as
            # something to buy. That trim was about the old shop's budget.
            line.deferred_by_budget = False
            target_anchors.add(anchor)
            next_sequence += 1
            moved += 1

        self.repository.save_changes()
        return MoveLinesResponse(moved_count=moved, skipped_duplicates=skipped)


@SHOPPING_LIST_ROUTER.route(
    "/<uuid:source_id>/move-unticked-to/<uuid:target_id>", methods=["POST"]
)
def move_unticked_to(source_id: UUID, target_id: UUID):
    _Response = MoveLinesHandler(SqlAlchemyRepository()).handle(source_id, target_id)
    _Error = _move_error_response(_Response, source_id, target_id)
    if _Error is not None:
        return _Error
    _LOGGER.info(
        f"Moved {_Response.moved_count} unticked line(s) from {source_id} -> {target_id} "
        f"({_Response.skipped_duplicates} duplicates skipped)"
    )
    return ok({
        "moved_count": _Response.moved_count,
        "skipped_duplicates": _Response.skipped_duplicates,
    })


def _move_error_response(
    response: MoveLinesResponse, source_id: UUID, target_id: UUID
):
    """None when the move succeeded; otherwise the error to return."""
    if response.source_not_found:
        return not_found("ShoppingList (source)", source_id)
    if response.target_not_found:
        return not_found("ShoppingList (target)", target_id)
    if response.same_list:
        return business_rule_violation("Source and target lists are the same.")
    if response.target_archived:
        return business_rule_violation(
            "Cannot move items to an archived list. Unarchive it first."
        )
    return None


# ───── Clear all lines ────────────────────────────────────────────────────

@dataclass(slots=True)
class ClearListResponse:
    not_found: bool = False
    removed_count: int = 0


class ClearListHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, shopping_list_id: UUID) -> ClearListResponse:
        lst = self.repository.get(ShoppingList).by_id(shopping_list_id)
        if lst is None:
            return ClearListResponse(not_found=True)
        lines: List[ShoppingListLine] = self.repository.get(ShoppingListLine).all(
            EntityField(ShoppingListLine, "shopping_list_id").eq(shopping_list_id)
        )
        for line in lines:
            self.repository.remove(line)
        self.repository.save_changes()
        return ClearListResponse(removed_count=len(lines))


@SHOPPING_LIST_ROUTER.route("/<uuid:shopping_list_id>/clear", methods=["POST"])
def clear_list(shopping_list_id: UUID):
    _Response = ClearListHandler(SqlAlchemyRepository()).handle(shopping_list_id)
    if _Response.not_found:
        return not_found("ShoppingList", shopping_list_id)
    _LOGGER.info(f"Cleared {_Response.removed_count} lines from list {shopping_list_id}")
    return ok({"removed_count": _Response.removed_count})


# ───── Discard the unticked lines ─────────────────────────────────────────

@dataclass(slots=True)
class DiscardUntickedResponse:
    not_found: bool = False
    removed_count: int = 0


class DiscardUntickedHandler:
    """Deletes every unticked line on a list.

    The finish flow's third disposition, alongside move-to-existing and
    move-to-new. A finished list is a receipt, and a receipt doesn't record
    what you didn't buy — leaving the leftovers in place stranded them on an
    archived list forever and kept them counted in the dashboard's "queued"
    card. So the finish dialog now makes the user choose, and this is the
    "I didn't want them after all" branch.

    One request rather than a delete-per-line loop: the same reason the bulk
    endpoints exist.
    """
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, shopping_list_id: UUID) -> DiscardUntickedResponse:
        lst = self.repository.get(ShoppingList).by_id(shopping_list_id)
        if lst is None:
            return DiscardUntickedResponse(not_found=True)
        lines: List[ShoppingListLine] = self.repository.get(ShoppingListLine).all(
            EntityField(ShoppingListLine, "shopping_list_id").eq(shopping_list_id)
            & EntityField(ShoppingListLine, ShoppingListLine.Fields.IS_TICKED).eq(False)
        )
        for line in lines:
            self.repository.remove(line)
        self.repository.save_changes()
        return DiscardUntickedResponse(removed_count=len(lines))


@SHOPPING_LIST_ROUTER.route(
    "/<uuid:shopping_list_id>/discard-unticked", methods=["POST"]
)
def discard_unticked(shopping_list_id: UUID):
    _Response = DiscardUntickedHandler(SqlAlchemyRepository()).handle(shopping_list_id)
    if _Response.not_found:
        return not_found("ShoppingList", shopping_list_id)
    _LOGGER.info(
        f"Discarded {_Response.removed_count} unticked line(s) from list {shopping_list_id}"
    )
    return ok({"removed_count": _Response.removed_count})
