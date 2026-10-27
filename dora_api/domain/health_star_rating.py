"""The Health Star Rating algorithm, as published by FSANZ.

Transcribed from **Health Star Rating system Calculator and Style Guide,
June 2025, Version 8.1** (healthstarrating.gov.au) — Tables 1, 4, 6 and 7 and
the Step 4–7 method. Nothing here is Dora's invention: the thresholds, the
point ceilings, the protein gate and the score→star bands are the published
ones, and the docstrings name the table each came from so a reader can check
them against the source without trusting this file.

Pure and repository-free, like `domain/stock_status.py`: callers pass an
already-computed per-100g nutrient profile and get a rating back. That keeps
the one piece of the feature anybody would want to audit — the arithmetic —
free of I/O and trivially testable against the worked examples in the guide.

**Scope: Category 2 only.** The guide defines six categories (1 non-dairy
beverages, 1D milk and dairy beverages, 2 all other foods, 2D dairy foods,
3 oils and spreads, 3D cheese). A *recipe* is a dish, and Category 2 is
literally "all foods other than those included in Category 1, 1D, 2D, 3 or
3D" — so it is both the correct answer and the default. The other five
categories are defined by properties of a packaged product (calcium per
100 mL, ≥75% dairy content, being an edible oil as defined in Standard 2.4.1)
that a home recipe has no way to assert, and guessing at them would move a
dish between star bands on the strength of a guess. If a category ever needs
to be chosen, it should be chosen by a human, not inferred here.

**Two honest departures from the published method**, both forced by the
difference between a packaged product and a recipe, and both surfaced to the
user rather than hidden:

1. *Per 100 g of what.* HSR scores the product as consumed. Dora can only sum
   raw ingredient weights, so the denominator is the raw weight of everything
   it could resolve. A sauce that reduces reads too kindly; a soup made with
   water nobody listed as an ingredient reads too harshly. Owner's call
   2026-08-27: accept it and label the rating an estimate rather than add a
   finished-weight field nobody would fill in.
2. *The automatic ratings* in Step 1 (plain water → 5, unsweetened flavoured
   water → 4.5, fresh and minimally processed fruit and vegetables → 5) are
   **not** implemented. They are rules about how a *product* is sold and
   processed, not about a dish, and a recipe made of fresh produce scores
   close to 5 on the calculator anyway.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
from dora_api.domain.rating_tables import points_for


# The guide's Category 2 — "all foods other than those included in Category 1,
# 1D, 2D, 3 or 3D". See the module docstring for why it's the only one here.
CATEGORY_2 = "2"

# kcal → kJ lives in `rating_tables` (both schemes score kJ).


# ── Baseline points ─────────────────────────────────────────────────────
# Guide Table 1: "HSR baseline points for Category 1D, 2 and 2D products".
#
# Each tuple is (points, threshold) and the rule the guide states is
# **strictly greater than** the threshold — row 0 is "≤ first threshold", every
# later row is "> this". So the score is the highest row whose threshold the
# value exceeds. The ceilings differ per nutrient and that is not a
# transcription slip: energy stops at 11, sugars at 25, saturated fat and
# sodium at 30.
_BASELINE_ENERGY_KJ: Tuple[Tuple[int, float], ...] = (
    (1, 335), (2, 670), (3, 1005), (4, 1340), (5, 1675), (6, 2010),
    (7, 2345), (8, 2680), (9, 3015), (10, 3350), (11, 3685),
)
_BASELINE_SATURATED_FAT_G: Tuple[Tuple[int, float], ...] = (
    (1, 1.0), (2, 2.0), (3, 3.0), (4, 4.0), (5, 5.0), (6, 6.0), (7, 7.0),
    (8, 8.0), (9, 9.0), (10, 10.0), (11, 11.2), (12, 12.5), (13, 13.9),
    (14, 15.5), (15, 17.3), (16, 19.3), (17, 21.6), (18, 24.1), (19, 26.9),
    (20, 30.0), (21, 33.5), (22, 37.4), (23, 41.7), (24, 46.6), (25, 52.0),
    (26, 58.0), (27, 64.7), (28, 72.3), (29, 80.6), (30, 90.0),
)
_BASELINE_TOTAL_SUGARS_G: Tuple[Tuple[int, float], ...] = (
    (1, 5.0), (2, 8.9), (3, 12.8), (4, 16.8), (5, 20.7), (6, 24.6), (7, 28.5),
    (8, 32.4), (9, 36.3), (10, 40.3), (11, 44.2), (12, 48.1), (13, 52.0),
    (14, 55.9), (15, 59.8), (16, 63.8), (17, 67.7), (18, 71.6), (19, 75.5),
    (20, 79.4), (21, 83.3), (22, 87.3), (23, 91.2), (24, 95.1), (25, 99.0),
)
_BASELINE_SODIUM_MG: Tuple[Tuple[int, float], ...] = (
    (1, 90), (2, 180), (3, 270), (4, 360), (5, 450), (6, 540), (7, 630),
    (8, 720), (9, 810), (10, 900), (11, 990), (12, 1080), (13, 1170),
    (14, 1260), (15, 1350), (16, 1440), (17, 1530), (18, 1620), (19, 1710),
    (20, 1800), (21, 1890), (22, 1980), (23, 2070), (24, 2160), (25, 2250),
    (26, 2340), (27, 2430), (28, 2520), (29, 2610), (30, 2700),
)

# ── Modifying points ────────────────────────────────────────────────────
# Guide Table 4, Column 2 — "% non-concentrated fvnl", capped at 8 for
# Category 2. Column 1 (concentrated fruits or vegetables) is deliberately not
# implemented: it applies only when a product's fruit/veg content is *all*
# concentrated, which is a claim about a manufactured product's formulation.
# Treating everything as non-concentrated is the conservative reading — it
# scores a recipe no better than it deserves.
#
# Row 0 is "≤40"; rows 1–7 are ">"; row 8 is "=100", which is why it can't be
# expressed as another ">" row and is handled separately in `_v_points`.
_V_POINTS_NON_CONCENTRATED: Tuple[Tuple[int, float], ...] = (
    (1, 40), (2, 60), (3, 67), (4, 75), (5, 80), (6, 90), (7, 95),
)
V_POINTS_MAX = 8

# Guide Table 6 — protein and fibre, max 15 each.
#
# The protein row for 2 points is "≥3.2" in the guide where every other row is
# ">". Transcribed as published rather than smoothed: at exactly 3.2 g the
# guide gives 2 points, not 1.
_P_POINTS_PROTEIN_G: Tuple[Tuple[int, float, bool], ...] = (
    (1, 1.6, False), (2, 3.2, True), (3, 4.8, False), (4, 6.4, False),
    (5, 8.0, False), (6, 9.6, False), (7, 11.6, False), (8, 13.9, False),
    (9, 16.7, False), (10, 20.0, False), (11, 24.0, False), (12, 28.9, False),
    (13, 34.7, False), (14, 41.6, False), (15, 50.0, False),
)
_F_POINTS_FIBRE_G: Tuple[Tuple[int, float], ...] = (
    (1, 0.9), (2, 1.9), (3, 2.8), (4, 3.7), (5, 4.7), (6, 5.4), (7, 6.3),
    (8, 7.3), (9, 8.4), (10, 9.7), (11, 11.2), (12, 13.0), (13, 15.0),
    (14, 17.3), (15, 20.0),
)

# Guide Step 5.1, stated twice (Step 5 summary and the note under Table 4):
# "Products that score ≥13 HSR baseline points are not permitted to score
# points for protein unless they score five or more HSR V points."
#
# This is the rule that makes FVNL load-bearing rather than a bonus. Without an
# FVNL figure an energy-dense dish scores zero V points, which then locks out
# its protein credit entirely — so a vegetable-heavy stir fry and a sausage
# roll land far closer together than they should. It is the reason the food
# category is imported at all.
PROTEIN_GATE_BASELINE_POINTS = 13
PROTEIN_GATE_MIN_V_POINTS = 5

# Guide Table 7, Category 2 column, read as (minimum score, rating) descending.
# The guide's bands are contiguous integers: ≤-11 → 5.0, -10..-7 → 4.5,
# -6..-2 → 4.0, -1..2 → 3.5, 3..6 → 3.0, 7..11 → 2.5, 12..15 → 2.0,
# 16..20 → 1.5, 21..24 → 1.0, ≥25 → 0.5.
_STAR_BANDS_CATEGORY_2: Tuple[Tuple[int, float], ...] = (
    (25, 0.5), (21, 1.0), (16, 1.5), (12, 2.0), (7, 2.5),
    (3, 3.0), (-1, 3.5), (-6, 4.0), (-10, 4.5),
)
_STAR_BEST = 5.0


@dataclass(frozen=True, slots=True)
class NutrientProfile:
    """What a rating is computed from: the composition of 100 g of the food.

    Every field is nullable because a source can know a food's protein and not
    its fibre. A `None` scores **zero points** for that component, which is the
    only defensible default — but note it is not symmetric in effect: a missing
    baseline nutrient flatters the food, while a missing modifying nutrient
    penalises it. That asymmetry is exactly why the caller must report per
    nutrient how much of the recipe's weight was actually known, and why the
    rating carries that coverage with it rather than standing alone.
    """
    energy_kj: Optional[float]
    saturated_fat_g: Optional[float]
    total_sugars_g: Optional[float]
    sodium_mg: Optional[float]
    protein_g: Optional[float]
    fibre_g: Optional[float]
    # Percentage (0–100) of the food's weight that is fruit, vegetables, nuts
    # or legumes. `None` and 0.0 both score zero V points; they are kept
    # distinct so the caller can tell "no FVNL in this dish" from "we could not
    # tell", and say so.
    fvnl_percent: Optional[float]


@dataclass(frozen=True, slots=True)
class HealthStarRating:
    """A rating with every intermediate the guide names, so the UI can show its
    working rather than assert a number."""
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
    # False when the ≥13-baseline / <5-V gate suppressed the protein credit.
    # Surfaced because "your protein didn't count, and here's why" is the one
    # part of the result that reads as a bug when it isn't.
    protein_counted: bool


def _protein_points(value: Optional[float]) -> int:
    """As `_points_for`, but Table 6's 2-point protein row is `≥`, not `>`."""
    if value is None:
        return 0
    points = 0
    for row_points, threshold, inclusive in _P_POINTS_PROTEIN_G:
        if value >= threshold if inclusive else value > threshold:
            points = row_points
        else:
            break
    return points


