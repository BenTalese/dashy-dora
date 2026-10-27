"""Cuisine CRUD — the user-configurable recipe cuisine vocabulary.
Shares its behaviour with the other vocabularies through
`features/_vocabulary.py`; this module owns the DTO and the routes.

Endpoints:

  GET    /api/cuisines        — list all (with recipe counts), ordered
  POST   /api/cuisines        — create
  PATCH  /api/cuisines/<id>   — rename
  DELETE /api/cuisines/<id>   — delete (recipes' cuisine_id → NULL via the FK's ON DELETE SET NULL)
"""
import logging
from dataclasses import dataclass
from uuid import UUID

from dora_api.domain.entities.cuisine import Cuisine
from dora_api.features._vocabulary import (VocabularyHandler,
                                           VocabularyNameRequest,
                                           counts_by_recipe_fk)
from dora_api.features.routers import CUISINE_ROUTER
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  created, not_found, ok)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)

_RECIPE_COUNTS = counts_by_recipe_fk("cuisine")


@dataclass(frozen=True, slots=True)
class CuisineDto:
    cuisine_id: UUID
    name: str
    sequence: int
    recipe_count: int


def _handler() -> VocabularyHandler[Cuisine]:
    return VocabularyHandler(SqlAlchemyRepository(), Cuisine, _RECIPE_COUNTS)


@CUISINE_ROUTER.route("", methods=["GET"])
def get_cuisines():
    return ok([
        CuisineDto(cuisine_id=entry.id, name=entry.name, sequence=entry.sequence, recipe_count=count)
        for entry, count in _handler().list()
    ])


@CUISINE_ROUTER.route("", methods=["POST"])
@has_request_body(VocabularyNameRequest)
def create_cuisine():
    _Request: VocabularyNameRequest = get_request_body()
    _Response = _handler().create(_Request.name)
    if _Response.duplicate:
        return business_rule_violation(f"A cuisine named '{_Request.name}' already exists.")
    _LOGGER.info(f"Created cuisine {_Response.entry_id} '{_Request.name}'")
    return created(
        _Response.entry_id,
        f"{CUISINE_ROUTER.name}.{get_cuisines.__name__}",
        "cuisine_id",
        body={"cuisine_id": _Response.entry_id},
    )


@CUISINE_ROUTER.route("/<uuid:cuisine_id>", methods=["PATCH"])
@has_request_body(VocabularyNameRequest)
def update_cuisine(cuisine_id: UUID):
    _Request: VocabularyNameRequest = get_request_body()
    _Response = _handler().rename(cuisine_id, _Request.name)
    if _Response.not_found:
        return not_found("Cuisine", cuisine_id)
    if _Response.duplicate:
        return business_rule_violation(f"A cuisine named '{_Request.name}' already exists.")
    return ok({"cuisine_id": cuisine_id})


@CUISINE_ROUTER.route("/<uuid:cuisine_id>", methods=["DELETE"])
def delete_cuisine(cuisine_id: UUID):
    _Response = _handler().delete(cuisine_id)
    if _Response.not_found:
        return not_found("Cuisine", cuisine_id)
    _LOGGER.info(f"Deleted cuisine {cuisine_id}; {_Response.recipes_affected} recipe reference(s) removed")
    return ok({"recipes_affected": _Response.recipes_affected})
