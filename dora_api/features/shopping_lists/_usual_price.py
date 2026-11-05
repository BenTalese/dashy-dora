"""Freeze the household's usual price onto finished lines (FU-831 / ADR-068).

Runs at finish, before this list's own prices are harvested, so a line's
baseline is what the household paid *before* this shop. The usual price is the
"Your prices" median for the item (`usual_unit_price`, R-003: one definition),
on the basis this line's purchase sits on (its product's size, or a pack of
unknown size), scaled to one item of this line.
"""
from datetime import datetime

from dora_api.domain import units
from dora_api.domain.entities.product import Product
from dora_api.domain.entities.shopping_list import ShoppingListLine
from dora_api.domain.entities.stock_item_price_observation import \
    StockItemPriceObservation
from dora_api.features.shopping_lists._line_price import harvest_observation_fields
from dora_api.features.stock_items.your_prices import PriceBasis, usual_unit_price
from dora_api.persistence.field import EntityField
from dora_api.infrastructure.ports import Repository


def snapshot_usual_prices(
    repository: Repository, lines: list[ShoppingListLine], *, now: datetime,
) -> None:
    """Set `usual_price_at_pick` on each priced line with enough history."""
    priced = [l for l in lines if l.stock_item_id and l.actual_unit_price is not None]
    if not priced:
        return
    item_ids = list({l.stock_item_id for l in priced})
    observations: dict = {}
    for obs in repository.get(StockItemPriceObservation).all(
        EntityField(
            StockItemPriceObservation, StockItemPriceObservation.Fields.STOCK_ITEM_ID,
        ).in_(item_ids)
    ):
        observations.setdefault(obs.stock_item_id, []).append(obs)
    product_ids = [l.selected_product_id for l in priced if l.selected_product_id]
    products = {
        p.id: p for p in repository.get(Product).all(EntityField(Product, "id").in_(product_ids))
    } if product_ids else {}

    for line in priced:
        product = products.get(line.selected_product_id) if line.selected_product_id else None
        line.usual_price_at_pick = usual_price_for_one(
            observations.get(line.stock_item_id, []), product, now=now,
        )


def usual_price_for_one(
    observations: list[StockItemPriceObservation], product: Product | None, *, now: datetime,
) -> float | None:
    """The usual price for one item of this purchase: the item's usual price
    per canonical unit on the basis this purchase sits on, times one item's
    measure. None when there's too little history."""
    # One item, folded the way its observation will be.
    _total, measure, unit, _pc, sizeless = harvest_observation_fields(
        unit_price=1.0, quantity=1,
        size_value=product.size_value if product else None,
        size_unit=product.size_unit if product else None,
    )
    dimension = units.find_unit(unit).dimension
    basis = PriceBasis(dimension, sizeless=sizeless and dimension == units.COUNT)
    per_unit = usual_unit_price(observations, basis, now=now)
    if per_unit is None:
        return None
    measure_in_canonical = units.convert(measure, unit, units.CANONICAL_PRICE_UNIT[dimension])
    return round(per_unit * measure_in_canonical, 4) if measure_in_canonical else None
