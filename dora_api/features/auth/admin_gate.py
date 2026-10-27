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

from flask import session

from dora_api.domain.entities.user import User
from dora_api.infrastructure.session_user import SESSION_USER_ID_KEY
from dora_api.infrastructure.api_response import forbidden, unauthorized
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


def require_admin() -> tuple[UUID | None, object]:
    _UserIdRaw = session.get(SESSION_USER_ID_KEY)
    if not _UserIdRaw:
        return None, unauthorized()
    try:
        _UserId = UUID(_UserIdRaw)
    except (ValueError, TypeError):
        session.clear()
        return None, unauthorized()

    repository = SqlAlchemyRepository()
    me: User | None = repository.get(User).by_id(_UserId)
    if me is None:
        session.clear()
        return None, unauthorized()
    # A deactivated account keeps its cookie until `get_me` next runs, so the
    # admin gate re-checks rather than trusting the session. This closes the
    # admin half only; the general "any authenticated route" half needs the
    # shared session→User resolver tracked as FU-654 (see FU-655).
    if not me.is_active:
        session.clear()
        return None, unauthorized(
            "This account has been deactivated. Ask an admin to switch it back on."
        )
    if not me.is_admin:
        return None, forbidden("Admin role required.")
    return _UserId, None

