"""Canonical unit-conversion authority (FU-227 chunk 1).

The single server-side source of truth for measurement units, their aliases,
conversion factors, ingredient densities, and the gas-mark scale. Was inlined
in ``features/assistant/tools.py`` until the pricing reassessment exposed it
as a domain concept the price-entry widget, the harvest path, and the
assistant tool all need.

Six dimensions: ``volume`` (base ``ml``), ``mass`` (base ``g``), ``count``
(base ``ea`` — new per B1 for sizeless price entry), ``temperature`` (base
``°C``, handled with offsets out-of-band), ``length`` (base ``mm``),
``energy`` (base ``kJ``).

R-003: this module owns the table; nothing else may declare a unit factor or
density. The SPA mirror at ``web_app/src/generated/units_table.ts`` is
codegen'd from this file via ``scripts/dump_units.py`` — never hand-edited.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any


# ── Dimensions ────────────────────────────────────────────────────────────

VOLUME = "volume"
MASS = "mass"
COUNT = "count"             # sizeless ("ea", "pack", "dozen").
TEMPERATURE = "temperature"
LENGTH = "length"
ENERGY = "energy"

# The dimensions a price observation may be expressed in. Volume + mass cover
# weighed/measured goods; count covers the sizeless "$9 for 3 punnets" case.
# Temperature/length/energy are recipe-side only and never appear on a price
# row (a charter call — observations are price records, not recipe records).
PRICE_DIMENSIONS = frozenset({VOLUME, MASS, COUNT})


# the **compute** denominator per dimension. Baseline math
# (`your_prices.py`) normalises every observation into one of these before
# computing the median, so the median is comparable across observations
# logged in different aliases (e.g. "L" + "ml" both land on "L"). The
# user-facing denominator may differ — see `display_denominator_for` below.
CANONICAL_PRICE_UNIT: dict[str, str] = {
    VOLUME: "L",
    MASS: "kg",
    COUNT: "ea",
}


# ── Measurement system ────────────────────────────────────────────────────
#
# The install-wide answer to "which units does this household actually use?".
# Owner feedback 2026-08-27: *"Locale and region settings should also include
# units config, which then determines what units appear throughout the app …
# for universal ones, e.g. 'dash', always include those."*
#
# Three systems, and they are not three disjoint sets:
#
#   ``metric``    ml/L, g/kg, the 250 ml cup and 20 ml tablespoon (AU/NZ).
#   ``us``        fl oz/qt/gal, oz/lb, the 240 ml US cup and 14.8 ml US tbsp.
#   ``imperial``  the UK reality: metric core for weights and volumes (that is
#                 how UK shelves and recipes are labelled) *plus* oz/lb, fl oz
#                 and the 568 ml imperial pint.
#
# `UNIT_SYSTEMS` is keyed by **canonical** form, not by alias — one row per
# real unit, ~35 rows instead of ~150. It is the only place the mapping lives
# (R-003); `units_for_system()` is the only reader, and the SPA gets it via the
# generated mirror rather than restating it.
METRIC = "metric"
IMPERIAL = "imperial"
US_CUSTOMARY = "us"

SUPPORTED_MEASUREMENT_SYSTEMS: frozenset[str] = frozenset({
    METRIC, IMPERIAL, US_CUSTOMARY,
})

# Units that belong to no system because they belong to all of them: the
# informal cooking amounts, the count units, and energy (a nutrition label is
# not a measurement system). Always offered, whatever the install picks.
UNIVERSAL_CANONICAL_UNITS: frozenset[str] = frozenset({
    "smidgen", "pinch", "dash",
    # 5 ml here, 4.93 ml in the US, 5.9 ml in the UK — nobody measures a
    # teaspoon to 2%. One row, offered everywhere.
    "tsp",
    "ea", "pack", "dozen", "whole",
    "kJ", "kcal", "J",
})

UNIT_SYSTEMS: dict[str, frozenset[str]] = {
    # volume
    "ml":       frozenset({METRIC, IMPERIAL}),
    "L":        frozenset({METRIC, IMPERIAL}),
    "tbsp":     frozenset({METRIC, IMPERIAL}),
    "cup":      frozenset({METRIC, IMPERIAL}),
    "US tbsp":  frozenset({US_CUSTOMARY}),
    "US cup":   frozenset({US_CUSTOMARY}),
    "fl oz":    frozenset({IMPERIAL, US_CUSTOMARY}),
    "pt":       frozenset({IMPERIAL}),           # 568 ml — UK, not the US pint
    "qt":       frozenset({US_CUSTOMARY}),
    "gal":      frozenset({US_CUSTOMARY}),
    # mass
    "mg":       frozenset({METRIC, IMPERIAL}),
    "g":        frozenset({METRIC, IMPERIAL}),
    "kg":       frozenset({METRIC, IMPERIAL}),
    "oz":       frozenset({IMPERIAL, US_CUSTOMARY}),
    "lb":       frozenset({IMPERIAL, US_CUSTOMARY}),
    "stick":    frozenset({US_CUSTOMARY}),       # butter, a US supermarket fact
    # length — recipe metadata (tin sizes), not quantities
    "mm":       frozenset({METRIC, IMPERIAL}),
    "cm":       frozenset({METRIC, IMPERIAL}),
    "m":        frozenset({METRIC, IMPERIAL}),
    "in":       frozenset({IMPERIAL, US_CUSTOMARY}),
    "ft":       frozenset({IMPERIAL, US_CUSTOMARY}),
}


def units_for_system(system: str) -> frozenset[str]:
    """Canonical units offered by pickers under *system*.

    Universal units are always included. An unrecognised system falls back to
    metric rather than raising — a bad value in one setting must not empty
    every unit dropdown in the app.
    """
    resolved = system if system in SUPPORTED_MEASUREMENT_SYSTEMS else METRIC
    return frozenset(
        UNIVERSAL_CANONICAL_UNITS
        | {c for c, systems in UNIT_SYSTEMS.items() if resolved in systems}
    )


def pricing_convention_for(system: str) -> str:
    """Which shelf-pricing convention *system* implies: ``"US"`` or ``"AU"``.

    Only the US prices by the quart and the pound. The UK sells in metric by
    law and displays ``/100g`` and ``/L`` exactly as Australia does, so
    ``imperial`` maps to the AU convention — the imperial units it keeps are
    for cooking, not for shelf labels.
    """
    return "US" if system == US_CUSTOMARY else "AU"


def display_denominator_for(
    active_dim: str,
    latest_measure_in_canonical: float,
    *,
    system: str = METRIC,
) -> tuple[str, float]:
    """The shelf display convention for a per-unit price.

    Returns ``(label, divide_factor)``: the user-facing denominator the
    widget renders (e.g. ``"L"`` / ``"100ml"`` for AU; ``"qt"`` / ``"fl oz"``
    for US) and the number by which a price computed in the dimension's
    :data:`CANONICAL_PRICE_UNIT` (compute unit) must be divided to land in
    that denominator.

    AU is fixed: always ``/100g`` and ``/100ml``, whatever the pack size, so
    a 500 g and a 2 kg pack of the same thing quote in the same unit and can be
    compared at a glance (owner, FU-914). US stays size-aware: the flip kicks in
    once the latest observation reaches a full target unit (≥ 1 qt / ≥ 1 lb),
    and below that the smaller denominator reads more naturally ("$0.50 / fl oz"
    vs "$16.00 / qt"). Count stays "ea" (no fractional convention either way).

    The system is resolved server-side from ``AppSetting.measurement_system``
    — single source so the chart axis, sidecar entries, widget headline, and
    chart points all share one denominator, and so the units a picker offers
    and the denominator a price is quoted in can never disagree. (This used to
    be its own ``unit_pricing_locale`` setting on an AU/US axis, which was a
    second name for the same fact and was never exposed in the UI at all.)
    Compute math is system-independent; only the rendered denominator changes.
    """
    if active_dim == COUNT:
        return (COUNT_DENOMINATOR.label, COUNT_DENOMINATOR.factor)
    rule = PRICE_DISPLAY_RULES[pricing_convention_for(system)][active_dim]
    flips = rule.flip_at is not None and latest_measure_in_canonical >= rule.flip_at
    chosen = rule.full if flips else rule.sub
    return (chosen.label, chosen.factor)


@dataclass(frozen=True, slots=True)
class DisplayDenominator:
    """One shelf denominator: what it is called, and the number a price in the
    dimension's :data:`CANONICAL_PRICE_UNIT` is divided by to land in it."""
    label: str
    factor: float


