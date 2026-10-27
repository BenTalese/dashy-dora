"""POST /api/auth/me/password — change the signed-in user's password.

Separate endpoint (instead of accepting `password` on `PATCH /auth/me`) so
the contract is unambiguous: changing a password requires the *current*
password as proof-of-possession, and the response is intentionally empty.

A1: bumps password_changed_at (invalidates other-device sessions via the
session-staleness check in get_me), keeps the current session alive by
re-stamping its pwd_v marker, fires a confirmation email, and audits.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from flask import session
from pydantic import BaseModel, ConfigDict, Field
from werkzeug.security import check_password_hash

from dora_api.domain.entities.audit_event import SEVERITY_AUDIT
from dora_api.domain.entities.user import User
from dora_api.features.auth.register_user import (
    SESSION_PWD_V_KEY, SESSION_USER_ID_KEY,
)
from dora_api.features.routers import AUTH_ROUTER
from dora_api.infrastructure.api_response import (
    business_rule_violation,
    no_content,
    unauthorized,
    validation_failed,
)
from dora_api.infrastructure.audit import emit as audit_emit
from dora_api.infrastructure.auth_helpers import hash_password, validate_password
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.email_sender import render_template, send_email
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=1, max_length=255)


@dataclass(slots=True)
class ChangePasswordResponse:
    user_not_found: bool = False
    current_password_wrong: bool = False
    new_password_changed_at: datetime | None = None


class ChangePasswordHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: ChangePasswordRequest, user_id: UUID) -> ChangePasswordResponse:
        _User: User | None = self.repository.get(User).by_id(user_id)
        if _User is None or not _User.password_hash:
            return ChangePasswordResponse(user_not_found=True)
        if not check_password_hash(_User.password_hash, request.current_password):
            return ChangePasswordResponse(current_password_wrong=True)

        now = datetime.now(timezone.utc)
        _User.password_hash = hash_password(request.new_password)
        _User.password_changed_at = now
        self.repository.save_changes()
        return ChangePasswordResponse(new_password_changed_at=now)


@AUTH_ROUTER.route("/me/password", methods=["POST"])
@has_request_body(ChangePasswordRequest)
def change_password():
    _UserIdRaw = session.get(SESSION_USER_ID_KEY)
    if not _UserIdRaw:
        return unauthorized()
    try:
        _UserId = UUID(_UserIdRaw)
    except (ValueError, TypeError):
        session.clear()
        return unauthorized()

    _Request: ChangePasswordRequest = get_request_body()
    pwd_error = validate_password(_Request.new_password)
    if pwd_error:
        return validation_failed({"new_password": [pwd_error]})

    repo = SqlAlchemyRepository()
    _Response = ChangePasswordHandler(repo).handle(_Request, _UserId)

    if _Response.user_not_found:
        session.clear()
        return unauthorized()
    if _Response.current_password_wrong:
        return business_rule_violation("Current password is incorrect.")

    # Keep this device signed in by re-stamping pwd_v; the get_me
    # staleness check will sign out other devices on their next probe.
    if _Response.new_password_changed_at is not None:
        session[SESSION_PWD_V_KEY] = _Response.new_password_changed_at.isoformat()

    # Notification email (best-effort) — same repository as the write.
    user = repo.get(User).by_id(_UserId)
    if user is not None and user.email:
        try:
            send_email(
                to=user.email,
                subject="Your Dashy Dora password was changed",
                html_body=render_template(
                    "password_changed.html",
                    subject="Your Dashy Dora password was changed",
                    username=user.username,
                ),
                text_body=(
                    f"Hi {user.username}, your Dashy Dora password was just changed. "
                    "If this wasn't you, contact your admin."
                ),
            )
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("password-changed email send failed: %s", exc)

    audit_emit(
        "auth.password.changed",
        severity=SEVERITY_AUDIT,
        actor_user_id=_UserId,
        entity_type="User", entity_id=_UserId,
    )
    _LOGGER.info("Password changed for user %s", _UserId)
    return no_content()
