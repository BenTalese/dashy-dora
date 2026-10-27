import logging
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.recipe import Recipe
from dora_api.features.recipes.pool import bump_pool
from dora_api.features.routers import RECIPE_ROUTER
from dora_api.infrastructure.api_response import not_found, ok
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


class AdjustRecipeMealsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Bounded for fat-finger protection — there's no undo on a pool
    # adjustment, and 999 covers any realistic batch-cook freezer haul.
    delta: int = Field(ge = -999, le = 999)


@dataclass(slots=True)
class AdjustRecipeMealsResponse:
    recipe_not_found: bool = False
    available_meals: int = 0


class AdjustRecipeMealsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: AdjustRecipeMealsRequest, recipe_id: UUID) -> AdjustRecipeMealsResponse:
        _Recipe = self.repository.get(Recipe).by_id(recipe_id)
        if not _Recipe:
            return AdjustRecipeMealsResponse(recipe_not_found = True)
        # FU-317 Chunk 2 — one authority for pool math (features/recipes/pool.py).
        # The floor-at-zero rule that used to live here (`max(_New, 0)`)
        # is now inside `bump_pool`'s SQL CASE WHEN.
        _NewPool = bump_pool(_Recipe.id, request.delta)
        self.repository.save_changes()
        return AdjustRecipeMealsResponse(available_meals = _NewPool)


@RECIPE_ROUTER.route("<uuid:recipe_id>/adjust-meals", methods=["POST"])
@has_request_body(AdjustRecipeMealsRequest)
def adjust_recipe_meals(recipe_id: UUID):
    _Handler = AdjustRecipeMealsHandler(SqlAlchemyRepository())
    _Request: AdjustRecipeMealsRequest = get_request_body()
    _Response = _Handler.handle(_Request, recipe_id)
    if _Response.recipe_not_found:
        return not_found(Recipe.__name__, recipe_id)
    _LOGGER.info(
        f"Adjusted recipe {recipe_id} meals by {_Request.delta} "
        f"(pool now {_Response.available_meals})"
    )
    return ok({"available_meals": _Response.available_meals})
