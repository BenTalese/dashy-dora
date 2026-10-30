"""20260814_nutrition_complex

Owner call 2026-08-14 — nutrition becomes install-wide, and `complex` mode
becomes real.

Two things at once, because they're the same decision:

1. **Install-wide.** `AppSetting.nutrition_enabled` (bool) + `User.nutrition_mode`
   (per-user off/simple/complex) collapse into one `AppSetting.nutrition_mode`.
   Two switches answering "is nutrition on?" was the money-settings shape the
   owner had already removed on 2026-08-12; nutrition kept it until now.
   Existing installs with `nutrition_enabled = 1` carry over to `simple` —
   the mode that matches what was actually usable before today.

2. **Complex is implemented, so its fake seam goes.** `nutrition_db_source`
   was a free-form string with no UI anywhere whose only job was to gate a
   mode with zero implementation. Complex-mode availability is now *derived*
   from what's installed (a downloaded dataset, a USDA API key, OFF reachable),
   so the string has nothing left to say. Replaced by real config:
   `nutrition_usda_api_key` and `nutrition_off_lookup_enabled`.

New tables `NutritionFood` (the catalogue, per-100g) and `NutritionPortion`
(household measure → gram weight, which is what makes recipe rollup possible),
plus `StockItem.nutrition_food_id` — the explicit, human-confirmed link.

**Pre-release hard change:** per-user nutrition modes are not preserved (there
is no sensible merge from N users to one household value; the install-wide
carry-over above is the honest substitute).

Revision ID: b9e3f1a7c4d2
Revises: a7f4d2c8e1b6
Create Date: 2026-08-14 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy_utils import UUIDType


revision = 'b9e3f1a7c4d2'
down_revision = 'a7f4d2c8e1b6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'NutritionFood',
        sa.Column('id', UUIDType, primary_key=True),
        sa.Column('source', sa.String(length=32), nullable=False),
        sa.Column('source_ref', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=512), nullable=False),
        sa.Column('brand', sa.String(length=255), nullable=True),
        sa.Column('barcode', sa.String(length=64), nullable=True),
        sa.Column('kcal_per_100g', sa.Float(), nullable=True),
        sa.Column('protein_g_per_100g', sa.Float(), nullable=True),
        sa.Column('carbs_g_per_100g', sa.Float(), nullable=True),
        sa.Column('fat_g_per_100g', sa.Float(), nullable=True),
        sa.Column('imported_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('source', 'source_ref', name='uq_nutrition_food_source_ref'),
    )
    op.create_index('ix_NutritionFood_source', 'NutritionFood', ['source'])
    op.create_index('ix_NutritionFood_name', 'NutritionFood', ['name'])
    op.create_index('ix_NutritionFood_barcode', 'NutritionFood', ['barcode'])

    op.create_table(
        'NutritionPortion',
        sa.Column('id', UUIDType, primary_key=True),
        sa.Column(
            'nutrition_food_id', UUIDType,
            sa.ForeignKey('NutritionFood.id', ondelete='CASCADE'), nullable=False,
        ),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('measure', sa.String(length=255), nullable=False),
        sa.Column('gram_weight', sa.Float(), nullable=False),
    )
    op.create_index(
        'ix_NutritionPortion_nutrition_food_id', 'NutritionPortion', ['nutrition_food_id'],
    )

    with op.batch_alter_table('StockItem') as batch_op:
        batch_op.add_column(sa.Column('nutrition_food_id', UUIDType, nullable=True))
        batch_op.create_foreign_key(
            'fk_stock_item_nutrition_food_id', 'NutritionFood',
            ['nutrition_food_id'], ['id'], ondelete='SET NULL',
        )

    with op.batch_alter_table('AppSetting') as batch_op:
        batch_op.add_column(sa.Column(
            'nutrition_mode', sa.String(length=10), nullable=False, server_default='off',
        ))
        batch_op.add_column(sa.Column(
            'nutrition_usda_api_key', sa.String(length=255), nullable=False, server_default='',
        ))
        batch_op.add_column(sa.Column(
            'nutrition_off_lookup_enabled', sa.Boolean(), nullable=False, server_default=sa.true(),
        ))

    # Carry the old install bool over before dropping it: an install that had
    # nutrition switched on keeps it on, at the depth that actually worked.
    # Bare boolean predicate: `= 1` is a type error against a Postgres boolean.
    op.execute(
        'UPDATE "AppSetting" SET nutrition_mode = \'simple\' WHERE nutrition_enabled'
    )

    with op.batch_alter_table('AppSetting') as batch_op:
        batch_op.drop_column('nutrition_enabled')
        batch_op.drop_column('nutrition_db_source')

    with op.batch_alter_table('User') as batch_op:
        batch_op.drop_column('nutrition_mode')


def downgrade():
    with op.batch_alter_table('User') as batch_op:
        batch_op.add_column(sa.Column(
            'nutrition_mode', sa.String(length=10), nullable=False, server_default='off',
        ))

    with op.batch_alter_table('AppSetting') as batch_op:
        batch_op.add_column(sa.Column(
            'nutrition_enabled', sa.Boolean(), nullable=False, server_default=sa.false(),
        ))
        batch_op.add_column(sa.Column(
            'nutrition_db_source', sa.String(length=255), nullable=False, server_default='',
        ))

    # `sa.true()` renders `1` on SQLite and `true` on Postgres.
    app_setting = sa.table(
        'AppSetting',
        sa.column('nutrition_enabled', sa.Boolean()),
        sa.column('nutrition_mode', sa.String()),
    )
    op.execute(
        app_setting.update()
        .where(app_setting.c.nutrition_mode != 'off')
        .values(nutrition_enabled=sa.true())
    )

    with op.batch_alter_table('AppSetting') as batch_op:
        batch_op.drop_column('nutrition_off_lookup_enabled')
        batch_op.drop_column('nutrition_usda_api_key')
        batch_op.drop_column('nutrition_mode')

    with op.batch_alter_table('StockItem') as batch_op:
        batch_op.drop_constraint('fk_stock_item_nutrition_food_id', type_='foreignkey')
        batch_op.drop_column('nutrition_food_id')

    op.drop_index('ix_NutritionPortion_nutrition_food_id', table_name='NutritionPortion')
    op.drop_table('NutritionPortion')
    op.drop_index('ix_NutritionFood_barcode', table_name='NutritionFood')
    op.drop_index('ix_NutritionFood_name', table_name='NutritionFood')
    op.drop_index('ix_NutritionFood_source', table_name='NutritionFood')
    op.drop_table('NutritionFood')
