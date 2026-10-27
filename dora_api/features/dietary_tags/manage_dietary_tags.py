"""DietaryTag CRUD (C-4 Chunk 2) — the user-configurable dietary / allergen
/ nutritional tag vocabulary (replaces the in-code catalogue). Each tag has a
grouping `category` label (e.g. "Allergen-free") used to cluster the picker.

Endpoints:

  GET    /api/dietary-tags        — list all (with recipe counts), ordered
  POST   /api/dietary-tags        — create
  PATCH  /api/dietary-tags/<id>   — rename / recategorise
  DELETE /api/dietary-tags/<id>   — delete (RecipeTag links cascade away)
"""
import logging
from dataclasses import dataclass
from typing import List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from dora_api.app import db
from dora_api.domain.entities.dietary_tag import DietaryTag
from dora_api.features.routers import DIETARY_TAG_ROUTER
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  created, not_found, ok)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DietaryTagDto:
    dietary_tag_id: UUID
    name: str
    category: str
    sequence: int
    recipe_count: int


def _recipe_counts() -> dict[UUID, int]:
    table = db.metadata.tables["RecipeTag"]
    rows = db.session.execute(
        select(table.c.dietary_tag_id, func.count(table.c.recipe_id))
        .group_by(table.c.dietary_tag_id)
    ).all()
    return {row[0]: int(row[1] or 0) for row in rows}


# ───── List ──────────────────────────────────────────────────────────────

class GetDietaryTagsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self) -> List[DietaryTagDto]:
        tags: List[DietaryTag] = self.repository.get(DietaryTag).all()
        counts = _recipe_counts()
        out = [
            DietaryTagDto(
                dietary_tag_id=t.id,
                name=t.name,
                category=t.category,
                sequence=t.sequence,
                recipe_count=counts.get(t.id, 0),
            )
            for t in tags
        ]
        out.sort(key=lambda t: (t.sequence, t.category.lower(), t.name.lower()))
        return out


@DIETARY_TAG_ROUTER.route("", methods=["GET"])
def get_dietary_tags():
    _Result = GetDietaryTagsHandler(SqlAlchemyRepository()).handle()
    return ok(_Result)


# ───── Create ────────────────────────────────────────────────────────────

class CreateDietaryTagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=255)


@dataclass(slots=True)
class CreateDietaryTagResponse:
    dietary_tag_id: UUID | None = None
    duplicate: bool = False


class CreateDietaryTagHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: CreateDietaryTagRequest) -> CreateDietaryTagResponse:
        existing = self.repository.get(DietaryTag).all()
        normalised = request.name.strip().lower()
        if any(t.name.strip().lower() == normalised for t in existing):
            return CreateDietaryTagResponse(duplicate=True)
        next_seq = max((t.sequence for t in existing), default=-1) + 1
        tag = DietaryTag(
            name=request.name.strip(),
            category=request.category.strip(),
            sequence=next_seq,
        )
        self.repository.add(tag)
        self.repository.save_changes()
        return CreateDietaryTagResponse(dietary_tag_id=tag.id)


@DIETARY_TAG_ROUTER.route("", methods=["POST"])
@has_request_body(CreateDietaryTagRequest)
def create_dietary_tag():
    _Request: CreateDietaryTagRequest = get_request_body()
    _Response = CreateDietaryTagHandler(SqlAlchemyRepository()).handle(_Request)
    if _Response.duplicate:
        return business_rule_violation(f"A dietary tag named '{_Request.name}' already exists.")
    _LOGGER.info(f"Created dietary tag {_Response.dietary_tag_id} '{_Request.name}'")
    return created(
        _Response.dietary_tag_id,
        f"{DIETARY_TAG_ROUTER.name}.{get_dietary_tags.__name__}",
        "dietary_tag_id",
        body={"dietary_tag_id": _Response.dietary_tag_id},
    )


# ───── Update (rename / recategorise) ──────────────────────────────────────

class UpdateDietaryTagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, min_length=1, max_length=255)


@dataclass(slots=True)
class UpdateDietaryTagResponse:
    not_found: bool = False
    duplicate: bool = False


class UpdateDietaryTagHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: UpdateDietaryTagRequest, dietary_tag_id: UUID) -> UpdateDietaryTagResponse:
        tag: DietaryTag | None = self.repository.get(DietaryTag).by_id(dietary_tag_id)
        if tag is None:
            return UpdateDietaryTagResponse(not_found=True)
        if request.name is not None:
            target = request.name.strip()
            normalised = target.lower()
            for t in self.repository.get(DietaryTag).all():
                if t.id != dietary_tag_id and t.name.strip().lower() == normalised:
                    return UpdateDietaryTagResponse(duplicate=True)
            tag.name = target
        if request.category is not None:
            tag.category = request.category.strip()
        self.repository.save_changes()
        return UpdateDietaryTagResponse()


@DIETARY_TAG_ROUTER.route("/<uuid:dietary_tag_id>", methods=["PATCH"])
@has_request_body(UpdateDietaryTagRequest)
def update_dietary_tag(dietary_tag_id: UUID):
    _Request: UpdateDietaryTagRequest = get_request_body()
    _Response = UpdateDietaryTagHandler(SqlAlchemyRepository()).handle(_Request, dietary_tag_id)
    if _Response.not_found:
        return not_found("DietaryTag", dietary_tag_id)
    if _Response.duplicate:
        return business_rule_violation(f"A dietary tag named '{_Request.name}' already exists.")
    return ok({"dietary_tag_id": dietary_tag_id})


# ───── Delete ────────────────────────────────────────────────────────────

@dataclass(slots=True)
class DeleteDietaryTagResponse:
    not_found: bool = False
    recipes_affected: int = 0


class DeleteDietaryTagHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, dietary_tag_id: UUID) -> DeleteDietaryTagResponse:
        tag: DietaryTag | None = self.repository.get(DietaryTag).by_id(dietary_tag_id)
        if tag is None:
            return DeleteDietaryTagResponse(not_found=True)
        # `_recipe_counts()` is keyed by UUID, but `dietary_tag_id` arrives as
        # the raw str path param — a bare `.get(str, 0)` always missed, so
        # recipes_affected was always 0 (FU-528 str/UUID family).
        affected = _recipe_counts().get(UUID(str(dietary_tag_id)), 0)
        # RecipeTag links cascade away via the FK's ON DELETE CASCADE.
        self.repository.remove(tag)
        self.repository.save_changes()
        return DeleteDietaryTagResponse(recipes_affected=affected)


@DIETARY_TAG_ROUTER.route("/<uuid:dietary_tag_id>", methods=["DELETE"])
def delete_dietary_tag(dietary_tag_id: UUID):
    _Response = DeleteDietaryTagHandler(SqlAlchemyRepository()).handle(dietary_tag_id)
    if _Response.not_found:
        return not_found("DietaryTag", dietary_tag_id)
    _LOGGER.info(f"Deleted dietary tag {dietary_tag_id}; {_Response.recipes_affected} link(s) removed")
    return ok({"recipes_affected": _Response.recipes_affected})
