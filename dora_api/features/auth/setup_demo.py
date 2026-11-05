"""First-setup demo: look around Dora with sample data before creating the
first admin, then clear it out and set up for real (owner ask, 2026-11-06).

POST /api/auth/setup-demo                     (public)
    Only while the install has no users (the same window as /bootstrap-admin)
    and isn't locked to ADMIN_BOOTSTRAP_EMAIL. Writes a marker file, empties
    every table, seeds the curated showcase dataset (`seed_showcase_data`, the
    one `DORA_DEMO_MODE` serves) and signs the browser in as its `demo` user.

POST /api/auth/setup-demo/reset               (signed in as the demo user)
    Only while the demo is active. Drops every table (Alembic's version table
    too) and runs the production migration path from empty, so the install is
    exactly a fresh one again: no users, so the SPA routes to /setup.

"Active" needs the marker file AND the database to agree: the marker exists
and the only user is the showcase's `demo`. The file alone is never enough, so
a marker left behind (a manual wipe and real setup, a backup restored during
the demo, a second admin created, a datastore switch) can't turn the reset on
against real data. A successful /bootstrap-admin also deletes the marker.

Neither runs on a `DORA_DEMO_MODE` install: that is an operator's public demo,
and a reset there would hand any visitor the first-admin setup. The demo also
refuses on an install locked to ADMIN_BOOTSTRAP_EMAIL: it would otherwise hand
an anonymous visitor an admin session the lock exists to prevent.

Why a marker file rather than a column: the demo empties the database twice
(in, then out), so a flag kept only in it would be wiped with everything else.

Why the reset re-runs migrations instead of emptying tables: the migrations
seed default rows (stock levels, recipe vocabularies, meal slots), so "empty
tables" is not what a fresh install looks like; `upgrade()` from empty is (the
path `test_fresh_install_smoke` pins).

Best-effort on a multi-worker deploy: other workers serving mid-reset get
errors until it finishes, and on Postgres the drop waits at most
`_PG_LOCK_TIMEOUT` for other connections' locks. A reset that fails part-way
leaves either the demo or an empty schema; the next boot's `upgrade()` turns
the latter back into a fresh install, and the database check keeps the
leftover marker inert.
"""
import dataclasses
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import session
from flask_migrate import upgrade
from sqlalchemy import MetaData, text

from dora_api.app import db
from dora_api.domain.entities.user import User
from dora_api.features.auth.register_user import AuthenticatedUserDto
from dora_api.features.routers import AUTH_ROUTER
from dora_api.infrastructure.api_response import (forbidden, gone, no_content, ok,
                                                  too_many_requests)
from dora_api.infrastructure.auth_helpers import rate_limit, rate_limit_remaining_seconds
from dora_api.infrastructure.configuration_manager import DORA_CONFIG
from dora_api.infrastructure.session_user import (SESSION_PWD_V_KEY, SESSION_USER_ID_KEY,
                                                  current_user_id)
from dora_api.persistence.field import EntityField
from dora_api.persistence.seed_showcase import seed_showcase_data
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)

_MARKER_NAME = "setup_demo.marker"
DEMO_USERNAME = "demo"
_PG_LOCK_TIMEOUT = "10s"


def _marker() -> Path:
    return DORA_CONFIG.get_data_dir() / _MARKER_NAME


def forget_setup_demo_marker() -> None:
    """Called once a real first admin exists: the demo is over for good."""
    _marker().unlink(missing_ok=True)


def _bootstrap_locked() -> bool:
    return bool((os.environ.get("ADMIN_BOOTSTRAP_EMAIL") or "").strip())


def _demo_user_only() -> User | None:
    """The showcase `demo` user, when it is the database's only user."""
    users = SqlAlchemyRepository().get(User).all()
    if len(users) == 1 and users[0].username == DEMO_USERNAME:
        return users[0]
    return None


