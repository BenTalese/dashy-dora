"""Hypothesis property tests for the pure domain modules (FU-520 item 4,
PROPOSAL_TEST_SUITE_IMPROVEMENTS §5.F).

The golden-value tests (test_recipe_cookability.py / test_stock_status.py /
test_product_offer.py / test_units.py) pin specific decided examples; these
tests pin the *invariants* — statements that must hold for every input, so
Hypothesis can hunt the edges (dedup collisions, band boundaries, rounding,
float round-trips) that examples miss.

Determinism: no wall-clock reads anywhere — the datetime strategy is bounded
to a pinned 2024–2026 window and values are only compared among themselves.
All strategies are bounded (small pools / bounded floats) so shrinking stays
fast; default Hypothesis profile, no deadline overrides.

Pure Python: imports only ``dora_api.domain.*``, stdlib, and hypothesis —
no DB, no HTTP, no Flask app.
"""
from __future__ import annotations

import math
from datetime import datetime
from types import SimpleNamespace

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from dora_api.domain import units
from dora_api.domain.product_offer import discount_percent
from dora_api.domain.recipe_cookability import (cookability_state,
                                                missing_count_for,
                                                missing_stock_item_names_for,
                                                unlinked_count_for)
from dora_api.domain.stock_status import (EXPIRING_SOON_WINDOW_DAYS,
                                          LOW_STOCK_SEQUENCE,
                                          OUT_OF_STOCK_SEQUENCE, StockStatus,
                                          effective_expiring_soon_window,
                                          get_stock_item_unit_cost_with_unit_at,
                                          is_low_stock, is_missing,
                                          is_out_of_stock, level_for_status,
                                          needs_restock, status_for)

# ═══════════════════════════════════════════════════════════════════════════
# Shared strategies — duck-typed stubs mirroring the entity shapes the domain
# modules read (sequence / stock_level / stock_item / is_optional).
# ═══════════════════════════════════════════════════════════════════════════

# Levels: None (no stock record) or a sequence 0..4 — covers all three seeded
# bands plus the beyond-the-worst clamp zone.
_levels = st.one_of(
    st.none(),
    st.builds(lambda seq: SimpleNamespace(sequence=seq), st.integers(0, 4)),
)

# Small id/name pools so duplicate stock items (the dedup rules) are common.
_stock_items = st.builds(
    lambda i, name, level: SimpleNamespace(id=i, name=name, stock_level=level),
    st.integers(0, 5),
    st.sampled_from(["apple", "beet", "corn", "daal", "egg"]),
    _levels,
)

_ingredients = st.builds(
    lambda item, optional: SimpleNamespace(stock_item=item, is_optional=optional),
    st.one_of(st.none(), _stock_items),  # None = unlinked ingredient
    st.booleans(),
)

_ingredient_lists = st.lists(_ingredients, max_size=8)


def _required(ingredients):
    """Test-side notion of 'required' (stubs always carry is_optional)."""
    return [i for i in ingredients if not i.is_optional]


# ═══════════════════════════════════════════════════════════════════════════
# recipe_cookability
# ═══════════════════════════════════════════════════════════════════════════


@given(_ingredient_lists)
def test__cookability_state__property__cookable_implies_every_required_ingredient_in_stock(ings):
    """The canonical invariant: cookable ⇒ every required ingredient is
    linked to a stock item that is not missing."""
    if cookability_state(ings) is True:
        for ing in _required(ings):
            assert ing.stock_item is not None
            assert not is_missing(ing.stock_item.stock_level)


@given(_ingredient_lists)
def test__cookability_state__property__none_iff_some_required_ingredient_unlinked(ings):
    """Tri-state None fires exactly when a required ingredient is unlinked
    (IMPL_PLAN_RECIPE_IMPORTER §Chunk 4) — and agrees with unlinked_count_for."""
    any_unlinked = any(i.stock_item is None for i in _required(ings))
    assert (cookability_state(ings) is None) == any_unlinked
    assert (unlinked_count_for(ings) > 0) == any_unlinked


@given(_ingredient_lists, st.lists(_ingredients, max_size=4))
def test__cookability__property__optional_ingredients_are_inert(ings, extras):
    """§1.9 — optional ingredients are ignored *entirely*: appending any
    number of optional rows (missing, unlinked, whatever) changes nothing."""
    optional_extras = [
        SimpleNamespace(stock_item=e.stock_item, is_optional=True) for e in extras
    ]
    augmented = ings + optional_extras
    assert cookability_state(augmented) == cookability_state(ings)
    assert (missing_count_for(augmented) == 0) == (missing_count_for(ings) == 0)
    assert missing_count_for(augmented) == missing_count_for(ings)
    assert unlinked_count_for(augmented) == unlinked_count_for(ings)
    assert missing_stock_item_names_for(augmented) == missing_stock_item_names_for(ings)


