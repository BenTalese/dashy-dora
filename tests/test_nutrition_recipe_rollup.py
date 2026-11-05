"""Recipe nutrition rollup — gram conversion, coverage honesty, and the
per-serving basis.

The numbers here are the whole point of complex mode, so what's pinned is
mostly *when we refuse to answer*: an ingredient whose weight can't be known
must land in the coverage line rather than be approximated, because a total
that quietly skips two ingredients while presenting itself as complete is
worse than no total at all.
"""
from uuid import uuid4

import pytest

from dora_api.features.nutrition.recipe_rollup import (
    BASIS_RECIPE,
    BASIS_SERVING,
    RecipeNutrition,
    effective_kcal_per_serving,
    REASON_NOT_LINKED,
    REASON_NO_CONVERSION,
    REASON_NO_DATA,
    REASON_NO_FOOD,
    REASON_NO_QUANTITY,
    rollup_recipe_nutrition,
)


class _Food:
    def __init__(self, name, kcal=100.0, protein=None, carbs=None, fat=None,
                 saturated_fat=None, sugars=None, fibre=None, sodium=None,
                 food_category=None):
        self.id = uuid4()
        self.name = name
        self.kcal_per_100g = kcal
        self.protein_g_per_100g = protein
        self.carbs_g_per_100g = carbs
        self.fat_g_per_100g = fat
        # The Health Star Rating inputs (2026-08-27). Default None so every
        # existing test still describes a food that knows only its energy.
        self.saturated_fat_g_per_100g = saturated_fat
        self.sugars_g_per_100g = sugars
        self.fibre_g_per_100g = fibre
        self.sodium_mg_per_100g = sodium
        # USDA's food group, the fvnl test's only input. See
        # `features/nutrition/food_categories.py`.
        self.food_category = food_category


class _Portion:
    def __init__(self, food_id, amount, measure, gram_weight):
        self.nutrition_food_id = food_id
        self.amount = amount
        self.measure = measure
        self.gram_weight = gram_weight


class _StockItem:
    def __init__(self, name, food=None):
        self.id = uuid4()
        self.name = name
        self.nutrition_food_id = food.id if food else None


class _Ingredient:
    def __init__(self, stock_item=None, quantity=None, unit=None, is_optional=False):
        self.stock_item = stock_item
        self.quantity = quantity
        self.unit = unit
        self.is_optional = is_optional
        self.id = uuid4()


class _Recipe:
    def __init__(self, ingredients, servings=None):
        self.id = uuid4()
        self.ingredients = ingredients
        self.servings = servings


class _Repo:
    """Serves the three batch queries the rollup makes, without a database.

    Deliberately ignores the filter condition and returns everything seeded —
    the repository query path itself is covered by the e2e suite; here the
    subject is the arithmetic. Stock items are collected from the recipe under
    test so the `stock_item → food` hop resolves the same way it does live.
    """
    def __init__(self, foods=(), portions=(), stock_items=()):
        self._foods = list(foods)
        self._portions = list(portions)
        self._stock_items = list(stock_items)
        self._pending = None

    def get(self, entity):
        self._pending = entity.__name__
        return self

    def where(self, _condition):
        return self

    def all(self):
        if self._pending == "StockItem":
            return self._stock_items
        if self._pending == "NutritionFood":
            return self._foods
        return self._portions


def _repo_for(recipe, foods=(), portions=()):
    """A repo double seeded with the recipe's own stock items."""
    items = [
        ing.stock_item for ing in recipe.ingredients if ing.stock_item is not None
    ]
    return _Repo(foods=foods, portions=portions, stock_items=items)


#region gram conversion

def test__rollup__MassUnit__ConvertsDirectly():
    food = _Food("Flour", kcal=364.0)
    recipe = _Recipe([_Ingredient(_StockItem("Flour", food), 250, "g")], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [food]), recipe)

    assert result.kcal == pytest.approx(910)
    assert (result.counted_count, result.total_count) == (1, 1)


