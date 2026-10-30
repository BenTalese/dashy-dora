
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dora_api.domain.entities.app_setting import AppSetting
from dora_api.domain.entities.nutrition_food import NutritionFood
from dora_api.domain.entities.consumption_event import (
    CONSUMPTION_SOURCE_COOK, CONSUMPTION_SOURCE_MANUAL,
    CONSUMPTION_SOURCE_WASTE, ConsumptionEvent,
)
from dora_api.domain.entities.recipe import Recipe
from dora_api.domain.entities.stock_group import StockGroup
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_level import StockLevel
from dora_api.domain.entities.stock_level_change import StockLevelChange
from dora_api.domain.entities.stock_location import StockLocation
from dora_api.domain.entities.store import Store
from dora_api.domain.stock_status import needs_restock
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.features.app_settings.clock import household_today
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  entity_existence_failure,
                                                  no_content, not_found, ok)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.features.shopping_lists._line_defaults import apply_line_defaults
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.features.stock_items.expiry_change import apply_expiry_change

_LOGGER = logging.getLogger(__name__)


class UpdateStockItemRequest(BaseModel):
    """Partial update — only fields present in the request body are applied.

    `stock_level_id` and `name` have special handling. Everything else is
    treated as a straight setattr.
    """
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default = None, min_length = 1, max_length = 255)
    notes: str | None = Field(default = None, max_length = 255)
    # PROPOSAL_STOCKTAKE_MODE — the old per-item `days_until_stocktake_alert`
    # dial was retired in the 2026-07-04 cleanup. `stocktake_alerts_are_
    # enabled` is now the only per-item stocktake field (Mute toggle).
    stocktake_alerts_are_enabled: bool | None = None
    stock_level_id: UUID | None = None
    stock_location_id: UUID | None = None
    stock_group_id: UUID | None = None
    expiry_date: date | None = None
    is_essential: bool | None = None
    is_open: bool | None = None
    # Explicit override for `opened_on` — usually set automatically when
    # `is_open` flips True, but the spec also wants a manual edit path
    # ("I can edit the date a stock item was opened on…").
    opened_on: date | None = None
    # usual store hint. Send a UUID to bind, omit to leave alone;
    # send `clear_usual_store=true` to blank an existing value (the same
    # clear-vs-unset pattern as ShoppingListLine fields).
    usual_store_id: UUID | None = None
    clear_usual_store: bool = False
    # Nutrition complex-mode link (the food whose per-100g values describe this
    # item). Same clear-vs-unset shape as `usual_store_id` above: send a UUID to
    # bind, omit to leave alone, `clear_nutrition_food=true` to unlink. Only
    # ever set from the picker's explicit confirm — a name match is a
    # suggestion, never a saved link (P12 No-invent).
    nutrition_food_id: UUID | None = None
    clear_nutrition_food: bool = False
    # "Never suggest a food for this one" — the opt-out behind the auto-matcher
    # (dish soap has no calories). A plain tri-state bool rather than a clear
    # flag: unlike the FK above there's no difference between "set it to false"
    # and "clear it", so the omitted-means-leave-alone default is enough.
    nutrition_ignored: bool | None = None
    # Explicit clear flags for location and group — the relationships are
    # mapped `lazy="noload"`, so assigning the relationship-side to None
    # is a silent no-op (the FK column never goes dirty). The clear-flag
    # path drives the FK column directly, sidestepping the SQLAlchemy
    # quirk so the picker's X button actually persists.
    clear_stock_location: bool = False
    clear_stock_group: bool = False
    # consumption context. When a level DROP accompanies
    # this update (e.g. the cook-mode finish dialog marking an ingredient
    # down), the handler records a ConsumptionEvent so run-out prediction +
    # the Zero-Input Pantry belief can blend cooking with purchases. Only
    # honoured when the level actually drops; a valid `consumption_source`
    # is one of the CONSUMPTION_SOURCE_* markers. `consumption_recipe_id`
    # attributes the depletion to a recipe (denormalised name captured
    # server-side so history survives a recipe delete).
    consumption_source: str | None = None
    consumption_recipe_id: UUID | None = None

    # Normalise the name the same way create does — strip surrounding
    # whitespace before the length checks, so a rename to "   " is a 422 and
    # " Milk " can't dodge the case-insensitive duplicate check. None (field
    # omitted) passes through untouched (partial-update semantics).
    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


