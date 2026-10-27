"""`recipe_cost._line_cost` — what one ingredient contributes to the estimate.

Its sibling `test_recipe_item_price` pins the *price* half (what one countable
item costs). These pin the *quantity* half: how a written ingredient meets the
unit its price is per.

Written 2026-09-09, driving a realistic recipe through the estimator line by
line. Three of the cases below were defects it surfaced:

* a cross-dimension line (a recipe in cups against a price per kilo) was never
  even attempted, because the ingredient's name — the key the density table is
  keyed on — was not passed to `units.convert` (FU-874);
* "2 sticks of celery" was billed at 226 g, `stick` being a stick of butter;
* an ingredient with no amount at all ("salt to taste") was billed as one whole
  product *and* counted toward the priced ratio.
"""
from dataclasses import dataclass

import pytest

from dora_api.features.recipes.recipe_cost import (
    UNPRICED_NO_QUANTITY, UNPRICED_UNIT_MISMATCH, UNPRICED_UNIT_NO_PACK_COUNT,
    UNPRICED_UNIT_NO_PACK_SIZE, UNPRICED_UNIT_UNKNOWN_DENSITY,
    UNPRICED_UNIT_WRONG_FOOD, UnitPrice, _cost_one, _line_cost,
    _price_line,
)
from dora_api.persistence.uuid_key import uuid_key


@dataclass(frozen=True)
class _Ingredient:
    stock_item_id: object
    stock_item_name: str | None
    quantity: float | None
    unit: str | None


@dataclass(frozen=True)
class _Portion:
    """Duck-typed `NutritionPortion` — a household measure and its weight."""
    amount: float
    measure: str
    gram_weight: float


def _ing(name, quantity, unit, stock_item_id="item-1"):
    return _Ingredient(stock_item_id, name, quantity, unit)


# ── Same dimension ────────────────────────────────────────────────────────


def test__line_cost__SameUnitAsThePrice__MultipliesDirectly():
    assert _line_cost(
        _ing("Chicken Thighs", 800, "g"), UnitPrice(0.011, "g"),
    ) == pytest.approx(8.80)


def test__line_cost__WithinOneDimension__ConvertsFirst():
    assert _line_cost(
        _ing("Chicken Thighs", 0.8, "kg"), UnitPrice(0.011, "g"),
    ) == pytest.approx(8.80)


# ── Mass ↔ volume: the density bridge (FU-874) ────────────────────────────


def test__line_cost__CupsAgainstAPerGramPrice__UsesTheDensityTable():
    """A quarter of a 250 ml cup of flour at 0.53 g/ml is 33.125 g. The bridge
    existed and the table was right; the name was simply never handed over, so
    this answered None."""
    assert _line_cost(
        _ing("Plain Flour", 0.25, "cup"), UnitPrice(0.0018, "g"),
    ) == pytest.approx(33.125 * 0.0018)


def test__line_cost__QualifiedPantryName__StillReachesTheTable():
    """The other half of the same fix: households type "Full Cream Milk"."""
    assert _line_cost(
        _ing("Full Cream Milk", 300, "ml"), UnitPrice(0.0015, "ml"),
    ) == pytest.approx(0.45)
    assert _line_cost(
        _ing("Full Cream Milk", 300, "ml"), UnitPrice(0.002, "g"),
    ) == pytest.approx(309.0 * 0.002)


def test__line_cost__IngredientTheTableDoesNotList__StaysUnpriced():
    """ADR-073 is unchanged by the widened lookup: no density, no guess."""
    assert _line_cost(
        _ing("Dijon Mustard", 2, "tsp"), UnitPrice(0.019, "g"),
    ) is None


# ── Food-specific mass units ──────────────────────────────────────────────


def test__line_cost__SticksOfCelery__AreNotSticksOfButter():
    """226 g of celery at $4/kg is 90c for two stalks that cost about 30c."""
    assert _line_cost(
        _ing("Celery", 2, "sticks"), UnitPrice(0.004, "g"),
    ) is None


def test__line_cost__SticksOfButter__StillPrice():
    assert _line_cost(
        _ing("Salted Butter", 1, "stick"), UnitPrice(0.012, "g"),
    ) == pytest.approx(113.0 * 0.012)


