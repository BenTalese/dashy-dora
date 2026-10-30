"""20260828_line_planned_store

Shopping-list feedback 2026-08-28 — *"people are unable to change which store
they want to get the item from on the list before shopping, they can only mark
where they actually got it from at the end."*

Exactly right. The plan face's only writable store was `purchased_store_id`,
which means "where I bought it" and is a record of something that has already
happened. Using it to express intent worked by accident (it is rung 1 of the
store ladder, so setting it did re-group the line) but made planning and
recording the same field — so a list could not distinguish "I mean to get this
at Aldi" from "I got this at Aldi".

`StockItem.usual_store_id` was the other candidate and is the wrong scope: it
is a standing preference, so setting it from one list would silently change
every future list too.

Hence a per-line column. The prefill chain is
``usual_store_id → planned_store_id → purchased_store_id``, each the *default*
for the next and never a write-back (ADR-058's sibling concern: an incidental
purchase is not a change of habit).

No backfill. A NULL `planned_store_id` falls through to `usual_store_id` in the
resolution ladder, which is exactly what every existing line does today — so
copying values in would freeze a currently-live inference into a stale literal.

Revision ID: b2d9f4a7c3e1
Revises: a7f4c2e9b1d6
Create Date: 2026-08-28 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy_utils import UUIDType

# revision identifiers, used by Alembic.
revision = 'b2d9f4a7c3e1'
down_revision = 'a7f4c2e9b1d6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ShoppingListLine') as batch:
        # UUIDType, as the model declares it (`sa.Uuid` is CHAR(32) on SQLite).
        # Installs that ran the `sa.Uuid` form are converted by e7a2c5f9b3d1.
        batch.add_column(sa.Column('planned_store_id', UUIDType(), nullable=True))
        batch.create_foreign_key(
            'fk_shopping_list_line_planned_store',
            'Store', ['planned_store_id'], ['id'], ondelete='SET NULL',
        )


def downgrade():
    with op.batch_alter_table('ShoppingListLine') as batch:
        batch.drop_constraint('fk_shopping_list_line_planned_store', type_='foreignkey')
        batch.drop_column('planned_store_id')
