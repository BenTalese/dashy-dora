"""How recipes are committed to meal plans: future un-cooked servings and
how often each recipe appears on any plan. Read by the cookbook's pool and
"frequently planned" hydrations; meal-plan commitment math belongs here, with
the meal plans (finalisation 01-R39).

R-005 carve-out: grouped aggregates over `MealPlanEntry`, which the generic
repository has no port for. `select()` against the mapped table (not raw
`text()`) so SQLAlchemy applies the UUIDType bind processor on SQLite and
Postgres alike (FU-081).
"""
from datetime import date
from uuid import UUID

from sqlalchemy import func, select

from dora_api.app import db
from dora_api.persistence.uuid_key import uuid_key


def committed_servings_by_recipe(recipe_ids: list[UUID], today: date) -> dict[str, int]:
    """`{recipe_id: servings}` still to be cooked on or after `today`."""
    if not recipe_ids:
        return {}
    entry = db.metadata.tables["MealPlanEntry"]
    rows = db.session.execute(
        select(entry.c.recipe_id, func.sum(entry.c.servings))
        .where(entry.c.consumed_at.is_(None))
        .where(entry.c.scheduled_for >= today)
        .where(entry.c.recipe_id.in_(recipe_ids))
        .group_by(entry.c.recipe_id)
    ).all()
    return {uuid_key(row[0]): int(row[1] or 0) for row in rows}


def plan_counts_by_recipe(recipe_ids: list[UUID]) -> dict[str, int]:
    """`{recipe_id: entries}` across every meal plan, all time."""
    if not recipe_ids:
        return {}
    entry = db.metadata.tables["MealPlanEntry"]
    rows = db.session.execute(
        select(entry.c.recipe_id, func.count())
        .where(entry.c.recipe_id.in_(recipe_ids))
        .group_by(entry.c.recipe_id)
    ).all()
    return {uuid_key(row[0]): int(row[1] or 0) for row in rows}


def recipe_ids_scheduled_between(start: date, end: date) -> list[UUID]:
    """Distinct recipe ids with an entry scheduled in `[start, end]`. Read as an
    id projection *before* the entries are loaded: a recipe the entry query has
    already put in the identity map comes back without its ingredients when
    loaded again with them (R-032), so cookability must load first
    (finalisation 08-R16)."""
    entry = db.metadata.tables["MealPlanEntry"]
    rows = db.session.execute(
        select(entry.c.recipe_id)
        .where(entry.c.scheduled_for >= start)
        .where(entry.c.scheduled_for <= end)
        .distinct()
    ).all()
    return [row[0] for row in rows]
