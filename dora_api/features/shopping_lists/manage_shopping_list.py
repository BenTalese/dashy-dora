"""Create / update / delete / archive / copy / finish for ShoppingList.

Bundled into one file because most of these handlers are 10-20 lines and
they share the list-status lifecycle (draft → shopping → done) — keeping
them together makes that contract obvious. Finish + copy live here too because they're
shopping-list-scoped actions, not line-scoped.
"""
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import update

from dora_api.domain.entities.shopping_list import (
    SHOPPING_LIST_STATUS_DONE, SHOPPING_LIST_STATUS_DRAFT,
    SHOPPING_LIST_STATUS_SHOPPING, SHOPPING_LIST_STATUS_VALUES, ShoppingList,
    ShoppingListLine)
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_level import StockLevel
from dora_api.domain.stock_status import StockStatus, level_for_status
from dora_api.features.routers import SHOPPING_LIST_ROUTER
from dora_api.features.shopping_lists._line_defaults import apply_line_defaults
from dora_api.features.shopping_lists._line_retention import \
    snapshot_line_display_names
from dora_api.features.shopping_lists.get_shopping_lists import get_shopping_lists
from dora_api.features.shopping_lists.manage_shopping_list_lines import \
    snapshot_offer_rrp
from dora_api.features.shopping_lists._observation_sync import (
    sync_line_observations)
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  created, no_content,
                                                  not_found, ok)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


# ───── Create ─────────────────────────────────────────────────────────────

class CreateShoppingListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, max_length=255)
    # Optional shop day for this list.
    planned_shop_date: date | None = None


@dataclass(slots=True)
class CreateShoppingListResponse:
    shopping_list_id: UUID | None = None


class CreateShoppingListHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: CreateShoppingListRequest) -> CreateShoppingListResponse:
        now = datetime.now(timezone.utc)
        # No auto-materialised date name (UX-v2): name stays NULL unless the
        # user typed one, and the API serves a date-derived display_name that
        # tracks the planned shop date if one is set later.
        name = (request.name or "").strip() or None
        new_list = ShoppingList(
            name=name,
            created_at=now,
            planned_shop_date=request.planned_shop_date,
        )
        self.repository.add(new_list)
        self.repository.save_changes()
        return CreateShoppingListResponse(shopping_list_id=new_list.id)


@SHOPPING_LIST_ROUTER.route("", methods=["POST"])
@has_request_body(CreateShoppingListRequest)
def create_shopping_list():
    _Request: CreateShoppingListRequest = get_request_body()
    _Response = CreateShoppingListHandler(SqlAlchemyRepository()).handle(_Request)
    _LOGGER.info(f"Created shopping list {_Response.shopping_list_id}")
    return created(
        _Response.shopping_list_id,
        f"{SHOPPING_LIST_ROUTER.name}.{get_shopping_lists.__name__}",
        "shopping_list_id",
        body={"shopping_list_id": _Response.shopping_list_id},
    )


# ───── Update ─────────────────────────────────────────────────────────────

class UpdateShoppingListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Pass a string to set, or explicit `null` to clear the custom name (the
    # list then self-labels from its dates via display_name). Field unset on
    # the wire = leave the existing value alone — same convention as
    # planned_shop_date below.
    name: str | None = Field(default=None, max_length=255)
    # Lifecycle status (draft / shopping / done). Setting it to/from `done`
    # also manages completed_at. Note: this is the plain status edit — the
    # restock-and-snapshot Finish flow lives in /finish, not here.
    status: str | None = None
    # Pass an ISO date to set, or `null` (explicit) to clear.
    # Field unset on the wire = leave the existing value alone.
    planned_shop_date: date | None = None


@dataclass(slots=True)
class UpdateShoppingListResponse:
    not_found: bool = False
    invalid_status: bool = False
    done_via_finish: bool = False


class UpdateShoppingListHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: UpdateShoppingListRequest, shopping_list_id: UUID) -> UpdateShoppingListResponse:
        lst: ShoppingList | None = self.repository.get(ShoppingList).by_id(shopping_list_id)
        if lst is None:
            return UpdateShoppingListResponse(not_found=True)

        set_fields = request.model_fields_set
        # Explicit `null` (or a blank string) clears the custom name;
        # field absent = no change.
        if "name" in set_fields:
            lst.name = (request.name or "").strip() or None
        if "status" in set_fields and request.status is not None:
            if request.status not in SHOPPING_LIST_STATUS_VALUES:
                return UpdateShoppingListResponse(invalid_status=True)
            # E3 (FU-227 chunk 5): /finish is the ONLY path to `done` — it's
            # what snapshots prices, harvests observations and bumps stock
            # levels. The SPA never PATCHes `status=done`; this guard makes
            # that contract enforceable (no half-baked done list that skipped
            # the restock review). draft⇄shopping still flow through here.
            if request.status == SHOPPING_LIST_STATUS_DONE:
                return UpdateShoppingListResponse(done_via_finish=True)
            lst.status = request.status
            lst.completed_at = None
        # Chunk 7: explicit `null` clears the date; field absent = no change.
        if "planned_shop_date" in set_fields:
            lst.planned_shop_date = request.planned_shop_date

        self.repository.save_changes()
        return UpdateShoppingListResponse()


@SHOPPING_LIST_ROUTER.route("/<uuid:shopping_list_id>", methods=["PATCH"])
@has_request_body(UpdateShoppingListRequest)
def update_shopping_list(shopping_list_id: UUID):
    _Request: UpdateShoppingListRequest = get_request_body()
    _Response = UpdateShoppingListHandler(SqlAlchemyRepository()).handle(_Request, shopping_list_id)
    if _Response.not_found:
        return not_found("ShoppingList", shopping_list_id)
    if _Response.invalid_status:
        return business_rule_violation(
            "`status` must be one of: draft, shopping."
        )
    if _Response.done_via_finish:
        return business_rule_violation(
            "A list becomes done by finishing it: POST /finish (which "
            "snapshots prices and restocks), not PATCH status=done."
        )
    _LOGGER.info(f"Updated shopping list {shopping_list_id}")
    return no_content()


# ───── Delete ─────────────────────────────────────────────────────────────

@dataclass(slots=True)
class DeleteShoppingListResponse:
    not_found: bool = False


class DeleteShoppingListHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, shopping_list_id: UUID) -> DeleteShoppingListResponse:
        lst: ShoppingList | None = self.repository.get(ShoppingList).by_id(shopping_list_id)
        if lst is None:
            return DeleteShoppingListResponse(not_found=True)
        self.repository.remove(lst)
        self.repository.save_changes()
        return DeleteShoppingListResponse()


@SHOPPING_LIST_ROUTER.route("/<uuid:shopping_list_id>", methods=["DELETE"])
def delete_shopping_list(shopping_list_id: UUID):
    _Response = DeleteShoppingListHandler(SqlAlchemyRepository()).handle(shopping_list_id)
    if _Response.not_found:
        return not_found("ShoppingList", shopping_list_id)
    _LOGGER.info(f"Deleted shopping list {shopping_list_id}")
    return no_content()


# ───── Finish (restock review) ────────────────────────────────────────────

class FinishShoppingListRequest(BaseModel):
    # Finishing a list means you bought the items, so every ticked line
    # restocks to Stocked. There is deliberately nothing to configure —
    # the per-item level picker (UX-v2 M12) was cut, see FU-582.
    model_config = ConfigDict(extra="forbid")


@dataclass(slots=True)
class FinishShoppingListResponse:
    not_found: bool = False
    ticked_lines: int = 0


