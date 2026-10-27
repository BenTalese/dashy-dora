import logging
from dataclasses import dataclass
from uuid import UUID

from dora_api.domain.entities.recipe_collection import RecipeCollection
from dora_api.features.routers import RECIPE_COLLECTION_ROUTER
from dora_api.infrastructure.api_response import no_content, not_found
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DeleteRecipeCollectionResponse:
    recipe_collection_not_found: bool = False


class DeleteRecipeCollectionHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, recipe_collection_id: UUID) -> DeleteRecipeCollectionResponse:
        _Collection = self.repository.get(RecipeCollection).by_id(recipe_collection_id)
        if not _Collection:
            return DeleteRecipeCollectionResponse(recipe_collection_not_found = True)

        # Recipes referencing this collection get recipe_collection_id NULLed by FK.
        self.repository.remove(_Collection)
        self.repository.save_changes()
        return DeleteRecipeCollectionResponse()


@RECIPE_COLLECTION_ROUTER.route("<uuid:recipe_collection_id>", methods=["DELETE"])
def delete_recipe_collection(recipe_collection_id: UUID):
    _Handler = DeleteRecipeCollectionHandler(SqlAlchemyRepository())
    _Response = _Handler.handle(recipe_collection_id)

    if _Response.recipe_collection_not_found:
        return not_found(RecipeCollection.__name__, recipe_collection_id)

    _LOGGER.info(f"Deleted recipe collection {recipe_collection_id}")
    return no_content()
