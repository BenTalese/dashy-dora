"""Server-derived "Your prices" baseline + signal (FU-227 chunk 4).

Owns the median / "above usual" math (C1/C2 — locked at median, 1.15×, min 3
samples, trailing 12 months). Per-dimension grouping (B4) — observations
logged in volume vs mass vs count get separate baselines and the most-recent
dimension wins for the headline. **LC-2 source-blind:** ``sample_count``
counts observations only — offers never contribute to the baseline median
even when products are on. They show up in the offers sidecar instead (a
separate UI region in the widget; "Current shelf prices: …"), so a flash
sale doesn't poison the user's baseline.

R-003: this module is the single place baseline math lives. The client never
re-derives — it renders ``baseline`` / ``current`` / ``above_baseline`` from
the DTO straight to the screen.
"""
from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable
from uuid import UUID

from dora_api.domain import units
from dora_api.domain.entities.product import Product
from dora_api.domain.entities.product_offer import ProductOffer
from dora_api.domain.entities.stock_item_price_observation import \
    StockItemPriceObservation
from dora_api.domain.entities.store import Store
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.features.products.product_links import linked_stock_items
from dora_api.persistence.field import EntityField


def _as_naive_utc(dt: datetime) -> datetime:
    """SQLite strips tzinfo on read, so observation `observed_at` comes back
    naive even though the writer stores UTC. The cutoff is built with
    `datetime.now(timezone.utc)` so it's aware. Make both naive (UTC-rooted)
    before comparing — otherwise `<` raises TypeError. R-005 carve-out: the
    Postgres-portable fix would be a tz-aware column read, but until the
    Postgres migration (FU-045) we live with this and centralise the
    coercion here."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def measurement_system_from_repo(repo) -> str:
    """Resolve the install-wide measurement system ("metric" / "imperial" /
    "us") from the AppSetting singleton. Falls back to metric if no row exists
    yet (the accessor lazily creates one on first read elsewhere). Single read
    per build_* call — small fetch, never hot enough to need caching.

    Replaces the old ``unit_pricing_locale`` read: which units this household
    measures in and which denominator its shelf prices are quoted in are one
    fact, and holding it twice is how they drift (R-003).
    """
    # Through the one accessor (R-003 / FU-759 class — finalisation 06-R15);
    # this used to be a second `AppSetting.all()[0]` read.
    return get_or_create_app_setting(repo).measurement_system or units.METRIC


# Tunable constants — module-level so they're discoverable for review.
MIN_SAMPLES: int = 3
ABOVE_THRESHOLD: float = 1.15
# The mirror for good news (FU-707): at or under 85% of usual is "less than
# usual", so a saving gets a chip as loud as an overpay.
BELOW_THRESHOLD: float = 0.85
# Below this many prices the usual price is a rough guide, and says so.
STEADY_SAMPLES: int = 6
BASELINE_WINDOW: timedelta = timedelta(days=365)


@dataclass(frozen=True, slots=True)
class OfferSidecarEntry:
    """A single "what stores are listing right now" entry. Lives next to
    the baseline widget but is **never** folded into the median (LC-2)."""
    store_name: str
    price_per_unit: float       # normalised to the active dimension's canonical unit
    unit: str                   # the canonical unit string ("L", "kg", "ea")


@dataclass(frozen=True, slots=True)
class YourPrices:
    """Server-derived signal for a single stock item.

    Empty state (no observations): every numeric field is ``None`` /
    ``False`` / ``0``; the widget renders the empty-state copy.
    Below MIN_SAMPLES: ``baseline`` / ``above_baseline`` stay null/false,
    but ``current`` may be set so the widget shows a "Last seen $X" line.
    Above MIN_SAMPLES: full output; ``above_baseline`` is **strictly**
    greater than ``baseline * ABOVE_THRESHOLD`` (edge case is NOT above).
    """
    baseline: float | None
    baseline_unit: str | None       # "L" / "kg" / "ea" — never the raw alias
    current: float | None
    above_baseline: bool
    below_baseline: bool
    sample_count: int               # observations only (LC-2)
    # Fewer than STEADY_SAMPLES prices behind the usual price (FU-707).
    rough: bool
    # Prices left out because they're on another basis (another unit, or a
    # pack of unknown size beside sized ones; R-105), so a headline that a
    # stray log can't move still says what it didn't count.
    left_out_count: int
    last_observed_at: datetime | None
    last_seen_store_name: str | None
    offers_sidecar: list[OfferSidecarEntry]


def per_unit_in_canonical(
    *, total_price: float, total_measure: float, unit: str,
) -> tuple[float, str] | None:
    """Convert one observation to (per-unit-price, canonical-unit).

    Public (was `_per_unit_in_canonical`) since Reports' item-price-movers
    report normalises the same observations the same way — R-003 wants one
    definition of "per-unit price of an observation", not a second one in a
    reporting handler.

    Returns None when the unit is unknown or the measure is zero. The
    canonical unit is the dimension's display denominator
    (``L`` / ``kg`` / ``ea``) — every observation in the same dimension
    lands on the same denominator so the median is comparable.
    """
    if total_measure <= 0:
        return None
    udef = units.find_unit(unit)
    if udef is None or udef.dimension not in units.PRICE_DIMENSIONS:
        return None
    canonical = units.CANONICAL_PRICE_UNIT[udef.dimension]
    measure_in_canonical = units.convert(total_measure, unit, canonical)
    if measure_in_canonical is None or measure_in_canonical <= 0:
        return None
    return total_price / measure_in_canonical, canonical


def window_unit_prices(
    observations: list[StockItemPriceObservation], basis: PriceBasis, *, now: datetime,
) -> list[float]:
    """Per-canonical-unit prices on ``basis`` inside ``BASELINE_WINDOW``: the
    samples a usual price is the median of."""
    cutoff = _as_naive_utc(now - BASELINE_WINDOW)
    prices: list[float] = []
    for obs in observations:
        if not basis.holds(obs) or _as_naive_utc(obs.observed_at) < cutoff:
            continue
        pu = per_unit_in_canonical(
            total_price=obs.total_price,
            total_measure=obs.total_measure,
            unit=obs.unit,
        )
        if pu is not None:
            prices.append(pu[0])
    return prices


def usual_unit_price(
    observations: list[StockItemPriceObservation], basis: PriceBasis, *, now: datetime,
) -> float | None:
    """The household's usual price per canonical unit on ``basis``: the median
    the "Your prices" baseline shows, or None below ``MIN_SAMPLES``."""
    prices = window_unit_prices(observations, basis, now=now)
    return statistics.median(prices) if len(prices) >= MIN_SAMPLES else None


def _empty_your_prices(last_observed_at: datetime | None = None) -> YourPrices:
    return YourPrices(
        baseline=None, baseline_unit=None, current=None,
        above_baseline=False, below_baseline=False, sample_count=0, rough=False,
        left_out_count=0,
        last_observed_at=last_observed_at, last_seen_store_name=None,
        offers_sidecar=[],
    )


def _baseline_from_observations(
    repo, observations: list[StockItemPriceObservation], *,
    now: datetime, system: str,
    sidecar: Callable[[str, str, float], list[OfferSidecarEntry]] | None = None,
) -> YourPrices:
    """The baseline math shared by the per-item and per-product signals.

    Algorithm (B4 / C1-C5 / LC-2):
      1. No observations → empty state.
      2. Active dimension = the dimension most observations are in.
      3. Filter to observations in that dimension within ``BASELINE_WINDOW``.
      4. Normalise each to a per-canonical-unit price.
      5. ``current`` = the most-recent observation's per-unit price (set
         whenever there is any observation, even below a baseline).
      6. ``sample_count`` < MIN_SAMPLES → baseline None, above_baseline
         False. Else median + strict-greater threshold compare.
      7. ``sidecar(canonical_unit, display_unit, display_factor)`` builds the
         LC-2 offers sidecar (already in display units); it never contributes
         to the median.
    """
    if not observations:
        return _empty_your_prices()

    observations = sorted(observations, key=lambda o: o.observed_at, reverse=True)
    basis = active_price_basis(observations)
    if basis is None:
        # Defensive — the write path validates this so it's a "should never"
        # case; degrade to empty state rather than 500.
        return _empty_your_prices(observations[0].observed_at)
    active_dim = basis.dimension
    # "Current" and the display denominator read the newest price on the
    # basis the baseline is on, not a stray in another one.
    latest = next(o for o in observations if basis.holds(o))
    canonical_unit = units.CANONICAL_PRICE_UNIT[active_dim]

    latest_per_unit = per_unit_in_canonical(
        total_price=latest.total_price,
        total_measure=latest.total_measure,
        unit=latest.unit,
    )
    current_value = latest_per_unit[0] if latest_per_unit else None

    # AU-shelf display denominator (FU-228 follow-up): pick /L vs /100ml (or
    # /kg vs /100g) based on whether the **latest** observation reached a
    # full canonical unit. Below the flip, display per-100; at-or-above,
    # display per-canonical. `display_factor` is what we divide a
    # per-canonical price by to land in the display denominator. Single
    # source so the widget headline, the sidecar entries, and the chart
    # axis can't drift.
    latest_measure_in_canonical = units.convert(
        latest.total_measure, latest.unit, canonical_unit,
    ) or 0.0
    display_unit, display_factor = units.display_denominator_for(
        active_dim, latest_measure_in_canonical, system=system,
    )

    # The most-recent observation's store (A2 — "Last seen $X at Coles").
    last_seen_store_name: str | None = None
    if latest.store_id is not None:
        store = repo.get(Store).by_id(latest.store_id)
        if store is not None:
            last_seen_store_name = store.name

    in_dim_window = window_unit_prices(observations, basis, now=now)

    sample_count = len(in_dim_window)
    baseline: float | None = None
    above: bool = False
    below: bool = False
    if sample_count >= MIN_SAMPLES:
        baseline = statistics.median(in_dim_window)
        # "Strictly greater" per the C2 edge-case test (current == baseline*1.15
        # is NOT above) — keeps the warning chip from flashing on round-number
        # ties.
        if current_value is not None:
            above = current_value > baseline * ABOVE_THRESHOLD
            below = current_value <= baseline * BELOW_THRESHOLD

    # Shelf offers are priced per sized pack, so they can't sit beside prices
    # per pack of unknown size.
    offers = (
        sidecar(canonical_unit, display_unit, display_factor)
        if sidecar and not basis.sizeless else []
    )

    # Internal compute stays in canonical units; only the DTO is shifted.
    display_baseline = baseline / display_factor if baseline is not None else None
    display_current = current_value / display_factor if current_value is not None else None

    # `baseline_unit` is also the unit `current` is reported in — so set it
    # whenever the active dimension is known (even when baseline is null
    # below MIN_SAMPLES), otherwise the widget renders "Last seen $2.72"
    # with no denominator.
    return YourPrices(
        baseline=display_baseline,
        baseline_unit=display_unit if display_current is not None else None,
        current=display_current,
        above_baseline=above,
        below_baseline=below,
        sample_count=sample_count,
        rough=baseline is not None and sample_count < STEADY_SAMPLES,
        left_out_count=sum(
            1 for o in observations
            if observation_basis(o) is not None and not basis.holds(o)
        ),
        last_observed_at=latest.observed_at,
        last_seen_store_name=last_seen_store_name,
        offers_sidecar=offers,
    )


def _observations_for(repo, stock_item_ids: list[UUID]) -> list[StockItemPriceObservation]:
    if not stock_item_ids:
        return []
    return repo.get(StockItemPriceObservation).all(
        EntityField(
            StockItemPriceObservation,
            StockItemPriceObservation.Fields.STOCK_ITEM_ID,
        ).in_(stock_item_ids)
    )


def build_your_prices_for_item(
    repo, stock_item_id: UUID, *,
    now: datetime | None = None, system: str | None = None,
) -> YourPrices:
    """The YourPrices signal for one stock item, with the offers sidecar
    from its linked products' current offers."""
    return _baseline_from_observations(
        repo, _observations_for(repo, [stock_item_id]),
        now=now or datetime.now(timezone.utc),
        system=system or measurement_system_from_repo(repo),
        sidecar=lambda canonical_unit, display_unit, display_factor: _build_offers_sidecar(
            repo, stock_item_id,
            canonical_unit=canonical_unit,
            display_unit=display_unit,
            display_factor=display_factor,
        ),
    )


