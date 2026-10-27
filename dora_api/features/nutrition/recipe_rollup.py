"""Server-owned recipe nutrition rollup (FU-635 chunk 6).

Complex mode's one user-facing number: what a serving of this recipe holds,
summed from the foods its ingredients are linked to. Sibling of
`features/recipes/recipe_cost.py` — same shape (server owns the math, R-003;
the client renders it and never re-derives it), same honesty contract (a
partial total is always shown *with* its coverage, never as a clean figure).

The chain per ingredient is:

    RecipeIngredient.quantity + unit
      → StockItem.nutrition_food_id
        → NutritionFood (nutrients per 100g)
        + NutritionPortion (a household measure → its gram weight)
      → grams → nutrients

Every link can fail, and each failure is *named* rather than swallowed —
`uncounted` carries a count per reason so the UI can say "3 ingredients
aren't linked to a food" instead of an unexplained shortfall (P3 Honest).

**Grams are never guessed.** Mass units convert outright; volumes prefer the
food's own USDA portion row ("1 cup, chopped" → 125 g) and fall back to the
shared density table only when the food has no matching portion; counts
("2 bananas") need a portion row and are reported unconvertible without one.
Nothing here invents a weight (P12 No-invent) — an unconvertible ingredient
lands in the coverage line, where a partial total can't pass for a complete
one.

Optional ingredients sit outside both halves of the coverage ratio, matching
the cookability rule's treatment of them (R-003): they aren't part of the
recipe as written, so they neither add nutrients nor count as a gap.
"""
from dataclasses import dataclass, field
from typing import Iterable, List

from dora_api.domain import health_star_rating as hsr
from dora_api.domain import nutri_score as ns
from dora_api.domain.entities.nutrition_food import NutritionFood
from dora_api.features.nutrition.food_categories import (
    is_fvl_category,
    is_fvnl_category,
)
from dora_api.features.nutrition.household_measures import (
    food_ids_by_stock_item,
    portions_by_food,
    resolve_grams,
)
from dora_api.infrastructure.ports import Repository
from dora_api.persistence.field import EntityField as Field
from dora_api.domain.rating_tables import kcal_to_kj


# Why an ingredient contributed nothing. Closed set (R-010) — the SPA maps
# each to its own copy line, so a new reason can never arrive unlabelled.
REASON_NOT_LINKED = "not_linked"        # no stock item on the ingredient row
REASON_NO_FOOD = "no_food"              # stock item isn't linked to a food
REASON_NO_QUANTITY = "no_quantity"      # "salt to taste" — nothing to weigh
REASON_NO_CONVERSION = "no_conversion"  # quantity known, grams unknowable
REASON_NO_DATA = "no_data"              # food carries no kcal figure
UNCOUNTED_REASONS = (
    REASON_NOT_LINKED,
    REASON_NO_FOOD,
    REASON_NO_QUANTITY,
    REASON_NO_CONVERSION,
    REASON_NO_DATA,
)

# What the figure is per. `servings` is user-typed and often unset; rather
# than divide by a guessed 4 we report the whole-recipe total and say so.
BASIS_SERVING = "serving"
BASIS_RECIPE = "recipe"

# Coverage at or above which the estimate is solid enough to *judge* a recipe
# on — filter it out of a "≤ N kcal" search, or rank it against its peers.
# Displaying a partial figure with its coverage is always fine; excluding a
# recipe from a search on the strength of a 3-of-12 estimate is not, and for
# someone eating to a number that's worse than showing nothing (R-041).
# Threshold lives here alone — the client reads the resulting boolean and never
# re-derives it (R-003).
RELIABLE_COVERAGE_RATIO = 0.8

# Every nutrient the rollup sums, as `(rollup key, NutritionFood attribute)`.
#
# The first four are the display panel's macros and predate the Health Star
# Rating; the last four were added for it (saturated fat, sugars and sodium are
# three of HSR's four baseline nutrients, fibre is a modifying one). They are
# summed the same way, in the same loop, because there is no reason for two
# passes over the same ingredients — and listing them here rather than inline
# means adding a fifth HSR input later is one line, not three (R-002).
_SUMMED_NUTRIENTS = (
    ("kcal", "kcal_per_100g"),
    ("protein_g", "protein_g_per_100g"),
    ("carbs_g", "carbs_g_per_100g"),
    ("fat_g", "fat_g_per_100g"),
    ("saturated_fat_g", "saturated_fat_g_per_100g"),
    ("sugars_g", "sugars_g_per_100g"),
    ("fibre_g", "fibre_g_per_100g"),
    ("sodium_mg", "sodium_mg_per_100g"),
)

