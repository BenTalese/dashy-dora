"""GET /api/meal-plans/shortfall — which recipes still have to be cooked.

The pool-vs-commitments model this reports on lives in `planned_meals.py`
(2026-09-03, R-003). This module used to own a raw-SQL copy of it —
`SUM(e.servings) > r.available_meals`, grouped by recipe — which was correct
but could only ever answer the recipe-level question. The per-entry reading
("*which* of the three planned fried rices is already covered") was needed for
the stock surfaces' planned-demand signal, and two implementations of one
domain rule is the thing R-003 exists to prevent, so both now read the same
allocation.

Behaviour is unchanged: a recipe appears when its committed servings exceed
its cooked pool, and `shortfall` is still that difference. `earliest_needed`
is now the earliest *uncovered* entry rather than the earliest entry full
stop — a strictly better answer, and the same one whenever the pool is empty,
which is every household that doesn't batch-cook.
"""
import logging
from dataclasses import dataclass
from datetime import date
from typing import List
from uuid import UUID

from dora_api.features.meal_plans.planned_meals import (recipe_shortfalls,
                                                        upcoming_planned_meals)
from dora_api.features.routers import MEAL_PLAN_ROUTER
from dora_api.infrastructure.api_response import ok
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ShortfallDto:
    recipe_id: UUID
    recipe_name: str
    available_meals: int
    committed_meals: int
    shortfall: int
    earliest_needed: date | None


class GetShortfallHandler:
    def handle(self) -> List[ShortfallDto]:
        repository = SqlAlchemyRepository()
        snapshot = upcoming_planned_meals(repository)
        return [
            ShortfallDto(
                recipe_id=row.recipe_id,
                recipe_name=row.recipe_name,
                available_meals=row.available_meals,
                committed_meals=row.committed_meals,
                shortfall=row.shortfall,
                earliest_needed=row.earliest_needed,
            )
            for row in recipe_shortfalls(snapshot)
        ]


@MEAL_PLAN_ROUTER.route("shortfall")
def get_shortfall():
    _Result = GetShortfallHandler().handle()
    _LOGGER.info(f"Shortfall report: {len(_Result)} recipes need cooking")
    return ok(_Result)
