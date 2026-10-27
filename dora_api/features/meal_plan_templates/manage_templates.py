"""Meal-plan templates (C-2.F) — CRUD + snapshot-a-week + apply-to-a-week.

Templates are small and share imports, so the endpoints live together.

  GET    /api/meal-plan-templates           — list summaries
  GET    /api/meal-plan-templates/<id>       — detail (entries + recipe names)
  POST   /api/meal-plan-templates            — snapshot a week's plan as a template
  PATCH  /api/meal-plan-templates/<id>       — rename / re-describe
  DELETE /api/meal-plan-templates/<id>
  POST   /api/meal-plans/from-template       — fork a week from a template

Editing or deleting a template never touches plans already forked from it
(Decision 1) — the forked MealPlan keeps `source_template_id` only as provenance.
"""
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.meal_plan import MealPlan
from dora_api.domain.entities.meal_plan_entry import MealPlanEntry
from dora_api.domain.entities.meal_plan_template import (MealPlanTemplate,
                                                         MealPlanTemplateEntry,
                                                         MealPlanTemplateSet,
                                                         MealPlanTemplateSetItem)
from dora_api.domain.entities.recipe import Recipe
from dora_api.features.app_settings.clock import household_today
from dora_api.features.routers import (MEAL_PLAN_ROUTER,
                                       MEAL_PLAN_TEMPLATE_ROUTER)
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  created, no_content,
                                                  not_found, ok)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


# ───── DTOs ──────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class MealPlanTemplateEntryDto:
    recipe_id: UUID
    recipe_name: str
    offset_from_monday: int
    slot: str
    servings: int


@dataclass(frozen=True, slots=True)
class MealPlanTemplateSummaryDto:
    meal_plan_template_id: UUID
    name: str
    description: str | None
    entry_count: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class MealPlanTemplateDetailDto:
    meal_plan_template_id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    entries: List[MealPlanTemplateEntryDto] = field(default_factory=list)


def _entries_for(repository, template_id: UUID) -> List[MealPlanTemplateEntry]:
    rows: List[MealPlanTemplateEntry] = repository.get(MealPlanTemplateEntry).all(
        EntityField(MealPlanTemplateEntry, "template_id").eq(template_id)
    )
    rows.sort(key=lambda e: (e.offset_from_monday, e.slot))
    return rows


# ───── List ────────────────────────────────────────────────────────────────

class GetMealPlanTemplatesHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self) -> List[MealPlanTemplateSummaryDto]:
        templates: List[MealPlanTemplate] = self.repository.get(MealPlanTemplate).all()
        if not templates:
            return []
        counts: dict[UUID, int] = {}
        for entry in self.repository.get(MealPlanTemplateEntry).all():
            counts[entry.template_id] = counts.get(entry.template_id, 0) + 1
        summaries = [
            MealPlanTemplateSummaryDto(
                meal_plan_template_id = t.id,
                name = t.name,
                description = t.description,
                entry_count = counts.get(t.id, 0),
                created_at = t.created_at,
                updated_at = t.updated_at,
            )
            for t in templates
        ]
        summaries.sort(key=lambda s: s.updated_at, reverse=True)
        return summaries


@MEAL_PLAN_TEMPLATE_ROUTER.route("", methods=["GET"])
def get_meal_plan_templates():
    _Result = GetMealPlanTemplatesHandler(SqlAlchemyRepository()).handle()
    return ok(_Result)


# ───── Detail ────────────────────────────────────────────────────────────────

class GetMealPlanTemplateDetailHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, template_id: UUID) -> MealPlanTemplateDetailDto | None:
        template: MealPlanTemplate | None = self.repository.get(MealPlanTemplate).by_id(template_id)
        if template is None:
            return None
        entries = _entries_for(self.repository, template_id)
        recipe_ids = list({e.recipe_id for e in entries})
        recipes: dict[UUID, Recipe] = {}
        if recipe_ids:
            recipes = {
                r.id: r for r in self.repository.get(Recipe).all(
                    EntityField(Recipe, "id").in_(recipe_ids)
                )
            }
        return MealPlanTemplateDetailDto(
            meal_plan_template_id = template.id,
            name = template.name,
            description = template.description,
            created_at = template.created_at,
            updated_at = template.updated_at,
            entries = [
                MealPlanTemplateEntryDto(
                    recipe_id = e.recipe_id,
                    recipe_name = recipes[e.recipe_id].name if e.recipe_id in recipes else "(missing recipe)",
                    offset_from_monday = e.offset_from_monday,
                    slot = e.slot,
                    servings = e.servings,
                )
                for e in entries
            ],
        )


