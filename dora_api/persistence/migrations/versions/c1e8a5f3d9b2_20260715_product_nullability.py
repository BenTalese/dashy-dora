"""20260715_product_nullability

FU-564 (from the FU-393 data-model sanity sweep, Finding 3) — reconcile the
three `Product` columns whose nullability drifted between the ORM model and the
migrated schema. The model has long declared the intended state; production
never enforced it, so a `create_all` dev DB and a migrated prod DB disagreed:

  * `is_active`      — model NOT NULL, prod nullable  → tighten prod to NOT NULL
  * `is_available`   — model NOT NULL, prod nullable  → tighten prod to NOT NULL
  * `merchant_stockcode` — model nullable, prod NOT NULL → loosen prod to nullable

The app always sets `is_active`/`is_available` explicitly (True on the ingestion
+ create-product + seed paths), so any stray prod NULL is backfilled to True
before the NOT NULL is applied. `merchant_stockcode` was loosened in the
merchant→store era but the column stayed NOT NULL in prod, which could reject an
insert a dev DB accepts.

Nullability changes need a column rebuild on SQLite, so this uses
`batch_alter_table` (which emits a native `ALTER COLUMN` on Postgres — portable,
R-005/R-006). Batch mode reflects + recreates the existing `Product` table, so
the store_id FK's current (drifted, ondelete=None) shape is preserved verbatim —
that separate ondelete drift is FU-565, deliberately not touched here.

The fourth nullability drift, `User.username` (model NOT NULL / prod nullable),
is a documented, intentional deferral (see the model comment + FU-564) and is
left as-is.

Revision ID: c1e8a5f3d9b2
Revises: b9d4f2a7c3e1
Create Date: 2026-07-15 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op


revision = 'c1e8a5f3d9b2'
down_revision = 'b9d4f2a7c3e1'
branch_labels = None
depends_on = None


def upgrade():
    # Backfill any prod NULLs before tightening (app default is True). No-op on a
    # fresh from-empty upgrade; matters only for an existing populated install.
    # `sa.true()` renders `1` on SQLite and `true` on Postgres (a boolean column
    # there rejects the integer literal).
    product = sa.table(
        'Product',
        sa.column('is_active', sa.Boolean()),
        sa.column('is_available', sa.Boolean()),
    )
    op.execute(product.update().where(product.c.is_active.is_(None)).values(is_active=sa.true()))
    op.execute(product.update().where(product.c.is_available.is_(None)).values(is_available=sa.true()))
    with op.batch_alter_table('Product') as batch:
        batch.alter_column('is_active', existing_type=sa.Boolean(), nullable=False)
        batch.alter_column('is_available', existing_type=sa.Boolean(), nullable=False)
        batch.alter_column(
            'merchant_stockcode',
            existing_type=sa.String(length=255),
            nullable=True,
        )


def downgrade():
    with op.batch_alter_table('Product') as batch:
        batch.alter_column(
            'merchant_stockcode',
            existing_type=sa.String(length=255),
            nullable=False,
        )
        batch.alter_column('is_available', existing_type=sa.Boolean(), nullable=True)
        batch.alter_column('is_active', existing_type=sa.Boolean(), nullable=True)