# How many decimal places each is rendered to. Sodium and energy are whole
# numbers (nobody reads a fraction of a milligram of salt); the grams matter to
# one place.
_NUTRIENT_DECIMALS = {
    "kcal": 0, "protein_g": 1, "carbs_g": 1, "fat_g": 1,
    "saturated_fat_g": 1, "sugars_g": 1, "fibre_g": 1, "sodium_mg": 0,
}

# The four HSR baseline (penalty) nutrients. Coverage for these is reported
# separately because a *missing* one flatters the recipe: no sugars figure
# means no sugars points, which reads as a better rating rather than an
# unknown one. The modifying nutrients fail safe in the other direction, so
# they need no such warning.
HSR_BASELINE_NUTRIENTS = ("kcal", "saturated_fat_g", "sugars_g", "sodium_mg")


@dataclass(frozen=True, slots=True)
class IngredientInput:
    """The only ingredient facts the rollup needs. Both callers flatten to this
    — the detail path from loaded entities, the list path from its DTOs — so
    there is one arithmetic path rather than two that drift."""
    stock_item_id: object | None
    stock_item_name: str | None
    quantity: float | None
    unit: str | None
    is_optional: bool = False
    # What to call this row when it lands in `uncounted_ingredients`. Only the
    # detail path fills it — the list path never emits the per-ingredient gaps
    # (see `get_recipes._nutrition_dto`), so paying to carry a label there
    # would buy nothing.
    display_name: str | None = None


@dataclass(frozen=True, slots=True)
class RecipeNutritionInput:
    recipe_id: object
    servings: int | None
    ingredients: List[IngredientInput]


def input_from_entity(recipe) -> RecipeNutritionInput:  # noqa: ANN001
    """Adapter for the detail path — a loaded `Recipe` with its ingredients'
    `stock_item` included."""
    return RecipeNutritionInput(
        recipe_id = recipe.id,
        servings = recipe.servings,
        ingredients = [
            IngredientInput(
                stock_item_id = ing.stock_item.id if ing.stock_item else None,
                stock_item_name = ing.stock_item.name if ing.stock_item else None,
                quantity = ing.quantity,
                unit = ing.unit,
                is_optional = getattr(ing, "is_optional", False),
                # The pantry item's name when there is one: a gap on a linked
                # row is fixed on that item, so naming it the way the pantry
                # does is what makes the fix findable. Unlinked rows have only
                # the text the author typed.
                display_name = (
                    ing.stock_item.name if ing.stock_item
                    else getattr(ing, "raw_text", None)
                ),
            )
            for ing in (recipe.ingredients or [])
        ],
    )


@dataclass(frozen=True, slots=True)
class UncountedIngredient:
    """One ingredient that contributed nothing, named and reasoned.

    The counts in `uncounted` say *how many* rows a gap covers; this says
    *which*, which is the difference between a coverage line the reader can
    only nod at and one they can act on. `stock_item_id` is the anchor for
    that action — a `no_food` / `no_data` gap is closed by linking a food to
    that pantry item — and is None exactly when the reason is `not_linked`.
    """
    name: str | None
    stock_item_id: object | None
    reason: str


