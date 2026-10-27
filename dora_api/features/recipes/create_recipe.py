import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.category import Category
from dora_api.domain.entities.cuisine import Cuisine
from dora_api.domain.entities.recipe import (
    ALLOWED_DIFFICULTY_VALUES,
    ALLOWED_STEPS_MODES,
    Recipe,
)
from dora_api.domain.entities.recipe_collection import RecipeCollection
from dora_api.domain.entities.recipe_ingredient import RecipeIngredient
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.types import EMPTY_UUID
from dora_api.features.meal_slots.slot_validation import (
    get_valid_slot_names, invalid_slot_message)
from dora_api.features.recipes.get_recipes import GetRecipesHandler, get_recipes
from dora_api.features.recipes.ingredient_choice import (
    InvalidIngredientChoice, resolve_ingredient_choice,
)
from dora_api.features.recipes.recipe_tag_access import set_tag_ids_for_recipe
from dora_api.features.recipes.recipe_tool_access import (
    set_tool_ids_for_recipe, sync_recipe_tools_from_steps,
)
from dora_api.features.recipes.recipe_step_access import (
    StepWrite, replace_steps_for_recipe,
)
from dora_api.features.recipes.recipe_step_image_access import (
    StepImageWrite, replace_step_images_for_recipe,
)
from dora_api.features.recipes.recipe_section_access import (
    SectionWrite, replace_sections_for_recipe,
)
from dora_api.features.routers import RECIPE_ROUTER
from dora_api.infrastructure.api_response import created
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.features.recipes._recipe_errors import (RecipeWriteOutcome,
                                                     recipe_write_error_response)
from dora_api.features.recipes.recipe_requests import (RecipeIngredientRequest,
                                                     RecipeSectionRequest,
                                                     RecipeStepRequest)
from dora_api.infrastructure.data_url import image_field

_LOGGER = logging.getLogger(__name__)


class CreateRecipeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length = 1, max_length = 255)
    # cuisine + category are FK vocabularies (single-select each).
    category_id: UUID | None = None
    cook_time_minutes: int | None = Field(default = None, ge = 0)
    cuisine_id: UUID | None = None
    difficulty: str | None = Field(default = None, max_length = 50)
    instructions: str | None = None
    # RD-29 — free-text personal notes (cook's own commentary). Cap generous
    # for a paragraph or two; distinct from `instructions` (the method).
    notes: str | None = Field(default = None, max_length = 5000)
    prep_time_minutes: int | None = Field(default = None, ge = 0)
    recipe_collection_id: UUID | None = None
    servings: int | None = Field(default = None, ge = 1)
    # origin URL for imported recipes.
    source: str | None = Field(default = None, max_length = 2048)
    time_of_day: str | None = Field(default = None, max_length = 50)
    # simple nutrition (kcal). Gated on the C-cross
    # nutrition opt-in client-side; the server stores whatever's sent.
    kcal: int | None = Field(default = None, ge = 0, le = 100_000)
    ingredients: List[RecipeIngredientRequest] = Field(default_factory = list)
    # dietary tag ids (FK to DietaryTag). Validated server-side
    # against existing rows; unknown ids surface as a 400.
    dietary_tag_ids: List[UUID] = Field(default_factory = list)
    # tool ids (FK to Tool).
    tool_ids: List[UUID] = Field(default_factory = list)
    # optional image as a data-URL string ("data:image/...;
    # base64,..."). Stored as UTF-8 bytes; served back via GET /recipes/<id>/
    # image. Capped to keep the row sane (~4MB raw image).
    image: str | None = image_field()
    # structured steps. Empty list = unstructured recipe
    # (cook-mode falls back to splitting `instructions` on newline). Each
    # step's `ingredient_client_ids` references its sibling ingredients via
    # the `client_id` field above.
    steps: List[RecipeStepRequest] = Field(default_factory = list)
    # PROPOSAL_RECIPE_IMAGE_STEPS — explicit step payload selector. Closed
    # set validated below (R-010). Defaults to 'freeform'; the editor flips
    # to 'structured'/'image' as the user picks the mode.
    steps_mode: str = Field(default = "freeform", max_length = 16)
    # PROPOSAL_RECIPE_IMAGE_STEPS — ordered data-URL strings for the image
    # mode. Empty list when not in image mode. Cap mirrored from the
    # access helper.
    step_images: List[str] = Field(default_factory = list)
    # named sections (optional). When non-empty, the server
    # creates RecipeSection rows; ingredients and steps reference them by
    # `section_client_id`. Unreferenced sections still get created (empty
    # group) so the user can type the name first, then drop rows into it.
    sections: List[RecipeSectionRequest] = Field(default_factory = list)


@dataclass(slots=True)
class CreateRecipeResponse(RecipeWriteOutcome):
    new_recipe_id: UUID = EMPTY_UUID


class CreateRecipeHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: CreateRecipeRequest) -> CreateRecipeResponse:
        # §1.7/§1.12 — closed-set vocabularies (R-010).
        if request.difficulty is not None and request.difficulty not in ALLOWED_DIFFICULTY_VALUES:
            return CreateRecipeResponse(
                invalid_vocabulary_message=(
                    f"Invalid difficulty '{request.difficulty}'. "
                    f"Allowed: {', '.join(ALLOWED_DIFFICULTY_VALUES)}."
                ),
            )
        # `time_of_day` is the household meal-slot vocabulary
        # (MealSlot table), validated at the boundary (R-010). Off-vocab
        # values are rejected on new writes; legacy stored values persist.
        if request.time_of_day is not None:
            _ValidSlots = get_valid_slot_names(self.repository)
            if request.time_of_day not in _ValidSlots:
                return CreateRecipeResponse(
                    invalid_vocabulary_message=invalid_slot_message(
                        request.time_of_day, _ValidSlots
                    ),
                )

        _RecipeName = EntityField(Recipe, Recipe.Fields.NAME)
        _ExistingRecipe: Recipe | None = (
            self.repository
            .get(Recipe)
            .one(_RecipeName.eq(request.name))
        )
        if _ExistingRecipe:
            return CreateRecipeResponse(recipe_already_exists = True)

        _Collection: RecipeCollection | None = None
        if request.recipe_collection_id:
            _Collection = self.repository.get(RecipeCollection).by_id(request.recipe_collection_id)
            if not _Collection:
                return CreateRecipeResponse(recipe_collection_not_found = True)

        _Cuisine: Cuisine | None = None
        if request.cuisine_id:
            _Cuisine = self.repository.get(Cuisine).by_id(request.cuisine_id)
            if not _Cuisine:
                return CreateRecipeResponse(cuisine_not_found = True)

        _Category: Category | None = None
        if request.category_id:
            _Category = self.repository.get(Category).by_id(request.category_id)
            if not _Category:
                return CreateRecipeResponse(category_not_found = True)

        _Ingredients: List[RecipeIngredient] = []
        _IngredientPairs: List[tuple[str | None, RecipeIngredient]] = []
        _MissingIds: List[UUID] = []
        for _IngredientRequest in request.ingredients:
            # IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 — a request row may be
            # linked (stock_item_id), unlinked (raw_text only), or both.
            # Model validator upstream guarantees at least one is set.
            _StockItem = None
            if _IngredientRequest.stock_item_id is not None:
                _StockItem = self.repository.get(StockItem).by_id(_IngredientRequest.stock_item_id)
                if not _StockItem:
                    _MissingIds.append(_IngredientRequest.stock_item_id)
                    continue
            try:
                _Choice = resolve_ingredient_choice(
                    self.repository, _StockItem, _IngredientRequest.label,
                    _IngredientRequest.preferred_buy_id, _IngredientRequest.selected_product_id,
                )
            except InvalidIngredientChoice as exc:
                return CreateRecipeResponse(invalid_choice_message = str(exc))
            _NewIngredient = RecipeIngredient(
                notes = _IngredientRequest.notes,
                quantity = _IngredientRequest.quantity,
                stock_item = _StockItem,
                unit = _IngredientRequest.unit,
                is_optional = _IngredientRequest.is_optional,
                raw_text = (_IngredientRequest.raw_text or None),
                label = _Choice.label,
                preferred_buy_id = _Choice.preferred_buy_id,
                selected_product_id = _Choice.selected_product_id,
            )
            _Ingredients.append(_NewIngredient)
            _IngredientPairs.append((_IngredientRequest.client_id, _NewIngredient))

        if _MissingIds:
            return CreateRecipeResponse(missing_stock_item_ids = tuple(_MissingIds))

        # `add()` assigns the real id (uuid4), so the client→real map for
        # structured-step ingredient linkage must be built AFTER this loop.
        for _Ingredient in _Ingredients:
            self.repository.add(_Ingredient)
        _IngredientClientToReal: dict[str, UUID] = {
            client_id: ing.id
            for client_id, ing in _IngredientPairs
            if client_id
        }

        _NewRecipe = Recipe(
            available_meals = 0,
            category = _Category,
            cook_time_minutes = request.cook_time_minutes,
            cuisine = _Cuisine,
            difficulty = request.difficulty,
            image = request.image.encode("utf-8") if request.image else None,
            ingredients = _Ingredients,
            instructions = request.instructions,
            is_favourite = False,
            last_made_on = None,
            name = request.name,
            prep_time_minutes = request.prep_time_minutes,
            recipe_collection = _Collection,
            servings = request.servings,
            source = request.source,
            time_of_day = request.time_of_day,
            # singletons get NULL; the new-version endpoint
            # is the only path that populates this.
            version_group_id = None,
            kcal = request.kcal,
            steps_mode = request.steps_mode if request.steps_mode in ALLOWED_STEPS_MODES else "freeform",
            # stamp at write time so the cookbook "Recently
            # added" sort axis has a stable, recipe-owned timestamp.
            created_at = datetime.now(timezone.utc),
            notes = request.notes,
        )

        self.repository.add(_NewRecipe)
        # FU-456 unit-of-work: one commit, at the end. Flush so downstream
        # Core-level inserts (tags / tools / sections / steps / images
        # access helpers all reach the DB via `db.session.execute(...)`)
        # can reference the recipe row's FK without tripping on it. Any
        # ValueError below returns early WITHOUT committing; teardown
        # rolls the whole thing back so a partial recipe never persists.
        # Error responses drop `new_recipe_id` accordingly — the id was
        # only ever a Python-side uuid4, never a real DB row.
        self.repository.flush()

        # insert sections, then back-fill ingredient
        # rows with their resolved section_id. Sections live as their
        # own table so the FK from RecipeIngredient.section_id is
        # satisfiable; the back-fill keeps the rest of the request
        # logic (steps replace below) on the same map.
        _SectionClientToReal: dict[str, UUID] = {}
        if request.sections:
            try:
                _SectionWrites = [
                    SectionWrite(
                        client_id=section.client_id,
                        sequence=section.sequence,
                        name=section.name,
                    )
                    for section in request.sections
                ]
                _SectionClientToReal = {
                    str(k): v
                    for k, v in replace_sections_for_recipe(
                        _NewRecipe.id, _SectionWrites
                    ).items()
                }
            except ValueError as exc:
                return CreateRecipeResponse(invalid_section_message=str(exc))
            # Back-fill section_id on the freshly-added ingredients (a plain
            # mapped column, so the ORM writes it with the rest).
            for ing_req, (_cid, ing_ent) in zip(request.ingredients, _IngredientPairs):
                real = _SectionClientToReal.get(ing_req.section_client_id) if ing_req.section_client_id else None
                if real is not None:
                    ing_ent.section_id = real

        if request.dietary_tag_ids or request.tool_ids:
            try:
                if request.dietary_tag_ids:
                    set_tag_ids_for_recipe(_NewRecipe.id, request.dietary_tag_ids)
            except ValueError as exc:
                return CreateRecipeResponse(invalid_tag_message=str(exc))
            try:
                if request.tool_ids:
                    set_tool_ids_for_recipe(_NewRecipe.id, request.tool_ids)
            except ValueError as exc:
                return CreateRecipeResponse(invalid_tool_message=str(exc))

        if request.steps:
            try:
                _StepWrites = [
                    StepWrite(
                        client_id=step.client_id,
                        parent_client_id=step.parent_client_id,
                        sequence=step.sequence,
                        text=step.text,
                        hint=step.hint,
                        timer_minutes=step.timer_minutes,
                        ingredient_ids=[
                            _IngredientClientToReal[c]
                            for c in step.ingredient_client_ids
                            if c in _IngredientClientToReal
                        ],
                        tool_ids=list(step.tool_ids),
                        section_id=(
                            _SectionClientToReal.get(step.section_client_id)
                            if step.section_client_id else None
                        ),
                    )
                    for step in request.steps
                ]
                replace_steps_for_recipe(_NewRecipe.id, _StepWrites)
            except ValueError as exc:
                return CreateRecipeResponse(invalid_step_message=str(exc))

        # Recipe-view feedback 2026-08-27 — same derivation as the PATCH: a
        # structured recipe's tools are the union of its steps'. Keeps an
        # imported recipe's cookbook tool filter truthful without the importer
        # having to send a second, redundant list.
        if _NewRecipe.steps_mode == "structured":
            sync_recipe_tools_from_steps(_NewRecipe.id)

        # PROPOSAL_RECIPE_IMAGE_STEPS — write step images last so the FK to
        # the just-created recipe is satisfied. The replace helper validates
        # the data-URL shape and per-recipe cap before any insert.
        if request.step_images:
            try:
                _ImageWrites = [
                    StepImageWrite(sequence=i, image_data_url=data_url)
                    for i, data_url in enumerate(request.step_images)
                ]
                replace_step_images_for_recipe(_NewRecipe.id, _ImageWrites)
            except ValueError as exc:
                return CreateRecipeResponse(invalid_step_message=str(exc))

        # Single commit at the end — everything or nothing.
        self.repository.save_changes()
        return CreateRecipeResponse(new_recipe_id = _NewRecipe.id)


@RECIPE_ROUTER.route("", methods=["POST"])
@has_request_body(CreateRecipeRequest)
def create_recipe():
    _LOGGER.info("Received request to create recipe.")
    _Handler = CreateRecipeHandler(SqlAlchemyRepository())
    _Request: CreateRecipeRequest = get_request_body()
    _Response = _Handler.handle(_Request)

    _Error = recipe_write_error_response(_Response, _Request)
    if _Error is not None:
        return _Error

    _LOGGER.info(f"Successfully created recipe with ID: {_Response.new_recipe_id}")
    _Dto = GetRecipesHandler(SqlAlchemyRepository()).handle_by_id(_Response.new_recipe_id)
    return created(
        _Response.new_recipe_id,
        f"{RECIPE_ROUTER.name}.{get_recipes.__name__}",
        "recipe_id",
        body = _Dto,
    )
