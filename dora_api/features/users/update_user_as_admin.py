"""Admin-only user maintenance endpoints.

`PATCH /api/users/<user_id>` lets an admin change another user's username,
email, deals subscription, or admin flag. Password resets live on a
dedicated route (see reset_user_password.py) so they don't share a payload
with general edits.
"""
import logging
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.user import User
from dora_api.features.auth.admin_gate import require_admin
from dora_api.features.routers import USER_ROUTER
from dora_api.features.users.admin_guards import other_usable_admins
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  no_content, not_found)
from dora_api.infrastructure.auth_helpers import is_valid_email, normalise_email
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)



class AdminUpdateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    is_admin: bool | None = None
    # Deactivate-instead-of-delete (owner, 2026-08-17).
    is_active: bool | None = None
    deals_email_enabled: bool | None = None
    # Settings rebuild Phase 4 (§2.9) — admins can clear a problematic user's
    # profile picture. The "set one, for completeness" half (`image`) had no
    # caller and went in finalisation 13-R15; people set their own picture on
    # `/auth/me`.
    clear_image: bool = False


@dataclass(slots=True)
class AdminUpdateUserResponse:
    user_not_found: bool = False
    username_taken: bool = False
    email_taken: bool = False
    email_invalid: bool = False
    would_remove_last_admin: bool = False
    would_deactivate_self: bool = False
    would_deactivate_last_admin: bool = False


class AdminUpdateUserHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def _other_usable_admins(self, user_id: UUID) -> int:
        """How many admins *other than this one* could still sign in — the
        shared `admin_guards.other_usable_admins`, which the DELETE guard
        reads too, so demote / deactivate / delete apply one bar."""
        return other_usable_admins(self.repository, user_id)

    def handle(
        self,
        request: AdminUpdateUserRequest,
        user_id: UUID,
        caller_id: UUID | None = None,
    ) -> AdminUpdateUserResponse:
        _Target: User | None = self.repository.get(User).by_id(user_id)
        if _Target is None:
            return AdminUpdateUserResponse(user_not_found=True)

        _SetFields = request.model_fields_set

        if "username" in _SetFields and request.username is not None:
            _UsernameField = EntityField(User, User.Fields.USERNAME)
            _SameName: User | None = (
                self.repository.get(User).one(_UsernameField.eq(request.username))
            )
            # str(...) both sides — raw str path param vs UUID id (FU-528
            # family): a bare `!=` made an admin re-submitting a user's own
            # username 422 as "taken".
            if _SameName and str(_SameName.id) != str(user_id):
                return AdminUpdateUserResponse(username_taken=True)
            _Target.username = request.username

        if "email" in _SetFields:
            # Same rules as self-service `/auth/me` and admin create: normalise,
            # validate, keep addresses unique, and drop the verified mark on a
            # change (a new address has not been confirmed). This branch used
            # to assign the raw string with none of the four (finalisation
            # 13-R2).
            _Email = normalise_email(request.email)
            if _Email is not None and not is_valid_email(_Email):
                return AdminUpdateUserResponse(email_invalid=True)
            if _Email is not None:
                _SameEmail = self.repository.get(User).one(
                    EntityField(User, User.Fields.EMAIL).eq(_Email)
                )
                if _SameEmail and str(_SameEmail.id) != str(user_id):
                    return AdminUpdateUserResponse(email_taken=True)
            if _Email != _Target.email:
                _Target.email_verified = False
            _Target.email = _Email

        if "is_admin" in _SetFields and request.is_admin is not None:
            # Guard against demoting the install's last usable admin — see
            # `_other_usable_admins` for why "usable" (active) is the bar.
            if not request.is_admin and _Target.is_admin:
                if self._other_usable_admins(user_id) == 0:
                    return AdminUpdateUserResponse(would_remove_last_admin=True)
            _Target.is_admin = request.is_admin

        if "is_active" in _SetFields and request.is_active is not None:
            if not request.is_active:
                # Deactivating yourself would sign you out mid-action with no
                # way back in (get_me kills the cookie on the next probe), so
                # it's refused outright rather than confirmed — the same shape
                # as the existing "you can't delete your own account" rule.
                if caller_id is not None and str(caller_id) == str(user_id):
                    return AdminUpdateUserResponse(would_deactivate_self=True)
                if _Target.is_admin and self._other_usable_admins(user_id) == 0:
                    return AdminUpdateUserResponse(would_deactivate_last_admin=True)
            _Target.is_active = request.is_active

        if "deals_email_enabled" in _SetFields and request.deals_email_enabled is not None:
            _Target.deals_email_enabled = request.deals_email_enabled

        # Settings rebuild Phase 4 — "Remove picture" from the Users overflow.
        if request.clear_image:
            _Target.image = None

        self.repository.save_changes()
        return AdminUpdateUserResponse()


@USER_ROUTER.route("<uuid:user_id>", methods=["PATCH"])
@has_request_body(AdminUpdateUserRequest)
def admin_update_user(user_id: UUID):
    _CallerId, err = require_admin()
    if err is not None:
        return err

    _Request: AdminUpdateUserRequest = get_request_body()
    _Response = AdminUpdateUserHandler(SqlAlchemyRepository()).handle(
        _Request, user_id, _CallerId,
    )

    if _Response.user_not_found:
        return not_found("User", user_id)
    if _Response.username_taken:
        return business_rule_violation(
            f"Username '{_Request.username}' is already taken."
        )
    if _Response.email_invalid:
        return business_rule_violation("That doesn't look like a valid email address.")
    if _Response.email_taken:
        return business_rule_violation(
            f"Email '{_Request.email}' is already used by another account."
        )
    if _Response.would_remove_last_admin:
        return business_rule_violation(
            "Can't remove the last admin. Promote someone else first."
        )
    if _Response.would_deactivate_self:
        return business_rule_violation(
            "You can't deactivate your own account."
        )
    if _Response.would_deactivate_last_admin:
        return business_rule_violation(
            "Can't deactivate the last admin. Promote someone else first."
        )

    _LOGGER.info("Admin updated user %s", user_id)
    return no_content()
