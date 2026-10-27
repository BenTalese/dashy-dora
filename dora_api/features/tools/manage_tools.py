"""Tool CRUD — the user-configurable recipe tool vocabulary (kitchen tools; counts come from the RecipeTool links).
Shares its behaviour with the other vocabularies through
`features/_vocabulary.py`; this module owns the DTO and the routes.

Endpoints:

  GET    /api/tools        — list all (with recipe counts), ordered
  POST   /api/tools        — create
  PATCH  /api/tools/<id>   — rename
  DELETE /api/tools/<id>   — delete (RecipeTool links cascade away)
"""
import logging
from dataclasses import dataclass
from uuid import UUID

from dora_api.domain.entities.tool import Tool
from dora_api.features._vocabulary import (VocabularyHandler,
                                           VocabularyNameRequest,
                                           counts_by_link_table)
from dora_api.features.routers import TOOL_ROUTER
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  created, not_found, ok)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)

_RECIPE_COUNTS = counts_by_link_table("RecipeTool", "tool_id")


@dataclass(frozen=True, slots=True)
class ToolDto:
    tool_id: UUID
    name: str
    sequence: int
    recipe_count: int


def _handler() -> VocabularyHandler[Tool]:
    return VocabularyHandler(SqlAlchemyRepository(), Tool, _RECIPE_COUNTS)


@TOOL_ROUTER.route("", methods=["GET"])
def get_tools():
    return ok([
        ToolDto(tool_id=entry.id, name=entry.name, sequence=entry.sequence, recipe_count=count)
        for entry, count in _handler().list()
    ])


@TOOL_ROUTER.route("", methods=["POST"])
@has_request_body(VocabularyNameRequest)
def create_tool():
    _Request: VocabularyNameRequest = get_request_body()
    _Response = _handler().create(_Request.name)
    if _Response.duplicate:
        return business_rule_violation(f"A tool named '{_Request.name}' already exists.")
    _LOGGER.info(f"Created tool {_Response.entry_id} '{_Request.name}'")
    return created(
        _Response.entry_id,
        f"{TOOL_ROUTER.name}.{get_tools.__name__}",
        "tool_id",
        body={"tool_id": _Response.entry_id},
    )


@TOOL_ROUTER.route("/<uuid:tool_id>", methods=["PATCH"])
@has_request_body(VocabularyNameRequest)
def update_tool(tool_id: UUID):
    _Request: VocabularyNameRequest = get_request_body()
    _Response = _handler().rename(tool_id, _Request.name)
    if _Response.not_found:
        return not_found("Tool", tool_id)
    if _Response.duplicate:
        return business_rule_violation(f"A tool named '{_Request.name}' already exists.")
    return ok({"tool_id": tool_id})


@TOOL_ROUTER.route("/<uuid:tool_id>", methods=["DELETE"])
def delete_tool(tool_id: UUID):
    _Response = _handler().delete(tool_id)
    if _Response.not_found:
        return not_found("Tool", tool_id)
    _LOGGER.info(f"Deleted tool {tool_id}; {_Response.recipes_affected} recipe link(s) removed")
    return ok({"recipes_affected": _Response.recipes_affected})
