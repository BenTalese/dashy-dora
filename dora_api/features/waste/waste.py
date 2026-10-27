"""C-waste — Expiry rescue + waste log (slim).

  GET    /api/waste/rescue            — items expiring soon + recipes that
                                         use the most of them
  POST   /api/waste/events            — log a discarded stock item (reason
                                         only — no quantity/value/note)
  GET    /api/waste/events?limit=N    — recent waste log
  DELETE /api/waste/events/{event_id} — idempotent (backs the Undo toast)
  GET    /api/waste/insights          — {most_wasted, most_recent}

Per `PROPOSAL_WASTE_MINIMISATION.md`: the `/waste` page is gone; capture
lives as a one-tap action on the stock-item row. The signal (events
themselves) is preserved so the future Dora Score can still read it.
"""
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import List
from uuid import UUID

from flask import request
from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.recipe import Recipe
from dora_api.domain.entities.recipe_ingredient import RecipeIngredient
from dora_api.domain.entities.shopping_list import ShoppingListLine
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_item_waste_event import (
    StockItemWasteEvent, WASTE_REASON_VALUES,
)
from dora_api.domain.stock_status import effective_expiring_soon_window, is_missing
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.features.app_settings.clock import household_today
from dora_api.features.routers import WASTE_ROUTER
from dora_api.features.shopping_lists._line_price import line_paid_unit_price
from dora_api.infrastructure.api_response import (bad_request, no_content,
                                                  not_found, ok)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


# How far ahead "expiring soon" looks by default: the admin-configured
# `expiring_soon_window_days` (`effective_expiring_soon_window`), the same
# number alerts and the assistant's whats_expiring tool read — it used to be
# a third fixed copy of 7 (finalisation 12-R9, R-003).
_MAX_HORIZON_DAYS = 60

# Cap returned rows everywhere — the rescue feed is a one-glance signal,
# not a paginated list. The insights tool ditto.
_MAX_ROWS = 25


# ── /api/waste/rescue ────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ExpiringItemDto:
    stock_item_id: UUID
    name: str
    expiry_date: str
    days_until_expiry: int
    is_expired: bool
    stock_level_name: str | None
    estimated_value: float | None


@dataclass(frozen=True, slots=True)
class RescueRecipeDto:
    recipe_id: UUID
    name: str
    cook_time_minutes: int | None
    difficulty: str | None
    matching_expiring_items: List[str]
    matching_count: int
    missing_ingredients: List[str]
    is_favourite: bool


@dataclass(frozen=True, slots=True)
class WasteRescueDto:
    horizon_days: int
    items: List[ExpiringItemDto]
    recipes: List[RescueRecipeDto]


class GetWasteRescueHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, horizon_days: int) -> WasteRescueDto:
        horizon_days = max(0, min(horizon_days, _MAX_HORIZON_DAYS))
        # R-021 — waste-rescue horizon is a household calendar window.
        today = household_today(self.repository)
        cutoff = today + timedelta(days=horizon_days)

        items: list[StockItem] = (
            self.repository.get(StockItem)
            .include(StockItem.Fields.STOCK_LEVEL)
            .all(
                EntityField(StockItem, StockItem.Fields.EXPIRY_DATE).is_not_null()
                & EntityField(StockItem, StockItem.Fields.EXPIRY_DATE).lte(cutoff)
            )
        )
        items.sort(key=lambda i: i.expiry_date or date.max)

        # Last-paid price per stock item — the "value at risk" estimate on
        # the rescue feed so the assistant can frame what's-about-to-spoil in
        # dollar terms. "Last" means the most recently *added* priced line:
        # this used to pick by `sequence`, which is a per-list position, so
        # across lists the pick was arbitrary (finalisation 12-R5). The waste
        # *event* itself no longer stores a value (C-waste slim).
        value_lookup: dict[UUID, float] = {}
        if items:
            item_ids = [i.id for i in items]
            lines = self.repository.get(ShoppingListLine).all(
                EntityField(ShoppingListLine, ShoppingListLine.Fields.STOCK_ITEM_ID)
                .in_(item_ids)
            )
            for line in sorted(lines, key=lambda l: (l.added_at is None, l.added_at)):
                price = line_paid_unit_price(line)
                if price is not None:
                    value_lookup[line.stock_item_id] = price

        item_dtos: list[ExpiringItemDto] = []
        for item in items[:_MAX_ROWS]:
            days = (item.expiry_date - today).days if item.expiry_date else 0
            item_dtos.append(ExpiringItemDto(
                stock_item_id=item.id,
                name=item.name,
                expiry_date=item.expiry_date.isoformat() if item.expiry_date else "",
                days_until_expiry=days,
                is_expired=days < 0,
                stock_level_name=item.stock_level.name if item.stock_level else None,
                estimated_value=value_lookup.get(item.id),
            ))

        # Rank recipes by how many of the at-risk items they'd use.
        # We deliberately don't filter to "fully-cookable now" — the
        # point is to surface options that *help*, not options that
        # require a full pantry.
        # Only recipes that use an at-risk item can rank, so they are found
        # from the ingredient side rather than by loading every recipe
        # (finalisation 12-R27, the 11-R41 pattern).
        at_risk_ids = {i.id for i in items}
        recipe_ids = list({
            ing._recipe_id  # noqa: SLF001 (the FK is mapped privately)
            for ing in self.repository.get(RecipeIngredient).all(
                EntityField(RecipeIngredient, "_stock_item_id").in_(list(at_risk_ids))
            )
        }) if at_risk_ids else []
        recipes: list[Recipe] = (
            self.repository.get(Recipe)
            .include(Recipe.Fields.INGREDIENTS)
            .then_include(RecipeIngredient.Fields.STOCK_ITEM)
            .then_include(StockItem.Fields.STOCK_LEVEL)
            .all(EntityField(Recipe, "id").in_(recipe_ids))
        ) if recipe_ids else []
        ranked: list[RescueRecipeDto] = []
        for recipe in recipes:
            matches: list[str] = []
            missing: list[str] = []
            for ing in (recipe.ingredients or []):
                item = ing.stock_item
                if item is None:
                    continue
                # Cookbook revision §1.9 — optional ingredients are skipped
                # so the rescue ranking matches the cookability rule.
                if getattr(ing, "is_optional", False):
                    continue
                if item.id in at_risk_ids:
                    matches.append(item.name)
                else:
                    if is_missing(item.stock_level):
                        missing.append(item.name)
            if not matches:
                continue
            ranked.append(RescueRecipeDto(
                recipe_id=recipe.id,
                name=recipe.name,
                cook_time_minutes=recipe.cook_time_minutes,
                difficulty=recipe.difficulty,
                matching_expiring_items=matches,
                matching_count=len(matches),
                missing_ingredients=missing[:5],
                is_favourite=bool(recipe.is_favourite),
            ))
        # Most rescues first; favourites break ties so familiar food gets
        # the nudge over an obscure recipe with the same coverage.
        ranked.sort(key=lambda r: (-r.matching_count, not r.is_favourite, r.name))

        return WasteRescueDto(
            horizon_days=horizon_days,
            items=item_dtos,
            recipes=ranked[:_MAX_ROWS],
        )


@WASTE_ROUTER.route("/rescue", methods=["GET"])
def get_waste_rescue():
    repository = SqlAlchemyRepository()
    default_horizon = effective_expiring_soon_window(get_or_create_app_setting(repository))
    try:
        horizon = int(request.args.get("horizon_days", default_horizon))
    except (TypeError, ValueError):
        horizon = default_horizon
    dto = GetWasteRescueHandler(repository).handle(horizon)
    _LOGGER.debug(
        "waste rescue horizon=%d items=%d recipes=%d",
        dto.horizon_days, len(dto.items), len(dto.recipes),
    )
    return ok(dto)


# ── /api/waste/events ────────────────────────────────────────────────────

class LogWasteEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stock_item_id: UUID
    reason: str = Field(min_length=1, max_length=32)


@dataclass(slots=True)
class LogWasteEventResponse:
    event_id: UUID | None = None
    item_not_found: bool = False
    invalid_reason: bool = False


class LogWasteEventHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: LogWasteEventRequest) -> LogWasteEventResponse:
        if request.reason not in WASTE_REASON_VALUES:
            return LogWasteEventResponse(invalid_reason=True)

        item: StockItem | None = self.repository.get(StockItem).by_id(request.stock_item_id)
        if item is None:
            return LogWasteEventResponse(item_not_found=True)

        event = StockItemWasteEvent(
            stock_item_id=item.id,
            stock_item_name=item.name,
            reason=request.reason,
            occurred_at=datetime.now(timezone.utc),
        )
        self.repository.add(event)
        self.repository.save_changes()
        return LogWasteEventResponse(event_id=event.id)


