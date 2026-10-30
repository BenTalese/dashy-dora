import io
import shutil
from pathlib import Path
from urllib.parse import urlsplit

from tests.db_backend import IS_POSTGRES, configure_db_env

# Pick the DB backend and pin the env BEFORE importing `dora_api.app` so
# `DoraConfig.get_db_connection_string()` resolves it at import. SQLite (a temp
# file) is the default — zero external deps + per-process isolation; set
# `DORA_TEST_DB=postgres` to run the same suite against the dedicated
# `dora_test` Postgres (FU-520 item 1) to catch SQLite-vs-Postgres divergence.
#
# NOTE (SQLite branch) — `configure_db_env()` hard-sets `DORA_DB_PATH` (not
# setdefault) so a `.env` `DORA_DB_PATH=./data/dora.dev.db` can't leak into the
# suite and clobber the developer's actual dev DB. Confirmed hazard 2026-07-09.
configure_db_env()

_REPO_ROOT = Path(__file__).resolve().parents[3]
(_REPO_ROOT / "data").mkdir(parents=True, exist_ok=True)
_TEST_DB_PATH = _REPO_ROOT / "data" / "dora.test.db"
_SNAPSHOT_DB_PATH = _REPO_ROOT / "data" / "dora.test.snapshot.db"

import pytest
import requests
from sqlalchemy import select

from dora_api.app import app, db
from dora_api.startup import startup

# ── Postgres per-test isolation snapshot ──────────────────────────────
# SQLite restores by copying the seeded .db file; Postgres can't. Instead we
# capture every seeded row once (after the seed) and restore per-test by
# DELETE-all (reverse FK order) + bulk reinsert. This restores the WHOLE DB
# regardless of which connection wrote — so, like the file copy, it also
# captures the reconcile sweep's out-of-session `db.engine.begin()` writes.
# DELETE+reinsert (~30-40 ms) is ~6x cheaper than TRUNCATE on 59 tables.
_PG_SNAPSHOT: dict[str, list[dict]] = {}


def _pg_capture_snapshot() -> None:
    with app.app_context():
        snapshot = {}
        with db.engine.connect() as conn:
            for table in db.metadata.sorted_tables:
                snapshot[table.name] = [
                    dict(row) for row in conn.execute(select(table)).mappings().all()
                ]
    _PG_SNAPSHOT.clear()
    _PG_SNAPSHOT.update(snapshot)


def _pg_restore_snapshot() -> None:
    with app.app_context():
        db.session.rollback()
        db.session.remove()
        tables = list(db.metadata.sorted_tables)
        with db.engine.begin() as conn:
            for table in reversed(tables):  # children before parents (FK-safe)
                conn.execute(table.delete())
            for table in tables:
                rows = _PG_SNAPSHOT.get(table.name)
                if rows:
                    conn.execute(table.insert(), rows)


@pytest.fixture(scope="session", autouse=True)
def api():
    # the e2e suite used to boot a real werkzeug HTTP server in a
    # thread and drive it with `requests` over the loopback socket — ~2.7s
    # per test (real TCP + the Windows `localhost` IPv6-fallback penalty),
    # ~13.5 min for the suite. We now dispatch in-process through Flask's
    # test client. The test bodies are untouched: they still call bare
    # `requests.get/post/...` (authenticated) and `requests.Session()` (a
    # fresh anonymous jar); we rebind both to thin adapters over
    # `app.test_client()`. No socket, no network stack.
    startup(is_test_env=True)

    # FU-169 Phase 2 — snapshot the freshly seeded DB so the per-test rollback
    # fixture below can restore the baseline cheaply.
    if IS_POSTGRES:
        # FU-520 — capture the seeded rows in memory (no file to copy).
        _pg_capture_snapshot()
    else:
        # SQLite: snapshot the .db file. Closing the engine pool first ensures
        # every buffered page is flushed to disk before the copy. `db.engine`
        # is a Flask-SQLAlchemy property tied to `current_app`, so we need the
        # app context around the dispose call.
        with app.app_context():
            db.engine.dispose()
        shutil.copyfile(_TEST_DB_PATH, _SNAPSHOT_DB_PATH)

    # Authenticated client backing the module-level `requests.*` helpers.
    # The test client keeps its own cookie jar, so every subsequent call
    # carries the `dora_session` cookie — mirroring the old logged-in
    # `requests.Session`.
    client = app.test_client()
    _LoginResponse = client.post(
        "/api/auth/login",
        json={"username": "dora", "password": "dora"},
    )
    assert _LoginResponse.status_code == 200, (
        f"Test login failed ({_LoginResponse.status_code}): "
        f"{_LoginResponse.get_data(as_text=True)}"
    )

    _Originals = {
        name: getattr(requests, name)
        for name in ("get", "post", "put", "patch", "delete")
    }
    for name in _Originals:
        setattr(requests, name, _adapt(client, name))

    # `requests.Session()` → a brand-new (anonymous) test client. Tests that
    # call `_fresh_session()` want an isolated cookie jar; a fresh test
    # client is exactly that.
    _OriginalSession = requests.Session
    requests.Session = lambda: _TestClientSession(app.test_client())

    api_client = _TestClientSession(client)

    try:
        yield api_client
    finally:
        for name, fn in _Originals.items():
            setattr(requests, name, fn)
        requests.Session = _OriginalSession


