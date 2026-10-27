"""Server-owned recipe cost estimation (R-003 — one definition of "what a
recipe costs", never duplicated on the client or across features).

Extracted from `get_recipes._compute_estimated_cost` (C-4 Chunk 9 / DEC-5) so
both the recipe-detail endpoint and the FU-451 budget-defense swap ranker
price recipes the same way. The single-recipe path preserves the original
behaviour exactly; the batch path prices many recipes in **two queries total**
(one offer lookup, one observation fallback) rather than 2×N — important for
the swap ranker, which costs the whole candidate pool at once.

Pricing ladder per ingredient (PROPOSAL §3.2):
  1. cheapest linked-product current offer → unit price (price_now / size_value)
  2. else the stock item's price-observation unit cost (FU-216 substrate)
  3. else unpriced (contributes nothing; surfaced via the priced/total ratio)

**Counting the contents of a measured pack (feedback 2026-09-03).** The same
category error survived on the counted side. `pack_amount` — the price used
when a recipe says "2 tins" or a bare "3" — was set to the offer price for
*every* product, including one whose size is a mass or a volume. So "3 yolks"
of an ingredient linked to *Free Range Eggs 700 g @ $5.50* priced as three
whole 700 g cartons: **$16.50**, off a shelf price of $7.86/kg, which is the
owner's report. A measured pack does not say how many countable things are
inside it — nobody recorded what one egg weighs — so a bare count can no
longer be priced from one. Where the count *is* recorded the answer is better
than it was: `pack_count` ("4 × 125 g") and a count-dimension size ("12 ea")
both give a genuine per-item price, and a `dozen` is divided by twelve rather
than sold whole. Everything else is reported unpriced.

**Unit reconciliation (feedback 2026-08-19).** It used to be pass-through —
the ingredient quantity was multiplied by the unit price whatever the two
units were. That is not a rough heuristic, it's a category error: a price of
"$4.20 per bottle" times "200 ml" produced $840, and the seed's two-ingredient
Juice Bowl reported **$1590**. Every price now carries the unit it is per, the
ingredient quantity is converted into that unit, and an ingredient whose units
can't bridge (200 ml of a thing priced per bottle — we don't know the bottle's
size) is reported **unpriced** rather than guessed at. Unpriced ingredients
already have a home in the UI: the "N of M priced" ratio. An honest gap beats
a confident wrong number.
"""
from dataclasses import dataclass
from typing import Iterable

from dora_api.domain import units
from dora_api.domain.entities.stock_item_price_observation import \
    StockItemPriceObservation
from dora_api.domain.stock_status import \
    get_stock_item_unit_cost_with_unit_at
from dora_api.features.nutrition.household_measures import (
    portions_by_stock_item,
    resolve_grams,
)
from dora_api.persistence.field import EntityField
from dora_api.persistence.uuid_key import uuid_key

# Why an ingredient contributed nothing — surfaced per line in the recipe
# page's expandable cost breakdown, so "why is this estimate low?" is
# answerable without reading the code.
UNPRICED_NO_LINK = "no_link"            # ingredient isn't linked to a stock item
UNPRICED_NO_PRICE = "no_price"          # linked, but no offer and no observation
# Priced, but the ingredient's amount can't be turned into that price. Split
# by cause (FU-875) so the breakdown can say which gap it is; the bare
# `unit_mismatch` remains for a pair none of the specific reasons explain.
UNPRICED_UNIT_MISMATCH = "unit_mismatch"
UNPRICED_UNIT_NO_PACK_COUNT = "unit_no_pack_count"  # "3" of a pack sold by weight
UNPRICED_UNIT_NO_PACK_SIZE = "unit_no_pack_size"    # "250 g" of a pack priced per item
UNPRICED_UNIT_UNKNOWN_DENSITY = "unit_unknown_density"  # cups vs kg, density unknown
UNPRICED_UNIT_WRONG_FOOD = "unit_wrong_food"        # "2 sticks" of something not butter
# "Salt to taste", "oil for frying" — an ingredient with no amount on it. It
# used to default to a quantity of 1, which against a per-item price billed a
# whole jar of salt and counted the line as *priced*, flattering the coverage
# ratio as well as the total. The nutrition rollup has always had this reason
# (`REASON_NO_QUANTITY`); costing was missing its half (owner 2026-09-09).
UNPRICED_NO_QUANTITY = "no_quantity"