class FinishShoppingListHandler:
    """Marks the list as done. For every ticked line, set the linked stock
    item's stock level to Stocked — you just bought it. Untouched lines are
    left on the now-done list — the caller can copy them to a new list or
    use the "move unchecked" flow.
    """

    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: FinishShoppingListRequest, shopping_list_id: UUID) -> FinishShoppingListResponse:
        lst: ShoppingList | None = self.repository.get(ShoppingList).by_id(shopping_list_id)
        if lst is None:
            return FinishShoppingListResponse(not_found=True)
        # Idempotent: a repeat POST (double-tap, retry) must not re-stock
        # every ticked item, re-harvest prices or move completed_at.
        if lst.is_done:
            return FinishShoppingListResponse()

        # The `is_done` read above is only the fast path — on its own it is
        # check-then-act, and two devices finishing at the same instant both
        # passed it and both restocked + harvested. Claim the transition with
        # a conditional UPDATE instead: the database serialises the two
        # writers on the row, and only the one that actually flips the status
        # goes on to restock. The loser gets the idempotent "nothing
        # restocked" answer, same as a late double-tap.
        now = datetime.now(timezone.utc)
        claimed = self.repository.session.execute(
            update(ShoppingList)
            .where(
                (ShoppingList.id == shopping_list_id)
                & (ShoppingList.status != SHOPPING_LIST_STATUS_DONE)
            )
            .values(status=SHOPPING_LIST_STATUS_DONE, completed_at=now)
        )
        if (claimed.rowcount or 0) == 0:
            self.repository.session.rollback()
            return FinishShoppingListResponse()

        ticked_lines = self.repository.get(ShoppingListLine).all(
            EntityField(ShoppingListLine, "shopping_list_id").eq(shopping_list_id)
            & EntityField(ShoppingListLine, ShoppingListLine.Fields.IS_TICKED).eq(True)
        )

        # Finishing no longer back-fills a *price* from the shop's offer
        # (2026-09-17). It used to, so that every finished list contributed
        # something to reports — but what it contributed was an advertised
        # price the user had never confirmed, recorded as money they spent. A
        # list finished with no prices entered now records no spend, which is
        # the owner's call and the honest one: "that's up to the user".
        #
        # The offer's **RRP** is still frozen, on lines that carry a price the
        # user entered: that is what "you saved $4 against the shelf price"
        # is measured from, and it is context for their number rather than a
        # replacement for it.
        for line in ticked_lines:
            snapshot_offer_rrp(self.repository, line)

        # Resolve the restock target once, by status identity, not name.
        all_levels = self.repository.get(StockLevel).all()
        stocked = level_for_status(all_levels, StockStatus.STOCKED)

        updated = 0
        if ticked_lines and stocked is not None:
            stock_item_ids = [l.stock_item_id for l in ticked_lines if l.stock_item_id]
            stock_items = self.repository.get(StockItem).all(
                EntityField(StockItem, "id").in_(stock_item_ids)
            ) if stock_item_ids else []
            for item in stock_items:
                item.stock_level = stocked
                item.stock_level_last_updated = now
                updated += 1

        # harvest a price observation per priced ticked line
        # (the closed loop: confirm what you paid at the till → it feeds "Your
        # prices"). After the snapshot loop above so the picked-offer fallback
        # is populated; before the status flip so the harvest shares the single
        # save_changes transaction below.
        sync_line_observations(self.repository, ticked_lines)

        # FU-883 — freeze each line's display name as the list becomes a
        # receipt, so a later stock-item/product delete leaves a readable
        # historic line instead of a nameless row (which is why those FKs
        # used to CASCADE the line away entirely). Every line on the list,
        # not just the ticked ones: unticked lines stay on a done list.
        all_lines = self.repository.get(ShoppingListLine).all(
            EntityField(ShoppingListLine, "shopping_list_id").eq(shopping_list_id)
        )
        snapshot_line_display_names(self.repository, all_lines)

        # status + completed_at were written by the claiming UPDATE above;
        # this commit lands them together with the restock and the harvest.
        self.repository.save_changes()
        return FinishShoppingListResponse(ticked_lines=updated)


