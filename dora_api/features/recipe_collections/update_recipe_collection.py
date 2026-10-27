import logging
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.recipe_collection import RecipeCollection
from dora_api.features.routers import RECIPE_COLLECTION_ROUTER
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  no_content, not_found)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


class UpdateRecipeCollectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length = 1, max_length = 255)


@dataclass(slots=True)
class UpdateRecipeCollectionResponse:
    recipe_collection_not_found: bool = False
    recipe_collection_already_exists: bool = False


class UpdateRecipeCollectionHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: UpdateRecipeCollectionRequest, recipe_collection_id: UUID) -> UpdateRecipeCollectionResponse:
        _Collection = self.repository.get(RecipeCollection).by_id(recipe_collection_id)
        if not _Collection:
            return UpdateRecipeCollectionResponse(recipe_collection_not_found = True)

        _NameField = EntityField(RecipeCollection, RecipeCollection.Fields.NAME)
        _SameName: RecipeCollection | None = self.repository.get(RecipeCollection).one(_NameField.eq(request.name))
        if _SameName and _SameName.id != recipe_collection_id:
            return UpdateRecipeCollectionResponse(recipe_collection_already_exists = True)

        _Collection.name = request.name
        self.repository.save_changes()
        return UpdateRecipeCollectionResponse()


@RECIPE_COLLECTION_ROUTER.route("<uuid:recipe_collection_id>", methods=["PATCH"])
@has_request_body(UpdateRecipeCollectionRequest)
def update_recipe_collection(recipe_collection_id: UUID):
    _Handler = UpdateRecipeCollectionHandler(SqlAlchemyRepository())
    _Request: UpdateRecipeCollectionRequest = get_request_body()
    _Response = _Handler.handle(_Request, recipe_collection_id)

    if _Response.recipe_collection_not_found:
        return not_found(RecipeCollection.__name__, recipe_collection_id)

    if _Response.recipe_collection_already_exists:
        _LOGGER.warning(f"Recipe collection already exists: {_Request.name}")
        return business_rule_violation(
            f"A recipe collection with the name '{_Request.name}' already exists."
        )

    return no_content()