@dataclass(frozen=True, slots=True)
class DenominatorRule:
    """The pair of denominators one convention uses for one dimension, and the
    pack size (in the dimension's canonical unit) at which the larger one takes
    over. ``flip_at=None`` means it never does. Data rather than branches so `scripts/dump_units.py` can mirror the
    rule to the SPA instead of the client restating it (R-003) — the price-entry
    widget previews a denominator while you type, which can't round-trip."""
    full: DisplayDenominator
    sub: DisplayDenominator
    flip_at: float | None


# Count has no fractional convention either way, so it sits outside the table.
COUNT_DENOMINATOR = DisplayDenominator("ea", 1.0)

# US flip thresholds in the dimension's canonical unit:
#   1 qt = 0.946 L (volume canonical)
#   1 lb = 0.4536 kg (mass canonical)
# Divide factors precomputed from the conversion table so $/L → $/qt is
# `price / (qt-per-L)` = `price / 1.0567` ≈ `price × 0.946`.
_US_FLIP_QT_L = 0.946352946
_US_FLIP_LB_KG = 0.45359237

PRICE_DISPLAY_RULES: dict[str, dict[str, DenominatorRule]] = {
    # Fixed /100g and /100ml, the Australian shelf-tag unit (FU-914).
    "AU": {
        VOLUME: DenominatorRule(
            full=DisplayDenominator("L", 1.0),
            sub=DisplayDenominator("100ml", 10.0),
            flip_at=None,
        ),
        MASS: DenominatorRule(
            full=DisplayDenominator("kg", 1.0),
            sub=DisplayDenominator("100g", 10.0),
            flip_at=None,
        ),
    },
    "US": {
        VOLUME: DenominatorRule(
            full=DisplayDenominator("qt", 1.0 / _US_FLIP_QT_L),      # qt per L ≈ 1.0567
            sub=DisplayDenominator("fl oz", 1000.0 / 29.5735),        # fl oz per L ≈ 33.8140
            flip_at=_US_FLIP_QT_L,
        ),
        MASS: DenominatorRule(
            full=DisplayDenominator("lb", 1.0 / _US_FLIP_LB_KG),      # lb per kg ≈ 2.2046
            sub=DisplayDenominator("oz", 1000.0 / 28.3495),           # oz per kg ≈ 35.2740
            flip_at=_US_FLIP_LB_KG,
        ),
    },
}


