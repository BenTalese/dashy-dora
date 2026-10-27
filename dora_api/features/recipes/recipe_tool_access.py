"""C-4 Chunk 5 — the `RecipeTool` link (recipe ↔ user-configurable `Tool`),
through the shared `RecipeLinkAccess` (`_recipe_link_access`), plus the
step-derived tool set. The module-level names are the ones the handlers
import."""
from uuid import UUID

from sqlalchemy import select

from dora_api.app import db
from dora_api.features.recipes._recipe_link_access import RecipeLinkAccess

TOOLS = RecipeLinkAccess(
    "RecipeTool", "Tool", "tool_id",
    "'{raw}' is not a recognised tool. See /api/tools for the list.",
)

validate_tool_ids = TOOLS.validate_ids
resolve_tool_filter_values = TOOLS.resolve_filter_values
get_tool_ids_for_recipe = TOOLS.ids_for_recipe
get_tool_ids_for_recipes = TOOLS.ids_for_recipes
set_tool_ids_for_recipe = TOOLS.set_ids_for_recipe
find_recipe_ids_with_all_tools = TOOLS.recipe_ids_with_all
find_recipe_ids_with_any_tools = TOOLS.recipe_ids_with_any


def _step_table():
    return db.metadata.tables["RecipeStep"]


def _step_tool_table():
    return db.metadata.tables["RecipeStepTool"]


def get_tool_ids_from_steps(recipe_id: UUID) -> list[UUID]:
    """The union of the tools every structured step of ``recipe_id`` declares,
    in first-appearance order (steps ordered by parent-then-sequence)."""
    steps = _step_table()
    step_tools = _step_tool_table()
    rows = db.session.execute(
        select(step_tools.c.tool_id)
        .select_from(steps.join(step_tools, step_tools.c.step_id == steps.c.id))
        .where(steps.c.recipe_id == recipe_id)
        .order_by(steps.c.parent_step_id, steps.c.sequence)
    ).all()
    seen: set[UUID] = set()
    out: list[UUID] = []
    for (tool_id,) in rows:
        if tool_id in seen:
            continue
        seen.add(tool_id)
        out.append(tool_id)
    return out


def sync_recipe_tools_from_steps(recipe_id: UUID) -> list[UUID]:
    """Recipe-view feedback 2026-08-27 — in ``structured`` mode a recipe's
    tools are *derived*, not typed: the recipe-level set is the union of what
    its steps say they use.

    The recipe-level `RecipeTool` rows still exist because that is what the
    cookbook's tool filter reads (`find_recipe_ids_with_any_tools`), and
    re-deriving it per query would push step-shaped domain math into the list
    endpoint. So the union is computed once, here, on every write that can
    change it, and the page shows it read-only.

    Freeform/image recipes have no steps to derive from and keep their own
    editable set — callers only reach this in structured mode. Returns the
    ids written, for the caller's DTO.
    """
    derived = get_tool_ids_from_steps(recipe_id)
    set_tool_ids_for_recipe(recipe_id, derived)
    return derived
