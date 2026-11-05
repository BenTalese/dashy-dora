"""20261106_price_alert_threshold_price

`PriceAlert.threshold_unit_price` → `threshold_price` (FU-917 / FU-911). The
watch is compared with the product's shelf `price_now`, a pack price, so the
"unit" in the name said something the value isn't. A rename; values kept.

Revision ID: b5e8c2a7d3f9
Revises: a4d9e2b7c5f1
Create Date: 2026-11-06 00:00:00.000000
"""
from alembic import op


revision = 'b5e8c2a7d3f9'
down_revision = 'a4d9e2b7c5f1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('PriceAlert') as batch:
        batch.alter_column('threshold_unit_price', new_column_name='threshold_price')


def downgrade():
    with op.batch_alter_table('PriceAlert') as batch:
        batch.alter_column('threshold_price', new_column_name='threshold_unit_price')