# Practical price-entry picker whitelist. The conversion engine knows many
# more units (`cup` / `tsp` / `tbsp` / `pinch` / `dash` / `fl oz` / `pt` /
# `qt` / `gal` / `smidgen` / `stick`), but those are **cooking** units —
# nobody in AU buys oil by the cup or eggs by the pinch. The picker shows
# only what people actually shop in. The server still ACCEPTS the broader
# set (the harvest path may see a sized product in `cup` or `fl oz`), so
# this is purely a UI narrowing, not a validation tightening.
PRICE_PICKER_CANONICAL_UNITS: frozenset[str] = frozenset({
    # volume
    "ml", "L",
    # mass — practical AU + imperial for meat/cheese
    "g", "kg", "oz", "lb",
    # count
    "ea", "dozen", "pack",
})


# ── Unit table ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class UnitDef:
    """One row in :data:`UNIT_TABLE`. ``factor`` converts an amount in this
    unit to the dimension's base unit (ml / g / ea / mm / kJ; temperature is
    offset-based so its factor is the linear scale only)."""
    dimension: str
    factor: float
    canonical: str          # the preferred display alias for this unit


# Every alias keys an entry. ``canonical`` is the same string for every alias
# of a single unit so the SPA picker can group/dedupe. Aussie-metric defaults
# (250 ml cup, 20 ml tbsp); US cup/tbsp explicitly distinct.
UNIT_TABLE: dict[str, UnitDef] = {
    # ── Volume — base ml ──────────────────────────────────────────────
    "ml": UnitDef(VOLUME, 1.0, "ml"),
    "milliliter": UnitDef(VOLUME, 1.0, "ml"),
    "millilitre": UnitDef(VOLUME, 1.0, "ml"),
    "milliliters": UnitDef(VOLUME, 1.0, "ml"),
    "millilitres": UnitDef(VOLUME, 1.0, "ml"),
    "l": UnitDef(VOLUME, 1000.0, "L"),
    "litre": UnitDef(VOLUME, 1000.0, "L"),
    "liter": UnitDef(VOLUME, 1000.0, "L"),
    "litres": UnitDef(VOLUME, 1000.0, "L"),
    "liters": UnitDef(VOLUME, 1000.0, "L"),
    "smidgen": UnitDef(VOLUME, 0.156, "smidgen"),
    "smidge": UnitDef(VOLUME, 0.156, "smidgen"),
    "pinch": UnitDef(VOLUME, 0.3125, "pinch"),
    "pinches": UnitDef(VOLUME, 0.3125, "pinch"),
    "dash": UnitDef(VOLUME, 0.625, "dash"),
    "dashes": UnitDef(VOLUME, 0.625, "dash"),
    "tsp": UnitDef(VOLUME, 5.0, "tsp"),
    "teaspoon": UnitDef(VOLUME, 5.0, "tsp"),
    "teaspoons": UnitDef(VOLUME, 5.0, "tsp"),
    "tbsp": UnitDef(VOLUME, 20.0, "tbsp"),          # AU metric (20 ml)
    "tablespoon": UnitDef(VOLUME, 20.0, "tbsp"),
    "tablespoons": UnitDef(VOLUME, 20.0, "tbsp"),
    "us tbsp": UnitDef(VOLUME, 14.7868, "US tbsp"),
    "american tbsp": UnitDef(VOLUME, 14.7868, "US tbsp"),
    "us tablespoon": UnitDef(VOLUME, 14.7868, "US tbsp"),
    "cup": UnitDef(VOLUME, 250.0, "cup"),            # AU metric (250 ml)
    "cups": UnitDef(VOLUME, 250.0, "cup"),
    "us cup": UnitDef(VOLUME, 240.0, "US cup"),
    "us cups": UnitDef(VOLUME, 240.0, "US cup"),
    "american cup": UnitDef(VOLUME, 240.0, "US cup"),
    "american cups": UnitDef(VOLUME, 240.0, "US cup"),
    "fl oz": UnitDef(VOLUME, 29.5735, "fl oz"),
    "floz": UnitDef(VOLUME, 29.5735, "fl oz"),
    "fluid ounce": UnitDef(VOLUME, 29.5735, "fl oz"),
    "fluid ounces": UnitDef(VOLUME, 29.5735, "fl oz"),
    "pint": UnitDef(VOLUME, 568.261, "pt"),          # UK
    "pints": UnitDef(VOLUME, 568.261, "pt"),
    "pt": UnitDef(VOLUME, 568.261, "pt"),
    "quart": UnitDef(VOLUME, 946.353, "qt"),         # US
    "quarts": UnitDef(VOLUME, 946.353, "qt"),
    "qt": UnitDef(VOLUME, 946.353, "qt"),
    "gallon": UnitDef(VOLUME, 3785.41, "gal"),
    "gallons": UnitDef(VOLUME, 3785.41, "gal"),
    "gal": UnitDef(VOLUME, 3785.41, "gal"),

    # ── Mass — base g ─────────────────────────────────────────────────
    "mg": UnitDef(MASS, 0.001, "mg"),
    "milligram": UnitDef(MASS, 0.001, "mg"),
    "milligrams": UnitDef(MASS, 0.001, "mg"),
    "g": UnitDef(MASS, 1.0, "g"),
    "gm": UnitDef(MASS, 1.0, "g"),
    "gram": UnitDef(MASS, 1.0, "g"),
    "grams": UnitDef(MASS, 1.0, "g"),
    "kg": UnitDef(MASS, 1000.0, "kg"),
    "kilo": UnitDef(MASS, 1000.0, "kg"),
    "kilos": UnitDef(MASS, 1000.0, "kg"),
    "kilogram": UnitDef(MASS, 1000.0, "kg"),
    "kilograms": UnitDef(MASS, 1000.0, "kg"),
    "oz": UnitDef(MASS, 28.3495, "oz"),
    "ounce": UnitDef(MASS, 28.3495, "oz"),
    "ounces": UnitDef(MASS, 28.3495, "oz"),
    "lb": UnitDef(MASS, 453.592, "lb"),
    "lbs": UnitDef(MASS, 453.592, "lb"),
    "pound": UnitDef(MASS, 453.592, "lb"),
    "pounds": UnitDef(MASS, 453.592, "lb"),
    # 113 g is a stick *of butter*. See FOOD_SPECIFIC_MASS_UNITS below — the
    # figure is only meaningful for the foods listed there, and both recipe
    # calculators check that before trusting it.
    "stick": UnitDef(MASS, 113.0, "stick"),
    "sticks": UnitDef(MASS, 113.0, "stick"),

    # ── Count — base ea (new — B1, FU-227) ────────────────────────────
    # "pack" is a placeholder: long-term a pack is N items, but without a
    # per-product pack size we can't know N (see plan §7 / Risk). For now
    # a pack means "the thing the price is per" with factor 1, identical
    # to ea — explicit aliasing for UI clarity, not different math.
    "ea": UnitDef(COUNT, 1.0, "ea"),
    "each": UnitDef(COUNT, 1.0, "ea"),
    "unit": UnitDef(COUNT, 1.0, "ea"),
    "units": UnitDef(COUNT, 1.0, "ea"),
    # "1 whole onion" is a count, and was previously an *unknown* word — which
    # meant the nutrition rollup's count ladder (each/whole/medium/large/…)
    # never ran for it and only a portion row literally saying "whole" could
    # answer. "1 onion" weighed 110 g while "1 whole onion" weighed nothing
    # (owner 2026-09-09). Its own canonical rather than an "ea" alias: a recipe
    # that says whole means the ingredient uncut, and flattening that to "1 ea"
    # in the ingredient list would lose a word the cook reads.
    "whole": UnitDef(COUNT, 1.0, "whole"),
    "wholes": UnitDef(COUNT, 1.0, "whole"),
    "pack": UnitDef(COUNT, 1.0, "pack"),
    "packs": UnitDef(COUNT, 1.0, "pack"),
    "dozen": UnitDef(COUNT, 12.0, "dozen"),
    "dozens": UnitDef(COUNT, 12.0, "dozen"),

    # ── Length — base mm ──────────────────────────────────────────────
    "mm": UnitDef(LENGTH, 1.0, "mm"),
    "millimeter": UnitDef(LENGTH, 1.0, "mm"),
    "millimetre": UnitDef(LENGTH, 1.0, "mm"),
    "millimeters": UnitDef(LENGTH, 1.0, "mm"),
    "millimetres": UnitDef(LENGTH, 1.0, "mm"),
    "cm": UnitDef(LENGTH, 10.0, "cm"),
    "centimeter": UnitDef(LENGTH, 10.0, "cm"),
    "centimetre": UnitDef(LENGTH, 10.0, "cm"),
    "centimeters": UnitDef(LENGTH, 10.0, "cm"),
    "centimetres": UnitDef(LENGTH, 10.0, "cm"),
    "m": UnitDef(LENGTH, 1000.0, "m"),
    "meter": UnitDef(LENGTH, 1000.0, "m"),
    "metre": UnitDef(LENGTH, 1000.0, "m"),
    "meters": UnitDef(LENGTH, 1000.0, "m"),
    "metres": UnitDef(LENGTH, 1000.0, "m"),
    "in": UnitDef(LENGTH, 25.4, "in"),
    "inch": UnitDef(LENGTH, 25.4, "in"),
    "inches": UnitDef(LENGTH, 25.4, "in"),
    '"': UnitDef(LENGTH, 25.4, "in"),
    "ft": UnitDef(LENGTH, 304.8, "ft"),
    "foot": UnitDef(LENGTH, 304.8, "ft"),
    "feet": UnitDef(LENGTH, 304.8, "ft"),

    # ── Energy — base kJ (AU nutrition labels show both) ──────────────
    "kj": UnitDef(ENERGY, 1.0, "kJ"),
    "kilojoule": UnitDef(ENERGY, 1.0, "kJ"),
    "kilojoules": UnitDef(ENERGY, 1.0, "kJ"),
    "kcal": UnitDef(ENERGY, 4.184, "kcal"),
    "cal": UnitDef(ENERGY, 4.184, "kcal"),
    "calorie": UnitDef(ENERGY, 4.184, "kcal"),
    "calories": UnitDef(ENERGY, 4.184, "kcal"),
    "j": UnitDef(ENERGY, 0.001, "J"),
    "joule": UnitDef(ENERGY, 0.001, "J"),
    "joules": UnitDef(ENERGY, 0.001, "J"),
}


