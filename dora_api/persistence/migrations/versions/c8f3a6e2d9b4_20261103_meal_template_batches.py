"""20261103_meal_template_batches

A meal-plan template remembers which meals were one batch cook and which were
cooked fresh (owner, FU-939). Applying it mints a batch per `cook_key` group,
the token a meal-plan write already uses.

Revision ID: c8f3a6e2d9b4
Revises: b6e1d9c4a2f7
Create Date: 2026-11-03 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'c8f3a6e2d9b4'
down_revision = 'b6e1d9c4a2f7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('MealPlanTemplateEntry') as batch:
        batch.add_column(sa.Column('cook_key', sa.String(64), nullable=True))
        batch.add_column(sa.Column(
            'cook_fresh', sa.Boolean(), nullable=False, server_default=sa.false(),
        ))


def downgrade():
    with op.batch_alter_table('MealPlanTemplateEntry') as batch:
        batch.drop_column('cook_fresh')
        batch.drop_column('cook_key')