@pytest.fixture(autouse=True)
def _clear_rate_limit_buckets():
    """Every test starts with empty in-memory rate-limit buckets.

    The limiter (`auth_helpers._buckets`) is process-lifetime and keyed per
    IP — and every test-client request comes from the same 127.0.0.1 — so
    without this, auth calls accumulate across tests and a later test's 400
    or 401 can become a 429 depending on run order. A test that pins the
    limit builds its own burst inside the test.
    """
    from dora_api.infrastructure import auth_helpers
    with auth_helpers._buckets_lock:
        auth_helpers._buckets.clear()
        auth_helpers._bucket_windows.clear()
    yield


@pytest.fixture(autouse=True)
def _db_rollback():
    """FU-169 Phase 2 — per-test DB rollback via SQLite file snapshot.

    Kills the order-coupling the FU-166 hand-patches worked around: each
    test now starts from the freshly seeded baseline, no test can see
    another's writes. The reconcile sweep's `db.engine.begin()` (the one
    place in the codebase that opens its own connection outside `db.session`)
    is included in the isolation because we're restoring the whole file,
    not fighting individual transactions.

    Shape:
      1. Test runs against the live DB.
      2. Teardown: rollback+close the ORM session (any pending writes
         drop cleanly), dispose the engine pool (release file handles),
         copy the seeded snapshot over the live DB.
      3. The next test-client call opens fresh connections against the
         restored file.

    Cost: SQLite file copy is ~1-3 ms for the seed DB. Cheap enough that
    even 900+ tests only add a few seconds. The Postgres branch (FU-520) is
    DELETE-all + reinsert (~30-40 ms) — same whole-DB restore semantics.
    """
    yield
    if IS_POSTGRES:
        _pg_restore_snapshot()
        return
    with app.app_context():
        db.session.rollback()
        db.session.remove()
        db.engine.dispose()
    shutil.copyfile(_SNAPSHOT_DB_PATH, _TEST_DB_PATH)


def _to_path(url: str) -> str:
    """Strip scheme + host from a full test URL, leaving the path (and query
    string) the test client expects. Bodies still write absolute URLs like
    `http://localhost:5170/api/...`; the test client only wants `/api/...`."""
    parts = urlsplit(url)
    if not parts.scheme and not parts.netloc:
        return url  # already a bare path
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"
    return path


_MUTATING = frozenset({"post", "put", "patch", "delete"})


def _adapt(client, method_name: str):
    """Wrap one test-client verb so it accepts `requests`-style args and
    returns a `requests`-shaped response."""
    client_method = getattr(client, method_name)

    def _call(url: str, **kwargs):
        # `requests` uses `params=` for the query string; the werkzeug test
        # client uses `query_string=`. `json=`/`headers=` pass through as-is.
        if "params" in kwargs:
            kwargs["query_string"] = kwargs.pop("params")
        if "files" in kwargs:
            _translate_multipart(kwargs)
        # auto-attach the double-submit CSRF header from the
        # client's cookie jar so existing tests don't need to know CSRF
        # exists. The browser equivalent lives in axiosHttpClient.ts;
        # this mirrors it for the in-process test client. Tests that
        # want to exercise the CSRF-missing path can pass a `headers=`
        # dict that explicitly sets `X-CSRF-Token: ''` (or omit via a
        # bespoke helper).
        if method_name.lower() in _MUTATING:
            csrf_cookie = _read_csrf_cookie(client)
            if csrf_cookie:
                headers = dict(kwargs.pop("headers", None) or {})
                headers.setdefault("X-CSRF-Token", csrf_cookie)
                kwargs["headers"] = headers
        return _TestClientResponse(client_method(_to_path(url), **kwargs))

    return _call


