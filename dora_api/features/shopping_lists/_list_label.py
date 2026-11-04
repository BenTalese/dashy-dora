"""One list label per request: the household's locale and today, read once,
applied to each list (FU-969)."""
from typing import Callable

from dora_api.domain.entities.shopping_list import ShoppingList
from dora_api.features.app_settings.clock import household_locale, household_today


def list_labeller(repository) -> Callable[[ShoppingList], str]:
    locale = household_locale(repository)
    today = household_today(repository)
    return lambda shopping_list: shopping_list.display_label(locale, today)
