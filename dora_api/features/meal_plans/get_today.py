"""GET /api/meal-plans/today — the household's current date in the install's
configured timezone (Meal Plans C-2.K).

The planner trusts this rather than recomputing "today" from the browser clock,
so past-day dimming + the drop guard match the server's date-boundary rules
exactly (no UTC-vs-local drift).
"""
import logging

from dora_api.features.app_settings.clock import household_today
from dora_api.features.routers import MEAL_PLAN_ROUTER
from dora_api.infrastructure.api_response import ok
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)


@MEAL_PLAN_ROUTER.route("today")
def get_today():
    _Today = household_today(SqlAlchemyRepository())
    _LOGGER.debug("Household today: %s", _Today)
    return ok({"today": _Today.isoformat()})
