import logging

from flask import session

from dora_api.domain.entities.audit_event import SEVERITY_AUDIT
from dora_api.features.routers import AUTH_ROUTER
from dora_api.infrastructure import csrf
from dora_api.infrastructure.api_response import no_content
from dora_api.infrastructure.audit import emit as audit_emit
from dora_api.infrastructure.session_user import SESSION_USER_ID_KEY, current_user_id

_LOGGER = logging.getLogger(__name__)


@AUTH_ROUTER.route("/logout", methods=["POST"])
def logout():
    _Actor = current_user_id()
    _SignedIn = SESSION_USER_ID_KEY in session
    if _SignedIn:
        # FU-548 — session termination is a security-relevant event, so it's
        # audited like login is. Emitted explicitly HERE (before session.clear
        # wipes the actor), not via the middleware auto-audit — which is why
        # `logout` stays in audit._NO_AUDIT_ENDPOINTS: mirrors login's own
        # auth.* emit and avoids a duplicate, actor-less row.
        audit_emit(
            "auth.logout",
            severity=SEVERITY_AUDIT,
            actor_user_id=_Actor,
            entity_type="User",
            entity_id=_Actor,
        )
    session.clear()
    response = no_content()
    # The CSRF cookie is paired with the session (`csrf.clear_cookie`'s own
    # contract); it used to survive logout (finalisation 15-R4).
    csrf.clear_cookie(response)
    if _SignedIn:
        _LOGGER.info("Logout for user %s", _Actor)
    return response
