"""DELETE /api/users/<user_id> — admin removes another user's account.

Hard-delete of the User row. FK-cascaded tables (PriceAlert, AuthToken,
per-user LLM config) drop with the row automatically. Tables that carry a
plain `user_id` column with no FK constraint — AlertInteraction,
AlertPreference, PushSubscription — are cleaned up explicitly here so
they don't orphan. Household-shared rows survive (RecipeCookEvent's
`cooked_by_user_id` and ShoppingList's `created_by_user_id` FKs are
`ON DELETE SET NULL`, so recipes / lists the user touched keep their
history without a broken foreign key). AuditEvent rows are intentionally
left with their historical `actor_user_id` even after the User is gone —
the audit trail preserves what happened, dangling ref or not.

Guards:
- Refuses to delete the caller (an admin can't self-delete; that path
  belongs to a future self-serve account-close flow if we ever ship one).
- Refuses to delete the last admin, mirroring the "would_remove_last_admin"
  guard on `update_user_as_admin.py`.
"""
import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete

from dora_api.app import db
from dora_api.domain.entities.audit_event import SEVERITY_AUDIT
from dora_api.domain.entities.user import User
from dora_api.features.auth.admin_gate import require_admin
from dora_api.features.routers import USER_ROUTER
from dora_api.features.users.admin_guards import other_usable_admins
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  forbidden, no_content,
                                                  not_found)
from dora_api.infrastructure.audit import emit as audit_emit
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


# Tables that carry a plain `user_id` column with no FK-cascade — we clear
# them explicitly before dropping the User row.
_USER_SCOPED_UNCONSTRAINED_TABLES = (
    "AlertInteraction",
    "AlertPreference",
    "PushSubscription",
)


@dataclass(slots=True)
class AdminDeleteUserResponse:
    user_not_found: bool = False
    would_remove_last_admin: bool = False


class AdminDeleteUserHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, user_id: UUID) -> AdminDeleteUserResponse:
        _Target: User | None = self.repository.get(User).by_id(user_id)
        if _Target is None:
            return AdminDeleteUserResponse(user_not_found=True)

        if _Target.is_admin and other_usable_admins(self.repository, user_id) == 0:
            # "Usable" = active. Counting `is_admin` rows alone let the only
            # *active* admin be deleted while a deactivated one still counted
            # (finalisation 13-R3); the PATCH demote / deactivate guards already
            # applied the active bar — this is the same helper now.
            return AdminDeleteUserResponse(would_remove_last_admin=True)

        for _TableName in _USER_SCOPED_UNCONSTRAINED_TABLES:
            _Table = db.metadata.tables[_TableName]
            db.session.execute(
                delete(_Table).where(_Table.c.user_id == user_id),
            )

        self.repository.remove(_Target)
        self.repository.save_changes()
        return AdminDeleteUserResponse()


@USER_ROUTER.route("<uuid:user_id>", methods=["DELETE"])
def admin_delete_user(user_id: UUID):
    _CallerId, err = require_admin()
    if err is not None:
        return err

    if _CallerId == user_id:
        return forbidden(
            "Refusing to delete your own account. Ask another admin to "
            "remove you, or use a future self-serve account-close flow."
        )

    _Response = AdminDeleteUserHandler(SqlAlchemyRepository()).handle(user_id)

    if _Response.user_not_found:
        return not_found("User", user_id)
    if _Response.would_remove_last_admin:
        return business_rule_violation(
            "Can't delete the last admin. Promote someone else first."
        )

    audit_emit(
        "user.deleted_by_admin",
        severity=SEVERITY_AUDIT,
        actor_user_id=_CallerId,
        entity_type="User", entity_id=user_id,
        payload={},
    )

    _LOGGER.info("Admin %s deleted user %s", _CallerId, user_id)
    return no_content()