@WASTE_ROUTER.route("/events", methods=["POST"])
@has_request_body(LogWasteEventRequest)
def log_waste_event():
    _Request: LogWasteEventRequest = get_request_body()
    _Response = LogWasteEventHandler(SqlAlchemyRepository()).handle(_Request)
    if _Response.invalid_reason:
        return bad_request(
            f"Invalid reason '{_Request.reason}'. Allowed: "
            f"{sorted(WASTE_REASON_VALUES)}"
        )
    if _Response.item_not_found:
        return not_found("StockItem", _Request.stock_item_id)
    _LOGGER.info(
        "Logged waste event %s (item=%s reason=%s)",
        _Response.event_id, _Request.stock_item_id, _Request.reason,
    )
    return ok({"event_id": _Response.event_id})


@WASTE_ROUTER.route("/events", methods=["GET"])
def list_waste_events():
    try:
        limit = max(1, min(int(request.args.get("limit", 25)), 200))
    except (TypeError, ValueError):
        limit = 25
    repo = SqlAlchemyRepository()
    events: list[StockItemWasteEvent] = repo.get(StockItemWasteEvent).all()
    events.sort(key=lambda e: e.occurred_at, reverse=True)
    return ok({
        "events": [
            {
                "event_id": str(e.id),
                "stock_item_id": str(e.stock_item_id) if e.stock_item_id else None,
                "stock_item_name": e.stock_item_name,
                "reason": e.reason,
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
            }
            for e in events[:limit]
        ],
    })


# Idempotent — the Undo toast may fire a delete for an event that's
# already gone (double-tap, retry after network blip). Returning 204
# in both the "deleted now" and "not present" cases keeps the client
# simple. Only a malformed UUID is a real error.
@WASTE_ROUTER.route("/events/<uuid:event_id>", methods=["DELETE"])
def delete_waste_event(event_id: UUID):
    # R-033: uuid converter parses the id at the routing edge (FU-544).
    repo = SqlAlchemyRepository()
    event = repo.get(StockItemWasteEvent).by_id(event_id)
    if event is None:
        _LOGGER.debug("Delete waste event %s: already gone (no-op)", event_id)
        return no_content()
    repo.remove(event)
    repo.save_changes()
    _LOGGER.info("Deleted waste event %s", event_id)
    return no_content()


# ── /api/waste/events/bulk ───────────────────────────────────────────────
#
# 2026-08-22 owner feedback: "bulk actions seem to be performed one item at
# a time and it can be slow. noticed this on log waste." Bulk waste was the
# worst offender in the app — the SPA fired up to THREE sequential requests
# per selected item (log the event, PATCH the expiry away, re-read the row),
# so a 20-item selection cost 60 round-trips before the toast appeared.
#
# These two endpoints collapse that to one request each way. They orchestrate
# the existing single-item handlers rather than writing their own SQL: waste
# capture and expiry clearing both have side effects with owners
# (`StockItemExpiryEvent` emission lives in `UpdateStockItemHandler`), and a
# second implementation of "clear an expiry" is exactly the drift R-003
# exists to stop. What the caller saves is latency, which is what was slow.

_MAX_BULK_IDS = 500


class BulkLogWasteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stock_item_ids: List[UUID] = Field(min_length=1, max_length=_MAX_BULK_IDS)
    reason: str = Field(min_length=1, max_length=32)
    # Matches the single-item row flow, which clears the expiry once the
    # thing is in the bin. Off is supported for callers that only want the
    # signal recorded.
    clear_expiry: bool = True


@dataclass(slots=True)
class BulkLoggedEvent:
    event_id: UUID
    stock_item_id: UUID
    # The expiry this call cleared, or None if there was nothing to clear.
    # Echoed back so the Undo path can put it right where it was — the
    # event row itself doesn't store it.
    previous_expiry_date: str | None


@dataclass(slots=True)
class BulkLogWasteResponse:
    invalid_reason: bool = False
    logged: List[BulkLoggedEvent] = field(default_factory=list)
    missing_ids: List[UUID] = field(default_factory=list)


class BulkLogWasteHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: BulkLogWasteRequest) -> BulkLogWasteResponse:
        if request.reason not in WASTE_REASON_VALUES:
            return BulkLogWasteResponse(invalid_reason=True)

        # Deferred so the module-level import graph stays acyclic —
        # `update_stock_item` reaches into shopping lists for its auto-add
        # hook, and this module is imported from there indirectly.
        from dora_api.features.stock_items.update_stock_item import (
            UpdateStockItemHandler, UpdateStockItemRequest,
        )

        log_handler = LogWasteEventHandler(self.repository)
        update_handler = UpdateStockItemHandler(self.repository)
        logged: list[BulkLoggedEvent] = []
        missing: list[UUID] = []

        for stock_item_id in request.stock_item_ids:
            # Read the expiry BEFORE logging: the clear below wipes it, and
            # the Undo payload needs the old value.
            item: StockItem | None = self.repository.get(StockItem).by_id(stock_item_id)
            if item is None:
                missing.append(stock_item_id)
                continue
            previous_expiry = item.expiry_date

            response = log_handler.handle(LogWasteEventRequest(
                stock_item_id=stock_item_id,
                reason=request.reason,
            ))
            if response.event_id is None:
                missing.append(stock_item_id)
                continue

            if request.clear_expiry and previous_expiry is not None:
                update_handler.handle(
                    UpdateStockItemRequest(expiry_date=None), stock_item_id,
                )

            logged.append(BulkLoggedEvent(
                event_id=response.event_id,
                stock_item_id=stock_item_id,
                previous_expiry_date=(
                    previous_expiry.isoformat() if previous_expiry else None
                ),
            ))

        return BulkLogWasteResponse(logged=logged, missing_ids=missing)


@WASTE_ROUTER.route("/events/bulk", methods=["POST"])
@has_request_body(BulkLogWasteRequest)
def bulk_log_waste_events():
    _Request: BulkLogWasteRequest = get_request_body()
    _Response = BulkLogWasteHandler(SqlAlchemyRepository()).handle(_Request)
    if _Response.invalid_reason:
        return bad_request(
            f"Invalid reason '{_Request.reason}'. Allowed: "
            f"{sorted(WASTE_REASON_VALUES)}"
        )
    _LOGGER.info(
        "Bulk-logged %d of %d waste event(s) (reason=%s)",
        len(_Response.logged), len(_Request.stock_item_ids), _Request.reason,
    )
    return ok({
        "events": [
            {
                "event_id": str(e.event_id),
                "stock_item_id": str(e.stock_item_id),
                "previous_expiry_date": e.previous_expiry_date,
            }
            for e in _Response.logged
        ],
        "missing_ids": [str(i) for i in _Response.missing_ids],
    })


# ── /api/waste/events/bulk-delete ────────────────────────────────────────
#
# The Undo half. POST rather than DELETE because it carries a body, and
# idempotent for the same reason the single-item delete is: the toast can
# fire twice. Restoring the expiry is the caller's choice per event — it
# passes back what the bulk log told it, so an item that had no expiry
# before doesn't grow one on undo.

class BulkDeleteWasteEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    restore_expiry_date: date | None = None


class BulkDeleteWasteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: List[BulkDeleteWasteEntry] = Field(min_length=1, max_length=_MAX_BULK_IDS)


@dataclass(slots=True)
class BulkDeleteWasteResponse:
    deleted_count: int = 0
    restored_count: int = 0


class BulkDeleteWasteHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: BulkDeleteWasteRequest) -> BulkDeleteWasteResponse:
        from dora_api.features.stock_items.update_stock_item import (
            UpdateStockItemHandler, UpdateStockItemRequest,
        )

        update_handler = UpdateStockItemHandler(self.repository)
        deleted = 0
        restored = 0

        for entry in request.events:
            event: StockItemWasteEvent | None = (
                self.repository.get(StockItemWasteEvent).by_id(entry.event_id)
            )
            if event is None:
                # Already gone — no-op, same as the single-item delete.
                continue
            stock_item_id = event.stock_item_id
            self.repository.remove(event)
            deleted += 1

            if entry.restore_expiry_date is not None and stock_item_id is not None:
                update_handler.handle(
                    UpdateStockItemRequest(expiry_date=entry.restore_expiry_date),
                    stock_item_id,
                )
                restored += 1

        # One commit for the removals (R-031); each expiry restore above
        # commits through the update handler's own write path.
        self.repository.save_changes()
        return BulkDeleteWasteResponse(deleted_count=deleted, restored_count=restored)


