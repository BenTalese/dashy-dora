"""20260826_store_brand_colour

Shopping-list feedback 2026-08-26 — the "Where you'll spend it" store
breakdown coloured its buckets from a categorical chart ramp, so Woolworths
could come out red and Coles green. The colour is now derived from the store's
own uploaded logo (majority/primary colour), which is a fact about the store,
not about the chart — hence a column rather than a client-side computation.

Backfilled here because logos already uploaded would otherwise stay on the
hash swatch forever: there is no other write path that would revisit them.
The extraction is best-effort — a greyscale or unreadable logo simply leaves
NULL, which is the fallback the SPA already handles.

Revision ID: c9f2a7d4e1b8
Revises: b3f7c1d9a2e6
Create Date: 2026-08-26 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy_utils import UUIDType

from dora_api.features.stores._logo_colour import dominant_colour

# revision identifiers, used by Alembic.
revision = 'c9f2a7d4e1b8'
down_revision = 'b3f7c1d9a2e6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('Store') as batch:
        batch.add_column(sa.Column('brand_colour', sa.String(7), nullable=True))

    connection = op.get_bind()
    # UUIDType, as the model declares it: the stored id is 16 raw bytes on
    # SQLite (BINARY(16)) and a native uuid on Postgres. `sa.Uuid` reads it as
    # a 32-char hex string on SQLite and fails on every row.
    store = sa.table(
        'Store',
        sa.column('id', UUIDType()),
        sa.column('image', sa.LargeBinary),
        sa.column('brand_colour', sa.String),
    )
    rows = connection.execute(
        sa.select(store.c.id, store.c.image).where(store.c.image.isnot(None))
    ).all()
    for store_id, image in rows:
        colour = dominant_colour(image)
        if colour is None:
            continue
        connection.execute(
            store.update().where(store.c.id == store_id).values(brand_colour=colour)
        )


def downgrade():
    with op.batch_alter_table('Store') as batch:
        batch.drop_column('brand_colour')
