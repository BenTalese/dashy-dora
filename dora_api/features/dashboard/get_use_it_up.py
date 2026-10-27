"""GET /api/dashboard/use-it-up — what's about to go off, and what it cooks.

Owner feedback, 2026-09-04. The dashboard used to carry a "Needs your
attention" card and a "Dora suggests" card; between them and the alerts bell
and the Dora chat, four surfaces on one screen said the same thing. The owner
cut the two cards and asked the obvious next question: *"Surely… there's a LOT
of data in this app that is connected. Are there some insights into this that
could be useful to the end user?"*

This is one of the two answers. Expiry alone is not an insight — the bell
already states it, and stating it again is what made the attention card
redundant. The insight is the **join**: these three things go off this week,
*and here are the recipes that use them*, so the answer to "what do I cook
tonight" is the same as the answer to "what stops me throwing food away".

Nothing here is new domain logic. The expiry window is the household's own
`expiring_soon_window_days` setting read through the shared
`stock_attention` predicates (B1 — never a literal at the call site), and the
recipe→stock-item link is the same `_stock_item_id` FK `planned_demand` walks.
What is new is putting them together, which is precisely the work R-003 says
belongs on the server: the SPA cannot join expiry windows to ingredient links
without re-implementing both.

Not gated. Expiry needs no feature flag — every install tracks it — and the
card degrades to its empty state on a pantry with no expiry dates, which is
the honest answer rather than a hidden card.
"""
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List
from uuid import UUID

from dora_api.domain.entities.recipe import Recipe
from dora_api.domain.entities.recipe_ingredient import RecipeIngredient
from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.features.app_settings.clock import household_today
from dora_api.features.routers import DASHBOARD_ROUTER
from dora_api.features.stock_items.stock_attention import (is_expired,
                                                           is_expiring_soon)
from dora_api.infrastructure.api_response import ok
from dora_api.infrastructure.ports import Repository
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)

# How many rows each half of the card shows. The card is one of nine on the
# page — it answers "what should I deal with", not "list my pantry".
MAX_ITEMS = 5
MAX_RECIPES = 3


@dataclass(frozen=True, slots=True)
class UseItUpItem:
    stock_item_id: UUID
    name: str
    expiry_date: date
    # Negative when already past. The SPA renders the words ("2 days",
    # "today", "overdue") — the server owns the arithmetic so "today" means
    # the household's today, not the browser's (R-021).
    days_remaining: int
    is_expired: bool


@dataclass(frozen=True, slots=True)
class UseItUpRecipe:
    recipe_id: UUID
    name: str
    # Which of the expiring items this recipe would use up. Named, not
    # counted: "uses spinach and ricotta" is a reason to cook it; "uses 2 of
    # your expiring items" is a statistic about it.
    uses: List[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class UseItUpDto:
    items: List[UseItUpItem] = field(default_factory=list)
    recipes: List[UseItUpRecipe] = field(default_factory=list)
    # The household's own window, so the card's copy can name it rather than
    # hardcoding "this week" over a setting that might say 3 days or 30.
    window_days: int = 7


class GetUseItUpHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self) -> UseItUpDto:
        today = household_today(self.repository)
        window = int(get_or_create_app_setting(self.repository).expiring_soon_window_days)

        # Expiry is indexed and most pantries are small, but "every item with
        # an expiry date at all" is still the wrong fetch on a large one — so
        # bound it in SQL and let the shared predicates do the grading.
        # `<=` on the far edge because `is_expiring_soon` is inclusive.
        horizon = today + timedelta(days=window)
        candidates: List[StockItem] = self.repository.get(StockItem).all(
            EntityField(StockItem, StockItem.Fields.EXPIRY_DATE).is_not_null()
            & EntityField(StockItem, StockItem.Fields.EXPIRY_DATE).lte(horizon)
        )

        # Expired first, then soonest. An item already past its date is the
        # more urgent fact *and* the one the household is most likely to have
        # stopped seeing, which is why it leads rather than being filtered out.
        graded = [
            i for i in candidates
            if is_expired(i, today) or is_expiring_soon(i, today, window)
        ]
        graded.sort(key=lambda i: (i.expiry_date, i.name.lower()))
        chosen = graded[:MAX_ITEMS]

        items = [
            UseItUpItem(
                stock_item_id=i.id,
                name=i.name,
                expiry_date=i.expiry_date,
                days_remaining=(i.expiry_date - today).days,
                is_expired=is_expired(i, today),
            )
            for i in chosen
        ]

        return UseItUpDto(
            items=items,
            recipes=self._recipes_using(chosen),
            window_days=window,
        )

    def _recipes_using(self, items: List[StockItem]) -> List[UseItUpRecipe]:
        """Recipes that require at least one of `items`, best first.

        "Best" = uses the most of them, tie-broken by name so the list is
        stable between loads (an insight card that reshuffles on every refresh
        reads as noise).

        R-032: `RecipeIngredient.stock_item` is `lazy="noload"` and reading it
        returns None silently, so the link is resolved off the private mapped
        FK column — the same idiom `planned_demand` and `_level_access` use
        after that trap made the buy-verdict endpoint answer "unsure" for
        every item.

        Optional ingredients are skipped: "you could put the spinach in" is
        not a reason the recipe uses it up.
        """
        if not items:
            return []
        name_by_item = {i.id: i.name for i in items}
        ingredients: List[RecipeIngredient] = self.repository.get(RecipeIngredient).all(
            EntityField(RecipeIngredient, "_stock_item_id").in_(list(name_by_item))
        )
        uses_by_recipe: dict[UUID, set[UUID]] = {}
        for ing in ingredients:
            if ing.is_optional or ing._stock_item_id is None:
                continue
            uses_by_recipe.setdefault(ing._recipe_id, set()).add(ing._stock_item_id)
        if not uses_by_recipe:
            return []

        recipes: List[Recipe] = self.repository.get(Recipe).all(
            EntityField(Recipe, Recipe.Fields.ID).in_(list(uses_by_recipe))
        )
        rows = [
            UseItUpRecipe(
                recipe_id=r.id,
                name=r.name,
                # Ordered by the item list itself, so the names read in the
                # same urgency order the card shows above.
                uses=[
                    name_by_item[i.id] for i in items
                    if i.id in uses_by_recipe.get(r.id, set())
                ],
            )
            for r in recipes
        ]
        rows.sort(key=lambda r: (-len(r.uses), r.name.lower()))
        return rows[:MAX_RECIPES]


@DASHBOARD_ROUTER.route("/use-it-up", methods=["GET"])
def get_use_it_up():
    _Result = GetUseItUpHandler(SqlAlchemyRepository()).handle()
    _LOGGER.debug(
        "Use it up: %d expiring items, %d recipes",
        len(_Result.items), len(_Result.recipes),
    )
    return ok(_Result)
