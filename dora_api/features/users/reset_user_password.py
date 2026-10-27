"""POST /api/users/<user_id>/reset-password — admin sets a user's password.

Two modes, one route:

* **Chosen** — the admin sends `{"password": "..."}` and that becomes the
  password. This is the surface's default now (owner call 2026-08-17): the
  admin is usually standing next to the person, and "type it in together"
  beats "copy this 12-char string out of a dialog". The response carries no
  password back — the admin already knows it.
* **Generated** — an empty body still mints a one-time password and returns it
  once, for the "they're not here, I'll message it to them" case. Unchanged.

Either way `password_changed_at` is bumped, which invalidates every existing
session for that user (see the staleness check in `get_me`) — the point of an
admin-driven change is usually that the old credential is compromised or lost.
"""
import logging
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.audit_event import SEVERITY_AUDIT
from dora_api.domain.entities.user import User
from dora_api.features.routers import USER_ROUTER
from dora_api.features.auth.admin_gate import require_admin
from dora_api.infrastructure.api_response import (not_found, ok, ProblemDetails,
                                                  unprocessable_entity)
from dora_api.infrastructure.audit import emit as audit_emit
from dora_api.infrastructure.auth_helpers import hash_password, validate_password
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


# 12-char alphanumeric — readable enough to relay over chat, strong enough
# as a one-time pad until the user changes it themselves.
_RESET_ALPHABET = string.ascii_letters + string.digits


class AdminSetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Absent / empty ⇒ generate one. Every field optional so the historical
    # empty-body call still parses (the middleware validates `{}`).
    password: str | None = Field(default=None, max_length=255)


@dataclass(slots=True)
class ResetPasswordResponse:
    user_not_found: bool = False
    new_password: str | None = None


class ResetUserPasswordHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, user_id: UUID, chosen: str | None = None) -> ResetPasswordResponse:
        _Target: User | None = self.repository.get(User).by_id(user_id)
        if _Target is None:
            return ResetPasswordResponse(user_not_found=True)

        new_password = chosen or "".join(
            secrets.choice(_RESET_ALPHABET) for _ in range(12)
        )
        _Target.password_hash = hash_password(new_password)
        # Sign every existing session for this user out. Was missing before —
        # an admin-driven change is the *most* likely case to want it.
        _Target.password_changed_at = datetime.now(timezone.utc)
        self.repository.save_changes()
        return ResetPasswordResponse(
            new_password=None if chosen else new_password,
        )


@USER_ROUTER.route("<uuid:user_id>/reset-password", methods=["POST"])
@has_request_body(AdminSetPasswordRequest)
def reset_user_password(user_id: UUID):
    _CallerId, err = require_admin()
    if err is not None:
        return err

    _Request: AdminSetPasswordRequest = get_request_body()
    _Chosen = (_Request.password or "").strip() or None

    # Same bar as a self-serve change (`validate_password` is the single
    # authority, R-003) — an admin can't set a password weaker than the one
    # the user would be forced to pick themselves.
    if _Chosen:
        pwd_error = validate_password(_Chosen)
        if pwd_error:
            return unprocessable_entity(ProblemDetails(
                detail="See errors property for more details.",
                errors={"password": [pwd_error]},
                status=422, title="Validation failed.",
                type="https://datatracker.ietf.org/doc/html/rfc4918#section-11.2",
            ))

    _Response = ResetUserPasswordHandler(SqlAlchemyRepository()).handle(
        user_id, _Chosen,
    )
    if _Response.user_not_found:
        return not_found("User", user_id)

    # An admin changing their *own* password here would otherwise log
    # themselves out on the next `/auth/me` (the staleness check compares the
    # session's stamp against `password_changed_at`). Re-stamp this device,
    # exactly as `change_password` does — other devices still get signed out.
    if _CallerId is not None and str(_CallerId) == str(user_id):
        from flask import session
        from dora_api.features.auth.register_user import SESSION_PWD_V_KEY
        _Fresh = SqlAlchemyRepository().get(User).by_id(user_id)
        if _Fresh is not None and _Fresh.password_changed_at is not None:
            session[SESSION_PWD_V_KEY] = _Fresh.password_changed_at.isoformat()

    audit_emit(
        "user.password_set_by_admin",
        severity=SEVERITY_AUDIT,
        actor_user_id=_CallerId,
        entity_type="User", entity_id=user_id,
        payload={"generated": _Chosen is None},
    )
    _LOGGER.info("Admin set password for user %s", user_id)
    return ok({"new_password": _Response.new_password})