def test__rollup__KilogramsAndOunces__NormaliseToGrams():
    food = _Food("Rice", kcal=130.0)
    recipe = _Recipe(
        [
            _Ingredient(_StockItem("Rice", food), 0.5, "kg"),
            _Ingredient(_StockItem("Rice", food), 1, "oz"),
        ],
        servings=1,
    )

    result = rollup_recipe_nutrition(_repo_for(recipe, [food]), recipe)

    # 500g + 28.3495g at 130 kcal/100g.
    assert result.kcal == pytest.approx(round((500 + 28.3495) / 100 * 130))


def test__rollup__VolumeWithMatchingPortion__PrefersTheMeasuredPortionOverDensity():
    # "cup" is in the density table as flour (0.53 g/ml → 132.5g per AU cup),
    # but the food's own portion row says 125g. The measured row wins.
    food = _Food("Flour", kcal=100.0)
    portion = _Portion(food.id, 1, "cup", 125.0)
    recipe = _Recipe([_Ingredient(_StockItem("flour", food), 2, "cups")], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [food], [portion]), recipe)

    assert result.kcal == pytest.approx(250)


def test__rollup__VolumeWithoutPortion__FallsBackToTheSharedDensityTable():
    food = _Food("Milk", kcal=100.0)
    recipe = _Recipe([_Ingredient(_StockItem("milk", food), 500, "ml")], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [food]), recipe)

    # milk density 1.03 g/ml → 515g.
    assert result.kcal == pytest.approx(515)


def test__rollup__PortionMatching__TakesTheLeastQualifiedMeasure():
    # A recipe saying "1 cup" means a plain cup; "cup, chopped" weighs
    # differently and is the wrong answer unless the recipe said chopped.
    food = _Food("Onion", kcal=100.0)
    portions = [
        _Portion(food.id, 1, "cup, chopped", 160.0),
        _Portion(food.id, 1, "cup", 110.0),
    ]
    recipe = _Recipe([_Ingredient(_StockItem("onion", food), 1, "cup")], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [food], portions), recipe)

    assert result.kcal == pytest.approx(110)


def test__rollup__CountWithNoUnit__UsesAWholeItemPortion():
    food = _Food("Bananas, raw", kcal=89.0)
    portions = [
        _Portion(food.id, 1, "cup, sliced", 150.0),
        _Portion(food.id, 1, "medium (7\" long)", 118.0),
    ]
    recipe = _Recipe([_Ingredient(_StockItem("Banana", food), 2, None)], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [food], portions), recipe)

    assert result.kcal == pytest.approx(round(2 * 118 / 100 * 89))


def test__rollup__CountWithNoWholeItemPortion__IsUnconvertibleNotGuessed():
    food = _Food("Onion", kcal=40.0)
    portions = [_Portion(food.id, 1, "cup, chopped", 160.0)]
    recipe = _Recipe([_Ingredient(_StockItem("Onion", food), 1, None)], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [food], portions), recipe)

    assert result.kcal is None
    assert result.uncounted == {REASON_NO_CONVERSION: 1}


def test__rollup__WholeAsAUnit__CountsTheSameAsNoUnitAtAll():
    """"1 whole onion" and "1 onion" are the same ingredient. `whole` used to
    be an unrecognised word, so only a portion row literally saying "whole"
    could answer it — the count ladder never ran (owner 2026-09-09)."""
    food = _Food("Onion", kcal=40.0)
    portions = [_Portion(food.id, 1, "medium", 110.0)]
    recipe = _Recipe([_Ingredient(_StockItem("Onion", food), 1, "whole")], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [food], portions), recipe)

    assert result.kcal == pytest.approx(round(110 / 100 * 40))


def test__rollup__SticksOfCelery__WeighedByThePortionRowNotTheButterStick():
    """`units` prices a stick at 113 g because that is butter. Celery went
    through the same conversion and came out at 226 g for two stalks."""
    food = _Food("Celery", kcal=16.0)
    portions = [_Portion(food.id, 1, "stalk, medium", 40.0)]
    recipe = _Recipe([_Ingredient(_StockItem("Celery", food), 2, "sticks")], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [food], portions), recipe)

    assert result.total_grams == pytest.approx(80.0)


def test__rollup__SticksWithNoPortionRow__IsUnconvertibleNotButter():
    """The point of the guard: absent a row of the food's own, a food-specific
    mass word reports honestly rather than borrowing butter's weight."""
    food = _Food("Cinnamon", kcal=247.0)
    recipe = _Recipe([_Ingredient(_StockItem("Cinnamon", food), 1, "stick")], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [food]), recipe)

    assert result.kcal is None
    assert result.uncounted == {REASON_NO_CONVERSION: 1}


