import logging
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.stock_location import StockLocation
from dora_api.features.routers import LOCATION_ROUTER
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  no_content, not_found)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


class UpdateLocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    sequence: int | None = None
    parent_id: UUID | None = None


@dataclass(slots=True)
class UpdateLocationResponse:
    location_not_found: bool = False
    parent_not_found: bool = False
    would_create_cycle: bool = False
    parent_kind_mismatch: bool = False


class UpdateLocationHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: UpdateLocationRequest, location_id: UUID) -> UpdateLocationResponse:
        location: StockLocation | None = self.repository.get(StockLocation).by_id(location_id)
        if location is None:
            return UpdateLocationResponse(location_not_found=True)

        if "name" in request.model_fields_set and request.name is not None:
            location.name = request.name

        if "sequence" in request.model_fields_set and request.sequence is not None:
            location.sequence = request.sequence

        if "parent_id" in request.model_fields_set:
            new_parent_id = request.parent_id
            if new_parent_id is not None:
                parent: StockLocation | None = (
                    self.repository.get(StockLocation).by_id(new_parent_id)
                )
                if parent is None:
                    return UpdateLocationResponse(parent_not_found=True)

                # Cycle check — walk up from the proposed parent.
                cursor: StockLocation | None = parent
                while cursor is not None:
                    if cursor.id == location_id:
                        return UpdateLocationResponse(would_create_cycle=True)
                    if cursor.parent_id is None:
                        break
                    cursor = self.repository.get(StockLocation).by_id(cursor.parent_id)

                # Kind constraint: parent's kind must be one rung above ours.
                if (location.kind == "section" and parent.kind != "area") or (
                    location.kind == "area" and parent.kind != "zone"
                ) or (location.kind == "zone"):
                    return UpdateLocationResponse(parent_kind_mismatch=True)
            elif location.kind != "zone":
                # Only a zone may sit at the root; an area/section always
                # has a parent one rung above it.
                return UpdateLocationResponse(parent_kind_mismatch=True)

            location.parent_id = new_parent_id

        self.repository.save_changes()
        return UpdateLocationResponse()


@LOCATION_ROUTER.route("/<uuid:location_id>", methods=["PATCH"])
@has_request_body(UpdateLocationRequest)
def update_location(location_id: UUID):
    _Handler = UpdateLocationHandler(SqlAlchemyRepository())
    _Request: UpdateLocationRequest = get_request_body()
    _Response = _Handler.handle(_Request, location_id)

    if _Response.location_not_found:
        return not_found("StockLocation", location_id)
    if _Response.parent_not_found:
        return business_rule_violation("Parent location was not found.")
    if _Response.would_create_cycle:
        return business_rule_violation(
            "Cannot move a location underneath itself or one of its descendants."
        )
    if _Response.parent_kind_mismatch:
        return business_rule_violation(
            "Reparenting would put this location under an invalid parent kind."
        )

    _LOGGER.info(f"Updated location {location_id}")
    return no_content()
