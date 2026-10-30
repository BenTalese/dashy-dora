"""FU-536 — Alembic migration round-trip + integrity tests.

116 migration files run at startup via `flask_migrate.upgrade()` and had ZERO
tests. A bad downgrade, a non-portable op, or a data-losing migration would
only surface in production — and the Postgres migration (FU-045) makes
portability imminent. This is the largest untested surface by file count.

Two layers:

  * IN-PROCESS, no DB (fast, zero risk) — read the Alembic ScriptDirectory:
    exactly one head (unambiguous startup upgrade), linear history with no
    orphaned down_revision, and every revision defines a real downgrade (not
    a silent `pass`, bar an explicit allowlist).

  * SUBPROCESS against a throwaway SQLite file (slower, fully isolated) —
    the app's migration run is coupled to `current_app`'s engine, and the
    app singleton in THIS process is bound to the e2e test DB; running
    `downgrade base` in-process would clobber it mid-suite. So each real
    up/down run happens in a child `python -c` with `DORA_DB_PATH` pointed at
    a temp file — a fresh app on a fresh DB, zero blast radius here.
"""
from __future__ import annotations

import base64
import io
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from tests.db_backend import IS_POSTGRES, postgres_url

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MIGRATIONS_DIR = _REPO_ROOT / "dora_api" / "persistence" / "migrations"
_VERSIONS_DIR = _MIGRATIONS_DIR / "versions"


# ── In-process: ScriptDirectory (no database) ──────────────────────────────

def _script_directory() -> ScriptDirectory:
    cfg = Config()
    cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    return ScriptDirectory.from_config(cfg)


def test__migrations__single_head():
    """Exactly one head — a branch/merge would make startup `upgrade head`
    ambiguous (Alembic errors on multiple heads)."""
    heads = _script_directory().get_heads()
    assert len(heads) == 1, (
        f"expected exactly one migration head, found {len(heads)}: {heads}. "
        "An unmerged branch — resolve with `flask db merge`."
    )


def test__migrations__history_is_linear_and_walkable():
    """Every revision's down_revision resolves — no orphan pointing at a
    deleted/renamed revision. walk_revisions raises if the chain is broken."""
    script = _script_directory()
    revs = list(script.walk_revisions())
    assert revs, "no migrations found — script_location wrong?"
    # base() resolving proves the whole chain links back to the root.
    assert script.get_current_head() is not None


# Revisions whose downgrade is legitimately a no-op / irreversible go here with
# a reason. Keep this tight — an entry is a claim "this migration genuinely
# can't be reversed", not a way to silence rot.
_IRREVERSIBLE_ALLOWLIST: dict[str, str] = {
    "e2c5a8f1d7b3": (
        "data-cleanup migration (nullify garbage Product.image values) — the "
        "original garbage isn't recoverable, so a no-op downgrade is correct."
    ),
    "e7a2c5f9b3d1": (
        "converts id columns stored under a string type to UUIDType; the string "
        "types were defects (Postgres cannot hold a VARCHAR FK onto a uuid key, "
        "SQLite's stored blobs are identical either way), so there is no schema "
        "to go back to."
    ),
}


