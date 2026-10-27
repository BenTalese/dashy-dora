"""Meal-slot CRUD (C-2.A) — the household-wide meal-slot vocabulary for meal
planning. Mirrors manage_cuisines.py.

Endpoints:

  GET    /api/meal-slots          — list all (with usage count), ordered
  POST   /api/meal-slots          — create (case-insensitive dup-check)
  PATCH  /api/meal-slots/reorder  — bulk set sequences
  PATCH  /api/meal-slots/<id>     — rename
  DELETE /api/meal-slots/<id>     — delete (NO cascade: MealPlanEntry.slot /
                                    Recipe.time_of_day keep their label string)
"""
import logging
from dataclasses import dataclass
from typing import List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from dora_api.app import db
from dora_api.domain.entities.meal_plan_entry import MealPlanEntry
from dora_api.domain.entities.meal_slot import MealSlot
from dora_api.features.routers import MEAL_SLOT_ROUTER
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  created, not_found, ok)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MealSlotDto:
    meal_slot_id: UUID
    name: str
    sequence: int
    # Slots are not FKs; count usages by matching the stored label string on
    # both meal-plan entries and recipe `time_of_day` values.
    usage_count: int


# ───── List ──────────────────────────────────────────────────────────────

def _slot_usage_counts() -> dict[str, int]:
    """Label -> uses across meal-plan entries and recipe `time_of_day`.
    R-005 carve-out: grouped counts the generic repository has no port for."""
    entry = db.metadata.tables["MealPlanEntry"]
    recipe = db.metadata.tables["Recipe"]
    counts: dict[str, int] = {}
    for column in (entry.c.slot, recipe.c.time_of_day):
        rows = db.session.execute(
            select(column, func.count()).where(column.is_not(None)).group_by(column)
        ).all()
        for label, n in rows:
            counts[label] = counts.get(label, 0) + int(n)
    return counts


class GetMealSlotsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self) -> List[MealSlotDto]:
        slots: List[MealSlot] = self.repository.get(MealSlot).all()
        counts = _slot_usage_counts()
        out = [
            MealSlotDto(
                meal_slot_id=s.id,
                name=s.name,
                sequence=s.sequence,
                usage_count=counts.get(s.name, 0),
            )
            for s in slots
        ]
        out.sort(key=lambda s: (s.sequence, s.name.lower()))
        return out


@MEAL_SLOT_ROUTER.route("", methods=["GET"])
def get_meal_slots():
    _Result = GetMealSlotsHandler(SqlAlchemyRepository()).handle()
    return ok(_Result)


# ───── Create ────────────────────────────────────────────────────────────

class CreateMealSlotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=50)


@dataclass(slots=True)
class CreateMealSlotResponse:
    meal_slot_id: UUID | None = None
    duplicate: bool = False


class CreateMealSlotHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: CreateMealSlotRequest) -> CreateMealSlotResponse:
        existing = self.repository.get(MealSlot).all()
        normalised = request.name.strip().lower()
        if any(s.name.strip().lower() == normalised for s in existing):
            return CreateMealSlotResponse(duplicate=True)
        next_seq = max((s.sequence for s in existing), default=-1) + 1
        slot = MealSlot(name=request.name.strip(), sequence=next_seq)
        self.repository.add(slot)
        self.repository.save_changes()
        return CreateMealSlotResponse(meal_slot_id=slot.id)


@MEAL_SLOT_ROUTER.route("", methods=["POST"])
@has_request_body(CreateMealSlotRequest)
def create_meal_slot():
    _Request: CreateMealSlotRequest = get_request_body()
    _Response = CreateMealSlotHandler(SqlAlchemyRepository()).handle(_Request)
    if _Response.duplicate:
        return business_rule_violation(f"A meal slot named '{_Request.name}' already exists.")
    _LOGGER.info(f"Created meal slot {_Response.meal_slot_id} '{_Request.name}'")
    return created(
        _Response.meal_slot_id,
        f"{MEAL_SLOT_ROUTER.name}.{get_meal_slots.__name__}",
        "meal_slot_id",
        body={"meal_slot_id": _Response.meal_slot_id},
    )


# ───── Reorder ───────────────────────────────────────────────────────────
# Registered before the `/<meal_slot_id>` rename route so the literal
# `/reorder` path wins over the UUID converter.

class ReorderMealSlotItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meal_slot_id: UUID
    sequence: int = Field(ge=0)


class ReorderMealSlotsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slots: List[ReorderMealSlotItem] = Field(default_factory=list)


@dataclass(slots=True)
class ReorderMealSlotsResponse:
    unknown_ids: tuple[UUID, ...] = ()


class ReorderMealSlotsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: ReorderMealSlotsRequest) -> ReorderMealSlotsResponse:
        by_id = {s.id: s for s in self.repository.get(MealSlot).all()}
        unknown = [item.meal_slot_id for item in request.slots if item.meal_slot_id not in by_id]
        if unknown:
            return ReorderMealSlotsResponse(unknown_ids=tuple(unknown))
        for item in request.slots:
            by_id[item.meal_slot_id].sequence = item.sequence
        self.repository.save_changes()
        return ReorderMealSlotsResponse()


@MEAL_SLOT_ROUTER.route("/reorder", methods=["PATCH"])
@has_request_body(ReorderMealSlotsRequest)
def reorder_meal_slots():
    _Request: ReorderMealSlotsRequest = get_request_body()
    _Response = ReorderMealSlotsHandler(SqlAlchemyRepository()).handle(_Request)
    if _Response.unknown_ids:
        return business_rule_violation(f"Unknown meal slot IDs: {_Response.unknown_ids}")
    _LOGGER.info(f"Reordered {len(_Request.slots)} meal slot(s)")
    return ok({})


# ───── Rename ────────────────────────────────────────────────────────────

class UpdateMealSlotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=50)


@dataclass(slots=True)
class UpdateMealSlotResponse:
    not_found: bool = False
    duplicate: bool = False


class UpdateMealSlotHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: UpdateMealSlotRequest, meal_slot_id: UUID) -> UpdateMealSlotResponse:
        slot: MealSlot | None = self.repository.get(MealSlot).by_id(meal_slot_id)
        if slot is None:
            return UpdateMealSlotResponse(not_found=True)
        target = request.name.strip()
        normalised = target.lower()
        for s in self.repository.get(MealSlot).all():
            if s.id != meal_slot_id and s.name.strip().lower() == normalised:
                return UpdateMealSlotResponse(duplicate=True)
        slot.name = target
        self.repository.save_changes()
        return UpdateMealSlotResponse()


@MEAL_SLOT_ROUTER.route("/<uuid:meal_slot_id>", methods=["PATCH"])
@has_request_body(UpdateMealSlotRequest)
def update_meal_slot(meal_slot_id: UUID):
    _Request: UpdateMealSlotRequest = get_request_body()
    _Response = UpdateMealSlotHandler(SqlAlchemyRepository()).handle(_Request, meal_slot_id)
    if _Response.not_found:
        return not_found("MealSlot", meal_slot_id)
    if _Response.duplicate:
        return business_rule_violation(f"A meal slot named '{_Request.name}' already exists.")
    return ok({"meal_slot_id": meal_slot_id})


# ───── Delete ────────────────────────────────────────────────────────────

@dataclass(slots=True)
class DeleteMealSlotResponse:
    not_found: bool = False
    entries_affected: int = 0


class DeleteMealSlotHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, meal_slot_id: UUID) -> DeleteMealSlotResponse:
        slot: MealSlot | None = self.repository.get(MealSlot).by_id(meal_slot_id)
        if slot is None:
            return DeleteMealSlotResponse(not_found=True)
        # No FK: deleting the vocab row does NOT cascade or null anything.
        # Existing entries keep their label string (they become off-vocab).
        # Pre-count by label match for the UI delete warning.
        affected = self.repository.get(MealPlanEntry).count(
            EntityField(MealPlanEntry, MealPlanEntry.Fields.SLOT).eq(slot.name)
        )
        self.repository.remove(slot)
        self.repository.save_changes()
        return DeleteMealSlotResponse(entries_affected=affected)


@MEAL_SLOT_ROUTER.route("/<uuid:meal_slot_id>", methods=["DELETE"])
def delete_meal_slot(meal_slot_id: UUID):
    _Response = DeleteMealSlotHandler(SqlAlchemyRepository()).handle(meal_slot_id)
    if _Response.not_found:
        return not_found("MealSlot", meal_slot_id)
    _LOGGER.info(f"Deleted meal slot {meal_slot_id}; {_Response.entries_affected} entry(ies) keep the label")
    return ok({"entries_affected": _Response.entries_affected})
