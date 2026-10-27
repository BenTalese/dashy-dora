"""Unit tests for the Health Star Rating algorithm.

The value of this file is that it pins a **transcription**. `domain/
health_star_rating.py` is a copy of published FSANZ tables (Calculator and
Style Guide v8.1, Tables 1/4/6/7); the risk is not that the code is subtly
wrong, it's that a threshold was typed wrong, an inequality is `>` where the
guide says `≥`, or a band edge is off by one. So these tests hammer the
boundaries rather than the middles: every assertion below is a value sitting
exactly on a published threshold, or one step either side of it.
"""
import pytest

from dora_api.domain.health_star_rating import (
    PROTEIN_GATE_BASELINE_POINTS,
    PROTEIN_GATE_MIN_V_POINTS,
    V_POINTS_MAX,
    NutrientProfile,
    rate,
    stars_for_score,
)
from dora_api.domain.rating_tables import KJ_PER_KCAL, kcal_to_kj


def _profile(**overrides) -> NutrientProfile:
    """A nutritionally blank food — every component scores zero — so a test can
    vary exactly one axis and read the effect of that axis alone."""
    base = dict(
        energy_kj = 0.0,
        saturated_fat_g = 0.0,
        total_sugars_g = 0.0,
        sodium_mg = 0.0,
        protein_g = 0.0,
        fibre_g = 0.0,
        fvnl_percent = 0.0,
    )
    base.update(overrides)
    return NutrientProfile(**base)


# ── Baseline points: Table 1 boundaries ─────────────────────────────────

@pytest.mark.parametrize("energy_kj,expected", [
    (335, 0),      # row 0 is "≤335"
    (335.1, 1),    # row 1 is ">335"
    (670, 1),
    (670.1, 2),
    (3685, 10),
    (3685.1, 11),
    (99_999, 11),  # energy caps at 11 points, unlike sat fat and sodium
])
def test__energy_points__sit_on_the_published_band_edges(energy_kj, expected):
    assert rate(_profile(energy_kj=energy_kj)).energy_points == expected


@pytest.mark.parametrize("saturated_fat_g,expected", [
    (1.0, 0), (1.01, 1),
    (11.2, 10), (11.21, 11),   # the table stops being linear here
    (90.0, 29), (90.1, 30),
    (500.0, 30),               # saturated fat caps at 30
])
def test__saturated_fat_points__sit_on_the_published_band_edges(saturated_fat_g, expected):
    assert rate(_profile(saturated_fat_g=saturated_fat_g)).saturated_fat_points == expected


@pytest.mark.parametrize("total_sugars_g,expected", [
    (5.0, 0), (5.01, 1),
    (8.9, 1), (8.91, 2),
    (99.0, 24), (99.01, 25),
    (100.0, 25),               # total sugars caps at 25
])
def test__total_sugars_points__sit_on_the_published_band_edges(total_sugars_g, expected):
    assert rate(_profile(total_sugars_g=total_sugars_g)).total_sugars_points == expected


@pytest.mark.parametrize("sodium_mg,expected", [
    (90, 0), (91, 1),
    (900, 9), (901, 10),
    (2700, 29), (2701, 30),
    (10_000, 30),              # sodium caps at 30
])
def test__sodium_points__sit_on_the_published_band_edges(sodium_mg, expected):
    assert rate(_profile(sodium_mg=sodium_mg)).sodium_points == expected


def test__baseline_points__is_the_sum_of_the_four_components():
    rating = rate(_profile(
        energy_kj = 1500,      # 4
        saturated_fat_g = 5.5,  # 5
        total_sugars_g = 10.0,  # 2
        sodium_mg = 500,        # 5
    ))
    assert (rating.energy_points, rating.saturated_fat_points,
            rating.total_sugars_points, rating.sodium_points) == (4, 5, 2, 5)
    assert rating.baseline_points == 16


# ── Modifying points: Tables 4 and 6 ────────────────────────────────────