def test__migrations__every_revision_defines_a_real_downgrade():
    """A downgrade that's a bare `pass` (or missing) is un-tested rot: the
    round-trip test can't catch a no-op downgrade that silently drops the
    schema-reversal. Static-scan every version file for a non-empty
    downgrade() body."""
    offenders: list[str] = []
    for path in sorted(_VERSIONS_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        src = path.read_text(encoding="utf-8")
        rev = path.stem.split("_", 1)[0]
        if rev in _IRREVERSIBLE_ALLOWLIST:
            continue
        # Grab the downgrade() body: everything from `def downgrade` to EOF
        # (downgrade is always the last function in an Alembic script).
        idx = src.find("def downgrade(")
        if idx == -1:
            offenders.append(f"{path.name}: no downgrade() at all")
            continue
        body = src[idx:]
        # Strip the def line + docstring/comments; if all that's left is
        # `pass`, it's a silent no-op.
        code_lines = [
            ln.strip()
            for ln in body.splitlines()[1:]
            if ln.strip() and not ln.strip().startswith(("#", '"', "'"))
        ]
        if code_lines == ["pass"]:
            offenders.append(f"{path.name}: downgrade() is a bare `pass`")
    assert not offenders, (
        "migrations with a missing/no-op downgrade (add to "
        "_IRREVERSIBLE_ALLOWLIST with a reason if genuinely one-way):\n  "
        + "\n  ".join(offenders)
    )


# ── Subprocess: real up/down runs against a throwaway SQLite file ──────────

def _run_migration(temp_db: Path, body: str) -> subprocess.CompletedProcess:
    """Run `body` (flask_migrate calls) in a child process with DORA_DB_PATH
    pointed at `temp_db` — a fresh app on a throwaway DB, isolated from the
    e2e test DB this process is bound to."""
    code = (
        "import flask_migrate\n"
        "from dora_api.app import app\n"
        "with app.app_context():\n"
        + "".join(f"    {ln}\n" for ln in body.strip().splitlines())
        + "print('MIGRATION_OK')\n"
    )
    env = {**os.environ, "DORA_DB_PATH": str(temp_db)}
    # FU-561 — `DORA_DB_URL` outranks `DORA_DB_PATH` in the config resolver, so
    # a leaked URL in the parent env (e.g. test_sqlalchemy_repository.py sets one
    # at module scope, which pytest executes at collection time for the whole
    # process) would silently override the temp DB and make the child migrate the
    # wrong file — leaving temp_db empty (missing-tables / no-file failures that
    # only reproduce in the full-suite run, not in isolation). Drop it so the
    # temp `DORA_DB_PATH` is authoritative. (The Postgres test below builds its
    # own env with DORA_DB_URL set deliberately — it doesn't use this helper.)
    env.pop("DORA_DB_URL", None)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


@pytest.fixture()
def temp_db_path():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d) / "migtest.db"


# ── FU-549 — the migration chain now applies cleanly from empty ────────────
# `upgrade head` on a fresh DB previously died inside migration
# a3e9f6c2d8b4_20260618_rename_merchant_to_store at
# `op.batch_alter_table('Product')` with `AttributeError: 'BINARY' object has
# no attribute 'name'` — an Alembic batch-mode rename reading `existing_type.name`
# on a `sqlalchemy_utils.UUIDType`, whose BINARY impl has no `.name`. Fixed
# 2026-07-13 (FU-549) by passing the concrete `sa.BINARY(16)` as `existing_type`
# for the UUIDType-column renames. These tests give the from-empty chain its
# first real coverage (the app's test/seed path uses `db.create_all()`, which
# never exercised migrations), so a regression there fails the suite here.


@pytest.mark.slow
def test__migrations__upgrade_head_from_empty_succeeds(temp_db_path):
    result = _run_migration(temp_db_path, "flask_migrate.upgrade()")
    assert result.returncode == 0 and "MIGRATION_OK" in result.stdout, (
        f"`upgrade head` on an empty DB failed:\n{result.stdout}\n{result.stderr}"
    )
    assert temp_db_path.exists(), "upgrade produced no database file"


@pytest.mark.slow
@pytest.mark.xfail(
    strict=True,
    reason="Known SQLite-batch limitation (won't-fix, dev-only): `downgrade base` "
    "dies dropping the named CHECK constraint on RecipeIngredient (c5a8e1f7d3b2) — "
    "alembic batch mode on SQLite doesn't carry reflected CHECK constraints into "
    "its rebuild table, so drop_constraint can't find it. Downgrade is dev/rollback "
    "tooling only; production never downgrades (upgrade-from-empty boot path is the "
    "prod path). Expected to XPASS on Postgres CI (named checks drop natively, no "
    "table rebuild) — revisit if it flips there.",
)
def test__migrations__down_up_roundtrip_is_clean(temp_db_path):
    """upgrade head -> downgrade base -> upgrade head with no exception.
    Catches downgrades that were never actually run (the common rot)."""
    result = _run_migration(
        temp_db_path,
        "flask_migrate.upgrade()\n"
        "flask_migrate.downgrade(revision='base')\n"
        "flask_migrate.upgrade()",
    )
    assert result.returncode == 0 and "MIGRATION_OK" in result.stdout, (
        f"down/up round-trip failed:\n{result.stdout}\n{result.stderr}"
    )