def test__line_cost__SticksOfSomethingUnnamed__AreRefused():
    """No name means no way to know whose stick it is, and the wrong answer is
    the expensive one."""
    assert _line_cost(
        _ing(None, 2, "sticks"), UnitPrice(0.004, "g"),
    ) is None


# ── Counted ingredients ───────────────────────────────────────────────────


def test__line_cost__ACountedItem__UsesThePerItemPrice():
    assert _line_cost(
        _ing("Eggs", 3, None), UnitPrice(0.60, "ea", pack_amount=0.50),
    ) == pytest.approx(1.50)


def test__line_cost__ADozen__IsTwelveItems():
    assert _line_cost(
        _ing("Eggs", 1, "dozen"), UnitPrice(0.60, "ea", pack_amount=0.50),
    ) == pytest.approx(6.00)


def test__line_cost__AMeasuredPackCountedByItem__StaysUnpriced():
    """`pack_amount` is None when nothing says how many items are in the pack —
    the $16.50 egg-yolk rule, from the other side."""
    assert _line_cost(_ing("Eggs", 3, None), UnitPrice(0.0079, "g")) is None


# ── No quantity at all ────────────────────────────────────────────────────


def test__cost_one__IngredientWithNoAmount__IsUnpricedNotBilledAsOne():
    """"Salt to taste" against a $2.50 jar used to add $2.50 to the recipe and
    count itself as one of the priced ingredients."""
    salt = _ing("Sea Salt", None, None)
    prices = {uuid_key("item-1"): UnitPrice(2.50, "ea", pack_amount=2.50)}

    estimate = _cost_one([salt], prices, {})

    assert estimate.estimated_cost is None
    assert estimate.priced_count == 0
    assert estimate.lines[0].reason == UNPRICED_NO_QUANTITY
    # The price is still shown: only the amount is missing, and the reader can
    # see the pantry item is priced.
    assert estimate.lines[0].unit_price == pytest.approx(2.50)


def test__cost_one__QuantifiedNeighbours__AreUnaffected():
    lines = [_ing("Sea Salt", None, None), _ing("Eggs", 2, None, "item-2")]
    prices = {
        uuid_key("item-1"): UnitPrice(2.50, "ea", pack_amount=2.50),
        uuid_key("item-2"): UnitPrice(0.60, "ea", pack_amount=0.60),
    }

    estimate = _cost_one(lines, prices, {})

    assert estimate.estimated_cost == pytest.approx(1.20)
    assert estimate.priced_count == 1
    assert estimate.total_count == 2


# ── Sub-item units: a part of a shelf item, never the item (FU-904) ───────


def test__line_cost__ClovesOfGarlic__AreNotWholeBulbs():
    """The measured defect: three cloves came to $3.60 against a $1.20 bulb."""
    assert _line_cost(
        _ing("Garlic", 3, "cloves"), UnitPrice(1.20, "ea", pack_amount=1.20),
    ) is None


def test__line_cost__SprigsAndRashersAndSlices__AreTheSameShape():
    per_item = UnitPrice(2.50, "ea", pack_amount=2.50)
    assert _line_cost(_ing("Tarragon", 2, "sprigs"), per_item) is None
    assert _line_cost(_ing("Streaky Bacon", 4, "rashers"), per_item) is None
    assert _line_cost(_ing("Sourdough", 2, "slices"), per_item) is None


def test__line_cost__AVagueAmount__IsNotAWholeProduct():
    """"A knob of butter" is not a block of butter."""
    assert _line_cost(
        _ing("Salted Butter", 1, "knob"), UnitPrice(6.50, "ea", pack_amount=6.50),
    ) is None


def test__line_cost__TinsAreStillCounted():
    """The permissive branch survives for the case that motivated it — a tin
    *is* the shelf item, and this must not become collateral damage."""
    assert _line_cost(
        _ing("Tinned Tomatoes", 2, "tins"), UnitPrice(1.40, "ea", pack_amount=1.40),
    ) == pytest.approx(2.80)


