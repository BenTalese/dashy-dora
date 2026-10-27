"""The recipe vocabulary managers (categories, cuisines, tools) share one
shape: list with recipe counts, create with dedupe + next sequence, rename
with dedupe, delete reporting how many recipes it touched (finalisation
01-R5). Each feature module keeps its own DTO and explicit routes and calls
this handler; only how recipes are counted differs (a recipe FK, or a link
table).
"""
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from dora_api.app import db
from dora_api.domain.entities.recipe import Recipe
from dora_api.infrastructure.ports import Repository

T = TypeVar("T")
RecipeCounter = Callable[[Repository], dict[UUID, int]]


class VocabularyNameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)


@dataclass(slots=True)
class VocabularyCreated:
    entry_id: UUID | None = None
    duplicate: bool = False


@dataclass(slots=True)
class VocabularyRenamed:
    not_found: bool = False
    duplicate: bool = False


@dataclass(slots=True)
class VocabularyDeleted:
    not_found: bool = False
    recipes_affected: int = 0


def counts_by_recipe_fk(field: str) -> RecipeCounter:
    """Recipes per entry through a Recipe FK relationship (category, cuisine).
    The relationship is noload, so it is included explicitly."""
    def count(repository: Repository) -> dict[UUID, int]:
        counts: dict[UUID, int] = {}
        for recipe in repository.get(Recipe).include(field).all():
            entry = getattr(recipe, field)
            if entry is not None:
                counts[entry.id] = counts.get(entry.id, 0) + 1
        return counts
    return count


def counts_by_link_table(table_name: str, fk_column: str) -> RecipeCounter:
    """Recipes per entry through a recipe link table (RecipeTool). R-005
    carve-out: a grouped count over an association with no entity."""
    def count(_repository: Repository) -> dict[UUID, int]:
        table = db.metadata.tables[table_name]
        rows = db.session.execute(
            select(table.c[fk_column], func.count(table.c.recipe_id)).group_by(table.c[fk_column])
        ).all()
        return {row[0]: int(row[1] or 0) for row in rows}
    return count


class VocabularyHandler(Generic[T]):
    """`entity_cls` has `id`, `name` and `sequence`; names are unique by a
    trimmed, case-insensitive match."""

    def __init__(self, repository: Repository, entity_cls: type[T], count_recipes: RecipeCounter) -> None:
        self.repository = repository
        self.entity_cls = entity_cls
        self.count_recipes = count_recipes

    def list(self) -> list[tuple[T, int]]:
        """Every entry with its recipe count, by sequence then name."""
        counts = self.count_recipes(self.repository)
        entries = sorted(self.repository.get(self.entity_cls).all(), key=lambda e: (e.sequence, e.name.lower()))
        return [(e, counts.get(e.id, 0)) for e in entries]

    def _clash(self, name: str, except_id: UUID | None = None) -> bool:
        normalised = name.strip().lower()
        return any(
            e.id != except_id and e.name.strip().lower() == normalised
            for e in self.repository.get(self.entity_cls).all()
        )

    def create(self, name: str) -> VocabularyCreated:
        if self._clash(name):
            return VocabularyCreated(duplicate=True)
        existing = self.repository.get(self.entity_cls).all()
        next_sequence = max((e.sequence for e in existing), default=-1) + 1
        entry = self.entity_cls(name=name.strip(), sequence=next_sequence)
        self.repository.add(entry)
        self.repository.save_changes()
        return VocabularyCreated(entry_id=entry.id)

    def rename(self, entry_id: UUID, name: str) -> VocabularyRenamed:
        entry = self.repository.get(self.entity_cls).by_id(entry_id)
        if entry is None:
            return VocabularyRenamed(not_found=True)
        if self._clash(name, except_id=entry_id):
            return VocabularyRenamed(duplicate=True)
        entry.name = name.strip()
        self.repository.save_changes()
        return VocabularyRenamed()

    def delete(self, entry_id: UUID) -> VocabularyDeleted:
        """The recipes' reference is cleared by the FK (ON DELETE SET NULL) or
        the link rows cascade away; the count is taken first for the UI."""
        entry = self.repository.get(self.entity_cls).by_id(entry_id)
        if entry is None:
            return VocabularyDeleted(not_found=True)
        affected = self.count_recipes(self.repository).get(entry_id, 0)
        self.repository.remove(entry)
        self.repository.save_changes()
        return VocabularyDeleted(recipes_affected=affected)
