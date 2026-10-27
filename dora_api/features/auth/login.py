import logging
from dataclasses import dataclass

from flask import session
from pydantic import BaseModel, ConfigDict, Field
from werkzeug.security import check_password_hash

from dora_api.domain.entities.user import User
from dora_api.features.auth.register_user import (AuthenticatedUserDto,
                                                  SESSION_USER_ID_KEY)
from dora_api.features.routers import AUTH_ROUTER
from dora_api.domain.entities.audit_event import SEVERITY_AUDIT, SEVERITY_WARN
from dora_api.infrastructure.api_response import ok, unauthorized
from dora_api.infrastructure.audit import emit as audit_emit
from dora_api.infrastructure.auth_helpers import (
    rate_limit, rate_limit_remaining_seconds,
)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.api_response import too_many_requests

_LOGGER = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length = 1, max_length = 255)
    password: str = Field(min_length = 1, max_length = 255)


@dataclass(slots=True)
class LoginResponse:
    user: User | None = None
    # Distinct from `user=None`: the credentials were *right*, the account is
    # switched off. Kept separate so the route can say so — at this point the
    # caller has already proved they own the account, so naming the reason
    # leaks nothing and saves them guessing at a password that works.
    deactivated: bool = False


class LoginHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: LoginRequest) -> LoginResponse:
        _UsernameField = EntityField(User, User.Fields.USERNAME)
        _User: User | None = self.repository.get(User).one(_UsernameField.eq(request.username))
        if not _User or not _User.password_hash:
            return LoginResponse(user = None)
        if not check_password_hash(_User.password_hash, request.password):
            return LoginResponse(user = None)
        if not _User.is_active:
            return LoginResponse(user = None, deactivated = True)
        return LoginResponse(user = _User)


@AUTH_ROUTER.route("/login", methods=["POST"])
@has_request_body(LoginRequest)
def login():
    if not rate_limit("auth.login", max_per_minute=5):
        return too_many_requests(rate_limit_remaining_seconds("auth.login", 5))
    _Handler = LoginHandler(SqlAlchemyRepository())
    _Request: LoginRequest = get_request_body()
    _Response = _Handler.handle(_Request)

    if _Response.deactivated:
        _LOGGER.warning(
            f"Login refused for deactivated account '{_Request.username}'"
        )
        audit_emit(
            "auth.login.deactivated",
            severity=SEVERITY_WARN,
            payload={"username": _Request.username},
        )
        return unauthorized(
            "This account has been deactivated. Ask an admin to switch it back on."
        )

    if _Response.user is None:
        _LOGGER.warning(f"Failed login attempt for username '{_Request.username}'")
        audit_emit(
            "auth.login.failed",
            severity=SEVERITY_WARN,
            payload={"username": _Request.username},
        )
        # Intentionally generic so we don't leak whether the user exists.
        return unauthorized("Invalid username or password.")

    from dora_api.features.auth.register_user import SESSION_PWD_V_KEY
    session.clear()
    session[SESSION_USER_ID_KEY] = str(_Response.user.id)
    # Snapshot the user's current password_changed_at into the session
    # so get_me can detect a stale cookie after a reset.
    if _Response.user.password_changed_at is not None:
        session[SESSION_PWD_V_KEY] = _Response.user.password_changed_at.isoformat()
    session.permanent = True

    _LOGGER.info(f"Login success for {_Response.user.username} ({_Response.user.id})")
    audit_emit(
        "auth.login.success",
        severity=SEVERITY_AUDIT,
        actor_user_id=_Response.user.id,
        entity_type="User",
        entity_id=_Response.user.id,
        payload={"username": _Response.user.username},
    )
    from dora_api.features.assistant.providers import get_provider_config
    _ActiveProvider = (
        get_provider_config(
            SqlAlchemyRepository(), _Response.user.id, _Response.user.llm_provider,
        )
        if _Response.user.llm_provider else None
    )
    return ok(AuthenticatedUserDto.from_entity(_Response.user, _ActiveProvider))