# Grams per millilitre. Cross-dimension mass↔volume needs this; without an
# ingredient hint the cross-dimension call fails cleanly.
INGREDIENT_DENSITY_G_PER_ML: dict[str, float] = {
    # Liquids
    "water": 1.00, "milk": 1.03,
    "olive oil": 0.92, "oil": 0.92, "vegetable oil": 0.92, "canola oil": 0.92,
    "honey": 1.42, "maple syrup": 1.32, "golden syrup": 1.40,
    # Flours
    "flour": 0.53, "plain flour": 0.53,
    "all-purpose flour": 0.53, "all purpose flour": 0.53,
    "self-raising flour": 0.53, "self raising flour": 0.53,
    "wholemeal flour": 0.56, "whole wheat flour": 0.56, "bread flour": 0.55,
    "almond flour": 0.42, "almond meal": 0.42,
    # Sugars
    "sugar": 0.85, "white sugar": 0.85, "caster sugar": 0.85, "granulated sugar": 0.85,
    "brown sugar": 0.93,
    "icing sugar": 0.56, "powdered sugar": 0.56, "confectioners sugar": 0.56,
    # Fats / dairy
    "butter": 0.91, "margarine": 0.91,
    # Both spellings: the app ships in Australian English, where the table's
    # US spelling never matches what anyone types into their pantry.
    "yogurt": 1.04, "greek yogurt": 1.05,
    "yoghurt": 1.04, "greek yoghurt": 1.05,
    "sour cream": 0.95, "cream cheese": 0.95, "ricotta": 0.85, "mascarpone": 1.00,
    "cream": 1.00, "heavy cream": 1.00, "thickened cream": 1.00,
    # Aerated, so it is barely half the density of the cream in its name —
    # without its own row, "Vanilla Ice Cream" resolves to `cream` and reads
    # nearly twice its real weight.
    "ice cream": 0.55,
    "peanut butter": 1.05,
    # Grains / pulses / starches
    "rice": 0.78, "white rice": 0.78, "brown rice": 0.76,
    "rolled oats": 0.41, "oats": 0.41, "porridge oats": 0.41,
    "quinoa": 0.72, "couscous": 0.72,
    "dried lentils": 0.85, "lentils": 0.85,
    "dried beans": 0.85, "chickpeas": 0.78,
    "pasta": 0.50, "dry pasta": 0.50,
    "cornstarch": 0.65, "cornflour": 0.65,
    # Bakery / nuts / dried
    "chocolate chips": 0.65, "chocolate": 0.62,
    "chopped almonds": 0.50, "sliced almonds": 0.45, "whole almonds": 0.60,
    "chopped walnuts": 0.55, "walnuts": 0.55,
    "raisins": 0.65, "sultanas": 0.65,
    "shredded coconut": 0.30, "desiccated coconut": 0.45,
    "breadcrumbs": 0.45, "panko": 0.30,
    "cocoa powder": 0.51, "cocoa": 0.51,
    "salt": 1.20,
    # Cheese (grated)
    "parmesan": 0.45, "grated parmesan": 0.45,
    "cheddar": 0.48, "grated cheddar": 0.48, "grated cheese": 0.48,
}


