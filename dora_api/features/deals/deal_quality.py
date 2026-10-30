"""FU-450 — deal-quality signal (upstream of the budget-defense swaps).

A pure function over a product's own offer history plus the household's
real paid-price history, producing a small ``DealQuality`` verdict. It
runs on any surface that already has a ``Product``:

* the Buy Verdict card (a `fake_markdown` demotes a `buy` → `wait`),
* the budget-defense swap ranker (fake markdowns are filtered out).

Design lock: `docs/04_proposals/PROPOSAL_BUDGET_DEFENSE_SWAPS.md` §4a.

**Explicitly NOT computed here** — the 0-100 numeric score, the percentile
UI surface, or a price-history chart. P8-05's Buy Verdict card is the
canonical "should I buy" surface; this signal feeds it, it doesn't
compete. The band (`poor/fair/good/great`) is an internal enum, never
rendered as a number.

Two layers, same file shape as `get_buy_verdict.py`:

* :func:`compute_deal_quality` — pure, no repo, driven by fixture lists
  in the unit tests.
* :func:`get_deal_quality` — the only part that touches the repo; loads a
  product's offers + the household's price observations and delegates.
"""
import logging
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Optional
from uuid import UUID

from dora_api.persistence.aware import as_utc
from dora_api.domain.entities.product import Product
from dora_api.domain.entities.stock_item_price_observation import \
    StockItemPriceObservation
from dora_api.features.app_settings.clock import household_timezone, household_today
from dora_api.features.products.product_links import linked_stock_items
from dora_api.features.stock_items.your_prices import per_unit_in_canonical
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)

# Window over which a product's offer history is judged. 90 days matches
# the Buy Verdict's "cheapest in 3 months" horizon so the two surfaces
# agree on what "recent" means. Admin-configurable via the default arg.
DEFAULT_WINDOW_DAYS = 90

DealBand = Literal["poor", "fair", "good", "great"]


@dataclass(frozen=True, slots=True)
class DealQuality:
    """The verdict. All prices are the product's *offer* price (`price_now`,
    the pack price) except where a per-unit comparison is called out."""
    lowest_price: float
    highest_price: float
    median_price: float
    current_price: float
    is_lowest_in_window: bool
    # 0..1 "cheapness percentile": the fraction of window prices at or
    # above the current price. 1.0 ⇒ current is the cheapest the product
    # has been in the window; 0.0 ⇒ the most expensive. Higher is a better
    # deal — the bands read off this directly.
    percentile: float
    # True ⇒ the merchant claims a saving (was > now) but the household has
    # recently paid *less* than the "special", so the markdown is inflated.
    fake_markdown: bool
    band: DealBand


def _band_for(percentile: float, fake_markdown: bool) -> DealBand:
    """Map the cheapness percentile → band, clamped to ``poor`` for a fake
    markdown (a dishonest "special" is never a good deal, however it ranks
    against the product's own inflated history)."""
    if fake_markdown:
        return "poor"
    if percentile < 0.5:
        return "poor"
    if percentile < 0.7:
        return "fair"
    if percentile < 0.9:
        return "good"
    return "great"


def compute_deal_quality(
    current_price: Optional[float],
    offer_claims_saving: bool,
    window_prices: list[float],
    household_unit_paid_prices: list[float],
    current_unit_price: Optional[float] = None,
) -> Optional[DealQuality]:
    """Pure verdict.

    * ``current_price`` — the product's current ``price_now`` (pack price).
    * ``offer_claims_saving`` — the current offer has ``price_was > price_now``.
    * ``window_prices`` — every ``price_now`` (current + historic) inside the
      window, same pack-price basis as ``current_price``.
    * ``household_unit_paid_prices`` — the household's per-unit paid prices
      for the product's linked stock item (FU-216 observations). Ground
      truth for "what this actually costs us".
    * ``current_unit_price`` — the product's current price per canonical unit,
      on the SAME basis as ``household_unit_paid_prices`` (the caller puts
      both through ``per_unit_in_canonical`` and keeps only same-dimension
      observations). ``None`` when the product's size can't be put on that
      basis — the fake-markdown test then doesn't fire: a pack price against
      a per-unit median made genuine specials read "poor".

    Returns ``None`` when there's no current price or no window history —
    the caller treats that as "no signal", never a fabricated band.
    """
    if current_price is None or not window_prices:
        return None

    lowest = min(window_prices)
    highest = max(window_prices)
    median = statistics.median(window_prices)

    # Cheapness percentile: how much of the window's price distribution the
    # current price sits at or below. min → 1.0, max → toward 0.0.
    at_or_above = sum(1 for p in window_prices if p >= current_price)
    percentile = at_or_above / len(window_prices)

    # A markdown is fake when the merchant claims a saving but the household
    # has, on the median, paid less than the "special" price recently. No
    # household history ⇒ we can't assert dishonesty, so it's not flagged
    # (Charter P8 — never celebrate a fake, but never invent one either).
    fake_markdown = False
    if offer_claims_saving and household_unit_paid_prices and current_unit_price is not None:
        household_median = statistics.median(household_unit_paid_prices)
        fake_markdown = current_unit_price >= household_median

    return DealQuality(
        lowest_price=round(lowest, 2),
        highest_price=round(highest, 2),
        median_price=round(median, 2),
        current_price=round(current_price, 2),
        is_lowest_in_window=current_price <= lowest,
        percentile=round(percentile, 4),
        fake_markdown=fake_markdown,
        band=_band_for(percentile, fake_markdown),
    )


