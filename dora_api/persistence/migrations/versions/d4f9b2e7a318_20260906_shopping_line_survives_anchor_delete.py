"""20260906_shopping_line_survives_anchor_delete

FU-883 — deleting a stock item erased its lines from *completed* shopping
lists, because `ShoppingListLine.stock_item_id` / `product_id` were both
ON DELETE CASCADE. A finished list is a receipt; losing entries from it is
data loss. (The same table has always treated stores correctly:
`purchased_store_id` / `planned_store_id` are SET NULL, commented "losing a
store must not take the line with it".)

Three coupled changes:

1. `display_name_snapshot` — the line's display name, frozen at
   `POST /finish`. The name only ever lived on the anchor row, so a
   SET NULL survivor would otherwise be nameless, which is precisely why
   CASCADE was chosen originally.
2. Both anchors flip CASCADE → SET NULL.
3. `ck_shopping_list_line_anchor` gains a third clause. It demanded an
   anchor be present; nulling the last anchor of a product-only line would
   violate it and the delete would fail — **loudly on Postgres, silently on
   SQLite** (FKs off by default there), which is the divergence class that
   has bitten this repo before.

**The backfill is not optional.** Existing rows predate the snapshot, so a
line already sitting on a done list would have neither an anchor (after a
later delete) nor a snapshot, and would violate the new CHECK at delete
time. Every existing line is backfilled from its current anchor, so the
constraint holds for historic data from the moment it exists.

Revision ID: d4f9b2e7a318
Revises: b8d2f4a6c091
Create Date: 2026-09-06 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = 'd4f9b2e7a318'
down_revision = 'b8d2f4a6c091'
branch_labels = None
depends_on = None

_ANCHOR_CHECK_SUFFIX = 'ck_shopping_list_line_anchor'


def _anchor_check_name() -> str:
    """Reflect the anchor CHECK's real name instead of assuming it.

    It differs by how the database was built. `ck_%(table_name)s_%(constraint_name)s`
    is re-applied to the already-prefixed name every time a batch_alter_table
    rebuilds this table, so a migrated DB currently carries
    `ck_ShoppingListLine_` **four times** over, while one built by `create_all`
    carries it once. Hardcoding either spelling breaks the other.
    """
    inspector = sa.inspect(op.get_bind())
    for constraint in inspector.get_check_constraints('ShoppingListLine'):
        name = constraint.get('name') or ''
        if name.endswith(_ANCHOR_CHECK_SUFFIX):
            return name
    raise RuntimeError(
        f"No CHECK constraint ending in '{_ANCHOR_CHECK_SUFFIX}' on "
        "ShoppingListLine — schema is not in the state this migration expects."
    )


def _reflected(batch_op, name: str) -> str:
    """The reflected CHECK name, in the form each backend's drop matches.

    Postgres drops natively, so the name must reach `DROP CONSTRAINT` as-is:
    `f()` stops the naming convention being applied to the already-final name
    (which would name a constraint that doesn't exist). SQLite's batch rebuild
    looks the name up among the reflected constraints, which carry the
    convention applied once more, so there the plain name is what matches.
    """
    return name if op.get_bind().dialect.name == 'sqlite' else batch_op.f(name)


def upgrade():
    op.add_column(
        'ShoppingListLine',
        sa.Column('display_name_snapshot', sa.String(255), nullable=True),
    )

    # Backfill from whichever anchor names the line today: the stock item
    # when there is one, else the product (the same precedence the detail
    # DTO uses to build its display name). Correlated subqueries rather than
    # UPDATE..FROM so this runs identically on SQLite and Postgres.
    op.execute("""
        UPDATE "ShoppingListLine"
        SET display_name_snapshot = (
            SELECT "StockItem".name FROM "StockItem"
            WHERE "StockItem".id = "ShoppingListLine".stock_item_id
        )
        WHERE stock_item_id IS NOT NULL
    """)
    op.execute("""
        UPDATE "ShoppingListLine"
        SET display_name_snapshot = (
            SELECT "Product".name FROM "Product"
            WHERE "Product".id = "ShoppingListLine".product_id
        )
        WHERE display_name_snapshot IS NULL AND product_id IS NOT NULL
    """)

    # Batch mode so SQLite gets a table rebuild; on Postgres these are
    # straight constraint swaps. `env.py` injects the metadata naming
    # convention into every batch_alter_table, so the FKs carry deterministic
    # names and can be dropped by name on both backends.
    anchor_check = _anchor_check_name()
    with op.batch_alter_table('ShoppingListLine') as batch_op:
        batch_op.drop_constraint(
            'fk_ShoppingListLine_stock_item_id_StockItem', type_='foreignkey',
        )
        batch_op.create_foreign_key(
            'fk_ShoppingListLine_stock_item_id_StockItem',
            'StockItem', ['stock_item_id'], ['id'], ondelete='SET NULL',
        )
        batch_op.drop_constraint(
            'fk_ShoppingListLine_product_id_Product', type_='foreignkey',
        )
        batch_op.create_foreign_key(
            'fk_ShoppingListLine_product_id_Product',
            'Product', ['product_id'], ['id'], ondelete='SET NULL',
        )
        batch_op.drop_constraint(_reflected(batch_op, anchor_check), type_='check')
        batch_op.create_check_constraint(
            _ANCHOR_CHECK_SUFFIX,
            'stock_item_id IS NOT NULL OR product_id IS NOT NULL '
            'OR display_name_snapshot IS NOT NULL',
        )


def downgrade():
    # Lines orphaned while the new rule was in force have no anchor to
    # restore, and CASCADE cannot express "keep". Drop them, matching what
    # the old schema would have done to them at delete time.
    op.execute("""
        DELETE FROM "ShoppingListLine"
        WHERE stock_item_id IS NULL AND product_id IS NULL
    """)

    anchor_check = _anchor_check_name()
    with op.batch_alter_table('ShoppingListLine') as batch_op:
        batch_op.drop_constraint(
            'fk_ShoppingListLine_stock_item_id_StockItem', type_='foreignkey',
        )
        batch_op.create_foreign_key(
            'fk_ShoppingListLine_stock_item_id_StockItem',
            'StockItem', ['stock_item_id'], ['id'], ondelete='CASCADE',
        )
        batch_op.drop_constraint(
            'fk_ShoppingListLine_product_id_Product', type_='foreignkey',
        )
        batch_op.create_foreign_key(
            'fk_ShoppingListLine_product_id_Product',
            'Product', ['product_id'], ['id'], ondelete='CASCADE',
        )
        batch_op.drop_constraint(_reflected(batch_op, anchor_check), type_='check')
        batch_op.create_check_constraint(
            _ANCHOR_CHECK_SUFFIX,
            'stock_item_id IS NOT NULL OR product_id IS NOT NULL',
        )
        batch_op.drop_column('display_name_snapshot')
