"""Reports' count cards, ungated so the page survives with money off.

  GET /api/reports/most-bought-items?range=...&limit=10
  GET /api/reports/meals-cooked?range=...&limit=N
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List
from uuid import UUID

from flask import request
from sqlalchemy import func, select

from dora_api.domain.entities.cook_event import CookEvent
from dora_api.domain.entities.recipe import Recipe
from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.shopping_lists._line_price import spend_lines
from dora_api.features.routers import REPORTS_ROUTER
from dora_api.infrastructure.api_response import ok
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.features.reports._common import bucket_size_days, parse_range


# R-005 carve-out: multi-table aggregates are Core `select()` over the mapped
# classes, not repository walks (the documented reports pattern).

# ───── 3. Most-bought items ───────────────────────────────────────────────

@dataclass(slots=True)
class MostBoughtRow:
    stock_item_id: UUID
    name: str
    appearances: int


class MostBoughtItemsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, since: datetime | None, limit: int) -> List[MostBoughtRow]:
        # Distinct-(list, item) count, so the same item appearing across
        # five lists scores 5, not 5 × however many times it was edited.
        # Bought lines only: the card says "Bought most", and a line added
        # and never bought is not a purchase (finalisation 12-R4; the FU-768
        # "on the list ≠ bought" class).
        lists_by_item: Dict[UUID, set[UUID]] = {}
        for line in spend_lines(self.repository.session, since):
            if line.stock_item_id is not None:
                lists_by_item.setdefault(line.stock_item_id, set()).add(line.shopping_list_id)
        if not lists_by_item:
            return []

        counts: Dict[UUID, int] = {item_id: len(ids) for item_id, ids in lists_by_item.items()}
        items = self.repository.get(StockItem).all(
            EntityField(StockItem, "id").in_(list(counts.keys()))
        )
        rows = [
            MostBoughtRow(
                stock_item_id=item.id,
                name=item.name,
                appearances=counts.get(item.id, 0),
            )
            for item in items
        ]
        rows.sort(key=lambda r: (-r.appearances, r.name.lower()))
        return rows[:limit]


@REPORTS_ROUTER.route("/most-bought-items", methods=["GET"])
def most_bought_items():
    _Since = parse_range(request.args.get("range"))
    try:
        _Limit = max(1, min(int(request.args.get("limit", "10")), 50))
    except (TypeError, ValueError):
        _Limit = 10
    _Rows = MostBoughtItemsHandler(SqlAlchemyRepository()).handle(_Since, _Limit)
    return ok({
        "range": request.args.get("range", "30d"),
        "rows": [asdict(r) for r in _Rows],
    })

# ───── 8. Meals cooked over time (P8-09 memory) ───────────────────────────
# What was actually cooked in this window. Every CookEvent = one POST to
# /recipes/<id>/cook, so a Sunday batch-cook that fed the week leaves ONE
# row (not seven) — the count is honest about intent-events, not portions.
# `meals_cooked` on each event is the *portion count* the user entered on
# that cook, and the report sums those separately for "how many
# meals-worth" (rather than "how many cooking sessions").

@dataclass(slots=True)
class MealsCookedTopRow:
    recipe_id: UUID | None
    recipe_name: str
    cook_count: int      # number of CookEvent rows for this recipe
    meals_total: int     # sum of meals_cooked across those rows


@dataclass(slots=True)
class MealsCookedBucketPoint:
    date: str            # ISO date at the start of the bucket
    cook_count: int
    meals_total: int


class MealsCookedHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, since: datetime | None, limit: int) -> dict:
        session = self.repository.session

        query = select(
            CookEvent.recipe_id,
            CookEvent.recipe_name,
            CookEvent.meals_cooked,
            CookEvent.occurred_at,
        )
        if since is not None:
            query = query.where(CookEvent.occurred_at >= since)
        rows = session.execute(query).all()
        if not rows:
            return {
                "cook_count": 0,
                "meals_total": 0,
                "distinct_recipes": 0,
                "top_recipes": [],
                "timeline": [],
                **self._repertoire(),
            }

        # Top-N recipes by cook_count (with meals_total as tiebreak signal
        # so a rice cooker cooked once feeding 8 doesn't outrank a nightly
        # curry). Group by recipe_id when non-null, else by the denorm name
        # so deleted-recipe events still land in a labelled bucket.
        by_key: dict[tuple, dict] = {}
        for row in rows:
            key = (row.recipe_id, row.recipe_name)
            bucket = by_key.setdefault(key, {
                "recipe_id": row.recipe_id,
                "recipe_name": row.recipe_name,
                "cook_count": 0,
                "meals_total": 0,
            })
            bucket["cook_count"] += 1
            bucket["meals_total"] += int(row.meals_cooked or 0)

        top = sorted(
            by_key.values(),
            key=lambda b: (-b["cook_count"], -b["meals_total"], b["recipe_name"].lower()),
        )[:limit]
        top_rows = [
            MealsCookedTopRow(
                recipe_id=b["recipe_id"],
                recipe_name=b["recipe_name"],
                cook_count=b["cook_count"],
                meals_total=b["meals_total"],
            )
            for b in top
        ]

        # Timeline — bucket by the shared bucket_size_days helper so
        # 30d/90d get daily, 1y weekly, 2y+/all monthly. Deterministic
        # bucket edges relative to *now* (not the event stream) keep the
        # chart's x-axis stable across refreshes.
        bucket_days = bucket_size_days(since)
        now = datetime.now(timezone.utc)
        # Strip tz for arithmetic against timestamps that may be tz-naive
        # (SQLite doesn't preserve tz; the mapper stores naive UTC).
        now_naive = now.replace(tzinfo=None)

        def _bucket_start(index: int) -> str:
            return (
                now_naive - timedelta(days=(index + 1) * bucket_days - 1)
            ).date().isoformat()

        buckets: dict[str, dict[str, int]] = {}
        highest_index = 0
        for row in rows:
            ts = row.occurred_at
            if ts is None:
                continue
            ts_naive = ts.replace(tzinfo=None) if ts.tzinfo else ts
            delta_days = (now_naive - ts_naive).days
            bucket_index = delta_days // bucket_days
            highest_index = max(highest_index, bucket_index)
            key = _bucket_start(bucket_index)
            b = buckets.setdefault(key, {"cook_count": 0, "meals_total": 0})
            b["cook_count"] += 1
            b["meals_total"] += int(row.meals_cooked or 0)

        # Fill the quiet buckets. Only buckets that HAD a cook used to be
        # emitted, so a household that cooked on ten scattered days got ten
        # evenly-spaced points and the days it didn't cook silently vanished —
        # the chart drew a flat, unbroken run of activity over a month that was
        # mostly quiet. The gaps are the finding: "you cooked twice this week"
        # only means something against the weeks you didn't. Empty buckets are
        # a derived domain fact about the window, so the server owns them
        # (R-003) rather than each client reconstructing the calendar.
        # A bounded range spans its whole window — the quiet weeks at the end of
        # a 30-day view are exactly what the busy ones are read against. "All
        # time" has no start date to span, so it runs back to the oldest cook.
        last_index = highest_index
        if since is not None:
            since_naive = since.replace(tzinfo=None) if since.tzinfo else since
            span_days = max(0, (now_naive - since_naive).days)
            last_index = max(highest_index, span_days // bucket_days)
        for index in range(last_index + 1):
            buckets.setdefault(_bucket_start(index), {"cook_count": 0, "meals_total": 0})

        timeline = [
            MealsCookedBucketPoint(
                date=date_key,
                cook_count=v["cook_count"],
                meals_total=v["meals_total"],
            )
            for date_key, v in sorted(buckets.items())
        ]

        return {
            "cook_count": len(rows),
            "meals_total": sum(int(r.meals_cooked or 0) for r in rows),
            # REPORTS_PAGE_REVIEW.md §3.8 — repertoire is the thing this report
            # is uniquely able to say and never did: "9 different recipes" is a
            # different fact from "14 cooks", and it is the one that sends you
            # back to the cookbook. Counted the same way `top_recipes` groups —
            # by recipe_id when there is one, else the denormalised name, so a
            # deleted recipe still counts as something you cooked.
            "distinct_recipes": len(by_key),
            "top_recipes": [asdict(r) for r in top_rows],
            "timeline": [asdict(p) for p in timeline],
            **self._repertoire(),
        }

    def _repertoire(self) -> dict:
        """How much of the cookbook is actually in rotation.

        Deliberately **not** range-bounded, unlike everything else in this
        handler: "you have 40 recipes and haven't cooked 31 of them in a year"
        is a fact about the cookbook, not about the window the user picked, and
        re-scoping it to a 30-day range would make it say "you haven't cooked 38
        of them" every month — true, useless, and alarming.
        """
        session = self.repository.session
        total_recipes = session.execute(
            select(func.count(Recipe.id))
        ).scalar_one()
        a_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
        cooked_recently = {
            row[0] for row in session.execute(
                select(CookEvent.recipe_id).where(
                    CookEvent.recipe_id.isnot(None),
                    CookEvent.occurred_at >= a_year_ago,
                )
            ).all()
        }
        return {
            "total_recipes": int(total_recipes),
            # Saved recipes with no cook event in the last 365 days.
            "uncooked_recipes": max(0, int(total_recipes) - len(cooked_recently)),
        }


@REPORTS_ROUTER.route("/meals-cooked", methods=["GET"])
def meals_cooked():
    since = parse_range(request.args.get("range"))
    try:
        limit = max(1, min(int(request.args.get("limit", "10")), 50))
    except (TypeError, ValueError):
        limit = 10
    payload = MealsCookedHandler(SqlAlchemyRepository()).handle(since, limit)
    return ok({
        "range": request.args.get("range", "30d"),
        **payload,
    })
