"""FU-876: an item's price dimension is the one most observations are in."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dora_api.domain.entities.stock_item_price_observation import \
    StockItemPriceObservation
from dora_api.features.stock_items.your_prices import active_price_dimension

_NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)


def _obs(unit: str, days_ago: int) -> StockItemPriceObservation:
    when = _NOW - timedelta(days=days_ago)
    return StockItemPriceObservation(
        stock_item_id=uuid4(), total_price=4.0, total_measure=1.0, unit=unit,
        observed_at=when, store_id=None, shopping_list_line_id=None, created_at=when,
    )


def test__active_price_dimension__majority_beats_a_newer_stray():
    observations = [_obs("kg", days) for days in range(2, 11)] + [_obs("ea", 0)]
    assert active_price_dimension(observations) == "mass"


def test__active_price_dimension__tie_goes_to_the_newest():
    assert active_price_dimension([_obs("kg", 3), _obs("ea", 1)]) == "count"


def test__active_price_dimension__none_without_observations():
    assert active_price_dimension([]) is None