@pytest.mark.parametrize("fvnl_percent,expected", [
    (40, 0), (40.1, 1),
    (60, 1), (60.1, 2),
    (80, 4), (80.1, 5),
    (95, 6), (95.1, 7),
    (99.9, 7),                 # the top row is "=100", not ">95"
    (100, V_POINTS_MAX),
])
def test__v_points__top_row_requires_exactly_100_percent(fvnl_percent, expected):
    assert rate(_profile(fvnl_percent=fvnl_percent)).v_points == expected


@pytest.mark.parametrize("protein_g,expected", [
    (1.6, 0), (1.61, 1),
    # Table 6's 2-point protein row is "≥3.2" where every other row is ">".
    # Exactly 3.2 must score 2, not 1 — this is the one asymmetry in the table
    # and the easiest thing in the file to transcribe wrongly.
    (3.2, 2),
    (3.19, 1),
    (50.0, 14), (50.01, 15),
    (200.0, 15),               # protein caps at 15
])
def test__protein_points__respect_the_inclusive_two_point_row(protein_g, expected):
    assert rate(_profile(protein_g=protein_g)).protein_points == expected


@pytest.mark.parametrize("fibre_g,expected", [
    (0.9, 0), (0.91, 1),
    (4.7, 4), (4.71, 5),
    (20.0, 14), (20.01, 15),
    (100.0, 15),               # fibre caps at 15
])
def test__fibre_points__sit_on_the_published_band_edges(fibre_g, expected):
    assert rate(_profile(fibre_g=fibre_g)).fibre_points == expected


# ── The protein gate ────────────────────────────────────────────────────
# "Products that score ≥13 HSR baseline points are not permitted to score
# points for protein unless they score five or more HSR V points."

def test__protein_gate__below_thirteen_baseline_points_protein_always_counts():
    # 12 baseline points (sodium alone), no FVNL at all.
    rating = rate(_profile(sodium_mg=1100, protein_g=25.0))
    assert rating.baseline_points == PROTEIN_GATE_BASELINE_POINTS - 1
    assert rating.v_points == 0
    assert rating.protein_counted is True
    assert rating.protein_points == 11


def test__protein_gate__at_thirteen_baseline_points_without_fvnl_protein_is_locked_out():
    rating = rate(_profile(sodium_mg=1200, protein_g=25.0))
    assert rating.baseline_points == PROTEIN_GATE_BASELINE_POINTS
    assert rating.v_points == 0
    assert rating.protein_counted is False
    assert rating.protein_points == 0


def test__protein_gate__five_v_points_unlocks_protein_at_high_baseline():
    # Same food as above, but 81% of it is vegetables → 5 V points, which is
    # exactly the published threshold that reopens the protein credit.
    rating = rate(_profile(sodium_mg=1200, protein_g=25.0, fvnl_percent=81))
    assert rating.baseline_points >= PROTEIN_GATE_BASELINE_POINTS
    assert rating.v_points == PROTEIN_GATE_MIN_V_POINTS
    assert rating.protein_counted is True
    assert rating.protein_points == 11


def test__protein_gate__four_v_points_is_not_enough():
    rating = rate(_profile(sodium_mg=1200, protein_g=25.0, fvnl_percent=76))
    assert rating.v_points == PROTEIN_GATE_MIN_V_POINTS - 1
    assert rating.protein_counted is False
    assert rating.protein_points == 0


def test__protein_gate__is_why_fvnl_matters_to_the_ranking():
    """The whole reason the food category is imported: without an FVNL figure a
    rich-but-wholesome dish is scored as if it were a rich one."""
    dense_and_savoury = dict(
        energy_kj = 1400, saturated_fat_g = 6.0, total_sugars_g = 6.0,
        sodium_mg = 700, protein_g = 12.0, fibre_g = 6.0,
    )
    unknown_fvnl = rate(_profile(**dense_and_savoury, fvnl_percent=None))
    known_fvnl = rate(_profile(**dense_and_savoury, fvnl_percent=85))
    assert unknown_fvnl.protein_counted is False
    assert known_fvnl.protein_counted is True
    assert known_fvnl.stars > unknown_fvnl.stars


