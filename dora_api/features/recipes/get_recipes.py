import dataclasses
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List
from uuid import UUID

from flask import request

from dora_api.domain.entities.app_setting import (
    NUTRITION_MODE_COMPLEX,
    RATING_SCHEME_HEALTH_STAR,
    RATING_SCHEME_NONE,
    RATING_SCHEME_NUTRI_SCORE,
)
from dora_api.domain.entities.dietary_tag import DietaryTag
from dora_api.domain.entities.recipe import Recipe
from dora_api.domain.entities.recipe_ingredient import RecipeIngredient
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.recipe_tags import RECIPE_TAG_DISCLAIMER
from dora_api.domain.recipe_cookability import (cookability_state,
                                                 missing_count_for,
                                                 missing_stock_item_names_for,
                                                 unlinked_count_for)
from dora_api.domain.stock_status import (is_low_stock, is_missing)
from dora_api.features.app_settings.access import (get_or_create_app_setting,
                                                  money_features_enabled)
from dora_api.features.app_settings.clock import household_today
from dora_api.features.meal_plans.commitment_access import (committed_servings_by_recipe,
                                                           plan_counts_by_recipe)
from dora_api.features.nutrition.recipe_rollup import (
    IngredientInput, RecipeNutritionInput, effective_kcal_per_serving,
    rollup_recipe_nutrition, rollup_recipes_nutrition,
)
from dora_api.features.nutrition.sources import nutrition_mode
from dora_api.features.recipes.image_flags import recipe_ids_with_image
from dora_api.features.recipes.recipe_cost import (estimate_cost_for_ingredients,
                                                   estimate_costs_for)
from dora_api.features.recipes.recipe_tag_access import (
    find_recipe_ids_with_all_tags, find_recipe_ids_with_any_tags,
    get_tag_ids_for_recipes,
)
from dora_api.features.recipes.recipe_tool_access import (
    find_recipe_ids_with_all_tools, find_recipe_ids_with_any_tools,
    get_tool_ids_for_recipes,
)
from dora_api.features.recipes.recipe_step_access import (
    get_steps_for_recipe, has_structured_steps_for_recipes,
)
from dora_api.features.recipes.recipe_step_image_access import (
    get_step_image_metadata_for_recipe,
    get_step_image_bytes,
)
from dora_api.features.recipes.recipe_section_access import (
    get_section_count_for_recipes, get_sections_for_recipe,
)
from dora_api.features.stock_items._level_access import resolve_levels_by_item
from dora_api.features.stock_items.inference_overlay import (
    SURFACE_RECIPES, IngredientRow, recipe_hint, resolve_divergence,
)
from dora_api.features.routers import RECIPE_ROUTER
from dora_api.infrastructure.api_response import bad_request, not_found, ok, paginated
from dora_api.infrastructure.query_options import (InvalidQueryParameter,
                                                   parse_query_options)
from dora_api.persistence.field import EntityField
from dora_api.persistence.page import Page
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.data_url import data_url_response
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


# How far ahead the cookbook counts an ingredient as "at risk". Owns the
# number for both the "Uses expiring ingredients" filter and the per-
# ingredient `is_expiring` flag below, so a recipe the filter matched can
# never open with nothing marked (the mismatch the owner hit 2026-08-17).
#
# Deliberately NOT the rescue feed's admin-set `expiring_soon_window_days`: that's
# a one-glance "rescue this now" signal, this is "plan around it this
# fortnight". Two horizons, two jobs — but each has exactly one home.
EXPIRING_HORIZON_DAYS = 14


@dataclass(frozen=True, slots=True)
class RecipeIngredientDto:
    recipe_ingredient_id: UUID
    # IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 — nullable so unlinked
    # (paste-imported, no fuzzy match) rows round-trip. The SPA renders
    # unlinked rows with an "Unlinked · Link" pill. When null,
    # ``stock_item_name``, ``stock_level_id``, ``stock_location_id``,
    # ``stock_location_name`` are all null; ``raw_text`` carries the
    # ingredient label; ``is_missing`` / ``is_low_stock`` are False (we
    # can't say what's missing about an ingredient we haven't linked).
    stock_item_id: UUID | None
    stock_item_name: str | None
    stock_level_id: UUID | None
    # Direct location only — the frontend resolves the full breadcrumb via
    # the cached locations tree so recipe queries stay cheap.
    stock_location_id: UUID | None
    stock_location_name: str | None
    quantity: float | None
    unit: str | None
    notes: str | None
    # Server-derived stock status for this ingredient (§3.1 contract), so the
    # client never matches a stock-level name to decide cookability.
    is_missing: bool
    is_low_stock: bool
    # nullable section grouping. NULL = implicit "main"
    # group; the client uses this to bucket ingredients under the named
    # section headers from `RecipeDto.sections`.
    section_id: UUID | None
    # Cookbook revision §1.9 — optional ingredients. The recipe-level
    # `cookable` rollup and `missing_stock_item_names` both ignore
    # optional rows; they're surfaced here only so the edit dialog,
    # picker modal, and cook-mode UI can render them differently.
    is_optional: bool = False
    # IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 — the ingredient text as
    # pasted / imported. Persists even when linked; the SPA prefers it
    # for the label when non-empty ("1 pound ground turkey" is more
    # informative than "ground turkey").
    raw_text: str | None = None
    # The linked stock item's expiry, echoed so the UI can say *when*
    # without a second fetch. Null when unlinked or no expiry is set.
    expiry_date: str | None = None
    # Server-derived, same shape and same reason as `is_missing` above: the
    # client must not decide "is this at risk?" for itself, because the
    # cookbook's horizon (`EXPIRING_HORIZON_DAYS`) is a domain constant while
    # the client's expiry *display* band is a different, shorter number.
    # Stamped by `_hydrate_expiring_ingredients` — needs today plus the shared
    # at-risk query, neither of which `from_entity` has.
    is_expiring: bool = False
    # Already past its date. `is_expiring` is true for these too (the at-risk
    # set includes expired items); this only splits amber "use it soon" from
    # red "it's gone off", so the client does no date arithmetic of its own.
    is_expired: bool = False
    # Which one of the stock item the recipe means (`ingredient_choice`).
    # `label` is the name the recipe shows for it (null: the stock item's
    # name); the picks are ids only, carried onto a shopping line.
    label: str | None = None
    preferred_buy_id: UUID | None = None
    selected_product_id: UUID | None = None

    @classmethod
    def from_entity(cls, ingredient: RecipeIngredient) -> 'RecipeIngredientDto':
        _Item = ingredient.stock_item
        _Loc = _Item.stock_location if _Item else None
        _Level = _Item.stock_level if _Item else None
        return RecipeIngredientDto(
            recipe_ingredient_id = ingredient.id,
            stock_item_id = _Item.id if _Item else None,
            stock_item_name = _Item.name if _Item else None,
            stock_level_id = _Level.id if _Level else None,
            stock_location_id = _Loc.id if _Loc else None,
            stock_location_name = _Loc.name if _Loc else None,
            quantity = ingredient.quantity,
            unit = ingredient.unit,
            notes = ingredient.notes,
            is_missing = is_missing(_Level) if _Item else False,
            is_low_stock = is_low_stock(_Level) if _Item else False,
            section_id = ingredient.section_id,
            is_optional = ingredient.is_optional,
            raw_text = ingredient.raw_text,
            expiry_date = _Item.expiry_date.isoformat() if _Item and _Item.expiry_date else None,
            label = ingredient.label,
            preferred_buy_id = ingredient.preferred_buy_id,
            selected_product_id = ingredient.selected_product_id,
        )


@dataclass(frozen=True, slots=True)
class RecipeVersionSiblingDto:
    """C-4 Chunk 8 — a light view of a sibling version. The detail endpoint
    embeds an array of these so the UI can render a "Versions" card
    without a second round-trip; the fields are the minimum needed for the
    card row (name + last-made + meals-on-hand).

    Recipe-view feedback 2026-08-24 — `created_at` joined it: the version
    panel prints when each version was made, which is the only fact that
    distinguishes two versions of the same recipe at a glance."""
    recipe_id: UUID
    name: str
    last_made_on: date | None
    available_meals: int
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RecipeStepDto:
    """C-4 Chunk 6 — one structured step or sub-step.

    Flat shape; the frontend reassembles the tree from `parent_step_id`.
    `ingredient_ids` references the recipe's own `RecipeIngredient` rows
    (highlight which row this step uses); `tool_ids` references the Tool
    vocab.
    """
    step_id: UUID
    parent_step_id: UUID | None
    sequence: int
    text: str
    hint: str | None
    ingredient_ids: List[UUID]
    tool_ids: List[UUID]
    # top-level steps may belong to a section; NULL = main.
    # Sub-steps carry the same section_id as their parent for cheap reads.
    section_id: UUID | None = None
    # Owner feedback 2026-09-01 — an explicit timer on this step, in minutes.
    # NULL means none was declared, and cook mode falls back to sniffing the
    # step text (the only option a free-text method ever had).
    timer_minutes: int | None = None