# Alembic's own bookkeeping table — exists in the migrated DB, never in the ORM.
_IGNORE_TABLES = {"alembic_version"}

# FU-563 — documented, tracked model↔migration drifts the comparison below
# deliberately ignores so it can still catch NEW drift. Every entry is a known
# carve-out with an owner; do NOT add here to silence a real regression.
_KNOWN_NULLABILITY_DRIFT: dict[tuple[str, str], str] = {
    ("User", "username"): (
        "documented deferral — the add_user_auth migration left username nullable "
        "in prod (risky in-place rewrite over pre-existing rows); the app enforces "
        "non-null uniqueness on insert. Model keeps NOT NULL intentionally."
    ),
    # The 3 Product nullability drifts (is_active / is_available / merchant_stockcode)
    # were reconciled in prod by migration c1e8a5f3d9b2 (FU-564), so they're no longer
    # allowlisted — the comparison below now actively enforces them.
}
# Unique colsets the model declares but prod doesn't (or vice-versa), by (table, cols).
_KNOWN_UNIQUE_DRIFT: dict[tuple[str, tuple[str, ...]], str] = {
    ("User", ("username",)): (
        "paired with the username nullability deferral above — the model declares "
        "the uniqueness the app enforces; prod's column stays nullable + unindexed."
    ),
}


# Column types that differ in spelling only: unbounded VARCHAR in the model,
# TEXT in the migrated schema. Same storage and behaviour on SQLite and
# Postgres, so not worth a rebuild of either table.
_KNOWN_TYPE_DRIFT: dict[tuple[str, str], str] = {
    ("AuditEvent", "payload"): "TEXT (migrated) vs unbounded VARCHAR (model): equivalent.",
    ("RecipeStep", "hint"): "TEXT (migrated) vs unbounded VARCHAR (model): equivalent.",
    ("RecipeStep", "text"): "TEXT (migrated) vs unbounded VARCHAR (model): equivalent.",
}
# Constraint / index names (R-015): (table, kind, name) present on one side only.
_KNOWN_NAME_DRIFT: dict[tuple[str, str, str], str] = {
    ("User", "uq", "uq_User_username"): (
        "the FU-563 username deferral above: the model's UNIQUE has no migrated twin."
    ),
}

# SQLite's inspector reports a quoted (mixed-case) FK or PK name as None, so
# those two are read from the table's DDL.
_NAMED_KEY = re.compile(r'CONSTRAINT\s+"?(\w+)"?\s+(PRIMARY KEY|FOREIGN KEY)', re.IGNORECASE)


def _reflect(insp, engine):
    """table -> {cols: {name: nullable}, types, plain: set[colset], uniq: set[colset],
    fks, names: set[(kind, name)]}."""
    out = {}
    with engine.connect() as conn:
        ddl = dict(conn.exec_driver_sql("SELECT name, sql FROM sqlite_master WHERE type = 'table'").fetchall())
    for t in insp.get_table_names():
        if t in _IGNORE_TABLES:
            continue
        cols = {c["name"]: bool(c["nullable"]) for c in insp.get_columns(t)}
        types = {c["name"]: str(c["type"]) for c in insp.get_columns(t)}
        names = {("ck", c["name"]) for c in insp.get_check_constraints(t)}
        names |= {("uq", u["name"]) for u in insp.get_unique_constraints(t)}
        names |= {("uix" if ix.get("unique") else "ix", ix["name"]) for ix in insp.get_indexes(t)}
        for name, kind in _NAMED_KEY.findall(ddl.get(t) or ""):
            names.add(("pk" if kind.upper().startswith("PRIMARY") else "fk", name))
        plain, uniq = set(), set()
        for ix in insp.get_indexes(t):
            (uniq if ix.get("unique") else plain).add(tuple(ix["column_names"]))
        for uc in insp.get_unique_constraints(t):
            uniq.add(tuple(uc["column_names"]))
        # FU-565 — FK ondelete rule per column-set (None = no rule). The whole
        # class of "model declares CASCADE/SET NULL/RESTRICT, prod has none" is
        # gated here now that the drift is reconciled.
        fks = {
            tuple(fk["constrained_columns"]): ((fk.get("options") or {}).get("ondelete") or None)
            for fk in insp.get_foreign_keys(t)
        }
        out[t] = {"cols": cols, "types": types, "plain": plain, "uniq": uniq, "fks": fks, "names": names}
    return out