@dataclass(frozen=True, slots=True)
class UnitPrice:
    """A price and the unit it is *per*. The unit is the half that used to be
    dropped on the floor.

    `pack_amount` is the price of one **countable item** where that is known
    (see `_item_price`) — a 12-egg carton at $6.00 has `amount` per egg-less
    unit of measure **and** `pack_amount=0.50`. Recipes are written both ways
    ("400 g of tomatoes", "2 tins of tomatoes") and only one of the two prices
    can answer each. It is `None` when the pack is measured rather than
    counted, because then nothing in the data says how many items are in it —
    that is a gap we report, not one we fill in.
    """
    amount: float
    unit: str
    pack_amount: float | None = None


@dataclass(frozen=True, slots=True)
class CostLine:
    """One ingredient's contribution, for the breakdown UI. `line_cost` is
    None exactly when `reason` is set."""
    name: str
    quantity: float | None
    unit: str | None
    unit_price: float | None
    priced_unit: str | None
    line_cost: float | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class CostEstimate:
    """Per-recipe result. `estimated_cost` is None when nothing priced."""
    estimated_cost: float | None
    priced_count: int
    total_count: int
    lines: tuple[CostLine, ...] = ()


def _item_price(
    pack_price: float,
    size_value: float | None,
    size_unit: str | None,
    pack_count: int | None,
) -> float | None:
    """The price of **one countable item**, or None when that isn't knowable.

    This is the half of a price a *counted* ingredient needs ("2 tins", "3",
    "1 onion"), and it is not the same number as the shelf price. Three ways
    it is knowable, and one way it isn't:

    * an explicit multipack count ("4 x 125 g at $4.20") - divide by it;
    * a sizeless product - the shelf item is the item;
    * a size expressed as a count ("12 ea", "1 dozen") - divide by the total
      count, remembering that a `dozen` is twelve of them;
    * a size expressed as a mass or a volume with no pack count - **unknown**.
      "700 g of eggs" answers "what does 200 g cost?" and says nothing at all
      about what three of them cost. Guessing here is what charged $16.50 for
      three egg yolks (owner, 2026-09-03).
    """
    if pack_count is not None and pack_count > 0:
        return pack_price / float(pack_count)
    if not (size_value and float(size_value) > 0 and size_unit):
        return pack_price
    found = units.find_unit(str(size_unit))
    if found is None or found.dimension != units.COUNT:
        return None
    return pack_price / (float(size_value) * found.factor)


