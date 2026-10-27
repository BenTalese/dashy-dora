import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dora_api.domain.entities.stock_group import StockGroup
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_item_expiry_event import (
    StockItemExpiryEvent, classify_expiry_transition,
)
from dora_api.domain.entities.stock_level import StockLevel
from dora_api.domain.entities.stock_location import StockLocation
from dora_api.domain.types import EMPTY_UUID
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.features.app_settings.clock import household_today
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.features.stock_items.get_stock_items import (GetStockItemsHandler,
                                                         get_stock_items)
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  created,
                                                  entity_existence_failure)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import (field_of, get_request_body)
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


class CreateStockItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # max_length mirrors the DB column (String(255)) so an over-length name is a
    # clean 422 rather than a DB-layer 500 on Postgres (SQLite would silently
    # accept it) — same class as the FU-520 alert_key truncation fix. The
    # sibling UpdateStockItemRequest already carries this bound.
    name: str = Field(min_length = 1, max_length = 255)
    stock_level_id: UUID
    stock_location_id: UUID | None = None
    stock_group_id: UUID | None = None
    expiry_date: date | None = None
    is_essential: bool = False
    is_open: bool = False
    # Per-item stocktake mute, settable at create time (2026-08-28 feedback).
    # Tri-state on purpose: omitted ⇒ the handler falls back to the install-wide
    # `stocktake_new_items_opt_in` default, so a caller that doesn't render the
    # toggle (the import path, a scan flow) keeps the previous behaviour.
    stocktake_alerts_are_enabled: bool | None = None
    # usual store hint. No clear flag needed — a create has nothing
    # to clear, so omitted/None both mean "no usual store".
    usual_store_id: UUID | None = None

    # Normalise the name at the request boundary: strip surrounding whitespace
    # BEFORE the length checks run, so a whitespace-only name ("   ") collapses
    # to "" and fails min_length (422) instead of being stored, and " Milk "
    # can't masquerade as distinct from "Milk" past the case-insensitive
    # duplicate check. Single authority for every caller of the endpoint.
    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


@dataclass(slots=True)
class CreateStockItemResponse:
    new_stock_item_id: UUID = EMPTY_UUID
    stock_level_not_found: bool = False
    stock_location_not_found: bool = False
    stock_group_not_found: bool = False
    stock_item_already_exists: bool = False


class CreateStockItemHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: CreateStockItemRequest) -> CreateStockItemResponse:
        _StockLevel = self.repository.get(StockLevel).by_id(request.stock_level_id)
        if not _StockLevel:
            return CreateStockItemResponse(stock_level_not_found = True)

        _StockLocation: StockLocation | None = None
        if request.stock_location_id:
            _StockLocation = self.repository.get(StockLocation).by_id(request.stock_location_id)

            if not _StockLocation:
                return CreateStockItemResponse(stock_location_not_found=True)

        # Stock group is optional; we look it up locally so we can pass the
        # entity into the StockItem constructor (saves an extra round-trip
        # from the repository on read later).
        _StockGroup = None
        if request.stock_group_id:
            _StockGroup = self.repository.get(StockGroup).by_id(request.stock_group_id)
            if not _StockGroup:
                return CreateStockItemResponse(stock_group_not_found=True)

        _StockItemName = EntityField(StockItem, StockItem.Fields.NAME)
        _ExistingStockItem: StockItem | None = (
            self.repository
            .get(StockItem)
            .one(_StockItemName.eq(request.name))
        )

        if _ExistingStockItem:
            return CreateStockItemResponse(stock_item_already_exists=True)

        # 2026-08-20 — install-wide default for the per-item mute flag. An
        # explicit value on the request wins (the create dialog's Stocktake
        # toggle, 2026-08-28); omitted still falls back to the install default.
        _StocktakeOptIn = (
            request.stocktake_alerts_are_enabled
            if request.stocktake_alerts_are_enabled is not None
            else bool(getattr(
                get_or_create_app_setting(self.repository),
                "stocktake_new_items_opt_in",
                True,
            ))
        )

        # PROPOSAL_STOCKTAKE_MODE — per-item cadence is no longer a stored
        # field; the queue resolves it from the household default band +
        # Auto self-tuning (R-003, single authority in
        # `features/stocktake/cadence.py`). The per-item flag below is the
        # *mute*: a new item joins the rotation by default (owner call
        # 2026-08-17 — an item you bothered to add is one you want checked;
        # opting each one in by hand was the wrong default) unless the install
        # says otherwise, and the engagement gate still decides when it
        # actually surfaces.
        _NewStockItem = StockItem(
            name = request.name,
            notes = None,
            stock_group = _StockGroup,
            stock_level = _StockLevel,
            # R-021 — wall-clock event (UTC); the schema's `timezone=True` flag
            # is preserved on serialisation via DoraJSONProvider.
            stock_level_last_updated = datetime.now(timezone.utc),
            stock_location = _StockLocation,
            # 2026-08-20 — the default is now an install-wide setting
            # (`AppSetting.stocktake_new_items_opt_in`, default True) rather
            # than a hardcoded True, so an install that counts only a handful
            # of things can opt items in by hand instead.
            stocktake_alerts_are_enabled = _StocktakeOptIn,
            expiry_date = request.expiry_date,
            is_essential = request.is_essential,
            is_open = request.is_open,
            # usual store hint. Not re-validated here for the same reason
            # `update_stock_item` doesn't: the FK is SET NULL ondelete, so a
            # stale id degrades to "no usual store" rather than breaking the
            # item, and the picker only ever offers real rows.
            usual_store_id = request.usual_store_id,
            # R-021 — opened_on is the household calendar day, not server-local.
            opened_on = household_today(self.repository) if request.is_open else None,
        )

        self.repository.add(_NewStockItem)
        # History-tab feed — a "Set expiry" event whenever the item is
        # born with a non-null expiry. `previous_expiry_date=None` is a
        # first-time set, so classify_expiry_transition emits `set`.
        _ExpiryTransition = classify_expiry_transition(None, request.expiry_date)
        if _ExpiryTransition is not None:
            _Kind, _Delta = _ExpiryTransition
            # The event carries an FK to the just-added StockItem. The classic
            # imperative mapping has no relationship linking the two, so the
            # unit-of-work has no reason to insert them in that order; without
            # this flush SQLite's FK check on the event's INSERT fails.
            self.repository.flush()
            self.repository.add(StockItemExpiryEvent(
                stock_item_id = _NewStockItem.id,
                kind = _Kind,
                previous_expiry_date = None,
                new_expiry_date = request.expiry_date,
                delta_days = _Delta,
                occurred_at = datetime.now(timezone.utc),
            ))
        self.repository.save_changes()

        return CreateStockItemResponse(new_stock_item_id = _NewStockItem.id)


@STOCK_ITEM_ROUTER.route("", methods=["POST"])
@has_request_body(CreateStockItemRequest)
def create_stock_item():
    _LOGGER.info("Received request to create stock item.")
    _Handler = CreateStockItemHandler(SqlAlchemyRepository())
    _Request: CreateStockItemRequest = get_request_body()
    _Response = _Handler.handle(_Request)

    if _Response.stock_level_not_found:
        _LOGGER.warning(f"Stock level not found: {_Request.stock_level_id}")
        return entity_existence_failure(StockLevel.__name__, field_of(CreateStockItemRequest, 'stock_level_id'), _Request.stock_level_id)

    if _Response.stock_location_not_found and _Request.stock_location_id:
        _LOGGER.warning(f"Stock location not found: {_Request.stock_location_id}")
        return entity_existence_failure(StockLocation.__name__, field_of(CreateStockItemRequest, 'stock_location_id'), _Request.stock_location_id)

    if _Response.stock_group_not_found and _Request.stock_group_id:
        _LOGGER.warning(f"Stock group not found: {_Request.stock_group_id}")
        # Lazy import — avoids dragging StockGroup into the module's top-
        # level imports just for an error response constant.
        return entity_existence_failure(
            StockGroup.__name__,
            field_of(CreateStockItemRequest, 'stock_group_id'),
            _Request.stock_group_id,
        )

    if _Response.stock_item_already_exists:
        _LOGGER.warning(f"Stock item already exists with name: {_Request.name}")
        return business_rule_violation(f"A stock item with the name '{_Request.name}' already exists.")

    _LOGGER.info(f"Successfully created stock item with ID: {_Response.new_stock_item_id}")
    _Dto = GetStockItemsHandler(SqlAlchemyRepository()).handle_by_id(
        _Response.new_stock_item_id
    )
    return created(
        _Response.new_stock_item_id,
        f"{STOCK_ITEM_ROUTER.name}.{get_stock_items.__name__}",
        "stock_item_id",
        body = _Dto,
    )
