"""Bulk-linker endpoints for unlinked recipe ingredients.

IMPL_PLAN_RECIPE_IMPORTER §Chunk 6 — the paste importer lands
ingredients with ``stock_item_id=NULL`` when RapidFuzz can't match them
against a tracked ``StockItem`` (Chunk 4 made ``RecipeIngredient``
row-persistable in that shape). Linking them one-by-one on each recipe
is slow; this file exposes a settings-page-shaped bulk workflow:

* ``GET /api/recipes/unlinked-ingredients`` — every unlinked row
  grouped by normalised ``raw_text`` (case-insensitive trim + collapsed
  whitespace), sorted by count desc / text asc.
* ``POST /api/recipes/unlinked-ingredients/bulk-link`` — atomically
  point every row whose normalised ``raw_text`` matches to a single
  ``StockItem``. One request per group; no per-recipe PATCH round-trip.
  Recipes that transition from "any unlinked" to "all linked" have
  ``is_cookable_now`` re-derive to a real ``True``/``False`` on the
  next read (server-owned tri-state, R-003).

Cookability itself is derived at read-time from the ingredient set
(see ``domain/recipe_cookability.py``), so no explicit re-materialise
step is needed after the bulk-link — the next ``GET /recipes`` picks
up the change.
"""
import logging
import re
from dataclasses import dataclass
from typing import List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.recipe_ingredient import RecipeIngredient
from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.routers import RECIPE_ROUTER
from dora_api.infrastructure.api_response import (bad_request,
                                                  entity_existence_failure,
                                                  ok)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository


_LOGGER = logging.getLogger(__name__)

# One shared whitespace-collapse regex — the normaliser is called from
# both the grouper (GET) and the bulk-link matcher (POST), so drift
# between the two would silently split what should be one group.
_WHITESPACE_RE = re.compile(r"\s+")


def normalise_raw_text(text: str) -> str:
    """Case-insensitive comparison key for grouping ``raw_text``.

    Strips leading/trailing whitespace, collapses internal whitespace
    (tabs, newlines, multiple spaces) to a single space, and lowercases.
    The grouper and the bulk-link matcher share this exactly so what
    the user sees as "one row" always resolves to the same set of DB
    rows.
    """
    return _WHITESPACE_RE.sub(" ", text.strip()).lower()


@dataclass(frozen=True, slots=True)
class UnlinkedIngredientGroupDto:
    raw_text: str  # The display form — first row's raw_text as pasted.
    used_in_recipe_ids: List[UUID]
    count: int


@dataclass(frozen=True, slots=True)
class UnlinkedIngredientsDto:
    unlinked: List[UnlinkedIngredientGroupDto]


class BulkLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # The comparison key — normalised on the server before matching so
    # a client that sends the display form still works, but it's cheaper
    # (and less ambiguous) if the client sends the exact string it saw
    # on the row it just clicked.
    raw_text: str = Field(min_length=1, max_length=500)
    # The stock item every matching row should point at.
    stock_item_id: UUID


@dataclass(frozen=True, slots=True)
class BulkLinkResultDto:
    linked_count: int  # How many RecipeIngredient rows were updated.


class GetUnlinkedIngredientsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self) -> UnlinkedIngredientsDto:
        # RecipeIngredient rows where the FK is null are the unlinked
        # set. ``raw_text`` is guaranteed non-null on those rows by the
        # ``recipe_ingredient_anchor`` CHECK (Chunk 4).
        rows = (
            self.repository.get(RecipeIngredient)
            # FK column is bound to the underscore-prefixed property in
            # table_mappings (`_stock_item_id`); the un-prefixed name isn't a
            # mapped property, so it raised AttributeError → 500 on every call.
            .all(EntityField(RecipeIngredient, "_stock_item_id").is_null())
        )

        # Group by the normalised key; keep the *first-seen* raw_text
        # as the display form (deterministic for a given DB order —
        # any collapsing on display is a lossy display choice we do
        # NOT bake into the key).
        by_key: dict[str, dict] = {}
        for row in rows:
            raw = row.raw_text or ""
            key = normalise_raw_text(raw)
            if not key:
                continue
            bucket = by_key.setdefault(
                key,
                {"display": raw.strip(), "recipe_ids": []},
            )
            # R-032 — the recipe FK is bound to the underscore-prefixed
            # property in table_mappings (`_recipe_id`, hidden from
            # verify_mappings alongside `_stock_item_id`); the un-prefixed
            # `recipe_id` isn't a mapped property, so `getattr(row,
            # "recipe_id")` silently returned None and EVERY group reported
            # count 0 / empty `used_in_recipe_ids` ("Used in 0 recipes" on the
            # bulk-linker page). Read the mapped FK property.
            recipe_id = getattr(row, "_recipe_id", None)
            if recipe_id is not None:
                bucket["recipe_ids"].append(recipe_id)

        groups: list[UnlinkedIngredientGroupDto] = []
        for bucket in by_key.values():
            # De-dup recipe ids inside a group (same recipe may pin the
            # same raw_text twice — legal, e.g. "1 onion, diced" and
            # "1 onion, sliced" both grouped under "1 onion").
            unique_ids = list(dict.fromkeys(bucket["recipe_ids"]))
            groups.append(UnlinkedIngredientGroupDto(
                raw_text=bucket["display"],
                used_in_recipe_ids=unique_ids,
                count=len(unique_ids),
            ))

        # Sort: highest impact first (count desc), then alphabetical
        # by the display text (case-insensitive, stable).
        groups.sort(key=lambda g: (-g.count, g.raw_text.lower()))

        return UnlinkedIngredientsDto(unlinked=groups)


class BulkLinkHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, raw_text: str, stock_item_id: UUID) -> BulkLinkResultDto | tuple[str, str]:
        target = self.repository.get(StockItem).by_id(stock_item_id)
        if target is None:
            return ("not_found", "StockItem")

        key = normalise_raw_text(raw_text)
        if not key:
            return ("bad_request", "raw_text normalises to empty")

        # Pull every unlinked row and filter in Python — the grouping
        # key is a normalised transform that SQLite/Postgres can't
        # express identically without a stored generated column, and
        # the total unlinked set is small (recipes × ingredients),
        # not a hot path. If this becomes a scale concern, add a
        # ``raw_text_normalised`` generated column (Chunk 7 candidate).
        rows: list[RecipeIngredient] = (
            self.repository.get(RecipeIngredient)
            # See above — FK is `_stock_item_id`, not `stock_item_id`.
            .all(EntityField(RecipeIngredient, "_stock_item_id").is_null())
        )
        linked = 0
        for row in rows:
            if not row.raw_text:
                continue
            if normalise_raw_text(row.raw_text) != key:
                continue
            # Point the FK at the target StockItem via the mapped
            # attribute; the ORM writes the FK column. The mapped
            # ``stock_item`` relationship carries the entity so the
            # domain object stays consistent with the row.
            row.stock_item = target
            linked += 1

        self.repository.save_changes()
        return BulkLinkResultDto(linked_count=linked)


@RECIPE_ROUTER.route("unlinked-ingredients", methods=["GET"])
def get_unlinked_ingredients():
    handler = GetUnlinkedIngredientsHandler(SqlAlchemyRepository())
    dto = handler.handle()
    _LOGGER.info(
        "Unlinked ingredient groups: %d groups across %d rows.",
        len(dto.unlinked),
        sum(g.count for g in dto.unlinked),
    )
    return ok(dto)


@RECIPE_ROUTER.route("unlinked-ingredients/count", methods=["GET"])
def get_unlinked_ingredient_count():
    """The settings badge's number (FU-858): the groups the bulk-linker would
    list, without shipping them."""
    return ok({"count": len(GetUnlinkedIngredientsHandler(SqlAlchemyRepository()).handle().unlinked)})


@RECIPE_ROUTER.route("unlinked-ingredients/bulk-link", methods=["POST"])
@has_request_body(BulkLinkRequest)
def bulk_link_unlinked_ingredients():
    request_body: BulkLinkRequest = get_request_body()
    handler = BulkLinkHandler(SqlAlchemyRepository())
    result = handler.handle(request_body.raw_text, request_body.stock_item_id)
    if isinstance(result, tuple):
        kind, detail = result
        if kind == "not_found":
            return entity_existence_failure(detail, "stock_item_id", request_body.stock_item_id)
        return bad_request(detail)
    _LOGGER.info(
        "Bulk-linked %d RecipeIngredient rows matching raw_text %r to StockItem %s.",
        result.linked_count,
        request_body.raw_text,
        request_body.stock_item_id,
    )
    return ok(result)
