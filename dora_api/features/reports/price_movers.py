"""GET /api/reports/item-price-movers?range=...: movement in the prices the
household logged itself, per canonical unit."""

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import List
from uuid import UUID

from flask import request
from sqlalchemy import select

from dora_api.persistence.aware import as_utc
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_item_price_observation import (
    StockItemPriceObservation)
from dora_api.domain import units
from dora_api.features.stock_items.your_prices import (
    active_dim_from_latest, display_denominator_for_series,
    measurement_system_from_repo, per_unit_in_canonical)
from dora_api.features.routers import REPORTS_ROUTER
from dora_api.infrastructure.api_response import forbidden, ok
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.features.reports._common import (
    MONEY_DISABLED_DETAIL, money_off, parse_range)


# R-005 carve-out: multi-table aggregates are Core `select()` over the mapped
# classes, not repository walks (the documented reports pattern).

# ───── 11. Item price movers (own data) ───────────────────────────────────

@dataclass(slots=True)
class ItemPriceMoverRow:
    stock_item_id: UUID
    name: str
    # The denominator both prices share, in the install's own shelf convention
    # ("L" / "100ml" / "kg" / "100g" / "ea", or the US set). Every observation
    # for a row is normalised to it server-side, so the two figures are
    # comparable, the client never divides (R-003), and the figure matches what
    # the item's own chart and YourPrices widget quote.
    unit: str
    first_price: float
    last_price: float
    delta: float
    delta_pct: float
    observation_count: int
    first_observed_on: str
    last_observed_on: str


