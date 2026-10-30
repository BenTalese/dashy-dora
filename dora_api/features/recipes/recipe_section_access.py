"""C-4 Chunk 10 — read/write helpers for recipe sections.

A recipe owns 0..N `RecipeSection` rows (DEC-3 option A — named groups,
not sub-recipes). Sections aren't required: a recipe with zero sections
renders the same as it always did, with all ingredients/steps in the
implicit "main" group.

`replace_sections_for_recipe` is the single write path — wipes existing
sections and re-inserts from the request shape. Replace semantics match
how ingredients + steps are handled on the same endpoint. Because the FK
on RecipeIngredient.section_id / RecipeStep.section_id is ON DELETE SET
NULL, deleting a section keeps its rows (just unsectioned) — the
ingredients/steps replace path is the only thing that re-pins them.
"""
from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select

from dora_api.app import db


@dataclass(slots=True)
class SectionWrite:
    """Wire shape for a single section on create/update. `client_id` is
    an arbitrary key the client uses to point its ingredients + steps at
    this section before the server has assigned a real UUID. The helper
    returns a client_id → real id map so the caller can rewrite the
    ingredient/step payloads."""
    client_id: object
    sequence: int
    name: str


def _section_table():
    return db.metadata.tables["RecipeSection"]


def _ingredient_table():
    return db.metadata.tables["RecipeIngredient"]


def _step_table():
    return db.metadata.tables["RecipeStep"]


def get_sections_for_recipe(recipe_id: UUID) -> list[dict]:
    """Return the recipe's sections as flat dicts ordered by `sequence`.

    Shape: `{id, sequence, name}`. Empty list when the recipe has none —
    the caller treats that as "everything in the implicit main group".
    """
    table = _section_table()
    rows = db.session.execute(
        select(table.c.id, table.c.sequence, table.c.name)
        .where(table.c.recipe_id == recipe_id)
        .order_by(table.c.sequence)
    ).all()
    return [
        {"id": row[0], "sequence": row[1], "name": row[2]}
        for row in rows
    ]


def get_section_count_for_recipes(recipe_ids: list[UUID]) -> dict[UUID, int]:
    """Bulk count per recipe — used by the list endpoint to surface the
    section-count badge on the card without loading every row."""
    if not recipe_ids:
        return {}
    table = _section_table()
    rows = db.session.execute(
        select(table.c.recipe_id).where(table.c.recipe_id.in_(recipe_ids))
    ).all()
    counts: dict[UUID, int] = defaultdict(int)
    for (rid,) in rows:
        counts[rid] += 1
    return dict(counts)


def replace_sections_for_recipe(
    recipe_id: UUID, sections: list[SectionWrite]
) -> dict[object, UUID]:
    """Wipe and re-insert the recipe's sections. Returns a
    `client_id → real UUID` map so the caller can rewrite section
    references inside the ingredient/step payloads before they're
    written. An empty list clears all sections (all rows fall back to
    the implicit main group; FK is ON DELETE SET NULL)."""
    if any(not (s.name or "").strip() for s in sections):
        raise ValueError("Every section must have a non-empty name.")
    if len({s.client_id for s in sections}) != len(sections):
        # Two sections sharing a client_id would collapse onto one row id.
        raise ValueError("Every section must have a distinct client_id.")

    table = _section_table()
    db.session.execute(table.delete().where(table.c.recipe_id == recipe_id))

    if not sections:
        return {}

    client_to_id: dict[object, UUID] = {s.client_id: uuid4() for s in sections}
    db.session.execute(
        table.insert(),
        [
            {
                "id": client_to_id[s.client_id],
                "recipe_id": recipe_id,
                "sequence": s.sequence,
                "name": s.name.strip(),
            }
            for s in sections
        ],
    )
    return client_to_id
