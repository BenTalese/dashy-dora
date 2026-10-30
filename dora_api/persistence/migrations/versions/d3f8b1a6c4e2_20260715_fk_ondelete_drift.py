"""20260715_fk_ondelete_drift

FU-565 (from the FU-393 data-model sanity sweep, Finding 4) — 6 foreign keys
declare an ``ondelete`` rule in the ORM model that the migrated production schema
never had (created before the ondelete discipline, as anonymous FKs, and never
altered). This is a real correctness gap on BOTH engines — SQLite runs with
``PRAGMA foreign_keys=ON`` (see dora_api/app.py), and Postgres enforces natively —
so e.g. deleting a StockLevel referenced by a StockItem should SET NULL (model)
but instead errors, and deleting a Store a Product points at should be RESTRICTed
(model) but isn't.

Reconciled to the model:
  * ProductOffer.product_id          -> Product  CASCADE
  * ProductHistoricOffer.product_id  -> Product  CASCADE
  * Product.store_id                 -> Store    RESTRICT
  * StockItem.stock_group_id         -> StockGroup    SET NULL
  * StockItem.stock_level_id         -> StockLevel    SET NULL
  * StockItem.stock_location_id      -> StockLocation SET NULL

Changing an FK's ondelete is a constraint recreate → a table rebuild on SQLite
(``batch_alter_table``), a native DROP/ADD CONSTRAINT on Postgres. The reflected
anonymous FKs are named via the metadata NAMING_CONVENTION on the rebuild, and
we wrap the names in ``batch.f(...)`` so the convention isn't applied a second
time (the double-render trap documented on c5a8e1f7d3b2). The batch rebuild
reflects + recreates every other column, FK, and index on these tables, so
StockItem.usual_store_id (already SET NULL) and the FU-563 covering indexes are
preserved.

Revision ID: d3f8b1a6c4e2
Revises: c1e8a5f3d9b2
Create Date: 2026-07-15 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op


revision = 'd3f8b1a6c4e2'
down_revision = 'c1e8a5f3d9b2'
branch_labels = None
depends_on = None


# (table, fk_name, ref_table, [cols], [ref_cols], model_ondelete, prev_ondelete)
_FKS = [
    ("ProductOffer", "fk_ProductOffer_product_id_Product", "Product", ["product_id"], ["id"], "CASCADE"),
    ("ProductHistoricOffer", "fk_ProductHistoricOffer_product_id_Product", "Product", ["product_id"], ["id"], "CASCADE"),
    ("Product", "fk_Product_store_id_Store", "Store", ["store_id"], ["id"], "RESTRICT"),
    ("StockItem", "fk_StockItem_stock_group_id_StockGroup", "StockGroup", ["stock_group_id"], ["id"], "SET NULL"),
    ("StockItem", "fk_StockItem_stock_level_id_StockLevel", "StockLevel", ["stock_level_id"], ["id"], "SET NULL"),
    ("StockItem", "fk_StockItem_stock_location_id_StockLocation", "StockLocation", ["stock_location_id"], ["id"], "SET NULL"),
]


def _existing_fk_name(table, cols, conventional):
    """The FK's current name. On SQLite the batch rebuild reflects these FKs
    anonymous and names them by the convention, so `conventional` is right.
    Postgres keeps whatever name the FK was created with, and
    `Product.store_id`'s is still `fk_Product_merchant_id_Merchant` from before
    the merchant→store rename (a3e9f6c2d8b4), which renamed the column and
    table but not the constraint."""
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        return conventional
    for fk in sa.inspect(bind).get_foreign_keys(table):
        if list(fk['constrained_columns']) == list(cols) and fk.get('name'):
            return fk['name']
    return conventional


def _apply(ondelete_for):
    """Recreate each FK with `ondelete_for(model_ondelete)`, one batch per table
    so a table with several drifted FKs (StockItem) rebuilds only once."""
    by_table: dict[str, list] = {}
    for table, name, ref, cols, refcols, model_od in _FKS:
        by_table.setdefault(table, []).append((name, ref, cols, refcols, model_od))
    for table, fks in by_table.items():
        existing = {name: _existing_fk_name(table, cols, name) for name, _r, cols, _rc, _od in fks}
        with op.batch_alter_table(table) as batch:
            for name, ref, cols, refcols, model_od in fks:
                batch.drop_constraint(batch.f(existing[name]), type_="foreignkey")
                batch.create_foreign_key(
                    batch.f(name), ref, cols, refcols, ondelete=ondelete_for(model_od),
                )


def upgrade():
    _apply(lambda model_od: model_od)


def downgrade():
    # Reverse to the pre-drift prod state: the FKs had NO ondelete rule.
    _apply(lambda _model_od: None)