@dataclass(frozen=True, slots=True)
class RecipeNutrition:
    """Per-recipe result. Nutrient fields are None when *no* counted
    ingredient carried that nutrient — a source can know kcal but not fibre,
    and a 0 would read as "this recipe has no fat"."""
    basis: str
    servings: int | None
    kcal: float | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    counted_count: int
    total_count: int
    uncounted: dict[str, int]
    # The same gaps, named row by row, in ingredient order.
    uncounted_ingredients: list[UncountedIngredient] = field(default_factory=list)
    # Whether the estimate covers enough of the recipe to rank or filter on
    # (see RELIABLE_COVERAGE_RATIO). Display is never gated on this — a partial
    # figure shown with its coverage is honest; a partial figure used to hide a
    # recipe from a calorie search is not.
    is_reliable: bool = False
    # ── Health Star Rating inputs and result (2026-08-27) ───────────────
    saturated_fat_g: float | None = None
    sugars_g: float | None = None
    fibre_g: float | None = None
    sodium_mg: float | None = None
    # Raw weight of everything the rollup could resolve, in grams. HSR is
    # scored per 100 g, so this is the denominator — and because it is the
    # *raw* weight it is an estimate: a sauce that reduces is more
    # concentrated than this says, and a soup made with water nobody listed
    # as an ingredient is less. Owner's call 2026-08-27 was to accept that
    # and label the rating an estimate rather than ask for a finished weight.
    total_grams: float | None = None
    # Percentage of `total_grams` that is fruit, vegetable, nut or legume.
    # None when nothing was counted at all — distinct from 0.0, which means
    # "counted, and none of it was fvnl".
    fvnl_percent: float | None = None
    # The Nutri-Score twin of `fvnl_percent`: fruit, vegetable or legume, with
    # nuts and seeds excluded from the numerator but still in the denominator.
    # Kept as its own figure rather than derived from the one above, because
    # the two published methods define the component differently — see
    # `food_categories.FVL_CATEGORIES`. Feeding either one to the other
    # scheme's module misgrades food.
    fvl_percent: float | None = None
    # Per nutrient, the fraction (0..1) of counted grams whose food actually
    # carried a figure. Keyed by the rollup names in `_SUMMED_NUTRIENTS`.
    # Weighted by mass rather than by ingredient count: 200 g of an
    # unmeasured ingredient distorts a per-100g figure far more than 2 g of
    # one does, and HSR is entirely a per-100g question.
    nutrient_coverage: dict[str, float] = field(default_factory=dict)
    # The rating itself, or None when nothing could be weighed.
    rating: hsr.HealthStarRating | None = None
    # The Nutri-Score, on the same terms. Both schemes are computed here rather
    # than the caller passing in which one it wants: they are pure table
    # lookups over figures this function has already done the expensive work to
    # assemble, so computing the unused one costs a few comparisons, while
    # taking a setting as an argument would give this module a dependency on
    # install configuration it otherwise has no reason to know about. The
    # caller decides which to *emit* (see `get_recipes`).
    nutri_score: ns.NutriScore | None = None