def _unit_price_map(repository, stock_item_ids: list) -> tuple[dict, dict]:
    """(offer_unit_price_by_item, observation_unit_cost_by_item) keyed by the
    stringified stock-item id. One offer query + one observation query."""
    from sqlalchemy import func, select
    from dora_api.app import db

    if not stock_item_ids:
        return {}, {}

    link_table = db.metadata.tables["StockItemProduct"]
    product_table = db.metadata.tables["Product"]
    offer_table = db.metadata.tables["ProductOffer"]

    stmt = (
        select(
            link_table.c.stock_item_id,
            product_table.c.size_value,
            product_table.c.size_unit,
            product_table.c.pack_count,
            func.min(offer_table.c.price_now).label("price_now"),
        )
        .select_from(
            link_table
            .join(product_table, product_table.c.id == link_table.c.product_id)
            .join(offer_table, offer_table.c.product_id == product_table.c.id)
        )
        .where(
            link_table.c.stock_item_id.in_(stock_item_ids),
            product_table.c.is_active.is_(True),
            offer_table.c.price_now.isnot(None),
        )
        .group_by(
            link_table.c.stock_item_id,
            product_table.c.size_value,
            product_table.c.size_unit,
            product_table.c.pack_count,
        )
    )
    offer_by_item: dict[str, UnitPrice] = {}
    for sid, size_value, size_unit, pack_count, price in db.session.execute(stmt).all():
        if price is None:
            continue
        # A sized product prices per its own size unit ("$5 / 1000 g" → $/g);
        # a sizeless one prices per item, which is a count of "ea".
        #
        # The *item* price is a separate question, and the answer used to be
        # "the shelf price, always" — which silently claimed that one pack
        # holds one countable thing. True of a tin, false of a 700 g carton of
        # eggs, and the recipe page charged $16.50 for three yolks on the
        # strength of it. `_item_price` answers it honestly or not at all,
        # which is the same stance the observation branch below already took.
        if size_value and float(size_value) > 0 and size_unit:
            amount = float(price) / float(size_value)
            unit = str(size_unit)
        else:
            amount, unit = float(price), "ea"
        unit_price = UnitPrice(
            amount, unit, _item_price(float(price), size_value, size_unit, pack_count),
        )
        prev = offer_by_item.get(uuid_key(sid))
        if prev is None or _cheaper(unit_price, prev):
            offer_by_item[uuid_key(sid)] = unit_price

    # Observation fallback: one query, grouped per item, delegated to the
    # server-owned per-unit cost helper (R-003).
    obs_by_item: dict[str, list] = {}
    for obs in repository.get(StockItemPriceObservation).all(
        EntityField(StockItemPriceObservation, "stock_item_id").in_(stock_item_ids)
    ):
        obs_by_item.setdefault(uuid_key(obs.stock_item_id), []).append(obs)
    obs_cost_by_item: dict[str, UnitPrice] = {}
    for sid_key, obs_list in obs_by_item.items():
        cost = get_stock_item_unit_cost_with_unit_at(obs_list)
        if cost is None:
            continue
        # A count observation ("$9 for 3 punnets") already *is* a per-item
        # price. A measure observation ("$6 for 4 L") spans an unknown number
        # of packs, so it can't yield one, unless the user recorded the pack
        # count with it ("$5.50 for 12 eggs, 700 g"; FU-856).
        found = units.find_unit(cost.unit)
        # `/ factor` for the same reason `_item_price` divides: "$60 per dozen"
        # is a per-item price of $5, not $60.
        pack = (cost.amount / found.factor
                if found is not None and found.dimension == units.COUNT
                else cost.item_price)
        obs_cost_by_item[sid_key] = UnitPrice(cost.amount, cost.unit, pack)

    return offer_by_item, obs_cost_by_item


def _cheaper(candidate: UnitPrice, incumbent: UnitPrice) -> bool:
    """Is *candidate* the better price? Only comparable within one dimension —
    "$0.004 per g" and "$2.50 per ea" are not two numbers on the same scale, so
    when the dimensions differ (or a unit is unrecognised) the incumbent stands
    and the choice stays deterministic rather than arbitrary."""
    src = units.find_unit(candidate.unit)
    dst = units.find_unit(incumbent.unit)
    if src is None or dst is None or src.dimension != dst.dimension:
        return False
    # Normalise both to the dimension's base unit before comparing.
    return (candidate.amount / src.factor) < (incumbent.amount / dst.factor)


def _line_cost(ingredient, price: UnitPrice, portions: list | None = None) -> float | None:
    """What this ingredient contributes, or None when it can't be priced."""
    return _price_line(ingredient, price, portions)[0]


