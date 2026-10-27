import logging
from dataclasses import dataclass
from datetime import date
from typing import List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.cook_batch import CookBatch
from dora_api.domain.entities.meal_plan import MealPlan
from dora_api.domain.entities.meal_plan_entry import MealPlanEntry
from dora_api.features.app_settings.clock import household_today
from dora_api.features.meal_plans._entry_writes import (
    MealPlanEntryRequest, MealPlanWriteOutcome, apply_to_entry, batch_for,
    check_entries, meal_plan_write_error_response, mint_batches, new_entry,
    resolve_recipes)
from dora_api.features.meal_slots.slot_validation import (allowed_slot_names,
                                                          get_valid_slot_names)
from dora_api.features.routers import MEAL_PLAN_ROUTER
from dora_api.infrastructure.api_response import (bad_request, no_content,
                                                  not_found)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


class UpdateMealPlanEntryRequest(MealPlanEntryRequest):
    # FU-878 — the saved entry this row edits. A forward entry of this plan
    # with this id is updated in place and keeps its id; anything else (no id,
    # an id from another plan, a past entry's id, or one already claimed by an
    # earlier row) is created as a new entry.
    meal_plan_entry_id: UUID | None = None


class UpdateMealPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default = None, min_length = 1, max_length = 255)
    start_date: date | None = None
    entries: List[UpdateMealPlanEntryRequest] | None = None
    # Explicit opt-in for the destructive "clear every future entry"
    # path. Sending `entries: []` without this flag is rejected so a
    # caller can't accidentally nuke a plan by forgetting to populate
    # the array. Past/consumed entries are preserved regardless.
    confirm_clear_entries: bool = False


@dataclass(slots=True)
class UpdateMealPlanResponse(MealPlanWriteOutcome):
    meal_plan_not_found: bool = False
    needs_clear_confirmation: bool = False


class UpdateMealPlanHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: UpdateMealPlanRequest, meal_plan_id: UUID) -> UpdateMealPlanResponse:
        _Plan = (
            self.repository
            .get(MealPlan)
            .include(MealPlan.Fields.ENTRIES)
            .one(EntityField(MealPlan, "id").eq(meal_plan_id))
        )
        if not _Plan:
            return UpdateMealPlanResponse(meal_plan_not_found = True)

        _SetFields = request.model_fields_set

        if "name" in _SetFields and request.name is not None:
            _Plan.name = request.name
        if "start_date" in _SetFields and request.start_date is not None:
            _Plan.start_date = request.start_date

        if "entries" in _SetFields and request.entries is not None:
            if len(request.entries) == 0 and not request.confirm_clear_entries:
                return UpdateMealPlanResponse(needs_clear_confirmation = True)

            # Validate slot names against the household MealSlot vocabulary
            # (R-010) PLUS the labels this plan already carries. Deleting a
            # slot is deliberately non-cascading — existing entries keep their
            # label — and the planner resends every forward entry on each edit,
            # so validating the payload against the live vocabulary alone made
            # the whole week unsaveable the moment one entry held a deleted
            # slot (owner report 2026-09-01). A genuinely NEW off-vocab slot is
            # still refused; see `allowed_slot_names`.
            _ValidSlots = get_valid_slot_names(self.repository)
            _AllowedSlots = allowed_slot_names(
                _ValidSlots, (_Entry.slot for _Entry in (_Plan.entries or []))
            )
            _Today = household_today(self.repository)
            # The message names the current vocabulary, not the allowance:
            # "Allowed: …, Snack" would read as an invitation to keep using a
            # slot the household has deleted. A forward entry scheduled before
            # today is a genuine "can't schedule in the past" error: the client
            # never sends past entries (FU-595, preserved server-side below).
            _Failure = check_entries(request.entries, _Today, _AllowedSlots, _ValidSlots)
            if _Failure is not None:
                return UpdateMealPlanResponse(
                    invalid_slot_message = _Failure.invalid_slot_message,
                    invalid_cook_batch_message = _Failure.invalid_cook_batch_message,
                    has_past_entry = _Failure.has_past_entry,
                )

            # Preserve the immutable past. Past days are read-only, so the
            # client resends only forward-looking entries; anything already
            # in the plan that is consumed OR scheduled before today is
            # history we keep as-is, replacing only the forward portion.
            # FU-595: this must cover past-*unconsumed* entries too, not just
            # consumed ones. A past day the user didn't cook (auto-drain off,
            # or "Didn't cook") is unconsumed; if it weren't preserved here the
            # replace would silently drop it, and the old client's workaround
            # of resending it tripped the past-date guard above — freezing the
            # whole week.
            _PreservedExisting = [
                _Entry for _Entry in (_Plan.entries or [])
                if _Entry.consumed_at is not None or _Entry.scheduled_for < _Today
            ]

            _RecipeById, _MissingIds = resolve_recipes(self.repository, request.entries)
            if _MissingIds:
                return UpdateMealPlanResponse(missing_recipe_ids = tuple(_MissingIds))

            # PROPOSAL_MEAL_PLANS_PART_2 — forward CookBatches are rebuilt from the
            # resent cook_keys. Keep only batches still referenced by a preserved
            # (past/consumed) entry; delete the rest of this plan's batches. Forward
            # entries that pointed at one are re-pointed below; the SET NULL FK means
            # deleting a batch first can't trip an FK error.
            _PreservedBatchIds = {
                _Entry.cook_batch_id for _Entry in _PreservedExisting
                if _Entry.cook_batch_id is not None
            }
            _ExistingBatches = self.repository.get(CookBatch).all(
                EntityField(CookBatch, CookBatch.Fields.MEAL_PLAN_ID).eq(meal_plan_id)
            )
            for _Batch in _ExistingBatches:
                if _Batch.id not in _PreservedBatchIds:
                    self.repository.remove(_Batch)
            self.repository.flush()

            # Rebuild the forward batches from the resent cook_keys.
            #
            # A key that names a batch we just PRESERVED is re-attached to that
            # same batch rather than creating a second one. This matters for a
            # cook batch that straddles today: its cook day is in the past (so
            # it lives in `_PreservedExisting`, still pointing at the original
            # batch) while its leftover days come back in the payload carrying
            # that batch's id as their `cook_key`. Minting a new batch for them
            # split one cook in two — and since the client's cook-batch view
            # calls a batch's EARLIEST day the cook, the first surviving
            # leftover day started rendering as a second cook that nobody was
            # going to do. Measured live 2026-09-03: a Wednesday-cooked Sunday
            # Ragu turned its Thursday leftovers into "Cook · serves 4" as soon
            # as any unrelated meal elsewhere in the week was edited.
            _PreservedBatchById = {
                str(_Batch.id): _Batch for _Batch in _ExistingBatches
                if _Batch.id in _PreservedBatchIds
            }
            _BatchByKey = mint_batches(
                self.repository, meal_plan_id, request.entries, _PreservedBatchById
            )

            # Match-and-update (FU-878). The forward portion used to be deleted
            # and re-inserted, so every entry's id changed on any save. Now a
            # row naming one of this plan's forward entries edits it in place;
            # forward entries no row names are dropped by the reassignment below.
            _PreservedIds = {_Entry.id for _Entry in _PreservedExisting}
            _ForwardById = {
                _Entry.id: _Entry for _Entry in (_Plan.entries or [])
                if _Entry.id not in _PreservedIds
            }
            _ForwardEntries: List[MealPlanEntry] = []
            for _EntryRequest in request.entries:
                _Recipe = _RecipeById[_EntryRequest.recipe_id]
                _Batch = batch_for(_EntryRequest, _BatchByKey)
                _Entry = _ForwardById.pop(_EntryRequest.meal_plan_entry_id, None)
                if _Entry is None:
                    _Entry = new_entry(_EntryRequest, _Recipe, _Batch)
                    self.repository.add(_Entry)
                else:
                    apply_to_entry(_Entry, _EntryRequest, _Recipe, _Batch)
                _ForwardEntries.append(_Entry)
            _Plan.entries = _PreservedExisting + _ForwardEntries

        self.repository.save_changes()
        return UpdateMealPlanResponse()


@MEAL_PLAN_ROUTER.route("<uuid:meal_plan_id>", methods=["PATCH"])
@has_request_body(UpdateMealPlanRequest)
def update_meal_plan(meal_plan_id: UUID):
    _Handler = UpdateMealPlanHandler(SqlAlchemyRepository())
    _Request: UpdateMealPlanRequest = get_request_body()
    _Response = _Handler.handle(_Request, meal_plan_id)

    if _Response.meal_plan_not_found:
        return not_found(MealPlan.__name__, meal_plan_id)

    if _Response.needs_clear_confirmation:
        return bad_request(
            "Refusing to clear every future entry without confirmation. "
            "Resend with `confirm_clear_entries: true` if that's really the intent."
        )

    _Error = meal_plan_write_error_response(_Response, UpdateMealPlanRequest)
    if _Error is not None:
        return _Error

    return no_content()