def test__rollup__SticksOfButter__StillWeighedFromItsOwnPortionRow():
    food = _Food("Butter", kcal=717.0)
    portions = [_Portion(food.id, 1, "stick", 113.0)]
    recipe = _Recipe([_Ingredient(_StockItem("Butter", food), 1, "stick")], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [food], portions), recipe)

    assert result.total_grams == pytest.approx(113.0)


def test__rollup__VolumeAgainstAQualifiedPantryName__ReachesTheDensityTable():
    """The density fallback is keyed on the ingredient's name, and matched it
    exactly until 2026-09-09 — so it fired for "milk" and never for what a
    household actually calls the carton."""
    food = _Food("Milk", kcal=64.0)
    recipe = _Recipe(
        [_Ingredient(_StockItem("Full Cream Milk", food), 200, "ml")], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [food]), recipe)

    assert result.total_grams == pytest.approx(206.0)


def test__rollup__UnknownUnitWord__AnsweredOnlyByAPortionRow():
    food = _Food("Garlic", kcal=149.0)
    portions = [_Portion(food.id, 1, "clove", 3.0)]
    recipe = _Recipe([_Ingredient(_StockItem("Garlic", food), 3, "cloves")], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [food], portions), recipe)

    assert result.kcal == pytest.approx(round(9 / 100 * 149))


def test__rollup__UnknownUnitWordWithNoPortion__IsUnconvertible():
    food = _Food("Parsley", kcal=36.0)
    recipe = _Recipe([_Ingredient(_StockItem("Parsley", food), 2, "sprigs")], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [food]), recipe)

    assert result.uncounted == {REASON_NO_CONVERSION: 1}

#endregion

#region coverage honesty

def test__rollup__EveryFailureKind__IsNamedInTheCoverageMap():
    good = _Food("Flour", kcal=364.0)
    dataless = _Food("Water", kcal=None)
    recipe = _Recipe(
        [
            _Ingredient(_StockItem("Flour", good), 100, "g"),
            _Ingredient(None, 1, "g"),                                   # not linked
            _Ingredient(_StockItem("Salt"), 1, "g"),                     # no food
            _Ingredient(_StockItem("Water", dataless), 1, "g"),          # no kcal
            _Ingredient(_StockItem("Pepper", good), None, None),         # no quantity
            _Ingredient(_StockItem("Basil", good), 2, "sprigs"),         # no conversion
        ],
        servings=1,
    )

    result = rollup_recipe_nutrition(_repo_for(recipe, [good, dataless]), recipe)

    assert (result.counted_count, result.total_count) == (1, 6)
    assert result.uncounted == {
        REASON_NOT_LINKED: 1,
        REASON_NO_FOOD: 1,
        REASON_NO_DATA: 1,
        REASON_NO_QUANTITY: 1,
        REASON_NO_CONVERSION: 1,
    }


def test__rollup__EveryFailureKind__NamesTheIngredientBehindIt():
    # The counts say how many; this says which — the panel offers a "find a
    # food" search per row, and it needs the pantry item to write the link to.
    good = _Food("Flour", kcal=364.0)
    recipe = _Recipe(
        [
            _Ingredient(_StockItem("Flour", good), 100, "g"),
            _Ingredient(None, 1, "g"),
            _Ingredient(_StockItem("Salt"), 1, "g"),
        ],
        servings=1,
    )

    result = rollup_recipe_nutrition(_repo_for(recipe, [good]), recipe)

    assert [(row.name, row.reason) for row in result.uncounted_ingredients] == [
        (None, REASON_NOT_LINKED),
        ("Salt", REASON_NO_FOOD),
    ]
    # Only the linked row carries an anchor to fix it on.
    assert result.uncounted_ingredients[0].stock_item_id is None
    assert result.uncounted_ingredients[1].stock_item_id is not None
    # Every gap names its own row, the anchor for an on-the-row fix (FU-895).
    assert [row.ingredient_id for row in result.uncounted_ingredients] == [
        ing.id for ing in recipe.ingredients[1:]
    ]


