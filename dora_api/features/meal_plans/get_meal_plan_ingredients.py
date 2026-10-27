import logging
from dataclasses import dataclass
from typing import List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.meal_plan import MealPlan
from dora_api.domain.entities.recipe import Recipe
from dora_api.domain.entities.recipe_ingredient import RecipeIngredient
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.stock_status import is_low_stock, is_missing
from dora_api.features.app_settings.access import money_features_enabled
from dora_api.features.recipes.recipe_cost import estimate_cost_for_ingredients
from dora_api.features.routers import MEAL_PLAN_ROUTER
from dora_api.infrastructure.api_response import not_found, ok
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MealPlanIngredientDto:
    stock_item_id: UUID
    stock_item_name: str
    total_quantity: float | None
    unit: str | None
    used_in_recipe_ids: List[UUID]
    # Owner feedback 2026-08-27 — the shared add-to-list picker files optional
    # ingredients into their own unticked section, so the aggregate has to say
    # which items are optional. Aggregation means one stock item can arrive
    # from several ingredient rows across several recipes: it is optional only
    # when *every* contributing row was optional. One required row anywhere in
    # the week makes the item required (the same "required wins" rule the
    # recipe picker already applies within a single recipe — we would rather
    # over-stock than under-stock).
    is_optional: bool


@dataclass(frozen=True, slots=True)
class UnlinkedIngredientDto:
    """An ingredient row with no linked stock item, so it cannot become a
    shopping-list line. FU-505 surfaced these from the auto-generate endpoint;
    the picker-driven add (owner feedback 2026-08-27) replaced that call, so
    the aggregate has to carry them instead or the guarantee is silently
    lost."""
    recipe_name: str
    ingredient_name: str
    # Owner 2026-09-12 — *"make the [free-text] ingredient rows the same as the
    # other ingredient sections: highlight source meals on hover and show
    # quantity required."* Both need data this DTO didn't carry: the recipe id
    # is what the planner highlights meals by, and the amount is what the other
    # rows put in their caption. Scaled to the plan's servings, exactly as the
    # linked rows are, so the two lists quote the same week.
    recipe_id: UUID
    quantity: float | None
    unit: str | None


@dataclass(frozen=True, slots=True)
class MealPlanIngredientsDto:
    """Envelope. Was a bare list until 2026-08-27; `unlinked` cannot be
    expressed per-item (those rows have no stock item to hang off)."""
    items: List[MealPlanIngredientDto]
    unlinked: List[UnlinkedIngredientDto]
    # Owner 2026-09-12 — *"change text to '# low - # out'. We don't necessarily
    # need to buy low items. Also no cost estimate shown? Should be one for
    # low/out ingredients, and one for the meals planned."* All four are
    # server-derived: the bands are a cross-entity read of the stock levels
    # behind the aggregate, and the two figures come from the app's one pricing
    # ladder (R-003), never from a client adding rows up.
    low_count: int = 0
    out_count: int = 0
    #: What the low/out items would cost to buy, and what the whole selection's
    #: ingredients are worth. Both None when money features are off (R-058) or
    #: when nothing in the set could be priced.
    to_buy_cost: float | None = None
    meals_cost: float | None = None