def build_your_prices_for_product(
    repo, product_id: UUID, *,
    now: datetime | None = None, system: str | None = None,
) -> YourPrices:
    """Per-product variant used by the Price-History page: the observations
    of the stock item the product is linked to, through the same baseline
    math. No offers sidecar — that page already shows offers as the primary
    series."""
    link = linked_stock_items(repo, [product_id]).get(product_id)
    return _baseline_from_observations(
        repo, _observations_for(repo, [link.stock_item_id] if link else []),
        now=now or datetime.now(timezone.utc),
        system=system or measurement_system_from_repo(repo),
    )


# ── Price-history series (FU-227 chunk 6) ─────────────────────────────────
#
# The bottom-sheet "Full history" chart (C5b) and the per-product Price-History
# page's H2 observation overlay both render a *per-unit* series. These helpers
# normalise every point to the active dimension's canonical unit (the same
# basis as the baseline median) so "your data" (observations) and "context"
# (linked-product offers) sit on one comparable y-axis. R-003: all the
# normalisation lives here, never on the client.


@dataclass(frozen=True, slots=True)
class PriceSeriesPoint:
    """One point on the unioned price-history chart, already normalised to the
    series' canonical unit. ``source`` drives the chart's D2 styling
    (observations = solid + dots / "your data"; offers = dashed + faint /
    "context")."""
    observed_at: datetime
    unit_price: float           # per canonical unit (L / kg / ea)
    source: str                 # "observation" | "offer"
    store_name: str | None


