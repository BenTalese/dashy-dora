"""20260625_recipe_steps_mode

Recipe image-mode steps — add `Recipe.steps_mode` (explicit enum replacing
today's implicit "has step rows?" detection) and a new `RecipeStepImage`
child table for ordered photo-mode step content.

Backfill: existing recipes get `steps_mode = 'structured'` if they own at
least one RecipeStep row, else `'freeform'`. New recipes default to
`'freeform'`.

Pre-release: no idempotent guards.

Revision ID: d3a8f1c5e2b9
Revises: c2d4a9f7b1e8
Create Date: 2026-06-25 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy_utils import UUIDType


revision = 'd3a8f1c5e2b9'
down_revision = 'c2d4a9f7b1e8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('Recipe') as batch_op:
        batch_op.add_column(sa.Column(
            'steps_mode',
            sa.String(length=16),
            nullable=False,
            server_default='freeform',
        ))

    # Quoted: Postgres folds unquoted identifiers to lower case.
    op.execute(
        "UPDATE \"Recipe\" SET steps_mode = 'structured' "
        'WHERE id IN (SELECT DISTINCT recipe_id FROM "RecipeStep")'
    )

    op.create_table(
        'RecipeStepImage',
        sa.Column('id', UUIDType, primary_key=True),
        sa.Column(
            'recipe_id', UUIDType,
            sa.ForeignKey('Recipe.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('sequence', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('image', sa.LargeBinary(), nullable=False),
    )
    op.create_index(
        'ix_recipe_step_image_recipe_id',
        'RecipeStepImage', ['recipe_id'],
    )


def downgrade():
    op.drop_index('ix_recipe_step_image_recipe_id', table_name='RecipeStepImage')
    op.drop_table('RecipeStepImage')
    with op.batch_alter_table('Recipe') as batch_op:
        batch_op.drop_column('steps_mode')
