"""The signed-in user, read from the Flask session.

One parse of `session["user_id"]` for every feature (FU-654): a missing or
malformed value reads as "nobody signed in", never as an exception.
"""
from __future__ import annotations

from uuid import UUID

from flask import session

from dora_api.domain.entities.user import User

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
