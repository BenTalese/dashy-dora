"""20261030_constraint_names_match_model

R-015 / R-034: give every constraint and index the name the ORM model gives it.
A migrated database and a `create_all` one disagreed on 30-odd names, for three
reasons:

* hand-written literals in older migrations (`fk_recipe_category_id`,
  `uq_push_subscription_endpoint`, `pk_stock_item_price_observation`, ...),
  which bypass the naming convention;
* table renames (ProductBarcode → Barcode, Merchant → Store), which rename the
  table but not its constraints. SQLite re-derived some of these on a later
  batch rebuild; Postgres never does, so it still has `pk_Merchant` and
  `fk_IngestionStoreMapping_merchant_id_Merchant`;
* SQLite batch rebuilds re-applying `ck_%(table_name)s_` to a CHECK name that
  already carried it (`ck_ShoppingListLine_ck_ShoppingListLine_ck_...`).

A later migration that drops one of these by its conventional name fails on
whichever backend kept the other spelling, which is the class of bug d3f8b1a6c4e2
and d4f9b2e7a318 hit. Also, `IngestionStoreMapping (source_id, external_name)`
was a UNIQUE constraint in the migrated schema and a unique index in the model;
it becomes the index.

Each name is reflected first and only touched when it differs, so the
migration is a no-op wherever a name is already right (R-006 carve-out: which
names are wrong depends on the backend and on the install's history).

Postgres renames in place (`ALTER TABLE ... RENAME CONSTRAINT`,
`ALTER INDEX ... RENAME`). SQLite cannot rename a constraint, so each affected
table is rebuilt in batch mode; rows are copied as they are (R-095), and
`env.py` runs the chain with foreign keys off so rebuilding a parent table
does not fire its children's ON DELETE actions.

Revision ID: f4b8d1c6a9e2
Revises: e7a2c5f9b3d1
Create Date: 2026-10-30 00:00:00.000000
"""
import re

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql.elements import conv


revision = 'f4b8d1c6a9e2'
down_revision = 'e7a2c5f9b3d1'
branch_labels = None
depends_on = None


# (table, columns, referred table, ondelete, legacy literal name or None)
_FKS = [
    ('Barcode', ('product_id',), 'Product', 'CASCADE', None),
    ('Barcode', ('stock_item_id',), 'StockItem', 'CASCADE', None),
    ('IngestionStoreMapping', ('store_id',), 'Store', 'SET NULL', None),
    ('MealPlanEntry', ('cook_batch_id',), 'CookBatch', 'SET NULL', 'fk_meal_plan_entry_cook_batch_id'),
    ('Recipe', ('category_id',), 'Category', 'SET NULL', 'fk_recipe_category_id'),
    ('Recipe', ('cuisine_id',), 'Cuisine', 'SET NULL', 'fk_recipe_cuisine_id'),
    ('RecipeIngredient', ('section_id',), 'RecipeSection', 'SET NULL', 'fk_recipe_ingredient_section'),
    ('RecipeStep', ('section_id',), 'RecipeSection', 'SET NULL', 'fk_recipe_step_section'),
    ('ShoppingListLine', ('planned_store_id',), 'Store', 'SET NULL', 'fk_shopping_list_line_planned_store'),
    ('ShoppingListLine', ('purchased_store_id',), 'Store', 'SET NULL', 'fk_shoppinglistline_purchased_merchant'),
    ('StockItem', ('nutrition_food_id',), 'NutritionFood', 'SET NULL', 'fk_stock_item_nutrition_food_id'),
    ('StockItemPriceObservation', ('shopping_list_line_id',), 'ShoppingListLine', 'SET NULL',
     'fk_stock_item_price_observation_shopping_list_line_id'),
    ('StockItemPriceObservation', ('stock_item_id',), 'StockItem', 'CASCADE',
     'fk_stock_item_price_observation_stock_item_id'),
    ('StockItemPriceObservation', ('store_id',), 'Store', 'SET NULL', 'fk_stock_item_price_observation_store_id'),
]

# (table, columns, legacy literal name or None)
_PKS = [
    ('Barcode', ('id',), None),
    ('StockItemPriceObservation', ('id',), 'pk_stock_item_price_observation'),
    ('Store', ('id',), None),
]

# (table, columns, legacy literal name or None)
_UNIQUES = [
    ('Barcode', ('barcode',), None),
    ('Barcode', ('product_id',), 'uq_barcode_product_id'),
    ('IngestionSource', ('key_hash',), 'uq_ingestion_source_key_hash'),
    ('PushSubscription', ('endpoint',), 'uq_push_subscription_endpoint'),
]

# (table, columns, legacy literal name or None)
_INDEXES = [
    ('Recipe', ('version_group_id',), 'ix_recipe_version_group_id'),
]

# A UNIQUE constraint in the migrated schema, a unique index in the model.
_UNIQUE_INDEX = (
    'IngestionStoreMapping', ('source_id', 'external_name'), 'uq_ingestion_store_mapping_source_external',
)

