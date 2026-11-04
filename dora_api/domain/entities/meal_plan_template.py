"""Meal-plan templates (C-2.F).

A template is a saved *week shape* — meals positioned by day-of-week
(`offset_from_monday` 0..6) + slot — that can be forked onto any week. Editing
or deleting a template never touches plans already forked from it (Decision 1);
the forked `MealPlan` carries `source_template_id` only as provenance.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from uuid import UUID

from dora_api.domain.entities.base_entity import BaseEntity


@dataclass
class MealPlanTemplateEntry(BaseEntity):
    template_id: UUID
    recipe_id: UUID
    offset_from_monday: int
    slot: str
    servings: int = 1
    # FU-939: entries sharing a `cook_key` were one batch cook in the week the
    # template came from; `cook_fresh` marks a meal cooked on the day.
    cook_key: str | None = None
    cook_fresh: bool = False

    class Fields(BaseEntity.Fields):
        TEMPLATE_ID = "template_id"
        RECIPE_ID = "recipe_id"
        OFFSET_FROM_MONDAY = "offset_from_monday"
        SLOT = "slot"
        COOK_KEY = "cook_key"
        COOK_FRESH = "cook_fresh"
        SERVINGS = "servings"


@dataclass
class MealPlanTemplate(BaseEntity):
    name: str
    created_at: datetime
    updated_at: datetime
    description: str | None = None
    entries: List[MealPlanTemplateEntry] = field(default_factory=list)

    class Fields(BaseEntity.Fields):
        NAME = "name"
        CREATED_AT = "created_at"
        UPDATED_AT = "updated_at"
        DESCRIPTION = "description"
        ENTRIES = "entries"


@dataclass
class MealPlanTemplateSetItem(BaseEntity):
    set_id: UUID
    template_id: UUID
    position: int = 0

    class Fields(BaseEntity.Fields):
        SET_ID = "set_id"
        TEMPLATE_ID = "template_id"
        POSITION = "position"


@dataclass
class MealPlanTemplateSet(BaseEntity):
    """An ordered list of templates that rotates by week (C-2.G) — applying a
    set over a date range forks `items[week_index mod len]` onto each week."""
    name: str
    created_at: datetime
    updated_at: datetime
    description: str | None = None
    items: List[MealPlanTemplateSetItem] = field(default_factory=list)

    class Fields(BaseEntity.Fields):
        NAME = "name"
        CREATED_AT = "created_at"
        UPDATED_AT = "updated_at"
        DESCRIPTION = "description"
        ITEMS = "items"