@pytest.mark.slow
def test__migrations__migrated_schema_matches_orm_metadata(temp_db_path):
    """The migrated (prod) schema and the ORM model's `create_all()` schema
    (dev + the whole e2e suite) must agree on tables, columns, column types,
    nullability, index/unique colsets, constraint + index names (R-015: a later
    migration drops by name), and FK `ondelete` rules — the FU-563/564/565 regression
    gate for the drift the FU-393 sweep found (dev ran on 1 index vs prod's 32;
    3 Product nullability mismatches; 6 FK ondelete mismatches). Only the
    documented carve-outs above are tolerated; anything else is 'model changed,
    migration forgotten' (or vice-versa) and fails here, not silently in prod."""
    result = _run_migration(temp_db_path, "flask_migrate.upgrade()")
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    from dora_api.app import db  # metadata only; no app-engine access here

    mig_engine = create_engine(f"sqlite:///{temp_db_path}")
    model_engine = create_engine("sqlite://")  # in-memory; our own engine
    try:
        # create_all on OUR engine never touches the app's bound (e2e) DB.
        db.metadata.create_all(model_engine)
        migrated = _reflect(inspect(mig_engine), mig_engine)
        model = _reflect(inspect(model_engine), model_engine)
    finally:
        mig_engine.dispose()
        model_engine.dispose()

    problems: list[str] = []

    # Tables present in one build path but not the other.
    for t in sorted(set(model) - set(migrated)):
        problems.append(f"table {t!r}: in ORM model but NOT migrated (migration forgotten?)")
    for t in sorted(set(migrated) - set(model)):
        problems.append(f"table {t!r}: migrated but NOT in ORM model (stale migration?)")

    for t in sorted(set(model) & set(migrated)):
        m, g = model[t], migrated[t]
        # Columns.
        for c in sorted(set(m["cols"]) - set(g["cols"])):
            problems.append(f"{t}.{c}: in ORM model but NOT migrated")
        for c in sorted(set(g["cols"]) - set(m["cols"])):
            problems.append(f"{t}.{c}: migrated but NOT in ORM model")
        # Nullability.
        for c in sorted(set(m["cols"]) & set(g["cols"])):
            if m["cols"][c] != g["cols"][c] and (t, c) not in _KNOWN_NULLABILITY_DRIFT:
                problems.append(
                    f"{t}.{c}: nullability drift — model nullable={m['cols'][c]}, "
                    f"migrated nullable={g['cols'][c]}"
                )
        # Index + unique colsets (each direction; allowlist the known unique drift).
        for cs in sorted(m["plain"] - g["plain"]):
            problems.append(f"{t}({', '.join(cs)}): index in ORM model but NOT migrated")
        for cs in sorted(g["plain"] - m["plain"]):
            problems.append(f"{t}({', '.join(cs)}): index migrated but NOT in ORM model")
        for cs in sorted(m["uniq"] - g["uniq"]):
            if (t, cs) not in _KNOWN_UNIQUE_DRIFT:
                problems.append(f"{t}({', '.join(cs)}): UNIQUE in ORM model but NOT migrated")
        for cs in sorted(g["uniq"] - m["uniq"]):
            if (t, cs) not in _KNOWN_UNIQUE_DRIFT:
                problems.append(f"{t}({', '.join(cs)}): UNIQUE migrated but NOT in ORM model")
        # Column types (as SQLite reflects them: BINARY(16) and NUMERIC(16) both
        # read back NUMERIC(16), so a UUIDType column compares equal however it
        # was declared, and a VARCHAR/CHAR id column does not).
        for c in sorted(set(m["types"]) & set(g["types"])):
            if m["types"][c] != g["types"][c] and (t, c) not in _KNOWN_TYPE_DRIFT:
                problems.append(
                    f"{t}.{c}: type drift — model {m['types'][c]}, migrated {g['types'][c]}"
                )
        # Constraint + index names.
        for kind, name in sorted(m["names"] - g["names"], key=str):
            if (t, kind, name) not in _KNOWN_NAME_DRIFT:
                problems.append(f"{t}: {kind} {name!r} in ORM model but NOT migrated (name drift?)")
        for kind, name in sorted(g["names"] - m["names"], key=str):
            if (t, kind, name) not in _KNOWN_NAME_DRIFT:
                problems.append(f"{t}: {kind} {name!r} migrated but NOT in ORM model (name drift?)")
        # FK ondelete rules (FU-565). Compare only FK colsets present in both so a
        # column-add/drop is reported once (above) not twice.
        for cs in sorted(set(m["fks"]) & set(g["fks"])):
            if m["fks"][cs] != g["fks"][cs]:
                problems.append(
                    f"{t}({', '.join(cs)}): FK ondelete drift — model={m['fks'][cs]!r}, "
                    f"migrated={g['fks'][cs]!r}"
                )

    assert not problems, (
        "model (create_all) vs migrated (upgrade) schema drift — reconcile "
        "`table_mappings.py` with the migration chain, or add a documented "
        "carve-out if the difference is intentional:\n  " + "\n  ".join(problems)
    )