def test__rollup__NothingCountable__ReportsNullsRatherThanZero():
    recipe = _Recipe([_Ingredient(None, 1, "g"), _Ingredient(None, 2, "g")])

    result = rollup_recipe_nutrition(_repo_for(recipe), recipe)

    assert (result.kcal, result.protein_g, result.carbs_g, result.fat_g) == (None, None, None, None)
    assert (result.counted_count, result.total_count) == (0, 2)


def test__rollup__MacroMissingOnEveryCountedFood__StaysNullWhileKcalCounts():
    # A source can know kcal but not fat; a 0 would read as "this recipe has
    # no fat", which is a different claim from "nobody told us".
    food = _Food("Flour", kcal=364.0, protein=10.3)
    recipe = _Recipe([_Ingredient(_StockItem("Flour", food), 100, "g")], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [food]), recipe)

    assert result.kcal == pytest.approx(364)
    assert result.protein_g == pytest.approx(10.3)
    assert result.fat_g is None


def test__rollup__OptionalIngredients__SitOutsideBothHalvesOfTheRatio():
    food = _Food("Flour", kcal=364.0)
    recipe = _Recipe(
        [
            _Ingredient(_StockItem("Flour", food), 100, "g"),
            _Ingredient(_StockItem("Truffle", food), 100, "g", is_optional=True),
        ],
        servings=1,
    )

    result = rollup_recipe_nutrition(_repo_for(recipe, [food]), recipe)

    assert (result.counted_count, result.total_count) == (1, 1)
    assert result.kcal == pytest.approx(364)

#endregion

#region basis

def test__rollup__ServingsTypedIn__DividesPerServing():
    food = _Food("Flour", kcal=100.0, protein=10.0)
    recipe = _Recipe([_Ingredient(_StockItem("Flour", food), 400, "g")], servings=4)

    result = rollup_recipe_nutrition(_repo_for(recipe, [food]), recipe)

    assert result.basis == BASIS_SERVING
    assert result.servings == 4
    assert result.kcal == pytest.approx(100)
    assert result.protein_g == pytest.approx(10.0)


@pytest.mark.parametrize("servings", [None, 0])
def test__rollup__NoServings__ReportsTheWholeRecipeAndSaysSo(servings):
    food = _Food("Flour", kcal=100.0)
    recipe = _Recipe([_Ingredient(_StockItem("Flour", food), 400, "g")], servings=servings)

    result = rollup_recipe_nutrition(_repo_for(recipe, [food]), recipe)

    assert result.basis == BASIS_RECIPE
    assert result.servings is None
    assert result.kcal == pytest.approx(400)

#endregion


#region effective per-serving figure (what every surface reads)

def _rollup(**over) -> RecipeNutrition:
    base = dict(
        basis=BASIS_SERVING, servings=4, kcal=500.0, protein_g=None, carbs_g=None,
        fat_g=None, counted_count=8, total_count=8, uncounted={}, is_reliable=True,
    )
    base.update(over)
    return RecipeNutrition(**base)


def test__effective_kcal__SimpleMode__UsesTheTypedNumberAndTrustsIt():
    # No coverage to doubt — the user asserted it themselves.
    assert effective_kcal_per_serving("simple", 420, None) == (420.0, True)


def test__effective_kcal__SimpleModeWithNothingTyped__HasNoFigure():
    assert effective_kcal_per_serving("simple", None, None) == (None, False)


def test__effective_kcal__ComplexMode__UsesTheRollupAndIgnoresAStaleTypedNumber():
    assert effective_kcal_per_serving("complex", 999, _rollup(kcal=500.0)) == (500.0, True)


def test__effective_kcal__ComplexModeThinCoverage__ShowsTheFigureButWontBeJudgedOn():
    assert effective_kcal_per_serving(
        "complex", None, _rollup(kcal=500.0, counted_count=1, is_reliable=False),
    ) == (500.0, False)


def test__effective_kcal__WholeRecipeBasis__RefusesToInventAPerServingFigure():
    # No servings typed in, so the rollup's number is the whole pot. Dividing
    # it by a serving count nobody stated would invent the answer.
    assert effective_kcal_per_serving(
        "complex", None, _rollup(basis=BASIS_RECIPE, servings=None),
    ) == (None, False)


