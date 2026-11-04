"""Test-suite DB backend selector (FU-520 item 1).

The suite defaults to a throwaway **SQLite** file — zero external deps, the
fast local loop. Set `DORA_TEST_DB=postgres` to run the *same* suite against
the `compose.dev.yml` **Postgres** instead, which is what catches the class of
SQLite-vs-Postgres divergence that SQLite silently masks (tz-naive vs aware
datetimes, str vs isoformat ordering, stricter typing — cf. FU-526 / FU-533).

Both conftests (`tests/conftest.py` for the domain-unit layer and
`tests/e2e/dora_api/conftest.py` for the e2e layer) import `configure_db_env()`
and call it *before* importing `dora_api.app`, so the DB URL is resolved once,
consistently, at import time.

Postgres safety: the suite runs `drop_all()`/`DELETE`-restore, so it must NEVER
point at the dev `dora` database. `configure_db_env()` targets a dedicated
`dora_test` database (override the whole URL via `DORA_TEST_PG_URL`).
"""
import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

# FU-952: two pytest runs at once used to share `data/dora.test.db` and corrupt
# each other. `DORA_TEST_DB_FILE` gives a run its own file (and snapshot).
SQLITE_TEST_DB = _REPO_ROOT / "data" / os.environ.get("DORA_TEST_DB_FILE", "dora.test.db")
SQLITE_SNAPSHOT_DB = SQLITE_TEST_DB.with_name(SQLITE_TEST_DB.stem + ".snapshot.db")

# Dedicated test database on the compose.dev.yml Postgres. A separate DB from
# the dev `dora` one on purpose — the suite is destructive (drop_all + seed).
_DEFAULT_PG_URL = "postgresql+psycopg://dora:dora@localhost:5432/dora_test"


def _requested_backend() -> str:
    return (os.environ.get("DORA_TEST_DB") or "sqlite").strip().lower()


IS_POSTGRES = _requested_backend() in ("postgres", "postgresql", "pg")


def postgres_url() -> str:
    return os.environ.get("DORA_TEST_PG_URL") or _DEFAULT_PG_URL


def configure_db_env() -> None:
    """Pin the DB env vars for the chosen backend. Idempotent; call before any
    `dora_api.app` import so `DoraConfig.get_db_connection_string()` sees it."""
    if IS_POSTGRES:
        # `DORA_DB_URL` is the full-override branch (resolution step 1), so it
        # wins over any stray `DORA_DB_PATH` from a developer's .env.
        os.environ["DORA_DB_URL"] = postgres_url()
    else:
        (_REPO_ROOT / "data").mkdir(parents=True, exist_ok=True)
        os.environ["DORA_DB_PATH"] = str(SQLITE_TEST_DB)