# (table, identifying suffix, model name). Found by suffix because the
# migrated spelling varies by backend and by how often SQLite rebuilt the table.
_CHECKS = [
    ('Barcode', 'barcode_target_at_least_one', 'ck_Barcode_ck_barcode_target_at_least_one'),
    ('RecipeIngredient', 'recipe_ingredient_anchor', 'ck_RecipeIngredient_recipe_ingredient_anchor'),
    ('ShoppingListLine', 'shopping_list_line_anchor', 'ck_ShoppingListLine_ck_shopping_list_line_anchor'),
    ('StockItemSubstitute', 'substitute_canonical', 'ck_StockItemSubstitute_ck_substitute_canonical'),
    ('StockItemSubstitute', 'substitute_ratio_all_or_none', 'ck_StockItemSubstitute_ck_substitute_ratio_all_or_none'),
]


def _conventional(name):
    """`name` as the naming convention would emit it on this backend, i.e.
    truncated with a hash suffix where it exceeds the identifier limit
    (Postgres: 63)."""
    preparer = op.get_bind().dialect.identifier_preparer
    return preparer.truncate_and_render_constraint_name(conv(name), _alembic_quote=False)


def _fk_name(table, cols, ref):
    return _conventional(f'fk_{table}_{cols[0]}_{ref}')


_SQLITE_NAMED = re.compile(
    r'CONSTRAINT\s+"?(\w+)"?\s+(PRIMARY KEY|FOREIGN KEY)\s*\(([^)]*)\)', re.IGNORECASE,
)


class _Reflected:
    """Current names on one table. SQLite's inspector reports a quoted FK or
    PK name as None, so on SQLite those two are read from the table's DDL."""

    def __init__(self, table):
        bind = op.get_bind()
        insp = sa.inspect(bind)
        self.sqlite = bind.dialect.name == 'sqlite'
        self.fk_reflected = {tuple(fk['constrained_columns']): fk.get('name') for fk in insp.get_foreign_keys(table)}
        pk = insp.get_pk_constraint(table)
        self.pk_reflected = pk.get('name')
        self.fk = dict(self.fk_reflected)
        self.pk = self.pk_reflected
        if self.sqlite:
            ddl = bind.execute(
                sa.text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :t"), {'t': table},
            ).scalar() or ''
            for name, kind, cols in _SQLITE_NAMED.findall(ddl):
                key = tuple(c.strip().strip('"') for c in cols.split(','))
                if kind.upper() == 'PRIMARY KEY':
                    self.pk = name
                else:
                    self.fk[key] = name
        self.unique = {tuple(u['column_names']): u['name'] for u in insp.get_unique_constraints(table)}
        self.index = {tuple(i['column_names']): (i['name'], bool(i.get('unique'))) for i in insp.get_indexes(table)}
        self.checks = [(c['name'], c['sqltext']) for c in insp.get_check_constraints(table)]


def _plan(want):
    """Per table, what differs from `want` (the name each object should have).

    `want` keys: ('fk'|'pk'|'uq'|'ix', table, cols) and ('ck', table, suffix),
    plus ('uix', table, cols) / ('uq-from-uix', table, cols) for the
    IngestionStoreMapping constraint<->index swap.
    """
    tables = sorted({key[1] for key in want})
    plan = {}
    for table in tables:
        cur = _Reflected(table)
        changes = []
        for key, target in want.items():
            if key[1] != table:
                continue
            kind, cols = key[0], key[2]
            if kind == 'fk':
                existing = cur.fk.get(cols)
                if existing is not None and existing != target:
                    changes.append(('fk', cols, existing, target))
            elif kind == 'pk':
                if cur.pk is not None and cur.pk != target:
                    changes.append(('pk', cols, cur.pk, target))
            elif kind == 'uq':
                existing = cur.unique.get(cols)
                if existing is not None and existing != target:
                    changes.append(('uq', cols, existing, target))
            elif kind == 'ix':
                existing = cur.index.get(cols)
                if existing is not None and existing[0] != target:
                    changes.append(('ix', cols, existing[0], target))
            elif kind == 'uix':
                if cols in cur.unique:
                    changes.append(('uq->uix', cols, cur.unique[cols], target))
            elif kind == 'uq-from-uix':
                existing = cur.index.get(cols)
                if existing is not None and existing[1]:
                    changes.append(('uix->uq', cols, existing[0], target))
            elif kind == 'ck':
                for name, _sql in cur.checks:
                    if name.endswith(cols) and name != target:
                        changes.append(('ck', cols, name, target))
        if changes:
            plan[table] = (cur, changes)
    return plan


def _quote(name):
    return op.get_bind().dialect.identifier_preparer.quote(name)


