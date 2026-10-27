import logging
from uuid import UUID

from flask import session

from dora_api.domain.entities.audit_event import SEVERITY_AUDIT
from dora_api.features.routers import AUTH_ROUTER
from dora_api.infrastructure.api_response import no_content
from dora_api.infrastructure.audit import emit as audit_emit

_LOGGER = logging.getLogger(__name__)


@AUTH_ROUTER.route("/logout", methods=["POST"])
def logout():
    _UserId = session.get("user_id")
    if _UserId:
        # FU-548 — session termination is a security-relevant event, so it's
        # audited like login is. Emitted explicitly HERE (before session.clear
        # wipes the actor), not via the middleware auto-audit — which is why
        # `logout` stays in audit._NO_AUDIT_ENDPOINTS: mirrors login's own
        # auth.* emit and avoids a duplicate, actor-less row.
        try:
            _Actor = UUID(_UserId)
        except (ValueError, TypeError):
            _Actor = None
        audit_emit(
            "auth.logout",
            severity=SEVERITY_AUDIT,
            actor_user_id=_Actor,
            entity_type="User",
            entity_id=_Actor,
        )
    session.clear()
    if _UserId:
        _LOGGER.info(f"Logout for user {_UserId}")
    return no_content()