def _resolve_store_names(repo, store_ids: Iterable[UUID | None]) -> dict[UUID, str]:
    """Batch-resolve store names for a set of (possibly-None) store ids."""
    ids = {sid for sid in store_ids if sid is not None}
    if not ids:
        return {}
    out: dict[UUID, str] = {}
    for s in repo.get(Store).all(EntityField(Store, "id").in_(list(ids))):
        out[s.id] = s.name
    return out


def display_denominator_for_series(
    observations: list[StockItemPriceObservation],
    products: list[Product],
    *,
    basis: PriceBasis,
    canonical_unit: str,
    system: str = units.METRIC,
) -> tuple[str, float]:
    """Pick the shelf display denominator for a chart series.

    Public (was `_display_for_series`) because Reports' item-price-movers report
    quotes the same prices for the same items and must use the same
    denominator: it reported "$24.00/L" for an item whose own chart, one click
    away, said "$2.40/100ml" — the same price in two languages, which
    `display_denominator_for`'s own docstring exists to prevent. Found by
    driving it (R-003).

    Mirrors the YourPrices rule: AU is always /100ml / /100g; US uses the
    latest observation's measure in canonical units to decide whether to flip
    to the smaller unit (/fl oz / /oz). If there are no observations
    (offer-only series — e.g. a linked product with no in-app obs yet),
    fall back to the first usable linked-product size so the chart axis
    still picks an appropriate denominator.
    """
    active_dim = basis.dimension
    measure_in_canonical = 0.0
    in_dim = [o for o in observations if basis.holds(o)]
    if in_dim:
        latest = max(in_dim, key=lambda o: o.observed_at)
        measure_in_canonical = units.convert(
            latest.total_measure, latest.unit, canonical_unit,
        ) or 0.0
    if measure_in_canonical == 0.0:
        for prod in products:
            if not prod.size_unit or not prod.size_value:
                continue
            offer_def = units.find_unit(prod.size_unit)
            if offer_def is None or offer_def.dimension != active_dim:
                continue
            measure_in_canonical = units.convert(
                prod.size_value, prod.size_unit, canonical_unit,
            ) or 0.0
            if measure_in_canonical > 0:
                break
    return units.display_denominator_for(active_dim, measure_in_canonical, system=system)


