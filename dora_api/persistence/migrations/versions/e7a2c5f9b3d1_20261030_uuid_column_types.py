"""20261030_uuid_column_types

Three id columns were created with a type other than the model's `UUIDType`:

* `StockItemSubstitute.stock_item_a_id` / `stock_item_b_id` — VARCHAR(36)
  (c8a1d3b6e9f4). On Postgres that migration could not even run (a VARCHAR
  foreign key onto a uuid column), and a VARCHAR column there would compare
  `character varying = uuid` at runtime.
* `ShoppingListLine.planned_store_id` — `sa.Uuid`, CHAR(32) on SQLite
  (b2d9f4a7c3e1). On Postgres `sa.Uuid` is already a native uuid.

Both original migrations now create `UUIDType`, so a database built after this
fix has nothing to convert. One built before it still carries the old types,
which is why each column is reflected and converted only while it is still a
string type (R-006 carve-out: the two install histories genuinely differ, and
this migration is what brings them back together).

Data (R-095): on SQLite the stored values are already the 16-byte blobs
`UUIDType` writes, whatever the declared type, because SQLite never coerces a
blob to a column's affinity. The rebuild therefore copies them as they are; the
column is overridden in `reflect_args` rather than altered with `type_=`,
because the latter makes batch mode wrap the copy in `CAST(... AS BINARY(16))`,
which SQLite reads as NUMERIC and which would destroy every blob. On Postgres
the string form is the canonical uuid text, cast with `USING col::uuid`.

Revision ID: e7a2c5f9b3d1
Revises: b8d2f4a6c1e3
Create Date: 2026-10-30 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy_utils import UUIDType


revision = 'e7a2c5f9b3d1'
down_revision = 'b8d2f4a6c1e3'
branch_labels = None
depends_on = None


# table -> {column: (referred table, ondelete, primary key, nullable)}
_COLUMNS = {
    'StockItemSubstitute': {
        'stock_item_a_id': ('StockItem', 'CASCADE', True, False),
        'stock_item_b_id': ('StockItem', 'CASCADE', True, False),
    },
    'ShoppingListLine': {
        'planned_store_id': ('Store', 'SET NULL', False, True),
    },
}


def _string_columns(table, columns):
    """The columns of `columns` still stored under a string type."""
    reflected = {c['name']: c['type'] for c in sa.inspect(op.get_bind()).get_columns(table)}
    return [name for name in columns if isinstance(reflected[name], sa.String)]


def _keep_check_names(batch, table):
    """Re-create each CHECK under exactly its current name. A SQLite rebuild
    otherwise re-applies the naming convention to the reflected name and
    prefixes it with `ck_<table>_` once more."""
    for check in sa.inspect(op.get_bind()).get_check_constraints(table):
        batch.drop_constraint(check['name'], type_='check')
        batch.create_check_constraint(batch.f(check['name']), check['sqltext'])


def upgrade():
    sqlite = op.get_bind().dialect.name == 'sqlite'
    for table, columns in _COLUMNS.items():
        stale = _string_columns(table, columns)
        if not stale:
            continue
        if sqlite:
            # The overriding Column replaces the reflected one wholesale, so it
            # restates the key and the foreign key the reflected one carried.
            overrides = [
                sa.Column(
                    name, UUIDType(),
                    sa.ForeignKey(f'{columns[name][0]}.id', ondelete=columns[name][1]),
                    primary_key=columns[name][2], nullable=columns[name][3],
                )
                for name in stale
            ]
            with op.batch_alter_table(table, recreate='always', reflect_args=overrides) as batch:
                _keep_check_names(batch, table)
        else:
            for name in stale:
                op.alter_column(
                    table, name,
                    type_=UUIDType(),
                    existing_nullable=columns[name][3],
                    postgresql_using=f'"{name}"::uuid',
                )


def downgrade():
    # The string types were defects, not a schema to return to: a VARCHAR
    # foreign key onto a uuid key cannot exist on Postgres, and on SQLite the
    # stored blobs are identical either way. Nothing to reverse (listed in
    # tests/test_migrations.py `_IRREVERSIBLE_ALLOWLIST`).
    pass