@dataclass(frozen=True, slots=True)
class RecipeSectionDto:
    """C-4 Chunk 10 — a named group within a recipe (DEC-3 option A).

    Sections are optional; a recipe with zero sections renders the same
    as it always did, with all ingredients/steps in the implicit "main"
    group (their `section_id` is NULL).
    """
    section_id: UUID
    sequence: int
    name: str


@dataclass(frozen=True, slots=True)
class RecipeCostLineDto:
    """One ingredient's row in the cost breakdown (feedback 2026-08-19).

    `line_cost` is set exactly when `reason` is null. `reason` is one of
    `recipe_cost.UNPRICED_*` — the client maps it to a phrase; the server
    doesn't ship prose it would then have to keep in sync with the UI.
    """
    name: str
    quantity: float | None
    unit: str | None
    unit_price: float | None
    priced_unit: str | None
    line_cost: float | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class RecipeHealthStarRatingDto:
    """The Health Star Rating for a recipe (owner ask 2026-08-27).

    Present only when the install's `nutrition_rating_scheme` is `health_star`
    **and** it is in complex nutrition mode — a rating is computed from the
    foods the ingredients link to, and simple mode has only a typed kcal.

    Every intermediate the FSANZ method names is carried, not just the star
    count, because the one thing this feature must not be is an unexplained
    number: a cook who disagrees with 2.5 stars should be able to see that it
    was 14 baseline points against 3 fibre and no fvnl. `protein_counted` is
    here for the same reason — the ≥13-baseline gate silently zeroing a
    recipe's protein credit reads as a bug unless the UI can say why.
    """
    stars: float
    score: int
    baseline_points: int
    energy_points: int
    saturated_fat_points: int
    total_sugars_points: int
    sodium_points: int
    v_points: int
    protein_points: int
    fibre_points: int
    protein_counted: bool
    # Percentage of the dish's counted weight that is fruit, vegetable, nut or
    # legume — the input the whole feature turned on (see
    # `features/nutrition/food_categories.py`).
    fvnl_percent: float | None
    # Raw summed ingredient weight, in grams. HSR is scored per 100 g of the
    # food *as consumed*; this is the raw weight, so the rating is an estimate
    # and the client says so. Owner's call 2026-08-27.
    total_grams: float | None


@dataclass(frozen=True, slots=True)
class RecipeNutriScoreDto:
    """The Nutri-Score for a recipe (owner ask 2026-08-27).

    The European sibling of `RecipeHealthStarRatingDto`, present only when the
    install's `nutrition_rating_scheme` is `nutri_score` and it is in complex
    nutrition mode. Never present at the same time as the Health Star Rating —
    the scheme is a single choice.

    Carries every intermediate the published method names, for the same reason
    its HSR twin does: a cook who disagrees with a D should be able to see it
    was 14 negative points against 2 fibre and no fruit. `protein_counted` is
    here because the N ≥ 11 gate silently dropping a recipe's protein credit
    reads as a bug unless the UI can say why.

    Note the shapes deliberately do **not** share a base class. They look
    similar but the components are not the same quantities — HSR's `v_points`
    (max 8, fvnl) and Nutri-Score's `fvl_points` (max 5, no nuts) would be a
    trap to unify, and the point ceilings differ throughout.
    """
    grade: str                  # 'A'..'E'
    score: int
    negative_points: int
    energy_points: int
    saturated_fat_points: int
    total_sugars_points: int
    salt_points: int
    positive_points: int
    protein_points: int
    fibre_points: int
    fvl_points: int
    protein_counted: bool
    # Percentage of the dish's counted weight that is fruit, vegetable or
    # legume. **Not** the HSR fvnl figure — nuts and seeds are excluded from
    # this numerator (see `features/nutrition/food_categories.py`).
    fvl_percent: float | None
    # Raw summed ingredient weight, in grams. The published recipe modality
    # asks for ingredient values *as consumed*, with cooking yield accounted
    # for; this is the raw weight, so the grade is an estimate and the client
    # says so. See `domain/nutri_score.py` and FU-748.
    total_grams: float | None


