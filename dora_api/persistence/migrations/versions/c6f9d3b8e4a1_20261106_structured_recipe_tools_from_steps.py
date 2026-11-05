"""20261106_structured_recipe_tools_from_steps

FU-744: a structured recipe's tools are the union of its steps' tools,
re-derived on every save since 2026-08-27 (`sync_recipe_tools_from_steps`).
Recipes last saved before then kept the set typed by hand, so the cookbook's
tool filter could disagree with the steps. Re-derive them once, the same way.
Freeform and image recipes keep their own set.

Revision ID: c6f9d3b8e4a1
Revises: b5e8c2a7d3f9
Create Date: 2026-11-06 00:00:01.000000
"""
from alembic import op


revision = 'c6f9d3b8e4a1'
down_revision = 'b5e8c2a7d3f9'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        'DELETE FROM "RecipeTool" WHERE recipe_id IN '
        '(SELECT id FROM "Recipe" WHERE steps_mode = \'structured\')'
    )
    op.execute(
        'INSERT INTO "RecipeTool" (recipe_id, tool_id) '
        'SELECT DISTINCT s.recipe_id, st.tool_id '
        'FROM "RecipeStep" s '
        'JOIN "RecipeStepTool" st ON st.step_id = s.id '
        'JOIN "Recipe" r ON r.id = s.recipe_id '
        'WHERE r.steps_mode = \'structured\''
    )


def downgrade():
    # The hand-typed sets this replaced aren't recoverable, and the derived
    # ones are what the app writes on every save anyway.
    pass