def _price_line(
    ingredient, price: UnitPrice, portions: list | None = None,
) -> tuple[float | None, str | None]:
    """``(cost, None)``, or ``(None, reason)`` naming why it can't be priced.

    Recipes measure ingredients two different ways and each needs a different
    half of the price:

    * **By measure** — "400 g of tomatoes", "2 cups of juice". Convert the
      quantity into the unit the price is per, then multiply. A conversion
      that can't bridge dimensions (200 ml of a thing priced per bottle: we
      don't know the bottle's size) is **unpriced**. Guessing here is what
      produced the $1590 Juice Bowl.
      Mass↔volume is the one cross-dimension bridge, and it needs to know
      *what* is being converted — 250 ml of oil and 250 ml of honey are 50 g
      apart. The ingredient's name is passed for that (FU-874): until
      2026-09-09 it was omitted, so `units.convert` refused every mass-vs-volume
      pair and a recipe measured in cups against a product priced per kilo read
      as unpriced no matter how well the density table knew the ingredient.
      This does not soften ADR-073 — an ingredient the table doesn't list still
      returns None and is still reported unpriced.
    * **By the item** — "2 tins", "1 onion", or a bare "2". Multiply by the
      price of one countable item. Permissive about the unit itself: "tins"
      isn't a unit we know and doesn't need to be, because the count is all the
      arithmetic needs. But the *price* side has to be a real per-item figure —
      a pack measured in grams doesn't say how many items are in it, so that
      combination is **unpriced** rather than billed as whole packs (feedback
      2026-09-03; see `_item_price`).
      Two exceptions, both added 2026-09-09 after driving a real recipe through
      this function. `units.SUB_ITEM_UNITS` names the words that mean a *part*
      of a shelf item — "3 cloves" was being billed as three whole bulbs
      (FU-904) — and those are never counted. And a counted ingredient with no
      per-item price can still be priced from its **weight**, when the pantry
      knows what one of them weighs.

    `portions` is that last piece: the linked food's measured household
    measures, when the caller has them. With them, "2 leeks" against a per-kilo
    price is 178 g rather than unpriced, and one cup of flour weighs the same
    here as it does on the nutrition panel (FU-905). Without them — no dataset
    imported, no food linked — every path falls back to exactly what it did
    before.
    """
    # `_cost_one` refuses a quantity-less ingredient before it gets here
    # (UNPRICED_NO_QUANTITY); the 1.0 remains only for the direct callers in
    # the tests, and is never how a real line is billed.
    qty = float(ingredient.quantity) if ingredient.quantity is not None else 1.0
    ing_unit = (ingredient.unit or "").strip()
    ing_def = units.find_unit(ing_unit) if ing_unit else None

    name = ingredient.stock_item_name
    names = [n for n in (name,) if n]

    def by_weight() -> float | None:
        """Price this line through its weight in grams. Only meaningful when
        the price is per mass — grams say nothing about what one of something
        costs when the shelf price is per item or per litre."""
        price_def = units.find_unit(price.unit)
        if price_def is None or price_def.dimension != units.MASS:
            return None
        grams = resolve_grams(qty, ing_unit or None, portions or [], names)
        if grams is None:
            return None
        in_price_unit = units.convert(grams, "g", price.unit)
        return None if in_price_unit is None else in_price_unit * price.amount

    def weighed_or(reason: str) -> tuple[float | None, str | None]:
        cost = by_weight()
        return (cost, None) if cost is not None else (None, reason)

    # A part of a shelf item, never the item. Weight is the only honest route.
    if units.is_sub_item_unit(ing_unit):
        return weighed_or(UNPRICED_UNIT_MISMATCH)

    measured = ing_def is not None and ing_def.dimension != units.COUNT
    if measured:
        # "2 sticks" is 226 g of butter or two stalks of celery, and the table
        # only knows the first. Billing celery at butter's weight is the same
        # class of error as the $16.50 egg yolks, so an ingredient this unit
        # doesn't belong to is unpriced rather than over-billed — unless a
        # portion row can say what this food's stick actually weighs.
        if not units.food_specific_mass_applies(ing_unit, name):
            return weighed_or(UNPRICED_UNIT_WRONG_FOOD)
        if units.normalise_unit(ing_unit) == units.normalise_unit(price.unit):
            return qty * price.amount, None
        # Weight first when the price is per mass: a measured portion row beats
        # the modelled density, and `resolve_grams` owns that precedence so the
        # cost breakdown and the nutrition panel can't disagree about a cup.
        weighed = by_weight()
        if weighed is not None:
            return weighed, None
        converted = units.convert(qty, ing_unit, price.unit, ingredient=name)
        if converted is not None:
            return converted * price.amount, None
        return None, _measured_gap(ing_def, price)

    # Counted (no unit, an unrecognised unit, or an explicit count unit).
    if ing_def is not None and ing_def.dimension == units.COUNT:
        qty *= ing_def.factor          # "1 dozen" is twelve items
    if price.pack_amount is not None:
        return qty * price.pack_amount, None
    # No per-item price. "2 leeks" against $6.90/kg used to stop here; if the
    # pantry knows a leek is 89 g, it doesn't have to.
    return weighed_or(UNPRICED_UNIT_NO_PACK_COUNT)


def _measured_gap(ing_def, price: UnitPrice) -> str:
    """Why a measured amount ("250 g", "2 cups") didn't convert to the price."""
    price_def = units.find_unit(price.unit)
    if price_def is None:
        return UNPRICED_UNIT_MISMATCH
    if price_def.dimension == units.COUNT:
        return UNPRICED_UNIT_NO_PACK_SIZE
    if {ing_def.dimension, price_def.dimension} == {units.MASS, units.VOLUME}:
        return UNPRICED_UNIT_UNKNOWN_DENSITY
    return UNPRICED_UNIT_MISMATCH