@dataclass(frozen=True, slots=True)
class RecipeNutritionGapDto:
    """One ingredient the rollup couldn't count, named and reasoned.

    Owner feedback 2026-09-08 — the panel could say "2 stock items not linked
    to a food" but not *which*, so the reader had to go and find them. The id
    travels because it is what the fix is applied to: linking a food is a write
    against that stock item, and the panel can offer the search inline rather
    than sending the cook to the pantry page and back.
    """
    name: str | None
    stock_item_id: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class RecipeNutritionDto:
    """FU-635 chunk 6 — complex-mode nutrition rolled up from the ingredients'
    linked foods. Detail endpoint only, and only while the install is in
    complex mode; `null` otherwise.

    Always carries its coverage (`counted_count` / `total_count` + the
    per-reason `uncounted` map) so the client can't render a partial total as
    a complete one — the owner's call was "partials shown and marked", never
    hidden.
    """
    basis: str                  # 'serving' | 'recipe' (no servings typed in)
    servings: int | None
    kcal: float | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    counted_count: int
    total_count: int
    uncounted: dict
    # FU-637 — whether coverage is high enough to *judge* the recipe on (rank
    # it, or exclude it from a "≤ N kcal" search). Display never gates on this;
    # a thin estimate is still shown, with its coverage. The threshold is a
    # domain constant and stays server-side (R-003).
    is_reliable: bool = False
    # The four nutrients the display panel gained for the Health Star Rating
    # (2026-08-27). Same per-serving basis as the macros above.
    saturated_fat_g: float | None = None
    sugars_g: float | None = None
    fibre_g: float | None = None
    sodium_mg: float | None = None
    # Per nutrient, the fraction (0..1) of the recipe's counted *weight* whose
    # food carried a figure. Mass-weighted, not row-counted, because these feed
    # a per-100g calculation. It exists because the gap is not symmetric: a
    # missing penalty nutrient (sugars is known for only ~77% of USDA SR
    # Legacy) makes a recipe rate *better*, so the panel has to be able to say
    # which figures were thin rather than present the score as complete.
    nutrient_coverage: dict = field(default_factory=dict)
    # At most one of these is ever non-null — the install picks one scheme.
    # They are separate fields rather than one polymorphic `rating` because a
    # client rendering stars and a client rendering an A–E badge need different
    # shapes, and a discriminated union in JSON would just move the branch into
    # the SPA without removing it.
    health_star_rating: 'RecipeHealthStarRatingDto | None' = None
    nutri_score: 'RecipeNutriScoreDto | None' = None
    # The named gaps behind `uncounted`. Detail path only — the cookbook list
    # renders a kcal badge and has no use for a per-ingredient ledger, and
    # shipping one per card would grow the page payload for nothing.
    uncounted_ingredients: list = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RecipeDto:
    recipe_id: UUID
    name: str
    available_meals: int
    unallocated_meals: int
    # Sum of future, un-consumed meal-plan servings for this recipe (the raw
    # commitment — NOT floored, unlike unallocated_meals). Lets the UI show a
    # shortfall (committed > available) in red. Hydrated post-query.
    committed_meals: int
    # "haven't had in a while" (last_made_on NULL or older than the
    # household 21-day window) + how often this recipe appears across meal
    # plans ("frequently planned"). Both hydrated post-query — the server owns
    # the window + the count (R-003); the client just renders the trays.
    not_made_recently: bool
    plan_count: int
    # true iff at least one MealPlanEntry for this recipe is
    # scheduled today or later AND not yet consumed. Server-owned (R-003)
    # so the cookbook's "Planned" / "Not planned" filter doesn't need to
    # walk every meal plan client-side. Hydrated alongside the existing
    # `committed_meals` derivation in `_hydrate_unallocated` (same query
    # — zero extra round-trip).
    is_planned: bool
    # cuisine + category are FK vocabularies. The id drives the
    # edit-form selects + client filters; the name is carried for cheap
    # display (card subtitle, search, export) without a client-side join.
    cuisine_id: UUID | None
    cuisine_name: str | None
    category_id: UUID | None
    category_name: str | None
    cook_time_minutes: int | None
    difficulty: str | None
    instructions: str | None
    is_favourite: bool
    last_made_on: date | None
    prep_time_minutes: int | None
    # Same id-plus-name shape as cuisine/category above, and for the same
    # reason: the cookbook prints the collection on every card's meta line
    # now that the collection *folders* are gone, and resolving the name
    # client-side would mean a join against a separately-fetched collection
    # list on every render (R-003).
    recipe_collection_id: UUID | None
    recipe_collection_name: str | None
    servings: int | None
    # origin URL when the recipe was imported.
    source: str | None
    time_of_day: str | None
    # version sibling group. NULL means singleton. List
    # endpoint sets `version_group_id` (cheap); detail endpoint also
    # populates `version_siblings[]` (the other recipes sharing the id).
    version_group_id: UUID | None
    # simple nutrition (kcal). Stored per-recipe; the
    # client gates the render on the C-cross nutrition opt-in. NULL when
    # the user hasn't typed one.
    kcal: int | None
    # when the recipe was added to this household. Drives the
    # cookbook "Recently added" sort axis. Never null on a row that came
    # through the create handlers (which stamp it) or through the
    # backfill migration f9d3a7c2b5e8.
    created_at: datetime | None
    ingredients: List[RecipeIngredientDto]
    # Server-owned cookability — computed once from the already-loaded
    # ingredient tree (§3.2 state-ownership refactor).
    # IMPL_PLAN_RECIPE_IMPORTER §Chunk 4: ``cookable`` is now tri-state
    # (bool | None). ``None`` fires when any required ingredient is
    # unlinked; the SPA renders the badge dimmed with a "link
    # ingredients to check" tooltip. ``missing_count`` and
    # ``missing_stock_item_names`` count only LINKED-missing rows, so
    # they can safely be zero / empty on a None-cookable recipe.
    missing_count: int
    cookable: bool | None
    # Distinct, alphabetised names of the missing stock items — lets the
    # client render a "Missing: flour, eggs" hint without rejoining the
    # ingredient tree or the stock-level table.
    missing_stock_item_names: List[str]
    # whether the recipe has an image (the bytes are served via
    # GET /recipes/<id>/image, never inlined in list/detail JSON).
    has_image: bool
    # RD-29 — free-text personal notes about the recipe (cook's own
    # commentary). Surfaced in cook mode under the steps; NULL when unset.
    notes: str | None = None
    # when the recipe was last edited. NULL until its first PATCH; the
    # recipe page's version panel prints it beside `created_at`.
    updated_at: datetime | None = None
    # IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 — count of REQUIRED ingredients
    # whose ``stock_item_id`` is null. Drives the recipe-detail
    # "N ingredients need linking" prompt and the shopping-list
    # "add missing" flow's linking-first message.
    unlinked_ingredient_count: int = 0
    # dietary tag + tool ids. Empty list when none. Hydrated by
    # the handler after the base query — mutable so `from_entity` stays
    # agnostic of association loading.
    dietary_tag_ids: List[UUID] = field(default_factory=list)
    tool_ids: List[UUID] = field(default_factory=list)
    # structured steps. The list endpoint sets only
    # `has_structured_steps` (cheap existence check); detail hydrates
    # `steps[]` from the link tables. Empty steps + has_structured_steps
    # false ⇒ recipe is unstructured; cook-mode falls back to splitting
    # `instructions` on newline.
    has_structured_steps: bool = False
    steps: List['RecipeStepDto'] = field(default_factory=list)
    # populated only by `handle_by_id` (detail). List endpoint
    # leaves this empty; the client uses `version_group_id` on the list DTO
    # to know whether siblings exist at all.
    version_siblings: List['RecipeVersionSiblingDto'] = field(default_factory=list)
    # server-derived cost estimate (DEC-5). Populated only
    # on the detail endpoint and only when at least one ingredient has
    # a linked product offer; client gates render on the C-cross money
    # opt-in. NULL when no estimate could be computed (no linked
    # products in the recipe).
    estimated_cost: float | None = None
    # Companion to estimated_cost: count of ingredients we *couldn't*
    # price (no linked product / no current offer). Lets the UI add a
    # "based on N of M ingredients" disclaimer so the estimate is read
    # as an estimate, not a quote.
    estimated_cost_priced_count: int = 0
    estimated_cost_total_count: int = 0
    # Owner 2026-09-05 — the cookbook wanted to see and sort on cost, and the
    # comparable number across a list is per-serving, not per-recipe: a tray
    # bake that costs $18 and feeds eight is cheaper than a $9 dish for two,
    # and a total-cost column would rank them the other way round. Server-owned
    # (R-003) rather than an `estimated_cost / servings` division on the client
    # — the null rules are the interesting part and they belong in one place.
    # NULL when the recipe is unpriced OR has no servings typed in; both mean
    # "we can't put a per-serving figure on this", and the card says so instead
    # of dividing by a guess.
    estimated_cost_per_serving: float | None = None
    # Feedback 2026-08-19 — the per-ingredient working behind the estimate,
    # for the recipe page's expandable cost card. Detail endpoint only; the
    # collapsed card still reads only the three fields above.
    estimated_cost_lines: List['RecipeCostLineDto'] = field(default_factory=list)
    # named sections (DEC-3 option A). The list endpoint
    # populates only `section_count` (cheap), the detail endpoint also
    # hydrates `sections[]`. Empty sections + section_count == 0 ⇒ the
    # recipe is flat; ingredients/steps render under no header.
    section_count: int = 0
    sections: List['RecipeSectionDto'] = field(default_factory=list)
    # C-waste W4 — number of this recipe's ingredients (non-optional) that
    # are currently in stock and either expired or expiring within the
    # filter's horizon. Populated only when the request asked for the
    # filter (`?expiring_within_days=N`); zero otherwise. The cookbook
    # surfaces a "Uses N expiring" badge from this number.
    expiring_ingredient_count: int = 0
    # Soonest expiry date (ISO) among the counted at-risk ingredients, or None.
    # Drives the cookbook's urgency ranking + chip colour so "2 expiring today"
    # outranks "4 expiring next week" (owner feedback 2026-08-18). A date
    # rather than a day count, so the client colours it with the same shared
    # expiry-tone helper every other surface uses instead of a second
    # threshold (R-003).
    expiring_soonest_date: str | None = None
    # PROPOSAL_RECIPE_IMAGE_STEPS — which step payload to render. Server-
    # owned; replaces the implicit "has structured rows?" detection so
    # 'image' is a first-class peer. Default 'freeform' for new recipes.
    steps_mode: str = "freeform"
    # PROPOSAL_RECIPE_IMAGE_STEPS — ordered image metadata for the detail
    # endpoint only. The list endpoint leaves this empty; bytes are never
    # inlined either way (the SPA loads each via the dedicated bytes
    # endpoint at `/recipes/<id>/step-images/<image_id>`).
    step_images: List['RecipeStepImageDto'] = field(default_factory=list)
    # FU-635 — complex-mode nutrition rollup: the full breakdown + coverage,
    # for the recipe detail card. NULL outside complex mode.
    nutrition: 'RecipeNutritionDto | None' = None
    # FU-637 — the *effective* per-serving kcal for the install's current mode
    # (typed number in simple, rollup in complex), so no client re-derives
    # "which field, and may I trust it" (R-003). Distinct from `kcal` above,
    # which is the stored value the editor writes. NULL when there's no figure
    # — including a complex rollup with no servings typed in, where a
    # per-serving number would have to be invented.
    kcal_per_serving: float | None = None
    # Whether `kcal_per_serving` may be used to *judge* the recipe (filter it
    # out of a "≤ N kcal" search, rank it) as opposed to just display it.
    kcal_is_reliable: bool = False
    # FU-653 — the Zero-Input belief's remark about this recipe, or None.
    # 'at_risk' (reads cookable, but Dora believes a required ingredient has
    # run out) | 'maybe_cookable' (reads not-cookable, but she believes every
    # missing ingredient is back). **Purely additive**: `cookable`,
    # `missing_count` and the `?cookable` filter above are untouched by it, by
    # owner directive. Always None when the user hasn't opted the recipes
    # surface in. Hydrated by `_hydrate_inference`, not `from_entity` — it
    # needs the signed-in user plus a bulk belief gather.
    inference_hint: str | None = None
    inference_stock_item_names: List[str] = field(default_factory=list)

    @classmethod
    def from_entity(cls, recipe: Recipe, dietary_tag_ids: list[UUID] | None = None, unallocated_meals: int | None = None) -> 'RecipeDto':
        _Available = recipe.available_meals or 0
        _IngDtos = [RecipeIngredientDto.from_entity(i) for i in (recipe.ingredients or [])]
        # Distinct missing stock items via the shared cookability rule (R-003) —
        # an ingredient listed on multiple rows is still one shopping line.
        _Missing = missing_count_for(recipe.ingredients)
        # Tri-state cookability (Chunk 4): None fires when any required
        # ingredient is unlinked. Rule owned by ``cookability_state``.
        _Cookable = cookability_state(recipe.ingredients)
        _Unlinked = unlinked_count_for(recipe.ingredients)
        return RecipeDto(
            recipe_id = recipe.id,
            name = recipe.name,
            available_meals = _Available,
            unallocated_meals = _Available if unallocated_meals is None else unallocated_meals,
            committed_meals = 0,
            not_made_recently = False,
            plan_count = 0,
            is_planned = False,
            cuisine_id = recipe.cuisine.id if recipe.cuisine else None,
            cuisine_name = recipe.cuisine.name if recipe.cuisine else None,
            category_id = recipe.category.id if recipe.category else None,
            category_name = recipe.category.name if recipe.category else None,
            cook_time_minutes = recipe.cook_time_minutes,
            difficulty = recipe.difficulty,
            instructions = recipe.instructions,
            is_favourite = recipe.is_favourite,
            last_made_on = recipe.last_made_on,
            prep_time_minutes = recipe.prep_time_minutes,
            recipe_collection_id = recipe.recipe_collection.id if recipe.recipe_collection else None,
            recipe_collection_name = recipe.recipe_collection.name if recipe.recipe_collection else None,
            servings = recipe.servings,
            source = recipe.source,
            time_of_day = recipe.time_of_day,
            version_group_id = recipe.version_group_id,
            kcal = recipe.kcal,
            created_at = recipe.created_at,
            updated_at = recipe.updated_at,
            ingredients = _IngDtos,
            missing_count = _Missing,
            cookable = _Cookable,
            missing_stock_item_names = missing_stock_item_names_for(recipe.ingredients),
            unlinked_ingredient_count = _Unlinked,
            # `image` is now a deferred column; accessing
            # `recipe.image` here would trigger N+1 lazy loads on the
            # list path. Default False and let the handler hydrate
            # via a bulk SELECT below.
            has_image = False,
            dietary_tag_ids = dietary_tag_ids or [],
            steps_mode = recipe.steps_mode or "freeform",
            notes = recipe.notes,
        )