def _read_csrf_cookie(client) -> str | None:
    """Pull the `dora_csrf` value out of the test client's cookie jar.
    Werkzeug's API surface for this has shifted across versions — handle
    both the modern `_cookies` dict (Werkzeug 3) and the older list."""
    jar = getattr(client, "_cookies", None)
    if jar is None:
        return None
    if isinstance(jar, dict):
        # Werkzeug ≥ 3: dict keyed by (domain, path, name) → cookie obj
        for key, cookie in jar.items():
            name = key[2] if isinstance(key, tuple) and len(key) >= 3 else getattr(cookie, "key", None)
            if name == "dora_csrf":
                value = getattr(cookie, "value", None)
                if value:
                    return value
        return None
    # Older Werkzeug: iterable of Cookie objects with .name + .value
    for cookie in jar:
        if getattr(cookie, "name", None) == "dora_csrf":
            return getattr(cookie, "value", None) or None
    return None


def _translate_multipart(kwargs: dict) -> None:
    """Fold `requests`-style `files=`/`data=` into the single `data` dict the
    werkzeug test client expects. requests file specs are
    `(filename, content[, content_type])`; werkzeug wants
    `(stream, filename[, content_type])` — different order, stream-first."""
    files = kwargs.pop("files")
    data = dict(kwargs.pop("data", None) or {})
    for field, spec in files.items():
        if isinstance(spec, (tuple, list)):
            filename, content = spec[0], spec[1]
            content_type = spec[2] if len(spec) > 2 else None
        else:
            filename, content, content_type = None, spec, None
        if hasattr(content, "read"):
            stream = content
        elif isinstance(content, bytes):
            stream = io.BytesIO(content)
        else:
            stream = io.BytesIO(str(content).encode())
        if content_type:
            data[field] = (stream, filename, content_type)
        else:
            data[field] = (stream, filename)
    kwargs["data"] = data
    kwargs["content_type"] = "multipart/form-data"


class _TestClientResponse:
    """Adapts a werkzeug `TestResponse` to the slice of the `requests.Response`
    API the suite touches: `.status_code`, `.headers`, `.text`, `.json()`."""

    def __init__(self, werkzeug_response):
        self._response = werkzeug_response

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def headers(self):
        return self._response.headers

    @property
    def text(self) -> str:
        return self._response.get_data(as_text=True)

    @property
    def content(self) -> bytes:
        return self._response.get_data()

    def json(self):
        return self._response.get_json()

    def raise_for_status(self) -> None:
        """Mirror `requests.Response.raise_for_status`. Some backup/restore
        tests call this to fail fast on the download-attachment path;
        without it the calls hit `AttributeError` before the assertion
        that matters."""
        if 400 <= self._response.status_code < 600:
            raise RuntimeError(
                f"HTTP {self._response.status_code}: "
                f"{self._response.get_data(as_text=True)[:200]}"
            )


class _TestClientSession:
    """Stand-in for `requests.Session` backed by a single test client (its own
    cookie jar). Exposes the verb methods the suite uses."""

    def __init__(self, client):
        self._client = client

    def get(self, url, **kwargs):
        return _adapt(self._client, "get")(url, **kwargs)

    def post(self, url, **kwargs):
        return _adapt(self._client, "post")(url, **kwargs)

    def put(self, url, **kwargs):
        return _adapt(self._client, "put")(url, **kwargs)

    def patch(self, url, **kwargs):
        return _adapt(self._client, "patch")(url, **kwargs)

    def delete(self, url, **kwargs):
        return _adapt(self._client, "delete")(url, **kwargs)
