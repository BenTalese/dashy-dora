"""What the two front-of-pack rating schemes (Health Star Rating, Nutri-Score)
share: the threshold-table lookup and the energy conversion. Both score energy
in kilojoules; Dora stores kcal.
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple

# 1 kcal = 4.184 kJ, the food-labelling convention.
#
# Dora stores energy as kcal (`NutritionFood.kcal_per_100g`) because that is
# what the whole app reads; both schemes' tables are in kilojoules. USDA does
# publish a separate kJ row, and importing it would avoid this conversion — but
# it is derived from the same Atwater factors, the two agree to well under a
# percent, and HSR's energy bands are **335 kJ wide**. A sub-1% difference can
# only change the answer for a food sitting exactly on a band edge, which is not
# worth a second energy column and a second thing to keep in step (R-002).
KJ_PER_KCAL = 4.184


def kcal_to_kj(kcal: Optional[float]) -> Optional[float]:
    """The one place the conversion happens (R-003)."""
    return None if kcal is None else kcal * KJ_PER_KCAL


def points_for(value: Optional[float], table: Sequence[Tuple[int, float]]) -> int:
    """The highest row in *table* whose threshold *value* strictly exceeds.

    `None` → 0. Every table's row 0 is "≤ the first threshold", so a value at or
    below it scores nothing and everything above steps up the table.
    """
    if value is None:
        return 0
    points = 0
    for row_points, threshold in table:
        if value > threshold:
            points = row_points
        else:
            break
    return points
