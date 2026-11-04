"""20261103_template_line_product_anchor

A shopping-list template line can be anchored by a product instead of a stock
item, the same rule a list line follows (owner, FU-940 D1). "Save as template"
used to skip product-only lines.

`stock_item_id` becomes nullable, `product_id` (CASCADE, like the stock-item
anchor) is added, and a CHECK requires one of the two.

Revision ID: b6e1d9c4a2f7
Revises: a8d3e6f1b2c9
Create Date: 2026-11-03 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils


revision = 'b6e1d9c4a2f7'
down_revision = 'a8d3e6f1b2c9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ShoppingListTemplateLine') as batch:
        batch.alter_column(
            'stock_item_id', existing_type=sqlalchemy_utils.types.uuid.UUIDType(), nullable=True,
        )
        batch.add_column(sa.Column(
            'product_id', sqlalchemy_utils.types.uuid.UUIDType(), nullable=True,
        ))
        batch.create_foreign_key(
            op.f('fk_ShoppingListTemplateLine_product_id_Product'),
            'Product', ['product_id'], ['id'], ondelete='CASCADE',
        )
        batch.create_index(op.f('ix_ShoppingListTemplateLine_product_id'), ['product_id'])
        batch.create_check_constraint(
            op.f('ck_ShoppingListTemplateLine_template_line_anchor'),
            'stock_item_id IS NOT NULL OR product_id IS NOT NULL',
        )


def downgrade():
    op.execute('DELETE FROM "ShoppingListTemplateLine" WHERE stock_item_id IS NULL')
    with op.batch_alter_table('ShoppingListTemplateLine') as batch:
        batch.drop_constraint(
            op.f('ck_ShoppingListTemplateLine_template_line_anchor'), type_='check',
        )
        batch.drop_index(op.f('ix_ShoppingListTemplateLine_product_id'))
        batch.drop_constraint(
            op.f('fk_ShoppingListTemplateLine_product_id_Product'), type_='foreignkey',
        )
        batch.drop_column('product_id')
        batch.alter_column(
            'stock_item_id', existing_type=sqlalchemy_utils.types.uuid.UUIDType(), nullable=False,
        )