@dataclass(slots=True)
class UpdateStockItemResponse:  # noqa: D401
    stock_item_already_exists: bool = False
    stock_item_not_found: bool = False
    stock_level_not_found: bool = False
    stock_location_not_found: bool = False
    stock_group_not_found: bool = False
    usual_store_not_found: bool = False
    nutrition_food_not_found: bool = False
    # When the auto-add hook fires (FU-511: driven by AppSetting.auto_add_mode
    # + this item's is_essential), the API needs to know so it can surface an
    # undoable "Tomato Soup auto-added to <list>" notification. None when no
    # auto-add happened.
    auto_added_line_id: UUID | None = None
    auto_added_to_list_id: UUID | None = None


class UpdateStockItemHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: UpdateStockItemRequest, stock_item_id: UUID) -> UpdateStockItemResponse:
        # `.include(STOCK_LEVEL)` is load-bearing (FU-533): `stock_level` is a
        # lazy="noload" relationship, so a plain `by_id()` load left
        # `_PreviousLevel` below always None. That silently (a) appended a
        # StockLevelChange history row on EVERY level PATCH (the id != None
        # guard always passed → "Stocked → Stocked" noise) and (b) dropped
        # every depletion ConsumptionEvent (the recorder bails when the
        # previous sequence is None) — the P8-07/FU-449 cook-mode depletion
        # leg wrote nothing. Eager-loading the current level fixes both.
        _StockItem: StockItem | None = (
            self.repository.get(StockItem)
            .include(StockItem.Fields.STOCK_LEVEL)
            .by_id(stock_item_id)
        )
        if not _StockItem:
            return UpdateStockItemResponse(stock_item_not_found = True)

        _SetFields = request.model_fields_set

        # Capture the *previous* stock level so we can detect the
        # specific transition the auto-add hook cares about (something
        # not-yet-restock-needing dropping to low/out). Kept as the
        # loaded StockLevel entity so both branches — the transition
        # check below and the level-change history append — read from
        # the same object; also lets the auto-add predicate go through
        # `needs_restock` (R-003) rather than a raw sequence literal.
        _PreviousLevel: StockLevel | None = _StockItem.stock_level
        _PreviousLevelSeq: int | None = (
            _PreviousLevel.sequence if _PreviousLevel else None
        )
        _PreviousLevelId = _PreviousLevel.id if _PreviousLevel else None

        if "stock_level_id" in _SetFields and request.stock_level_id is not None:
            _StockLevel = self.repository.get(StockLevel).by_id(request.stock_level_id)
            if not _StockLevel:
                return UpdateStockItemResponse(stock_level_not_found=True)
            # Same lazy="noload" trap as the location/group relationships —
            # the relationship-side assignment doesn't always dirty the FK
            # column when the loaded relationship state is None, so set
            # `_stock_level_id` directly. Without this the level appears to
            # change in the SPA (optimistic) but the next refresh comes
            # back with the OLD id + old `stock_level_last_updated`, which
            # is what was driving the "Updated X ago doesn't update" bug.
            _StockItem._stock_level_id = _StockLevel.id
            _StockItem.stock_level = _StockLevel
            # Stock-level changes always touch the last-updated timestamp so
            # the overview can show "updated X ago" honestly. X1: also bump
            # last_checked_at — a level change is implicitly a check of the
            # current state too.
            _Now = datetime.now(UTC)
            _StockItem.stock_level_last_updated = _Now
            _StockItem.last_checked_at = _Now
            # Append to the level-change history when the level actually moves.
            if _StockLevel.id != _PreviousLevelId:
                self.repository.add(StockLevelChange(
                    stock_item_id = _StockItem.id,
                    stock_level_id = _StockLevel.id,
                    stock_level_name = _StockLevel.name,
                    changed_at = datetime.now(UTC),
                ))
            # record a ConsumptionEvent when this level
            # change is a DROP (higher sequence = more depleted) tagged with
            # a consumption source. This is the depletion leg of the loop:
            # cooking with an item now feeds run-out prediction + the belief,
            # not only buying it. A level RISE (restock) or an unchanged/
            # unsourced update records nothing.
            self._maybe_record_consumption(request, _StockItem, _PreviousLevelSeq, _StockLevel)

        # stock_location: same lazy="noload" trap as stock_group below — a
        # relationship-only None assignment doesn't dirty the FK column, so
        # set `_stock_location_id` directly when clearing.
        if request.clear_stock_location:
            _StockItem._stock_location_id = None
            _StockItem.stock_location = None
        elif "stock_location_id" in _SetFields:
            if request.stock_location_id is None:
                _StockItem._stock_location_id = None
                _StockItem.stock_location = None
            else:
                _StockLocation = self.repository.get(StockLocation).by_id(request.stock_location_id)
                if not _StockLocation:
                    return UpdateStockItemResponse(stock_location_not_found=True)
                _StockItem.stock_location = _StockLocation

        if "name" in _SetFields and request.name is not None:
            _NameField = EntityField(StockItem, StockItem.Fields.NAME)
            _SameName: StockItem | None = (
                self.repository.get(StockItem).one(_NameField.eq(request.name))
            )
            # str(...) both sides: `stock_item_id` is the raw str path param,
            # `_SameName.id` a UUID — a bare `!=` never matched, so renaming an
            # item to its OWN name was rejected as a duplicate (FU-528 family).
            if _SameName and str(_SameName.id) != str(stock_item_id):
                return UpdateStockItemResponse(stock_item_already_exists=True)
            _StockItem.name = request.name

        if "notes" in _SetFields:
            _StockItem.notes = request.notes

        if "stocktake_alerts_are_enabled" in _SetFields and request.stocktake_alerts_are_enabled is not None:
            _StockItem.stocktake_alerts_are_enabled = request.stocktake_alerts_are_enabled

        if "expiry_date" in _SetFields:
            # The one expiry write path: records the History-tab transition.
            apply_expiry_change(self.repository, _StockItem, request.expiry_date)

        if "is_essential" in _SetFields and request.is_essential is not None:
            _StockItem.is_essential = request.is_essential

        # usual store hint. Clear flag wins over a present-but-None. The
        # target must exist — the FK would otherwise 500 at commit.
        if request.clear_usual_store:
            _StockItem.usual_store_id = None
        elif "usual_store_id" in _SetFields and request.usual_store_id is not None:
            if not self.repository.get(Store).exists(request.usual_store_id):
                return UpdateStockItemResponse(usual_store_not_found=True)
            _StockItem.usual_store_id = request.usual_store_id

        # Nutrition food link — same clear-flag pattern and existence check.
        # (The FK is SET NULL ondelete, so a dataset re-import that drops the
        # row later leaves the item unlinked rather than broken.)
        if request.clear_nutrition_food:
            _StockItem.nutrition_food_id = None
        elif "nutrition_food_id" in _SetFields and request.nutrition_food_id is not None:
            if not self.repository.get(NutritionFood).exists(request.nutrition_food_id):
                return UpdateStockItemResponse(nutrition_food_not_found=True)
            _StockItem.nutrition_food_id = request.nutrition_food_id

        # Linking a food and ignoring the item are mutually exclusive answers to
        # the same question, so an explicit link clears the opt-out — otherwise
        # an item ignored months ago and later linked by hand would keep its
        # stale "don't ask" flag and read as ignored on the matching page.
        if request.nutrition_ignored is not None:
            _StockItem.nutrition_ignored = request.nutrition_ignored
        elif _StockItem.nutrition_food_id is not None:
            _StockItem.nutrition_ignored = False

        # stock_group: nullable FK with the same lazy="noload" trap — see
        # the comment on stock_location above. Explicit `clear_stock_group`
        # is the SPA's canonical clear path; the present-but-None branch
        # also writes the FK column so a stray null still works.
        if request.clear_stock_group:
            _StockItem._stock_group_id = None
            _StockItem.stock_group = None
        elif "stock_group_id" in _SetFields:
            if request.stock_group_id is None:
                _StockItem._stock_group_id = None
                _StockItem.stock_group = None
            else:
                _Group = self.repository.get(StockGroup).by_id(request.stock_group_id)
                if _Group is None:
                    return UpdateStockItemResponse(stock_group_not_found=True)
                _StockItem.stock_group = _Group

        # `is_open` flipping True records today's date in `opened_on`
        # automatically (the spec). Flipping back to False clears it.
        # An explicit `opened_on` value in the same request overrides the
        # auto-set, supporting the "edit the opened date" case.
        if "is_open" in _SetFields and request.is_open is not None:
            previous_open = bool(_StockItem.is_open)
            _StockItem.is_open = request.is_open
            if request.is_open and not previous_open:
                # R-021 — "opened on" stamps the household calendar day.
                _StockItem.opened_on = household_today(self.repository)
            elif not request.is_open:
                _StockItem.opened_on = None

        if "opened_on" in _SetFields:
            _StockItem.opened_on = request.opened_on

        # Auto-add hook: if this update transitioned the item from "ok" to
        # low-or-out, drop it onto the user's open draft list. This is the
        # only writer of `is_auto_added=True` — the line lands without the
        # user asking for it, so the list marks it. Whether the
        # transition fires the hook depends on the install-wide
        # `AppSetting.auto_add_mode` (FU-511, replacing the retired per-item
        # `auto_add_when_low` boolean):
        #   `off`             — never.
        #   `essential_only`  — only when the item is `is_essential=True`.
        #   `all`             — always on a low/out transition.
        # Skipped silently if there's no single draft, or if the item is already
        # on ANY non-archived list — the user already knows; double-add
        # would be annoying.
        #
        # `needs_restock` is R-003 (single authority in `stock_status.py`)
        # so this stays correct across any future stock-band changes.
        _AutoAddResult: tuple[UUID, UUID] | None = None
        if (
            self._auto_add_enabled_for(_StockItem)
            and needs_restock(_StockItem.stock_level)
            and not needs_restock(_PreviousLevel)
        ):
            _AutoAddResult = self._try_auto_add(_StockItem)

        self.repository.save_changes()
        if _AutoAddResult is not None:
            line_id, list_id = _AutoAddResult
            return UpdateStockItemResponse(
                auto_added_line_id=line_id,
                auto_added_to_list_id=list_id,
            )
        return UpdateStockItemResponse()

    _VALID_CONSUMPTION_SOURCES = frozenset({
        CONSUMPTION_SOURCE_COOK,
        CONSUMPTION_SOURCE_MANUAL,
        CONSUMPTION_SOURCE_WASTE,
    })

    def _maybe_record_consumption(
        self,
        request: "UpdateStockItemRequest",
        stock_item: StockItem,
        previous_seq: int | None,
        new_level: StockLevel,
    ) -> None:
        """P8-07 / FU-449 — persist a ConsumptionEvent when a sourced level
        DROP happens. Higher sequence = more depleted, so a drop is
        `new.sequence > previous.sequence`. A restock (rise), an unchanged
        level, or an update with no `consumption_source` records nothing.
        """
        source = request.consumption_source
        if source not in self._VALID_CONSUMPTION_SOURCES:
            return
        new_seq = new_level.sequence
        if previous_seq is None or new_seq <= previous_seq:
            return
        recipe_name: str | None = None
        if request.consumption_recipe_id is not None:
            recipe = self.repository.get(Recipe).by_id(request.consumption_recipe_id)
            recipe_name = recipe.name if recipe else None
        self.repository.add(ConsumptionEvent(
            stock_item_id = stock_item.id,
            stock_item_name = stock_item.name,
            recipe_id = request.consumption_recipe_id,
            recipe_name = recipe_name,
            source = source,
            from_sequence = previous_seq,
            to_sequence = new_seq,
            occurred_at = datetime.now(UTC),
        ))

    def _auto_add_enabled_for(self, stock_item: StockItem) -> bool:
        """FU-511 — resolve the install-wide auto-add mode against this
        item's `is_essential`. Returns True iff the mode says fire for this
        item. Unknown / missing modes degrade to `essential_only`, matching
        the seeded default so a bad row can't silently disable auto-add
        for `is_essential` items."""
        setting: AppSetting = get_or_create_app_setting(self.repository)
        mode = (setting.auto_add_mode or "essential_only").strip().lower()
        if mode == "off":
            return False
        if mode == "all":
            return True
        return bool(stock_item.is_essential)

    def _try_auto_add(self, stock_item: StockItem) -> tuple[UUID, UUID] | None:
        """Adds the stock item to the user's one open draft list.

        Returns (line_id, list_id) on a successful add; None when skipped
        (no unambiguous draft target, already on any active list, etc).
        Imported locally because pulling shopping-list entities at module
        import time creates a cycle.
        """
        from dora_api.domain.entities.shopping_list import (
            SHOPPING_LIST_STATUS_DONE,
            ShoppingList,
            ShoppingListLine,
        )

        # Already on ANY active list? Skip — the user already knows.
        active_lists: list[ShoppingList] = self.repository.get(ShoppingList).all(
            EntityField(ShoppingList, ShoppingList.Fields.STATUS).ne(SHOPPING_LIST_STATUS_DONE)
        )
        active_ids = [l.id for l in active_lists]
        if active_ids:
            on_any = self.repository.get(ShoppingListLine).one(
                EntityField(ShoppingListLine, "stock_item_id").eq(stock_item.id)
                & EntityField(ShoppingListLine, "shopping_list_id").in_(active_ids)
            )
            if on_any is not None:
                return None

        # Auto-add only when there's an unambiguous DRAFT target — if the user
        # has 0 or 2+ drafts, the cart button still does the right thing on the
        # next manual click; we don't silently pick one.
        from dora_api.features.shopping_lists.quick_add_target_resolver import \
            resolve_quick_add_target
        outcome = resolve_quick_add_target(active_lists)
        if outcome.kind != "single":
            return None
        target = next(
            (l for l in active_lists if l.id == outcome.target_list_id), None
        )
        if target is None:
            return None

        siblings = self.repository.get(ShoppingListLine).all(
            EntityField(ShoppingListLine, "shopping_list_id").eq(target.id)
        )
        next_sequence = (max((l.sequence for l in siblings), default=-1)) + 1
        line = ShoppingListLine(
            shopping_list_id=target.id,
            stock_item_id=stock_item.id,
            quantity=1,
            sequence=next_sequence,
            is_auto_added=True,
            added_at=datetime.now(UTC),
        )
        apply_line_defaults(self.repository, [line])
        self.repository.add(line)
        return (line.id, target.id)