def aggregate_meal_plan_ingredients(
    repository, recipe_id_to_servings: dict[UUID, int],
) -> MealPlanIngredientsDto:
    """Aggregate a {recipe_id: total_servings} demand into per-stock-item
    quantities, scaling each recipe's ingredient amounts by
    `servings / recipe.servings`. The single source of this scaling math (F34,
    R-003) — used by both the saved-plan ingredients endpoint and the
    sequential-builder preview."""
    if not recipe_id_to_servings:
        return MealPlanIngredientsDto(items=[], unlinked=[])

    aggregated: dict[UUID, dict] = {}
    unlinked: List[UnlinkedIngredientDto] = []
    recipes_by_id = {
        r.id: r
        for r in repository
        .get(Recipe)
        .include(Recipe.Fields.INGREDIENTS)
            .then_include(RecipeIngredient.Fields.STOCK_ITEM)
        .all(EntityField(Recipe, "id").in_(list(recipe_id_to_servings)))
    }
    for recipe_id, servings in recipe_id_to_servings.items():
        recipe = recipes_by_id.get(recipe_id)
        if not recipe:
            continue
        recipe_servings = recipe.servings or 1
        scale = servings / recipe_servings if recipe_servings else 1
        for ingredient in recipe.ingredients or []:
            # An *unlinked* ingredient (paste-imported, never matched to a
            # pantry item — IMPL_PLAN_RECIPE_IMPORTER §Chunk 4) has no stock
            # item to aggregate against. This used to read `.id` off None and
            # 500 the whole endpoint, so both this preview and a saved plan's
            # ingredients died outright if any recipe in the selection had one
            # unlinked row. It still can't become a line — a shopping list is
            # a list of *stock items*, and "1 cup of something" isn't one — but
            # since 2026-08-27 it is *reported* rather than silently dropped,
            # so the add-to-list picker can name what it couldn't take.
            if ingredient.stock_item is None:
                unlinked.append(UnlinkedIngredientDto(
                    recipe_name = recipe.name,
                    ingredient_name = (ingredient.raw_text or "").strip()
                        or "(unnamed ingredient)",
                    recipe_id = recipe_id,
                    quantity = (
                        ingredient.quantity * scale
                        if ingredient.quantity is not None else None
                    ),
                    unit = ingredient.unit,
                ))
                continue
            existing = aggregated.setdefault(ingredient.stock_item.id, {
                "stock_item_name": ingredient.stock_item.name,
                "total_quantity": 0.0 if ingredient.quantity is not None else None,
                "unit": ingredient.unit,
                "used_in_recipe_ids": set(),
                "is_optional": True,
            })
            if ingredient.quantity is not None and existing["total_quantity"] is not None:
                existing["total_quantity"] += ingredient.quantity * scale
            elif ingredient.quantity is not None:
                existing["total_quantity"] = ingredient.quantity * scale
            if existing["unit"] is None:
                existing["unit"] = ingredient.unit
            existing["used_in_recipe_ids"].add(recipe_id)
            # Required wins: one non-optional row anywhere clears the flag.
            if not ingredient.is_optional:
                existing["is_optional"] = False

    return MealPlanIngredientsDto(
        items = [
            MealPlanIngredientDto(
                stock_item_id = stock_item_id,
                stock_item_name = data["stock_item_name"],
                total_quantity = data["total_quantity"],
                unit = data["unit"],
                used_in_recipe_ids = list(data["used_in_recipe_ids"]),
                is_optional = data["is_optional"],
            )
            for stock_item_id, data in aggregated.items()
        ],
        unlinked = unlinked,
    )


@dataclass(frozen=True, slots=True)
class _DemandRow:
    """An aggregated ingredient, shaped for the pricing ladder. `_cost_one`
    asks for exactly these four attributes, so the week's demand can be priced
    by the same code that prices a recipe rather than by a second estimator
    that could disagree with it (R-003)."""
    stock_item_id: UUID
    quantity: float | None
    unit: str | None
    stock_item_name: str


