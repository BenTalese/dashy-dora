"""C-4 Chunk 6 — read/write helpers for structured recipe steps.

A recipe owns 0..N `RecipeStep` rows. Each row is either top-level
(`parent_step_id IS NULL`) or a sub-step (one level only — depth > 1 is
rejected). Within a parent, `sequence` is the display order. Two link
tables (`RecipeStepIngredient`, `RecipeStepTool`) attach each step to the
recipe's own ingredients and to tools from the Chunk 5 vocabulary.

DTOs are surfaced as a flat list ordered by (parent_step_id NULLS FIRST,
sequence) — the frontend reassembles the tree from `parent_step_id`.

`replace_steps_for_recipe` is the single write path: a full nested write
that wipes existing steps + links and re-creates them from the request
shape. Replace semantics (not diff) matches how `ingredients` is handled
on the same endpoint.
"""
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable
from uuid import UUID, uuid4

from sqlalchemy import select

from dora_api.app import db


@dataclass(slots=True)
class StepWrite:
    """Wire shape for a single step on create/update. `client_id` is an
    arbitrary key (any hashable value) the client uses to point sub-steps
    at their parent before the server has assigned ids; the helper resolves
    it to a real UUID on insert."""
    client_id: object
    parent_client_id: object | None
    sequence: int
    text: str
    hint: str | None
    ingredient_ids: list[UUID]
    tool_ids: list[UUID]
    # optional section grouping (resolved by the caller
    # from the matching section's client_id before this write). NULL
    # keeps the step in the implicit "main" group.
    section_id: UUID | None = None
    # Owner feedback 2026-09-01 — explicit per-step timer in minutes. None
    # leaves cook mode to sniff the step text as it always did.
    timer_minutes: int | None = None


def _step_table():
    return db.metadata.tables["RecipeStep"]


def _step_ingredient_table():
    return db.metadata.tables["RecipeStepIngredient"]


def _step_tool_table():
    return db.metadata.tables["RecipeStepTool"]


def _recipe_ingredient_table():
    return db.metadata.tables["RecipeIngredient"]


def _tool_table():
    return db.metadata.tables["Tool"]


def has_structured_steps(recipe_id: UUID) -> bool:
    """Cheap existence check for the list DTO `has_structured_steps` flag."""
    table = _step_table()
    row = db.session.execute(
        select(table.c.id).where(table.c.recipe_id == recipe_id).limit(1)
    ).first()
    return row is not None


def has_structured_steps_for_recipes(recipe_ids: Iterable[UUID]) -> set[UUID]:
    """Bulk variant — returns the subset of input ids that own >= 1 step."""
    ids = list(recipe_ids)
    if not ids:
        return set()
    table = _step_table()
    rows = db.session.execute(
        select(table.c.recipe_id.distinct()).where(table.c.recipe_id.in_(ids))
    ).all()
    return {row[0] for row in rows}


def get_steps_for_recipe(recipe_id: UUID) -> list[dict]:
    """Return the recipe's steps as flat dicts, ordered by
    (parent NULLS FIRST, sequence). Each dict carries `ingredient_ids` +
    `tool_ids` populated from the link tables in two batch queries.

    Shape matches the DTO: id, parent_step_id, sequence, text, hint,
    timer_minutes, ingredient_ids, tool_ids. The frontend rebuilds the tree.
    """
    steps_tbl = _step_table()
    rows = db.session.execute(
        select(
            steps_tbl.c.id,
            steps_tbl.c.parent_step_id,
            steps_tbl.c.sequence,
            steps_tbl.c.text,
            steps_tbl.c.hint,
            steps_tbl.c.section_id,
            steps_tbl.c.timer_minutes,
        )
        .where(steps_tbl.c.recipe_id == recipe_id)
        # ORDER BY parent IS NULL DESC puts NULLs first portably (SQLite +
        # Postgres agree on bool ordering DESC=True-first).
        .order_by(steps_tbl.c.parent_step_id.is_(None).desc(), steps_tbl.c.sequence)
    ).all()
    if not rows:
        return []

    step_ids = [row[0] for row in rows]

    ingredients_tbl = _step_ingredient_table()
    ing_rows = db.session.execute(
        select(
            ingredients_tbl.c.step_id,
            ingredients_tbl.c.recipe_ingredient_id,
        ).where(ingredients_tbl.c.step_id.in_(step_ids))
    ).all()
    ing_map: dict[UUID, list[UUID]] = defaultdict(list)
    for step_id, ing_id in ing_rows:
        ing_map[step_id].append(ing_id)

    tools_tbl = _step_tool_table()
    tool_rows = db.session.execute(
        select(tools_tbl.c.step_id, tools_tbl.c.tool_id)
        .where(tools_tbl.c.step_id.in_(step_ids))
    ).all()
    tool_map: dict[UUID, list[UUID]] = defaultdict(list)
    for step_id, tool_id in tool_rows:
        tool_map[step_id].append(tool_id)

    return [
        {
            "id": row[0],
            "parent_step_id": row[1],
            "sequence": row[2],
            "text": row[3],
            "hint": row[4],
            "section_id": row[5],
            "timer_minutes": row[6],
            "ingredient_ids": ing_map.get(row[0], []),
            "tool_ids": tool_map.get(row[0], []),
        }
        for row in rows
    ]


