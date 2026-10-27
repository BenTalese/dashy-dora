"""Category CRUD — the user-configurable recipe category vocabulary, distinct from cuisine (L235).
Shares its behaviour with the other vocabularies through
`features/_vocabulary.py`; this module owns the DTO and the routes.

Endpoints:

  GET    /api/categories        — list all (with recipe counts), ordered
  POST   /api/categories        — create
  PATCH  /api/categories/<id>   — rename
  DELETE /api/categories/<id>   — delete (recipes' category_id → NULL via the FK's ON DELETE SET NULL)
"""
import logging
from dataclasses import dataclass
from uuid import UUID

from dora_api.domain.entities.category import Category
from dora_api.features._vocabulary import (VocabularyHandler,
                                           VocabularyNameRequest,
                                           counts_by_recipe_fk)
from dora_api.features.routers import CATEGORY_ROUTER
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  created, not_found, ok)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)

_RECIPE_COUNTS = counts_by_recipe_fk("category")


@dataclass(frozen=True, slots=True)
class CategoryDto:
    category_id: UUID
    name: str
    sequence: int
    recipe_count: int


def _handler() -> VocabularyHandler[Category]:
    return VocabularyHandler(SqlAlchemyRepository(), Category, _RECIPE_COUNTS)


@CATEGORY_ROUTER.route("", methods=["GET"])
def get_categories():
    return ok([
        CategoryDto(category_id=entry.id, name=entry.name, sequence=entry.sequence, recipe_count=count)
        for entry, count in _handler().list()
    ])


@CATEGORY_ROUTER.route("", methods=["POST"])
@has_request_body(VocabularyNameRequest)
def create_category():
    _Request: VocabularyNameRequest = get_request_body()
    _Response = _handler().create(_Request.name)
    if _Response.duplicate:
        return business_rule_violation(f"A category named '{_Request.name}' already exists.")
    _LOGGER.info(f"Created category {_Response.entry_id} '{_Request.name}'")
    return created(
        _Response.entry_id,
        f"{CATEGORY_ROUTER.name}.{get_categories.__name__}",
        "category_id",
        body={"category_id": _Response.entry_id},
    )


@CATEGORY_ROUTER.route("/<uuid:category_id>", methods=["PATCH"])
@has_request_body(VocabularyNameRequest)
def update_category(category_id: UUID):
    _Request: VocabularyNameRequest = get_request_body()
    _Response = _handler().rename(category_id, _Request.name)
    if _Response.not_found:
        return not_found("Category", category_id)
    if _Response.duplicate:
        return business_rule_violation(f"A category named '{_Request.name}' already exists.")
    return ok({"category_id": category_id})


@CATEGORY_ROUTER.route("/<uuid:category_id>", methods=["DELETE"])
def delete_category(category_id: UUID):
    _Response = _handler().delete(category_id)
    if _Response.not_found:
        return not_found("Category", category_id)
    _LOGGER.info(f"Deleted category {category_id}; {_Response.recipes_affected} recipe reference(s) removed")
    return ok({"recipes_affected": _Response.recipes_affected})