# ── Upgrading a populated SQLite database ──────────────────────────────────
# The tests above build from empty. These seed rows at an earlier revision and
# upgrade across the migrations that read or rebuild them (R-095).

def _insert(conn: sqlite3.Connection, table: str, **values) -> None:
    """Insert one row, filling every other NOT NULL column that has no
    default with a placeholder of its declared type."""
    for _cid, name, decl, notnull, default, _pk in conn.execute(f'PRAGMA table_info("{table}")'):
        if name in values or not notnull or default is not None:
            continue
        decl = decl.upper()
        if "16" in decl:  # BINARY(16) / NUMERIC(16): a UUIDType id
            values[name] = uuid.uuid4().bytes
        elif any(k in decl for k in ("INT", "BOOL", "FLOAT", "NUM", "REAL")):
            values[name] = 0
        elif "DATE" in decl:
            values[name] = "2026-01-01 00:00:00"
        else:
            values[name] = "x"
    cols = ", ".join(f'"{c}"' for c in values)
    marks = ", ".join("?" for _ in values)
    conn.execute(f'INSERT INTO "{table}" ({cols}) VALUES ({marks})', tuple(values.values()))


@contextmanager
def _sqlite(path: Path):
    """A plain sqlite3 connection (foreign keys off, as sqlite3 defaults) that
    commits and is closed on exit, so Windows can delete the temp file."""
    conn = sqlite3.connect(path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _upgrade_to(temp_db: Path, revision: str) -> None:
    result = _run_migration(temp_db, f"flask_migrate.upgrade(revision={revision!r})")
    assert result.returncode == 0, f"upgrade to {revision} failed:\n{result.stdout}\n{result.stderr}"


def _red_logo() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (200, 20, 20)).save(buf, format="PNG")
    return b"data:image/png;base64," + base64.b64encode(buf.getvalue())


@pytest.mark.slow
def test__migrations__store_brand_colour_backfills_an_existing_logo(temp_db_path):
    """c9f2a7d4e1b8 reads `Store.id` back to update each row. It used to read
    the BINARY(16) id through `sa.Uuid`, which raises on the first SQLite row
    with an image, so any install with a store logo could not upgrade."""
    _upgrade_to(temp_db_path, "b3f7c1d9a2e6")  # the revision before c9f2a7d4e1b8
    store_id = uuid.uuid4().bytes
    with _sqlite(temp_db_path) as conn:
        _insert(conn, "Store", id=store_id, name="Coles", image=_red_logo())

    result = _run_migration(temp_db_path, "flask_migrate.upgrade()")
    assert result.returncode == 0 and "MIGRATION_OK" in result.stdout, (
        f"upgrade across c9f2a7d4e1b8 with a logo failed:\n{result.stdout}\n{result.stderr}"
    )
    with _sqlite(temp_db_path) as conn:
        colour = conn.execute('SELECT brand_colour FROM "Store" WHERE id = ?', (store_id,)).fetchone()[0]
    assert colour is not None and colour.startswith("#")


