"""20261105_line_usual_price_at_pick

`ShoppingListLine.usual_price_at_pick` (FU-831 / ADR-068): the household's own
usual price for one of the line's item, frozen when the list is finished. The
Reports savings figure moves from "under shelf price" to "less than you usually
pay" and is measured from this snapshot. No backfill: lists finished before
this have no snapshot and count as uncovered.

Revision ID: a4d9e2b7c5f1
Revises: f3c8a1e6b4d2
Create Date: 2026-11-05 00:00:02.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a4d9e2b7c5f1'
down_revision = 'f3c8a1e6b4d2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ShoppingListLine') as batch:
        batch.add_column(sa.Column('usual_price_at_pick', sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('ShoppingListLine') as batch:
        batch.drop_column('usual_price_at_pick')
