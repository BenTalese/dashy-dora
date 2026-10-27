"""GET /api/search?q=…&types=…&limit=N — global cross-entity search.

Returns a unified `results` array spanning stock items, shopping lists,
recipes, locations, products, meals and meal plans. Each row carries a
score, optional subtitle, and the substring spans of the query in the
title so the frontend can highlight matches.

Powers the command palette (S1) and the locations "find item" overlay.
"""
import logging
from dataclasses import dataclass
from typing import List, Sequence
from uuid import UUID

from flask import request

# rapidfuzz's `fuzz` module is a drop-in for fuzzywuzzy's;
# same scoring functions (ratio, partial_ratio, token_set_ratio, etc.) at
# the same 0-100 scale. Actively maintained, MIT-licensed, ships a C
# extension so no python-Levenshtein warning noise (the old
# `warnings.filterwarnings` dance is retired with the import).
from rapidfuzz import fuzz

from dora_api.domain.location_breadcrumb import build_breadcrumb
from dora_api.domain.entities.meal_plan import MealPlan
from dora_api.domain.entities.product import Product
from dora_api.domain.entities.recipe import Recipe
from dora_api.domain.entities.shopping_list import ShoppingList
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_location import StockLocation
from dora_api.features.routers import SEARCH_ROUTER
from dora_api.infrastructure.api_response import ok
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


ALL_TYPES = (
    "stock_item",
    "shopping_list",
    "recipe",
    "location",
    "product",
    "meal_plan",
)
DEFAULT_LIMIT = 8
MAX_LIMIT = 25
SCORE_THRESHOLD = 75


@dataclass(frozen=True)
class SearchResultDto:
    type: str
    id: UUID
    title: str
    subtitle: str | None
    icon: str | None
    score: float
    match_spans: List[List[int]]


@dataclass(frozen=True)
class SearchResponseDto:
    results: List[SearchResultDto]


def _score(query: str, text: str) -> float:
    """Combined substring + fuzzy score. Exact / prefix / contains win big so
    typed-in-full names beat partial fuzzy matches; otherwise fall back to
    partial_ratio (0-100) for typo tolerance."""
    if not query or not text:
        return 0
    q = query.lower()
    t = text.lower()
    if t == q:
        return 200
    if t.startswith(q):
        return 150 + min(len(q), 30)
    if q in t:
        return 110 + min(len(q), 20)
    return fuzz.partial_ratio(q, t)


def _spans(query: str, title: str) -> List[List[int]]:
    """All non-overlapping occurrences of `query` inside `title`."""
    if not query:
        return []
    q = query.lower()
    t = title.lower()
    out: List[List[int]] = []
    start = 0
    while True:
        idx = t.find(q, start)
        if idx < 0:
            break
        out.append([idx, idx + len(q)])
        start = idx + len(q)
    return out


def _breadcrumb(location: StockLocation, loc_by_id: dict[UUID, StockLocation]) -> List[str]:
    # R-003 — thin alias so the call sites below read as before; the walk
    # itself is shared (`domain.location_breadcrumb`).
    return build_breadcrumb(location, loc_by_id)


class GlobalSearchHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, query: str, types: Sequence[str], limit: int) -> SearchResponseDto:
        query = (query or "").strip()
        if not query:
            return SearchResponseDto(results=[])

        wanted = set(types) if types else set(ALL_TYPES)
        results: List[SearchResultDto] = []

        if "location" in wanted or "stock_item" in wanted:
            loc_by_id = {loc.id: loc for loc in self.repository.get(StockLocation).all()}
        else:
            loc_by_id = {}

        if "stock_item" in wanted:
            items = (
                self.repository.get(StockItem)
                .include(StockItem.Fields.STOCK_LOCATION)
                .all()
            )
            results.extend(
                self._score_and_collect(
                    query, "stock_item", limit,
                    [(i.id, i.name) for i in items],
                    subtitle_by_id={
                        i.id: (
                            " › ".join(_breadcrumb(i.stock_location, loc_by_id))
                            if i.stock_location
                            else None
                        )
                        for i in items
                    },
                )
            )

        if "location" in wanted:
            locations = list(loc_by_id.values())
            results.extend(
                self._score_and_collect(
                    query, "location", limit,
                    [(loc.id, loc.name) for loc in locations],
                    subtitle_by_id={
                        loc.id: " › ".join(_breadcrumb(loc, loc_by_id)[:-1]) or None
                        for loc in locations
                    },
                )
            )

        if "shopping_list" in wanted:
            lists = self.repository.get(ShoppingList).all()
            def list_sub(sl: ShoppingList) -> str:
                if sl.is_done:
                    return "Archived list"
                if sl.is_shopping:
                    return "Shopping in progress"
                return "Draft list"
            results.extend(
                self._score_and_collect(
                    query, "shopping_list", limit,
                    [(sl.id, sl.name) for sl in lists],
                    subtitle_by_id={sl.id: list_sub(sl) for sl in lists},
                )
            )

        if "recipe" in wanted:
            # cuisine + category flipped to noload; explicit
            # eager-load so the subtitle read below doesn't silently see None.
            recipes = (
                self.repository.get(Recipe)
                .include(Recipe.Fields.CUISINE)
                .include(Recipe.Fields.CATEGORY)
                .all()
            )
            results.extend(
                self._score_and_collect(
                    query, "recipe", limit,
                    [(r.id, r.name) for r in recipes],
                    subtitle_by_id={
                        r.id: (
                            (r.cuisine.name if r.cuisine else None)
                            or (r.category.name if r.category else None)
                        )
                        for r in recipes
                    },
                )
            )

        if "product" in wanted:
            products = (
                self.repository.get(Product)
                .include(Product.Fields.STORE)
                .all()
            )
            def product_sub(p: Product) -> str | None:
                parts = []
                if p.store:
                    parts.append(p.store.name)
                if p.size:
                    parts.append(p.size)
                return " · ".join(parts) if parts else None
            results.extend(
                self._score_and_collect(
                    query, "product", limit,
                    [(p.id, p.name) for p in products],
                    subtitle_by_id={p.id: product_sub(p) for p in products},
                )
            )

        if "meal_plan" in wanted:
            plans = self.repository.get(MealPlan).all()
            results.extend(
                self._score_and_collect(
                    query, "meal_plan", limit,
                    [(p.id, p.name) for p in plans],
                    subtitle_by_id={
                        p.id: f"Week of {p.start_date.isoformat()}" for p in plans
                    },
                )
            )

        return SearchResponseDto(results=results)

    @staticmethod
    def _score_and_collect(
        query: str,
        type_: str,
        limit: int,
        id_titles: List[tuple[UUID, str]],
        *,
        subtitle_by_id: dict[UUID, str | None],
        icon_by_id: dict[UUID, str | None] | None = None,
    ) -> List[SearchResultDto]:
        hits: List[SearchResultDto] = []
        for ent_id, title in id_titles:
            s = _score(query, title)
            if s < SCORE_THRESHOLD:
                continue
            hits.append(SearchResultDto(
                type=type_,
                id=ent_id,
                title=title,
                subtitle=subtitle_by_id.get(ent_id),
                icon=(icon_by_id.get(ent_id) if icon_by_id else None),
                score=s,
                match_spans=_spans(query, title),
            ))
        hits.sort(key=lambda r: (-r.score, r.title.lower()))
        return hits[:limit]


@SEARCH_ROUTER.route("", methods=["GET"])
def global_search():
    _Query = request.args.get("q", "").strip()
    _TypesRaw = request.args.get("types", "")
    _Types = [t for t in _TypesRaw.split(",") if t in ALL_TYPES] if _TypesRaw else []
    try:
        _Limit = int(request.args.get("limit", DEFAULT_LIMIT))
    except (TypeError, ValueError):
        _Limit = DEFAULT_LIMIT
    _Limit = max(1, min(_Limit, MAX_LIMIT))

    _Response = GlobalSearchHandler(SqlAlchemyRepository()).handle(_Query, _Types, _Limit)
    _LOGGER.info("Search '%s' (types=%s, limit=%d): %d results", _Query, _Types or "all", _Limit, len(_Response.results))
    return ok(_Response)