@dataclass(frozen=True, slots=True)
class RecipeStepImageDto:
    """PROPOSAL_RECIPE_IMAGE_STEPS — ordered image metadata. The actual
    bytes live behind `GET /recipes/<recipe_id>/step-images/<image_id>`
    (mirrors the dish-image pattern) so DTO payloads stay slim."""
    image_id: UUID
    sequence: int


_FIELD_MAP: dict[str, EntityField] = {
    "recipe_id": EntityField(Recipe, "id"),
    "recipe_collection_id": EntityField(Recipe, "_recipe_collection_id"),
    # exposed so the cookbook can sort/filter by "Recently added"
    # via the standard `sort=created_at:desc` query string if it ever moves
    # off the client-side sort. The client sort uses the DTO field
    # directly; this entry lets API consumers do the same server-side.
    "created_at": EntityField(Recipe, Recipe.Fields.CREATED_AT),
}


def _per_serving(cost: float | None, servings: int | None) -> float | None:
    """Cost per serving, or None when that isn't a number we can stand behind.

    Two ways it isn't: the recipe didn't price at all, or it has no servings
    typed in. The second is the one worth being strict about — a recipe with a
    blank servings field is not a one-serving recipe, and treating it as one
    would put a $14 dinner-for-four at the expensive end of a per-serving sort.
    Better a card that says nothing than a card that says something wrong.
    """
    if cost is None or not servings or servings <= 0:
        return None
    return cost / float(servings)


@dataclass(frozen=True, slots=True)
class RecipeFilters:
    """Independent recipe filters that compose with AND.

    - tags_include : recipe must carry every tag in this list.
    - tags_exclude : recipe must carry none of the tags in this list.
    - ingredient_exclude : recipe must not have an ingredient whose stock
      item name contains any of the substrings (case-insensitive). Lets
      users say "free from egg" without us having to maintain an allergen
      taxonomy.
    - cookable : when True, only recipes with nothing missing (the same
      `missing_count == 0` the DTO exposes); when False, only recipes with
      at least one missing ingredient. ``None`` = no constraint.
    - max_missing : recipe must have at most this many missing ingredients.
      (State-ownership §3.3 — lets the overview query "Missing ≤ N" instead of
      fetching every recipe + the whole pantry to filter in the browser.)
    - expiring_within_days : when set, recipe must use at least one
      in-stock ingredient whose expiry is within the window. The
      cookbook "Uses expiring ingredients" filter (C-waste W4) sets this
      to 14; the predicate is pushed to the server so no cross-entity
      computation lives on the client (R-003).
    """
    tags_include: tuple[str, ...] = ()
    tags_exclude: tuple[str, ...] = ()
    tools_include: tuple[str, ...] = ()
    tools_exclude: tuple[str, ...] = ()
    ingredient_exclude: tuple[str, ...] = ()
    cookable: bool | None = None
    max_missing: int | None = None
    expiring_within_days: int | None = None

    @property
    def is_empty(self) -> bool:
        return not (
            self.tags_include
            or self.tags_exclude
            or self.tools_include
            or self.tools_exclude
            or self.ingredient_exclude
            or self.cookable is not None
            or self.max_missing is not None
            or self.expiring_within_days is not None
        )

    @property
    def needs_cookability(self) -> bool:
        """True when a filter axis requires per-recipe missing counts."""
        return self.cookable is not None or self.max_missing is not None

    def matches_cookability(self, missing: int, unlinked: int) -> bool:
        """Whether a recipe with ``missing`` linked-missing ingredients and
        ``unlinked`` unlinked-required ingredients passes the cookability
        axes.

        IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 tri-state semantics: a recipe
        with any unlinked required ingredient reads as cookability
        ``None`` (unknown). ``?cookable=true`` and ``?cookable=false``
        both exclude None recipes — the filter answers "definitely yes"
        or "definitely no", not "I don't know". ``?max_missing=N``
        similarly excludes unknown recipes because the count is
        meaningless when some required ingredients aren't linked.
        """
        if unlinked > 0:
            # Tri-state None — excluded from every cookability axis.
            if self.cookable is not None or self.max_missing is not None:
                return False
            return True
        if self.cookable is True and missing != 0:
            return False
        if self.cookable is False and missing == 0:
            return False
        if self.max_missing is not None and missing > self.max_missing:
            return False
        return True


def load_expiring_stock_item_ids(
    repository, horizon_days: int,
) -> set[UUID]:
    """Stock items whose expiry is within the horizon (expired included).

    Reused by the cookbook "Uses expiring ingredients" filter and its
    DTO hydration. Mirrors the predicate in
    `GetWasteRescueHandler.handle()` — same definition of "at risk"
    across the rescue feed and the cookbook surface (R-003).
    """
    if horizon_days < 0:
        return set()
    # R-021 — at-risk horizon uses household-tz today.
    cutoff = household_today(repository) + timedelta(days=horizon_days)
    items = repository.get(StockItem).all(
        EntityField(StockItem, StockItem.Fields.EXPIRY_DATE).is_not_null()
        & EntityField(StockItem, StockItem.Fields.EXPIRY_DATE).lte(cutoff)
    )
    return {i.id for i in items}


def count_expiring_ingredients_per_recipe(
    repository, horizon_days: int,
) -> tuple[set[UUID], dict[UUID, int], dict[UUID, str]]:
    """`(at_risk_item_ids, count_by_recipe_id, soonest_date_by_recipe_id)`.

    The count ignores optional ingredients so the result matches the
    rescue feed's recipe ranking (cookbook revision §1.9 / R-003).
    Recipes whose count is zero are omitted from the dicts, so callers
    can `.get(rid, 0)` for hydration and `set(d.keys())` for the
    restriction filter.

    The third map is the **soonest** at-risk expiry date (ISO) among a
    recipe's counted ingredients. Owner feedback 2026-08-18: ranking on the
    raw count alone put "4 ingredients expiring next week" above "2 expiring
    today", which is backwards — the point of the filter is to cook the thing
    that's about to be thrown away. The date (not a day count) is what
    crosses the wire so the client can reuse its existing shared expiry-tone
    helper instead of re-deriving a second day-threshold (R-003).
    """
    at_risk_ids = load_expiring_stock_item_ids(repository, horizon_days)
    if not at_risk_ids:
        return at_risk_ids, {}, {}
    recipes = (
        repository
        .get(Recipe)
        .include(Recipe.Fields.INGREDIENTS)
            .then_include(RecipeIngredient.Fields.STOCK_ITEM)
        .all()
    )
    counts: dict[UUID, int] = {}
    soonest: dict[UUID, str] = {}
    for recipe in recipes:
        n = 0
        earliest: date | None = None
        for ing in (recipe.ingredients or []):
            item = ing.stock_item
            if item is None:
                continue
            if ing.is_optional:
                continue
            if item.id in at_risk_ids:
                n += 1
                # An at-risk item can still have no date (the predicate also
                # catches items flagged at-risk by other means), so guard.
                item_expiry = item.expiry_date
                if item_expiry is not None:
                    as_date = (
                        item_expiry if isinstance(item_expiry, date)
                        else date.fromisoformat(str(item_expiry))
                    )
                    if earliest is None or as_date < earliest:
                        earliest = as_date
        if n > 0:
            counts[recipe.id] = n
            if earliest is not None:
                soonest[recipe.id] = earliest.isoformat()
    return at_risk_ids, counts, soonest


def load_recipe_cookability(
    repository, recipe_ids=None,
) -> dict[UUID, tuple[int, int, int]]:
    """Map every recipe id (or just ``recipe_ids``) ->
    ``(missing_count, ingredient_count, unlinked_count)``.

    One eager-loaded query, shared by the ``?cookable`` / ``?max_missing`` recipe
    filter and the dashboard's ``cookable_count`` so the cookability rule lives in
    one place (R-003, via :func:`missing_count_for`).

    * ``missing_count`` — distinct linked stock items missing (§3.2).
    * ``ingredient_count`` — total ingredient rows on the recipe.
    * ``unlinked_count`` — required ingredients with no ``stock_item_id``
      (Chunk 4). Callers gate the cookable-now count on this being zero:
      a recipe with any unlinked required ingredient is tri-state None,
      not True, and is excluded from the dashboard tally.

    Levels are resolved by id rather than through an eager include: if the
    request already loaded these StockItems, the identity map returns them
    with ``stock_level`` unset and every ingredient would read as missing
    (FU-872, R-032). Safe to call at any point in a request.
    """
    query = (
        repository
        .get(Recipe)
        .include(Recipe.Fields.INGREDIENTS)
            .then_include(RecipeIngredient.Fields.STOCK_ITEM)
    )
    if recipe_ids is None:
        recipes = query.all()
    elif not recipe_ids:
        return {}
    else:
        recipes = query.all(EntityField(Recipe, "id").in_(list(recipe_ids)))
    items = {
        ing.stock_item.id: ing.stock_item
        for r in recipes
        for ing in (r.ingredients or [])
        if ing.stock_item is not None
    }
    levels_by_item = resolve_levels_by_item(repository, list(items.values()))
    return {
        r.id: (
            missing_count_for(r.ingredients, levels_by_item),
            len(r.ingredients or []),
            unlinked_count_for(r.ingredients),
        )
        for r in recipes
    }


class GetRecipesHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository
        # Populated by `_restrict_query` when the C-waste cookbook filter
        # is active; consumed by `_hydrate_expiring_count` so the count
        # query runs once per request.
        self._expiring_counts: dict[UUID, int] = {}
        # Soonest at-risk expiry date per recipe (ISO), same lifecycle as the
        # counts above — populated only when the expiring filter is active.
        self._expiring_soonest: dict[UUID, str] = {}

    def _base_query(self):
        return (
            self.repository
            .get(Recipe)
            .include(Recipe.Fields.INGREDIENTS)
                .then_include(RecipeIngredient.Fields.STOCK_ITEM)
                .then_include(StockItem.Fields.STOCK_LEVEL)
            .include(Recipe.Fields.INGREDIENTS)
                .then_include(RecipeIngredient.Fields.STOCK_ITEM)
                .then_include(StockItem.Fields.STOCK_LOCATION)
            .include(Recipe.Fields.RECIPE_COLLECTION)
            # cuisine + category flipped to noload; RecipeDto reads
            # both, so every list/detail hit must eager-load them here.
            .include(Recipe.Fields.CUISINE)
            .include(Recipe.Fields.CATEGORY)
        )

    def _ingredient_excluded_recipe_ids(self, terms: tuple[str, ...]) -> set[UUID]:
        """Recipe ids that have at least one ingredient whose stock item
        name contains any of the (case-insensitive) substrings. Returns
        an empty set for empty input — caller checks before subtracting.
        """
        if not terms:
            return set()
        normalised = [t.strip().lower() for t in terms if t.strip()]
        if not normalised:
            return set()
        # Walk ingredients with stock-item names loaded — a single query
        # via the eager include. We trade a full scan of the recipe-
        # ingredient join for simplicity; the personal-use scale doesn't
        # justify a denormalised search column yet.
        ingredients: list[RecipeIngredient] = (
            self.repository.get(RecipeIngredient)
            .include(RecipeIngredient.Fields.STOCK_ITEM)
            .all()
        )
        denied: set[UUID] = set()
        for ing in ingredients:
            item = ing.stock_item
            if item is None or not item.name:
                continue
            name_lower = item.name.lower()
            if any(term in name_lower for term in normalised):
                # `_recipe_id` is the FK column on the mapping; the
                # entity itself doesn't carry a `recipe_id` attribute.
                fk = ing._recipe_id  # noqa: SLF001
                if fk is not None:
                    denied.add(fk)
        return denied

    def _restrict_query(self, query, filters: RecipeFilters):
        """Resolve the filter axes into a single `id IN (...)` constraint
        applied to the page query. Returns the (possibly unchanged) query
        plus a boolean that's True when the filter set guarantees an empty
        result (e.g. `tags_include` matched zero recipes), so the caller can
        short-circuit the paginate."""
        if filters.is_empty:
            return query, False

        # Relationship-dependent maps are built FIRST. SQLAlchemy's
        # identity map hands already-loaded instances back to later
        # queries in the same session, so if the plain id-universe load
        # below ran first, its noload-empty `ingredients` collections
        # would poison these eager loads: every recipe would count
        # (0, 0, 0), silently turning `?cookable=true` into "keep all",
        # `?cookable=false` into "keep none", and the expiring filter
        # into an empty page (bug found by test_recipe_router.py,
        # 2026-07-10).
        cookability: dict[UUID, tuple[int, int, int]] | None = None
        if filters.needs_cookability:
            # `?cookable` matches the DTO `cookable` field exactly (missing == 0
            # AND every required ingredient linked, so an empty recipe is
            # cookable); `?max_missing=N` keeps recipes with at most N missing
            # ingredients; both exclude tri-state None (unlinked) per
            # ``matches_cookability``. One shared query (R-003).
            cookability = load_recipe_cookability(self.repository)
        expiring_counts: dict[UUID, int] | None = None
        if filters.expiring_within_days is not None:
            # C-waste W4 — narrow to recipes that use ≥1 in-stock ingredient
            # expiring within the horizon. Same predicate the rescue feed
            # uses (R-003); count cached on the handler so the hydration
            # step below doesn't recompute it.
            # R-003 carve-out: the horizon arrives as a request param, and the
            # cookbook client passes its own copy of `EXPIRING_HORIZON_DAYS`
            # rather than being told it — so the constant does currently live
            # in two languages. The per-ingredient chips read the server
            # constant, so the two agree today; making that structural needs
            # an explicit param change and is tracked as FU-669.
            _, expiring_counts, expiring_soonest = count_expiring_ingredients_per_recipe(
                self.repository, filters.expiring_within_days,
            )
            self._expiring_counts = expiring_counts
            self._expiring_soonest = expiring_soonest

        # Start with "every recipe id" as the candidate set, then narrow.
        # Loading every id is cheap enough to be honest at our scale.
        all_recipes = self.repository.get(Recipe).all()
        allowed: set[UUID] = {r.id for r in all_recipes}

        if filters.tags_include:
            allowed &= find_recipe_ids_with_all_tags(filters.tags_include)
        if filters.tags_exclude:
            allowed -= find_recipe_ids_with_any_tags(filters.tags_exclude)
        if filters.tools_include:
            allowed &= find_recipe_ids_with_all_tools(filters.tools_include)
        if filters.tools_exclude:
            allowed -= find_recipe_ids_with_any_tools(filters.tools_exclude)
        if filters.ingredient_exclude:
            allowed -= self._ingredient_excluded_recipe_ids(filters.ingredient_exclude)

        if cookability is not None and allowed:
            _kept: set[UUID] = set()
            for rid in allowed:
                missing, _ingr_count, unlinked = cookability.get(rid, (0, 0, 0))
                if filters.matches_cookability(missing, unlinked):
                    _kept.add(rid)
            allowed = _kept

        if expiring_counts is not None and allowed:
            allowed &= set(expiring_counts.keys())

        if not allowed:
            return query, True
        query = query.where(EntityField(Recipe, "id").in_(list(allowed)))
        return query, False

    def _compute_estimated_cost(self, dto: RecipeDto) -> RecipeDto:
        """C-4 Chunk 9 / DEC-5 — server-side cost estimate. For each
        ingredient that has a linked product carrying a current offer,
        sum `quantity * (offer.price_now / product.size_value)` to get
        an estimate. Ingredients without a linked-product offer fall back to
        the stock item's price observations (FU-216 — the everyday substrate);
        those with neither aren't priced. The caller surfaces "based on N of M"
        so the user reads the number as an estimate, not a quote.

        Stays server-side (DEC-5 / R-003 — domain math owned by the
        server, never duplicated on the client). Only the detail path
        triggers this; lists stay cheap.

        FU-463 — built with the ORM `select()` (not raw `text()`) so
        SQLAlchemy adapts UUID bindings to whatever the column type uses
        on each engine. The original raw-SQL version silently never
        matched on SQLite because the string IDs in the IN clause didn't
        compare against the UUIDType column (see
        `project_sqlite_uuid_text_binding` memory + FU-171). Symptom was
        `estimated_cost=None` on every recipe on SQLite deployments,
        regardless of whether the ingredients had priced products.
        """

        if not dto.ingredients:
            return dto

        # R-003 — pricing ladder lives in one place (recipe_cost.py), shared
        # with the FU-451 swap ranker. This method now just adapts the result
        # onto the DTO.
        est = estimate_cost_for_ingredients(self.repository, dto.ingredients)
        return dataclasses.replace(
            dto,
            estimated_cost=est.estimated_cost,
            estimated_cost_per_serving=_per_serving(est.estimated_cost, dto.servings),
            estimated_cost_priced_count=est.priced_count,
            estimated_cost_total_count=est.total_count,
            estimated_cost_lines=[
                RecipeCostLineDto(
                    name=line.name,
                    quantity=line.quantity,
                    unit=line.unit,
                    unit_price=line.unit_price,
                    priced_unit=line.priced_unit,
                    line_cost=line.line_cost,
                    reason=line.reason,
                )
                for line in est.lines
            ],
        )

    def _hydrate_estimated_cost(self, dtos: list[RecipeDto]) -> list[RecipeDto]:
        """Owner 2026-09-05 — cost on the cookbook list, in two queries total.

        `estimated_cost` used to be detail-only, deliberately: the per-recipe
        path is two queries and doing that per card is the N+1 that
        `test_recipes_query_count` exists to catch. `recipe_cost.estimate_costs_for`
        already solves that for the FU-451 swap ranker — one offer lookup and
        one observation lookup for the whole page — so the list can have the
        number at the same cost as the nutrition rollup beside it.

        **Skipped entirely when money is off**, which is the *default* install
        (`money_enabled` server-defaults to False). This is a gate on doing the
        work, not just on rendering it: an install that has opted out of money
        should not pay two joins per cookbook page to compute dollar figures
        nothing will draw. R-058 — a money feature refuses server-side rather
        than shipping numbers the client is expected to hide.

        `estimated_cost_lines` stays detail-only. The breakdown dialog is a
        detail-page surface and the lines are per-ingredient, so putting them
        on a 50-card page would balloon the payload for something nothing on
        the list reads.
        """

        if not dtos or not money_features_enabled(self.repository):
            return dtos

        estimates = estimate_costs_for(self.repository, dtos)

        def _with_cost(dto: RecipeDto) -> RecipeDto:
            est = estimates.get(dto.recipe_id)
            if est is None:
                return dto
            return dataclasses.replace(
                dto,
                estimated_cost=est.estimated_cost,
                estimated_cost_per_serving=_per_serving(est.estimated_cost, dto.servings),
                estimated_cost_priced_count=est.priced_count,
                # NOT `est.total_count`. The batch path's `_cost_one` counts
                # only *linked* ingredients, while the detail path overrides it
                # with `len(ingredients)` to preserve its original contract.
                # Taking the batch number here would make one recipe read
                # "2 of 3" on its card and "2 of 5" on its own page — the same
                # coverage ratio disagreeing with itself one click apart.
                # The detail page's definition wins because it is the one the
                # user reads the explanation against.
                estimated_cost_total_count=len(dto.ingredients),
            )

        return [_with_cost(dto) for dto in dtos]

    def _nutrition_mode(self) -> str:
        """The install's nutrition mode. The rollup runs only in complex (off /
        simple have no linked-food data, so the field stays NULL rather than
        reporting a hollow "0 of 8" — R-029); `kcal_per_serving` is filled in
        simple too, from the typed number.""" 

        return nutrition_mode(get_or_create_app_setting(self.repository))

    def _rating_scheme(self) -> str:
        """Which front-of-pack rating this install shows, if any. `none` by
        default everywhere (see the AppSetting's note)."""

        setting = get_or_create_app_setting(self.repository)
        return setting.nutrition_rating_scheme or RATING_SCHEME_NONE

    @staticmethod
    def _rating_dto(rollup) -> 'RecipeHealthStarRatingDto | None':  # noqa: ANN001
        rating = rollup.rating
        if rating is None:
            return None
        return RecipeHealthStarRatingDto(
            stars=rating.stars,
            score=rating.score,
            baseline_points=rating.baseline_points,
            energy_points=rating.energy_points,
            saturated_fat_points=rating.saturated_fat_points,
            total_sugars_points=rating.total_sugars_points,
            sodium_points=rating.sodium_points,
            v_points=rating.v_points,
            protein_points=rating.protein_points,
            fibre_points=rating.fibre_points,
            protein_counted=rating.protein_counted,
            fvnl_percent=rollup.fvnl_percent,
            total_grams=rollup.total_grams,
        )

    @staticmethod
    def _nutri_score_dto(rollup) -> 'RecipeNutriScoreDto | None':  # noqa: ANN001
        score = rollup.nutri_score
        if score is None:
            return None
        return RecipeNutriScoreDto(
            grade=score.grade,
            score=score.score,
            negative_points=score.negative_points,
            energy_points=score.energy_points,
            saturated_fat_points=score.saturated_fat_points,
            total_sugars_points=score.total_sugars_points,
            salt_points=score.salt_points,
            positive_points=score.positive_points,
            protein_points=score.protein_points,
            fibre_points=score.fibre_points,
            fvl_points=score.fvl_points,
            protein_counted=score.protein_counted,
            fvl_percent=rollup.fvl_percent,
            total_grams=rollup.total_grams,
        )

    @classmethod
    def _nutrition_dto(
        cls,
        rollup,  # noqa: ANN001
        scheme: str = RATING_SCHEME_NONE,
        include_gaps: bool = False,
    ) -> 'RecipeNutritionDto':
        return RecipeNutritionDto(
            basis=rollup.basis,
            servings=rollup.servings,
            kcal=rollup.kcal,
            protein_g=rollup.protein_g,
            carbs_g=rollup.carbs_g,
            fat_g=rollup.fat_g,
            counted_count=rollup.counted_count,
            total_count=rollup.total_count,
            uncounted=rollup.uncounted,
            is_reliable=rollup.is_reliable,
            saturated_fat_g=rollup.saturated_fat_g,
            sugars_g=rollup.sugars_g,
            fibre_g=rollup.fibre_g,
            sodium_mg=rollup.sodium_mg,
            nutrient_coverage=rollup.nutrient_coverage,
            # Gated server-side rather than in the client: an install should
            # not be shipped a rating it has decided not to show, nor the
            # scheme it didn't pick, and one gate beats one per surface
            # (R-003). The rollup computes both; exactly one leaves the API.
            health_star_rating=(
                cls._rating_dto(rollup)
                if scheme == RATING_SCHEME_HEALTH_STAR else None
            ),
            nutri_score=(
                cls._nutri_score_dto(rollup)
                if scheme == RATING_SCHEME_NUTRI_SCORE else None
            ),
            uncounted_ingredients=[
                RecipeNutritionGapDto(
                    name=row.name,
                    stock_item_id=str(row.stock_item_id) if row.stock_item_id else None,
                    reason=row.reason,
                )
                for row in (rollup.uncounted_ingredients if include_gaps else [])
            ],
        )

    def _compute_nutrition(self, dto: RecipeDto, entity: Recipe) -> RecipeDto:
        """FU-635 chunk 6 — complex-mode per-serving nutrition (detail path).

        Server-side for the same reason the cost estimate is (R-003): the
        gram-conversion ladder and the coverage rule are domain math, and a
        second copy in the SPA is how the two drift apart.
        """

        mode = self._nutrition_mode()
        rollup = (
            rollup_recipe_nutrition(self.repository, entity)
            if mode == NUTRITION_MODE_COMPLEX else None
        )
        kcal, reliable = effective_kcal_per_serving(mode, dto.kcal, rollup)
        scheme = self._rating_scheme() if rollup is not None else RATING_SCHEME_NONE
        return dataclasses.replace(
            dto,
            nutrition=(
                self._nutrition_dto(rollup, scheme, include_gaps=True)
                if rollup is not None else None
            ),
            kcal_per_serving=kcal,
            kcal_is_reliable=reliable,
        )

    def _hydrate_nutrition(self, dtos: list[RecipeDto]) -> list[RecipeDto]:
        """FU-637 — the same rollup for a whole page, in three queries total.

        Unlike `estimated_cost` (detail-only), nutrition is needed *on the
        list*: the cookbook card shows kcal/serving and the "≤ N kcal" filter
        judges on it, and a per-recipe fetch to render a card badge would be
        the N+1 that `test_recipes_query_count` exists to catch.
        """

        if not dtos:
            return dtos
        mode = self._nutrition_mode()
        if mode != NUTRITION_MODE_COMPLEX:
            # Simple mode still gets an effective figure — the typed number —
            # so the cookbook card and filter read one field in every mode.
            return [
                dataclasses.replace(
                    dto,
                    **dict(zip(
                        ("kcal_per_serving", "kcal_is_reliable"),
                        effective_kcal_per_serving(mode, dto.kcal, None),
                    )),
                )
                for dto in dtos
            ]

        inputs = [
            RecipeNutritionInput(
                recipe_id=dto.recipe_id,
                servings=dto.servings,
                ingredients=[
                    IngredientInput(
                        stock_item_id=ing.stock_item_id,
                        stock_item_name=ing.stock_item_name,
                        quantity=ing.quantity,
                        unit=ing.unit,
                        is_optional=ing.is_optional,
                    )
                    for ing in dto.ingredients
                ],
            )
            for dto in dtos
        ]
        rollups = rollup_recipes_nutrition(self.repository, inputs)
        # Read once for the whole page, not once per recipe — the cookbook
        # renders a rating chip on every row.
        scheme = self._rating_scheme()

        def _with_nutrition(dto: RecipeDto) -> RecipeDto:
            rollup = rollups.get(dto.recipe_id)
            if rollup is None:
                return dto
            kcal, reliable = effective_kcal_per_serving(mode, dto.kcal, rollup)
            return dataclasses.replace(
                dto,
                nutrition=self._nutrition_dto(rollup, scheme),
                kcal_per_serving=kcal,
                kcal_is_reliable=reliable,
            )

        return [_with_nutrition(dto) for dto in dtos]

    def _hydrate_has_image(self, dtos: list[RecipeDto]) -> list[RecipeDto]:
        """FU-090 — bulk-derive `has_image` without loading the image bytes."""
        if not dtos:
            return dtos
        with_image = recipe_ids_with_image(d.recipe_id for d in dtos)
        return [dataclasses.replace(d, has_image=str(d.recipe_id) in with_image) for d in dtos]

    def _hydrate_inference(self, dtos: list[RecipeDto]) -> list[RecipeDto]:
        """FU-653 — stamp the Zero-Input belief remark on each recipe.

        One bulk belief gather for every stock item the page references (not
        the whole pantry, and not one gather per recipe), then a pure decision
        per recipe. Returns the dtos untouched when the user hasn't opted the
        recipes surface in — `resolve_divergence` owns that gate.

        Cookability is *not* recomputed here: the hint reads the DTO's existing
        `missing_count` / `unlinked_ingredient_count`, which came from the
        domain authority. The overlay adds a remark; it never edits a verdict.
        """
        if not dtos:
            return dtos

        item_ids = {
            ingredient.stock_item_id
            for dto in dtos
            for ingredient in dto.ingredients
            if ingredient.stock_item_id is not None
        }
        if not item_ids:
            return dtos
        items = self.repository.get(StockItem).all(
            EntityField(StockItem, "id").in_(list(item_ids))
        )
        divergence = resolve_divergence(self.repository, SURFACE_RECIPES, items)
        if divergence.is_empty:
            return dtos

        out: list[RecipeDto] = []
        for dto in dtos:
            hint = recipe_hint(
                [IngredientRow.from_dto(i) for i in dto.ingredients],
                divergence,
                missing_count=dto.missing_count,
                unlinked_count=dto.unlinked_ingredient_count,
            )
            out.append(dto if hint is None else dataclasses.replace(
                dto,
                inference_hint=hint.kind,
                inference_stock_item_names=hint.stock_item_names,
            ))
        return out

    def _hydrate_section_count(self, dtos: list[RecipeDto]) -> list[RecipeDto]:
        """List endpoint only — one bulk query for the section-count
        badge on each recipe card. Detail endpoint loads the full
        `sections[]` instead."""
        if not dtos:
            return dtos
        counts = get_section_count_for_recipes([d.recipe_id for d in dtos])
        return [
            dataclasses.replace(d, section_count=counts.get(d.recipe_id, 0))
            for d in dtos
        ]

    def _hydrate_structured_steps_flag(self, dtos: list[RecipeDto]) -> list[RecipeDto]:
        """List endpoint only — set `has_structured_steps` via one bulk
        existence query. Detail endpoint (handle_by_id) goes further and
        loads the full `steps[]` list."""
        if not dtos:
            return dtos
        ids = [d.recipe_id for d in dtos]
        with_steps = has_structured_steps_for_recipes(ids)
        return [
            dataclasses.replace(d, has_structured_steps=d.recipe_id in with_steps)
            for d in dtos
        ]

    def _hydrate_expiring_count(self, dtos: list[RecipeDto]) -> list[RecipeDto]:
        """C-waste W4 — fill `expiring_ingredient_count` from the cache
        the filter step populated. Skipped (zeros all the way) when the
        filter wasn't asked for, so the cookbook's default load stays
        unchanged."""
        if not dtos or not self._expiring_counts:
            return dtos
        return [
            dataclasses.replace(
                d,
                expiring_ingredient_count=self._expiring_counts.get(d.recipe_id, 0),
                expiring_soonest_date=self._expiring_soonest.get(d.recipe_id),
            )
            for d in dtos
        ]

    def _hydrate_expiring_ingredients(self, dtos: list[RecipeDto]) -> list[RecipeDto]:
        """Mark which ingredients are the at-risk ones.

        `expiring_ingredient_count` above tells the cookbook card *how many*;
        this tells the recipe page *which*, so filtering to "uses expiring
        ingredients" and opening a result no longer leaves you hunting for the
        one that's about to go off (owner feedback 2026-08-17).

        Deliberately the same `load_expiring_stock_item_ids` predicate and the
        same horizon the filter uses (R-003) — one query for the whole page,
        not one per recipe, and no way for the two answers to disagree.

        Note this marks *optional* ingredients too, while the card's count
        ignores them (it mirrors the rescue feed's ranking). That's intended:
        the count answers "how much waste would cooking this head off?", where
        an optional garnish shouldn't inflate the number; the chip answers
        "which of these is the one?", where an expiring garnish is still worth
        pointing at. So a card badged 2 can open with 3 chips.
        """
        if not dtos:
            return dtos

        at_risk_ids = load_expiring_stock_item_ids(self.repository, EXPIRING_HORIZON_DAYS)
        if not at_risk_ids:
            return dtos
        # R-021 — "expired" is measured against the household's today, not the
        # server's, exactly as the at-risk query above is. Local import to
        # match `load_expiring_stock_item_ids` and the other clock callers in
        # this module.
        today = household_today(self.repository)

        out: list[RecipeDto] = []
        for dto in dtos:
            if not any(i.stock_item_id in at_risk_ids for i in dto.ingredients):
                out.append(dto)
                continue
            out.append(dataclasses.replace(
                dto,
                ingredients=[
                    i if i.stock_item_id not in at_risk_ids else dataclasses.replace(
                        i,
                        is_expiring=True,
                        is_expired=(
                            i.expiry_date is not None
                            and date.fromisoformat(i.expiry_date) < today
                        ),
                    )
                    for i in dto.ingredients
                ],
            ))
        return out

    def _hydrate_tags(self, dtos: list[RecipeDto]) -> list[RecipeDto]:
        """After paginate returns, bulk-load dietary tag + tool ids and rebuild
        the DTOs with them populated. The DTO is frozen, so we replace rather
        than mutate."""
        if not dtos:
            return dtos

        ids = [d.recipe_id for d in dtos]
        tag_map = get_tag_ids_for_recipes(ids)
        tool_map = get_tool_ids_for_recipes(ids)
        return [
            dataclasses.replace(
                d,
                dietary_tag_ids=tag_map.get(d.recipe_id, []),
                tool_ids=tool_map.get(d.recipe_id, []),
            )
            for d in dtos
        ]

    def _hydrate_unallocated(self, dtos: list[RecipeDto]) -> list[RecipeDto]:
        """Subtract the sum of future, un-consumed servings per recipe
        from `available_meals` to derive the unallocated pool. One
        GROUP BY query keeps this O(1) regardless of list size (the
        aggregates live in `meal_plans/commitment_access.py`). Same row set
        also stamps `is_planned` (FU-081 derivation)."""
        if not dtos:
            return dtos

        # "Today" in the household timezone (C-2.K), consistent with the
        # meal-plan rules — not server-local.
        _Today = household_today(self.repository)
        _Ids = [d.recipe_id for d in dtos]
        _Committed = committed_servings_by_recipe(_Ids, _Today)
        # How often each recipe appears across *all* meal plans (the
        # "frequently planned" tray).
        _PlanCount = plan_counts_by_recipe(_Ids)

        # "haven't had in a while": never made, or last made before the
        # household 21-day window. The server owns the threshold (R-003).
        _StaleCutoff = _Today - timedelta(days=21)

        def _stale(d: RecipeDto) -> bool:
            # R-021 — `last_made_on` is a date now; compare directly.
            return d.last_made_on is None or d.last_made_on < _StaleCutoff

        return [
            dataclasses.replace(
                d,
                committed_meals = _Committed.get(str(d.recipe_id), 0),
                unallocated_meals = max(d.available_meals - _Committed.get(str(d.recipe_id), 0), 0),
                plan_count = _PlanCount.get(str(d.recipe_id), 0),
                not_made_recently = _stale(d),
                # same query already filtered to future-unconsumed
                # entries; any presence in _Committed means at least one
                # such row exists.
                is_planned = _Committed.get(str(d.recipe_id), 0) > 0,
            )
            for d in dtos
        ]

    def handle(
        self,
        options,
        filters: RecipeFilters | None = None,
    ) -> Page[RecipeDto]:
        filters = filters or RecipeFilters()
        query = self._base_query()
        query, empty_result = self._restrict_query(query, filters)
        if empty_result:
            return Page(items=[], total=0, page=options.page, limit=options.limit)
        page = query.paginate(
            options, RecipeDto.from_entity, field_map=_FIELD_MAP
        )
        # Each step takes the page's DTOs and returns them with one more field
        # populated; they are independent and run in listed order. This was a
        # ten-deep nest of calls read inside-out — adding cost to it would have
        # made it eleven. A flat list is the same work and says what it does.
        items = page.items
        items = self._hydrate_tags(items)
        items = self._hydrate_expiring_count(items)
        items = self._hydrate_expiring_ingredients(items)
        items = self._hydrate_structured_steps_flag(items)
        items = self._hydrate_section_count(items)
        items = self._hydrate_has_image(items)
        items = self._hydrate_unallocated(items)
        items = self._hydrate_nutrition(items)
        items = self._hydrate_inference(items)
        items = self._hydrate_estimated_cost(items)
        return dataclasses.replace(page, items=items)

    def handle_by_id(self, recipe_id: UUID) -> RecipeDto | None:
        entity = self._base_query().by_id(recipe_id)
        if entity is None:
            return None
        dto = RecipeDto.from_entity(entity)
        # Keyed by the loaded entity's id (a real UUID) so the lookup matches
        # the UUID-keyed dict `get_tag_ids_for_recipes` returns whatever type
        # the caller passed in.
        tag_map = get_tag_ids_for_recipes([entity.id])
        tool_map = get_tool_ids_for_recipes([entity.id])
        step_rows = get_steps_for_recipe(recipe_id)
        step_dtos = [
            RecipeStepDto(
                step_id=row["id"],
                parent_step_id=row["parent_step_id"],
                sequence=row["sequence"],
                text=row["text"],
                hint=row["hint"],
                ingredient_ids=row["ingredient_ids"],
                tool_ids=row["tool_ids"],
                section_id=row.get("section_id"),
                timer_minutes=row.get("timer_minutes"),
            )
            for row in step_rows
        ]
        section_rows = get_sections_for_recipe(recipe_id)
        section_dtos = [
            RecipeSectionDto(
                section_id=row["id"],
                sequence=row["sequence"],
                name=row["name"],
            )
            for row in section_rows
        ]
        # sibling versions for the Versions card. One small
        # query; skipped entirely when the recipe has no group id.
        sibling_dtos: list[RecipeVersionSiblingDto] = []
        if entity.version_group_id is not None:
            siblings = (
                self.repository
                .get(Recipe)
                .all(
                    EntityField(Recipe, Recipe.Fields.VERSION_GROUP_ID).eq(entity.version_group_id),
                )
            )
            sibling_dtos = [
                RecipeVersionSiblingDto(
                    recipe_id=sib.id,
                    name=sib.name,
                    last_made_on=sib.last_made_on,
                    available_meals=sib.available_meals or 0,
                    created_at=sib.created_at,
                )
                for sib in siblings
                if sib.id != recipe_id
            ]
            # Oldest first. The panel reads as a history now that every row
            # carries its created date, and name order said nothing about
            # which version came from which.
            sibling_dtos.sort(key=lambda s: (s.created_at is None, s.created_at, s.name.lower()))
        step_image_rows = get_step_image_metadata_for_recipe(entity.id)
        step_image_dtos = [
            RecipeStepImageDto(
                image_id=row["id"],
                sequence=row["sequence"],
            )
            for row in step_image_rows
        ]
        _WithAssoc = dataclasses.replace(
            dto,
            # keys are UUIDs from the SQL result; use entity.id
            # (a real UUID) instead of the route-string `recipe_id`.
            dietary_tag_ids=tag_map.get(entity.id, []),
            tool_ids=tool_map.get(entity.id, []),
            steps=step_dtos,
            has_structured_steps=bool(step_dtos),
            version_siblings=sibling_dtos,
            sections=section_dtos,
            section_count=len(section_dtos),
            step_images=step_image_dtos,
        )
        _Hydrated = self._hydrate_inference(self._hydrate_expiring_ingredients(
            self._hydrate_unallocated(self._hydrate_has_image([_WithAssoc]))
        ))[0]
        return self._compute_nutrition(self._compute_estimated_cost(_Hydrated), entity)


