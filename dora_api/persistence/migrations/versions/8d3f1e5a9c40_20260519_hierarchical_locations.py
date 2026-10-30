"""20260519_hierarchical_locations

Replaces the flat StockLocation table with a self-referencing hierarchy
(zone -> area -> section) and adds the columns the heatmap/attention score
needs on StockItem (`expiry_date`, `is_flagged`).

Pre-release schema, so the migration drops existing StockLocation rows
(after nulling the StockItem FK to avoid a constraint failure). Anyone
running an older snapshot will lose their stock_location names; that's
acceptable per the project owner.

Revision ID: 8d3f1e5a9c40
Revises: 7c2e4a9b0d3f
Create Date: 2026-05-19 00:00:00.000000

"""
import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op

# revision identifiers, used by Alembic.
revision = '8d3f1e5a9c40'
down_revision = '7c2e4a9b0d3f'
branch_labels = None
depends_on = None


def upgrade():
    # Detach existing stock items so we can drop the old flat table without
    # tripping the FK.
    # Quoted: Postgres folds an unquoted identifier to lower case (`stockitem`).
    op.execute('UPDATE "StockItem" SET stock_location_id = NULL')

    with op.batch_alter_table('StockItem') as batch:
        batch.add_column(sa.Column('expiry_date', sa.Date(), nullable=True))
        batch.add_column(sa.Column(
            'is_flagged', sa.Boolean(), nullable=False, server_default=sa.false()
        ))

    op.drop_table('StockLocation')

    op.create_table(
        'StockLocation',
        sa.Column('id', sqlalchemy_utils.types.uuid.UUIDType(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False, server_default='zone'),
        sa.Column('parent_id', sqlalchemy_utils.types.uuid.UUIDType(), nullable=True),
        sa.Column('sequence', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['parent_id'], ['StockLocation.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    # Quoted: Postgres folds an unquoted identifier to lower case (`stockitem`).
    op.execute('UPDATE "StockItem" SET stock_location_id = NULL')
    op.drop_table('StockLocation')
    op.create_table(
        'StockLocation',
        sa.Column('id', sqlalchemy_utils.types.uuid.UUIDType(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('StockItem') as batch:
        batch.drop_column('is_flagged')
        batch.drop_column('expiry_date')