def _apply_postgres(plan):
    for table, (_cur, changes) in plan.items():
        for kind, cols, old, new in changes:
            if kind in ('fk', 'pk', 'uq', 'ck'):
                op.execute(f'ALTER TABLE {_quote(table)} RENAME CONSTRAINT {_quote(old)} TO {_quote(new)}')
            elif kind == 'ix':
                op.execute(f'ALTER INDEX {_quote(old)} RENAME TO {_quote(new)}')
            elif kind == 'uq->uix':
                op.drop_constraint(op.f(old), table, type_='unique')
                op.create_index(op.f(new), table, list(cols), unique=True)
            elif kind == 'uix->uq':
                op.drop_index(op.f(old), table_name=table)
                op.create_unique_constraint(op.f(new), table, list(cols))


def _apply_sqlite(plan, fk_specs):
    for table, (cur, changes) in plan.items():
        rebuild = [c for c in changes if c[0] in ('fk', 'pk', 'uq', 'ck', 'uq->uix')]
        if rebuild:
            # Inside a batch, a reflected FK/PK that SQLite reports unnamed
            # (quoted in the DDL) is keyed by its conventional name; a named
            # one by its own name. CHECK names come back with the convention
            # applied once more, so they are dropped by their plain name and
            # every one (not just the renamed ones) is re-created under an
            # exact `f()` name, or the rebuild would re-prefix it.
            check_target = {c[2]: c[3] for c in changes if c[0] == 'ck'}
            with op.batch_alter_table(table, recreate='always') as batch:
                for kind, cols, old, new in rebuild:
                    if kind == 'fk':
                        ref, ondelete = fk_specs[(table, cols)]
                        key = cur.fk_reflected.get(cols) or _fk_name(table, cols, ref)
                        batch.drop_constraint(batch.f(key), type_='foreignkey')
                        batch.create_foreign_key(batch.f(new), ref, list(cols), ['id'], ondelete=ondelete)
                    elif kind == 'pk':
                        key = cur.pk_reflected or f'pk_{table}'
                        batch.drop_constraint(batch.f(key), type_='primary')
                        batch.create_primary_key(batch.f(new), list(cols))
                    elif kind in ('uq', 'uq->uix'):
                        batch.drop_constraint(batch.f(old), type_='unique')
                        if kind == 'uq':
                            batch.create_unique_constraint(batch.f(new), list(cols))
                for name, sqltext in cur.checks:
                    batch.drop_constraint(name, type_='check')
                    batch.create_check_constraint(batch.f(check_target.get(name, name)), sqltext)
        for kind, cols, old, new in changes:
            if kind == 'ix':
                op.drop_index(op.f(old), table_name=table)
                op.create_index(op.f(new), table, list(cols))
            elif kind == 'uq->uix':
                op.create_index(op.f(new), table, list(cols), unique=True)
            elif kind == 'uix->uq':
                op.drop_index(op.f(old), table_name=table)
                with op.batch_alter_table(table, recreate='always') as batch:
                    batch.create_unique_constraint(batch.f(new), list(cols))
                    for name, sqltext in cur.checks:
                        batch.drop_constraint(name, type_='check')
                        batch.create_check_constraint(batch.f(name), sqltext)


def _reconcile(want):
    fk_specs = {(t, cols): (ref, ondelete) for t, cols, ref, ondelete, _legacy in _FKS}
    plan = _plan(want)
    if op.get_bind().dialect.name == 'sqlite':
        _apply_sqlite(plan, fk_specs)
    else:
        _apply_postgres(plan)


def upgrade():
    want = {}
    for t, cols, ref, _od, _legacy in _FKS:
        want[('fk', t, cols)] = _fk_name(t, cols, ref)
    for t, cols, _legacy in _PKS:
        want[('pk', t, cols)] = _conventional(f'pk_{t}')
    for t, cols, _legacy in _UNIQUES:
        want[('uq', t, cols)] = _conventional(f'uq_{t}_{cols[0]}')
    for t, cols, _legacy in _INDEXES:
        want[('ix', t, cols)] = _conventional(f'ix_{t}_{cols[0]}')
    t, cols, name = _UNIQUE_INDEX
    want[('uix', t, cols)] = name
    for t, suffix, name in _CHECKS:
        want[('ck', t, suffix)] = name
    _reconcile(want)


def downgrade():
    # Restore the hand-written literals, because earlier migrations' downgrades
    # drop those objects by that literal. Names that were convention-derived
    # from a table's old name (ProductBarcode, Merchant) and the doubled CHECK
    # prefixes are not referenced by any earlier migration and stay as the
    # model has them.
    want = {}
    for t, cols, _ref, _od, legacy in _FKS:
        if legacy:
            want[('fk', t, cols)] = legacy
    for t, cols, legacy in _PKS:
        if legacy:
            want[('pk', t, cols)] = legacy
    for t, cols, legacy in _UNIQUES:
        if legacy:
            want[('uq', t, cols)] = legacy
    for t, cols, legacy in _INDEXES:
        if legacy:
            want[('ix', t, cols)] = legacy
    t, cols, name = _UNIQUE_INDEX
    want[('uq-from-uix', t, cols)] = name
    _reconcile(want)
