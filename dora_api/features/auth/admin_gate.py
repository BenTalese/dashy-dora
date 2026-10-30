"""Shared admin-gate helper.

Single canonical `require_admin()` for every mutating route that
should be admin-only. Introduced in FU-341 / FU-198 to replace the
three ad-hoc copies (`users/update_user_as_admin.py`,
`audit/get_audit_events.py`, `app_settings/update_app_settings.py`
reusing the first) with one implementation. Keeping the gate here
(rather than importing from a feature module) prevents any single
feature from becoming the informal "auth home".

Returns a `(user_id, error_response)` tuple. `error_response` is
`None` when the caller is an authenticated admin. Callers idiom:

    _, err = require_admin()
    if err is not None:
        return err
"""
from uuid import UUID

from dora_api.infrastructure.session_user import (SESSION_DEACTIVATED,
                                                  resolve_session_user)
from dora_api.infrastructure.api_response import forbidden, unauthorized
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


def require_admin() -> tuple[UUID | None, object]:
    # The shared session rule (SEC-4): missing, deleted, deactivated and
    # stale-after-password-change cookies all fail here exactly as they do
    # in the middleware and `/auth/me`.
    me, reason = resolve_session_user(SqlAlchemyRepository())
    if me is None:
        if reason == SESSION_DEACTIVATED:
            return None, unauthorized(
                "This account has been deactivated. Ask an admin to switch it back on."
            )
        return None, unauthorized()
    if not me.is_admin:
        return None, forbidden("Admin role required.")
    return me.id, None
