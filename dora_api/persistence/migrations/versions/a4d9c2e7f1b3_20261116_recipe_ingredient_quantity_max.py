"""20261116_recipe_ingredient_quantity_max

An ingredient can carry a range ("1 to 2 carrots"). ``RecipeIngredient``
gains ``quantity_max``, the high end; ``quantity`` stays the low end and the
number every calculation reads. NULL (every existing row) is a single amount.

Revision ID: a4d9c2e7f1b3
Revises: e8b3f1a6c2d5
Create Date: 2026-11-16 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op


revision = 'a4d9c2e7f1b3'
down_revision = 'e8b3f1a6c2d5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('RecipeIngredient') as batch:
        batch.add_column(sa.Column('quantity_max', sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('RecipeIngredient') as batch:
        batch.drop_column('quantity_max')
