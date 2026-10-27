import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.cook_event import CookEvent
from dora_api.domain.entities.recipe import Recipe
from dora_api.features.app_settings.clock import household_today
from dora_api.features.recipes.pool import bump_pool
from dora_api.features.routers import RECIPE_ROUTER
from dora_api.infrastructure.api_response import not_found, ok
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.session_user import current_user_id

_LOGGER = logging.getLogger(__name__)


class CookRecipeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Upper bound is paranoia, not policy — a fat-finger 99999 is
    # almost certainly a typo, and there's no undo on the pool.
    meals_cooked: int = Field(ge = 0, le = 999)


@dataclass(slots=True)
class CookRecipeResponse:
    recipe_not_found: bool = False
    available_meals: int = 0


class CookRecipeHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(
        self,
        request: CookRecipeRequest,
        recipe_id: UUID,
        cooked_by_user_id: UUID | None = None,
    ) -> CookRecipeResponse:
        _Recipe = self.repository.get(Recipe).by_id(recipe_id)
        if not _Recipe:
            return CookRecipeResponse(recipe_not_found = True)
        # FU-317 Chunk 2 — one authority for pool math (features/recipes/pool.py).
        # `bump_pool` runs on the ORM session; the returned value is
        # authoritative because `_Recipe.available_meals` is now stale in the
        # Python identity map.
        _NewPool = bump_pool(_Recipe.id, request.meals_cooked)
        # R-021 — last_made_on is now a Date stamp (which household day).
        _Recipe.last_made_on = household_today(self.repository)
        # History-tab feed — persist the cook as a discrete event so the
        # Stock Item detail can surface "Used in <recipe>" for every
        # ingredient. Only recorded when the caller actually cooked >0
        # meals (a zero-meal POST is used purely to bump `last_made_on`).
        if request.meals_cooked > 0:
            self.repository.add(CookEvent(
                recipe_id = _Recipe.id,
                recipe_name = _Recipe.name,
                meals_cooked = request.meals_cooked,
                cooked_by_user_id = cooked_by_user_id,
                occurred_at = datetime.now(timezone.utc),
            ))
        self.repository.save_changes()
        return CookRecipeResponse(available_meals = _NewPool)


@RECIPE_ROUTER.route("<uuid:recipe_id>/cook", methods=["POST"])
@has_request_body(CookRecipeRequest)
def cook_recipe(recipe_id: UUID):
    _Handler = CookRecipeHandler(SqlAlchemyRepository())
    _Request: CookRecipeRequest = get_request_body()
    _Response = _Handler.handle(_Request, recipe_id, current_user_id())
    if _Response.recipe_not_found:
        return not_found(Recipe.__name__, recipe_id)
    _LOGGER.info(
        f"Cooked recipe {recipe_id}: +{_Request.meals_cooked} meals "
        f"(pool now {_Response.available_meals})"
    )
    # One shape whatever the count (finalisation 04-R19); 0 is a valid no-op.
    return ok({"available_meals": _Response.available_meals})
