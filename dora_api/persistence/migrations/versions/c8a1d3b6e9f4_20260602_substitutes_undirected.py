"""20260602_substitutes_undirected

Refactor StockItemSubstitute from a directed self-referential m2m
(stock_item_id → substitute_id) into an undirected pair with notes.

New columns: stock_item_a_id, stock_item_b_id, notes, created_at.
Canonical ordering enforced via CHECK (a < b) so each pair has exactly
one row regardless of which item you "started from".

Pre-release destructive migration — existing rows are dropped, not
migrated. Dev DB gets re-seeded by `seed_dev_data`; any real data should
be re-entered through the new /substitutes UI (N7).

Revision ID: c8a1d3b6e9f4
Revises: c6e9f4a82d15
Create Date: 2026-06-02 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy_utils import UUIDType

revision = 'c8a1d3b6e9f4'
down_revision = 'c6e9f4a82d15'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('StockItemSubstitute')
    op.create_table(
        'StockItemSubstitute',
        # UUIDType to match `StockItem.id`: Postgres refuses a VARCHAR FK onto
        # a uuid column. Installs that ran the earlier VARCHAR(36) form are
        # converted by e7a2c5f9b3d1.
        sa.Column('stock_item_a_id', UUIDType(), nullable=False),
        sa.Column('stock_item_b_id', UUIDType(), nullable=False),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['stock_item_a_id'], ['StockItem.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['stock_item_b_id'], ['StockItem.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('stock_item_a_id', 'stock_item_b_id'),
        sa.CheckConstraint('stock_item_a_id < stock_item_b_id', name='ck_substitute_canonical'),
    )


def downgrade():
    op.drop_table('StockItemSubstitute')
    op.create_table(
        'StockItemSubstitute',
        sa.Column('stock_item_id', UUIDType(), nullable=False),
        sa.Column('substitute_id', UUIDType(), nullable=False),
        sa.ForeignKeyConstraint(['stock_item_id'], ['StockItem.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['substitute_id'], ['StockItem.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('stock_item_id', 'substitute_id'),
    )