def test__line_cost__ClovesAgainstAPerWeightPrice__ArePricedFromTheirWeight():
    """Better than refusing: the portion row knows a clove is 3 g, so three of
    them against a $20/kg price is 6c rather than nothing."""
    assert _line_cost(
        _ing("Garlic", 3, "cloves"), UnitPrice(0.02, "g"),
        [_Portion(1, "clove", 3.0)],
    ) == pytest.approx(9.0 * 0.02)


# ── Weighing a counted ingredient from its portion row (FU-905) ───────────


def test__line_cost__CountedIngredientWithNoPerItemPrice__IsWeighed():
    """"2 leeks" against $6.90/kg: unpriced until the cost path could read the
    same portion rows the nutrition panel weighs with."""
    assert _line_cost(
        _ing("Leeks", 2, "whole"), UnitPrice(0.0069, "g"),
        [_Portion(1, "medium", 89.0)],
    ) == pytest.approx(178.0 * 0.0069)


def test__line_cost__AMeasuredPortion__BeatsTheModelledDensity():
    """The precedence `household_measures` exists to state once. A cup of flour
    is 132.5 g by density (250 ml × 0.53) and 125 g by the dataset's own row;
    the row wins, which is also what the nutrition panel shows."""
    with_row = _line_cost(
        _ing("Plain Flour", 1, "cup"), UnitPrice(0.0018, "g"),
        [_Portion(1, "cup", 125.0)],
    )
    without_row = _line_cost(_ing("Plain Flour", 1, "cup"), UnitPrice(0.0018, "g"))

    assert with_row == pytest.approx(125.0 * 0.0018)
    assert without_row == pytest.approx(132.5 * 0.0018)


def test__line_cost__SticksOfCeleryWithAStalkRow__ArePricedProperly():
    """The end of the `stick` story: refused when nothing knows better, and
    correct when the food's own row does."""
    assert _line_cost(
        _ing("Celery", 2, "sticks"), UnitPrice(0.004, "g"),
        [_Portion(1, "stalk, medium", 40.0)],
    ) == pytest.approx(80.0 * 0.004)


def test__line_cost__GramsAgainstAPerItemPrice__StayUnpriced():
    """Weight can't answer "what does one cost" — the $16.50 rule, unchanged by
    the new weighing path."""
    assert _line_cost(
        _ing("Leeks", 2, "whole"), UnitPrice(2.00, "ea"),
        [_Portion(1, "medium", 89.0)],
    ) is None


def test__line_cost__NoPortionRows__BehavesExactlyAsBefore():
    """An install with no nutrition dataset imported gets `{}` and every path
    falls back — the new capability degrades to the old behaviour."""
    assert _line_cost(_ing("Leeks", 2, "whole"), UnitPrice(0.0069, "g"), []) is None
    assert _line_cost(
        _ing("Chicken Thighs", 800, "g"), UnitPrice(0.011, "g"), [],
    ) == pytest.approx(8.80)


# ── Why a line is unpriced (FU-875) ───────────────────────────────────────


@pytest.mark.parametrize("ingredient, price, reason", [
    (_ing("Eggs", 3, None), UnitPrice(0.0079, "g"), UNPRICED_UNIT_NO_PACK_COUNT),
    (_ing("Eggs", 3, "yolks"), UnitPrice(0.0079, "g"), UNPRICED_UNIT_NO_PACK_COUNT),
    (_ing("Rice", 250, "g"), UnitPrice(4.00, "ea"), UNPRICED_UNIT_NO_PACK_SIZE),
    (_ing("Dijon Mustard", 2, "tsp"), UnitPrice(0.019, "g"), UNPRICED_UNIT_UNKNOWN_DENSITY),
    (_ing("Celery", 2, "sticks"), UnitPrice(0.004, "g"), UNPRICED_UNIT_WRONG_FOOD),
    (_ing("Garlic", 3, "cloves"), UnitPrice(1.00, "ea"), UNPRICED_UNIT_MISMATCH),
])
def test__price_line__NamesTheGap(ingredient, price, reason):
    assert _price_line(ingredient, price) == (None, reason)


def test__price_line__APricedLine__HasNoReason():
    cost, reason = _price_line(_ing("Chicken Thighs", 800, "g"), UnitPrice(0.011, "g"))
    assert cost == pytest.approx(8.80)
    assert reason is None