# Gas mark ↔ °C — non-linear UK oven scale. "Gas mark 6" means 200 °C; for
# the reverse we snap to the nearest entry.
GAS_MARK_TO_C: dict[str, float] = {
    "1/4": 110, "1/2": 120, "1": 140, "2": 150, "3": 160, "4": 180,
    "5": 190, "6": 200, "7": 220, "8": 230, "9": 240,
}
GAS_MARK_ALIASES = frozenset({"gas", "gas mark", "gm"})


# ── Helpers ───────────────────────────────────────────────────────────────


def normalise_unit(unit: str) -> str:
    """Lowercase + strip whitespace + strip degree marks. Use before any
    :data:`UNIT_TABLE` lookup so "L", " L", "°C" all collapse correctly."""
    # strip() LAST (FU-524): removing the degree mark can re-expose trailing
    # whitespace (e.g. "gas °" → "gas "), so stripping before the replace left
    # the result non-idempotent and missed UNIT_TABLE / gas-mark aliases.
    return unit.lower().replace("°", "").strip()


# DEC-3 unit-spacing rule: these sit tight against the number ("250g",
# "2ml"); everything else gets a space ("2 cloves"). The SPA's
# `formatQuantity.ts` reads this list from the generated `units_table.ts`
# (`scripts/dump_units.py`) — it used to hold its own copy with a comment
# asking humans to keep the two in sync (finalisation 20-R3, R-003).
NO_SPACE_UNITS: frozenset[str] = frozenset({
    "ml", "g", "kg", "l", "mg", "oz", "lb", "floz", "pt", "qt",
})
_NO_SPACE_UNITS = NO_SPACE_UNITS