# ── Final score and Table 7 ─────────────────────────────────────────────

def test__score__is_baseline_minus_every_modifying_point():
    rating = rate(_profile(
        energy_kj = 1400,       # 4
        saturated_fat_g = 2.5,  # 2
        total_sugars_g = 6.0,   # 1
        sodium_mg = 300,        # 3   → baseline 10, so the gate is open
        fvnl_percent = 68,      # 3
        protein_g = 9.0,        # 5
        fibre_g = 5.0,          # 5
    ))
    assert rating.baseline_points == 10
    assert (rating.v_points, rating.protein_points, rating.fibre_points) == (3, 5, 5)
    assert rating.score == 10 - 3 - 5 - 5 == -3
    assert rating.stars == 4.0


@pytest.mark.parametrize("score,stars", [
    (-50, 5.0), (-11, 5.0),
    (-10, 4.5), (-7, 4.5),
    (-6, 4.0), (-2, 4.0),
    (-1, 3.5), (2, 3.5),
    (3, 3.0), (6, 3.0),
    (7, 2.5), (11, 2.5),
    (12, 2.0), (15, 2.0),
    (16, 1.5), (20, 1.5),
    (21, 1.0), (24, 1.0),
    (25, 0.5), (99, 0.5),
])
def test__stars_for_score__matches_every_table_7_band_edge(score, stars):
    assert stars_for_score(score) == stars


def test__table_7_bands__are_contiguous_with_no_gap_or_overlap():
    """Walking the whole plausible score range must produce a monotonically
    non-increasing star rating — a transposed band edge would show up as a
    rating that goes back up as the food gets worse."""
    ratings = [stars_for_score(score) for score in range(-50, 100)]
    assert ratings == sorted(ratings, reverse=True)
    assert set(ratings) == {0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0}


# ── Missing data ────────────────────────────────────────────────────────

def test__missing_nutrients__score_zero_points_each():
    """`None` is not an error and not a guess — it simply earns nothing. The
    asymmetry (a missing *baseline* nutrient flatters the food, a missing
    *modifying* one penalises it) is why the caller reports coverage."""
    blank = rate(NutrientProfile(None, None, None, None, None, None, None))
    assert blank.baseline_points == 0
    assert (blank.v_points, blank.protein_points, blank.fibre_points) == (0, 0, 0)
    assert blank.score == 0
    # Table 7 puts a score of 0 in the -1..2 band. Worth stating: a food we
    # know *nothing* about lands mid-range rather than at either extreme,
    # which is why the rating must never render without its coverage.
    assert blank.stars == 3.5


def test__missing_sugars_flatters_the_food():
    """The measured gap in USDA SR Legacy (sugars known for ~77% of foods), as
    an assertion: the same dish scores better when its sugar is unknown, which
    is precisely why the UI has to report per-nutrient coverage rather than
    present the rating as complete."""
    known = rate(_profile(energy_kj=1400, total_sugars_g=30.0))
    unknown = rate(_profile(energy_kj=1400, total_sugars_g=None))
    assert unknown.stars > known.stars


# ── Energy conversion ───────────────────────────────────────────────────

def test__kcal_to_kj__uses_the_food_labelling_factor():
    assert kcal_to_kj(100) == pytest.approx(418.4)
    assert kcal_to_kj(None) is None
    assert KJ_PER_KCAL == 4.184


def test__kcal_to_kj__feeds_the_energy_table_at_the_right_scale():
    """A 400 kcal/100g food is ~1674 kJ — one band below the >1675 edge. Getting
    the conversion wrong by a factor of ten would be invisible in a unit test of
    the conversion alone, but moves this food five bands."""
    rating = rate(_profile(energy_kj=kcal_to_kj(400)))
    assert rating.energy_points == 4
