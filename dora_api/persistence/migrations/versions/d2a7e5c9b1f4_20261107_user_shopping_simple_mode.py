"""20261107_user_shopping_simple_mode

Per-user shopping page mode. Adds ``User.shopping_simple_mode`` (Boolean,
NOT NULL, server_default FALSE): False is flow mode (plan, shop, finish),
True is simple mode, one endless list where a tick means bought.

Revision ID: d2a7e5c9b1f4
Revises: c6f9d3b8e4a1
Create Date: 2026-11-07 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op


revision = 'd2a7e5c9b1f4'
down_revision = 'c6f9d3b8e4a1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('User') as batch:
        batch.add_column(sa.Column(
            'shopping_simple_mode', sa.Boolean(),
            nullable=False, server_default=sa.false(),
        ))


def downgrade():
    with op.batch_alter_table('User') as batch:
        batch.drop_column('shopping_simple_mode')
