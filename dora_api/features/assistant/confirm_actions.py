"""Resolve + commit "confirm-style" assistant actions.

These are mutating tools where the proposal reduces to a single human-readable
sentence and a single Confirm button on the frontend — distinct from the
add-to-shopping-list flow which has its own multi-item disambiguation UI.

Pattern per action:
  propose_<action>(args)  -> {type, summary, payload, status, candidates?}
  commit_<action>(payload) -> {ok, message}

`status` is one of:
  'ready'         - resolved; payload is sufficient to commit
  'ambiguous'     - multiple matching entities; `candidates` lists them
  'not_found'     - nothing matched
  'invalid'       - args don't make sense (bad level name, negative days, etc.)

The frontend treats anything non-'ready' as a non-mutating message and never
shows a Confirm button; the model's reply text already explains the issue.
"""
import logging
from datetime import date, timedelta
from typing import Any, Callable
from uuid import UUID


from dora_api.features.meal_slots.slot_validation import ordered_slot_names
from dora_api.features.assistant._name_resolution import (
    resolve_by_name, stock_item_candidate)
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.domain.money import format_money
from dora_api.features.assistant._limits import MAX_CANDIDATES
from dora_api.domain.entities.meal_plan import MealPlan
from dora_api.domain.entities.meal_plan_entry import MealPlanEntry
from dora_api.domain.entities.recipe import Recipe
from dora_api.domain.entities.recipe_ingredient import RecipeIngredient
from dora_api.domain.entities.shopping_list import ShoppingListLine
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_level import StockLevel
from dora_api.domain.entities.stock_location import StockLocation
from dora_api.domain.stock_status import (StockStatus, is_missing,
                                          level_for_status)
from dora_api.features.meal_plans.update_meal_plan import (
    UpdateMealPlanEntryRequest, UpdateMealPlanHandler, UpdateMealPlanRequest)
from dora_api.features.shopping_lists.manage_shopping_list_lines import (
    AddLineHandler, AddLineRequest, UpdateLineHandler, UpdateLineRequest)
from dora_api.features.shopping_lists.trim_to_budget import (
    TrimToBudgetHandler, TrimToBudgetRequest)
from dora_api.features.app_settings.clock import household_today
# "Primary" is inferred (exactly one draft list), never stored — this module
# used to carry its own copy querying the dropped `is_primary` column, which
# made tick / add-recipe / trim raise AttributeError on propose
# (finalisation 11-R1). One resolver, in `shopping_actions`.
from dora_api.features.assistant.shopping_actions import _primary_list
from dora_api.features.stock_items.move_stock_item import (
    MoveStockItemHandler, MoveStockItemRequest)
from dora_api.features.stock_items.update_stock_item import (
    UpdateStockItemHandler, UpdateStockItemRequest)
from dora_api.infrastructure.utils import pluralize
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.session_user import current_user_id

_LOGGER = logging.getLogger(__name__)



# ── Common helpers ─────────────────────────────────────────────────────

def _find_stock_item(repo: SqlAlchemyRepository, name: str) -> tuple[str, list[StockItem]]:
    """Returns ('exact'|'fuzzy'|'none', [items])."""
    return _match_kind(resolve_by_name(
        lambda: repo.get(StockItem)
        .include(StockItem.Fields.STOCK_LEVEL)
        .include(StockItem.Fields.STOCK_LOCATION),
        StockItem, name,
    ))


def _match_kind(resolution) -> tuple[str, list]:
    kind = "exact" if resolution.exact else ("fuzzy" if resolution.matches else "none")
    return kind, resolution.matches


def _resolve_single_item(name: str) -> dict[str, Any] | StockItem:
    """Resolve a name to a StockItem. Returns a status dict OR the StockItem
    itself when there's a single match. Caller flips the dict into the
    pending_action when not 'ready'."""
    if not name:
        return {"status": "invalid", "summary": "I didn't catch which item you meant.", "candidates": []}
    repo = SqlAlchemyRepository()
    kind, matches = _find_stock_item(repo, name)
    if not matches:
        return {"status": "not_found", "summary": f"I don't have anything called \"{name}\" in your stock.", "candidates": []}
    if len(matches) == 1:
        return matches[0]
    return {
        "status": "ambiguous",
        "summary": f"A few items match \"{name}\". Which one?",
        "candidates": [stock_item_candidate(m) for m in matches[:MAX_CANDIDATES]],
    }


# ── update_stock_level ─────────────────────────────────────────────────