@given(_ingredient_lists, _ingredients)
def test__cookability__property__adding_an_ingredient_never_improves_cookability(ings, extra):
    """Monotonicity: an extra ingredient can only keep or worsen the answer —
    missing_count never drops, and if the bigger recipe is cookable the
    smaller one must have been too."""
    augmented = ings + [extra]
    assert missing_count_for(augmented) >= missing_count_for(ings)
    if cookability_state(augmented) is True:
        assert cookability_state(ings) is True


@given(_ingredient_lists)
def test__cookability__property__restocking_every_missing_item_clears_missing(ings):
    """Restock monotonicity: replace every missing level with Stocked
    (sequence 0) and nothing can still be missing; cookability can only be
    True or None (unlinked rows are untouched by restocking)."""
    def _restock(ing):
        item = ing.stock_item
        if item is None or not is_missing(item.stock_level):
            return ing
        return SimpleNamespace(
            stock_item=SimpleNamespace(
                id=item.id, name=item.name, stock_level=SimpleNamespace(sequence=0)
            ),
            is_optional=ing.is_optional,
        )

    restocked = [_restock(i) for i in ings]
    assert missing_count_for(restocked) == 0
    assert missing_stock_item_names_for(restocked) == []
    assert cookability_state(restocked) in (True, None)


@given(_ingredient_lists)
def test__cookability__property__missing_names_sorted_distinct_and_grounded(ings):
    """The names list is alphabetised, duplicate-free, and every entry is the
    name of some required, linked, missing ingredient; empty when cookable."""
    names = missing_stock_item_names_for(ings)
    assert names == sorted(names)
    assert len(names) == len(set(names))
    missing_required_names = {
        i.stock_item.name
        for i in _required(ings)
        if i.stock_item is not None and is_missing(i.stock_item.stock_level)
    }
    assert set(names) == missing_required_names
    if cookability_state(ings) is True:
        assert names == []


@given(_ingredient_lists)
def test__cookability__property__tri_state_agrees_with_bool_when_fully_linked(ings):
    """When no required ingredient is unlinked, the tri-state answer collapses
    to the legacy boolean predicate."""
    assume(unlinked_count_for(ings) == 0)
    assert cookability_state(ings) is (missing_count_for(ings) == 0)


# ═══════════════════════════════════════════════════════════════════════════
# stock_status
# ═══════════════════════════════════════════════════════════════════════════

# Wider sequence range than the seeded 0..2: negatives (undefined) and
# beyond-the-worst values (clamp zone) included on purpose.
_wide_levels = st.one_of(
    st.none(),
    st.builds(lambda seq: SimpleNamespace(sequence=seq), st.integers(-3, 10)),
)


@given(_wide_levels)
def test__stock_status__property__predicates_cohere_with_status_for(level):
    """All predicates are projections of one status: they may never disagree
    with status_for, whatever the sequence (None, negative, clamped)."""
    status = status_for(level)
    assert is_out_of_stock(level) == (status is StockStatus.OUT_OF_STOCK)
    assert is_low_stock(level) == (status is StockStatus.LOW_STOCK)
    assert needs_restock(level) == (
        status in (StockStatus.LOW_STOCK, StockStatus.OUT_OF_STOCK)
    )
    assert is_missing(level) == (level is None or status is StockStatus.OUT_OF_STOCK)


@given(st.integers(0, 10), st.integers(0, 10))
def test__stock_status__property__band_predicates_monotone_in_sequence(seq_a, seq_b):
    """Worsening the ordinal never improves the band: once a sequence needs
    restock / is out of stock / is missing, every worse sequence does too."""
    lo, hi = sorted((seq_a, seq_b))
    better = SimpleNamespace(sequence=lo)
    worse = SimpleNamespace(sequence=hi)
    if needs_restock(better):
        assert needs_restock(worse)
    if is_out_of_stock(better):
        assert is_out_of_stock(worse)
    if is_missing(better):
        assert is_missing(worse)


@given(st.integers(0, 50))
def test__stock_status__property__status_for_total_over_defined_sequences(seq):
    """Every non-negative sequence maps to *some* status — the ≥-worst clamp
    means a future-inserted level can never silently read as 'no status'."""
    status = status_for(SimpleNamespace(sequence=seq))
    assert isinstance(status, StockStatus)
    if seq >= OUT_OF_STOCK_SEQUENCE:
        assert status is StockStatus.OUT_OF_STOCK
    elif seq == LOW_STOCK_SEQUENCE:
        assert status is StockStatus.LOW_STOCK
    else:
        assert status is StockStatus.STOCKED