def _rollup_one(recipe: 'RecipeNutritionInput', food_ids_by_item: dict, foods: dict, portions: dict) -> RecipeNutrition:
    totals = {key: 0.0 for key, _ in _SUMMED_NUTRIENTS}
    contributors = dict.fromkeys(totals, 0)
    # Grams of counted ingredient whose food knew this nutrient. The mass-
    # weighted twin of `contributors`, and what the coverage line reports.
    known_grams = dict.fromkeys(totals, 0.0)
    uncounted = {reason: 0 for reason in UNCOUNTED_REASONS}
    uncounted_rows: list[UncountedIngredient] = []
    counted = 0
    total_grams = 0.0
    fvnl_grams = 0.0
    fvl_grams = 0.0

    required = [ing for ing in recipe.ingredients if not ing.is_optional]

    def gap(ingredient: 'IngredientInput', reason: str) -> None:
        """Record a gap both ways — the count the coverage line reads, and the
        named row the panel offers a fix on."""
        uncounted[reason] += 1
        uncounted_rows.append(UncountedIngredient(
            name = ingredient.display_name or ingredient.stock_item_name,
            stock_item_id = ingredient.stock_item_id,
            reason = reason,
        ))

    for ingredient in required:
        if ingredient.stock_item_id is None:
            gap(ingredient, REASON_NOT_LINKED)
            continue
        food_id = food_ids_by_item.get(ingredient.stock_item_id)
        food = foods.get(food_id) if food_id else None
        if food is None:
            gap(ingredient, REASON_NO_FOOD)
            continue
        if food.kcal_per_100g is None:
            # kcal is the load-bearing figure; a food without one can't
            # contribute to the headline, so it reads as a gap either way.
            gap(ingredient, REASON_NO_DATA)
            continue
        quantity = ingredient.quantity
        if quantity is None or quantity <= 0:
            gap(ingredient, REASON_NO_QUANTITY)
            continue
        grams = resolve_grams(
            float(quantity),
            ingredient.unit,
            portions.get(food.id, []),
            [name for name in (ingredient.stock_item_name, food.name) if name],
        )
        if grams is None:
            gap(ingredient, REASON_NO_CONVERSION)
            continue

        counted += 1
        total_grams += grams
        # The HSR fvnl numerator. Keyed off USDA's own food-group description
        # (see `food_categories.py`) — never off the user's StockGroup, which
        # is their filing system and none of this feature's business.
        category = getattr(food, "food_category", None)
        if is_fvnl_category(category):
            fvnl_grams += grams
        # Narrower than fvnl on purpose: nuts and seeds are excluded from the
        # Nutri-Score numerator but stay in `total_grams` below.
        if is_fvl_category(category):
            fvl_grams += grams
        hundreds = grams / 100.0
        for key, attr in _SUMMED_NUTRIENTS:
            per_100g = getattr(food, attr, None)
            if per_100g is None:
                continue
            totals[key] += hundreds * float(per_100g)
            contributors[key] += 1
            known_grams[key] += grams

    servings = recipe.servings if (recipe.servings or 0) > 0 else None
    divisor = float(servings) if servings else 1.0
    total_count = len(required)

    def per_basis(key: str, places: int) -> float | None:
        if contributors[key] == 0:
            return None
        return round(totals[key] / divisor, places)

    # ── Health Star Rating ──────────────────────────────────────────────
    # Scored per 100 g of the dish, which is a different basis from every
    # other figure here (those are per serving). `total_grams` is the raw
    # summed weight — see the field's note for why that is an estimate.
    rating = None
    nutri_score = None
    fvnl_percent = None
    fvl_percent = None
    coverage: dict[str, float] = {}
    if total_grams > 0:
        fvnl_percent = round(100.0 * fvnl_grams / total_grams, 1)
        fvl_percent = round(100.0 * fvl_grams / total_grams, 1)
        coverage = {
            key: round(known_grams[key] / total_grams, 3)
            for key, _ in _SUMMED_NUTRIENTS
        }

        def per_100g(key: str) -> float | None:
            # A nutrient nothing carried is None, not 0 — `rate()` reads the
            # difference, and so does the coverage line.
            if contributors[key] == 0:
                return None
            return totals[key] / (total_grams / 100.0)

        rating = hsr.rate(hsr.NutrientProfile(
            energy_kj = kcal_to_kj(per_100g("kcal")),
            saturated_fat_g = per_100g("saturated_fat_g"),
            total_sugars_g = per_100g("sugars_g"),
            sodium_mg = per_100g("sodium_mg"),
            protein_g = per_100g("protein_g"),
            fibre_g = per_100g("fibre_g"),
            fvnl_percent = fvnl_percent,
        ))
        # Same per-100g figures, a different published method. Note the two
        # take their fruit-and-veg share from different numerators, and that
        # `nutri_score` wants sodium in mg exactly as HSR does — it converts to
        # salt internally.
        nutri_score = ns.rate(ns.NutrientProfile(
            energy_kj = kcal_to_kj(per_100g("kcal")),
            saturated_fat_g = per_100g("saturated_fat_g"),
            total_sugars_g = per_100g("sugars_g"),
            sodium_mg = per_100g("sodium_mg"),
            protein_g = per_100g("protein_g"),
            fibre_g = per_100g("fibre_g"),
            fvl_percent = fvl_percent,
        ))

    return RecipeNutrition(
        basis = BASIS_SERVING if servings else BASIS_RECIPE,
        servings = servings,
        kcal = per_basis("kcal", _NUTRIENT_DECIMALS["kcal"]),
        protein_g = per_basis("protein_g", _NUTRIENT_DECIMALS["protein_g"]),
        carbs_g = per_basis("carbs_g", _NUTRIENT_DECIMALS["carbs_g"]),
        fat_g = per_basis("fat_g", _NUTRIENT_DECIMALS["fat_g"]),
        counted_count = counted,
        total_count = total_count,
        uncounted = {reason: count for reason, count in uncounted.items() if count},
        uncounted_ingredients = uncounted_rows,
        is_reliable = (
            counted > 0 and total_count > 0
            and (counted / total_count) >= RELIABLE_COVERAGE_RATIO
        ),
        saturated_fat_g = per_basis("saturated_fat_g", _NUTRIENT_DECIMALS["saturated_fat_g"]),
        sugars_g = per_basis("sugars_g", _NUTRIENT_DECIMALS["sugars_g"]),
        fibre_g = per_basis("fibre_g", _NUTRIENT_DECIMALS["fibre_g"]),
        sodium_mg = per_basis("sodium_mg", _NUTRIENT_DECIMALS["sodium_mg"]),
        total_grams = round(total_grams, 1) if total_grams > 0 else None,
        fvnl_percent = fvnl_percent,
        fvl_percent = fvl_percent,
        nutrient_coverage = coverage,
        rating = rating,
        nutri_score = nutri_score,
    )