def test__effective_kcal__NutritionOff__SaysNothingEvenWithDataAvailable():
    assert effective_kcal_per_serving("off", 420, _rollup()) == (None, False)

#endregion


#endregion

#region health star rating (2026-08-27)
# The rollup's job for HSR is *not* the scoring — that lives in
# `domain/health_star_rating.py` and is pinned band-by-band in
# `test_health_star_rating.py`. What's pinned here is the plumbing between the
# two, which is where the mistakes would be: the per-100g basis (a different
# basis from every other figure the rollup returns), the fvnl numerator, and
# the mass-weighted coverage that stops a missing penalty nutrient passing for
# a clean score.

VEGETABLES = "Vegetables and Vegetable Products"
FRUIT = "Fruits and Fruit Juices"
DAIRY = "Dairy and Egg Products"


def test__rating__is_scored_per_100g_of_the_dish_not_per_serving():
    """The trap: every other figure the rollup returns is divided by servings.
    HSR is not — it is per 100 g of food, so a recipe serving 1 and the same
    recipe serving 8 must rate identically."""
    food = _Food("Rice", kcal=130.0, food_category="Cereal Grains and Pasta")
    one = _Recipe([_Ingredient(_StockItem("Rice", food), 500, "g")], servings=1)
    eight = _Recipe([_Ingredient(_StockItem("Rice", food), 500, "g")], servings=8)

    rated_one = rollup_recipe_nutrition(_repo_for(one, [food]), one)
    rated_eight = rollup_recipe_nutrition(_repo_for(eight, [food]), eight)

    assert rated_one.kcal != rated_eight.kcal          # per-serving figures differ
    assert rated_one.rating.stars == rated_eight.rating.stars
    assert rated_one.rating.score == rated_eight.rating.score


def test__rating__energy_points_come_from_the_per_100g_density():
    """400 kcal/100g is ~1674 kJ, one band below the >1675 edge — so the whole
    chain (per-100g division, then the kcal-to-kJ conversion) has to be right
    for this to land on 4 rather than 5 or 0."""
    food = _Food("Rich thing", kcal=400.0)
    recipe = _Recipe([_Ingredient(_StockItem("Rich thing", food), 250, "g")], servings=2)

    result = rollup_recipe_nutrition(_repo_for(recipe, [food]), recipe)

    assert result.total_grams == pytest.approx(250)
    assert result.rating.energy_points == 4


def test__fvnl_percent__is_the_mass_fraction_of_fvnl_category_foods():
    carrot = _Food("Carrot", kcal=41.0, food_category=VEGETABLES)
    butter = _Food("Butter", kcal=717.0, food_category="Fats and Oils")
    recipe = _Recipe([
        _Ingredient(_StockItem("Carrot", carrot), 300, "g"),
        _Ingredient(_StockItem("Butter", butter), 100, "g"),
    ], servings=2)

    result = rollup_recipe_nutrition(_repo_for(recipe, [carrot, butter]), recipe)

    assert result.total_grams == pytest.approx(400)
    assert result.fvnl_percent == pytest.approx(75.0)
    # 75% is the >75 band's floor, so it scores 3 — not 4. A mass fraction
    # computed by ingredient *count* instead would have given 50% here.
    assert result.rating.v_points == 3


def test__fvnl_percent__counts_fruit_and_vegetables_alike():
    apple = _Food("Apple", kcal=52.0, food_category=FRUIT)
    carrot = _Food("Carrot", kcal=41.0, food_category=VEGETABLES)
    recipe = _Recipe([
        _Ingredient(_StockItem("Apple", apple), 100, "g"),
        _Ingredient(_StockItem("Carrot", carrot), 100, "g"),
    ], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [apple, carrot]), recipe)

    assert result.fvnl_percent == pytest.approx(100.0)


def test__fvnl_percent__an_unclassified_food_scores_nothing_rather_than_guessing():
    """A food imported before the category column existed carries None. It has
    to read as "not fvnl" — the conservative direction — not as an error and
    not as a guess from its name."""
    unknown = _Food("Mystery veg", kcal=40.0, food_category=None)
    recipe = _Recipe([_Ingredient(_StockItem("Mystery veg", unknown), 200, "g")], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [unknown]), recipe)

    assert result.fvnl_percent == pytest.approx(0.0)
    assert result.rating.v_points == 0


