"""Auto-suggested nutrition links — what gets offered, and what deliberately
doesn't.

The matcher's whole value is in its restraint. Suggesting "Bananas, raw" for
"Bananas" saves a search; suggesting "Toilet" for "Toilet paper" trains the user
to stop reading the suggestions, and a pantry is mostly things a food catalogue
should never answer for. So the false-positive cases below are pinned as hard as
the true-positive ones — they're the reason the recall floor exists.

The confidence *bands* are pinned too, because `is_strong` is what the bulk
"accept all" verb acts on: a name that only reaches the weak band must keep
needing a human tap.
"""
import uuid

import pytest

from dora_api.domain.entities.nutrition_food import NUTRITION_SOURCE_USDA_SR_LEGACY
from dora_api.features.nutrition.suggestions import (
    MIN_CONFIDENCE, STRONG_CONFIDENCE, _best, _score,
)
from dora_api.features.nutrition.text_matching import normalised, singular, tokens


class _Food:
    """Only the fields the matcher reads. A real NutritionFood needs a
    persisted id and a source row; nothing here touches the database."""
    def __init__(self, name, kcal=100.0, brand=None):
        self.id = uuid.uuid4()
        self.name = name
        self.brand = brand
        self.source = NUTRITION_SOURCE_USDA_SR_LEGACY
        self.kcal_per_100g = kcal


def _score_of(item_name: str, food_name: str) -> float:
    return _score(tokens(item_name), normalised(item_name), _Food(food_name))


#region text normalisation

def test__tokens__PunctuationHeavyCatalogueName__MeetsPlainPantryName():
    # This is the whole reason tokens() exists: USDA writes
    # "Chicken, broilers or fryers, breast" and a user writes "chicken breast".
    assert tokens("chicken breast") <= tokens("Chicken, broilers or fryers, breast, raw")


def test__tokens__Digits__AreNotTokens():
    # "Milk 2%" and "Milk, 2% fat" should meet on `milk`; a stray number is
    # never what makes two foods the same thing.
    assert tokens("Milk 2%") == {"milk"}


@pytest.mark.parametrize("plural,expected", [
    ("bananas", "banana"), ("tomatoes", "tomato"), ("oats", "oat"),
])
def test__singular__CommonPlurals__Depluralised(plural, expected):
    assert singular(plural) == expected


@pytest.mark.parametrize("word", ["oz", "cos", "glass"])
def test__singular__ShortWordsAndDoubleS__LeftAlone(word):
    # Stripping the s off "oz" or "cos" changes what they mean.
    assert singular(word) == word

#endregion

#region what should be suggested

@pytest.mark.parametrize("item,food", [
    ("Bananas", "Bananas, raw"),
    ("Milk", "Milk, whole, 3.25% milkfat"),
    ("Olive oil", "Oil, olive, salad or cooking"),
    ("Cheddar cheese", "Cheese, cheddar"),
    ("Rolled oats", "Oats, whole grain, rolled, old fashioned"),
    ("Chicken breast", "Chicken, broilers or fryers, breast, meat only, raw"),
])
def test__score__RealPantryNames__ClearTheSuggestionFloor(item, food):
    assert _score_of(item, food) >= MIN_CONFIDENCE


def test__score__WordOrderReversed__ScoresAsAnExactMatch():
    # "Cheddar cheese" vs the catalogue's "Cheese, cheddar" is the same food;
    # the token sets are equal, so nothing is surplus and nothing is missing.
    assert _score_of("Cheddar cheese", "Cheese, cheddar") == pytest.approx(1.0)


def test__score__ExtraCatalogueQualifiers__CostScoreButStillMatch():
    plain = _score_of("Bananas", "Bananas, raw")
    qualified = _score_of("Bananas", "Bread, banana, prepared from recipe")
    assert plain > qualified

#endregion

#region what should NOT be suggested

@pytest.mark.parametrize("item,food", [
    # The owner's case: half a household item's name matching a one-word food
    # is not a match. Both of these scored exactly 0.50 before the recall floor.
    ("Toilet paper", "Toilet"),
    ("Dish soap", "Soap"),
    ("Washing powder", "Powder, baking"),
])
def test__score__NonFoodSharingOneWord__ScoresZero(item, food):
    assert _score_of(item, food) == 0.0


def test__score__NoSharedWords__ScoresZero():
    assert _score_of("Bananas", "Beef, ground, raw") == 0.0


def test__best__EverythingBelowTheFloor__NoSuggestion():
    assert _best("Tinned tomatoes", [_Food("Tomatoes, red, ripe, raw")]) is None


def test__best__FoodWithNoKcal__NeverSuggested():
    # Linking a food that carries no energy value changes no number on any
    # screen, so asking the user to confirm it is pure friction.
    assert _best("Bananas", [_Food("Bananas, raw", kcal=None)]) is None

#endregion

#region picking between candidates

def test__best__TiedScores__ShorterNameWins():
    # The less-qualified row is the generic one, which is the right answer for
    # a pantry staple — and without the tie-break the winner would depend on
    # database row order.
    chosen = _best("Cheese", [_Food("Cheese, cheddar, sharp"), _Food("Cheese, brie")])
    assert chosen.name == "Cheese, brie"


def test__best__ObviousMatch__IsStrongEnoughForBulkAccept():
    chosen = _best("Bananas", [_Food("Bananas, raw"), _Food("Banana chips, sweetened")])
    assert chosen.name == "Bananas, raw"
    assert chosen.is_strong is True


def test__best__HeavilyQualifiedMatch__NeedsAHumanTap():
    # Reaches the suggestion floor but not the bulk-accept band: a row this
    # specific ("meat only, raw") is a judgement call, not a certainty.
    chosen = _best("Chicken breast", [_Food("Chicken, broilers or fryers, breast, meat only, raw")])
    assert MIN_CONFIDENCE <= chosen.confidence < STRONG_CONFIDENCE
    assert chosen.is_strong is False


def test__best__Suggestion__CarriesItsSourceLabel():
    # Every suggestion says where the numbers came from, same as every lookup
    # result does (P3) — the UI badges it.
    assert _best("Bananas", [_Food("Bananas, raw")]).source_label == "USDA SR Legacy"

#endregion


#region regional vocabulary (FU-643)

@pytest.mark.parametrize("item,food", [
    ("Tinned tomatoes", "Tomatoes, red, ripe, canned, packed in tomato juice"),
    ("Capsicum", "Peppers, sweet, red, raw"),
    ("Aubergine", "Eggplant, raw"),
    ("Beef mince", "Beef, ground, 85% lean meat / 15% fat, raw"),
    ("Prawns", "Crustaceans, shrimp, raw"),
    ("Coriander", "Coriander (cilantro) leaves, raw"),
    ("Plain flour", "Wheat flour, white, all-purpose, enriched, bleached"),
    ("Icing sugar", "Sugars, powdered"),
])
def test__best__AuUkNames__FindTheUsCatalogueRow(item, food):
    """An Australian pantry name meets the US catalogue's word for it."""
    suggestion = _best(item, [_Food(food), _Food("Toilet"), _Food("Soup, chicken noodle")])
    assert suggestion is not None and suggestion.name == food


def test__best__UsNames__AreUnchanged():
    """A name already in the catalogue's words scores exactly as before."""
    assert _best("Bananas", [_Food("Bananas, raw")]).confidence == pytest.approx(
        _score_of("Bananas", "Bananas, raw"), abs=1e-3)

#endregion
