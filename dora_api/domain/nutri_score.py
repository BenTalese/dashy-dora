"""The Nutri-Score algorithm, as published by Santé publique France.

Transcribed from the **Nutri-Score scientific and technical FAQ, V11
(English)** — Tables 5 and 6 and the "Calculation of the nutritional score"
method — and cross-checked, threshold by threshold, against the **official
calculation workbook** `Nutri-Score_Updated-algorithm_20240404.xlsx`
(santepubliquefrance.fr), whose *General foods* sheet is the tool European
manufacturers actually use. Nothing here is Dora's invention.

**This is the Updated Algorithm (Nutri-Score 2023), not the 2017 original.**
The distinction matters more than it looks. The official workbook computes
*both* side by side on the same sheet — columns K–U are the original, W–AE the
updated — and they disagree in ways that change letters:

  * sugars ran 0–10 on a 4.5 g step; it now runs **0–15** on its own scale;
  * sodium (mg) was replaced by **salt (g)**, 0–10 becoming **0–20**;
  * protein ran 0–5; it now runs **0–7**;
  * fibre thresholds moved (0.9–4.7 g → 3.0–7.4 g);
  * **nuts left the positive component** — see `fvl_percent` below;
  * the grade-A cut-off moved from `< 0` to **`< 1`**;
  * the original's "protein still counts if FVL scores the full 5" carve-out
    is **gone** — above the gate, protein simply drops out.

Several widely-cited third-party write-ups of "the 2023 algorithm" quietly mix
the two generations. They were not used as a source, and the one that was
checked had the grade-A cut-off wrong.

Pure and repository-free, like `domain/health_star_rating.py` and
`domain/stock_status.py`: callers pass an already-computed per-100g nutrient
profile and get a grade back.

**Scope: the general-foods table only.** The published method defines five
calculation categories — general foods, red meat, cheese, fats/oils/nuts/seeds,
and beverages — with *different tables and different grade cut-offs* (grade A is
`< 1` for general foods but `< -5` for fats and oils). A recipe is a dish, and
general foods is the residual category, so it is both the correct answer and
the default. The other four are defined by properties of a packaged product
that a home recipe has no way to assert, and guessing would move a dish between
letters on the strength of a guess.

The FAQ explicitly contemplates this use ("In the case of recipes, for example
in magazines, apps or in promotional material, the calculation is based on the
quantities and nutritional values of the various ingredients that constitute
the dish") and directs exactly here: "the algorithm for general foods may be
used".

**Three honest departures from the published method**, all forced by the
difference between a packaged product and a recipe, and all surfaced to the
user rather than hidden:

1. *Per 100 g of what.* The FAQ's recipe modality asks for ingredient values
   **as consumed** — cooked, with the yield of each ingredient accounted for.
   Dora can only sum raw ingredient weights, so a sauce that reduces reads too
   kindly and a soup made with unlisted water reads too harshly. This is a
   stated condition of the recipe modality rather than merely an accuracy nicety,
   which is why every surface labels the result an estimate. Tracked as FU-748.
2. *The ×2 weighting* the FAQ applies to dried fruit and to concentrated fruit
   and vegetables (its worked example doubles 25 g of raisins, and doubles
   tomato concentrate in a pizza) is **not** implemented. Whether an ingredient
   is dried or concentrated is not something a USDA food category can answer,
   and treating everything as neither is the conservative reading — it scores a
   recipe no better than it deserves.
3. *The red-meat protein cap* (Table 6: at most 2 protein points for red meat
   and products thereof) is **not** implemented, because deciding a dish "is
   red meat and products thereof" is a judgement about a product, not an
   arithmetic fact about a recipe. Its effect is one-directional and small —
   an uncapped red-meat dish can read at most a little better than it should.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
from dora_api.domain.rating_tables import points_for


# ── Negative (N) component ──────────────────────────────────────────────
# FAQ Table 5: "Points attributed to each of the elements of the negative N
# component". Each tuple is (points, threshold); the rule is **strictly greater
# than** the threshold, so the score is the highest row whose threshold the
# value exceeds. The workbook states the same cascade the other way round
# (`IF(value<=threshold, n, …)`), which is equivalent.
#
# The ceilings differ per nutrient and that is not a transcription slip: energy
# and saturated fat stop at 10, sugars at 15, salt at 20. N therefore ranges
# 0–55, not 0–40 as it did in the 2017 original.

# Unchanged from the original algorithm — the workbook shares one column
# between both generations (`K`), in 335 kJ steps.
_N_ENERGY_KJ: Tuple[Tuple[int, float], ...] = (
    (1, 335), (2, 670), (3, 1005), (4, 1340), (5, 1675), (6, 2010),
    (7, 2345), (8, 2680), (9, 3015), (10, 3350),
)
# Also unchanged, and also shared (workbook column `M`): 1 g per point.
_N_SATURATED_FAT_G: Tuple[Tuple[int, float], ...] = (
    (1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (9, 9),
    (10, 10),
)
# New in 2023 (workbook column `AA`, thresholds on the `Scenario` sheet at
# `$AA$3..$AA$18`). Note the steps are uneven — 3.4/6.8 then 10/14/17 — which
# is as published, not a rounding of a regular series.
_N_SUGARS_G: Tuple[Tuple[int, float], ...] = (
    (1, 3.4), (2, 6.8), (3, 10), (4, 14), (5, 17), (6, 20), (7, 24), (8, 27),
    (9, 31), (10, 34), (11, 37), (12, 41), (13, 44), (14, 48), (15, 51),
)
# New in 2023 (workbook column `Z`, `Scenario!$O$3..$O$23`). Salt in **grams**,
# 0.2 g per point up to 4.0 g.
_N_SALT_G: Tuple[Tuple[int, float], ...] = (
    (1, 0.2), (2, 0.4), (3, 0.6), (4, 0.8), (5, 1.0), (6, 1.2), (7, 1.4),
    (8, 1.6), (9, 1.8), (10, 2.0), (11, 2.2), (12, 2.4), (13, 2.6), (14, 2.8),
    (15, 3.0), (16, 3.2), (17, 3.4), (18, 3.6), (19, 3.8), (20, 4.0),
)

# The FAQ's footnote to Table 5: "the sodium content corresponds to the salt
# content mentioned in the mandatory nutritional statement divided by 2.5."
# Dora stores sodium (that is what `NutritionFood` and the whole nutrition
# surface carry), so the conversion runs the other way, in exactly one place.
SALT_G_PER_SODIUM_G = 2.5

# ── Positive (P) component ──────────────────────────────────────────────
# FAQ Table 6. P ranges 0–17.
#
# Protein 0–7 (workbook `Scenario!$G$3..$G$10`).
_P_PROTEIN_G: Tuple[Tuple[int, float], ...] = (
    (1, 2.4), (2, 4.8), (3, 7.2), (4, 9.6), (5, 12), (6, 14), (7, 17),
)
# Fibre 0–5 (workbook `Scenario!$C$3..$C$8`).
_P_FIBRE_G: Tuple[Tuple[int, float], ...] = (
    (1, 3.0), (2, 4.1), (3, 5.2), (4, 6.3), (5, 7.4),
)
# Fruit/vegetables/legumes 0–5, but only four bands exist: >40 → 1, >60 → 2,
# >80 → 5. Three and four points are **unreachable**, exactly as published
# (workbook: `IF(fvl<=40,0,IF(fvl<=60,1,IF(fvl<=80,2,5)))`).
_P_FVL_PERCENT: Tuple[Tuple[int, float], ...] = (
    (1, 40), (2, 60), (5, 80),
)

# "If the total of the N component is greater than or equal to 11 points, then
# the nutritional score is equal to the total N component points from which is
# subtracted the sum of the points for 'fibres' and 'Fruits, vegetables,
# legumes'. In this case, the protein content is therefore not taken into
# account."
#
# The 2017 original spared protein when FVL scored the full 5; the 2023 method
# does not, and the workbook's updated column agrees with the prose. Do not
# reintroduce that carve-out from the original tables.
PROTEIN_GATE_N_POINTS = 11

# The grade bands, read from the workbook's updated classification
# (`IF(score<1,"A",IF(score<3,"B",IF(score<11,"C",IF(score<19,"D","E"))))`),
# as (exclusive upper bound, grade) ascending. The FAQ presents the same table
# as an image, which is why the workbook is cited here instead.
#
# The bands are open at the bottom and closed at the top: a score of exactly 0
# is an A, and the official "Apple sauce tinned" worked example lands there.
_GRADE_BANDS: Tuple[Tuple[int, str], ...] = (
    (1, "A"), (3, "B"), (11, "C"), (19, "D"),
)
_GRADE_WORST = "E"

GRADES: Tuple[str, ...] = ("A", "B", "C", "D", "E")


@dataclass(frozen=True, slots=True)
class NutrientProfile:
    """What a grade is computed from: the composition of 100 g of the food.

    Every field is nullable because a source can know a food's protein and not
    its fibre. A `None` scores **zero points** for that component, which is the
    only defensible default — but note it is not symmetric in effect: a missing
    negative nutrient flatters the food, while a missing positive one penalises
    it. That asymmetry is why the caller must report per nutrient how much of
    the recipe's weight was actually known, and why the grade carries that
    coverage with it rather than standing alone.

    Sodium rather than salt: `sodium_mg` is what the rest of Dora's nutrition
    stack carries, and `rate` applies the FAQ's ×2.5 conversion itself so the
    factor lives in one place (R-003).
    """
    energy_kj: Optional[float]
    saturated_fat_g: Optional[float]
    total_sugars_g: Optional[float]
    sodium_mg: Optional[float]
    protein_g: Optional[float]
    fibre_g: Optional[float]
    # Percentage (0–100) of the food's weight that is fruit, vegetables or
    # legumes.
    #
    # **Not the same quantity as the Health Star Rating's fvnl**, and the two
    # must never be fed to each other's module. The 2023 update moved nuts and
    # seeds out of this component and into their own calculation category, so
    # nuts now count toward the *denominator* but not the numerator. The FAQ's
    # own worked example makes the divergence concrete: a mix of cherries,
    # raisins, nuts and other ingredients is 46% under the original and 37%
    # under the updated algorithm, purely because the 15 g of nuts moved.
    #
    # `None` and 0.0 both score zero points; they are kept distinct so the
    # caller can tell "no fruit or veg in this dish" from "we could not tell",
    # and say so.
    fvl_percent: Optional[float]


@dataclass(frozen=True, slots=True)
class NutriScore:
    """A grade with every intermediate the method names, so the UI can show its
    working rather than assert a letter."""
    grade: str
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
    # False when the N ≥ 11 gate dropped the protein credit. Surfaced because
    # "your protein didn't count, and here's why" is the one part of the result
    # that reads as a bug when it isn't.
    protein_counted: bool


def sodium_mg_to_salt_g(sodium_mg: Optional[float]) -> Optional[float]:
    """The one place the conversion happens (R-003). See `SALT_G_PER_SODIUM_G`."""
    if sodium_mg is None:
        return None
    return sodium_mg / 1000.0 * SALT_G_PER_SODIUM_G


def rate(profile: NutrientProfile) -> NutriScore:
    """Score a per-100g nutrient profile against the general-foods table.

    The published method in order: the four negative components, the three
    positive ones, then the branch on N that decides whether protein counts.
    """
    energy = points_for(profile.energy_kj, _N_ENERGY_KJ)
    saturated_fat = points_for(profile.saturated_fat_g, _N_SATURATED_FAT_G)
    total_sugars = points_for(profile.total_sugars_g, _N_SUGARS_G)
    salt = points_for(sodium_mg_to_salt_g(profile.sodium_mg), _N_SALT_G)
    negative = energy + saturated_fat + total_sugars + salt

    protein = points_for(profile.protein_g, _P_PROTEIN_G)
    fibre = points_for(profile.fibre_g, _P_FIBRE_G)
    fvl = points_for(profile.fvl_percent, _P_FVL_PERCENT)

    # Below the gate the whole positive component counts; at or above it,
    # protein drops out and only fibre and fvl are subtracted.
    protein_counted = negative < PROTEIN_GATE_N_POINTS
    positive = protein + fibre + fvl
    score = negative - positive if protein_counted else negative - fibre - fvl

    return NutriScore(
        grade = grade_for_score(score),
        score = score,
        negative_points = negative,
        energy_points = energy,
        saturated_fat_points = saturated_fat,
        total_sugars_points = total_sugars,
        salt_points = salt,
        positive_points = positive,
        protein_points = protein,
        fibre_points = fibre,
        fvl_points = fvl,
        protein_counted = protein_counted,
    )


def grade_for_score(score: int) -> str:
    """The 5-colour scale. Bands are contiguous, so the first band whose
    exclusive upper bound the score falls under wins, walking best-first."""
    for upper_bound, grade in _GRADE_BANDS:
        if score < upper_bound:
            return grade
    return _GRADE_WORST