def test__fvnl_percent__is_none_when_nothing_could_be_weighed():
    """Distinct from 0.0: "we weighed this dish and none of it was fvnl" is a
    different statement from "we could not weigh this dish"."""
    recipe = _Recipe([_Ingredient(None, None, None)], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe), recipe)

    assert result.fvnl_percent is None
    assert result.total_grams is None
    assert result.rating is None


def test__nutrient_coverage__is_weighted_by_mass_not_by_ingredient_count():
    """200 g of an ingredient with no sugars figure distorts a per-100g total
    far more than 20 g of one does, and HSR is entirely a per-100g question —
    so coverage counts grams, not rows."""
    known = _Food("Known", kcal=100.0, sugars=10.0, food_category=DAIRY)
    unknown = _Food("Unknown", kcal=100.0, sugars=None, food_category=DAIRY)
    recipe = _Recipe([
        _Ingredient(_StockItem("Known", known), 100, "g"),
        _Ingredient(_StockItem("Unknown", unknown), 300, "g"),
    ], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [known, unknown]), recipe)

    # By row count this would be 0.5; by mass it is 100/400.
    assert result.nutrient_coverage["sugars_g"] == pytest.approx(0.25)
    assert result.nutrient_coverage["kcal"] == pytest.approx(1.0)


def test__missing_sugars__flatters_the_rating_which_is_why_coverage_is_reported():
    """The measured USDA gap (sugars known for ~77% of SR Legacy foods) as a
    rollup-level assertion. Both dishes are identical but for the sugar figure,
    and the one we know less about rates better — so the rating can never be
    rendered without its coverage beside it."""
    sweet = _Food("Sweet", kcal=350.0, sugars=45.0)
    silent = _Food("Sweet", kcal=350.0, sugars=None)
    known = _Recipe([_Ingredient(_StockItem("Sweet", sweet), 200, "g")], servings=1)
    unknown = _Recipe([_Ingredient(_StockItem("Sweet", silent), 200, "g")], servings=1)

    rated_known = rollup_recipe_nutrition(_repo_for(known, [sweet]), known)
    rated_unknown = rollup_recipe_nutrition(_repo_for(unknown, [silent]), unknown)

    assert rated_unknown.rating.stars > rated_known.rating.stars
    assert rated_known.nutrient_coverage["sugars_g"] == pytest.approx(1.0)
    assert rated_unknown.nutrient_coverage["sugars_g"] == pytest.approx(0.0)


def test__rating__the_new_nutrients_are_summed_per_serving_as_well():
    """Saturated fat, sugars, fibre and sodium ride the same per-serving path
    the macros do — the panel renders them, not just the rating."""
    food = _Food(
        "Thing", kcal=200.0, protein=10.0,
        saturated_fat=4.0, sugars=6.0, fibre=3.0, sodium=400.0,
    )
    recipe = _Recipe([_Ingredient(_StockItem("Thing", food), 200, "g")], servings=2)

    result = rollup_recipe_nutrition(_repo_for(recipe, [food]), recipe)

    # 200 g of the food, halved across 2 servings, so 100 g worth per serving.
    assert result.saturated_fat_g == pytest.approx(4.0)
    assert result.sugars_g == pytest.approx(6.0)
    assert result.fibre_g == pytest.approx(3.0)
    assert result.sodium_mg == pytest.approx(400)


def test__optional_ingredients__stay_out_of_the_rating_too():
    """They sit outside both halves of the coverage ratio already; they must
    also stay out of the fvnl fraction, or marking the garnish optional would
    change the star rating."""
    base = _Food("Base", kcal=300.0, food_category="Cereal Grains and Pasta")
    herb = _Food("Parsley", kcal=36.0, food_category="Spices and Herbs")
    recipe = _Recipe([
        _Ingredient(_StockItem("Base", base), 100, "g"),
        _Ingredient(_StockItem("Parsley", herb), 100, "g", is_optional=True),
    ], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [base, herb]), recipe)

    assert result.total_grams == pytest.approx(100)
    assert result.fvnl_percent == pytest.approx(0.0)

#endregion