@MEAL_PLAN_TEMPLATE_ROUTER.route("/<uuid:template_id>", methods=["GET"])
def get_meal_plan_template_detail(template_id: UUID):
    _Result = GetMealPlanTemplateDetailHandler(SqlAlchemyRepository()).handle(template_id)
    if _Result is None:
        return not_found("MealPlanTemplate", template_id)
    return ok(_Result)


# ───── Create (snapshot a week's plan) ──────────────────────────────────────

class CreateMealPlanTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    source_meal_plan_id: UUID


@dataclass(slots=True)
class CreateMealPlanTemplateResponse:
    template_id: UUID | None = None
    source_not_found: bool = False
    no_entries: bool = False


class CreateMealPlanTemplateHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: CreateMealPlanTemplateRequest) -> CreateMealPlanTemplateResponse:
        plan: MealPlan | None = (
            self.repository.get(MealPlan)
            .include(MealPlan.Fields.ENTRIES)
            .one(EntityField(MealPlan, "id").eq(request.source_meal_plan_id))
        )
        if plan is None:
            return CreateMealPlanTemplateResponse(source_not_found=True)

        # Position each meal by its day-of-week offset from the plan's Monday;
        # ignore anything outside the 7-day window (shouldn't happen).
        snapshot = [
            (e, (e.scheduled_for - plan.start_date).days)
            for e in (plan.entries or [])
        ]
        snapshot = [(e, off) for (e, off) in snapshot if 0 <= off <= 6]
        if not snapshot:
            return CreateMealPlanTemplateResponse(no_entries=True)

        now = datetime.now(timezone.utc)
        template = MealPlanTemplate(
            name = request.name.strip(),
            description = (request.description or "").strip() or None,
            created_at = now,
            updated_at = now,
        )
        self.repository.add(template)

        for entry, offset in snapshot:
            self.repository.add(MealPlanTemplateEntry(
                template_id = template.id,
                # Read the FK column directly — the `recipe` relationship is
                # noload and only eager-loads on the list (paginate) path.
                recipe_id = entry._recipe_id,
                offset_from_monday = offset,
                slot = entry.slot,
                servings = entry.servings,
            ))
        # FU-512 unit-of-work: one commit at the end. `add()` assigns
        # `template.id` client-side so the child FKs above don't need a
        # flush; a validation error would return before any add.
        self.repository.save_changes()
        return CreateMealPlanTemplateResponse(template_id=template.id)


@MEAL_PLAN_TEMPLATE_ROUTER.route("", methods=["POST"])
@has_request_body(CreateMealPlanTemplateRequest)
def create_meal_plan_template():
    _Request: CreateMealPlanTemplateRequest = get_request_body()
    _Response = CreateMealPlanTemplateHandler(SqlAlchemyRepository()).handle(_Request)
    if _Response.source_not_found:
        return not_found("MealPlan", _Request.source_meal_plan_id)
    if _Response.no_entries:
        return business_rule_violation("That week has no meals to save as a template.")
    _LOGGER.info(f"Created meal-plan template {_Response.template_id} '{_Request.name}'")
    return created(
        _Response.template_id,
        f"{MEAL_PLAN_TEMPLATE_ROUTER.name}.{get_meal_plan_templates.__name__}",
        "meal_plan_template_id",
        body={"meal_plan_template_id": _Response.template_id},
    )


# ───── Update (rename / re-describe) ────────────────────────────────────────

class UpdateMealPlanTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


@dataclass(slots=True)
class UpdateMealPlanTemplateResponse:
    not_found: bool = False


class UpdateMealPlanTemplateHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: UpdateMealPlanTemplateRequest, template_id: UUID) -> UpdateMealPlanTemplateResponse:
        template: MealPlanTemplate | None = self.repository.get(MealPlanTemplate).by_id(template_id)
        if template is None:
            return UpdateMealPlanTemplateResponse(not_found=True)
        _Set = request.model_fields_set
        if "name" in _Set and request.name is not None:
            template.name = request.name.strip()
        if "description" in _Set:
            template.description = (request.description or "").strip() or None
        template.updated_at = datetime.now(timezone.utc)
        self.repository.save_changes()
        return UpdateMealPlanTemplateResponse()


@MEAL_PLAN_TEMPLATE_ROUTER.route("/<uuid:template_id>", methods=["PATCH"])
@has_request_body(UpdateMealPlanTemplateRequest)
def update_meal_plan_template(template_id: UUID):
    _Request: UpdateMealPlanTemplateRequest = get_request_body()
    _Response = UpdateMealPlanTemplateHandler(SqlAlchemyRepository()).handle(_Request, template_id)
    if _Response.not_found:
        return not_found("MealPlanTemplate", template_id)
    return no_content()


# ───── Delete ────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class DeleteMealPlanTemplateResponse:
    not_found: bool = False


class DeleteMealPlanTemplateHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, template_id: UUID) -> DeleteMealPlanTemplateResponse:
        template: MealPlanTemplate | None = self.repository.get(MealPlanTemplate).by_id(template_id)
        if template is None:
            return DeleteMealPlanTemplateResponse(not_found=True)
        # Forked plans keep their (now-dangling) source_template_id — Decision 1,
        # the plan is unaffected by the template going away.
        self.repository.remove(template)
        self.repository.save_changes()
        return DeleteMealPlanTemplateResponse()


@MEAL_PLAN_TEMPLATE_ROUTER.route("/<uuid:template_id>", methods=["DELETE"])
def delete_meal_plan_template(template_id: UUID):
    _Response = DeleteMealPlanTemplateHandler(SqlAlchemyRepository()).handle(template_id)
    if _Response.not_found:
        return not_found("MealPlanTemplate", template_id)
    _LOGGER.info(f"Deleted meal-plan template {template_id}")
    return no_content()


# ───── Clone ────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class CloneMealPlanTemplateResponse:
    template_id: UUID | None = None
    not_found: bool = False


class CloneMealPlanTemplateHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, template_id: UUID) -> CloneMealPlanTemplateResponse:
        source: MealPlanTemplate | None = self.repository.get(MealPlanTemplate).by_id(template_id)
        if source is None:
            return CloneMealPlanTemplateResponse(not_found=True)
        entries = _entries_for(self.repository, template_id)
        now = datetime.now(timezone.utc)
        clone = MealPlanTemplate(
            name = f"{source.name} (copy)",
            description = source.description,
            created_at = now,
            updated_at = now,
        )
        self.repository.add(clone)
        for e in entries:
            self.repository.add(MealPlanTemplateEntry(
                template_id = clone.id,
                recipe_id = e.recipe_id,
                offset_from_monday = e.offset_from_monday,
                slot = e.slot,
                servings = e.servings,
            ))
        # FU-512 unit-of-work: single commit. Empty-entries case still
        # commits (a no-op save on just the template row).
        self.repository.save_changes()
        return CloneMealPlanTemplateResponse(template_id=clone.id)


@MEAL_PLAN_TEMPLATE_ROUTER.route("/<uuid:template_id>/clone", methods=["POST"])
def clone_meal_plan_template(template_id: UUID):
    _Response = CloneMealPlanTemplateHandler(SqlAlchemyRepository()).handle(template_id)
    if _Response.not_found:
        return not_found("MealPlanTemplate", template_id)
    _LOGGER.info(f"Cloned meal-plan template {template_id} -> {_Response.template_id}")
    return created(
        _Response.template_id,
        f"{MEAL_PLAN_TEMPLATE_ROUTER.name}.{get_meal_plan_templates.__name__}",
        "meal_plan_template_id",
        body={"meal_plan_template_id": _Response.template_id},
    )