_MAX_QUANTITY_DECIMALS = 2


def _format_number(quantity: Any) -> str:
    if quantity is None or quantity == "":
        return ""
    if isinstance(quantity, Decimal):
        quantity = float(quantity)
    if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
        return str(quantity)
    if not math.isfinite(quantity):
        return ""
    # Fixed-point then strip, like `Number(v.toFixed(2)).toString()`: a
    # `round(v, 2)` alone can still print float artefacts. Decimal(float) is
    # exact and ROUND_HALF_UP matches `toFixed` on ties (0.125 → "0.13"; the
    # f-string's half-even gave "0.12" and the print disagreed with the screen).
    text = str(Decimal(quantity).quantize(Decimal(1).scaleb(-_MAX_QUANTITY_DECIMALS), rounding=ROUND_HALF_UP))
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def format_quantity(quantity: Any, unit: Any) -> str:
    """Pretty-print a quantity + unit pair using the DEC-3 spacing rule.

    Mass/volume abbreviations sit tight against the number ("250g", "2ml");
    everything else gets a space ("1 tbsp", "2 cloves"). Either side may be
    None / empty.

    R-079: this function also owns the *precision*. A numeric quantity is
    written to at most two decimals with trailing zeros dropped ("2.0" -> "2",
    94/3 -> "31.33", 0.25 stays "0.25"), matching the SPA's
    `formatQuantity.ts`. It used to be `str(quantity)`, so every print view and
    CSV wrote "2.0 tbsp" / "100.0g". A non-finite number renders as nothing; a
    string (e.g. "1/2") passes through untouched.
    """
    qty = _format_number(quantity)
    trimmed_unit = "" if unit is None else str(unit).strip()
    if not qty and not trimmed_unit:
        return ""
    if not trimmed_unit:
        return qty
    if not qty:
        return trimmed_unit
    no_space = trimmed_unit.lower() in _NO_SPACE_UNITS
    return f"{qty}{trimmed_unit}" if no_space else f"{qty} {trimmed_unit}"


def find_unit(unit: str) -> UnitDef | None:
    """Return the :class:`UnitDef` for *unit* or None. Plural fallback: ``cups``
    is in the table directly; for one-off plurals not enumerated we'd strip
    trailing ``s`` — but we list common plurals exhaustively above to avoid
    swallowing units that legitimately end in s (e.g. ``oz``)."""
    norm = normalise_unit(unit)
    return UNIT_TABLE.get(norm)


def dimension_of(unit: str) -> str | None:
    """Convenience: the dimension string for *unit*, or None if unknown."""
    found = find_unit(unit)
    return found.dimension if found else None