@dataclass(frozen=True, slots=True)
class PriceBasis:
    """What an item's prices are compared on: a price dimension, and for
    counts whether the count is of packs of unknown size (FU-983). "1 ea" off
    a sizeless line is one carton; "12 ea" off a sized one is twelve eggs.
    Both are `ea`, and only the flag keeps them off one scale."""
    dimension: str
    sizeless: bool

    def holds(self, obs: StockItemPriceObservation) -> bool:
        return observation_basis(obs) == self


def observation_basis(obs: StockItemPriceObservation) -> PriceBasis | None:
    """The basis one observation is priced on; None outside a price dimension."""
    obs_def = units.find_unit(obs.unit)
    if obs_def is None or obs_def.dimension not in units.PRICE_DIMENSIONS:
        return None
    sizeless = obs_def.dimension == units.COUNT and bool(obs.is_sizeless)
    return PriceBasis(obs_def.dimension, sizeless)


def active_price_basis(
    observations: list[StockItemPriceObservation],
) -> PriceBasis | None:
    """The basis most of an item's price observations are on (FU-876), the
    most recent of the tied ones on a tie. None when no observation is in a
    price dimension.

    It used to be the latest observation's dimension, so nine prices in `kg`
    and one stray `ea` logged last gave a baseline from the one. Public for
    the same reason as `per_unit_in_canonical`: an item's "usual" and its
    reported movement must not disagree about which unit they are about."""
    counts: Counter[PriceBasis] = Counter()
    latest_by_basis: dict[PriceBasis, datetime] = {}
    for obs in observations:
        basis = observation_basis(obs)
        if basis is None:
            continue
        counts[basis] += 1
        seen = latest_by_basis.get(basis)
        if seen is None or obs.observed_at > seen:
            latest_by_basis[basis] = obs.observed_at
    if not counts:
        return None
    top = max(counts.values())
    return max(
        (basis for basis, count in counts.items() if count == top),
        key=lambda basis: latest_by_basis[basis],
    )