@SHOPPING_LIST_ROUTER.route("/<uuid:shopping_list_id>/finish", methods=["POST"])
@has_request_body(FinishShoppingListRequest)
def finish_shopping_list(shopping_list_id: UUID):
    _Request: FinishShoppingListRequest = get_request_body() or FinishShoppingListRequest()
    _Response = FinishShoppingListHandler(SqlAlchemyRepository()).handle(_Request, shopping_list_id)
    if _Response.not_found:
        return not_found("ShoppingList", shopping_list_id)
    _LOGGER.info(
        f"Finished shopping list {shopping_list_id}: "
        f"{_Response.ticked_lines} items restocked"
    )
    return ok({"items_restocked": _Response.ticked_lines})


# ───── Copy ────────────────────────────────────────────────────────────────

class CopyShoppingListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # If "all", copy every line. If "unticked", only the lines that weren't
    # ticked off (useful for "move unchecked to new list" flow).
    include: str = "all"
    name: str | None = Field(default=None, max_length=255)


@dataclass(slots=True)
class CopyShoppingListResponse:
    not_found: bool = False
    new_shopping_list_id: UUID | None = None


class CopyShoppingListHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: CopyShoppingListRequest, shopping_list_id: UUID) -> CopyShoppingListResponse:
        source: ShoppingList | None = self.repository.get(ShoppingList).by_id(shopping_list_id)
        if source is None:
            return CopyShoppingListResponse(not_found=True)

        source_lines = self.repository.get(ShoppingListLine).all(
            EntityField(ShoppingListLine, "shopping_list_id").eq(shopping_list_id)
        )
        if request.include == "unticked":
            source_lines = [l for l in source_lines if not l.is_ticked]

        now = datetime.now(timezone.utc)
        target = ShoppingList(
            # display_name, not raw name — the source may be self-labelled
            # (name NULL), and "Copy of Sat 14 Jun" beats "Copy of None".
            name = (request.name or "").strip() or f"Copy of {source.display_name}",
            created_at = now,
        )
        self.repository.add(target)

        # Both anchors and every "which one" / store choice travel, so a
        # product-only line copies (it used to lose both anchors and 500 on the
        # line-anchor check, finalisation 03-R1).
        copies = [
            ShoppingListLine(
                shopping_list_id = target.id,
                stock_item_id = sl.stock_item_id,
                product_id = sl.product_id,
                display_name_snapshot = sl.display_name_snapshot,
                quantity = sl.quantity,
                is_ticked = False,  # fresh list starts unticked
                selected_product_id = sl.selected_product_id,
                preferred_buy_id = sl.preferred_buy_id,
                planned_store_id = sl.planned_store_id,
                sequence = sl.sequence,
                added_at = now,
            )
            for sl in source_lines
        ]
        apply_line_defaults(self.repository, copies)
        for line in copies:
            self.repository.add(line)
        # FU-512 unit-of-work: one commit at the end.
        self.repository.save_changes()
        return CopyShoppingListResponse(new_shopping_list_id=target.id)


@SHOPPING_LIST_ROUTER.route("/<uuid:shopping_list_id>/copy", methods=["POST"])
@has_request_body(CopyShoppingListRequest)
def copy_shopping_list(shopping_list_id: UUID):
    _Request: CopyShoppingListRequest = get_request_body()
    if _Request.include not in ("all", "unticked"):
        return business_rule_violation("`include` must be 'all' or 'unticked'.")
    _Response = CopyShoppingListHandler(SqlAlchemyRepository()).handle(_Request, shopping_list_id)
    if _Response.not_found:
        return not_found("ShoppingList", shopping_list_id)
    _LOGGER.info(
        f"Copied shopping list {shopping_list_id} -> {_Response.new_shopping_list_id}"
    )
    return ok({"shopping_list_id": _Response.new_shopping_list_id})


