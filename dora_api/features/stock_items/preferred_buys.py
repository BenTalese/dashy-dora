"""Preferred-buys CRUD for a stock item (FU-211 / PROPOSAL_PRODUCTS_AS_OVERLAY §3.1).

Free-text "what I actually buy" reminders owned by a stock item — the everyday
counterpart to the power-user Product overlay. Always available (NOT gated by
the products or money features). Grouped here as one cohesive small surface
(add / rename / delete) rather than a file per verb.

FU-225 (2026-06-18): the manual reorder UI was retired; the SPA now sorts
alphabetically client-side. The `position` column + `reorder` endpoint were
removed at the same time.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.preferred_buy import PreferredBuy
from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.infrastructure.api_response import (bad_request, no_content,
                                                  not_found)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


class AddPreferredBuyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=255)


class UpdatePreferredBuyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=255)


@dataclass(slots=True)
class PreferredBuyMutationResponse:
    stock_item_not_found: bool = False
    preferred_buy_not_found: bool = False
    empty_label: bool = False


class PreferredBuyHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def _scoped(self, stock_item_id: UUID, preferred_buy_id: UUID) -> PreferredBuy | None:
        # Scope the lookup to the stock item so a mismatched pair 404s rather
        # than letting one item edit another's reminders.
        return self.repository.get(PreferredBuy).one(
            EntityField(PreferredBuy, "id").eq(preferred_buy_id)
            & EntityField(PreferredBuy, PreferredBuy.Fields.STOCK_ITEM_ID).eq(stock_item_id)
        )

    def add(self, stock_item_id: UUID, request: AddPreferredBuyRequest) -> PreferredBuyMutationResponse:
        if not self.repository.get(StockItem).exists(stock_item_id):
            return PreferredBuyMutationResponse(stock_item_not_found=True)
        label = request.label.strip()
        if not label:
            return PreferredBuyMutationResponse(empty_label=True)
        self.repository.add(PreferredBuy(
            stock_item_id=stock_item_id,
            label=label,
            created_at=datetime.now(timezone.utc),
        ))
        self.repository.save_changes()
        return PreferredBuyMutationResponse()

    def rename(
        self, stock_item_id: UUID, preferred_buy_id: UUID, request: UpdatePreferredBuyRequest
    ) -> PreferredBuyMutationResponse:
        match = self._scoped(stock_item_id, preferred_buy_id)
        if match is None:
            return PreferredBuyMutationResponse(preferred_buy_not_found=True)
        label = request.label.strip()
        if not label:
            return PreferredBuyMutationResponse(empty_label=True)
        match.label = label
        self.repository.save_changes()
        return PreferredBuyMutationResponse()

    def delete(self, stock_item_id: UUID, preferred_buy_id: UUID) -> PreferredBuyMutationResponse:
        match = self._scoped(stock_item_id, preferred_buy_id)
        if match is None:
            return PreferredBuyMutationResponse(preferred_buy_not_found=True)
        self.repository.remove(match)
        self.repository.save_changes()
        return PreferredBuyMutationResponse()


@STOCK_ITEM_ROUTER.route("<uuid:stock_item_id>/preferred-buys", methods=["POST"])
@has_request_body(AddPreferredBuyRequest)
def add_preferred_buy(stock_item_id: UUID):
    _Handler = PreferredBuyHandler(SqlAlchemyRepository())
    _Request: AddPreferredBuyRequest = get_request_body()
    _Response = _Handler.add(stock_item_id, _Request)
    if _Response.stock_item_not_found:
        return not_found(StockItem.__name__, stock_item_id)
    if _Response.empty_label:
        return bad_request("A preferred buy needs a label.")
    _LOGGER.info("Added preferred buy to stock item %s", stock_item_id)
    return no_content()


@STOCK_ITEM_ROUTER.route("<uuid:stock_item_id>/preferred-buys/<uuid:preferred_buy_id>", methods=["PATCH"])
@has_request_body(UpdatePreferredBuyRequest)
def update_preferred_buy(stock_item_id: UUID, preferred_buy_id: UUID):
    _Handler = PreferredBuyHandler(SqlAlchemyRepository())
    _Request: UpdatePreferredBuyRequest = get_request_body()
    _Response = _Handler.rename(stock_item_id, preferred_buy_id, _Request)
    if _Response.preferred_buy_not_found:
        return not_found(PreferredBuy.__name__, preferred_buy_id)
    if _Response.empty_label:
        return bad_request("A preferred buy needs a label.")
    return no_content()


@STOCK_ITEM_ROUTER.route("<uuid:stock_item_id>/preferred-buys/<uuid:preferred_buy_id>", methods=["DELETE"])
def delete_preferred_buy(stock_item_id: UUID, preferred_buy_id: UUID):
    _Handler = PreferredBuyHandler(SqlAlchemyRepository())
    _Response = _Handler.delete(stock_item_id, preferred_buy_id)
    if _Response.preferred_buy_not_found:
        return not_found(PreferredBuy.__name__, preferred_buy_id)
    return no_content()