def _observation_points(
    observations: list[StockItemPriceObservation],
    *,
    basis: PriceBasis,
    store_names: dict[UUID, str],
) -> list[PriceSeriesPoint]:
    """Normalise the observations on the active basis to per-canonical-unit points."""
    points: list[PriceSeriesPoint] = []
    for obs in observations:
        if not basis.holds(obs):
            continue
        pu = per_unit_in_canonical(
            total_price=obs.total_price,
            total_measure=obs.total_measure,
            unit=obs.unit,
        )
        if pu is None:
            continue
        points.append(PriceSeriesPoint(
            observed_at=obs.observed_at,
            unit_price=pu[0],
            source="observation",
            store_name=store_names.get(obs.store_id) if obs.store_id is not None else None,
        ))
    return points


def _linked_products(repo, stock_item_id: UUID) -> list[Product]:
    """Linked products for a stock item, via the unmapped StockItemProduct
    join table, with their store + offers eager-loaded.

    The offer/store relationships are ``lazy="noload"`` (table_mappings), so a
    bare ``repo.get(Product).all(...)`` leaves ``current_offer``/
    ``historic_offers``/``store`` empty — the includes are required to populate
    them. (This is the single linked-product loader for the file; the offers
    sidecar routes through it too.)"""
    from sqlalchemy import select
    from dora_api.app import db

    join_table = db.metadata.tables["StockItemProduct"]
    product_ids: list[UUID] = [
        row[0]
        for row in db.session.execute(
            select(join_table.c.product_id).where(
                join_table.c.stock_item_id == stock_item_id
            )
        ).all()
    ]
    if not product_ids:
        return []
    return list(
        repo.get(Product)
        .include("store")
        .include("current_offer")
        .include("historic_offers")
        .all(EntityField(Product, "id").in_(product_ids))
    )


def _first_product_price_dim(products: Iterable[Product]) -> str | None:
    """Fallback active dimension (no observations yet) — the dimension of the
    first linked product whose size unit is a price dimension, so the
    bottom-sheet can still show offer context."""
    for prod in products:
        if not prod.size_unit:
            continue
        unit_def = units.find_unit(prod.size_unit)
        if unit_def is not None and unit_def.dimension in units.PRICE_DIMENSIONS:
            return unit_def.dimension
    return None


