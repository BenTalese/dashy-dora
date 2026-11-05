"""FU-876 / FU-983: an item's price basis is the one most observations are on,
and a count of packs of unknown size is its own basis."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dora_api.domain.entities.stock_item_price_observation import \
    StockItemPriceObservation
from dora_api.features.stock_items.your_prices import (
    PriceBasis, _baseline_from_observations, active_price_basis)

_NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)


def _obs(unit: str, days_ago: int, *, price: float = 4.0, measure: float = 1.0,
         sizeless: bool = False) -> StockItemPriceObservation:
    when = _NOW - timedelta(days=days_ago)
    return StockItemPriceObservation(
        stock_item_id=uuid4(), total_price=price, total_measure=measure, unit=unit,
        observed_at=when, store_id=None, shopping_list_line_id=None, created_at=when,
        is_sizeless=sizeless,
    )


def test__active_price_basis__majority_beats_a_newer_stray():
    observations = [_obs("kg", days) for days in range(2, 11)] + [_obs("ea", 0)]
    assert active_price_basis(observations) == PriceBasis("mass", sizeless=False)


def test__active_price_basis__tie_goes_to_the_newest():
    assert active_price_basis([_obs("kg", 3), _obs("ea", 1)]) == PriceBasis("count", sizeless=False)


def test__active_price_basis__none_without_observations():
    assert active_price_basis([]) is None


def test__active_price_basis__loose_and_sized_counts_are_different_bases():
    observations = [
        _obs("ea", 1, price=6.0, measure=1.0, sizeless=True),
        _obs("ea", 5, price=6.0, measure=12.0),
        _obs("ea", 9, price=6.5, measure=12.0),
    ]
    assert active_price_basis(observations) == PriceBasis("count", sizeless=False)


def test__your_prices__a_loose_carton_does_not_enter_the_per_egg_baseline():
    # Three sized cartons at about 50c an egg, then one logged loose at $6.
    observations = [
        _obs("ea", 1, price=6.0, measure=1.0, sizeless=True),
        _obs("ea", 10, price=6.0, measure=12.0),
        _obs("ea", 20, price=6.0, measure=12.0),
        _obs("ea", 30, price=6.6, measure=12.0),
    ]
    result = _baseline_from_observations(None, observations, now=_NOW, system="metric")
    assert result.sample_count == 3
    assert result.current is not None and result.current < 1.0


def test__your_prices__a_cheap_shop_is_less_than_usual_and_says_how_sure():
    """FU-707: good news gets its own flag, a thin history is marked rough,
    and prices on another basis are counted as left out."""
    observations = [
        _obs("ea", 1, price=4.0, measure=12.0),
        _obs("ea", 10, price=6.0, measure=12.0),
        _obs("ea", 20, price=6.0, measure=12.0),
        _obs("ea", 30, price=6.0, measure=12.0),
        _obs("kg", 40, price=9.0, measure=1.0),
    ]
    result = _baseline_from_observations(None, observations, now=_NOW, system="metric")
    assert result.below_baseline is True
    assert result.above_baseline is False
    assert result.rough is True
    assert result.left_out_count == 1
