"""The whole household cookbook as list DTOs, for the planners that score
every recipe at once (auto-build, swap suggestions)."""
from dora_api.features.recipes.get_recipes import GetRecipesHandler
from dora_api.infrastructure.query_options import QueryOptions
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

# The cookbook is bounded (tens to hundreds of recipes), so one page holds it.
_ALL_RECIPES_LIMIT = 10_000


def load_all_recipe_dtos(repository: SqlAlchemyRepository) -> list:
    return list(
        GetRecipesHandler(repository)
        .handle(QueryOptions(page=1, limit=_ALL_RECIPES_LIMIT))
        .items
    )
