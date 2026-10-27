"""Shared offer-append mapping (R-003).

`POST /api/ingest` and `POST /api/products` both end up in the same
question: "given a product and a new price, what changes in the
catalogue?" This module owns that one answer, so the two callers don't
drift.

The mapping rule (PROPOSAL_INGESTION_API §2.3, "append-only; never
overwrite"):

- An unchanged offer (same `price_now` at the same `observed_at`) is a
  no-op. Dedupe key: `(product_id, observed_at, price_now)`.
- A new price → append a `ProductHistoricOffer` *and* move
  `current_offer` to the new value (so the catalogue read still reads
  the latest).
- The historic point carries the `source` string for provenance.

The mapping returns a small status so the caller can build per-record
result lines (`accepted` / `skipped`) without inspecting model state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from dora_api.domain.entities.product import Product
from dora_api.domain.entities.product_historic_offer import \
    ProductHistoricOffer
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


class OfferOutcome(str, Enum):
    APPENDED = "appended"      # new historic point + current moved
    DUPLICATE = "duplicate"    # same (product, observed_at, price) already on file


@dataclass(slots=True, frozen=True)
class OfferResult:
    outcome: OfferOutcome
    historic_offer_id: str | None  # None when DUPLICATE


# Source stamped on an offer a person typed in (create or edit a product), as
# against an ingest provenance string.
OFFER_SOURCE_MANUAL = "manual"


def apply_offer_to_product(
    repository: SqlAlchemyRepository,
    product: Product,
    *,
    price_now: float,
    price_was: float | None,
    observed_at: datetime,
    source: str | None,
) -> OfferResult:
    """Append a historic offer and move `current_offer` if the price
    actually changed at the given moment.

    The repository must have the product attached (i.e. loaded in the
    same session); historic-offer dedupe is checked on the in-memory
    `product.historic_offers` collection plus the live current offer.
    """
    effective_price_was = price_was if price_was is not None else price_now

    # Dedupe at the historic-table level (PROPOSAL_INGESTION_API §2.3):
    # a record matching (product, observed_at, price_now) is "already on
    # file" — re-sending it is a no-op. Querying the DB avoids both the
    # in-memory mutation timeline AND timezone-roundtrip surprises that
    # an `obj.attr == raw` check would have.
    field_product_id = EntityField(ProductHistoricOffer, "_product_id")
    field_offered_on = EntityField(
        ProductHistoricOffer, ProductHistoricOffer.Fields.OFFERED_ON
    )
    field_price_now = EntityField(
        ProductHistoricOffer, ProductHistoricOffer.Fields.PRICE_NOW
    )
    existing_point = repository.get(ProductHistoricOffer).one(
        field_product_id.eq(product.id)
        & field_offered_on.eq(observed_at)
        & field_price_now.eq(price_now)
    )
    if existing_point is not None:
        return OfferResult(OfferOutcome.DUPLICATE, None)

    # Append-only: ingest never rewrites history. The new point carries
    # the new price + source; current_offer moves to match.
    historic = ProductHistoricOffer(
        offered_on=observed_at,
        price_now=price_now,
        price_was=effective_price_was,
        source=source,
    )
    product.historic_offers.append(historic)
    repository.add(historic)

    # Move current. The 1:1 `current_offer` row is mutated in place
    # rather than rebuilt, because rebuilding would break the FK on the
    # owning Product row.
    if product.current_offer is not None:
        product.current_offer.offered_on = observed_at
        product.current_offer.price_now = price_now
        product.current_offer.price_was = effective_price_was

    return OfferResult(OfferOutcome.APPENDED, str(historic.id))
