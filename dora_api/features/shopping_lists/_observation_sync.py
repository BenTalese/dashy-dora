"""Harvest and re-sync of ``StockItemPriceObservation`` rows from shopping
lines (FU-726).

Finishing a list turns every priced, item-anchored ticked line into one
observation, joined back by ``shopping_list_line_id``. Amending a *finished*
list (the receipt face) can change the very fields that observation was built
from — price, store, quantity — so the write has to happen in two places. It
therefore lives in one place here rather than being copy-pasted into
``manage_shopping_list_lines`` (R-003: one definition of a domain rule).

The two callers differ only in what they do about an observation that already
exists: ``/finish`` skips it (idempotent under a double-tapped button), amend
rewrites it (the whole point — a typo'd $110.00 must stop poisoning every
future estimate for that item).
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from dora_api.domain.entities.product import Product
from dora_api.domain.entities.shopping_list import ShoppingListLine
from dora_api.domain.entities.stock_item_price_observation import \
    StockItemPriceObservation
from dora_api.features.shopping_lists._line_price import (
    harvest_observation_fields, line_paid_unit_price)
from dora_api.infrastructure.ports import Repository
from dora_api.persistence.field import EntityField


def sync_line_observations(
    repository: Repository,
    lines: list[ShoppingListLine],
    *,
    overwrite_existing: bool = False,
) -> None:
    """Write one observation per priced, item-anchored line in ``lines``.

    With ``overwrite_existing=False`` (the ``/finish`` harvest) a line that
    already produced an observation is left alone — the partial UNIQUE on
    ``shopping_list_line_id`` backs that pre-check.

    With ``overwrite_existing=True`` (receipt amend) the existing row is
    rewritten in place from the line's current price / store / quantity, and a
    line that has *lost* its price has its observation removed — leaving a
    stale number behind would be worse than having none, because observations
    feed the money ladder's historic rung.

    Never calls ``save_changes`` — the caller owns the transaction so the
    observation and the line edit land together.
    """
    anchored = [l for l in lines if l.stock_item_id is not None]
    if not anchored:
        return

    line_ids = [l.id for l in anchored]
    existing_by_line: dict[UUID, StockItemPriceObservation] = {
        o.shopping_list_line_id: o
        for o in repository.get(StockItemPriceObservation).all(
            EntityField(
                StockItemPriceObservation,
                StockItemPriceObservation.Fields.SHOPPING_LIST_LINE_ID,
            ).in_(line_ids)
        )
        if o.shopping_list_line_id is not None
    }

    # Bulk-load selected products for their pack size (E4 — a sized product
    # yields a measure observation; a sizeless line a count observation).
    product_ids = [l.selected_product_id for l in anchored if l.selected_product_id]
    products_by_id: dict[UUID, Product] = {}
    if product_ids:
        products_by_id = {
            p.id: p for p in repository.get(Product).all(
                EntityField(Product, "id").in_(product_ids)
            )
        }

    now = datetime.now(timezone.utc)
    for line in anchored:
        existing = existing_by_line.get(line.id)
        unit_price = line_paid_unit_price(line)

        if unit_price is None:
            # Only the amend path acts on "the price went away"; the harvest
            # path simply had nothing to write in the first place.
            if overwrite_existing and existing is not None:
                repository.remove(existing)
            continue

        if existing is not None and not overwrite_existing:
            continue

        product = (
            products_by_id.get(line.selected_product_id)
            if line.selected_product_id else None
        )
        total_price, total_measure, unit, pack_count, is_sizeless = harvest_observation_fields(
            unit_price=unit_price,
            quantity=line.quantity,
            size_value=product.size_value if product else None,
            size_unit=product.size_unit if product else None,
            product_pack_count=product.pack_count if product else None,
        )

        if existing is not None:
            existing.total_price = total_price
            existing.total_measure = total_measure
            existing.unit = unit
            existing.store_id = line.purchased_store_id
            existing.pack_count = pack_count
            existing.is_sizeless = is_sizeless
            # `observed_at` deliberately keeps its original value: the user is
            # correcting *when they recorded it wrong*, not buying it again.
            continue

        repository.add(StockItemPriceObservation(
            stock_item_id=line.stock_item_id,
            total_price=total_price,
            total_measure=total_measure,
            unit=unit,
            observed_at=now,
            store_id=line.purchased_store_id,
            shopping_list_line_id=line.id,
            created_at=now,
            pack_count=pack_count,
            is_sizeless=is_sizeless,
        ))
