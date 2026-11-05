from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import List
from uuid import UUID

from dora_api.domain.entities.base_entity import BaseEntity
from dora_api.domain.entities.category import Category
from dora_api.domain.entities.cuisine import Cuisine
from dora_api.domain.entities.recipe_collection import RecipeCollection
from dora_api.domain.entities.recipe_ingredient import RecipeIngredient


# Cookbook card revision §1.7 — closed-set vocabulary, validated at the
# create/update boundaries (R-010). Historic free-text values stay
# readable but new writes must match.
ALLOWED_DIFFICULTY_VALUES = ("Easy", "Medium", "Hard")

# the seeded default meal-slot set. Since C-2.A the household
# `MealSlot` table is the source of truth for the slot vocabulary; new
# `Recipe.time_of_day` / `MealPlanEntry.slot` writes validate against that
# table (see dora_api/features/meal_slots/slot_validation.py). This constant
# is retained only as the canonical seed (mirrored by the seed migration and
# seed.py) and as documentation of the default set.
DEFAULT_MEAL_SLOTS = ("Breakfast", "Lunch", "Dinner", "Snack", "Dessert")


@dataclass
class Recipe(BaseEntity):
    available_meals: int
    # cuisine + category are now FK-backed vocabularies, not
    # free-text. Single-select each (DEC-1). Relationships are selectin-loaded
    # so every recipe read carries them without an explicit include.
    category: Category | None
    cook_time_minutes: int | None
    cuisine: Cuisine | None
    difficulty: str | None
    image: bytes | None
    ingredients: List[RecipeIngredient]
    instructions: str | None
    is_favourite: bool
    last_made_on: date | None
    name: str
    prep_time_minutes: int | None
    recipe_collection: RecipeCollection | None
    servings: int | None
    # origin URL when the recipe was imported. Nullable; the
    # URL importer writes here instead of appending "Source: <url>" to the
    # instructions blob (Chunk 7's clean-up of L295 / L296). Hand-entered
    # recipes leave it None.
    source: str | None
    time_of_day: str | None
    # version siblings via a shared `version_group_id`.
    # Recipes sharing the same id are versions of each other (no current
    # pointer, no snapshot/current distinction per DEC-2 — they're equal
    # peers). NULL means the recipe is a singleton; it'll absorb future
    # versions when the user makes one.
    version_group_id: UUID | None
    # simple nutrition (kcal). Typed by the user when the
    # nutrition opt-in is `simple` (C-cross). NULL means no value set.
    kcal: int | None
    # PROPOSAL_RECIPE_IMAGE_STEPS — explicit declaration of which step
    # payload cook mode and the detail page render. Replaces the implicit
    # "does it have RecipeStep rows?" detection so a third mode (image)
    # can be a first-class peer.
    #   - 'structured' → RecipeStep rows
    #   - 'freeform'   → Recipe.instructions text blob (default for new)
    #   - 'image'      → ordered RecipeStepImage rows
    # Non-destructive switch: all three payloads can coexist; this field
    # only declares which is the active render path.
    steps_mode: str
    # when the recipe row was added to this household. Powers the
    # cookbook "Recently added" sort axis. Stamped by the create handlers
    # at write time.
    created_at: datetime
    # Recipe-view feedback 2026-08-24 — when the recipe was last *edited*.
    # Distinct from `last_made_on` (when it was cooked) and `created_at` (when
    # it was added). NULL on a recipe that has never been edited since it was
    # created; the version-information panel reads it alongside `created_at`.
    # Stamped by `mark_edited()`, which the persistence layer calls on every
    # flush that changes the recipe's content (FU-730,
    # `persistence/recipe_edit_stamp.py`) — not by individual handlers.
    updated_at: datetime | None = None
    # RD-29 — free-text personal notes about the recipe ("I halve the
    # chilli", "kids' favourite"). Distinct from `instructions` (the method):
    # this is the cook's own commentary, surfaced in cook mode under the
    # steps. NULL when unset. Default keeps every existing `Recipe(...)`
    # construction working without passing it.
    notes: str | None = None

    class Fields(BaseEntity.Fields):
        AVAILABLE_MEALS = "available_meals"
        CATEGORY = "category"
        COOK_TIME_MINUTES = "cook_time_minutes"
        CUISINE = "cuisine"
        DIFFICULTY = "difficulty"
        IMAGE = "image"
        INGREDIENTS = "ingredients"
        INSTRUCTIONS = "instructions"
        IS_FAVOURITE = "is_favourite"
        LAST_MADE_ON = "last_made_on"
        NAME = "name"
        PREP_TIME_MINUTES = "prep_time_minutes"
        RECIPE_COLLECTION = "recipe_collection"
        SERVINGS = "servings"
        SOURCE = "source"
        TIME_OF_DAY = "time_of_day"
        VERSION_GROUP_ID = "version_group_id"
        KCAL = "kcal"
        STEPS_MODE = "steps_mode"
        CREATED_AT = "created_at"
        UPDATED_AT = "updated_at"
        NOTES = "notes"

    def mark_edited(self, at: datetime | None = None) -> None:
        """Record that what this recipe *is* changed (FU-730)."""
        self.updated_at = at or datetime.now(UTC)


ALLOWED_STEPS_MODES = ("structured", "freeform", "image")

# Fields whose change records what *happened* to a recipe — cooked, its
# meal pool moved, favourited, grouped with a new version — not what it *is*.
# Changing only these never moves `updated_at`: the version panel would be
# useless if "last updated" moved every time you cooked (FU-730).
NON_EDIT_FIELDS = frozenset({
    Recipe.Fields.AVAILABLE_MEALS,
    Recipe.Fields.IS_FAVOURITE,
    Recipe.Fields.LAST_MADE_ON,
    Recipe.Fields.VERSION_GROUP_ID,
    Recipe.Fields.UPDATED_AT,
})