# Common phrasings the model might emit. Resolved to a canonical StockStatus
# (sequence-keyed) — never a level name string — so seed-customised level
# names still pick the right row (R-003 / Chunk 1 contract).
_LEVEL_ALIASES: dict[str, StockStatus] = {
    "out": StockStatus.OUT_OF_STOCK, "out of stock": StockStatus.OUT_OF_STOCK,
    "empty": StockStatus.OUT_OF_STOCK, "gone": StockStatus.OUT_OF_STOCK,
    "none": StockStatus.OUT_OF_STOCK, "finished": StockStatus.OUT_OF_STOCK,
    "low": StockStatus.LOW_STOCK, "low stock": StockStatus.LOW_STOCK,
    "running low": StockStatus.LOW_STOCK, "almost out": StockStatus.LOW_STOCK,
    "almost gone": StockStatus.LOW_STOCK,
    "stocked": StockStatus.STOCKED, "stocked up": StockStatus.STOCKED,
    "ok": StockStatus.STOCKED, "fine": StockStatus.STOCKED,
    "full": StockStatus.STOCKED, "plenty": StockStatus.STOCKED,
    "sufficient": StockStatus.STOCKED,
    "well stocked": StockStatus.STOCKED, "well-stocked": StockStatus.STOCKED,
}


def _resolve_level(repo: SqlAlchemyRepository, level_input: str) -> StockLevel | None:
    if not level_input:
        return None
    status = _LEVEL_ALIASES.get(level_input.lower().strip())
    if status is not None:
        return level_for_status(repo.get(StockLevel).all(), status)
    # Fallback: substring against the user's custom level name (in case the
    # alias map didn't cover a phrasing they actually use).
    matches = repo.get(StockLevel).all(
        EntityField(StockLevel, StockLevel.Fields.NAME).contains(level_input)
    )
    return matches[0] if len(matches) == 1 else None


def propose_update_stock_level(args: dict) -> dict[str, Any]:
    item_resolved = _resolve_single_item(str(args.get("item_name") or "").strip())
    if isinstance(item_resolved, dict):
        return {"type": "update_stock_level", **item_resolved}
    item: StockItem = item_resolved

    repo = SqlAlchemyRepository()
    level = _resolve_level(repo, str(args.get("level") or "").strip())
    if level is None:
        return {
            "type": "update_stock_level",
            "status": "invalid",
            "summary": f"I'm not sure what level to set {item.name} to. Try 'out', 'low', 'sufficient', or 'well stocked'.",
            "candidates": [],
        }
    previous = item.stock_level.name if item.stock_level else "(unknown)"
    if item.stock_level and item.stock_level.id == level.id:
        return {
            "type": "update_stock_level",
            "status": "invalid",
            "summary": f"{item.name} is already {previous}.",
            "candidates": [],
        }
    return {
        "type": "update_stock_level",
        "status": "ready",
        "summary": f"Set {item.name} to {level.name}? (was {previous})",
        "payload": {
            "stock_item_id": str(item.id),
            "stock_item_name": item.name,
            "new_level_id": str(level.id),
            "new_level_name": level.name,
            "previous_level_name": previous,
        },
        "candidates": [],
    }


def commit_update_stock_level(payload: dict[str, Any]) -> dict[str, Any]:
    handler = UpdateStockItemHandler(SqlAlchemyRepository())
    response = handler.handle(
        UpdateStockItemRequest(stock_level_id=UUID(payload["new_level_id"])),
        stock_item_id=UUID(payload["stock_item_id"]),
    )
    if response.stock_item_not_found:
        return {"ok": False, "message": "I lost track of that item. Maybe it was deleted."}
    if response.stock_level_not_found:
        return {"ok": False, "message": "That stock level doesn't exist anymore."}
    return {
        "ok": True,
        "message": f"Done. {payload['stock_item_name']} is now {payload['new_level_name']}.",
    }


# ── mark_opened / mark_closed ──────────────────────────────────────────

def propose_mark_opened(args: dict) -> dict[str, Any]:
    item_resolved = _resolve_single_item(str(args.get("item_name") or "").strip())
    if isinstance(item_resolved, dict):
        return {"type": "mark_opened", **item_resolved}
    item: StockItem = item_resolved
    closed = bool(args.get("closed"))
    already_in_state = (closed and not item.is_open) or (not closed and item.is_open)
    if already_in_state:
        state = "closed" if closed else "open"
        return {
            "type": "mark_opened",
            "status": "invalid",
            "summary": f"{item.name} is already marked as {state}.",
            "candidates": [],
        }
    verb = "closed" if closed else "opened"
    return {
        "type": "mark_opened",
        "status": "ready",
        "summary": f"Mark {item.name} as {verb}?",
        "payload": {
            "stock_item_id": str(item.id),
            "stock_item_name": item.name,
            "is_open": not closed,
        },
        "candidates": [],
    }


def commit_mark_opened(payload: dict[str, Any]) -> dict[str, Any]:
    handler = UpdateStockItemHandler(SqlAlchemyRepository())
    response = handler.handle(
        UpdateStockItemRequest(is_open=bool(payload["is_open"])),
        stock_item_id=UUID(payload["stock_item_id"]),
    )
    if response.stock_item_not_found:
        return {"ok": False, "message": "I lost track of that item. Maybe it was deleted."}
    state = "opened" if payload["is_open"] else "closed"
    return {"ok": True, "message": f"Done. {payload['stock_item_name']} marked as {state}."}


# ── push_expiry ────────────────────────────────────────────────────────