# ───── Start shopping ─────────────────────────────────────────────────────
# A dedicated endpoint (not a generic PATCH) because the transition is
# meaningful enough to log and defend invariants around (e.g. can't start a
# done list). The old /stop ("pause") endpoint was removed in UX-v2: the
# lifecycle is Start shopping → Finish & restock (→ Reopen), and the merged
# single page has no separate shop surface to exit from.

@dataclass(slots=True)
class StartShoppingResponse:
    not_found: bool = False
    archived: bool = False


class StartShoppingHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, shopping_list_id: UUID) -> StartShoppingResponse:
        lst: ShoppingList | None = self.repository.get(ShoppingList).by_id(shopping_list_id)
        if lst is None:
            return StartShoppingResponse(not_found=True)
        if lst.is_done:
            return StartShoppingResponse(archived=True)
        lst.status = SHOPPING_LIST_STATUS_SHOPPING
        self.repository.save_changes()
        return StartShoppingResponse()


# ───── Back to draft ──────────────────────────────────────────────────────
# The reverse of Start shopping, added 2026-09-17 (owner: *"No way to go back
# to draft mode from shop mode? Sometimes there are accidents."*). It is not
# the old /stop "pause" endpoint coming back: that existed because UX-v2 had a
# separate shop *surface* to exit from, and it left a half-shopped list in a
# state of its own. This is an undo for pressing the wrong button.
#
# **It unticks everything**, and the client says so before calling. A draft has
# no tick model at all — the picker shows a plain item count for a draft and a
# ratio only once shopping starts — so ticks have nowhere to live on the other
# side of this transition. Keeping them hidden would leave a draft quietly
# holding state the user can neither see nor edit, which is worse than the
# honest reset.
#
# A finished list is still final: `done` is not reversible here, because the
# restock it drove has already moved stock and undoing that is a different
# (and much larger) question than "I mis-tapped".

@dataclass(slots=True)
class BackToDraftResponse:
    not_found: bool = False
    archived: bool = False
    unticked_count: int = 0


class BackToDraftHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, shopping_list_id: UUID) -> BackToDraftResponse:
        lst: ShoppingList | None = self.repository.get(ShoppingList).by_id(shopping_list_id)
        if lst is None:
            return BackToDraftResponse(not_found=True)
        if lst.is_done:
            return BackToDraftResponse(archived=True)

        lines: list[ShoppingListLine] = self.repository.get(ShoppingListLine).all(
            EntityField(ShoppingListLine, "shopping_list_id").eq(shopping_list_id)
            & EntityField(ShoppingListLine, ShoppingListLine.Fields.IS_TICKED).eq(True)
        )
        for line in lines:
            line.is_ticked = False
        lst.status = SHOPPING_LIST_STATUS_DRAFT
        self.repository.save_changes()
        return BackToDraftResponse(unticked_count=len(lines))


@SHOPPING_LIST_ROUTER.route("/<uuid:shopping_list_id>/back-to-draft", methods=["POST"])
def back_to_draft(shopping_list_id: UUID):
    _Response = BackToDraftHandler(SqlAlchemyRepository()).handle(shopping_list_id)
    if _Response.not_found:
        return not_found("ShoppingList", shopping_list_id)
    if _Response.archived:
        return business_rule_violation(
            "A finished list can't go back to draft."
        )
    _LOGGER.info(
        f"List {shopping_list_id} returned to draft "
        f"({_Response.unticked_count} lines unticked)"
    )
    return ok({"unticked_count": _Response.unticked_count})


@SHOPPING_LIST_ROUTER.route("/<uuid:shopping_list_id>/start", methods=["POST"])
def start_shopping(shopping_list_id: UUID):
    _Response = StartShoppingHandler(SqlAlchemyRepository()).handle(shopping_list_id)
    if _Response.not_found:
        return not_found("ShoppingList", shopping_list_id)
    if _Response.archived:
        return business_rule_violation(
            "Cannot start shopping on a finished list."
        )
    _LOGGER.info(f"Started shopping on list {shopping_list_id}")
    return no_content()
