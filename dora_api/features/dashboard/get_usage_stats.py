"""GET /api/dashboard/usage-stats — what this household has *done* with Dora.

Owner feedback 2026-09-05: *"About screen 'your kitchen' should be more 'your
usage of the app' rather than a repeat of the dashboard or reports. Like total
stock items (already there I think), total spend tracked, total meals planned,
total shopping lists, total recipes curated, etc."*

The About page's "at a glance" block was reading
`GET /api/dashboard/summary` — the dashboard's own payload — so it showed
*current state*: how many items are low, how many are out, what's coming up
this week. Those are the dashboard's job and they answer "what needs doing".
Standing in the About page they answered a question nobody asked there, and
they changed every time you shopped.

These are **cumulative** instead: counts that only ever go up, of things the
household has accumulated or done. The distinction is the whole point of the
owner's note — "items running low" is a chore list, "1,208 prices recorded" is
a record of use. Nothing here is a filtered or windowed figure; where an
entity is deletable the count is of what survives, which is the honest answer
to "how much have you got".

**Money-gated fields are None, not zero, when money is off** (R-058). Zero
would read as "you have tracked no spend", which is false — the install has
opted out of the question. The SPA drops the tile entirely rather than
rendering "—".
"""
import logging
from dataclasses import dataclass

from dora_api.domain.entities.cook_event import CookEvent
from dora_api.domain.entities.meal_plan_entry import MealPlanEntry
from dora_api.domain.entities.recipe import Recipe
from dora_api.domain.entities.shopping_list import SHOPPING_LIST_STATUS_DONE, ShoppingList
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_item_price_observation import StockItemPriceObservation
from dora_api.features.app_settings.access import money_features_enabled
from dora_api.features.routers import DASHBOARD_ROUTER
from dora_api.features.shopping_lists._line_price import lifetime_spend
from dora_api.infrastructure.api_response import ok
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class UsageStatsDto:
    stock_items: int
    recipes: int
    meals_planned: int
    meals_cooked: int
    shopping_lists: int
    shops_completed: int
    # Money-gated (R-058). None — never 0 — when the install has money off.
    total_spend: float | None
    prices_recorded: int | None


class GetUsageStatsHandler:
    def __init__(self, repository: SqlAlchemyRepository) -> None:
        self.repository = repository

    def handle(self) -> UsageStatsDto:
        # Plain counts through the repository (R-005 — this used to reach for
        # `db.metadata.tables` + `db.session` for six counts the port already
        # does; finalisation 08-R6). Lifetime spend lives beside the per-line
        # price ladder in `_line_price.lifetime_spend` so About and Reports
        # read one rule.
        repo = self.repository
        money_on = money_features_enabled(repo)
        done = EntityField(ShoppingList, ShoppingList.Fields.STATUS).eq(SHOPPING_LIST_STATUS_DONE)

        return UsageStatsDto(
            stock_items=repo.get(StockItem).count(),
            recipes=repo.get(Recipe).count(),
            # Every entry ever placed on a plan, including past weeks. The
            # dashboard counts only what is upcoming; this is the opposite
            # question and the reason the About block needed its own endpoint.
            meals_planned=repo.get(MealPlanEntry).count(),
            # One row per cook (a batch cook that feeds five days is one
            # event), so this counts cooking sessions, not portions.
            meals_cooked=repo.get(CookEvent).count(),
            shopping_lists=repo.get(ShoppingList).count(),
            shops_completed=repo.get(ShoppingList).count(done),
            total_spend=lifetime_spend(repo.session) if money_on else None,
            prices_recorded=(
                repo.get(StockItemPriceObservation).count() if money_on else None
            ),
        )


@DASHBOARD_ROUTER.route("/usage-stats", methods=["GET"])
def get_usage_stats():
    _Result = GetUsageStatsHandler(SqlAlchemyRepository()).handle()
    _LOGGER.debug(
        "Usage stats: %d items, %d recipes, %d meals planned",
        _Result.stock_items, _Result.recipes, _Result.meals_planned,
    )
    return ok(_Result)