class ItemPriceMoversHandler:
    """"Which of my own items got more expensive?" — REPORTS_PAGE_REVIEW.md §5.

    The largest missing widget on the page, and the one report built on the
    everyday user's *own* data rather than the product catalogue: price trends
    charts `Product` offers, which most installs never populate, while every
    household that logs a shelf price or finishes a priced list accumulates
    `StockItemPriceObservation` rows. FU-703's decision D3 puts the trend job
    here.

    ## What it compares

    Per item, the **earliest and latest observation inside the range**, both
    normalised to the item's canonical unit. Not "median vs latest" — that is
    the buy verdict's question ("am I paying more than usual *right now*"), and
    it already has a surface. This one is drift: what a thing cost me then
    against what it costs me now.

    ## What it refuses to compare

    - **Fewer than two observations in the range.** One reading is a price, not
      a movement. Counted and reported (R-041), never silently dropped.
    - **Two readings in different price dimensions.** A 500g bag and a 2L bottle
      of the same item cannot be compared per-unit, so a row is built only from
      the observations sharing the item's *active* dimension — the dimension of
      its latest reading, the same rule the buy verdict's baseline uses. The
      others are counted as skipped.
    - **Zero as a base.** A first reading of 0 makes the percentage meaningless,
      so the row is dropped rather than reported as an infinite rise.
    - **A price that didn't move.** Two readings at the same price is an answer,
      but it is not a *change*, so it is counted (`items_unchanged`) and left
      out of the rows. Counting it as a mover made the card claim "7 of your
      items changed price" and then render four — the three flat ones belonged
      to neither the dearer nor the cheaper list. Found by driving it.
    """

    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, since: datetime | None, limit: int) -> dict:
        session = self.repository.session
        # One read for the install's measurement system, shared by every row —
        # it decides whether a price is quoted per litre or per 100ml, and the
        # item's own chart resolves it the same way.
        system = measurement_system_from_repo(self.repository)

        rows = session.execute(
            select(StockItemPriceObservation, StockItem.name)
            .join(StockItem, StockItem.id == StockItemPriceObservation.stock_item_id)
            .order_by(StockItemPriceObservation.observed_at.asc())
        ).all()

        # Range filtering happens here rather than in the WHERE clause, and
        # `_as_utc` is why: `observed_at` is `DateTime(timezone=True)` but
        # SQLite does not preserve tzinfo, so the stored value comes back naive
        # while `since` is aware. Comparing the two raised `TypeError` — FU-813,
        # a 500 on every bounded range of a sibling report, invisible on
        # Postgres. Every handler in this file coerces first; so does this one.
        by_item: dict[UUID, dict] = {}
        for obs, item_name in rows:
            observed_at = as_utc(obs.observed_at)
            if observed_at is None:
                continue
            if since is not None and observed_at < since:
                continue
            bucket = by_item.setdefault(obs.stock_item_id, {
                "name": item_name,
                "observations": [],
                "points": [],
            })
            bucket["observations"].append(obs)
            bucket["points"].append((observed_at, obs))

        movers: List[ItemPriceMoverRow] = []
        single_observation_items = 0
        mixed_unit_items = 0
        unchanged_items = 0
        for item_id, bucket in by_item.items():
            observations = bucket["observations"]
            # Active dimension = the dimension of the most recent reading, the
            # same chokepoint rule `build_your_prices_for_item` applies, so an
            # item's "usual" and its movement never disagree about which unit
            # they are talking about.
            active_dim = active_dim_from_latest(observations)
            if active_dim is None:
                continue

            priced: List[tuple[datetime, float]] = []
            skipped_dimension = False
            unit: str | None = None
            for observed_at, obs in bucket["points"]:
                obs_def = units.find_unit(obs.unit)
                if obs_def is None or obs_def.dimension != active_dim:
                    skipped_dimension = True
                    continue
                per_unit = per_unit_in_canonical(
                    total_price=obs.total_price,
                    total_measure=obs.total_measure,
                    unit=obs.unit,
                )
                if per_unit is None:
                    continue
                priced.append((observed_at, per_unit[0]))
                unit = per_unit[1]

            if skipped_dimension:
                mixed_unit_items += 1
            if len(priced) < 2 or unit is None:
                if len(priced) == 1:
                    single_observation_items += 1
                continue

            priced.sort(key=lambda pair: pair[0])
            first_at, first_price = priced[0]
            last_at, last_price = priced[-1]
            if first_price <= 0:
                continue

            # Quote it the way the rest of the app quotes it. The per-unit maths
            # runs in the dimension's canonical unit (L / kg / ea), but the shelf
            # convention quotes per 100ml / 100g (AU), so a bottle is
            # "$1.70/100ml", not "$17.00/L". Skipping this
            # is what made this report say "$24.00/L" for an item whose own
            # chart, one click away, said "$2.40/100ml": one price, two
            # languages (R-003; found by driving it).
            display_unit, display_factor = display_denominator_for_series(
                observations, [], active_dim=active_dim,
                canonical_unit=unit, system=system,
            )
            if display_factor != 1.0:
                first_price /= display_factor
                last_price /= display_factor

            delta = last_price - first_price
            # Rounded before the comparison, not after: two readings that differ
            # by a twentieth of a cent are the same shelf price, and a row
            # reading "+0.0%" is noise the reader has to dismiss.
            if round(delta, 2) == 0:
                unchanged_items += 1
                continue

            movers.append(ItemPriceMoverRow(
                stock_item_id=item_id,
                name=bucket["name"],
                unit=display_unit,
                first_price=round(first_price, 2),
                last_price=round(last_price, 2),
                delta=round(delta, 2),
                delta_pct=round((delta / first_price) * 100, 1),
                observation_count=len(priced),
                first_observed_on=first_at.date().isoformat(),
                last_observed_on=last_at.date().isoformat(),
            ))

        # Biggest movement first, in either direction: the question is "what
        # changed", and a 30% fall is as much news as a 30% rise. The client
        # splits the two ends; ordering by magnitude means it can take from
        # either without a second sort.
        movers.sort(key=lambda row: (-abs(row.delta_pct), row.name.lower()))
        return {
            "rows": [asdict(row) for row in movers[:limit]],
            # R-041 — the aggregate states what it was built from. "3 items" out
            # of a 40-item pantry is a very different report from "3 of 3".
            "items_with_movement": len(movers),
            "items_with_one_observation": single_observation_items,
            "items_with_mixed_units": mixed_unit_items,
            "items_unchanged": unchanged_items,
        }


@REPORTS_ROUTER.route("/item-price-movers", methods=["GET"])
def item_price_movers():
    # Money, not products — deliberately. This is the report that answers the
    # price question for an install that never touches the product catalogue
    # (FU-703 D3), so gating it on products would delete the only price trend
    # such a household can have.
    if money_off():
        return forbidden(MONEY_DISABLED_DETAIL)
    raw = request.args.get("range", "1y")
    try:
        limit = max(1, min(int(request.args.get("limit", "8")), 50))
    except ValueError:
        limit = 8
    payload = ItemPriceMoversHandler(SqlAlchemyRepository()).handle(
        parse_range(raw), limit,
    )
    return ok({"range": raw, **payload})
