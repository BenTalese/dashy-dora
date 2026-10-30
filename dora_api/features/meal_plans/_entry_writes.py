"""The entry-write half shared by meal-plan create and update (finalisation
02-R7/R8): the entry request shape, the pre-write checks, recipe resolution,
cook-batch minting, entry construction and the outcome-to-HTTP mapping."""
import logging
from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Sequence
from uuid import UUID

from flask import Response
from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.cook_batch import CookBatch
from dora_api.domain.entities.meal_plan_entry import MealPlanEntry
from dora_api.domain.entities.recipe import Recipe
from dora_api.features.meal_plans.cook_batch_grouping import (
    group_by_cook_key, validate_cook_groups)
from dora_api.features.meal_slots.slot_validation import (find_invalid_slot,
                                                          invalid_slot_message)
from dora_api.infrastructure.api_response import (bad_request,
                                                  entity_existence_failures)
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.utils import field_of

_LOGGER = logging.getLogger(__name__)


class MealPlanEntryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: UUID
    scheduled_for: date
    servings: int = Field(default = 1, ge = 1)
    slot: str = Field(min_length = 1, max_length = 50)
    # PROPOSAL_MEAL_PLANS_PART_2 — optional transient grouping token. Entries
    # sharing a `cook_key` become one CookBatch (cook once, eat several days).
    # It is NOT a DB id — the server materialises a fresh CookBatch per group.
    cook_key: str | None = Field(default = None, max_length = 64)
    # Owner 2026-09-04 — cooked on the day, outside the cooked-portion pool.
    # Mutually exclusive with `cook_key` (validated in `validate_cook_groups`).
    cook_fresh: bool = False


@dataclass(slots=True)
class MealPlanWriteOutcome:
    missing_recipe_ids: tuple[UUID, ...] = ()
    has_past_entry: bool = False
    invalid_slot_message: str | None = None
    invalid_cook_batch_message: str | None = None


def check_entries(
    entries: Sequence[MealPlanEntryRequest],
    today: date,
    allowed_slots: set[str],
    valid_slots: set[str],
    preserved_batch_keys: frozenset[str] = frozenset(),
) -> MealPlanWriteOutcome | None:
    """The structural checks every entry write runs before touching the DB,
    or None when they all pass. Slots are free-text labels validated against
    the household vocabulary (R-010); the message names `valid_slots`, not the
    allowance, so a deleted slot is never offered back. `preserved_batch_keys`
    are the ids of batches an update keeps (see `validate_cook_groups`)."""
    bad_slot = find_invalid_slot((e.slot for e in entries), allowed_slots)
    if bad_slot is not None:
        return MealPlanWriteOutcome(invalid_slot_message = invalid_slot_message(bad_slot, valid_slots))
    cook_batch_error = validate_cook_groups(entries, preserved_batch_keys)
    if cook_batch_error is not None:
        return MealPlanWriteOutcome(invalid_cook_batch_message = cook_batch_error)
    if any(e.scheduled_for < today for e in entries):
        return MealPlanWriteOutcome(has_past_entry = True)
    return None


def resolve_recipes(
    repository: Repository, entries: Iterable[MealPlanEntryRequest],
) -> tuple[dict[UUID, Recipe], list[UUID]]:
    """Each named recipe loaded once (a cook group repeats an id), before any
    write, so a missing recipe never leaves an orphan plan or batch behind."""
    by_id: dict[UUID, Recipe] = {}
    missing: List[UUID] = []
    for entry in entries:
        if entry.recipe_id in by_id or entry.recipe_id in missing:
            continue
        recipe = repository.get(Recipe).by_id(entry.recipe_id)
        if recipe:
            by_id[entry.recipe_id] = recipe
        else:
            missing.append(entry.recipe_id)
    return by_id, missing


def mint_batches(
    repository: Repository,
    meal_plan_id: UUID,
    entries: Sequence[MealPlanEntryRequest],
    preserved_by_key: dict[str, CookBatch] | None = None,
) -> dict[str, CookBatch]:
    """One CookBatch per `cook_key` group. A key naming a preserved batch
    re-attaches to it instead of minting a second one. New batches are flushed
    so the entries' FK sees them (no relationship links entry to batch)."""
    preserved_by_key = preserved_by_key or {}
    by_key: dict[str, CookBatch] = {}
    minted = False
    for key, members in group_by_cook_key(entries).items():
        existing = preserved_by_key.get(str(key))
        if existing is not None:
            by_key[key] = existing
            continue
        batch = CookBatch(meal_plan_id = meal_plan_id, recipe_id = members[0].recipe_id)
        repository.add(batch)
        by_key[key] = batch
        minted = True
    if minted:
        repository.flush()
    return by_key


def batch_for(entry: MealPlanEntryRequest, batches: dict[str, CookBatch]) -> CookBatch | None:
    return batches.get(entry.cook_key) if entry.cook_key else None


def new_entry(request: MealPlanEntryRequest, recipe: Recipe, batch: CookBatch | None) -> MealPlanEntry:
    return MealPlanEntry(
        recipe = recipe,
        scheduled_for = request.scheduled_for,
        servings = request.servings,
        slot = request.slot,
        cook_batch_id = batch.id if batch else None,
        cook_fresh = request.cook_fresh,
    )


def apply_to_entry(
    entry: MealPlanEntry, request: MealPlanEntryRequest, recipe: Recipe, batch: CookBatch | None,
) -> None:
    entry.recipe = recipe
    entry.scheduled_for = request.scheduled_for
    entry.servings = request.servings
    entry.slot = request.slot
    entry.cook_batch_id = batch.id if batch else None
    entry.cook_fresh = request.cook_fresh


def meal_plan_write_error_response(
    outcome: MealPlanWriteOutcome, request_model: type[BaseModel],
) -> Response | None:
    """The error response for a failed entry write, or None when it succeeded."""
    if outcome.invalid_slot_message:
        return bad_request(outcome.invalid_slot_message)
    if outcome.invalid_cook_batch_message:
        return bad_request(outcome.invalid_cook_batch_message)
    if outcome.has_past_entry:
        return bad_request("Meal plan entries cannot be scheduled in the past.")
    if outcome.missing_recipe_ids:
        _LOGGER.warning("Recipes not found: %s", outcome.missing_recipe_ids)
        return entity_existence_failures(
            Recipe.__name__, field_of(request_model, "entries"), *outcome.missing_recipe_ids,
        )
    return None
