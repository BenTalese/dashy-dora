import logging
from collections import Counter
from logging.config import fileConfig

from flask import current_app

from alembic import context, op


# R-0NN — wrap op.batch_alter_table so every migration's batch op inherits
# the metadata's naming convention without each call site having to pass it.
# Required because SQLite's lack of ALTER ... DROP CONSTRAINT forces Alembic
# to rebuild the table; rebuilding needs every UNIQUE/CHECK/FK to have a
# name, and the only way batch's reflection can name pre-existing anonymous
# constraints is if the convention is supplied at the call. See
# ENGINEERING_STANDARDS.md.
_ORIGINAL_BATCH_ALTER_TABLE = op.batch_alter_table


def _batch_alter_table_with_convention(*args, **kwargs):
    if 'naming_convention' not in kwargs:
        try:
            metadata = current_app.extensions['migrate'].db.metadata
            if metadata.naming_convention:
                kwargs['naming_convention'] = dict(metadata.naming_convention)
        except (RuntimeError, KeyError, AttributeError):
            pass
    return _ORIGINAL_BATCH_ALTER_TABLE(*args, **kwargs)


op.batch_alter_table = _batch_alter_table_with_convention

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')


def get_engine():
    try:
        # this works with Flask-SQLAlchemy<3 and Alchemical
        return current_app.extensions['migrate'].db.get_engine()
    except TypeError:
        # this works with Flask-SQLAlchemy>=3
        return current_app.extensions['migrate'].db.engine


def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace(
            '%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')


# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
config.set_main_option('sqlalchemy.url', get_engine_url())
target_db = current_app.extensions['migrate'].db

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_metadata():
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=get_metadata(),
        literal_binds=True,
        render_as_batch=True,
        # R-0NN — every constraint deterministically named; SQLite batch
        # mode can then rebuild a table without choking on unnamed UNIQUE/
        # CHECK/FK. See ENGINEERING_STANDARDS.md.
        naming_convention=get_metadata().naming_convention,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    connectable = get_engine()

    with connectable.connect() as connection:
        # SQLite: run the chain with foreign-key enforcement OFF. The app turns
        # it on for every connection (`_enable_sqlite_foreign_keys`), and with
        # it on, a batch rebuild's `DROP TABLE <parent>` runs an implicit
        # DELETE that fires every child's ON DELETE action: CASCADE children
        # are deleted and SET NULL links are blanked, even though the rows come
        # straight back in the rebuilt table (R-095). SQLite's own
        # table-rebuild procedure turns enforcement off first; the PRAGMA is a
        # no-op inside a transaction, so it has to happen here, before one
        # opens. `_check_sqlite_foreign_keys` then refuses any upgrade that
        # left a dangling reference the database did not already have.
        sqlite = connection.dialect.name == 'sqlite'
        if sqlite:
            connection.exec_driver_sql('PRAGMA foreign_keys=OFF')
            violations_before = _sqlite_foreign_key_violations(connection)
            head_before = _current_revisions(connection)
            # Close SQLAlchemy's autobegun transaction: Alembic treats a
            # connection already in one as externally managed and never
            # commits the migrations.
            connection.commit()
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            process_revision_directives=process_revision_directives,
            # R-0NN — see run_migrations_offline(). render_as_batch is
            # already in Flask-Migrate's configure_args for SQLite.
            naming_convention=get_metadata().naming_convention,
            **current_app.extensions['migrate'].configure_args
        )

        try:
            with context.begin_transaction():
                context.run_migrations()
                # Only worth the full scan when a revision actually ran: at
                # head the counts can't have changed, and the scan touches
                # every FK on every boot otherwise.
                if sqlite and _revision_applied(connection, head_before):
                    _check_sqlite_foreign_keys(connection, violations_before)
        finally:
            if sqlite:
                connection.exec_driver_sql('PRAGMA foreign_keys=ON')
                connection.commit()


def _sqlite_foreign_key_violations(connection):
    """Dangling references, counted per (child table, parent table). Counted
    rather than keyed by rowid because a batch rebuild may renumber rowids."""
    rows = connection.exec_driver_sql('PRAGMA foreign_key_check').fetchall()
    return Counter((row[0], row[2]) for row in rows)


def _current_revisions(connection) -> frozenset:
    try:
        rows = connection.exec_driver_sql('SELECT version_num FROM alembic_version').fetchall()
    except Exception:  # noqa: BLE001 — no version table yet (first run)
        return frozenset()
    return frozenset(r[0] for r in rows)


def _revision_applied(connection, head_before: frozenset) -> bool:
    return _current_revisions(connection) != head_before


def _check_sqlite_foreign_keys(connection, before):
    """Refuse to finish the boot if this run introduced dangling references.
    A loud detector, not a rollback: SQLite's DDL is non-transactional in
    Alembic (`transactional_ddl = False`), so each revision has already
    committed by the time this runs — the point is that the operator sees
    the loss on the boot that caused it, with the pre-upgrade backup still
    fresh, instead of months later. References that predate the run are left
    alone: they are not this upgrade's doing, and refusing them would strand
    the install."""
    introduced = _sqlite_foreign_key_violations(connection) - before
    if introduced:
        detail = ', '.join(f'{child} -> {parent}: {n}' for (child, parent), n in sorted(introduced.items()))
        raise RuntimeError(f'migration left new dangling foreign key references ({detail})')


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
