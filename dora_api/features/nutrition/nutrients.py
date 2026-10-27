"""The nutrient set Dora stores, how each source names it, and how it renders.

One module so adding a nutrient is a single edit. Before this existed the
mapping lived in three places — the bulk CSV importer's `_WANTED_NUTRIENTS`,
the live USDA-API parser's if/elif chain, and the Open Food Facts parser's
field list — which is exactly the drift R-002 exists to stop: a nutrient added
to the importer but not to the API path would silently be blank for installs
that use the live key.

Scope (owner decision 2026-08-17, superseding the narrower 2026-08-16 call):
the standard nutrition panel, **plus** an optional block of the vitamins and
minerals a pack commonly declares. The earlier decision deferred these on the
grounds that they'd need a per-nutrient child table; that only holds for the
*full* USDA table (hundreds of nutrients, amino-acid profiles, individual fatty
acids). A curated ~15-row shortlist is a column apiece, and the UI keeps it
behind a disclosure so a sparse source can't push the panel off the screen.
Still deliberately NOT stored: individual fatty acids, amino acids, sugar
alcohols, carotenoid breakdowns.

`kcal_per_100g` stays the only value the app treats as load-bearing; everything
else is display-only, and NULL means "this source didn't say", never zero
(P12 No-invent).

**Rendering lives here too** (R-003 / state-ownership: no domain constant in two
languages). The client used to carry its own copy of the label list, the row
order, the unit strings and the rounding policy, with a comment asking the next
person to keep the two in step by hand. `display_rows()` is now the one
authority; the SPA renders what it's handed.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# Which block of the panel a nutrient belongs to.
#
# `panel` is the statement every pack carries and every source populates —
# it renders inline, always. `more` is the vitamins-and-minerals block, which
# is sparse in every source (USDA Foundation is good, SR Legacy is patchy, OFF
# is whatever the manufacturer typed in), so it renders behind a disclosure and
# disappears entirely when nothing in it is known.
GROUP_PANEL = "panel"
GROUP_MORE = "more"


@dataclass(frozen=True, slots=True)
class Nutrient:
    """One stored nutrient and everything needed to read or render it."""
    attr: str
    label: str
    unit: str
    # USDA `(nutrient name, unit)` pairs, lowercased. More than one because
    # sources disagree: Foundation and SR Legacy name the sugar row differently,
    # and the bulk CSV writes micrograms as `UG` where the live API sends `µg`.
    usda_keys: Tuple[Tuple[str, str], ...]
    # Open Food Facts `nutriments` key, when OFF carries the value.
    off_key: Optional[str] = None
    # Multiplier applied to the OFF value to reach our stored unit. OFF reports
    # every non-energy nutriment in GRAMS per 100g, while we store milligrams
    # for minerals and micrograms for the vitamins that are declared that way —
    # and getting this wrong is a 1000× error on numbers people actually watch.
    off_scale: float = 1.0
    group: str = GROUP_PANEL
    # Rendered as a sub-row of the nutrient above it, the way a pack prints
    # saturated fat under total fat.
    indent: bool = False
    # Decimal places when rendering. 0 for the figures nobody reads a fraction
    # of (energy, sodium, the milligram minerals); 1 where 0.4 g vs 0 g is a
    # real difference.
    decimals: int = 1


# Display order too — the UI renders the list in this sequence.
#
# The panel block follows the order used on the back of a pack (FSANZ/FDA agree
# on this much): energy, protein, fat and its saturated sub-row, carbohydrate
# and its sugars sub-row, fibre, sodium. It previously listed carbohydrate
# before fat, which no printed panel does.
NUTRIENTS: Tuple[Nutrient, ...] = (
    Nutrient(
        attr="kcal_per_100g", label="Energy", unit="kcal",
        usda_keys=(("energy", "kcal"),),
        off_key="energy-kcal_100g", decimals=0,
    ),
    Nutrient(
        attr="protein_g_per_100g", label="Protein", unit="g",
        usda_keys=(("protein", "g"),),
        off_key="proteins_100g",
    ),
    Nutrient(
        attr="fat_g_per_100g", label="Fat, total", unit="g",
        usda_keys=(("total lipid (fat)", "g"),),
        off_key="fat_100g",
    ),
    Nutrient(
        attr="saturated_fat_g_per_100g", label="Saturated", unit="g",
        usda_keys=(("fatty acids, total saturated", "g"),),
        off_key="saturated-fat_100g", indent=True,
    ),
    Nutrient(
        attr="carbs_g_per_100g", label="Carbohydrate", unit="g",
        usda_keys=(("carbohydrate, by difference", "g"),),
        off_key="carbohydrates_100g",
    ),
    Nutrient(
        attr="sugars_g_per_100g", label="Sugars", unit="g",
        usda_keys=(
            ("total sugars", "g"),
            ("sugars, total including nlea", "g"),
            ("sugars, total", "g"),
        ),
        off_key="sugars_100g", indent=True,
    ),
    Nutrient(
        attr="fibre_g_per_100g", label="Dietary fibre", unit="g",
        usda_keys=(("fiber, total dietary", "g"),),
        off_key="fiber_100g",
    ),
    Nutrient(
        attr="sodium_mg_per_100g", label="Sodium", unit="mg",
        usda_keys=(("sodium, na", "mg"),),
        off_key="sodium_100g", off_scale=1000.0, decimals=0,
    ),

    # ── The optional block (owner request 2026-08-17) ──────────────────
    # Fats first (they're the rest of the fat breakdown a panel may print),
    # then cholesterol, then minerals, then vitamins — the order a US
    # Nutrition Facts label uses for the same rows.
    Nutrient(
        attr="trans_fat_g_per_100g", label="Trans fat", unit="g",
        usda_keys=(("fatty acids, total trans", "g"),),
        off_key="trans-fat_100g", group=GROUP_MORE,
    ),
    Nutrient(
        attr="monounsaturated_fat_g_per_100g", label="Monounsaturated fat", unit="g",
        usda_keys=(("fatty acids, total monounsaturated", "g"),),
        off_key="monounsaturated-fat_100g", group=GROUP_MORE,
    ),
    Nutrient(
        attr="polyunsaturated_fat_g_per_100g", label="Polyunsaturated fat", unit="g",
        usda_keys=(("fatty acids, total polyunsaturated", "g"),),
        off_key="polyunsaturated-fat_100g", group=GROUP_MORE,
    ),
    Nutrient(
        attr="cholesterol_mg_per_100g", label="Cholesterol", unit="mg",
        usda_keys=(("cholesterol", "mg"),),
        off_key="cholesterol_100g", off_scale=1000.0,
        group=GROUP_MORE, decimals=0,
    ),
    Nutrient(
        attr="potassium_mg_per_100g", label="Potassium", unit="mg",
        usda_keys=(("potassium, k", "mg"),),
        off_key="potassium_100g", off_scale=1000.0,
        group=GROUP_MORE, decimals=0,
    ),
    Nutrient(
        attr="calcium_mg_per_100g", label="Calcium", unit="mg",
        usda_keys=(("calcium, ca", "mg"),),
        off_key="calcium_100g", off_scale=1000.0,
        group=GROUP_MORE, decimals=0,
    ),
    Nutrient(
        attr="iron_mg_per_100g", label="Iron", unit="mg",
        usda_keys=(("iron, fe", "mg"),),
        off_key="iron_100g", off_scale=1000.0,
        group=GROUP_MORE,
    ),
    Nutrient(
        attr="magnesium_mg_per_100g", label="Magnesium", unit="mg",
        usda_keys=(("magnesium, mg", "mg"),),
        off_key="magnesium_100g", off_scale=1000.0,
        group=GROUP_MORE, decimals=0,
    ),
    Nutrient(
        attr="zinc_mg_per_100g", label="Zinc", unit="mg",
        usda_keys=(("zinc, zn", "mg"),),
        off_key="zinc_100g", off_scale=1000.0,
        group=GROUP_MORE,
    ),
    Nutrient(
        attr="vitamin_a_ug_per_100g", label="Vitamin A", unit="µg",
        usda_keys=(("vitamin a, rae", "ug"), ("vitamin a, rae", "µg")),
        off_key="vitamin-a_100g", off_scale=1_000_000.0,
        group=GROUP_MORE, decimals=0,
    ),
    Nutrient(
        attr="vitamin_c_mg_per_100g", label="Vitamin C", unit="mg",
        usda_keys=(("vitamin c, total ascorbic acid", "mg"),),
        off_key="vitamin-c_100g", off_scale=1000.0,
        group=GROUP_MORE,
    ),
    Nutrient(
        attr="vitamin_d_ug_per_100g", label="Vitamin D", unit="µg",
        usda_keys=(("vitamin d (d2 + d3)", "ug"), ("vitamin d (d2 + d3)", "µg")),
        off_key="vitamin-d_100g", off_scale=1_000_000.0,
        group=GROUP_MORE,
    ),
    Nutrient(
        attr="vitamin_e_mg_per_100g", label="Vitamin E", unit="mg",
        usda_keys=(("vitamin e (alpha-tocopherol)", "mg"),),
        off_key="vitamin-e_100g", off_scale=1000.0,
        group=GROUP_MORE,
    ),
    Nutrient(
        attr="vitamin_b12_ug_per_100g", label="Vitamin B12", unit="µg",
        usda_keys=(("vitamin b-12", "ug"), ("vitamin b-12", "µg")),
        off_key="vitamin-b12_100g", off_scale=1_000_000.0,
        group=GROUP_MORE, decimals=2,
    ),
    Nutrient(
        attr="folate_ug_per_100g", label="Folate", unit="µg",
        usda_keys=(("folate, total", "ug"), ("folate, total", "µg")),
        off_key="folates_100g", off_scale=1_000_000.0,
        group=GROUP_MORE, decimals=0,
    ),
)

NUTRIENT_ATTRS: Tuple[str, ...] = tuple(n.attr for n in NUTRIENTS)

# (lowercased USDA nutrient name, lowercased unit) → attribute name.
USDA_NUTRIENT_ATTRS: Dict[Tuple[str, str], str] = {
    key: nutrient.attr
    for nutrient in NUTRIENTS
    for key in nutrient.usda_keys
}


def to_float(raw) -> Optional[float]:  # noqa: ANN001
    """A number read from a dataset file or a source API: a number, a numeric
    string (whitespace allowed), or nothing. Blank and junk read as None."""
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def off_values(nutriments: dict) -> Dict[str, float]:
    """Pull our nutrient set out of an OFF `nutriments` blob. Missing keys are
    omitted, not zeroed."""
    values: Dict[str, float] = {}
    for nutrient in NUTRIENTS:
        if not nutrient.off_key:
            continue
        amount = to_float(nutriments.get(nutrient.off_key))
        if amount is not None:
            values[nutrient.attr] = amount * nutrient.off_scale
    return values


@dataclass(frozen=True, slots=True)
class NutrientRow:
    """One rendered line of the per-100g table, ready for the SPA to print."""
    label: str
    value: str          # already formatted, unit included ("2.6 g", "412 kcal")
    group: str
    indent: bool


def _format(amount: float, nutrient: Nutrient) -> str:
    if nutrient.decimals == 0:
        return f"{round(amount)} {nutrient.unit}"
    # Trailing zeros dropped: "2.5 g", but "3 g" rather than "3.0 g".
    trimmed = float(f"{amount:.{nutrient.decimals}f}")
    text = str(int(trimmed)) if trimmed == int(trimmed) else str(trimmed)
    return f"{text} {nutrient.unit}"


def display_rows(food: Any) -> List[NutrientRow]:
    """The per-100g table for `food`, in panel order, skipping what it doesn't
    know.

    Takes anything carrying the nutrient attributes — the `NutritionFood`
    entity, a lookup `FoodResult`, or a DTO — so the one formatting policy
    serves every surface that shows a nutrient table.
    """
    rows: List[NutrientRow] = []
    for nutrient in NUTRIENTS:
        amount = getattr(food, nutrient.attr, None)
        if amount is None:
            continue
        rows.append(NutrientRow(
            label=nutrient.label,
            value=_format(float(amount), nutrient),
            group=nutrient.group,
            indent=nutrient.indent,
        ))
    return rows