# FU-515 B.3 — sane bound on an LLM-supplied expiry shift (~10 years). The
# mutation gate already shows the resulting date on the confirm card, but a
# boundary cap rejects nonsense before it ever renders.
_MAX_EXPIRY_PUSH_DAYS = 3650


def propose_push_expiry(args: dict) -> dict[str, Any]:
    item_resolved = _resolve_single_item(str(args.get("item_name") or "").strip())
    if isinstance(item_resolved, dict):
        return {"type": "push_expiry", **item_resolved}
    item: StockItem = item_resolved
    try:
        days = int(args.get("days"))
    except (TypeError, ValueError):
        return {
            "type": "push_expiry", "status": "invalid",
            "summary": f"How many days should I push {item.name}'s expiry by?",
            "candidates": [],
        }
    if days == 0:
        return {
            "type": "push_expiry", "status": "invalid",
            "summary": "Zero days isn't really pushing anything, mate.",
            "candidates": [],
        }
    # FU-515 B.3 — bound the LLM-supplied magnitude at the tool boundary. A
    # ~10-year shift is already absurd for a pantry item; reject anything
    # larger so a mis-parsed / injected number can't propose a nonsense date.
    if abs(days) > _MAX_EXPIRY_PUSH_DAYS:
        return {
            "type": "push_expiry", "status": "invalid",
            "summary": (
                f"That's more than {_MAX_EXPIRY_PUSH_DAYS // 365} years. "
                f"Give me a sensible number of days."
            ),
            "candidates": [],
        }
    # R-021 — fallback base for the expiry push is household-tz today.
    base = item.expiry_date or household_today(SqlAlchemyRepository())
    new_expiry = base + timedelta(days=days)
    direction = "back" if days < 0 else "forward"
    delta = f"{abs(days)} {pluralize(days, 'day')}"
    base_phrase = item.expiry_date.isoformat() if item.expiry_date else f"today ({base.isoformat()})"
    return {
        "type": "push_expiry",
        "status": "ready",
        "summary": f"Push {item.name}'s expiry {direction} {delta}, from {base_phrase} to {new_expiry.isoformat()}?",
        "payload": {
            "stock_item_id": str(item.id),
            "stock_item_name": item.name,
            "new_expiry": new_expiry.isoformat(),
        },
        "candidates": [],
    }


def commit_push_expiry(payload: dict[str, Any]) -> dict[str, Any]:
    handler = UpdateStockItemHandler(SqlAlchemyRepository())
    response = handler.handle(
        UpdateStockItemRequest(expiry_date=date.fromisoformat(payload["new_expiry"])),
        stock_item_id=UUID(payload["stock_item_id"]),
    )
    if response.stock_item_not_found:
        return {"ok": False, "message": "I lost track of that item."}
    return {"ok": True, "message": f"Done. {payload['stock_item_name']} now expires {payload['new_expiry']}."}


# ── tick_shopping_line / untick ───────────────────────────────────────

def propose_tick_shopping_line(args: dict) -> dict[str, Any]:
    name = str(args.get("item_name") or "").strip()
    if not name:
        return {"type": "tick_shopping_line", "status": "invalid",
                "summary": "Which item should I tick off?", "candidates": []}
    untick = bool(args.get("untick"))
    repo = SqlAlchemyRepository()
    primary = _primary_list(repo)
    if primary is None:
        return {"type": "tick_shopping_line", "status": "invalid",
                "summary": "I add to your draft list, and that only works when you have exactly one.",
                "candidates": []}

    # Find lines on the primary list whose stock item name matches.
    lines: list[ShoppingListLine] = repo.get(ShoppingListLine).all(
        EntityField(ShoppingListLine, ShoppingListLine.Fields.SHOPPING_LIST_ID).eq(primary.id)
    )
    if not lines:
        return {"type": "tick_shopping_line", "status": "not_found",
                "summary": f"Your primary list \"{primary.name}\" is empty.", "candidates": []}

    item_ids = list({line.stock_item_id for line in lines})
    items: list[StockItem] = (
        repo.get(StockItem)
        .all(EntityField(StockItem, StockItem.Fields.ID).in_(item_ids))
        if item_ids else []
    )
    item_by_id = {it.id: it for it in items}

    name_lower = name.lower()
    matching = [
        line for line in lines
        if (item := item_by_id.get(line.stock_item_id)) is not None
        and name_lower in item.name.lower()
    ]
    if not matching:
        return {"type": "tick_shopping_line", "status": "not_found",
                "summary": f"\"{name}\" isn't on your primary list.", "candidates": []}
    if len(matching) > 1:
        return {
            "type": "tick_shopping_line",
            "status": "ambiguous",
            "summary": f"A few \"{name}\" entries on your list. Which?",
            "candidates": [
                {
                    "line_id": str(line.id),
                    "name": item_by_id[line.stock_item_id].name,
                    "is_ticked": line.is_ticked,
                }
                for line in matching[:MAX_CANDIDATES]
            ],
        }
    line = matching[0]
    item = item_by_id[line.stock_item_id]
    if untick and not line.is_ticked:
        return {"type": "tick_shopping_line", "status": "invalid",
                "summary": f"{item.name} isn't ticked yet.",
                "candidates": []}
    if not untick and line.is_ticked:
        return {"type": "tick_shopping_line", "status": "invalid",
                "summary": f"{item.name} is already ticked off.",
                "candidates": []}

    verb = "untick" if untick else "tick"
    return {
        "type": "tick_shopping_line",
        "status": "ready",
        "summary": f"{verb.capitalize()} {item.name} on \"{primary.name}\"?",
        "payload": {
            "shopping_list_id": str(primary.id),
            "line_id": str(line.id),
            "stock_item_name": item.name,
            "is_ticked": not untick,
        },
        "candidates": [],
    }


