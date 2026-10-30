"""POST /api/users — admin creates a user.

Admin-side counterpart to `/auth/register`. Skips the verification-email
flow (the admin implicitly vouches) and mints a one-time password the
admin relays to the user out-of-band — same shape as
`reset_user_password.py`. The new user lands with `email_verified=False`
so a subsequent self-serve verify still works if the admin wants to
require it later; there is no auto-login here (the caller is an admin,
not the freshly-created user).
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from dora_api.domain.entities.audit_event import SEVERITY_AUDIT
from dora_api.domain.entities.user import User
from dora_api.domain.types import EMPTY_UUID
from dora_api.features.auth.admin_gate import require_admin
from dora_api.features.routers import USER_ROUTER
from dora_api.infrastructure.api_response import business_rule_violation, ok, validation_failed
from dora_api.infrastructure.audit import emit as audit_emit
from dora_api.infrastructure.auth_helpers import (hash_password, is_valid_email,
                                                  mint_one_time_password,
                                                  normalise_email,
                                                  validate_password)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)



class AdminCreateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    is_admin: bool = False
    # Owner call 2026-08-17 — the admin can set the password themselves
    # instead of relaying a generated one. Omitted (or empty) keeps the
    # original behaviour: Dora mints a one-time password and hands it back
    # once. Set ⇒ the response carries no password at all, because the
    # admin already knows it and echoing a chosen secret back over the wire
    # buys nothing.
    password: str | None = Field(default=None, max_length=255)

    # Stripped once, here, so the strength check and the stored hash see the
    # same string: validating " Abcdefghij1 " and then storing it stripped let
    # a password through that was only ever checked with its padding.
    @field_validator("password", mode="before")
    @classmethod
    def _strip_password(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if value and not stripped:
            # Whitespace only is a typo, not "mint one for me" (that is an
            # absent / empty password).
            raise ValueError("Password cannot be only spaces.")
        return stripped


@dataclass(slots=True)
class AdminCreateUserResponse:
    new_user_id: UUID = EMPTY_UUID
    new_password: str | None = None
    username_taken: bool = False
    email_taken: bool = False


class AdminCreateUserHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: AdminCreateUserRequest) -> AdminCreateUserResponse:
        username_field = EntityField(User, User.Fields.USERNAME)
        if self.repository.get(User).one(username_field.eq(request.username)):
            return AdminCreateUserResponse(username_taken=True)

        email_norm = normalise_email(request.email)
        if email_norm:
            email_field = EntityField(User, User.Fields.EMAIL)
            existing_by_email = self.repository.get(User).one(email_field.eq(email_norm))
            if existing_by_email is not None:
                return AdminCreateUserResponse(email_taken=True)

        chosen = request.password or ""
        one_time_password = chosen or mint_one_time_password()
        now = datetime.now(timezone.utc)
        new_user = User(
            email=email_norm,
            password_hash=hash_password(one_time_password),
            send_deals_on_day=0,
            username=request.username,
            is_admin=request.is_admin,
            email_verified=False,
            password_changed_at=now,
        )
        self.repository.add(new_user)
        self.repository.save_changes()

        return AdminCreateUserResponse(
            new_user_id=new_user.id,
            # Only echoed when *Dora* invented it — a password the admin
            # typed doesn't need handing back.
            new_password=None if chosen else one_time_password,
        )


@USER_ROUTER.route("", methods=["POST"])
@has_request_body(AdminCreateUserRequest)
def admin_create_user():
    _CallerId, err = require_admin()
    if err is not None:
        return err

    _Request: AdminCreateUserRequest = get_request_body()

    # A chosen password meets exactly the same bar as a self-serve one —
    # `validate_password` is the single authority (R-003), so an admin can't
    # quietly seed accounts weaker than the rules the user is held to.
    if _Request.password:
        pwd_error = validate_password(_Request.password)
        if pwd_error:
            return validation_failed({"password": [pwd_error]})

    if _Request.email is not None and not is_valid_email(_Request.email):
        return validation_failed({"email": ["Please enter a valid email address."]})

    _Response = AdminCreateUserHandler(SqlAlchemyRepository()).handle(_Request)

    if _Response.username_taken:
        return business_rule_violation(
            f"Username '{_Request.username}' is already taken."
        )
    if _Response.email_taken:
        return business_rule_violation(
            "That email address is already registered."
        )

    audit_emit(
        "user.created_by_admin",
        severity=SEVERITY_AUDIT,
        actor_user_id=_CallerId,
        entity_type="User", entity_id=_Response.new_user_id,
        payload={
            "username": _Request.username,
            "is_admin": _Request.is_admin,
        },
    )

    _LOGGER.info(
        "Admin %s created user %s (%s, is_admin=%s)",
        _CallerId, _Request.username, _Response.new_user_id, _Request.is_admin,
    )
    return ok({
        "user_id": str(_Response.new_user_id),
        "new_password": _Response.new_password,
    })