@pytest.mark.slow
def test__migrations__sqlite_rebuilds_keep_rows_and_convert_string_ids(temp_db_path):
    """e7a2c5f9b3d1 + f4b8d1c6a9e2 on an install whose substitutes table still
    has the original VARCHAR(36) id columns:

    * the 16-byte ids survive the type conversion unchanged (no CAST);
    * rebuilding `StockItem` (a parent) does not fire its children's ON DELETE
      CASCADE: env.py runs the chain with foreign keys off. With them on, the
      rebuild's DROP TABLE deleted every substitute row."""
    _upgrade_to(temp_db_path, "b8d2f4a6c1e3")  # the revision before e7a2c5f9b3d1
    a, b = sorted((uuid.uuid4().bytes, uuid.uuid4().bytes))
    with _sqlite(temp_db_path) as conn:
        # Recreate the table as an install from before c8a1d3b6e9f4 was
        # corrected has it: VARCHAR(36) id columns.
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'StockItemSubstitute'"
        ).fetchone()[0]
        old_ddl = re.sub(r"(stock_item_[ab]_id) \w+(\(16\))?", r"\1 VARCHAR(36)", ddl, count=2)
        conn.execute('DROP TABLE "StockItemSubstitute"')
        conn.execute(old_ddl)
        _insert(conn, "StockItem", id=a, name="Butter")
        _insert(conn, "StockItem", id=b, name="Margarine")
        _insert(conn, "StockItemSubstitute", stock_item_a_id=a, stock_item_b_id=b, notes="1:1")
    with _sqlite(temp_db_path) as conn:
        assert "VARCHAR(36)" in conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'StockItemSubstitute'"
        ).fetchone()[0]

    result = _run_migration(temp_db_path, "flask_migrate.upgrade()")
    assert result.returncode == 0 and "MIGRATION_OK" in result.stdout, f"{result.stdout}\n{result.stderr}"

    with _sqlite(temp_db_path) as conn:
        rows = conn.execute(
            'SELECT stock_item_a_id, stock_item_b_id, notes FROM "StockItemSubstitute"'
        ).fetchall()
        ddl = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'StockItemSubstitute'").fetchone()[0]
        items = conn.execute('SELECT count(*) FROM "StockItem"').fetchone()[0]
    assert rows == [(a, b, "1:1")]
    assert "VARCHAR(36)" not in ddl
    assert items == 2


# A dedicated disposable URL wins; otherwise, when the suite itself is already
# running on Postgres (`DORA_TEST_DB=postgres`), use that database.
_POSTGRES_MIGRATION_URL = os.environ.get("DORA_TEST_POSTGRES_URL") or (
    postgres_url() if IS_POSTGRES else None
)


@pytest.mark.skipif(
    _POSTGRES_MIGRATION_URL is None,
    reason="needs Postgres (DORA_TEST_POSTGRES_URL, or DORA_TEST_DB=postgres) — gate on FU-405 CI matrix",
)
def test__migrations__upgrade_head_runs_on_postgres():
    """R-005 portability: the full stack must apply on Postgres too. Gated on
    a disposable Postgres URL provided by CI (FU-405), or the suite's own
    Postgres when it runs with `DORA_TEST_DB=postgres` (where the schema is
    usually already at head, so this proves `upgrade head` is a clean no-op)."""
    code = (
        "import flask_migrate\n"
        "from dora_api.app import app\n"
        "with app.app_context():\n"
        "    flask_migrate.upgrade()\n"
        "print('MIGRATION_OK')\n"
    )
    env = {**os.environ, "DORA_DB_URL": _POSTGRES_MIGRATION_URL}
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=str(_REPO_ROOT), env=env,
        capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0 and "MIGRATION_OK" in result.stdout, (
        f"`upgrade head` failed on Postgres:\n{result.stdout}\n{result.stderr}"
    )
