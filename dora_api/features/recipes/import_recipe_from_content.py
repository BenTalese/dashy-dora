"""POST /api/recipes/import-from-content — parse a pasted recipe.

IMPL_PLAN_RECIPE_IMPORTER §Chunk 5 — replaces the pre-Chunk-5
``POST /api/recipes/import-from-url`` fetcher. The server no longer
makes outbound HTTP requests: the user hands us the recipe text
(Ctrl+A / Ctrl+C / Ctrl+V from the recipe page in their browser) and
we parse it locally. Closes:

* **FU-104** (URL importer legal posture) — no companion split needed;
  the fetch moved to the user's browser via paste, so the operator of a
  hosted Dora instance no longer touches third-party sites.
* **FU-199** (SSRF in import-from-url) — closed by construction. There
  is no outbound HTTP call in this file; there is no host / redirect /
  scheme to validate.

Flow:

1. Client posts ``{content, source_url?}``.
2. ``parse_recipe_from_text`` (Chunks 2-3) turns ``content`` into an
   ``ImportedRecipeDto``.
3. This handler resolves cuisine + category vocab against existing
   rows (read-only; no creation) and fuzzy-matches each ingredient's
   ``raw_text`` against the user's ``StockItem`` set (RapidFuzz, score
   threshold 70 — unchanged from the FU-196 swap).
4. ``source_url`` is stamped onto the DTO as metadata. Never fetched.

Saving still goes through ``POST /api/recipes`` and its own
``RecipeIngredientRequest`` shape — Chunk 4 made that route
accept either ``stock_item_id`` (linked) or ``raw_text`` (unlinked),
so an ingredient that missed the fuzzy threshold round-trips as
unlinked all the way through save.
"""
import dataclasses
import logging
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from rapidfuzz import process as fuzz_process

from dora_api.domain.entities.category import Category
from dora_api.domain.entities.cuisine import Cuisine
from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.recipes._parse_recipe_from_text import parse_recipe_from_text
from dora_api.features.recipes.imported_recipe_dtos import (
    ImportedIngredientDto,
    ImportedRecipeDto,
)
from dora_api.features.routers import RECIPE_ROUTER
from dora_api.infrastructure.api_response import ok
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository


_LOGGER = logging.getLogger(__name__)

# RapidFuzz match threshold — unchanged from the pre-Chunk-5 URL
# importer. 0-100 scale. Ingredients below the threshold come back as
# unlinked (stock_item_id=None) with the raw pasted text preserved so
# the user can pick / create in the editor OR save-and-link-later via
# the bulk-linker (Chunk 6).
_MIN_MATCH_SCORE = 70


class ImportFromContentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # The recipe text — a Ctrl+A/C+V from a recipe website. Parser
    # tolerates page nav, story preamble, meta block, ingredient list,
    # instructions, and footer noise (see the corpus tests).
    content: str = Field(min_length=1, max_length=200_000)
    # Optional URL the user pasted into "Where's this from?". Stamped
    # on the response as metadata; NEVER fetched. Blank string is
    # equivalent to null.
    source_url: str = Field(default="", max_length=2048)


class ImportRecipeFromContentHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, content: str, source_url: str) -> ImportedRecipeDto:
        parsed = parse_recipe_from_text(content)

        # Cuisine + category: match by name against existing vocab rows.
        # Parser leaves these null today (Class A / Class B extraction
        # doesn't currently pull a cuisine hint from the text). Kept
        # here in case a future parser pass surfaces one — the match
        # logic is cheap and the surface shape stays consistent with
        # the pre-Chunk-5 importer.
        cuisine_id = self._match_vocab(Cuisine, parsed.cuisine_name)
        category_id = self._match_vocab(Category, parsed.category_name)

        # Fuzzy-match each ingredient's raw_text against the user's
        # tracked stock items. Below-threshold rows stay unlinked
        # (stock_item_id=None) — the raw_text they carry now round-
        # trips through the CreateRecipe endpoint (Chunk 4) so the
        # recipe saves fast even with unmatched ingredients.
        stock_items: list[StockItem] = self.repository.get(StockItem).all()
        name_to_id: dict[str, UUID] = {s.name: s.id for s in stock_items}
        all_names = list(name_to_id.keys())

        matched_ingredients: list[ImportedIngredientDto] = []
        for ingredient in parsed.ingredients:
            match_id: UUID | None = None
            match_name: str | None = None
            match_score = 0
            # The parser already stripped the qty + unit off — its
            # ``raw_text`` is what the user typed / what the site
            # published for the whole line (e.g. "1 pound ground
            # turkey"); the ``rest`` from ``_parse_qty_unit`` is the
            # readable-name portion (e.g. "ground turkey"). We fuzzy
            # against the raw_text because it's what the parser DTO
            # carries; RapidFuzz handles the leading qty gracefully.
            haystack = ingredient.raw_text
            if all_names and haystack:
                result = fuzz_process.extractOne(haystack, all_names)
                if result is not None:
                    candidate, score = result[0], int(result[1])
                    if score >= _MIN_MATCH_SCORE:
                        match_id = name_to_id[candidate]
                        match_name = candidate
                        match_score = score
            matched_ingredients.append(dataclasses.replace(
                ingredient,
                stock_item_id=match_id,
                stock_item_name=match_name,
                match_score=match_score,
            ))

        # Return a new DTO with the resolved vocab ids + matched
        # ingredients + stamped source_url. Everything else (name,
        # times, steps, instructions, is_degraded, total_time_minutes)
        # comes through from the parser unchanged.
        return dataclasses.replace(
            parsed,
            cuisine_id=cuisine_id,
            category_id=category_id,
            ingredients=matched_ingredients,
            source_url=source_url,
        )

    def _match_vocab(self, entity_type, name: str | None) -> UUID | None:
        """Case-insensitive lookup of an existing vocab row by name.
        Returns None on no match — the importer never creates vocab
        rows (the user picks/creates one in the editor on save)."""
        if not name:
            return None
        target = name.strip().lower()
        for row in self.repository.get(entity_type).all():
            if row.name.strip().lower() == target:
                return row.id
        return None


@RECIPE_ROUTER.route("import-from-content", methods=["POST"])
@has_request_body(ImportFromContentRequest)
def import_from_content():
    request_body: ImportFromContentRequest = get_request_body()
    handler = ImportRecipeFromContentHandler(SqlAlchemyRepository())
    result = handler.handle(request_body.content, request_body.source_url)
    _LOGGER.info(
        "Imported recipe %r from pasted content (%d chars) with %d ingredients "
        "(%d matched, %d unlinked)",
        result.name,
        len(request_body.content),
        len(result.ingredients),
        sum(1 for i in result.ingredients if i.stock_item_id is not None),
        sum(1 for i in result.ingredients if i.stock_item_id is None),
    )
    return ok(result)