def commit_tick_shopping_line(payload: dict[str, Any]) -> dict[str, Any]:
    handler = UpdateLineHandler(SqlAlchemyRepository())
    response = handler.handle(
        UpdateLineRequest(is_ticked=bool(payload["is_ticked"])),
        shopping_list_id=UUID(payload["shopping_list_id"]),
        line_id=UUID(payload["line_id"]),
    )
    if response.line_not_found:
        return {"ok": False, "message": "That line's not on the list anymore."}
    verb = "ticked" if payload["is_ticked"] else "unticked"
    return {"ok": True, "message": f"Done. {verb} {payload['stock_item_name']}."}


# ── move_item ──────────────────────────────────────────────────────────

def _find_location(repo: SqlAlchemyRepository, name: str) -> tuple[str, list[StockLocation]]:
    return _match_kind(resolve_by_name(lambda: repo.get(StockLocation), StockLocation, name))


def propose_move_item(args: dict) -> dict[str, Any]:
    item_resolved = _resolve_single_item(str(args.get("item_name") or "").strip())
    if isinstance(item_resolved, dict):
        return {"type": "move_item", **item_resolved}
    item: StockItem = item_resolved

    dest_name = str(args.get("destination") or "").strip()
    if not dest_name:
        return {"type": "move_item", "status": "invalid",
                "summary": f"Where should I move {item.name}?", "candidates": []}
    repo = SqlAlchemyRepository()
    _, locations = _find_location(repo, dest_name)
    if not locations:
        return {"type": "move_item", "status": "not_found",
                "summary": f"No location matches \"{dest_name}\".", "candidates": []}
    if len(locations) > 1:
        return {
            "type": "move_item",
            "status": "ambiguous",
            "summary": f"A few locations match \"{dest_name}\". Which one?",
            "candidates": [
                {"location_id": str(l.id), "name": l.name, "kind": l.kind}
                for l in locations[:MAX_CANDIDATES]
            ],
        }
    destination = locations[0]
    if item.stock_location and item.stock_location.id == destination.id:
        return {"type": "move_item", "status": "invalid",
                "summary": f"{item.name} is already in {destination.name}.",
                "candidates": []}
    current = item.stock_location.name if item.stock_location else "(no location)"
    return {
        "type": "move_item",
        "status": "ready",
        "summary": f"Move {item.name} from {current} to {destination.name}?",
        "payload": {
            "stock_item_id": str(item.id),
            "stock_item_name": item.name,
            "destination_location_id": str(destination.id),
            "destination_name": destination.name,
        },
        "candidates": [],
    }


def commit_move_item(payload: dict[str, Any]) -> dict[str, Any]:
    handler = MoveStockItemHandler(SqlAlchemyRepository())
    response = handler.handle(
        MoveStockItemRequest(destination_location_id=UUID(payload["destination_location_id"])),
        stock_item_id=UUID(payload["stock_item_id"]),
    )
    if getattr(response, "stock_item_not_found", False):
        return {"ok": False, "message": "I lost track of that item."}
    if response.destination_not_found:
        return {"ok": False, "message": "That destination doesn't exist anymore."}
    return {"ok": True, "message": f"Done. Moved {payload['stock_item_name']} to {payload['destination_name']}."}


# Chunk 2 removed `set_primary_list` — "primary" is now inferred from DRAFT
# count at read time, so there's no stored flag for the assistant to set.

# ── plan_meal_for_date ────────────────────────────────────────────────


def _plan_covering(repo: SqlAlchemyRepository, target: date) -> MealPlan | None:
    """Find the meal plan whose existing entries straddle the target date.
    Falls back to the latest plan whose start_date is on/before the target."""
    plans: list[MealPlan] = (
        repo.get(MealPlan).include(MealPlan.Fields.ENTRIES).all()
    )
    if not plans:
        return None
    covering = [p for p in plans if any(e.scheduled_for == target for e in (p.entries or []))]
    if covering:
        return covering[0]
    # Plans whose start_date is <= target — pick the most recent.
    earlier = [p for p in plans if p.start_date <= target]
    if earlier:
        return max(earlier, key=lambda p: p.start_date)
    # Otherwise just take the earliest plan and we'll add the entry to it.
    return min(plans, key=lambda p: p.start_date)