def summarise_demand(repository, dto: MealPlanIngredientsDto) -> MealPlanIngredientsDto:
    """Attach the band counts and the two cost figures to an aggregate.

    Low and out are counted separately on purpose (owner 2026-09-12): a low
    item is one you *may* not need to buy, so folding both into one "to buy"
    number overstated the shop. An item with no stock record at all counts as
    out — there is nothing on the shelf we know about.

    `to_buy_cost` prices only the low/out rows; `meals_cost` prices the whole
    demand, which is what the selected meals are worth to make. Both are
    skipped outright when money features are off, so an install that doesn't
    use them pays for none of this.
    """
    if not dto.items:
        return dto

    levels_by_item = {}
    stock_items = repository.get(StockItem).include(StockItem.Fields.STOCK_LEVEL).all(
        EntityField(StockItem, "id").in_([i.stock_item_id for i in dto.items])
    )
    for item in stock_items:
        levels_by_item[item.id] = item.stock_level

    def band(item: MealPlanIngredientDto) -> str:
        level = levels_by_item.get(item.stock_item_id)
        if is_missing(level):
            return "out"
        return "low" if is_low_stock(level) else "stocked"

    bands = {item.stock_item_id: band(item) for item in dto.items}
    low_count = sum(1 for b in bands.values() if b == "low")
    out_count = sum(1 for b in bands.values() if b == "out")

    to_buy_cost: float | None = None
    meals_cost: float | None = None
    if money_features_enabled(repository):
        rows = [
            _DemandRow(
                stock_item_id=i.stock_item_id,
                quantity=i.total_quantity,
                unit=i.unit,
                stock_item_name=i.stock_item_name,
            )
            for i in dto.items
        ]
        meals_cost = estimate_cost_for_ingredients(repository, rows).estimated_cost
        shopping = [r for r in rows if bands[r.stock_item_id] in ("low", "out")]
        if shopping:
            to_buy_cost = estimate_cost_for_ingredients(repository, shopping).estimated_cost

    return MealPlanIngredientsDto(
        items=dto.items,
        unlinked=dto.unlinked,
        low_count=low_count,
        out_count=out_count,
        to_buy_cost=to_buy_cost,
        meals_cost=meals_cost,
    )


class GetMealPlanIngredientsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, meal_plan_id: UUID) -> MealPlanIngredientsDto | None:
        _Plan = (
            self.repository
            .get(MealPlan)
            .include(MealPlan.Fields.ENTRIES)
            .one(EntityField(MealPlan, "id").eq(meal_plan_id))
        )
        if not _Plan:
            return None

        _RecipeIdToServings: dict[UUID, int] = {}
        for _Entry in _Plan.entries or []:
            if _Entry.consumed_at is not None:
                # Past entries already reduced the pool — they don't
                # contribute to the forward-looking shopping list.
                continue
            _RecipeIdToServings[_Entry._recipe_id] = (
                _RecipeIdToServings.get(_Entry._recipe_id, 0) + _Entry.servings
            )

        return summarise_demand(
            self.repository,
            aggregate_meal_plan_ingredients(self.repository, _RecipeIdToServings),
        )


@MEAL_PLAN_ROUTER.route("<uuid:meal_plan_id>/ingredients")
def get_meal_plan_ingredients(meal_plan_id: UUID):
    _Handler = GetMealPlanIngredientsHandler(SqlAlchemyRepository())
    _Result = _Handler.handle(meal_plan_id)
    if _Result is None:
        return not_found(MealPlan.__name__, meal_plan_id)
    _LOGGER.info(
        f"Meal plan {meal_plan_id} has {len(_Result.items)} aggregated ingredients"
        f" ({len(_Result.unlinked)} unlinked)"
    )
    return ok(_Result)


# ───── Preview ingredients for an unsaved selection (C-2.J) ─────────────────

class PreviewRecipeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipe_id: UUID
    servings: int = Field(default=1, ge=1)


class PreviewIngredientsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipes: List[PreviewRecipeInput] = Field(default_factory=list)


class PreviewIngredientsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: PreviewIngredientsRequest) -> MealPlanIngredientsDto:
        recipe_id_to_servings: dict[UUID, int] = {}
        for r in request.recipes:
            recipe_id_to_servings[r.recipe_id] = recipe_id_to_servings.get(r.recipe_id, 0) + r.servings
        return summarise_demand(
            self.repository,
            aggregate_meal_plan_ingredients(self.repository, recipe_id_to_servings),
        )


@MEAL_PLAN_ROUTER.route("preview-ingredients", methods=["POST"])
@has_request_body(PreviewIngredientsRequest)
def preview_meal_plan_ingredients():
    _Request: PreviewIngredientsRequest = get_request_body()
    _Result = PreviewIngredientsHandler(SqlAlchemyRepository()).handle(_Request)
    return ok(_Result)