@given(
    st.lists(st.builds(lambda s: SimpleNamespace(sequence=s), st.integers(-1, 5)), max_size=8),
    st.sampled_from(sorted(StockStatus)),
)
def test__level_for_status__property__returns_first_sequence_match_or_none(levels, status):
    result = level_for_status(levels, status)
    matches = [lvl for lvl in levels if lvl.sequence == int(status)]
    if matches:
        assert result is matches[0]
    else:
        assert result is None


@given(
    st.one_of(
        st.none(),
        st.integers(-10, 400),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(max_size=5),
    )
)
def test__effective_expiring_soon_window__property__always_positive_int(value):
    """Whatever garbage the AppSetting holds, the resolved window is a
    positive int — a valid positive-int override wins, everything else falls
    back to the single default constant."""
    setting = SimpleNamespace(expiring_soon_window_days=value)
    result = effective_expiring_soon_window(setting)
    assert isinstance(result, int) and result > 0
    if isinstance(value, int) and value > 0:
        assert result == value
    else:
        assert result == EXPIRING_SOON_WINDOW_DAYS
    assert effective_expiring_soon_window(None) == EXPIRING_SOON_WINDOW_DAYS


# Pinned observation window — bounded, wall-clock-free (naive datetimes are
# only ever compared to each other).
_observed_ats = st.datetimes(
    min_value=datetime(2024, 1, 1), max_value=datetime(2026, 1, 1)
)

_observations = st.builds(
    # `unit` joined the shape 2026-08-19: the cost estimator has to know what
    # a price is *per*, so the real observation's unit is now read as well as
    # its ratio. Every stored observation has always carried one.
    lambda price, measure, ts, unit: SimpleNamespace(
        total_price=price, total_measure=measure, observed_at=ts, unit=unit
    ),
    st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    # Mix of usable measures and the zero-measure rows the function must skip.
    st.one_of(st.just(0.0), st.floats(min_value=0.001, max_value=100.0,
                                      allow_nan=False, allow_infinity=False)),
    _observed_ats,
    st.sampled_from(["ea", "g", "kg", "ml", "L"]),
)


def _unit_cost(observations, when):
    priced = get_stock_item_unit_cost_with_unit_at(observations, when)
    return priced.amount if priced is not None else None


@given(st.lists(_observations, max_size=8), _observed_ats)
def test__unit_cost_at__property__observations_after_when_are_invisible(observations, when):
    """`when` is a hard cutoff: the result over the full history equals the
    result over only the at-or-before-`when` slice, and rows with a zero
    measure are inert."""
    visible = [o for o in observations if o.observed_at <= when]
    assert _unit_cost(observations, when) == \
        _unit_cost(visible, None)
    # None exactly when nothing usable is visible.
    usable = [o for o in visible if o.total_measure]
    assert (_unit_cost(observations, when) is None) == (not usable)


@given(st.lists(_observations, max_size=8))
def test__unit_cost_at__property__result_is_latest_usable_observations_ratio(observations):
    """The returned cost is exactly `total_price / total_measure` of the
    most recent usable (non-zero-measure) observation."""
    result = _unit_cost(observations, None)
    usable = [o for o in observations if o.total_measure]
    if not usable:
        assert result is None
    else:
        latest = max(usable, key=lambda o: o.observed_at)
        assert result == latest.total_price / latest.total_measure


# ═══════════════════════════════════════════════════════════════════════════
# product_offer.discount_percent
# ═══════════════════════════════════════════════════════════════════════════

_any_prices = st.one_of(
    st.none(),
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
)
_positive_prices = st.floats(
    min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False
)


@given(_any_prices, _any_prices)
def test__discount_percent__property__result_is_none_or_whole_percent_in_range(now, was):
    result = discount_percent(now, was)
    assert result is None or (isinstance(result, int) and 0 <= result <= 100)


@given(_positive_prices, _positive_prices)
def test__discount_percent__property__defined_iff_genuinely_cheaper(now, was):
    """For positive prices, a percent exists exactly when now < was — never
    for at-or-above RRP."""
    result = discount_percent(now, was)
    assert (result is not None) == (now < was)


@given(_positive_prices, _positive_prices, _positive_prices)
def test__discount_percent__property__lower_price_never_ranks_worse(now_a, now_b, was):
    """Monotone in price_now: against the same RRP, the cheaper offer's
    discount percent is never smaller — the best-deals ranking can't invert."""
    assume(now_a < was and now_b < was)
    lo, hi = sorted((now_a, now_b))
    assert discount_percent(lo, was) >= discount_percent(hi, was)