def effective_kcal_per_serving(mode: str, typed_kcal, rollup: RecipeNutrition | None) -> tuple:
    """The one answer to "what does a serving of this recipe cost, calorie-wise?"

    Which field holds it depends on the mode — `simple` uses the number the
    user typed, `complex` the rollup over linked foods — and three surfaces now
    ask (cookbook card, kcal filter/sort, meal-plan entries). Deciding it once
    here, server-side, is R-003: the alternative was each client re-deriving
    "which field, and may I trust it", which is precisely how two surfaces end
    up disagreeing about the same recipe.

    Returns `(kcal_per_serving, is_reliable)`. `is_reliable` says whether the
    figure may be used to *judge* the recipe (filter it out, rank it) as
    opposed to merely display it (R-041).

    A complex rollup whose basis is the *whole recipe* — no servings typed in —
    deliberately yields None: dividing it by a serving count nobody stated
    would invent the very number being asked for (P12).
    """
    from dora_api.domain.entities.app_setting import (
        NUTRITION_MODE_COMPLEX, NUTRITION_MODE_SIMPLE,
    )

    if mode == NUTRITION_MODE_SIMPLE:
        # A hand-typed figure carries no coverage to doubt — the user asserted
        # it, so it's as judgeable as it is accurate.
        return (float(typed_kcal), True) if typed_kcal is not None else (None, False)
    if mode == NUTRITION_MODE_COMPLEX and rollup is not None:
        if rollup.kcal is None or rollup.basis != BASIS_SERVING:
            return (None, False)
        return (rollup.kcal, rollup.is_reliable)
    return (None, False)


def _foods_by_id(repository: Repository, food_ids: list) -> dict:
    """Stays here rather than in `household_measures`: the nutrient figures are
    this module's business, while the portion rows beside them answer a
    question costing asks too."""
    if not food_ids:
        return {}
    rows = repository.get(NutritionFood).where(
        Field(NutritionFood, "id").in_(food_ids)
    ).all()
    return {row.id: row for row in rows}


def rollup_recipes_nutrition(repository: Repository, recipes: Iterable['RecipeNutritionInput']) -> dict:
    """`recipe_id → RecipeNutrition` for every recipe passed. Three queries
    total (stock-item links, foods, portions) regardless of how many recipes —
    the cookbook list calls this for a whole page."""
    recipes = list(recipes)
    stock_item_ids = list({
        ingredient.stock_item_id
        for recipe in recipes
        for ingredient in recipe.ingredients
        if ingredient.stock_item_id is not None and not ingredient.is_optional
    })
    food_ids_by_item = food_ids_by_stock_item(repository, stock_item_ids)
    food_ids = list(set(food_ids_by_item.values()))
    foods = _foods_by_id(repository, food_ids)
    portions = portions_by_food(repository, food_ids)
    return {
        recipe.recipe_id: _rollup_one(recipe, food_ids_by_item, foods, portions)
        for recipe in recipes
    }


def rollup_recipe_nutrition(repository: Repository, recipe) -> RecipeNutrition:  # noqa: ANN001
    """Single-recipe path (the detail endpoint). `recipe` is the loaded entity;
    its `ingredients[].stock_item` must be included, which the recipe-detail
    query already does."""
    single = input_from_entity(recipe)
    return rollup_recipes_nutrition(repository, [single])[single.recipe_id]