def _offer_points_from_products(
    products: Iterable[Product], *, active_dim: str, canonical_unit: str,
) -> list[PriceSeriesPoint]:
    """Linked-product offer history normalised to per-canonical-unit. Each
    point is one historic offer (plus the current live offer when it's not
    already represented). Offers in a different dimension to the active one are
    dropped — a per-ea pack price can't share an axis with a per-L baseline."""
    points: list[PriceSeriesPoint] = []
    for prod in products:
        if not prod.is_active or not prod.is_available:
            continue
        if not prod.size_unit or not prod.size_value or prod.size_value <= 0:
            continue
        offer_unit = units.find_unit(prod.size_unit)
        if offer_unit is None or offer_unit.dimension != active_dim:
            continue
        size_in_canonical = units.convert(prod.size_value, prod.size_unit, canonical_unit)
        if size_in_canonical is None or size_in_canonical <= 0:
            continue
        store_name = prod.store.name if prod.store else None
        seen_dates: set = set()
        for ho in (prod.historic_offers or []):
            if ho.price_now is None or ho.price_now <= 0:
                continue
            points.append(PriceSeriesPoint(
                observed_at=ho.offered_on,
                unit_price=float(ho.price_now) / size_in_canonical,
                source="offer",
                store_name=store_name,
            ))
            seen_dates.add(ho.offered_on)
        current = prod.current_offer
        if (current is not None and current.price_now is not None
                and current.price_now > 0 and current.offered_on not in seen_dates):
            points.append(PriceSeriesPoint(
                observed_at=current.offered_on,
                unit_price=float(current.price_now) / size_in_canonical,
                source="offer",
                store_name=store_name,
            ))
    return points


def build_stock_item_price_series(
    repo, stock_item_id: UUID, *, system: str | None = None,
) -> tuple[str | None, list[PriceSeriesPoint]]:
    """Unioned per-unit price series for one stock item (C5b bottom-sheet).

    Returns ``(display_unit, points)`` sorted oldest→newest, with every
    ``unit_price`` expressed in the install's measurement-system display denominator
    (AU ``L``/``100ml``/``kg``/``100g``/``ea`` or US ``qt``/``fl oz``/``lb``
    /``oz``/``ea`` — see `units.display_denominator_for`). Active dimension
    follows the most-recent observation (B4); with no observations we fall
    back to a linked product's dimension so offer context still renders.
    Returns ``(None, [])`` when neither exists.
    """
    _system = system or measurement_system_from_repo(repo)
    observations: list[StockItemPriceObservation] = repo.get(StockItemPriceObservation).all(
        EntityField(
            StockItemPriceObservation,
            StockItemPriceObservation.Fields.STOCK_ITEM_ID,
        ).eq(stock_item_id)
    )
    products = _linked_products(repo, stock_item_id)

    basis = active_price_basis(observations)
    if basis is None:
        fallback_dim = _first_product_price_dim(products)
        if fallback_dim is None:
            return None, []
        basis = PriceBasis(fallback_dim, sizeless=False)
    canonical_unit = units.CANONICAL_PRICE_UNIT[basis.dimension]

    # Display factor sourced from the latest **observation** when one exists
    # (the user's most-recent buy is the strongest signal for "what size are
    # we shopping in?"); falls back to the cheapest linked offer's size so
    # the chart axis still flips sensibly for an offer-only item.
    display_unit, display_factor = display_denominator_for_series(
        observations, products, basis=basis,
        canonical_unit=canonical_unit, system=_system,
    )

    store_names = _resolve_store_names(repo, (o.store_id for o in observations))
    points = _observation_points(observations, basis=basis, store_names=store_names)
    if not basis.sizeless:
        points += _offer_points_from_products(
            products, active_dim=basis.dimension, canonical_unit=canonical_unit)
    if display_factor != 1.0:
        points = [
            PriceSeriesPoint(
                observed_at=p.observed_at,
                unit_price=p.unit_price / display_factor,
                source=p.source,
                store_name=p.store_name,
            )
            for p in points
        ]
    points.sort(key=lambda p: p.observed_at)
    return display_unit, points