def _line_name(ingredient) -> str:
    """Display name for the breakdown. The batch path is fed entities that
    may not carry the joined stock-item name; the detail path is fed DTOs
    that always do."""
    return ingredient.stock_item_name or "Ingredient"


def _unpriced_line(ingredient, reason: str, price: UnitPrice | None) -> CostLine:
    return CostLine(
        name=_line_name(ingredient),
        quantity=float(ingredient.quantity) if ingredient.quantity is not None else None,
        unit=ingredient.unit,
        unit_price=price.amount if price is not None else None,
        priced_unit=price.unit if price is not None else None,
        line_cost=None,
        reason=reason,
    )


def _cost_one(
    ingredients,
    offer_by_item: dict,
    obs_cost_by_item: dict,
    portions_by_item: dict | None = None,
) -> CostEstimate:
    total = 0.0
    priced = 0
    lines: list[CostLine] = []
    for ing in ingredients:
        if ing.stock_item_id is None:
            lines.append(_unpriced_line(ing, UNPRICED_NO_LINK, None))
            continue
        sid = uuid_key(ing.stock_item_id)
        unit_price = offer_by_item.get(sid) or obs_cost_by_item.get(sid)
        if unit_price is None:
            lines.append(_unpriced_line(ing, UNPRICED_NO_PRICE, None))
            continue
        # Checked after the price so the row still shows what the ingredient
        # costs per unit — the reader can see the price exists and that only
        # the amount is missing.
        if ing.quantity is None:
            lines.append(_unpriced_line(ing, UNPRICED_NO_QUANTITY, unit_price))
            continue
        line_cost, reason = _price_line(
            ing, unit_price, (portions_by_item or {}).get(ing.stock_item_id))
        if line_cost is None:
            lines.append(_unpriced_line(ing, reason, unit_price))
            continue
        total += line_cost
        priced += 1
        lines.append(CostLine(
            name=_line_name(ing),
            quantity=float(ing.quantity) if ing.quantity is not None else None,
            unit=ing.unit,
            unit_price=unit_price.amount,
            priced_unit=unit_price.unit,
            line_cost=round(line_cost, 2),
            reason=None,
        ))

    linked_count = sum(1 for i in ingredients if i.stock_item_id is not None)
    return CostEstimate(
        estimated_cost=round(total, 2) if priced > 0 else None,
        priced_count=priced,
        total_count=linked_count,
        lines=tuple(lines),
    )


def estimate_costs_for(repository, recipes: Iterable) -> dict:
    """Batch: `recipe_id (UUID) → CostEstimate` for every recipe passed. Each
    recipe must expose `.recipe_id` and `.ingredients` (each ingredient with
    `.stock_item_id` and `.quantity`). Four queries total — two for the prices,
    two for the household measures that weigh a counted or volume ingredient
    (FU-905). All four are batched over the whole page; none scales with the
    recipe count, which is what `test_recipes_query_count` pins."""
    recipes = list(recipes)
    all_ids: list = []
    for r in recipes:
        for ing in (r.ingredients or []):
            if ing.stock_item_id is not None:
                all_ids.append(ing.stock_item_id)
    offer_by_item, obs_cost_by_item = _unit_price_map(repository, all_ids)
    portions_by_item = portions_by_stock_item(repository, all_ids)
    return {
        r.recipe_id: _cost_one(
            r.ingredients or [], offer_by_item, obs_cost_by_item, portions_by_item)
        for r in recipes
    }


def estimate_cost_for_ingredients(repository, ingredients) -> CostEstimate:
    """Single-recipe path used by the recipe-detail endpoint. `ingredients`
    is a list with `.stock_item_id` + `.quantity`."""
    ingredients = list(ingredients)
    ids = [i.stock_item_id for i in ingredients if i.stock_item_id is not None]
    offer_by_item, obs_cost_by_item = _unit_price_map(repository, ids)
    portions_by_item = portions_by_stock_item(repository, ids)
    # total_count preserves the original behaviour: it counted *all* dto
    # ingredients (the detail endpoint only ever passes linked-or-null rows and
    # reported len(ingredients)); keep that contract for the caller.
    est = _cost_one(ingredients, offer_by_item, obs_cost_by_item, portions_by_item)
    return CostEstimate(
        estimated_cost=est.estimated_cost,
        priced_count=est.priced_count,
        total_count=len(ingredients),
        lines=est.lines,
    )