def propose_plan_meal_for_date(args: dict) -> dict[str, Any]:
    name = str(args.get("meal_name") or "").strip()
    if not name:
        return {"type": "plan_meal_for_date", "status": "invalid",
                "summary": "Which meal should I plan?", "candidates": []}
    date_str = str(args.get("date") or "").strip()
    try:
        scheduled = date.fromisoformat(date_str)
    except ValueError:
        return {"type": "plan_meal_for_date", "status": "invalid",
                "summary": "I need a date in yyyy-mm-dd format.", "candidates": []}
    try:
        servings = max(1, int(args.get("servings", 1)))
    except (TypeError, ValueError):
        servings = 1

    repo = SqlAlchemyRepository()
    # No slot named → the household's first slot. The vocabulary is the
    # household's own, so the assistant doesn't assume a "Dinner" exists
    # (the 02-R32 rule).
    slot = str(args.get("slot") or "").strip() or next(iter(ordered_slot_names(repo)), "")
    recipes = _find_recipe(repo, name)
    if not recipes:
        return {"type": "plan_meal_for_date", "status": "not_found",
                "summary": f"No meal called \"{name}\".", "candidates": []}
    if len(recipes) > 1:
        return {
            "type": "plan_meal_for_date",
            "status": "ambiguous",
            "summary": f"A few meals match \"{name}\". Which?",
            "candidates": [{"recipe_id": str(r.id), "name": r.name} for r in recipes[:MAX_CANDIDATES]],
        }
    recipe = recipes[0]
    plan = _plan_covering(repo, scheduled)
    if plan is None:
        return {"type": "plan_meal_for_date", "status": "not_found",
                "summary": "You don't have a meal plan to add to yet.",
                "candidates": []}
    return {
        "type": "plan_meal_for_date",
        "status": "ready",
        "summary": f"Plan {recipe.name} for {slot.lower()} on {scheduled.isoformat()} (×{servings}) in \"{plan.name}\"?",
        "payload": {
            "meal_plan_id": str(plan.id),
            "recipe_id": str(recipe.id),
            "meal_name": recipe.name,
            "scheduled_for": scheduled.isoformat(),
            "slot": slot,
            "servings": servings,
        },
        "candidates": [],
    }


def commit_plan_meal_for_date(payload: dict[str, Any]) -> dict[str, Any]:
    """Append the requested entry to the target plan. UpdateMealPlanHandler
    replaces the plan's forward entries, so we resend the existing forward
    ones and append. Past and consumed entries are preserved server-side and
    must not be resent (a past one is refused as "in the past"). Each resent
    row carries its id, batch and fresh flag, so ids don't churn and cook
    batches survive the edit."""
    repo = SqlAlchemyRepository()
    plan_id = UUID(payload["meal_plan_id"])
    plan: MealPlan | None = (
        repo.get(MealPlan)
        .include(MealPlan.Fields.ENTRIES).then_include(MealPlanEntry.Fields.RECIPE)
        .by_id(plan_id)
    )
    if plan is None:
        return {"ok": False, "message": "That meal plan doesn't exist anymore."}
    today = household_today(repo)
    existing = [
        UpdateMealPlanEntryRequest(
            meal_plan_entry_id=e.id,
            recipe_id=e.recipe.id,
            scheduled_for=e.scheduled_for,
            servings=e.servings,
            slot=e.slot,
            cook_key=str(e.cook_batch_id) if e.cook_batch_id is not None else None,
            cook_fresh=e.cook_fresh,
        )
        for e in (plan.entries or [])
        if e.recipe is not None and e.consumed_at is None and e.scheduled_for >= today
    ]
    existing.append(UpdateMealPlanEntryRequest(
        recipe_id=UUID(payload["recipe_id"]),
        scheduled_for=date.fromisoformat(payload["scheduled_for"]),
        servings=int(payload["servings"]),
        slot=payload["slot"],
    ))
    handler = UpdateMealPlanHandler(SqlAlchemyRepository())
    response = handler.handle(UpdateMealPlanRequest(entries=existing), meal_plan_id=plan_id)
    if response.meal_plan_not_found:
        return {"ok": False, "message": "That meal plan vanished mid-request."}
    if response.missing_recipe_ids:
        return {"ok": False, "message": "One of the meals couldn't be found."}
    if response.has_past_entry:
        return {"ok": False, "message": "Can't plan a meal in the past."}
    if response.invalid_slot_message or response.invalid_cook_batch_message:
        return {"ok": False,
                "message": response.invalid_slot_message or response.invalid_cook_batch_message}
    return {
        "ok": True,
        "message": f"Done. {payload['meal_name']} planned for {payload['slot'].lower()} on {payload['scheduled_for']}.",
    }


# ── add_recipe_to_list ────────────────────────────────────────────────

def _find_recipe(repo: SqlAlchemyRepository, name: str) -> list[Recipe]:
    return resolve_by_name(lambda: repo.get(Recipe), Recipe, name).matches