#region nutri-score (2026-08-27)
# Same division of labour as the HSR region above: the arithmetic is pinned in
# `test_nutri_score.py` against the official worked examples, and what's
# pinned here is the plumbing. The one thing that genuinely differs between the
# two schemes at *this* layer is the fruit-and-veg numerator, so that is what
# these lean on.

NUTS = "Nut and Seed Products"


def test__both_schemes_are_computed_so_the_caller_can_choose():
    """The rollup does not know which scheme the install picked — it returns
    both and `get_recipes` emits one. A None here would mean a household that
    switches scheme sees nothing until something invalidates a cache."""
    carrot = _Food("Carrot", kcal=41.0, food_category=VEGETABLES)
    recipe = _Recipe([_Ingredient(_StockItem("Carrot", carrot), 200, "g")], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [carrot]), recipe)

    assert result.rating is not None
    assert result.nutri_score is not None


def test__fvl_percent__excludes_nuts_where_fvnl_includes_them():
    """The divergence that makes these two separate numerators rather than one.

    HSR counts nuts toward fvnl; the Nutri-Score 2023 update moved nuts and
    seeds out of the positive component, while leaving them in the denominator.
    A dish of half carrot, half almonds is therefore 100% fvnl and 50% fvl —
    and feeding the wrong one to either module silently misgrades the food.
    """
    carrot = _Food("Carrot", kcal=41.0, food_category=VEGETABLES)
    almond = _Food("Almond", kcal=579.0, food_category=NUTS)
    recipe = _Recipe([
        _Ingredient(_StockItem("Carrot", carrot), 100, "g"),
        _Ingredient(_StockItem("Almond", almond), 100, "g"),
    ], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [carrot, almond]), recipe)

    assert result.total_grams == pytest.approx(200)
    assert result.fvnl_percent == pytest.approx(100.0)
    assert result.fvl_percent == pytest.approx(50.0)
    # And the points follow: full marks on the HSR side, the middle band on the
    # Nutri-Score side.
    assert result.rating.v_points == 8
    assert result.nutri_score.fvl_points == 1


def test__fvl_percent__counts_legumes_and_fruit_alike():
    apple = _Food("Apple", kcal=52.0, food_category=FRUIT)
    lentil = _Food("Lentil", kcal=116.0, food_category="Legumes and Legume Products")
    recipe = _Recipe([
        _Ingredient(_StockItem("Apple", apple), 100, "g"),
        _Ingredient(_StockItem("Lentil", lentil), 100, "g"),
    ], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [apple, lentil]), recipe)

    assert result.fvl_percent == pytest.approx(100.0)
    assert result.nutri_score.fvl_points == 5


def test__nutri_score__is_scored_per_100g_of_the_dish_not_per_serving():
    """The same trap the HSR twin guards, for the same reason."""
    food = _Food("Rice", kcal=130.0, food_category="Cereal Grains and Pasta")
    one = _Recipe([_Ingredient(_StockItem("Rice", food), 500, "g")], servings=1)
    eight = _Recipe([_Ingredient(_StockItem("Rice", food), 500, "g")], servings=8)

    rated_one = rollup_recipe_nutrition(_repo_for(one, [food]), one)
    rated_eight = rollup_recipe_nutrition(_repo_for(eight, [food]), eight)

    assert rated_one.nutri_score.grade == rated_eight.nutri_score.grade
    assert rated_one.nutri_score.score == rated_eight.nutri_score.score


def test__nutri_score__salt_points_come_from_sodium_via_the_published_factor():
    """Dora stores sodium; Table 5 is in salt. 1000 mg sodium per 100 g is
    2.5 g salt, which is band 12 — a rollup that forgot the ×2.5 would report
    band 4 (treating 1.0 g), and a rollup that passed mg straight through
    would saturate at 20."""
    salty = _Food("Salty thing", kcal=100.0, sodium=1000.0, food_category=DAIRY)
    recipe = _Recipe([_Ingredient(_StockItem("Salty thing", salty), 100, "g")], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe, [salty]), recipe)

    assert result.nutri_score.salt_points == 12


def test__nutri_score__is_none_when_nothing_could_be_weighed():
    recipe = _Recipe([_Ingredient(None, None, None)], servings=1)

    result = rollup_recipe_nutrition(_repo_for(recipe), recipe)

    assert result.fvl_percent is None
    assert result.nutri_score is None

#endregion
