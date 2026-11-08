"""Create / update / delete / archive / copy / finish for ShoppingList.

Bundled into one file because most of these handlers are 10-20 lines and
they share the list-status lifecycle (active → done); keeping
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
    SHOPPING_LIST_STATUS_DONE, ShoppingList, ShoppingListLine)
from dora_api.features.routers import SHOPPING_LIST_ROUTER
from dora_api.features.shopping_lists._line_retention import \
    snapshot_line_display_names
from dora_api.features.shopping_lists._restock import restock_stock_items
from dora_api.features.shopping_lists.get_shopping_lists import get_shopping_lists
from dora_api.features.shopping_lists.manage_shopping_list_lines import \
    snapshot_offer_rrp
from dora_api.features.shopping_lists._observation_sync import (
    sync_line_observations)
from dora_api.features.shopping_lists._usual_price import snapshot_usual_prices
from dora_api.infrastructure.api_response import (created, no_content,
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
    # Pass an ISO date to set, or `null` (explicit) to clear.
    # Field unset on the wire = leave the existing value alone.
    planned_shop_date: date | None = None


@dataclass(slots=True)
class UpdateShoppingListResponse:
    not_found: bool = False


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


# ───── Finish ─────────────────────────────────────────────────────────────

class FinishShoppingListRequest(BaseModel):
    # Nothing to configure: the per-item level picker (UX-v2 M12) was cut,
    # see FU-582, and leftovers are moved or discarded before this is called.
    model_config = ConfigDict(extra="forbid")


@dataclass(slots=True)
class FinishShoppingListResponse:
    not_found: bool = False
    ticked_lines: int = 0


class FinishShoppingListHandler:
    """Marks the list as done and freezes it as a receipt: prices harvested,
    names frozen. Ticking already restocked each item (UX v5 D1); a line
    ticked before restock-on-tick existed (`restocked_at` is None) is
    restocked here instead, so no tick is ever lost. Unticked lines stay on
    the done list unless the caller moved or discarded them first.
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
        # The household's own usual price, the baseline Reports measures
        # savings from (FU-831). Before the harvest below, so this shop's
        # prices aren't part of their own baseline.
        snapshot_usual_prices(self.repository, ticked_lines, now=now)

        restock_stock_items(
            self.repository,
            (l.stock_item_id for l in ticked_lines if l.restocked_at is None),
            now=now,
        )
        # Distinct items: a nested product line shares its parent's item.
        updated = len({l.stock_item_id for l in ticked_lines if l.stock_item_id is not None})

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
