import logging
from dataclasses import dataclass
from uuid import UUID

from flask import request

from dora_api.domain.entities.recipe_collection import RecipeCollection
from dora_api.features.routers import RECIPE_COLLECTION_ROUTER
from dora_api.infrastructure.api_response import bad_request, paginated
from dora_api.infrastructure.query_options import (InvalidQueryParameter,
                                                   parse_query_options)
from dora_api.persistence.field import EntityField
from dora_api.persistence.page import Page
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RecipeCollectionDto:
    recipe_collection_id: UUID
    name: str

    @classmethod
    def from_entity(cls, collection: RecipeCollection) -> 'RecipeCollectionDto':
        return RecipeCollectionDto(
            recipe_collection_id = collection.id,
            name = collection.name,
        )


_FIELD_MAP: dict[str, EntityField] = {
    "recipe_collection_id": EntityField(RecipeCollection, "id"),
}


class GetRecipeCollectionsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, options) -> Page[RecipeCollectionDto]:
        return self.repository.get(RecipeCollection).paginate(
            options, RecipeCollectionDto.from_entity, field_map=_FIELD_MAP
        )

    def handle_by_id(self, recipe_collection_id: UUID) -> RecipeCollectionDto | None:
        entity = self.repository.get(RecipeCollection).by_id(recipe_collection_id)
        return RecipeCollectionDto.from_entity(entity) if entity else None


@RECIPE_COLLECTION_ROUTER.route("")
def get_recipe_collections():
    try:
        _Options = parse_query_options(request.args)
        _Page = GetRecipeCollectionsHandler(SqlAlchemyRepository()).handle(_Options)
    except InvalidQueryParameter as exc:
        return bad_request(str(exc))
    _LOGGER.info(f"Retrieved {len(_Page.items)} of {_Page.total} recipe collections.")
    return paginated(_Page.items, _Page.total, _Page.page, _Page.limit)