@STOCK_ITEM_ROUTER.route("<uuid:stock_item_id>", methods=["PATCH"])
@has_request_body(UpdateStockItemRequest)
def update_stock_item(stock_item_id: UUID):
    _LOGGER.info("Received request to update stock item.")
    _Handler = UpdateStockItemHandler(SqlAlchemyRepository())
    _Request: UpdateStockItemRequest = get_request_body()
    _Response = _Handler.handle(_Request, stock_item_id)

    if _Response.stock_item_not_found:
        _LOGGER.warning(f"Stock item not found with ID: {stock_item_id}")
        return not_found(StockItem.__name__, stock_item_id)

    if _Response.stock_item_already_exists:
        _LOGGER.warning(f"Stock item already exists with name: {_Request.name}")
        return business_rule_violation(f"A stock item with the name '{_Request.name}' already exists.")

    if _Response.stock_level_not_found and _Request.stock_level_id is not None:
        _LOGGER.warning(f"Stock level not found: {_Request.stock_level_id}")
        return entity_existence_failure(StockLevel.__name__, "stock_level_id", _Request.stock_level_id)

    if _Response.stock_location_not_found and _Request.stock_location_id is not None:
        _LOGGER.warning(f"Stock location not found: {_Request.stock_location_id}")
        return entity_existence_failure(StockLocation.__name__, "stock_location_id", _Request.stock_location_id)

    if _Response.stock_group_not_found and _Request.stock_group_id is not None:
        _LOGGER.warning(f"Stock group not found: {_Request.stock_group_id}")
        return entity_existence_failure(
            StockGroup.__name__, "stock_group_id", _Request.stock_group_id,
        )

    if _Response.usual_store_not_found:
        return entity_existence_failure(Store.__name__, "usual_store_id", _Request.usual_store_id)

    if _Response.nutrition_food_not_found:
        return entity_existence_failure(
            NutritionFood.__name__, "nutrition_food_id", _Request.nutrition_food_id,
        )

    _LOGGER.info(f"Successfully updated stock item with ID: {stock_item_id}")
    # If the auto-add hook fired (FU-511, driven by AppSetting.auto_add_mode +
    # is_essential), return a 200 with a minimal body so the UI can pop the
    # undoable "auto-added to <list>" toast. No trigger → keep the original
    # 204 for simplicity.
    if _Response.auto_added_line_id is not None:
        return ok({
            "auto_added": {
                "line_id": _Response.auto_added_line_id,
                "shopping_list_id": _Response.auto_added_to_list_id,
            },
        })
    return no_content()
