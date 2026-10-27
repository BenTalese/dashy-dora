"""20261024_drop_price_alert_last_fired_at

`PriceAlert.last_fired_at` was meant for a worker that never existed; nothing
writes it, and the `price_drop` alert's episode key does the "fire once" job
(FU-917).

Revision ID: b8d2f4a6c1e3
Revises: f2a6c8e1b4d7
Create Date: 2026-10-24 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'b8d2f4a6c1e3'
down_revision = 'f2a6c8e1b4d7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('PriceAlert') as batch:
        batch.drop_column('last_fired_at')


def downgrade():
    with op.batch_alter_table('PriceAlert') as batch:
        batch.add_column(sa.Column('last_fired_at', sa.DateTime(timezone=True), nullable=True))