def propose_add_recipe_to_list(args: dict) -> dict[str, Any]:
    name = str(args.get("recipe_name") or "").strip()
    if not name:
        return {"type": "add_recipe_to_list", "status": "invalid",
                "summary": "Which recipe's ingredients should I add?", "candidates": []}
    missing_only = bool(args.get("missing_only", True))
    repo = SqlAlchemyRepository()
    recipes = _find_recipe(repo, name)
    if not recipes:
        return {"type": "add_recipe_to_list", "status": "not_found",
                "summary": f"No recipe matches \"{name}\".", "candidates": []}
    if len(recipes) > 1:
        return {
            "type": "add_recipe_to_list",
            "status": "ambiguous",
            "summary": f"A few recipes match \"{name}\". Which?",
            "candidates": [{"recipe_id": str(r.id), "name": r.name} for r in recipes[:MAX_CANDIDATES]],
        }
    recipe = recipes[0]
    primary = _primary_list(repo)
    if primary is None:
        return {"type": "add_recipe_to_list", "status": "invalid",
                "summary": "You don't have a primary shopping list set yet.",
                "candidates": []}

    # Rehydrate ingredients with stock-level info so we know what's missing.
    full: Recipe | None = (
        repo.get(Recipe)
        .include(Recipe.Fields.INGREDIENTS)
        .then_include(RecipeIngredient.Fields.STOCK_ITEM)
        .then_include(StockItem.Fields.STOCK_LEVEL)
        .by_id(recipe.id)
    )
    ingredients = (full.ingredients if full else []) or []
    candidates: list[dict[str, Any]] = []
    for ing in ingredients:
        item = ing.stock_item
        if item is None:
            continue
        # Cookbook revision §1.9 — optional ingredients are excluded from
        # the assistant's add-recipe-to-list candidates (mirrors the
        # picker modal default: opt-in only).
        if ing.is_optional:
            continue
        if missing_only and not is_missing(item.stock_level):
            continue
        candidates.append({"stock_item_id": str(item.id), "name": item.name})

    if not candidates:
        msg = (
            f"Nothing missing for {recipe.name}. You can cook it now."
            if missing_only
            else f"{recipe.name} has no tracked ingredients to add."
        )
        return {"type": "add_recipe_to_list", "status": "invalid",
                "summary": msg, "candidates": []}

    count_phrase = f"{len(candidates)} missing ingredient" + ("s" if len(candidates) != 1 else "")
    if not missing_only:
        count_phrase = f"all {len(candidates)} tracked ingredient" + ("s" if len(candidates) != 1 else "")
    return {
        "type": "add_recipe_to_list",
        "status": "ready",
        "summary": f"Add {count_phrase} for {recipe.name} to \"{primary.name}\"?",
        "payload": {
            "shopping_list_id": str(primary.id),
            "list_name": primary.name,
            "recipe_name": recipe.name,
            "stock_item_ids": [c["stock_item_id"] for c in candidates],
            "ingredient_names": [c["name"] for c in candidates],
        },
        "candidates": [],
    }


def commit_add_recipe_to_list(payload: dict[str, Any]) -> dict[str, Any]:
    handler = AddLineHandler(SqlAlchemyRepository())
    list_id = UUID(payload["shopping_list_id"])
    added = 0
    already = 0
    missing = 0
    for raw in payload.get("stock_item_ids", []) or []:
        try:
            response = handler.handle(
                AddLineRequest(stock_item_id=UUID(str(raw)), quantity=1),
                shopping_list_id=list_id,
            )
        except ValueError:
            # A malformed id in the payload (pydantic's ValidationError is a
            # ValueError); anything else is a real failure and raises.
            missing += 1
            continue
        if response.item_not_found or response.list_not_found:
            missing += 1
        elif response.already_on_list:
            already += 1
        elif response.line_id is not None:
            added += 1
    bits: list[str] = []
    if added:
        bits.append(f"added {added}")
    if already:
        bits.append(f"{already} already there")
    if missing:
        bits.append(f"{missing} couldn't be added")
    detail = ", ".join(bits) if bits else "nothing changed"
    return {
        "ok": added > 0 or already > 0,
        "message": f"Done. {detail} on {payload['list_name']}.",
    }


# ── cook_recipe ────────────────────────────────────────────────────────

_MAX_COOK = 999


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(n, _MAX_COOK))


def propose_cook_recipe(args: dict) -> dict[str, Any]:
    name = str(args.get("recipe_name") or "").strip()
    if not name:
        return {"type": "cook_recipe", "status": "invalid",
                "summary": "Which recipe did you cook?", "candidates": []}
    count = _coerce_positive_int(args.get("meals_cooked"), 1)

    repo = SqlAlchemyRepository()
    recipes = _find_recipe(repo, name)
    if not recipes:
        return {"type": "cook_recipe", "status": "not_found",
                "summary": f"No recipe matches \"{name}\".", "candidates": []}
    if len(recipes) > 1:
        return {
            "type": "cook_recipe",
            "status": "ambiguous",
            "summary": f"A few recipes match \"{name}\". Which?",
            "candidates": [{"recipe_id": str(r.id), "name": r.name} for r in recipes[:MAX_CANDIDATES]],
        }
    recipe = recipes[0]
    suffix = "meal" if count == 1 else "meals"
    return {
        "type": "cook_recipe",
        "status": "ready",
        "summary": f"Log {count} cooked {suffix} for {recipe.name}? (Pool: {recipe.available_meals or 0} → {(recipe.available_meals or 0) + count})",
        "payload": {
            "recipe_id": str(recipe.id),
            "recipe_name": recipe.name,
            "meals_cooked": count,
        },
        "candidates": [],
    }