def build_product_observation_series(
    repo, product_id: UUID, *, system: str | None = None,
) -> tuple[str | None, list[PriceSeriesPoint]]:
    """Per-unit observation series for a product (H2 overlay on the
    per-product Price-History page).

    Unions observations across every stock item linked to ``product_id`` and
    normalises to the active dimension's canonical unit. Offers are NOT
    included here — the page renders its own offer rows from
    ``ProductHistoricOffer``; this is the observation series the chart layers
    in when the product has no offers (the H2 fallback). Returns
    ``(None, [])`` when there are no observations.
    """
    from sqlalchemy import select
    from dora_api.app import db

    join_table = db.metadata.tables["StockItemProduct"]
    stock_item_ids: list[UUID] = [
        row[0]
        for row in db.session.execute(
            select(join_table.c.stock_item_id).where(
                join_table.c.product_id == product_id
            )
        ).all()
    ]
    if not stock_item_ids:
        return None, []

    observations: list[StockItemPriceObservation] = repo.get(StockItemPriceObservation).all(
        EntityField(
            StockItemPriceObservation,
            StockItemPriceObservation.Fields.STOCK_ITEM_ID,
        ).in_(stock_item_ids)
    )
    basis = active_price_basis(observations)
    if basis is None:
        return None, []
    canonical_unit = units.CANONICAL_PRICE_UNIT[basis.dimension]
    _system = system or measurement_system_from_repo(repo)
    display_unit, display_factor = display_denominator_for_series(
        observations, [], basis=basis,
        canonical_unit=canonical_unit, system=_system,
    )
    store_names = _resolve_store_names(repo, (o.store_id for o in observations))
    points = _observation_points(observations, basis=basis, store_names=store_names)
    if display_factor != 1.0:
        points = [
            PriceSeriesPoint(
                observed_at=p.observed_at,
                unit_price=p.unit_price / display_factor,
                source=p.source,
                store_name=p.store_name,
            )
            for p in points
        ]
    points.sort(key=lambda p: p.observed_at)
    return display_unit, points


def _build_offers_sidecar(
    repo, stock_item_id: UUID, *,
    canonical_unit: str, display_unit: str, display_factor: float,
) -> list[OfferSidecarEntry]:
    """LC-2 — "Current shelf prices: $X at Y · $Z at W" for products users.

    Reads the current offers of every linked product, normalised to the
    same **display** denominator as the baseline so the sidebar reads as
    a direct comparison ("Usually $1.75 / 100ml" · "Current shelf prices:
    $1.50 / 100ml at Coles"). Sized in canonical first, then divided by
    `display_factor` to land in `display_unit`. Cross-dimension offers
    (e.g. a `12 ea` pack against a per-L baseline) are dropped.
    """
    # Shared loader (eager-loads current_offer/store — the relationships are
    # noload, so a bare repo fetch would leave current_offer None and the
    # sidecar silently empty).
    products: Iterable[Product] = _linked_products(repo, stock_item_id)
    if not products:
        return []

    target_dim_unit = units.find_unit(canonical_unit)
    target_dim = target_dim_unit.dimension if target_dim_unit else None

    out: list[OfferSidecarEntry] = []
    for prod in products:
        if not prod.is_active or not prod.is_available:
            continue
        offer: ProductOffer | None = prod.current_offer
        if offer is None or offer.price_now is None or offer.price_now <= 0:
            continue
        if not prod.size_unit or not prod.size_value or prod.size_value <= 0:
            continue
        # Skip offers in a different dimension to the baseline (e.g. a
        # "12 ea" pack offer when the baseline is per-L) — they'd just
        # confuse the sidebar.
        offer_unit = units.find_unit(prod.size_unit)
        if offer_unit is None or offer_unit.dimension != target_dim:
            continue
        size_in_canonical = units.convert(prod.size_value, prod.size_unit, canonical_unit)
        if size_in_canonical is None or size_in_canonical <= 0:
            continue
        per_canonical = float(offer.price_now) / size_in_canonical
        store_name = prod.store.name if prod.store else "Unknown store"
        out.append(OfferSidecarEntry(
            store_name=store_name,
            price_per_unit=per_canonical / display_factor,
            unit=display_unit,
        ))
    # Cheapest first — what users care about most is the deal.
    out.sort(key=lambda e: e.price_per_unit)
    return out