@WASTE_ROUTER.route("/events/bulk-delete", methods=["POST"])
@has_request_body(BulkDeleteWasteRequest)
def bulk_delete_waste_events():
    _Request: BulkDeleteWasteRequest = get_request_body()
    _Response = BulkDeleteWasteHandler(SqlAlchemyRepository()).handle(_Request)
    _LOGGER.info(
        "Bulk-deleted %d of %d waste event(s); restored %d expiry date(s)",
        _Response.deleted_count, len(_Request.events), _Response.restored_count,
    )
    return ok({
        "deleted_count": _Response.deleted_count,
        "restored_count": _Response.restored_count,
    })


# ── /api/waste/insights ──────────────────────────────────────────────────

# Slim shape (C-waste): two answers only — what gets wasted often, and
# what was most recently wasted. Reason breakdowns and value sums are
# gone because the underlying fields are. The Dora `waste_insights` tool
# reads the same data.
_INSIGHTS_WINDOW_DEFAULT_DAYS = 90
_INSIGHTS_WINDOW_MIN_DAYS = 7
_INSIGHTS_WINDOW_MAX_DAYS = 365
_MOST_RECENT_LIMIT = 10


def _rank_buckets(events: list[StockItemWasteEvent]) -> list[dict]:
    """Events grouped by item, most-wasted first.

    Grouped by (stock_item_id, name): the name is the one captured at log time,
    so renames don't merge buckets and deleted items still appear.
    """
    buckets: dict[tuple, dict] = {}
    for event in events:
        key = (event.stock_item_id, event.stock_item_name)
        bucket = buckets.setdefault(key, {
            "stock_item_id": str(event.stock_item_id) if event.stock_item_id else None,
            "stock_item_name": event.stock_item_name,
            "event_count": 0,
            "last_occurred_at": None,
        })
        bucket["event_count"] += 1
        if bucket["last_occurred_at"] is None or event.occurred_at > bucket["last_occurred_at"]:
            bucket["last_occurred_at"] = event.occurred_at
    ranked = sorted(
        buckets.values(),
        key=lambda b: (-b["event_count"], b["stock_item_name"]),
    )[:_MAX_ROWS]
    # Datetimes compare as datetimes; serialised once, here (12-R14).
    for bucket in ranked:
        bucket["last_occurred_at"] = bucket["last_occurred_at"].isoformat()
    return ranked


@WASTE_ROUTER.route("/insights", methods=["GET"])
def get_waste_insights():
    """Returns {most_wasted, most_recent} over the given window.

    `most_wasted` = items grouped by name, sorted by event count desc.
    `most_recent` = the latest events, newest first, no grouping.
    """
    try:
        window_days = int(request.args.get(
            "window_days", _INSIGHTS_WINDOW_DEFAULT_DAYS,
        ))
    except (TypeError, ValueError):
        window_days = _INSIGHTS_WINDOW_DEFAULT_DAYS
    window_days = max(
        _INSIGHTS_WINDOW_MIN_DAYS,
        min(window_days, _INSIGHTS_WINDOW_MAX_DAYS),
    )
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    repo = SqlAlchemyRepository()
    events: list[StockItemWasteEvent] = repo.get(StockItemWasteEvent).all(
        EntityField(StockItemWasteEvent, StockItemWasteEvent.Fields.OCCURRED_AT).gte(cutoff)
    )
    events.sort(key=lambda e: e.occurred_at, reverse=True)

    most_wasted = _rank_buckets(events)

    # The same ranking restricted to each reason, so the report's reason tiles
    # can filter the list (owner, 2026-09-27) without the client re-counting
    # events it never received.
    most_wasted_by_reason = {
        reason: _rank_buckets([e for e in events if e.reason == reason])
        for reason in WASTE_REASON_VALUES
    }

    # Per-reason counts. Every canonical reason is emitted even at zero, so
    # the client can render a fixed grid without hiding tiles the user
    # never populated (an empty tile is the intended affordance — "you
    # haven't logged any of these" is meaningful).
    by_reason = {reason: 0 for reason in WASTE_REASON_VALUES}
    for event in events:
        if event.reason in by_reason:
            by_reason[event.reason] += 1

    most_recent = [
        {
            "event_id": str(e.id),
            "stock_item_id": str(e.stock_item_id) if e.stock_item_id else None,
            "stock_item_name": e.stock_item_name,
            "reason": e.reason,
            "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
        }
        for e in events[:_MOST_RECENT_LIMIT]
    ]

    return ok({
        "window_days": window_days,
        "total_events": len(events),
        "by_reason": by_reason,
        "most_wasted": most_wasted,
        "most_wasted_by_reason": most_wasted_by_reason,
        "most_recent": most_recent,
    })