def commit_cook_recipe(payload: dict[str, Any]) -> dict[str, Any]:
    from dora_api.features.recipes.cook_recipe import (CookRecipeHandler,
                                                       CookRecipeRequest)
    handler = CookRecipeHandler(SqlAlchemyRepository())
    response = handler.handle(
        CookRecipeRequest(meals_cooked=int(payload["meals_cooked"])),
        recipe_id=UUID(payload["recipe_id"]),
    )
    if response.recipe_not_found:
        return {"ok": False, "message": "That recipe doesn't exist anymore."}
    n = int(payload["meals_cooked"])
    suffix = "meal" if n == 1 else "meals"
    return {
        "ok": True,
        "message": (
            f"Logged {n} cooked {suffix} for {payload['recipe_name']}. "
            f"Pool: {response.available_meals}."
        ),
    }


# ── adjust_recipe_meals ────────────────────────────────────────────────

_MAX_DELTA = 999


def _coerce_signed_int(value: Any) -> int | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return max(-_MAX_DELTA, min(n, _MAX_DELTA))


def propose_adjust_recipe_meals(args: dict) -> dict[str, Any]:
    name = str(args.get("recipe_name") or "").strip()
    if not name:
        return {"type": "adjust_recipe_meals", "status": "invalid",
                "summary": "Which recipe's meal count should I adjust?", "candidates": []}
    # FU-515 B.3 — `_coerce_signed_int` already clamps delta to ±_MAX_DELTA
    # (±999) at the boundary, so a nonsense magnitude can't reach the pool.
    delta = _coerce_signed_int(args.get("delta"))
    if delta is None or delta == 0:
        return {"type": "adjust_recipe_meals", "status": "invalid",
                "summary": "I need a non-zero amount, e.g. -1 for 'I ate one' or +2 for 'I have two more'.",
                "candidates": []}

    repo = SqlAlchemyRepository()
    recipes = _find_recipe(repo, name)
    if not recipes:
        return {"type": "adjust_recipe_meals", "status": "not_found",
                "summary": f"No recipe matches \"{name}\".", "candidates": []}
    if len(recipes) > 1:
        return {
            "type": "adjust_recipe_meals",
            "status": "ambiguous",
            "summary": f"A few recipes match \"{name}\". Which?",
            "candidates": [{"recipe_id": str(r.id), "name": r.name} for r in recipes[:MAX_CANDIDATES]],
        }
    recipe = recipes[0]
    # FU-317 Chunk 2 — preview shares the same floor rule as the write
    # (features/recipes/pool.py). Keep them wired to one authority so
    # a future rule change doesn't drift preview vs commit.
    from dora_api.features.recipes.pool import preview_pool_after
    current = recipe.available_meals or 0
    projected = preview_pool_after(current, delta)
    sign = "+" if delta > 0 else ""
    return {
        "type": "adjust_recipe_meals",
        "status": "ready",
        "summary": f"Adjust {recipe.name} by {sign}{delta}? (Pool: {current} → {projected})",
        "payload": {
            "recipe_id": str(recipe.id),
            "recipe_name": recipe.name,
            "delta": delta,
        },
        "candidates": [],
    }


def commit_adjust_recipe_meals(payload: dict[str, Any]) -> dict[str, Any]:
    from dora_api.features.recipes.adjust_recipe_meals import (
        AdjustRecipeMealsHandler, AdjustRecipeMealsRequest)
    handler = AdjustRecipeMealsHandler(SqlAlchemyRepository())
    response = handler.handle(
        AdjustRecipeMealsRequest(delta=int(payload["delta"])),
        recipe_id=UUID(payload["recipe_id"]),
    )
    if response.recipe_not_found:
        return {"ok": False, "message": "That recipe doesn't exist anymore."}
    return {
        "ok": True,
        "message": (
            f"Updated {payload['recipe_name']}. Pool: {response.available_meals}."
        ),
    }


# ── trim_list_to_budget ────────────────────────────────────────────────

