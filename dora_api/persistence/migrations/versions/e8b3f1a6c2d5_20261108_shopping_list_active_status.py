"""20261108_shopping_list_active_status

Shopping list UX v5 (PROPOSAL_SHOPPING_LIST_UX_V5): draft and shopping merge
into one ``active`` status, and ticking a line restocks its item.

- ``ShoppingList.status``: 'draft' and 'shopping' become 'active'; the column
  default follows. 'done' is untouched.
- ``ShoppingListLine`` gains the restock-on-tick record: ``restocked_at``
  (set when the tick restocked the item) and the item's level and timestamp
  from before it, so an untick puts them back. ``restock_from_level_id`` is a
  plain UUID with no FK, like ``preferred_buy_id``: SQLite batch mode and an
  added FK on this table don't mix, and a dangling id just restores no level.
- ``User.shopping_simple_mode`` goes: Simple mode is replaced by the merged
  list and never shipped.

Lines ticked before this migration were never restocked (``restocked_at`` is
NULL); ``/finish`` still restocks those.

Revision ID: e8b3f1a6c2d5
Revises: d2a7e5c9b1f4
Create Date: 2026-11-08 00:00:00.000000
"""
import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op


revision = 'e8b3f1a6c2d5'
down_revision = 'd2a7e5c9b1f4'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        'UPDATE "ShoppingList" SET status = \'active\' '
        'WHERE status IN (\'draft\', \'shopping\')'
    )
    with op.batch_alter_table('ShoppingList') as batch:
        batch.alter_column(
            'status', existing_type=sa.String(16), existing_nullable=False,
            server_default='active',
        )
    with op.batch_alter_table('ShoppingListLine') as batch:
        batch.add_column(sa.Column('restocked_at', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column(
            'restock_from_level_id', sqlalchemy_utils.types.uuid.UUIDType(), nullable=True,
        ))
        batch.add_column(sa.Column(
            'restock_from_level_updated_at', sa.DateTime(timezone=True), nullable=True,
        ))
    with op.batch_alter_table('User') as batch:
        batch.drop_column('shopping_simple_mode')


def downgrade():
    with op.batch_alter_table('User') as batch:
        batch.add_column(sa.Column(
            'shopping_simple_mode', sa.Boolean(),
            nullable=False, server_default=sa.false(),
        ))
    with op.batch_alter_table('ShoppingListLine') as batch:
        batch.drop_column('restock_from_level_updated_at')
        batch.drop_column('restock_from_level_id')
        batch.drop_column('restocked_at')
    with op.batch_alter_table('ShoppingList') as batch:
        batch.alter_column(
            'status', existing_type=sa.String(16), existing_nullable=False,
            server_default='draft',
        )
    op.execute('UPDATE "ShoppingList" SET status = \'draft\' WHERE status = \'active\'')
