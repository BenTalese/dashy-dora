"""20261105_user_reports_layout

`User.reports_layout` (FU-832): the Reports page gets the dashboard's card
order + hidden set, stored as its own opaque JSON string beside
`dashboard_layout` so the two layouts can't collide.

Revision ID: f3c8a1e6b4d2
Revises: e7b2d4f9a1c6
Create Date: 2026-11-05 00:00:01.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'f3c8a1e6b4d2'
down_revision = 'e7b2d4f9a1c6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('User') as batch:
        batch.add_column(sa.Column('reports_layout', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('User') as batch:
        batch.drop_column('reports_layout')
