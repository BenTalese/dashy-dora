import logging
from dataclasses import dataclass
from uuid import UUID

from dora_api.domain.entities.meal_plan import MealPlan
from dora_api.features.routers import MEAL_PLAN_ROUTER
from dora_api.infrastructure.api_response import no_content, not_found
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DeleteMealPlanResponse:
    meal_plan_not_found: bool = False


class DeleteMealPlanHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, meal_plan_id: UUID) -> DeleteMealPlanResponse:
        _Plan = (
            self.repository
            .get(MealPlan)
            .include(MealPlan.Fields.ENTRIES)
            .one(EntityField(MealPlan, "id").eq(meal_plan_id))
        )
        if not _Plan:
            return DeleteMealPlanResponse(meal_plan_not_found = True)
        self.repository.remove(_Plan)
        self.repository.save_changes()
        return DeleteMealPlanResponse()


@MEAL_PLAN_ROUTER.route("<uuid:meal_plan_id>", methods=["DELETE"])
def delete_meal_plan(meal_plan_id: UUID):
    _Handler = DeleteMealPlanHandler(SqlAlchemyRepository())
    _Response = _Handler.handle(meal_plan_id)
    if _Response.meal_plan_not_found:
        return not_found(MealPlan.__name__, meal_plan_id)
    _LOGGER.info(f"Deleted meal plan {meal_plan_id}")
    return no_content()
