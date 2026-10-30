import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from flask import session
from pydantic import BaseModel, ConfigDict, Field
from werkzeug.security import check_password_hash

from dora_api.domain.entities.user import User
from dora_api.features.auth.register_user import (AuthenticatedUserDto,
                                                  SESSION_USER_ID_KEY)
from dora_api.features.assistant.providers import get_provider_config
from dora_api.features.routers import AUTH_ROUTER
from dora_api.infrastructure.session_user import SESSION_PWD_V_KEY
from dora_api.domain.entities.audit_event import SEVERITY_AUDIT, SEVERITY_WARN
from dora_api.infrastructure.api_response import ok, unauthorized
from dora_api.infrastructure.audit import emit as audit_emit
from dora_api.infrastructure.auth_helpers import (
    hash_password, rate_limit, rate_limit_remaining_seconds, rate_limit_reset,
)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.aware import as_utc
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.api_response import too_many_requests

_LOGGER = logging.getLogger(__name__)

# Per-IP burst limit (pre-existing) plus a per-username limit that does NOT
# depend on the client IP — behind a misconfigured proxy, or with a forged
# `X-Forwarded-For` sent straight to the API port, the IP bucket rotates
# freely, so the username bucket is what actually caps password guessing
# against one account (NIST SP 800-63B §5.2.2 throttling).
_LOGIN_IP_SCOPE = "auth.login"
_LOGIN_IP_MAX_PER_MINUTE = 5
_LOGIN_USER_SCOPE = "auth.login.user"
_LOGIN_USER_MAX = 10
_LOGIN_USER_WINDOW_SECONDS = 15 * 60

# Verified against on the unknown-username path so a miss costs the same
# scrypt work as a wrong password — otherwise response timing reveals which
# usernames exist. Random throwaway secret; computed once at import.
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


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
            # Equalise timing with the wrong-password path (anti-enumeration).
            check_password_hash(_DUMMY_PASSWORD_HASH, request.password)
            return LoginResponse(user = None)
        if not check_password_hash(_User.password_hash, request.password):
            return LoginResponse(user = None)
        if not _User.is_active:
            return LoginResponse(user = None, deactivated = True)
        return LoginResponse(user = _User)


@AUTH_ROUTER.route("/login", methods=["POST"])
@has_request_body(LoginRequest)
def login():
    if not rate_limit(_LOGIN_IP_SCOPE, max_per_minute=_LOGIN_IP_MAX_PER_MINUTE):
        return too_many_requests(
            rate_limit_remaining_seconds(_LOGIN_IP_SCOPE, _LOGIN_IP_MAX_PER_MINUTE)
        )
    _Request: LoginRequest = get_request_body()
    _UserSubject = _Request.username.strip().lower()
    # The per-username bucket counts guesses, not a lockout: when it is
    # exhausted the password is still verified and a correct one is admitted,
    # so an attacker spraying someone's username can't lock them out — only
    # wrong passwords are refused early.
    _UserBudgetExhausted = not rate_limit(
        _LOGIN_USER_SCOPE, _LOGIN_USER_MAX, subject=_UserSubject,
        window_seconds=_LOGIN_USER_WINDOW_SECONDS,
    )
    _Handler = LoginHandler(SqlAlchemyRepository())
    _Response = _Handler.handle(_Request)
    if _UserBudgetExhausted and _Response.user is None:
        return too_many_requests(rate_limit_remaining_seconds(
            _LOGIN_USER_SCOPE, _LOGIN_USER_MAX, subject=_UserSubject,
            window_seconds=_LOGIN_USER_WINDOW_SECONDS,
        ))

    if _Response.deactivated:
        _LOGGER.warning("Login refused for deactivated account '%s'", _Request.username)
        audit_emit(
            "auth.login.deactivated",
            severity=SEVERITY_WARN,
            payload={"username": _Request.username},
        )
        return unauthorized(
            "This account has been deactivated. Ask an admin to switch it back on."
        )

    if _Response.user is None:
        _LOGGER.warning("Failed login attempt for username '%s'", _Request.username)
        audit_emit(
            "auth.login.failed",
            severity=SEVERITY_WARN,
            payload={"username": _Request.username},
        )
        # Intentionally generic so we don't leak whether the user exists.
        return unauthorized("Invalid username or password.")

    # Proven password → the per-username budget only tracks failed guesses.
    rate_limit_reset(_LOGIN_USER_SCOPE, subject=_UserSubject)
    session.clear()
    session[SESSION_USER_ID_KEY] = str(_Response.user.id)
    # Snapshot the user's current password_changed_at into the session so
    # get_me can detect a stale cookie after a reset. Always stamped: a user
    # who has never changed their password gets "now", so a later reset still
    # invalidates this session.
    session[SESSION_PWD_V_KEY] = (
        as_utc(_Response.user.password_changed_at) or datetime.now(timezone.utc)
    ).isoformat()
    session.permanent = True

    _LOGGER.info("Login success for %s (%s)", _Response.user.username, _Response.user.id)
    audit_emit(
        "auth.login.success",
        severity=SEVERITY_AUDIT,
        actor_user_id=_Response.user.id,
        entity_type="User",
        entity_id=_Response.user.id,
        payload={"username": _Response.user.username},
    )
    _ActiveProvider = (
        get_provider_config(
            SqlAlchemyRepository(), _Response.user.id, _Response.user.llm_provider,
        )
        if _Response.user.llm_provider else None
    )
    return ok(AuthenticatedUserDto.from_entity(_Response.user, _ActiveProvider))
