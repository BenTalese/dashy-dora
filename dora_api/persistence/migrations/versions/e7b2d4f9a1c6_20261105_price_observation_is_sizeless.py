"""20261105_price_observation_is_sizeless

`StockItemPriceObservation.is_sizeless` (FU-983): a finished line with no
sized product folds to one `ea` per item, and a count-sized line ("12 ea") lands
in `ea` too, so "Your prices" read a $6 carton as $6 an egg beside $0.50 an egg.
The flag keeps the two apart.

Existing rows: a harvested `ea` row whose line had no product, or a product
with no size, is sizeless. Hand-logged rows state their own measure.

Revision ID: e7b2d4f9a1c6
Revises: d5a9c3e7f2b1
Create Date: 2026-11-05 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'e7b2d4f9a1c6'
down_revision = 'd5a9c3e7f2b1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('StockItemPriceObservation') as batch:
        batch.add_column(sa.Column(
            'is_sizeless', sa.Boolean(), nullable=False, server_default=sa.false(),
        ))
    op.execute(sa.text(
        'UPDATE "StockItemPriceObservation" SET is_sizeless = :yes '
        "WHERE unit = 'ea' AND shopping_list_line_id IN ("
        '  SELECT l.id FROM "ShoppingListLine" l'
        '  LEFT JOIN "Product" p ON p.id = l.selected_product_id'
        '  WHERE p.id IS NULL OR p.size_value IS NULL OR p.size_value <= 0'
        '     OR p.size_unit IS NULL'
        ')'
    ).bindparams(yes=True))


def downgrade():
    with op.batch_alter_table('StockItemPriceObservation') as batch:
        batch.drop_column('is_sizeless')
