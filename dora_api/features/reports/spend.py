"""Reports' money cards: spend by store, savings captured, spend by category
and spend year-over-year.

Every figure is built from `shopping_lists._line_price.spend_lines`, the one
definition of "bought in this window" the budget shares, so the cards and the
budget agree on a total (finalisation 12-R10). Money endpoints refuse when the
install has money off (R-058, FU-816).

  GET /api/reports/spend-by-store?range=...
  GET /api/reports/savings-captured?range=...
  GET /api/reports/spend-by-category?range=...
  GET /api/reports/spend-year-over-year?range=...   (bounded ranges only)
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List
from uuid import UUID

from flask import request
from sqlalchemy import select

from dora_api.domain.entities.store import Store
from dora_api.domain.entities.product import Product
from dora_api.domain.entities.shopping_list import ShoppingList
from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.shopping_lists._line_price import resolve_store_id, spend_lines
from dora_api.features.routers import REPORTS_ROUTER
from dora_api.infrastructure.api_response import bad_request, forbidden, ok
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.features.reports._common import (
    MONEY_DISABLED_DETAIL, money_off, parse_range, range_days)


# R-005 carve-out: multi-table aggregates are Core `select()` over the mapped
# classes, not repository walks (the documented reports pattern).

# ───── 2. Spend by store ──────────────────────────────────────────────────

@dataclass(slots=True)
class StoreSpendRow:
    store_id: UUID | None
    store: str
    # FU-814 item 2 — the store's logo-derived colour travels with the row, so
    # every surface that draws this dataset can paint a store the same colour.
    # Reports used to hash the store *name* into the chart ramp, which is how
    # Woolworths came out green on the shopping list and mauve here.
    brand_colour: str | None
    spend: float
    list_count: int


@dataclass(slots=True)
class SpendByStoreResult:
    rows: List[StoreSpendRow]
    # R-041 coverage — how many ticked lines the total was built from, and how
    # many were dropped for carrying no price at all. The shopping list's own
    # card has always stated this ("12 items unpriced, not counted"); Reports
    # quietly undercounted and said nothing.
    counted_lines: int
    unpriced_lines: int


class SpendByStoreHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, since: datetime | None) -> SpendByStoreResult:
        # Every bought line, priced or not: the unpriced ones are counted for
        # the coverage figure rather than dropped, which is what let this
        # report undercount in silence.
        #
        # FU-815: a line needs no product to have a store. The product's store
        # is only the *last* rung of the store ladder, so a household that tags
        # items "I buy this at Aldi" and never touches products still gets a
        # breakdown here, matching its receipt.
        lines = spend_lines(self.repository.session, since)
        priced_rows = [line for line in lines if line.unit_price is not None]
        unpriced_lines = len(lines) - len(priced_rows)
        if not priced_rows:
            return SpendByStoreResult(
                rows=[], counted_lines=0, unpriced_lines=unpriced_lines,
            )

        product_ids = {line.selected_product_id for line in priced_rows if line.selected_product_id}
        store_by_product: Dict[UUID, Store] = {}
        if product_ids:
            products = self.repository.get(Product).include(Product.Fields.STORE).all(
                EntityField(Product, "id").in_(list(product_ids))
            )
            store_by_product = {p.id: p.store for p in products if p.store}

        stock_item_ids = {line.stock_item_id for line in priced_rows if line.stock_item_id}
        usual_store_by_item: Dict[UUID, UUID | None] = {}
        if stock_item_ids:
            usual_store_by_item = {
                item_id: usual_store_id
                for item_id, usual_store_id in self.repository.session.execute(
                    select(StockItem.id, StockItem.usual_store_id).where(
                        StockItem.id.in_(list(stock_item_ids))
                    )
                ).all()
            }

        spend_by_store: Dict[UUID | None, float] = {}
        lists_by_store: Dict[UUID | None, set] = {}
        for line in priced_rows:
            offer_store = (
                store_by_product.get(line.selected_product_id)
                if line.selected_product_id else None
            )
            # The R-003 chokepoint, same one the shopping list's own store
            # breakdown goes through, so the two agree by construction.
            #
            # `last_purchase_store_id` is deliberately None here: that rung
            # exists to *prefill* a line you haven't bought yet from where you
            # last bought it. These lines are ticked on a finished list, so the
            # purchase is a record rather than a guess — attributing one shop's
            # spend to a different shop's store would be a fabrication.
            store_id = resolve_store_id(
                purchased_store_id=line.purchased_store_id,
                planned_store_id=line.planned_store_id,
                usual_store_id=(
                    usual_store_by_item.get(line.stock_item_id)
                    if line.stock_item_id else None
                ),
                last_purchase_store_id=None,
                chosen_offer_store_id=offer_store.id if offer_store else None,
            )
            spend_by_store[store_id] = spend_by_store.get(store_id, 0.0) + line.spent
            lists_by_store.setdefault(store_id, set()).add(line.shopping_list_id)

        stores_by_id: Dict[UUID, Store] = {}
        resolved_store_ids = [sid for sid in spend_by_store if sid is not None]
        if resolved_store_ids:
            stores_by_id = {
                s.id: s for s in self.repository.get(Store).all(
                    EntityField(Store, "id").in_(resolved_store_ids)
                )
            }

        out: List[StoreSpendRow] = []
        for store_id, spend in spend_by_store.items():
            store = stores_by_id.get(store_id) if store_id else None
            out.append(StoreSpendRow(
                store_id=store_id,
                # `None` means the ladder found no store at all — the shopping
                # list calls that bucket "No store set" and so do we. "Unknown"
                # read as a store whose name we'd lost.
                store=store.name if store else "No store set",
                brand_colour=store.brand_colour if store else None,
                spend=round(spend, 2),
                list_count=len(lists_by_store.get(store_id, set())),
            ))
        out.sort(key=lambda r: (-r.spend, r.store.lower()))
        return SpendByStoreResult(
            rows=out,
            counted_lines=len(priced_rows),
            unpriced_lines=unpriced_lines,
        )


@REPORTS_ROUTER.route("/spend-by-store", methods=["GET"])
def spend_by_store():
    if money_off():
        return forbidden(MONEY_DISABLED_DETAIL)
    _Since = parse_range(request.args.get("range"))
    _Result = SpendByStoreHandler(SqlAlchemyRepository()).handle(_Since)
    _Rows = _Result.rows
    # R-041 — the total and the row count travel WITH the rows.
    #
    # The dashboard's spend card shows only the top 3 stores but rendered a
    # bare "$X total" that it had summed client-side over every row. Two
    # problems in one: a cross-collection aggregate computed in the browser
    # (state-ownership), and a total whose coverage the reader could not see —
    # "$412 total" beside three stores looks like the sum of those three. Now
    # the server ships both, so the client renders "top 3 of 5 stores" without
    # doing any arithmetic.
    return ok({
        "range": request.args.get("range", "30d"),
        "rows": [asdict(r) for r in _Rows],
        "total_spend": round(sum(r.spend for r in _Rows), 2),
        "store_count": len(_Rows),
        # R-041 / FU-815 — what the total was built from, so a card can say
        # "12 items unpriced, not counted" instead of undercounting silently.
        "counted_lines": _Result.counted_lines,
        "unpriced_lines": _Result.unpriced_lines,
    })

# ───── 6. Savings captured ────────────────────────────────────────────────

@dataclass(slots=True)
class SavingsListBreakdown:
    shopping_list_id: UUID
    name: str
    completed_at: datetime | None
    picked_total: float
    list_total: float
    savings: float


class SavingsCapturedHandler:
    """Aggregate savings = list_price_at_pick − what the user actually paid,
    per archived list with snapshot data.

    The paid side was `picked_offer_price` — the chosen offer's price, frozen
    at finish — until 2026-09-17, when offers stopped setting prices anywhere
    in the app. It reads `actual_unit_price` now, which means this report says
    something stronger than it used to: a saving is measured against a price
    the user typed, not against another number the shop supplied. Lines with no
    entered price contribute nothing here, exactly as they contribute nothing
    to spend-by-store. Legacy rows keep their old snapshot and still count,
    which is why the paid side coalesces rather than switching outright."""

    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, since: datetime | None) -> dict:
        picked_by_list: Dict[UUID, float] = {}
        list_total_by_list: Dict[UUID, float] = {}
        for line in spend_lines(self.repository.session, since):
            if line.unit_price is None or line.quantity <= 0:
                continue
            lst_id = line.shopping_list_id
            picked_by_list[lst_id] = picked_by_list.get(lst_id, 0.0) + line.spent
            # When the RRP snapshot is missing the list price falls back
            # to the paid price (so this line contributes 0 savings,
            # not negative).
            rrp = line.list_price_at_pick if line.list_price_at_pick is not None else line.unit_price
            list_total_by_list[lst_id] = list_total_by_list.get(lst_id, 0.0) + rrp * line.quantity
        if not picked_by_list:
            return {"total_savings": 0.0, "total_spent": 0.0, "lists": []}
        list_rows = self.repository.session.execute(
            select(ShoppingList.id, ShoppingList.name, ShoppingList.completed_at)
            .where(ShoppingList.id.in_(list(picked_by_list)))
        ).all()

        breakdowns: List[SavingsListBreakdown] = []
        for list_id, name, completed_at in list_rows:
            picked_total = round(picked_by_list.get(list_id, 0.0), 2)
            list_total = round(list_total_by_list.get(list_id, 0.0), 2)
            if picked_total == 0.0:
                continue
            breakdowns.append(SavingsListBreakdown(
                shopping_list_id=list_id,
                name=name,
                completed_at=completed_at,
                picked_total=picked_total,
                list_total=list_total,
                savings=round(list_total - picked_total, 2),
            ))
        breakdowns.sort(
            key=lambda b: (b.completed_at or datetime.min.replace(tzinfo=timezone.utc)),
        )
        total_savings = round(sum(b.savings for b in breakdowns), 2)
        total_spent = round(sum(b.picked_total for b in breakdowns), 2)
        return {
            "total_savings": total_savings,
            "total_spent": total_spent,
            "lists": [
                {
                    "shopping_list_id": b.shopping_list_id,
                    "name": b.name,
                    "completed_at": b.completed_at,
                    "picked_total": b.picked_total,
                    "list_total": b.list_total,
                    "savings": b.savings,
                }
                for b in breakdowns
            ],
        }


@REPORTS_ROUTER.route("/savings-captured", methods=["GET"])
def savings_captured():
    if money_off():
        return forbidden(MONEY_DISABLED_DETAIL)
    _Since = parse_range(request.args.get("range"))
    _Result = SavingsCapturedHandler(SqlAlchemyRepository()).handle(_Since)
    _Result["range"] = request.args.get("range", "30d")
    return ok(_Result)

# ───── 9. Spend by category (P8-09 memory) ────────────────────────────────
# Category = StockItem.stock_group (name). Aggregates paid unit price ×
# quantity on ticked lines of archived (done) lists in the range, joined
# through stock_item to its group. Lines with no stock_item, or whose stock
# item has no group, roll up into an "Uncategorised" bucket so nothing is
# silently dropped.

_UNCATEGORISED_LABEL = "Uncategorised"


@dataclass(slots=True)
class SpendByCategoryRow:
    category: str
    spent: float
    item_count: int  # distinct stock items contributing to this category
    share_pct: float


class SpendByCategoryHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(
        self, since: datetime | None, until: datetime | None = None,
    ) -> tuple[List[SpendByCategoryRow], float]:
        # Genuine spend: bought lines only, and a line with no captured price
        # adds nothing (`SpendLine.spent`).
        line_rows = [
            line for line in spend_lines(self.repository.session, since, until)
            if line.spent > 0
        ]
        if not line_rows:
            return [], 0.0

        # Fetch every stock item referenced + its group name in one pass.
        # Duplicate keys collapse via dict comprehension.
        stock_ids = {r.stock_item_id for r in line_rows if r.stock_item_id is not None}
        group_by_item: dict[UUID, str] = {}
        if stock_ids:
            items = self.repository.get(StockItem).include("stock_group").all(
                EntityField(StockItem, "id").in_(list(stock_ids))
            )
            for item in items:
                group_name = (
                    item.stock_group.name.strip()
                    if item.stock_group is not None and item.stock_group.name
                    else _UNCATEGORISED_LABEL
                )
                group_by_item[item.id] = group_name

        by_category: dict[str, dict] = {}
        for row in line_rows:
            spent = row.spent
            category = (
                group_by_item.get(row.stock_item_id, _UNCATEGORISED_LABEL)
                if row.stock_item_id is not None
                else _UNCATEGORISED_LABEL
            )
            bucket = by_category.setdefault(
                category, {"spent": 0.0, "items": set()},
            )
            bucket["spent"] += spent
            if row.stock_item_id is not None:
                bucket["items"].add(row.stock_item_id)

        total = sum(b["spent"] for b in by_category.values())
        rows = [
            SpendByCategoryRow(
                category=category,
                spent=round(b["spent"], 2),
                item_count=len(b["items"]),
                share_pct=round((b["spent"] / total) * 100, 1) if total > 0 else 0.0,
            )
            for category, b in by_category.items()
        ]
        rows.sort(key=lambda r: (-r.spent, r.category.lower()))
        return rows, round(total, 2)


@REPORTS_ROUTER.route("/spend-by-category", methods=["GET"])
def spend_by_category():
    if money_off():
        return forbidden(MONEY_DISABLED_DETAIL)
    since = parse_range(request.args.get("range"))
    rows, total = SpendByCategoryHandler(SqlAlchemyRepository()).handle(since)
    return ok({
        "range": request.args.get("range", "30d"),
        "total_spent": total,
        "rows": [asdict(r) for r in rows],
    })


# ───── 10. Spend year-over-year (P8-09 memory) ────────────────────────────
# Compares total spend + per-category spend between two same-length
# windows: the CURRENT window (range=N days ending now) and the PRIOR
# window immediately preceding it. E.g. range=1y → this year vs last
# year, category-by-category. Range=all is rejected — YoY needs a
# bounded window.

@dataclass(slots=True)
class SpendYoYCategoryRow:
    category: str
    current: float
    previous: float
    delta: float          # current - previous
    delta_pct: float | None  # None when previous == 0 (undefined)


class SpendYoYHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(
        self,
        current_since: datetime,
        previous_since: datetime,
        previous_until: datetime,
    ) -> dict:
        def _for_window(since: datetime, until: datetime | None) -> tuple[dict[str, float], float]:
            rows, _total = SpendByCategoryHandler(self.repository).handle(since, until)
            by_category = {row.category: row.spent for row in rows}
            return by_category, sum(by_category.values())

        current_totals, current_total = _for_window(current_since, None)
        previous_totals, previous_total = _for_window(previous_since, previous_until)

        categories = set(current_totals) | set(previous_totals)
        rows: list[SpendYoYCategoryRow] = []
        for category in categories:
            current = current_totals.get(category, 0.0)
            previous = previous_totals.get(category, 0.0)
            delta = current - previous
            delta_pct: float | None
            if previous > 0:
                delta_pct = round((delta / previous) * 100, 1)
            else:
                # Undefined when the prior window had zero spend in this
                # category — a "new" category has no rate-of-change. P3
                # Honest: don't render "+∞%" or "+100%" for that case.
                delta_pct = None
            rows.append(SpendYoYCategoryRow(
                category=category,
                current=round(current, 2),
                previous=round(previous, 2),
                delta=round(delta, 2),
                delta_pct=delta_pct,
            ))
        # Rank by absolute delta magnitude so the biggest movers surface
        # first, positive OR negative — the user cares "what moved?".
        rows.sort(key=lambda r: (-abs(r.delta), r.category.lower()))

        overall_delta = current_total - previous_total
        overall_delta_pct: float | None
        if previous_total > 0:
            overall_delta_pct = round((overall_delta / previous_total) * 100, 1)
        else:
            overall_delta_pct = None

        return {
            "current_total": round(current_total, 2),
            "previous_total": round(previous_total, 2),
            "delta": round(overall_delta, 2),
            "delta_pct": overall_delta_pct,
            "rows": [asdict(r) for r in rows],
        }


@REPORTS_ROUTER.route("/spend-year-over-year", methods=["GET"])
def spend_year_over_year():
    if money_off():
        return forbidden(MONEY_DISABLED_DETAIL)
    raw = request.args.get("range", "1y")
    days = range_days(raw)
    if days is None:
        return bad_request("range=all is not supported for spend-year-over-year. Pick a bounded window.")
    now = datetime.now(timezone.utc)
    current_since = now - timedelta(days=days)
    previous_since = now - timedelta(days=days * 2)
    previous_until = current_since
    payload = SpendYoYHandler(SqlAlchemyRepository()).handle(
        current_since, previous_since, previous_until,
    )
    return ok({
        "range": raw,
        "window_days": days,
        **payload,
    })