def _parse_bool(raw: str | None) -> bool | None:
    """Tri-state query-flag parse: 'true'/'1'/'yes' → True, 'false'/'0'/'no' →
    False, missing/blank → None (no constraint)."""
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in ("true", "1", "yes"):
        return True
    if value in ("false", "0", "no"):
        return False
    return None


def _parse_recipe_filters(args) -> RecipeFilters:
    """Read repeated query params (e.g. `?tags_include=vegan&tags_include=gluten-free`)
    plus comma-separated forms (`?tags_include=vegan,gluten-free`). Both
    are honoured because the SPA's `URLSearchParams` setter style and the
    Dora tool's `keywords-style` arg both feel natural.

    Also reads the cookability axes: `?cookable=true|false` and
    `?max_missing=N` (non-negative int; invalid → ignored)."""
    def collect(key: str) -> tuple[str, ...]:
        raw_values = args.getlist(key)
        if not raw_values:
            return ()
        merged: list[str] = []
        for raw in raw_values:
            for part in raw.split(","):
                trimmed = part.strip()
                if trimmed:
                    merged.append(trimmed)
        return tuple(merged)

    max_missing: int | None = None
    raw_max = args.get("max_missing")
    if raw_max is not None and raw_max.strip():
        try:
            parsed = int(raw_max)
            max_missing = parsed if parsed >= 0 else None
        except ValueError:
            max_missing = None

    expiring_within_days: int | None = None
    raw_expiring = args.get("expiring_within_days")
    if raw_expiring is not None and raw_expiring.strip():
        try:
            parsed_e = int(raw_expiring)
            # Cap at 60 days — the same ceiling the rescue feed uses
            # (`_MAX_HORIZON_DAYS` in waste.py). Negative values are
            # treated as "no constraint".
            if 0 <= parsed_e <= 60:
                expiring_within_days = parsed_e
        except ValueError:
            expiring_within_days = None

    return RecipeFilters(
        tags_include=collect("tags_include"),
        tags_exclude=collect("tags_exclude"),
        tools_include=collect("tools_include"),
        tools_exclude=collect("tools_exclude"),
        ingredient_exclude=collect("ingredient_exclude"),
        cookable=_parse_bool(args.get("cookable")),
        max_missing=max_missing,
        expiring_within_days=expiring_within_days,
    )


