import logging
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.stock_location import (ALLOWED_LOCATION_KINDS,
                                                     LOCATION_KIND_AREA,
                                                     LOCATION_KIND_SECTION,
                                                     LOCATION_KIND_ZONE,
                                                     StockLocation)
from dora_api.features.routers import LOCATION_ROUTER
from dora_api.infrastructure.api_response import (bad_request,
                                                  business_rule_violation,
                                                  created)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


# Allowed parent kind per child kind, so the tree can't grow sideways
# (e.g. a section under a zone, skipping the area level).
_VALID_PARENT_KIND = {
    LOCATION_KIND_ZONE: None,
    LOCATION_KIND_AREA: LOCATION_KIND_ZONE,
    LOCATION_KIND_SECTION: LOCATION_KIND_AREA,
}


def _with_article(word: str) -> str:
    return f"{'an' if word[:1].lower() in 'aeiou' else 'a'} {word}"


def _parent_kind_mismatch_message(kind: str, actual_parent_kind: str | None) -> str:
    """Names the parent the caller actually chose, and where `kind` belongs."""
    expected = _VALID_PARENT_KIND[kind]
    if expected is None:
        return f"{_with_article(kind).capitalize()} is top-level and can't have a parent."
    if actual_parent_kind is None:
        return f"{_with_article(kind).capitalize()} needs a parent {expected}."
    return (
        f"{_with_article(kind).capitalize()} can't live under "
        f"{_with_article(actual_parent_kind)} — it belongs under {_with_article(expected)}."
    )


class CreateLocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    kind: str
    parent_id: UUID | None = None
    sequence: int = 0


@dataclass(slots=True)
class CreateLocationResponse:
    new_location_id: UUID | None = None
    invalid_kind: bool = False
    parent_not_found: bool = False
    parent_kind_mismatch: bool = False
    # The kind of the parent the caller actually picked — None when there was
    # no parent at all. Feeds the mismatch message so it names what's wrong.
    actual_parent_kind: str | None = None


class CreateLocationHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: CreateLocationRequest) -> CreateLocationResponse:
        if request.kind not in ALLOWED_LOCATION_KINDS:
            return CreateLocationResponse(invalid_kind=True)

        expected_parent_kind = _VALID_PARENT_KIND[request.kind]
        if expected_parent_kind is None:
            if request.parent_id is not None:
                return CreateLocationResponse(parent_kind_mismatch=True)
        else:
            if request.parent_id is None:
                return CreateLocationResponse(parent_kind_mismatch=True)
            parent: StockLocation | None = (
                self.repository.get(StockLocation).by_id(request.parent_id)
            )
            if parent is None:
                return CreateLocationResponse(parent_not_found=True)
            if parent.kind != expected_parent_kind:
                return CreateLocationResponse(
                    parent_kind_mismatch=True, actual_parent_kind=parent.kind,
                )

        new_location = StockLocation(
            name = request.name,
            kind = request.kind,
            parent_id = request.parent_id,
            sequence = request.sequence,
        )
        self.repository.add(new_location)
        self.repository.save_changes()
        return CreateLocationResponse(new_location_id = new_location.id)


@LOCATION_ROUTER.route("", methods=["POST"])
@has_request_body(CreateLocationRequest)
def create_location():
    _Handler = CreateLocationHandler(SqlAlchemyRepository())
    _Request: CreateLocationRequest = get_request_body()
    _Response = _Handler.handle(_Request)

    if _Response.invalid_kind:
        return bad_request(f"Invalid location kind '{_Request.kind}'.")
    if _Response.parent_not_found:
        return business_rule_violation("Parent location was not found.")
    if _Response.parent_kind_mismatch:
        return business_rule_violation(
            _parent_kind_mismatch_message(_Request.kind, _Response.actual_parent_kind)
        )

    _LOGGER.info(f"Created {_Request.kind} '{_Request.name}' ({_Response.new_location_id})")
    return created(
        resource_id=_Response.new_location_id,
        get_route="LOCATION_ROUTER.get_location_tree",
        id_attribute_name="location_id",
        body={"location_id": _Response.new_location_id},
    )