def propose_trim_list_to_budget(_args: dict) -> dict[str, Any]:
    """FU-448 — preview the trim on the user's primary list. Returns
    'ready' with a summary sentence that names the amount to trim and
    the cut count; commit re-runs in apply mode."""
    repo = SqlAlchemyRepository()
    primary = _primary_list(repo)
    if primary is None:
        return {
            "type": "trim_list_to_budget", "status": "invalid",
            "summary": "You don't have a primary shopping list set yet.",
            "candidates": [],
        }
    if current_user_id() is None:
        return {
            "type": "trim_list_to_budget", "status": "invalid",
            "summary": "I can't see who's asking. Try refreshing.",
            "candidates": [],
        }
    preview = TrimToBudgetHandler(repo).handle(primary.id, TrimToBudgetRequest(mode="preview"))
    currency = get_or_create_app_setting(repo).currency
    if preview is None:
        return {
            "type": "trim_list_to_budget", "status": "invalid",
            "summary": "I couldn't read your primary list.",
            "candidates": [],
        }
    if preview.budget_target is None:
        return {
            "type": "trim_list_to_budget", "status": "invalid",
            "summary": (
                "You haven't set a grocery budget yet. Turn it on in "
                "Settings → Money."
            ),
            "candidates": [],
        }
    if preview.overshoot <= 0:
        return {
            "type": "trim_list_to_budget", "status": "invalid",
            "summary": (
                f"\"{primary.name}\" is already inside your "
                f"{format_money(preview.budget_target, currency)} remaining, so nothing to trim."
            ),
            "candidates": [],
        }
    if not preview.trimmed:
        # Overshooting but every line is essential / near-term / verdict=buy.
        return {
            "type": "trim_list_to_budget", "status": "invalid",
            "summary": (
                f"\"{primary.name}\" is {format_money(preview.overshoot, currency)} over budget "
                f"but everything on it is either essential or booked for a "
                f"meal soon, so nothing is safe to cut."
            ),
            "candidates": [],
        }
    cut_count = len(preview.trimmed)
    still_hint = (
        f" Still {format_money(preview.still_over, currency)} over after that."
        if preview.still_over > 0 else ""
    )
    return {
        "type": "trim_list_to_budget",
        "status": "ready",
        "summary": (
            f"Trim {format_money(sum(t.saved for t in preview.trimmed), currency)} off "
            f"\"{primary.name}\" ({cut_count} item"
            f"{'' if cut_count == 1 else 's'}) to fit your "
            f"{format_money(preview.budget_target, currency)} remaining budget?{still_hint}"
        ),
        "payload": {
            "shopping_list_id": str(primary.id),
            "list_name": primary.name,
        },
        "candidates": [],
    }


def commit_trim_list_to_budget(payload: dict[str, Any]) -> dict[str, Any]:
    """Re-run trim-to-budget in apply mode on the same list, ignoring the
    preview payload's specific cut set — the classifier is deterministic
    given current state, and a fresh apply is the honest behaviour if
    anything shifted between propose + commit."""
    if current_user_id() is None:
        return {"ok": False, "message": "I couldn't confirm who's asking."}
    repo = SqlAlchemyRepository()
    result = TrimToBudgetHandler(repo).handle(
        UUID(payload["shopping_list_id"]), TrimToBudgetRequest(mode="apply"),
    )
    currency = get_or_create_app_setting(repo).currency
    if result is None or not result.applied or not result.trimmed:
        return {"ok": False, "message": "Couldn't trim that list right now."}
    saved = sum(t.saved for t in result.trimmed)
    n = len(result.trimmed)
    tail = ""
    if result.still_over > 0:
        tail = (
            f" Still {format_money(result.still_over, currency)} over. I've cut everything "
            f"that was safe."
        )
    return {
        "ok": True,
        "message": (
            f"Done. Trimmed {format_money(saved, currency)} off "
            f"\"{payload['list_name']}\" ({n} item"
            f"{'' if n == 1 else 's'} moved to Deferred).{tail}"
        ),
    }


# ── Public dispatchers ─────────────────────────────────────────────────

PROPOSERS: dict[str, Callable[[dict], dict]] = {
    "update_stock_level": propose_update_stock_level,
    "mark_opened": propose_mark_opened,
    "push_expiry": propose_push_expiry,
    "tick_shopping_line": propose_tick_shopping_line,
    "move_item": propose_move_item,
    "plan_meal_for_date": propose_plan_meal_for_date,
    "add_recipe_to_list": propose_add_recipe_to_list,
    "cook_recipe": propose_cook_recipe,
    "adjust_recipe_meals": propose_adjust_recipe_meals,
    "trim_list_to_budget": propose_trim_list_to_budget,
}

COMMITTERS: dict[str, Callable[[dict], dict]] = {
    "update_stock_level": commit_update_stock_level,
    "mark_opened": commit_mark_opened,
    "push_expiry": commit_push_expiry,
    "tick_shopping_line": commit_tick_shopping_line,
    "move_item": commit_move_item,
    "plan_meal_for_date": commit_plan_meal_for_date,
    "add_recipe_to_list": commit_add_recipe_to_list,
    "cook_recipe": commit_cook_recipe,
    "adjust_recipe_meals": commit_adjust_recipe_meals,
    "trim_list_to_budget": commit_trim_list_to_budget,
}


def is_confirm_action(name: str) -> bool:
    return name in PROPOSERS


def propose(name: str, args: dict) -> dict | None:
    proposer = PROPOSERS.get(name)
    return proposer(args or {}) if proposer else None


def commit(name: str, payload: dict) -> dict | None:
    committer = COMMITTERS.get(name)
    return committer(payload or {}) if committer else None