# ── GET /api/recipes/<id> ───────────────────────────────────────────────
# Detail endpoint — the SPA's `recipeApiService.getAsync`. It returns the
# fully hydrated DTO `handle_by_id` builds (steps, sections, version
# siblings); the list endpoint's filter-by-id form is unused by the SPA.

@RECIPE_ROUTER.route("/<uuid:recipe_id>", methods=["GET"])
def get_recipe(recipe_id: UUID):
    handler = GetRecipesHandler(SqlAlchemyRepository())
    dto = handler.handle_by_id(recipe_id)
    if dto is None:
        return not_found(Recipe.__name__, recipe_id)
    return ok(dto)


@RECIPE_ROUTER.route("")
def get_recipes():
    try:
        _Options = parse_query_options(request.args)
    except InvalidQueryParameter as exc:
        return bad_request(str(exc))
    _Filters = _parse_recipe_filters(request.args)
    try:
        _Page = GetRecipesHandler(SqlAlchemyRepository()).handle(_Options, _Filters)
    except InvalidQueryParameter as exc:
        return bad_request(str(exc))
    _LOGGER.info(
        f"Retrieved {len(_Page.items)} of {_Page.total} recipes "
        f"(tags_include={_Filters.tags_include}, "
        f"tags_exclude={_Filters.tags_exclude}, "
        f"ingredient_exclude={_Filters.ingredient_exclude}, "
        f"cookable={_Filters.cookable}, max_missing={_Filters.max_missing}, "
        f"expiring_within_days={_Filters.expiring_within_days})."
    )
    return paginated(_Page.items, _Page.total, _Page.page, _Page.limit)


