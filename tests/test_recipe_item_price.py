"""`recipe_cost._item_price` — the price of one countable item.

Owner-reported 2026-09-03: a recipe calling for "3 yolks" of an ingredient
linked to *Woolworths Free Range Eggs 12pk* (700 g, $5.50) was costed at
**$16.50** — three whole cartons — off a shelf price the breakdown displayed
as $7.86/kg. The estimator had been treating every pack as exactly one
countable thing, which is true of a tin and false of a carton of eggs, and
nothing in the arithmetic distinguished them.

These pin the replacement rule: a bare count can be priced only when the data
actually says how many items are in the pack, and is reported unpriced
otherwise. The end-to-end behaviour (the `unit_mismatch` line and the "N of M
priced" ratio it drives) is covered in `tests/e2e/dora_api/test_recipe_router`.
"""
import pytest

from dora_api.features.recipes.recipe_cost import _item_price


def test__multipack_count_divides_the_pack_price():
    # "4 × 125 g at $4.20" — the count is recorded, so one item is $1.05.
    assert _item_price(4.20, 500.0, "g", 4) == pytest.approx(1.05)


def test__the_reported_egg_carton_is_now_priceable():
    # The seed's 12pk, with `pack_count` recorded: 3 eggs cost $1.375, not the
    # $16.50 the owner was shown.
    assert _item_price(5.50, 700.0, "g", 12) == pytest.approx(5.50 / 12)


def test__a_measured_pack_with_no_count_is_unknowable():
    # Nothing here says how many eggs are in 700 g, so there is no honest
    # per-item price. This is the regression: it used to answer $5.50.
    assert _item_price(5.50, 700.0, "g", None) is None
    assert _item_price(6.00, 2.0, "L", None) is None


def test__a_sizeless_product_is_its_own_item():
    assert _item_price(4.00, None, None, None) == pytest.approx(4.00)
    assert _item_price(4.00, 0.0, "", None) == pytest.approx(4.00)


def test__a_count_sized_pack_divides_by_the_count():
    assert _item_price(6.00, 1.0, "ea", None) == pytest.approx(6.00)
    assert _item_price(6.00, 12.0, "ea", None) == pytest.approx(0.50)


def test__a_dozen_is_twelve_of_them_not_one():
    # `dozen` carries a factor of 12, so "$6.00 for 1 dozen" is $0.50 an item.
    # Selling the whole dozen for the price of one was the same bug one scale
    # down, and it survived in the price-observation path too.
    assert _item_price(6.00, 1.0, "dozen", None) == pytest.approx(0.50)


def test__pack_count_wins_over_the_size_unit():
    # Both recorded: the explicit count is the more specific fact.
    assert _item_price(6.00, 12.0, "ea", 6) == pytest.approx(1.00)


def test__an_observation_with_a_pack_count_yields_an_item_price():
    # FU-856: "$5.50 for 12 eggs, 700 g" logged through the price sheet's
    # multipack field. The count used to be display-only, so 3 eggs stayed
    # unpriced against an observation that said exactly how many there were.
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from dora_api.domain.stock_status import get_stock_item_unit_cost_with_unit_at

    obs = SimpleNamespace(total_price=5.50, total_measure=700.0, unit="g",
                          observed_at=datetime.now(UTC), pack_count=12)
    cost = get_stock_item_unit_cost_with_unit_at([obs])

    assert cost.item_price == pytest.approx(5.50 / 12)

    obs.pack_count = None
    assert get_stock_item_unit_cost_with_unit_at([obs]).item_price is None


def test__an_observation_with_a_pack_count_yields_the_whole_pack_price():
    # QA2-18: "$5.50 for 12 eggs, 700 g" is one carton, so "1 pack" is $5.50.
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from dora_api.domain.stock_status import get_stock_item_unit_cost_with_unit_at

    obs = SimpleNamespace(total_price=5.50, total_measure=700.0, unit="g",
                          observed_at=datetime.now(UTC), pack_count=12)
    assert get_stock_item_unit_cost_with_unit_at([obs]).pack_price == pytest.approx(5.50)

    obs.pack_count = None   # may span several packs: unknown
    assert get_stock_item_unit_cost_with_unit_at([obs]).pack_price is None