@given(_positive_prices, _positive_prices, st.integers(-8, 8))
def test__discount_percent__property__invariant_under_currency_rescaling(now, was, exponent):
    """The percent depends only on the now/was ratio: scaling both prices by
    the same factor changes nothing. Powers of two keep the float scaling
    exact, so the assertion can be equality rather than a tolerance."""
    assume(now < was)
    k = 2.0 ** exponent
    assert discount_percent(now * k, was * k) == discount_percent(now, was)


# ═══════════════════════════════════════════════════════════════════════════
# units — conversion round-trips / idempotence
# ═══════════════════════════════════════════════════════════════════════════

_UNITS_BY_DIMENSION: dict[str, list[str]] = {}
for _alias, _udef in units.UNIT_TABLE.items():
    _UNITS_BY_DIMENSION.setdefault(_udef.dimension, []).append(_alias)


@st.composite
def _same_dimension_units(draw, count=2):
    dim = draw(st.sampled_from(sorted(_UNITS_BY_DIMENSION)))
    pool = sorted(_UNITS_BY_DIMENSION[dim])
    return tuple(draw(st.sampled_from(pool)) for _ in range(count))


_amounts = st.floats(
    min_value=1e-3, max_value=1e6, allow_nan=False, allow_infinity=False
)


@given(_amounts, _same_dimension_units())
def test__convert__property__same_dimension_round_trip(amount, pair):
    a, b = pair
    there = units.convert(amount, a, b)
    assert there is not None
    back = units.convert(there, b, a)
    assert back is not None
    assert math.isclose(back, amount, rel_tol=1e-9)


@given(_amounts, st.sampled_from(sorted(units.UNIT_TABLE)))
def test__convert__property__identity_conversion(amount, unit):
    result = units.convert(amount, unit, unit)
    assert result is not None
    assert math.isclose(result, amount, rel_tol=1e-12)


@given(_amounts, _same_dimension_units(count=3))
def test__convert__property__conversion_composes_transitively(amount, triple):
    """a→c gives the same answer as a→b→c (up to float rounding) — the table
    is a consistent single scale per dimension, not pairwise ad-hoc factors."""
    a, b, c = triple
    direct = units.convert(amount, a, c)
    via_b = units.convert(units.convert(amount, a, b), b, c)
    assert direct is not None and via_b is not None
    assert math.isclose(direct, via_b, rel_tol=1e-9)


@given(
    _amounts,
    st.sampled_from(sorted(_UNITS_BY_DIMENSION[units.MASS])),
    st.sampled_from(sorted(_UNITS_BY_DIMENSION[units.VOLUME])),
    st.sampled_from(sorted(units.INGREDIENT_DENSITY_G_PER_ML)),
)
def test__convert__property__mass_volume_density_round_trip(amount, mass_u, vol_u, ingredient):
    there = units.convert(amount, mass_u, vol_u, ingredient=ingredient)
    assert there is not None
    back = units.convert(there, vol_u, mass_u, ingredient=ingredient)
    assert back is not None
    assert math.isclose(back, amount, rel_tol=1e-9)


# FU-524 fixed (2026-07-12): normalise_unit now strips AFTER removing "°", so
# it's idempotent for ALL inputs incl. degree marks — the strategy no longer
# needs to exclude "°".
@given(st.text(max_size=20))
def test__normalise_unit__property__idempotent(raw):
    once = units.normalise_unit(raw)
    assert units.normalise_unit(once) == once


# Regression for the FU-524 fix: a degree mark beside end-of-string whitespace
# canonicalises fully (no re-exposed trailing space) and is idempotent.
def test__normalise_unit__degree_mark_beside_whitespace__idempotent():
    assert units.normalise_unit("gas °") == "gas"
    once = units.normalise_unit("gas °")
    assert units.normalise_unit(once) == once


@given(
    st.integers(0, 1000),
    st.integers(1, 20),
    st.integers(1, 20),
)
def test__parse_amount__property__mixed_fraction_parses_to_whole_plus_fraction(whole, num, den):
    result = units.parse_amount(f"{whole} {num}/{den}")
    assert result is not None
    assert math.isclose(result, whole + num / den, rel_tol=1e-12)


@given(st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False))
def test__parse_amount__property__float_string_round_trips_exactly(value):
    # repr(float) → float is exact in Python, so parse must return the value.
    assert units.parse_amount(value) == value
    assert units.parse_amount(str(value)) == value