# ── GET /api/recipes/tags ───────────────────────────────────────────────
# The SPA pulls the dietary-tag vocabulary at runtime so the picker stays in
# sync with the DB. The disclaimer travels with the list so any client can
# show the "planning aid, not a safety guarantee" framing without hardcoding
# the wording. The dedicated CRUD endpoints (/api/dietary-tags) own editing;
# this read stays here as the recipe-facing catalogue.

# ── GET /api/recipes/<id>/image ─────────────────────────────────────────
# Images are stored as a data-URL string (UTF-8 bytes) on the recipe row and
# served here as raw bytes so the SPA can use a plain <img src> without
# inlining megabytes of base64 into every list/detail JSON payload.

@RECIPE_ROUTER.route("/<uuid:recipe_id>/image", methods=["GET"])
def get_recipe_image(recipe_id):
    recipe = SqlAlchemyRepository().get(Recipe).by_id(recipe_id)
    return data_url_response(
        recipe.image if recipe else None, lambda: not_found(Recipe.__name__, recipe_id),
    )


# ── GET /api/recipes/<id>/step-images/<image_id> ────────────────────────
# PROPOSAL_RECIPE_IMAGE_STEPS — step images are stored as data-URL bytes on
# the RecipeStepImage row and served here as raw bytes, like the recipe image.

@RECIPE_ROUTER.route("/<uuid:recipe_id>/step-images/<uuid:image_id>", methods=["GET"])
def get_recipe_step_image(recipe_id, image_id):
    return data_url_response(
        get_step_image_bytes(recipe_id, image_id),
        lambda: not_found("RecipeStepImage", image_id),
    )


@RECIPE_ROUTER.route("/tags", methods=["GET"])
def get_recipe_tag_catalogue():
    repository = SqlAlchemyRepository()
    tags = sorted(
        repository.get(DietaryTag).all(),
        key=lambda t: (t.sequence, t.name.lower()),
    )
    return ok({
        "tags": [
            {"value": str(t.id), "label": t.name, "category": t.category}
            for t in tags
        ],
        "disclaimer": RECIPE_TAG_DISCLAIMER,
    })