# ───── Apply (fork weeks from a template / set) ─────────────────────────────

RECURRING_WEEK_CAP = 26


def _fork_template_onto_week(
    repository, template_entries, template_id, monday, today,
    *, set_id=None, rotation_index=None,
):
    """Fork one week from a template's entries onto `monday`. Mutates the
    repository but does NOT save (the caller saves once — important for the
    recurring loop). Skips past-day offsets (Decision 2) + deleted recipes; on
    an existing week, preserves consumed entries and replaces the future
    portion. Returns (meal_plan_id | None, added, skipped_past, replaced)."""
    new_entries: List[MealPlanEntry] = []
    skipped = 0
    for te in template_entries:
        scheduled = monday + timedelta(days=te.offset_from_monday)
        if scheduled < today:
            skipped += 1
            continue
        recipe = repository.get(Recipe).by_id(te.recipe_id)
        if recipe is None:
            continue
        new_entries.append(MealPlanEntry(
            recipe=recipe, scheduled_for=scheduled, servings=te.servings, slot=te.slot,
        ))

    existing: MealPlan | None = (
        repository.get(MealPlan)
        .include(MealPlan.Fields.ENTRIES)
        .one(EntityField(MealPlan, "start_date").eq(monday))
    )
    # No queries past this point until the caller saves: the just-built entries
    # have no meal_plan_id yet, so an autoflush would violate the FK.
    for entry in new_entries:
        repository.add(entry)

    if existing is not None:
        consumed = [e for e in (existing.entries or []) if e.consumed_at is not None]
        replaced = len([e for e in (existing.entries or []) if e.consumed_at is None])
        existing.entries = consumed + new_entries
        existing.source_template_id = template_id
        existing.source_template_set_id = set_id
        existing.rotation_index = rotation_index
        return existing.id, len(new_entries), skipped, replaced

    if not new_entries:
        return None, 0, skipped, 0

    plan = MealPlan(
        name=None, start_date=monday, entries=new_entries,
        source_template_id=template_id, source_template_set_id=set_id,
        rotation_index=rotation_index,
    )
    repository.add(plan)
    return plan.id, len(new_entries), skipped, 0


class ApplyTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_id: UUID
    # The Monday of the target week (the client sends the focused week's Monday).
    monday_of_week: date


@dataclass(slots=True)
class ApplyTemplateResponse:
    meal_plan_id: UUID | None = None
    template_not_found: bool = False
    added_count: int = 0
    skipped_past_count: int = 0
    replaced_count: int = 0


class ApplyTemplateHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: ApplyTemplateRequest) -> ApplyTemplateResponse:
        template: MealPlanTemplate | None = self.repository.get(MealPlanTemplate).by_id(request.template_id)
        if template is None:
            return ApplyTemplateResponse(template_not_found=True)
        today = household_today(self.repository)
        entries = _entries_for(self.repository, request.template_id)
        mpid, added, skipped, replaced = _fork_template_onto_week(
            self.repository, entries, request.template_id, request.monday_of_week, today,
        )
        self.repository.save_changes()
        return ApplyTemplateResponse(
            meal_plan_id=mpid, added_count=added,
            skipped_past_count=skipped, replaced_count=replaced,
        )


@MEAL_PLAN_ROUTER.route("from-template", methods=["POST"])
@has_request_body(ApplyTemplateRequest)
def apply_template():
    _Request: ApplyTemplateRequest = get_request_body()
    _Response = ApplyTemplateHandler(SqlAlchemyRepository()).handle(_Request)
    if _Response.template_not_found:
        return not_found("MealPlanTemplate", _Request.template_id)
    _LOGGER.info(
        f"Applied template {_Request.template_id} -> plan {_Response.meal_plan_id} "
        f"({_Response.added_count} added, {_Response.skipped_past_count} skipped)"
    )
    return ok({
        "meal_plan_id": _Response.meal_plan_id,
        "added_count": _Response.added_count,
        "skipped_past_count": _Response.skipped_past_count,
        "replaced_count": _Response.replaced_count,
    })


# ───── Recurring apply (a template or a rotating set over a date range) ─────

class ApplyRecurringRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_id: UUID | None = None
    template_set_id: UUID | None = None
    start_monday: date
    end_monday: date


@dataclass(slots=True)
class ApplyRecurringResponse:
    weeks_applied: int = 0
    total_added: int = 0
    total_skipped_past: int = 0
    first_meal_plan_id: UUID | None = None
    not_found_kind: str | None = None
    invalid: str | None = None


class ApplyRecurringHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: ApplyRecurringRequest) -> ApplyRecurringResponse:
        if (request.template_id is None) == (request.template_set_id is None):
            return ApplyRecurringResponse(invalid="Provide exactly one of template_id or template_set_id.")
        if request.end_monday < request.start_monday:
            return ApplyRecurringResponse(invalid="The end week must be on or after the start week.")

        weeks: List[date] = []
        cursor = request.start_monday
        while cursor <= request.end_monday:
            weeks.append(cursor)
            cursor = cursor + timedelta(days=7)
        if len(weeks) > RECURRING_WEEK_CAP:
            return ApplyRecurringResponse(
                invalid=f"That range is {len(weeks)} weeks; the maximum is {RECURRING_WEEK_CAP}.",
            )

        today = household_today(self.repository)
        plan_ids: List[UUID] = []
        total_added = 0
        total_skipped = 0

        if request.template_id is not None:
            if self.repository.get(MealPlanTemplate).by_id(request.template_id) is None:
                return ApplyRecurringResponse(not_found_kind="MealPlanTemplate")
            entries = _entries_for(self.repository, request.template_id)
            for monday in weeks:
                mpid, added, skipped, _ = _fork_template_onto_week(
                    self.repository, entries, request.template_id, monday, today,
                )
                if mpid is not None:
                    plan_ids.append(mpid)
                total_added += added
                total_skipped += skipped
        else:
            if self.repository.get(MealPlanTemplateSet).by_id(request.template_set_id) is None:
                return ApplyRecurringResponse(not_found_kind="MealPlanTemplateSet")
            items: List[MealPlanTemplateSetItem] = self.repository.get(MealPlanTemplateSetItem).all(
                EntityField(MealPlanTemplateSetItem, "set_id").eq(request.template_set_id)
            )
            items.sort(key=lambda i: i.position)
            if not items:
                return ApplyRecurringResponse(invalid="That template set has no templates yet.")
            entries_cache: dict[UUID, list] = {}
            for week_index, monday in enumerate(weeks):
                position = week_index % len(items)
                template_id = items[position].template_id
                if template_id not in entries_cache:
                    entries_cache[template_id] = _entries_for(self.repository, template_id)
                mpid, added, skipped, _ = _fork_template_onto_week(
                    self.repository, entries_cache[template_id], template_id, monday, today,
                    set_id=request.template_set_id, rotation_index=position,
                )
                if mpid is not None:
                    plan_ids.append(mpid)
                total_added += added
                total_skipped += skipped

        self.repository.save_changes()
        return ApplyRecurringResponse(
            weeks_applied=len(weeks), total_added=total_added,
            total_skipped_past=total_skipped,
            first_meal_plan_id=plan_ids[0] if plan_ids else None,
        )


@MEAL_PLAN_ROUTER.route("from-template/recurring", methods=["POST"])
@has_request_body(ApplyRecurringRequest)
def apply_template_recurring():
    _Request: ApplyRecurringRequest = get_request_body()
    _Response = ApplyRecurringHandler(SqlAlchemyRepository()).handle(_Request)
    if _Response.not_found_kind is not None:
        return not_found(_Response.not_found_kind, _Request.template_set_id or _Request.template_id)
    if _Response.invalid is not None:
        return business_rule_violation(_Response.invalid)
    _LOGGER.info(
        f"Recurring apply over {_Response.weeks_applied} week(s): "
        f"{_Response.total_added} added, {_Response.total_skipped_past} skipped"
    )
    return ok({
        "weeks_applied": _Response.weeks_applied,
        "total_added": _Response.total_added,
        "total_skipped_past": _Response.total_skipped_past,
        "first_meal_plan_id": _Response.first_meal_plan_id,
    })
