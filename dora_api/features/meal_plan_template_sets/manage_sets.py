"""Meal-plan template *sets* (C-2.G) — an ordered, rotating list of templates.

  GET    /api/meal-plan-template-sets        — list summaries
  GET    /api/meal-plan-template-sets/<id>    — detail (ordered items + names)
  POST   /api/meal-plan-template-sets         — create (name + ordered template_ids)
  PATCH  /api/meal-plan-template-sets/<id>    — rename / re-describe / reorder
  DELETE /api/meal-plan-template-sets/<id>

Applying a set over a date range (`POST /meal-plans/from-template/recurring`)
rotates `items[week_index mod len]` onto each week — see meal_plan_templates.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.meal_plan_template import (MealPlanTemplate,
                                                         MealPlanTemplateSet,
                                                         MealPlanTemplateSetItem)
from dora_api.features.routers import MEAL_PLAN_TEMPLATE_SET_ROUTER
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  created, no_content,
                                                  not_found, ok)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TemplateSetItemDto:
    template_id: UUID
    template_name: str
    position: int


@dataclass(frozen=True, slots=True)
class TemplateSetSummaryDto:
    meal_plan_template_set_id: UUID
    name: str
    description: str | None
    item_count: int
    template_names: List[str]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TemplateSetDetailDto:
    meal_plan_template_set_id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    items: List[TemplateSetItemDto] = field(default_factory=list)


def _items_for(repository, set_id: UUID) -> List[MealPlanTemplateSetItem]:
    rows: List[MealPlanTemplateSetItem] = repository.get(MealPlanTemplateSetItem).all(
        EntityField(MealPlanTemplateSetItem, "set_id").eq(set_id)
    )
    rows.sort(key=lambda i: i.position)
    return rows


def _template_names(repository, template_ids: List[UUID]) -> dict[UUID, str]:
    if not template_ids:
        return {}
    return {
        t.id: t.name for t in repository.get(MealPlanTemplate).all(
            EntityField(MealPlanTemplate, "id").in_(list(set(template_ids)))
        )
    }


# ───── List ────────────────────────────────────────────────────────────────

class GetSetsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self) -> List[TemplateSetSummaryDto]:
        sets: List[MealPlanTemplateSet] = self.repository.get(MealPlanTemplateSet).all()
        if not sets:
            return []
        all_items: List[MealPlanTemplateSetItem] = self.repository.get(MealPlanTemplateSetItem).all()
        names = _template_names(self.repository, [i.template_id for i in all_items])
        by_set: dict[UUID, List[MealPlanTemplateSetItem]] = {}
        for item in all_items:
            by_set.setdefault(item.set_id, []).append(item)
        out: List[TemplateSetSummaryDto] = []
        for s in sets:
            items = sorted(by_set.get(s.id, []), key=lambda i: i.position)
            out.append(TemplateSetSummaryDto(
                meal_plan_template_set_id = s.id,
                name = s.name,
                description = s.description,
                item_count = len(items),
                template_names = [names.get(i.template_id, "(missing template)") for i in items],
                created_at = s.created_at,
                updated_at = s.updated_at,
            ))
        out.sort(key=lambda s: s.updated_at, reverse=True)
        return out


@MEAL_PLAN_TEMPLATE_SET_ROUTER.route("", methods=["GET"])
def get_template_sets():
    return ok(GetSetsHandler(SqlAlchemyRepository()).handle())


# ───── Detail ────────────────────────────────────────────────────────────────

class GetSetDetailHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, set_id: UUID) -> TemplateSetDetailDto | None:
        s: MealPlanTemplateSet | None = self.repository.get(MealPlanTemplateSet).by_id(set_id)
        if s is None:
            return None
        items = _items_for(self.repository, set_id)
        names = _template_names(self.repository, [i.template_id for i in items])
        return TemplateSetDetailDto(
            meal_plan_template_set_id = s.id,
            name = s.name,
            description = s.description,
            created_at = s.created_at,
            updated_at = s.updated_at,
            items = [
                TemplateSetItemDto(
                    template_id = i.template_id,
                    template_name = names.get(i.template_id, "(missing template)"),
                    position = i.position,
                )
                for i in items
            ],
        )


@MEAL_PLAN_TEMPLATE_SET_ROUTER.route("/<uuid:set_id>", methods=["GET"])
def get_template_set_detail(set_id: UUID):
    _Result = GetSetDetailHandler(SqlAlchemyRepository()).handle(set_id)
    if _Result is None:
        return not_found("MealPlanTemplateSet", set_id)
    return ok(_Result)


# ───── Create ────────────────────────────────────────────────────────────────

class CreateSetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    template_ids: List[UUID] = Field(default_factory=list)


@dataclass(slots=True)
class CreateSetResponse:
    set_id: UUID | None = None
    missing_template_ids: tuple[UUID, ...] = ()


def _missing_templates(repository, template_ids: List[UUID]) -> tuple[UUID, ...]:
    if not template_ids:
        return ()
    known = set(_template_names(repository, template_ids).keys())
    return tuple(t for t in template_ids if t not in known)


class CreateSetHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: CreateSetRequest) -> CreateSetResponse:
        missing = _missing_templates(self.repository, request.template_ids)
        if missing:
            return CreateSetResponse(missing_template_ids=missing)
        now = datetime.now(timezone.utc)
        s = MealPlanTemplateSet(
            name = request.name.strip(),
            description = (request.description or "").strip() or None,
            created_at = now,
            updated_at = now,
        )
        self.repository.add(s)
        for position, template_id in enumerate(request.template_ids):
            self.repository.add(MealPlanTemplateSetItem(
                set_id = s.id, template_id = template_id, position = position,
            ))
        # FU-512 unit-of-work: one commit at the end. `missing_template_ids`
        # returns before any add, so the error path never commits.
        self.repository.save_changes()
        return CreateSetResponse(set_id=s.id)


@MEAL_PLAN_TEMPLATE_SET_ROUTER.route("", methods=["POST"])
@has_request_body(CreateSetRequest)
def create_template_set():
    _Request: CreateSetRequest = get_request_body()
    _Response = CreateSetHandler(SqlAlchemyRepository()).handle(_Request)
    if _Response.missing_template_ids:
        return business_rule_violation(
            f"Unknown template id(s): {', '.join(str(t) for t in _Response.missing_template_ids)}"
        )
    _LOGGER.info(f"Created template set {_Response.set_id} '{_Request.name}'")
    return created(
        _Response.set_id,
        f"{MEAL_PLAN_TEMPLATE_SET_ROUTER.name}.{get_template_sets.__name__}",
        "meal_plan_template_set_id",
        body={"meal_plan_template_set_id": _Response.set_id},
    )


# ───── Update (rename / re-describe / reorder-replace items) ────────────────

class UpdateSetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    # When present, fully replaces the ordered item list.
    template_ids: List[UUID] | None = None


@dataclass(slots=True)
class UpdateSetResponse:
    not_found: bool = False
    missing_template_ids: tuple[UUID, ...] = ()


class UpdateSetHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: UpdateSetRequest, set_id: UUID) -> UpdateSetResponse:
        s: MealPlanTemplateSet | None = self.repository.get(MealPlanTemplateSet).by_id(set_id)
        if s is None:
            return UpdateSetResponse(not_found=True)
        _Set = request.model_fields_set
        if "name" in _Set and request.name is not None:
            s.name = request.name.strip()
        if "description" in _Set:
            s.description = (request.description or "").strip() or None
        if "template_ids" in _Set and request.template_ids is not None:
            missing = _missing_templates(self.repository, request.template_ids)
            if missing:
                return UpdateSetResponse(missing_template_ids=missing)
            # Replace the ordered items: drop the old rows, recreate in order.
            for old in _items_for(self.repository, set_id):
                self.repository.remove(old)
            for position, template_id in enumerate(request.template_ids):
                self.repository.add(MealPlanTemplateSetItem(
                    set_id = set_id, template_id = template_id, position = position,
                ))
        s.updated_at = datetime.now(timezone.utc)
        self.repository.save_changes()
        return UpdateSetResponse()


@MEAL_PLAN_TEMPLATE_SET_ROUTER.route("/<uuid:set_id>", methods=["PATCH"])
@has_request_body(UpdateSetRequest)
def update_template_set(set_id: UUID):
    _Request: UpdateSetRequest = get_request_body()
    _Response = UpdateSetHandler(SqlAlchemyRepository()).handle(_Request, set_id)
    if _Response.not_found:
        return not_found("MealPlanTemplateSet", set_id)
    if _Response.missing_template_ids:
        return business_rule_violation(
            f"Unknown template id(s): {', '.join(str(t) for t in _Response.missing_template_ids)}"
        )
    return no_content()


# ───── Delete ────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class DeleteSetResponse:
    not_found: bool = False


class DeleteSetHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, set_id: UUID) -> DeleteSetResponse:
        s: MealPlanTemplateSet | None = self.repository.get(MealPlanTemplateSet).by_id(set_id)
        if s is None:
            return DeleteSetResponse(not_found=True)
        self.repository.remove(s)
        self.repository.save_changes()
        return DeleteSetResponse()


@MEAL_PLAN_TEMPLATE_SET_ROUTER.route("/<uuid:set_id>", methods=["DELETE"])
def delete_template_set(set_id: UUID):
    _Response = DeleteSetHandler(SqlAlchemyRepository()).handle(set_id)
    if _Response.not_found:
        return not_found("MealPlanTemplateSet", set_id)
    _LOGGER.info(f"Deleted template set {set_id}")
    return no_content()
