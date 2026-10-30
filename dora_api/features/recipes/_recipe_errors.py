"""The failure half of a recipe write, shared by create and update
(finalisation 01-R12): one set of outcome fields and one mapping from an
outcome to its HTTP response."""
import logging
from dataclasses import dataclass
from uuid import UUID

from flask import Response
from pydantic import BaseModel

from dora_api.domain.entities.category import Category
from dora_api.domain.entities.cuisine import Cuisine
from dora_api.domain.entities.recipe_collection import RecipeCollection
from dora_api.domain.entities.stock_item import StockItem
from dora_api.infrastructure.api_response import (bad_request,
                                                  business_rule_violation,
                                                  entity_existence_failure,
                                                  entity_existence_failures,
                                                  validation_failed)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RecipeWriteOutcome:
    recipe_already_exists: bool = False
    recipe_collection_not_found: bool = False
    cuisine_not_found: bool = False
    category_not_found: bool = False
    missing_stock_item_ids: tuple[UUID, ...] = ()
    invalid_tag_message: str | None = None
    invalid_tool_message: str | None = None
    invalid_step_message: str | None = None
    invalid_step_image_message: str | None = None
    invalid_section_message: str | None = None
    invalid_vocabulary_message: str | None = None
    invalid_choice_message: str | None = None


# (outcome flag, request field, entity name) — a not-found only reports when
# the request actually named an id (on a PATCH, an omitted field is None).
_FK_CHECKS = (
    ("recipe_collection_not_found", "recipe_collection_id", RecipeCollection.__name__),
    ("cuisine_not_found", "cuisine_id", Cuisine.__name__),
    ("category_not_found", "category_id", Category.__name__),
)

# (outcome message, log label, response builder)
_MESSAGE_CHECKS = (
    ("invalid_tag_message", "recipe tag", bad_request),
    ("invalid_tool_message", "recipe tool", bad_request),
    ("invalid_step_message", "recipe step", bad_request),
    ("invalid_step_image_message", "recipe step image",
     lambda message: validation_failed({"step_images": [message]})),
    ("invalid_section_message", "recipe section", bad_request),
    ("invalid_choice_message", "ingredient choice", business_rule_violation),
    ("invalid_vocabulary_message", "recipe vocabulary", bad_request),
)


def recipe_write_error_response(outcome: RecipeWriteOutcome, request: BaseModel) -> Response | None:
    """The error response for a failed write, or None when it succeeded."""
    if outcome.recipe_already_exists:
        _LOGGER.warning("Recipe already exists with name: %s", request.name)
        return business_rule_violation(f"A recipe with the name '{request.name}' already exists.")
    for flag, field, entity in _FK_CHECKS:
        value = getattr(request, field)
        if getattr(outcome, flag) and value is not None:
            _LOGGER.warning("%s not found: %s", entity, value)
            return entity_existence_failure(entity, field, value)
    if outcome.missing_stock_item_ids:
        _LOGGER.warning("Stock items not found: %s", outcome.missing_stock_item_ids)
        return entity_existence_failures(StockItem.__name__, "ingredients", *outcome.missing_stock_item_ids)
    for attr, label, respond in _MESSAGE_CHECKS:
        message = getattr(outcome, attr)
        if message:
            _LOGGER.warning("Invalid %s: %s", label, message)
            return respond(message)
    return None
