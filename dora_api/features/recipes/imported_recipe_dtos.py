"""Wire shapes for the recipe importer's preview response.

These DTOs are what
``POST /api/recipes/import-from-content`` sends back after parsing a
pasted recipe. The SPA hands the same shape to its preview surface;
saving still goes through ``POST /api/recipes`` and its own
``RecipeIngredientRequest`` shape.

Kept in their own module so both the parser
(``_parse_recipe_from_text.py``) and the handler
(``import_recipe_from_content.py``) can import them without circular
dependencies.
"""
from dataclasses import dataclass, field
from typing import List
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ImportedIngredientDto:
    raw_text: str
    # Best-guess stock item match; null when nothing tracked is close enough.
    stock_item_id: UUID | None
    stock_item_name: str | None
    match_score: int  # 0-100; ignored when stock_item_id is null.
    quantity: float | None
    unit: str | None
    notes: str | None


@dataclass(frozen=True, slots=True)
class ImportedStepDto:
    """C-4 Chunk 6 — one parsed recipe step (or sub-step) for the import
    preview. ``client_id`` is server-assigned (a uuid4) so the SPA can
    feed it straight into the create endpoint's ``steps[].client_id`` /
    ``parent_client_id`` plumbing without re-keying."""
    client_id: str
    parent_client_id: str | None
    sequence: int
    text: str
    hint: str | None


@dataclass(frozen=True, slots=True)
class ImportedRecipeDto:
    name: str
    # cuisine/category are FK vocabularies. The importer is a
    # no-persist preview, so it returns the parsed *name* (for display) plus
    # a resolved *id* when an existing vocab row matches by name. The id is
    # null when the parsed value has no match — the user picks/creates one
    # in the editor on save. No vocab rows are created here.
    cuisine_id: UUID | None
    cuisine_name: str | None
    category_id: UUID | None
    category_name: str | None
    difficulty: str | None
    servings: int | None
    prep_time_minutes: int | None
    cook_time_minutes: int | None
    instructions: str | None
    # IMPL_PLAN_RECIPE_IMPORTER §Chunk 5 — the URL (if any) the user typed
    # in the "Where's this from? (optional)" field of the paste dialog.
    # Metadata only; the server never fetches it. Empty string when the
    # user didn't provide one.
    source_url: str
    ingredients: List[ImportedIngredientDto] = field(default_factory=list)
    # structured steps parsed from the recipe. Empty when
    # the parser only produced a freeform ``instructions`` blob.
    steps: List[ImportedStepDto] = field(default_factory=list)
    # IMPL_PLAN_RECIPE_IMPORTER §Chunk 5 — true when the parser fell
    # back to its lowest-shape output (typically < 3 ingredients found).
    # SPA shows a "we couldn't auto-structure — review and edit" banner.
    is_degraded: bool = False
    # IMPL_PLAN_RECIPE_IMPORTER §Chunk 2 — some sites publish only a
    # total time (Simply Recipes 3, HBH 2/3, Woolworths, RecipeTin 1/3,
    # Smitten 3). Dropping it would lose real info. Populated only when
    # the source explicitly names a total; never derived from prep + cook
    # (that would be P12 No-invent).
    total_time_minutes: int | None = None