# ── The only repo-touching layer ──────────────────────────────────────


def get_deal_quality(
    product_id: UUID,
    repository: SqlAlchemyRepository,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> Optional[DealQuality]:
    """Load a product's offers + the household's paid prices for its linked
    stock item, then delegate to :func:`compute_deal_quality`."""
    product: Product | None = (
        repository.get(Product)
        .include(Product.Fields.CURRENT_OFFER)
        .include(Product.Fields.HISTORIC_OFFERS)
        .by_id(product_id)
    )
    if product is None or product.current_offer is None:
        return None

    # The window opens at the household's midnight (R-021). SQLite hands back
    # naive datetimes, which are stored as UTC.
    today = household_today(repository)
    horizon = datetime.combine(
        today - timedelta(days=window_days),
        datetime.min.time(), tzinfo=household_timezone(repository),
    )

    current = product.current_offer
    window_prices = window_offer_prices(current, product.historic_offers or [], horizon)

    offer_claims_saving = (
        current.price_was is not None and current.price_was > current.price_now
    )
    product_per_unit = per_unit_in_canonical(
        total_price=current.price_now,
        total_measure=product.size_value or 0,
        unit=product.size_unit or "",
    )

    # Household paid prices for whichever stock items this product links to,
    # per canonical unit — the same basis Buy Verdict reasons over.
    observations: list[StockItemPriceObservation] = []
    link = linked_stock_items(repository, [product_id]).get(product_id)
    stock_item_ids = [link.stock_item_id] if link else []
    if stock_item_ids:
        observations = repository.get(StockItemPriceObservation).all(
            EntityField(
                StockItemPriceObservation,
                StockItemPriceObservation.Fields.STOCK_ITEM_ID,
            ).in_(stock_item_ids)
        )

    return compute_deal_quality(
        current_price=current.price_now,
        offer_claims_saving=offer_claims_saving,
        window_prices=window_prices,
        household_unit_paid_prices=household_unit_prices_like(product_per_unit, observations),
        current_unit_price=product_per_unit[0] if product_per_unit else None,
    )


def window_offer_prices(current, historic_offers, horizon: datetime) -> list[float]:
    """The current price plus every historic price inside the window.

    The current offer is also written to history when it lands (the
    offer-append rule), so the historic row that IS the current offer is
    skipped — otherwise the current price counted twice and skewed the
    percentile."""
    prices: list[float] = [current.price_now]
    current_at = as_utc(current.offered_on)
    skipped_current = False
    for h in historic_offers:
        if h.price_now is None or h.offered_on is None:
            continue
        offered_at = as_utc(h.offered_on)
        if (not skipped_current and h.price_now == current.price_now
                and offered_at == current_at):
            skipped_current = True
            continue
        if offered_at >= horizon:
            prices.append(h.price_now)
    return prices


def household_unit_prices_like(
    product_per_unit: tuple[float, str] | None, observations,
) -> list[float]:
    """The household's per-unit paid prices on the product's canonical unit.

    Each observation is in its own unit; only those that land in the same
    canonical unit as the product (L / kg / ea) are comparable. No product
    basis ⇒ nothing is comparable."""
    if product_per_unit is None:
        return []
    _price, canonical = product_per_unit
    prices: list[float] = []
    for o in observations:
        per_unit = per_unit_in_canonical(
            total_price=o.total_price, total_measure=o.total_measure or 0, unit=o.unit or "",
        )
        if per_unit is not None and per_unit[1] == canonical:
            prices.append(per_unit[0])
    return prices
