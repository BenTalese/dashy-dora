import logging
from dataclasses import dataclass
from datetime import date
from typing import List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.meal_plan import MealPlan
from dora_api.domain.entities.meal_plan_entry import MealPlanEntry
from dora_api.domain.types import EMPTY_UUID
from dora_api.features.app_settings.clock import household_today
from dora_api.features.meal_plans._entry_writes import (
    MealPlanEntryRequest, MealPlanWriteOutcome, batch_for, check_entries,
    meal_plan_write_error_response, mint_batches, new_entry, resolve_recipes)
from dora_api.features.meal_plans.get_meal_plans import GetMealPlansHandler, get_meal_plans
from dora_api.features.meal_slots.slot_validation import get_valid_slot_names
from dora_api.features.routers import MEAL_PLAN_ROUTER
from dora_api.infrastructure.api_response import created
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


class CreateMealPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Optional (C-2.E): the planner creates nameless week-plans. A name may
    # still be supplied (e.g. templates / legacy callers).
    name: str | None = Field(default = None, max_length = 255)
    start_date: date
    entries: List[MealPlanEntryRequest] = Field(default_factory = list)


@dataclass(slots=True)
class CreateMealPlanResponse(MealPlanWriteOutcome):
    new_meal_plan_id: UUID = EMPTY_UUID


class CreateMealPlanHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: CreateMealPlanRequest) -> CreateMealPlanResponse:
        _ValidSlots = get_valid_slot_names(self.repository)
        _Failure = check_entries(
            request.entries, household_today(self.repository), _ValidSlots, _ValidSlots
        )
        if _Failure is not None:
            return CreateMealPlanResponse(
                invalid_slot_message = _Failure.invalid_slot_message,
                invalid_cook_batch_message = _Failure.invalid_cook_batch_message,
                has_past_entry = _Failure.has_past_entry,
            )

        _RecipeById, _MissingIds = resolve_recipes(self.repository, request.entries)
        if _MissingIds:
            return CreateMealPlanResponse(missing_recipe_ids = tuple(_MissingIds))

        # Plan first (batches FK it), then batches (entries FK them), then entries.
        # No relationships link plan<-batch or entry->batch, so flush between each
        # so SQLite's FK check sees the parent row (repository.flush contract).
        _NewPlan = MealPlan(name = request.name, start_date = request.start_date, entries = [])
        self.repository.add(_NewPlan)
        self.repository.flush()

        _BatchByKey = mint_batches(self.repository, _NewPlan.id, request.entries)

        _Entries: List[MealPlanEntry] = []
        for _EntryRequest in request.entries:
            _Entry = new_entry(
                _EntryRequest, _RecipeById[_EntryRequest.recipe_id], batch_for(_EntryRequest, _BatchByKey)
            )
            self.repository.add(_Entry)
            _Entries.append(_Entry)
        _NewPlan.entries = _Entries

        self.repository.save_changes()
        return CreateMealPlanResponse(new_meal_plan_id = _NewPlan.id)


@MEAL_PLAN_ROUTER.route("", methods=["POST"])
@has_request_body(CreateMealPlanRequest)
def create_meal_plan():
    _Handler = CreateMealPlanHandler(SqlAlchemyRepository())
    _Request: CreateMealPlanRequest = get_request_body()
    _Response = _Handler.handle(_Request)

    _Error = meal_plan_write_error_response(_Response, CreateMealPlanRequest)
    if _Error is not None:
        return _Error

    _Dto = GetMealPlansHandler(SqlAlchemyRepository()).handle_by_id(
        _Response.new_meal_plan_id
    )
    return created(
        _Response.new_meal_plan_id,
        f"{MEAL_PLAN_ROUTER.name}.{get_meal_plans.__name__}",
        "meal_plan_id",
        body = _Dto,
    )