def _v_points(fvnl_percent: Optional[float]) -> int:
    """Table 4, Column 2. The top row is `=100`, not `>95`, so a dish has to be
    entirely fruit/veg/nut/legume to score the full 8."""
    if fvnl_percent is None:
        return 0
    if fvnl_percent >= 100:
        return V_POINTS_MAX
    return points_for(fvnl_percent, _V_POINTS_NON_CONCENTRATED)


def rate(profile: NutrientProfile) -> HealthStarRating:
    """Score a per-100g nutrient profile as a Category 2 food.

    Steps 4–7 of the guide, in order: baseline points, modifying points, the
    protein gate, `score = baseline − V − P − F`, then Table 7.
    """
    energy = points_for(profile.energy_kj, _BASELINE_ENERGY_KJ)
    saturated_fat = points_for(profile.saturated_fat_g, _BASELINE_SATURATED_FAT_G)
    total_sugars = points_for(profile.total_sugars_g, _BASELINE_TOTAL_SUGARS_G)
    sodium = points_for(profile.sodium_mg, _BASELINE_SODIUM_MG)
    baseline = energy + saturated_fat + total_sugars + sodium

    v_points = _v_points(profile.fvnl_percent)
    fibre_points = points_for(profile.fibre_g, _F_POINTS_FIBRE_G)

    protein_counted = (
        baseline < PROTEIN_GATE_BASELINE_POINTS
        or v_points >= PROTEIN_GATE_MIN_V_POINTS
    )
    protein_points = _protein_points(profile.protein_g) if protein_counted else 0

    score = baseline - v_points - protein_points - fibre_points
    return HealthStarRating(
        stars = stars_for_score(score),
        score = score,
        baseline_points = baseline,
        energy_points = energy,
        saturated_fat_points = saturated_fat,
        total_sugars_points = total_sugars,
        sodium_points = sodium,
        v_points = v_points,
        protein_points = protein_points,
        fibre_points = fibre_points,
        protein_counted = protein_counted,
    )


def stars_for_score(score: int) -> float:
    """Table 7, Category 2. Bands are contiguous, so the first band whose floor
    the score reaches wins, walking worst-first."""
    for minimum, stars in _STAR_BANDS_CATEGORY_2:
        if score >= minimum:
            return stars
    return _STAR_BEST