def parse_amount(raw: Any) -> float | None:
    """Accept 1, 1.5, "1/2", "1 1/2" — fractions and mixed numbers fall out
    of LLM tool calls more often than clean floats, so handle them here."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    if not s:
        return None
    # Mixed: "1 1/2"
    parts = s.split()
    if len(parts) == 2 and "/" in parts[1]:
        try:
            whole = float(parts[0])
            num, den = parts[1].split("/")
            denom = float(den)
            if not denom:
                return None
            frac = float(num) / denom
            return whole - frac if whole < 0 else whole + frac
        except ValueError:
            return None
    # Pure fraction
    if "/" in s:
        try:
            num, den = s.split("/")
            denom = float(den)
            if not denom:
                return None
            return float(num) / denom
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def snap_gas_mark(celsius: float) -> str:
    """Nearest gas-mark string for *celsius*."""
    best_key, best_delta = "4", float("inf")
    for key, val in GAS_MARK_TO_C.items():
        delta = abs(val - celsius)
        if delta < best_delta:
            best_key, best_delta = key, delta
    return best_key


@dataclass(frozen=True, slots=True)
class FoodSpecificMass:
    """A mass unit whose gram value is a fact about one food, not about the
    unit. `owners` are the foods the figure belongs to; `portion_measures` are
    the words a nutrition dataset uses for the same household measure."""
    owners: tuple[str, ...]
    portion_measures: tuple[str, ...]


# The one entry, and the reason this exists: `stick` is 113 g because that is a
# stick of butter in a US supermarket. A stick of celery is about 40 g and a
# cinnamon stick about 2.6 g, so a table of universal conversions is quietly
# carrying one product's packaging. Rather than delete it — US households
# genuinely measure butter this way — the ambiguity is named here, and both
# recipe calculators ask before trusting the number: the nutrition rollup
# prefers the food's own portion row (`portion_measures`, including USDA's
# "stalk" for the celery case), and recipe costing refuses the conversion
# outright unless the ingredient is one of `owners`. Before that check,
# "2 sticks of celery" was weighed as 226 g and billed as 226 g (owner
# 2026-09-09).
FOOD_SPECIFIC_MASS_UNITS: dict[str, FoodSpecificMass] = {
    "stick": FoodSpecificMass(
        owners=("butter", "margarine"),
        portion_measures=("stick", "stalk"),
    ),
}


# Words that name a *part of* a shelf item, never the item itself. A recipe
# asking for three of these is asking for three pieces of one thing you buy,
# and costing them against the per-item price bills three of the thing:
# measured 2026-09-09, "3 cloves" of garlic came to $3.60 (three bulbs), "2
# sprigs" of tarragon to $5.00 (two bunches), "4 rashers" of bacon to $3.60
# (four packs). Same family as the $16.50 egg yolks (R-076/ADR-073).
#
# The counted branch is otherwise deliberately permissive — "2 tins" is the
# identical shape and is correct, because a tin *is* the shelf item — and no
# data distinguishes the two cases. This list is the distinction, stated
# explicitly. An ingredient measured in one of these is priced from its weight
# where a weight is knowable, and reported unpriced where it isn't; it is never
# billed as a whole product.
#
# Deliberately short. Every word here is a part in every kitchen — a "head" of
# garlic or a "bunch" of herbs is the thing you buy and is correctly counted,
# so neither belongs.
SUB_ITEM_UNITS: frozenset[str] = frozenset({
    "clove",        # of garlic
    "sprig",        # of a soft herb
    "rasher",       # of bacon
    "slice",        # of bread, cheese, ham
    "stalk",        # of celery, rhubarb
    "floret",       # of broccoli, cauliflower
    "leaf",         # of basil, gelatine
    "wedge",        # of lemon, lime
    # Not a part but the same failure: a vague amount, never a whole product.
    # "pinch", "dash" and "smidgen" are already real volume units and convert
    # properly, so only the ones with no defined size are listed.
    "knob",         # of butter
    "splash",
    "drizzle",
    "handful",
})


# Units a recipe quantity is *counted* in, so cook-mode scaling rounds them to
# whole numbers ("2 rashers", never "2.5 rashers"). Two purposes, one list
# each: `SUB_ITEM_UNITS` above answers "is this a part of a shelf item?" for
# pricing; this answers "is this a discrete thing?" for scaling. They overlap
# on the discrete parts but not on the vague amounts — a "handful" or
# "splash" is unpriceable *and* continuous (1.5 handfuls is fine). Emitted to
# the SPA via `scripts/dump_units.py` for `scaleQuantity.isCountableUnit` —
# the client used to carry a different list (finalisation 20-R4, R-003).
_VAGUE_AMOUNTS: frozenset[str] = frozenset({"splash", "drizzle", "handful"})
COUNTABLE_UNITS: frozenset[str] = (SUB_ITEM_UNITS - _VAGUE_AMOUNTS) | frozenset({
    "egg", "scoop", "piece", "stick", "can", "bunch", "pinch", "head",
})


def is_sub_item_unit(unit: str | None) -> bool:
    """Whether *unit* names a part of a shelf item rather than the item.
    Accepts plurals, which is how recipes are actually written ("3 cloves")."""
    if not unit:
        return False
    normalised = normalise_unit(unit)
    return normalised in SUB_ITEM_UNITS or normalised.rstrip("s") in SUB_ITEM_UNITS


def food_specific_mass(unit: str | None) -> FoodSpecificMass | None:
    """The ambiguity record for *unit*, or None when the unit means one thing
    everywhere. Accepts plurals ("sticks")."""
    if not unit:
        return None
    normalised = normalise_unit(unit)
    return FOOD_SPECIFIC_MASS_UNITS.get(
        normalised) or FOOD_SPECIFIC_MASS_UNITS.get(normalised.rstrip("s"))


def food_specific_mass_applies(unit: str | None, ingredient: str | None) -> bool:
    """Whether *unit*'s gram value may be applied to *ingredient*.

    True for a unit that isn't food-specific at all — the common case, and the
    reason callers can put this in front of every mass conversion. For one that
    is, the ingredient has to name one of the owning foods as a whole word,
    which means an unknown ingredient is a **no**: the number is unusable
    without knowing what it is measuring, and that is the state that produced
    the wrong answer.
    """
    record = food_specific_mass(unit)
    if record is None:
        return True
    if not ingredient:
        return False
    words = set("".join(
        c if c.isalnum() else " " for c in ingredient.lower()
    ).split())
    return any(owner in words for owner in record.owners)


def density_for_ingredient(name: str | None) -> float | None:
    """Grams per millilitre for *name*, or None when the table can't answer.

    An exact lookup was the whole of this until 2026-09-09, and it meant the
    table almost never fired against a real pantry: households type
    "Extra Virgin Olive Oil" and "Full Cream Milk", not "olive oil" and "milk",
    so a 77-entry table of correct densities sat there answering nothing and
    every volume-measured ingredient reported as unweighable.

    So: exact match first, then a table key appearing in the name **as whole
    words**, resolved by two rules in order.

    1. *Head noun wins.* English names an ingredient last — "Full Cream Milk"
       is a milk, not a cream — so a key that ends the name beats one buried in
       the middle. Without this rule that name reads as cream, and it is the
       common shape, not an edge case.
    2. *Then longest wins*, because "brown sugar" and "sugar" both appear in
       "Light Brown Sugar" and the specific one is the right answer. This is
       also what keeps "Vanilla Ice Cream" off the dairy-cream row.

    Whole words rather than a substring test throughout, or "buttermilk" would
    be butter and "coconut oil" would be right only by luck.

    This is still a lookup, not an estimate (P12 No-invent): a name with no
    listed ingredient in it returns None exactly as before, and the caller
    reports the ingredient as unconvertible rather than inventing a weight.
    """
    if not name:
        return None
    lowered = name.lower().strip()
    exact = INGREDIENT_DENSITY_G_PER_ML.get(lowered)
    if exact is not None:
        return exact
    words = [w for w in "".join(
        c if (c.isalnum() or c == "-") else " " for c in lowered
    ).split() if w]
    if not words:
        return None
    normalised = " ".join(words)
    haystack = f" {normalised} "
    matches = [
        key for key in INGREDIENT_DENSITY_G_PER_ML
        if f" {key} " in haystack
    ]
    if not matches:
        return None
    trailing = [key for key in matches if normalised.endswith(key)]
    best = max(trailing or matches, key=len)
    return INGREDIENT_DENSITY_G_PER_ML[best]


def convert(
    amount: float,
    from_unit: str,
    to_unit: str,
    *,
    ingredient: str | None = None,
) -> float | None:
    """Linear conversion within one dimension; cross-dimension mass↔volume
    when *ingredient* (lowercase) maps to a known density. Returns None when
    the units are unknown or the dimensions can't bridge — callers handle
    the error shape themselves.

    Temperature and gas mark are handled by :func:`convert_temperature` /
    :func:`convert_gas_mark` (offsets + non-linear; would muddy this
    function's contract)."""
    src = find_unit(from_unit)
    dst = find_unit(to_unit)
    if not src or not dst:
        return None
    if src.dimension == dst.dimension:
        return amount * src.factor / dst.factor
    if {src.dimension, dst.dimension} == {MASS, VOLUME}:
        if not ingredient:
            return None
        density = density_for_ingredient(ingredient)
        if density is None:
            return None
        base = amount * src.factor                # to source's base unit
        if src.dimension == MASS:                 # g → ml via density
            ml = base / density
            return ml / dst.factor
        grams = base * density                    # ml → g via density
        return grams / dst.factor
    return None


def convert_temperature(amount: float, from_unit: str, to_unit: str) -> float | None:
    """C/F/K with offsets. Returns None if either side isn't a temperature."""
    temp = {"c", "celsius", "celcius", "f", "fahrenheit", "k", "kelvin"}
    f, t = normalise_unit(from_unit), normalise_unit(to_unit)
    if f not in temp or t not in temp:
        return None

    def to_c(v: float, u: str) -> float:
        if u in ("c", "celsius", "celcius"):
            return v
        if u in ("f", "fahrenheit"):
            return (v - 32) * 5 / 9
        return v - 273.15  # kelvin

    def from_c(v: float, u: str) -> float:
        if u in ("c", "celsius", "celcius"):
            return v
        if u in ("f", "fahrenheit"):
            return v * 9 / 5 + 32
        return v + 273.15

    return from_c(to_c(amount, f), t)


def is_gas_mark_alias(token: str) -> bool:
    return normalise_unit(token) in GAS_MARK_ALIASES


# ── Price-entry convenience (chunk 3 / B3) ────────────────────────────────


@dataclass(frozen=True, slots=True)
class CanonicalUnitChoice:
    """One picker row for the price-entry widget. ``canonical`` is the
    persisted string; ``label`` is the display string."""
    canonical: str
    label: str
    dimension: str


def supported_price_units() -> list[CanonicalUnitChoice]:
    """Flat global list of units the price-entry widget offers (B3),
    grouped client-side by dimension. The cooking-only units (cup, tsp,
    tbsp, pinch, dash, fl oz, pt, qt, gal, smidgen, stick) are filtered out
    via :data:`PRICE_PICKER_CANONICAL_UNITS` — the conversion engine still
    knows them for the assistant and the harvest path, but the picker
    shows only what AU shoppers actually shop in."""
    seen: dict[str, CanonicalUnitChoice] = {}
    for udef in UNIT_TABLE.values():
        if udef.dimension not in PRICE_DIMENSIONS:
            continue
        if udef.canonical not in PRICE_PICKER_CANONICAL_UNITS:
            continue
        if udef.canonical in seen:
            continue
        seen[udef.canonical] = CanonicalUnitChoice(
            canonical=udef.canonical,
            label=udef.canonical,
            dimension=udef.dimension,
        )
    return list(seen.values())
