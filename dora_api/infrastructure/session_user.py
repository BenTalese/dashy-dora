"""The signed-in user, read from the Flask session.

One parse of `session["user_id"]` for every feature (FU-654): a missing or
malformed value reads as "nobody signed in", never as an exception.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from flask import session

from dora_api.domain.entities.user import User
from dora_api.persistence.aware import as_utc

SESSION_USER_ID_KEY = "user_id"
# Snapshot of `password_changed_at` taken at login; `get_me` compares it so a
# cookie minted before a password change reads as stale (finalisation 15-R14 —
# lived in `auth/register_user.py`, which `middleware` could not import).
SESSION_PWD_V_KEY = "pwd_v"


def current_user_id() -> UUID | None:
    raw = session.get(SESSION_USER_ID_KEY)
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except (ValueError, TypeError):
        return None


def current_user(repository) -> User | None:
    user_id = current_user_id()
    if user_id is None:
        return None
    return repository.get(User).by_id(user_id)


# Why a session stopped being valid. `resolve_session_user` returns one of
# these alongside `None` so the caller can word its 401.
SESSION_MISSING = "missing"
SESSION_STALE = "stale"
SESSION_DEACTIVATED = "deactivated"


def resolve_session_user(repository) -> tuple[User | None, str | None]:
    """The signed-in user, only while the cookie is still good (SEC-4).

    One rule for every authenticated route rather than `/auth/me` alone: the
    row must still exist, be active, and its password must not have changed
    since the cookie was minted (`pwd_v`). A cookie that fails any of those is
    cleared here, so a password change or reset signs out every other device
    on its next request, not only when it next calls `/auth/me`.
    """
    user = current_user(repository)
    if user is None:
        if SESSION_USER_ID_KEY in session:
            session.clear()
        return None, SESSION_MISSING
    if not user.is_active:
        session.clear()
        return None, SESSION_DEACTIVATED
    # Compared as instants, not ISO text (R-098): a naive SQLite value and an
    # aware Postgres one don't order as strings.
    stamped = session.get(SESSION_PWD_V_KEY)
    changed_at = as_utc(user.password_changed_at)
    if changed_at is not None and stamped:
        try:
            minted = as_utc(datetime.fromisoformat(stamped))
        except (ValueError, TypeError):
            minted = None
        if minted is None or minted < changed_at:
            session.clear()
            return None, SESSION_STALE
    return user, None