def is_setup_demo_available() -> bool:
    """Can /setup offer the demo right now? (No users, not locked, not an
    operator's demo install.)"""
    return (
        not DORA_CONFIG.is_demo_mode_enabled()
        and not _bootstrap_locked()
        and SqlAlchemyRepository().get(User).count() == 0
    )


def is_setup_demo_active() -> bool:
    """True while this install is showing the first-setup demo: the marker
    exists and the database is still the demo's (see the module docstring)."""
    if DORA_CONFIG.is_demo_mode_enabled() or not _marker().exists():
        return False
    return _demo_user_only() is not None


def _empty_every_table() -> None:
    for table in reversed(db.metadata.sorted_tables):
        db.session.execute(table.delete())


def _drop_everything() -> None:
    """Drop every table in the database, including ones the models don't map
    (alembic_version), so `upgrade()` starts from nothing."""
    db.session.remove()
    engine = db.engine
    reflected = MetaData()
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            # Don't hang the request behind another connection's open
            # transaction; fail and leave the demo in place instead.
            conn.execute(text(f"SET LOCAL lock_timeout = '{_PG_LOCK_TIMEOUT}'"))
        reflected.reflect(bind=conn)
        reflected.drop_all(bind=conn)
    engine.dispose()


def _rebuild_fresh_install() -> None:
    _drop_everything()
    upgrade()


@AUTH_ROUTER.route("/setup-demo", methods=["POST"])
def start_setup_demo():
    if not rate_limit("auth.setup_demo", max_per_minute=5):
        return too_many_requests(rate_limit_remaining_seconds("auth.setup_demo", 5))
    if DORA_CONFIG.is_demo_mode_enabled() or _bootstrap_locked():
        return gone("The demo isn't available on this install.", title="Demo unavailable.")
    if SqlAlchemyRepository().get(User).count() != 0:
        return gone("An admin account already exists. Sign in instead.",
                    title="Setup already complete.")

    # Marker first: if seeding dies part-way, the half-built demo is still
    # recognisably the demo's (only `demo` exists) and can be reset.
    _marker().parent.mkdir(parents=True, exist_ok=True)
    _marker().write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    try:
        _empty_every_table()
        seed_showcase_data()  # commits
        demo_user = _demo_user_only()
        if demo_user is None:
            # Someone else's /bootstrap-admin landed while the demo seeded.
            raise RuntimeError("the install gained a user while the demo was seeding")
    except Exception:
        _LOGGER.exception("First-setup demo failed to seed; rebuilding a fresh install.")
        db.session.rollback()
        if SqlAlchemyRepository().get(User).count() == 0 or _demo_user_only() is not None:
            _rebuild_fresh_install()
        forget_setup_demo_marker()
        raise

    session.clear()
    session[SESSION_USER_ID_KEY] = str(demo_user.id)
    session[SESSION_PWD_V_KEY] = (demo_user.password_changed_at or datetime.now(timezone.utc)).isoformat()
    session.permanent = True
    _LOGGER.info("First-setup demo started: showcase data seeded.")

    body = dataclasses.asdict(AuthenticatedUserDto.from_entity(demo_user))
    body["user_id"] = str(body["user_id"])
    return ok(body)


@AUTH_ROUTER.route("/setup-demo/reset", methods=["POST"])
def reset_setup_demo():
    if not rate_limit("auth.setup_demo_reset", max_per_minute=3):
        return too_many_requests(rate_limit_remaining_seconds("auth.setup_demo_reset", 3))
    demo_user = _demo_user_only() if is_setup_demo_active() else None
    if demo_user is None:
        return gone("This install isn't showing the setup demo.", title="Nothing to reset.")
    if current_user_id() != demo_user.id:
        return forbidden("Sign in to the demo to clear it.")

    session.clear()
    _rebuild_fresh_install()
    forget_setup_demo_marker()
    _LOGGER.info("First-setup demo cleared: database rebuilt from migrations.")
    return no_content()