def _validate_writes(steps: list[StepWrite]) -> None:
    """Reject obvious shape errors before any write hits the DB:
    - depth > 1 (sub-step whose parent is also a sub-step);
    - parent_client_id pointing at a non-existent client_id;
    - a client_id used twice (both would collapse onto one row id);
    - empty `text`.

    Raises ValueError on the first failure so the request layer can 400.
    """
    by_client: dict[object, StepWrite] = {s.client_id: s for s in steps}
    if len(by_client) != len(steps):
        raise ValueError("Every step must have a distinct client_id.")
    for step in steps:
        if not (step.text or "").strip():
            raise ValueError("Every step must have non-empty text.")
        if step.parent_client_id is None:
            continue
        parent = by_client.get(step.parent_client_id)
        if parent is None:
            raise ValueError(
                f"Step references a parent that isn't in the same write "
                f"(client_id={step.parent_client_id!r})."
            )
        if parent.parent_client_id is not None:
            raise ValueError(
                "Sub-steps cannot themselves have sub-steps "
                "(structured recipes support exactly one level of nesting)."
            )


def _validate_link_targets(
    recipe_id: UUID, steps: list[StepWrite]
) -> None:
    """Ingredient ids must belong to *this* recipe; tool ids must exist in
    the Tool vocab. Either failure raises ValueError."""
    wanted_ing: set[UUID] = set()
    wanted_tool: set[UUID] = set()
    for s in steps:
        wanted_ing.update(s.ingredient_ids)
        wanted_tool.update(s.tool_ids)

    if wanted_ing:
        ing_tbl = _recipe_ingredient_table()
        rows = db.session.execute(
            select(ing_tbl.c.id)
            .where(ing_tbl.c.recipe_id == recipe_id)
            .where(ing_tbl.c.id.in_(list(wanted_ing)))
        ).all()
        found = {row[0] for row in rows}
        missing = wanted_ing - found
        if missing:
            raise ValueError(
                f"Step references ingredients not on this recipe: "
                f"{sorted(str(m) for m in missing)}"
            )

    if wanted_tool:
        tool_tbl = _tool_table()
        rows = db.session.execute(
            select(tool_tbl.c.id).where(tool_tbl.c.id.in_(list(wanted_tool)))
        ).all()
        found = {row[0] for row in rows}
        missing = wanted_tool - found
        if missing:
            raise ValueError(
                f"Step references unknown tools: "
                f"{sorted(str(m) for m in missing)}"
            )


def replace_steps_for_recipe(
    recipe_id: UUID, steps: list[StepWrite]
) -> None:
    """Wipe existing steps + their links and re-insert from `steps`. Empty
    list clears all structure (recipe falls back to `instructions` text).

    Validates shape + link targets before any DB write so a bad payload
    surfaces as a 400 without partial damage. Caller catches ValueError.
    """
    _validate_writes(steps)
    _validate_link_targets(recipe_id, steps)

    steps_tbl = _step_table()
    # Delete cascades through both link tables via FK ondelete=CASCADE.
    db.session.execute(steps_tbl.delete().where(steps_tbl.c.recipe_id == recipe_id))

    if not steps:
        return

    # Resolve client-side ids -> server UUIDs in dependency order (parents
    # first, then children) so the parent_step_id FK is satisfied at insert.
    client_to_id: dict[object, UUID] = {s.client_id: uuid4() for s in steps}

    parent_rows: list[dict] = []
    child_rows: list[dict] = []
    for s in steps:
        row = {
            "id": client_to_id[s.client_id],
            "recipe_id": recipe_id,
            "parent_step_id": (
                client_to_id[s.parent_client_id]
                if s.parent_client_id is not None
                else None
            ),
            "sequence": s.sequence,
            "text": s.text.strip(),
            "hint": (s.hint or "").strip() or None,
            "section_id": s.section_id,
            "timer_minutes": s.timer_minutes,
        }
        if s.parent_client_id is None:
            parent_rows.append(row)
        else:
            child_rows.append(row)

    if parent_rows:
        db.session.execute(steps_tbl.insert(), parent_rows)
    if child_rows:
        db.session.execute(steps_tbl.insert(), child_rows)

    ing_tbl = _step_ingredient_table()
    tool_tbl = _step_tool_table()
    ing_inserts: list[dict] = []
    tool_inserts: list[dict] = []
    for s in steps:
        step_id = client_to_id[s.client_id]
        # dict.fromkeys de-duplicates in order: a repeated id is one link,
        # not a duplicate link row.
        for ing_id in dict.fromkeys(s.ingredient_ids):
            ing_inserts.append({"step_id": step_id, "recipe_ingredient_id": ing_id})
        for tool_id in dict.fromkeys(s.tool_ids):
            tool_inserts.append({"step_id": step_id, "tool_id": tool_id})
    if ing_inserts:
        db.session.execute(ing_tbl.insert(), ing_inserts)
    if tool_inserts:
        db.session.execute(tool_tbl.insert(), tool_inserts)
