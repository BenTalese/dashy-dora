import logging
from dataclasses import dataclass
from datetime import UTC, datetime
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
from dora_api.features.meal_slots.slot_validation import (
    allowed_slot_names, get_valid_slot_names, invalid_slot_message)
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
from dora_api.infrastructure.api_response import no_content, not_found
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


class UpdateRecipeRequest(BaseModel):
    """Partial update — only fields present in the request body are applied.

    Pydantic's `model_fields_set` is used to distinguish 'not provided' from
    'explicitly null'. Default values are placeholders and never applied.
    """
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default = None, min_length = 1, max_length = 255)
    # cuisine + category are FK vocabularies (resolved like
    # recipe_collection_id below). Explicit null clears the link.
    category_id: UUID | None = None
    cook_time_minutes: int | None = None
    cuisine_id: UUID | None = None
    difficulty: str | None = None
    instructions: str | None = None
    # RD-29 — free-text personal notes. Explicit null clears.
    notes: str | None = Field(default = None, max_length = 5000)
    is_favourite: bool | None = None
    prep_time_minutes: int | None = None
    recipe_collection_id: UUID | None = None
    servings: int | None = None
    # origin URL for imported recipes. Explicit null clears.
    source: str | None = Field(default = None, max_length = 2048)
    time_of_day: str | None = None
    # simple nutrition (kcal). Explicit null clears.
    kcal: int | None = Field(default = None, ge = 0, le = 100_000)
    ingredients: List[RecipeIngredientRequest] | None = None
    # when present (even as an empty list), the full tag/tool
    # set is replaced. Omit the field to leave the existing set untouched.
    dietary_tag_ids: List[UUID] | None = None
    tool_ids: List[UUID] | None = None
    # data-URL image string; explicit null clears it. Omit to
    # leave the existing image untouched.
    image: str | None = image_field()
    # structured steps. When present (even as []), the full
    # step set is replaced. Omit to leave existing steps untouched. An empty
    # list clears all structure (recipe falls back to plain `instructions`).
    steps: List[RecipeStepRequest] | None = None
    # present (even as []) = replace the full section set.
    # Empty list clears all sections; ingredients/steps fall back to the
    # implicit "main" group via ON DELETE SET NULL. Omit to leave
    # existing sections untouched.
    sections: List[RecipeSectionRequest] | None = None
    # PROPOSAL_RECIPE_IMAGE_STEPS — explicit steps_mode flip. Omit to leave
    # untouched; closed set validated below.
    steps_mode: str | None = Field(default = None, max_length = 16)
    # PROPOSAL_RECIPE_IMAGE_STEPS — present (even as []) = replace the full
    # step image set. Omit to leave untouched. Mode-switch is
    # non-destructive: clients toggling away from image mode can leave the
    # rows in place by omitting the field.
    step_images: List[str] | None = None


@dataclass(slots=True)
class UpdateRecipeResponse(RecipeWriteOutcome):
    recipe_not_found: bool = False


# Attributes that may safely be assigned from the request as-is, including
# explicit nulls for the nullable ones. `is_favourite` is handled separately
# because the entity column is NOT NULL — accepting null from a PATCH would
# turn a request-level oversight into a 500 at commit time. cuisine/category
# are FK relationships resolved separately below.
_NULLABLE_PLAIN_ATTRS = (
    "cook_time_minutes", "difficulty",
    "instructions", "notes", "prep_time_minutes",
    "servings", "source", "time_of_day", "kcal",
)


class UpdateRecipeHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: UpdateRecipeRequest, recipe_id: UUID) -> UpdateRecipeResponse:
        _Recipe: Recipe | None = (
            self.repository
            .get(Recipe)
            .include(Recipe.Fields.INGREDIENTS)
            .one(EntityField(Recipe, "id").eq(recipe_id))
        )
        if not _Recipe:
            return UpdateRecipeResponse(recipe_not_found = True)

        _SetFields = request.model_fields_set

        # §1.7/§1.12 — closed-set vocabularies (R-010).
        if "difficulty" in _SetFields and request.difficulty is not None \
                and request.difficulty not in ALLOWED_DIFFICULTY_VALUES:
            return UpdateRecipeResponse(
                invalid_vocabulary_message=(
                    f"Invalid difficulty '{request.difficulty}'. "
                    f"Allowed: {', '.join(ALLOWED_DIFFICULTY_VALUES)}."
                ),
            )
        # `time_of_day` validated against the household MealSlot vocabulary
        # (R-010) plus whatever this recipe already holds. Same seam as
        # `update_meal_plan` and fixed the same way (2026-09-01): deleting a
        # slot leaves stored labels intact by design, but the recipe editor
        # resends `time_of_day` on every save, so a recipe tagged with a
        # since-deleted slot could not be edited at all until you also changed
        # its slot. A new off-vocab value is still refused.
        if "time_of_day" in _SetFields and request.time_of_day is not None:
            _ValidSlots = get_valid_slot_names(self.repository)
            _AllowedSlots = allowed_slot_names(_ValidSlots, [_Recipe.time_of_day or ""])
            if request.time_of_day not in _AllowedSlots:
                return UpdateRecipeResponse(
                    invalid_vocabulary_message=invalid_slot_message(
                        request.time_of_day, _ValidSlots
                    ),
                )

        if "name" in _SetFields and request.name is not None:
            _NameField = EntityField(Recipe, Recipe.Fields.NAME)
            _SameName: Recipe | None = self.repository.get(Recipe).one(_NameField.eq(request.name))
            # str(...) both sides — raw str path param vs UUID id (FU-528
            # family): a bare `!=` made renaming a recipe to its own name 422.
            if _SameName and str(_SameName.id) != str(recipe_id):
                return UpdateRecipeResponse(recipe_already_exists = True)
            _Recipe.name = request.name

        # FU-533: these three are lazy="noload" relationships, so a
        # relationship-side `= None` assignment doesn't dirty the FK column
        # (the recipe was loaded without them) — an explicit-null clear 204'd
        # but the link survived. Write the underscore FK column directly on
        # both paths, same as update_stock_item.py does for stock_location.
        if "recipe_collection_id" in _SetFields:
            if request.recipe_collection_id is None:
                _Recipe._recipe_collection_id = None
                _Recipe.recipe_collection = None
            else:
                _Collection = self.repository.get(RecipeCollection).by_id(request.recipe_collection_id)
                if not _Collection:
                    return UpdateRecipeResponse(recipe_collection_not_found = True)
                _Recipe._recipe_collection_id = _Collection.id
                _Recipe.recipe_collection = _Collection

        if "cuisine_id" in _SetFields:
            if request.cuisine_id is None:
                _Recipe._cuisine_id = None
                _Recipe.cuisine = None
            else:
                _Cuisine = self.repository.get(Cuisine).by_id(request.cuisine_id)
                if not _Cuisine:
                    return UpdateRecipeResponse(cuisine_not_found = True)
                _Recipe._cuisine_id = _Cuisine.id
                _Recipe.cuisine = _Cuisine

        if "category_id" in _SetFields:
            if request.category_id is None:
                _Recipe._category_id = None
                _Recipe.category = None
            else:
                _Category = self.repository.get(Category).by_id(request.category_id)
                if not _Category:
                    return UpdateRecipeResponse(category_not_found = True)
                _Recipe._category_id = _Category.id
                _Recipe.category = _Category

        # sections replace first so the new ingredient/step
        # FKs can target the freshly-inserted rows. Empty list clears (rows
        # fall back to the implicit "main" group via ON DELETE SET NULL).
        _SectionClientToReal: dict[str, UUID] = {}
        if "sections" in _SetFields and request.sections is not None:
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
                        recipe_id, _SectionWrites
                    ).items()
                }
            except ValueError as exc:
                return UpdateRecipeResponse(invalid_section_message=str(exc))

        def _resolve_section(token: str | None) -> UUID | None:
            if not token:
                return None
            if token in _SectionClientToReal:
                return _SectionClientToReal[token]
            # Caller is leaving sections untouched and passed an existing
            # section UUID directly — trust it; the FK + ondelete=SET NULL
            # already protects us from dangling references.
            try:
                return UUID(token)
            except (ValueError, TypeError):
                return None

        _IngredientClientToReal: dict[str, UUID] = {}
        if "ingredients" in _SetFields and request.ingredients is not None:
            _NewIngredients: List[RecipeIngredient] = []
            _NewPairs: List[tuple[str | None, RecipeIngredient]] = []
            _MissingIds: List[UUID] = []
            for _IngredientRequest in request.ingredients:
                # Chunk 4 — the row may be linked (stock_item_id),
                # unlinked (raw_text only), or both. Validator upstream
                # guarantees at least one is set.
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
                    return UpdateRecipeResponse(invalid_choice_message = str(exc))
                _NewIngredient = RecipeIngredient(
                    notes = _IngredientRequest.notes,
                    quantity = _IngredientRequest.quantity,
                    stock_item = _StockItem,
                    unit = _IngredientRequest.unit,
                    section_id = _resolve_section(_IngredientRequest.section_client_id),
                    is_optional = _IngredientRequest.is_optional,
                    raw_text = (_IngredientRequest.raw_text or None),
                    label = _Choice.label,
                    preferred_buy_id = _Choice.preferred_buy_id,
                    selected_product_id = _Choice.selected_product_id,
                )
                _NewIngredients.append(_NewIngredient)
                _NewPairs.append((_IngredientRequest.client_id, _NewIngredient))
            if _MissingIds:
                return UpdateRecipeResponse(missing_stock_item_ids = tuple(_MissingIds))
            for _Ingredient in _NewIngredients:
                self.repository.add(_Ingredient)
            _Recipe.ingredients = _NewIngredients
            _IngredientClientToReal = {
                cid: ing.id for cid, ing in _NewPairs if cid
            }
            # Owner-reported 2026-08-29: "linking ingredients to step is
            # broken (cannot save)". The ingredient replace above leaves the
            # new rows *pending* in the ORM session, and every downstream
            # access helper reaches the DB through a Core
            # `db.session.execute(select(table))` — which, unlike an ORM
            # query, does not autoflush. So `replace_steps_for_recipe`'s
            # "do these ingredients belong to this recipe?" check saw the old
            # rows only and 400'd with the resolved-but-uninserted ids. Same
            # flush, for the same reason, as `create_recipe` does before its
            # own Core-level inserts.
            self.repository.flush()

        for _Attr in _NULLABLE_PLAIN_ATTRS:
            if _Attr in _SetFields:
                setattr(_Recipe, _Attr, getattr(request, _Attr))

        # is_favourite is bool-non-nullable on the entity; ignore explicit nulls.
        if "is_favourite" in _SetFields and request.is_favourite is not None:
            _Recipe.is_favourite = request.is_favourite

        # image: explicit null clears, a data-URL string sets it.
        if "image" in _SetFields:
            _Recipe.image = request.image.encode("utf-8") if request.image else None

        # PROPOSAL_RECIPE_IMAGE_STEPS — steps_mode flip. Closed set (R-010).
        if "steps_mode" in _SetFields and request.steps_mode is not None:
            if request.steps_mode not in ALLOWED_STEPS_MODES:
                return UpdateRecipeResponse(
                    invalid_vocabulary_message=(
                        f"Invalid steps_mode '{request.steps_mode}'. "
                        f"Allowed: {', '.join(ALLOWED_STEPS_MODES)}."
                    ),
                )
            _Recipe.steps_mode = request.steps_mode

        # replace the tag/tool set when explicitly provided.
        # Empty list clears; omitted field leaves untouched.
        if "dietary_tag_ids" in _SetFields and request.dietary_tag_ids is not None:
            try:
                set_tag_ids_for_recipe(recipe_id, request.dietary_tag_ids)
            except ValueError as exc:
                return UpdateRecipeResponse(invalid_tag_message=str(exc))
        if "tool_ids" in _SetFields and request.tool_ids is not None:
            try:
                set_tool_ids_for_recipe(recipe_id, request.tool_ids)
            except ValueError as exc:
                return UpdateRecipeResponse(invalid_tool_message=str(exc))

        # steps replace. Ingredient client_ids resolve via the
        # new-ingredients map; any token that didn't match (because the
        # client is keeping existing ingredients untouched) is parsed as a
        # raw UUID and trusted to the access helper's per-recipe validation.
        if "steps" in _SetFields and request.steps is not None:
            def _resolve_ing(token: str) -> UUID | None:
                if token in _IngredientClientToReal:
                    return _IngredientClientToReal[token]
                try:
                    return UUID(token)
                except (ValueError, TypeError):
                    return None
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
                            resolved
                            for resolved in (_resolve_ing(c) for c in step.ingredient_client_ids)
                            if resolved is not None
                        ],
                        tool_ids=list(step.tool_ids),
                        section_id=_resolve_section(step.section_client_id),
                    )
                    for step in request.steps
                ]
                replace_steps_for_recipe(recipe_id, _StepWrites)
            except ValueError as exc:
                return UpdateRecipeResponse(invalid_step_message=str(exc))

        # Recipe-view feedback 2026-08-27 — in structured mode the recipe's
        # tools are the union of its steps' tools, not a separate list the
        # user maintains in a second place. Derived *after* the steps replace
        # (it reads what was just written) and after the mode flip, so a
        # recipe switched into structured mode picks up the tools its existing
        # steps already declare. A client-sent `tool_ids` for a structured
        # recipe is deliberately overwritten rather than rejected: the page
        # stops sending one, and an older client shouldn't 400.
        if _Recipe.steps_mode == "structured":
            sync_recipe_tools_from_steps(recipe_id)

        # PROPOSAL_RECIPE_IMAGE_STEPS — full-replace semantics matching `steps`
        # above. Empty list clears all rows; mode flip alone (without
        # `step_images` in the payload) leaves existing rows in place so the
        # user can experiment with modes without re-uploading.
        if "step_images" in _SetFields and request.step_images is not None:
            try:
                _ImageWrites = [
                    StepImageWrite(sequence=i, image_data_url=data_url)
                    for i, data_url in enumerate(request.step_images)
                ]
                replace_step_images_for_recipe(recipe_id, _ImageWrites)
            except ValueError as exc:
                return UpdateRecipeResponse(invalid_step_message=str(exc))

        # Recipe-view feedback 2026-08-24 — the edit stamp the version panel
        # reads. Stamped on every PATCH that reaches here (i.e. one that
        # passed validation), not on cook / favourite / meal-pool writes:
        # those change what happened to the recipe, not what it *is*.
        _Recipe.updated_at = datetime.now(UTC)

        self.repository.save_changes()
        return UpdateRecipeResponse()


@RECIPE_ROUTER.route("<uuid:recipe_id>", methods=["PATCH"])
@has_request_body(UpdateRecipeRequest)
def update_recipe(recipe_id: UUID):
    _LOGGER.info("Received request to update recipe.")
    _Handler = UpdateRecipeHandler(SqlAlchemyRepository())
    _Request: UpdateRecipeRequest = get_request_body()
    _Response = _Handler.handle(_Request, recipe_id)

    if _Response.recipe_not_found:
        _LOGGER.warning(f"Recipe not found with ID: {recipe_id}")
        return not_found(Recipe.__name__, recipe_id)

    _Error = recipe_write_error_response(_Response, _Request)
    if _Error is not None:
        return _Error

    _LOGGER.info(f"Successfully updated recipe with ID: {recipe_id}")
    return no_content()
