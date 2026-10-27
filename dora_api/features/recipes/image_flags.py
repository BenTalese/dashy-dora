"""Which recipes have a photo, without loading the deferred `image` bytes
(FU-090). Shared by the cookbook and the meal planner (finalisation 02-R6).

R-005 carve-out: a single-column projection the repository can't express
without loading the entity. ORM `select()` (not raw `text()`) so the UUID
type binds correctly on SQLite's BINARY(16) id column.
"""
from typing import Iterable
from uuid import UUID

from sqlalchemy import select

from dora_api.app import db
from dora_api.domain.entities.recipe import Recipe


def recipe_ids_with_image(recipe_ids: Iterable[UUID]) -> set[str]:
    """String ids (both callers key their DTOs by `str(id)`) of the recipes
    among `recipe_ids` that carry an image."""
    ids = list(recipe_ids)
    if not ids:
        return set()
    rows = db.session.execute(
        select(Recipe.id).where(Recipe.id.in_(ids), Recipe.image.is_not(None))
    ).all()
    return {str(row[0]) for row in rows}
