from datetime import datetime
from uuid import UUID

from flask import session

from dora_api.domain.entities.user import User
from dora_api.features.auth.register_user import (AuthenticatedUserDto,
                                                  SESSION_PWD_V_KEY,
                                                  SESSION_USER_ID_KEY)
from dora_api.features.routers import AUTH_ROUTER
from dora_api.infrastructure.api_response import ok, unauthorized
from dora_api.persistence.aware import as_utc
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository


class GetMeHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, user_id: UUID) -> User | None:
        return self.repository.get(User).by_id(user_id)


@AUTH_ROUTER.route("/me")
def get_me():
    _UserIdRaw = session.get(SESSION_USER_ID_KEY)
    if not _UserIdRaw:
        return unauthorized()
    try:
        _UserId = UUID(_UserIdRaw)
    except (ValueError, TypeError):
        session.clear()
        return unauthorized()

    user = GetMeHandler(SqlAlchemyRepository()).handle(_UserId)
    if user is None:
        # User row disappeared (deleted while logged in). Treat session as invalid.
        session.clear()
        return unauthorized()

    # Deactivated while signed in. Same treatment as a deleted row: the
    # cookie stops working on the next probe, so switching an account off
    # actually signs that person out instead of waiting for the session to
    # lapse. (`login` is the other half of the gate.)
    if not user.is_active:
        session.clear()
        return unauthorized(
            "This account has been deactivated. Ask an admin to switch it back on."
        )

    # A1: session-staleness check. If this user's password was changed
    # after the session was minted, the cookie is invalid — covers reset
    # (which invalidates everyone) and self-serve change-password
    # invalidating other-device sessions.
    # Compared as instants, not ISO text (R-098): a naive SQLite value and an
    # aware Postgres one (rendered in the session's timezone) don't order as
    # strings.
    stamped = session.get(SESSION_PWD_V_KEY)
    changed_at = as_utc(user.password_changed_at)
    if (
        changed_at is not None
        and stamped
        and as_utc(datetime.fromisoformat(stamped)) < changed_at
    ):
        session.clear()
        return unauthorized()

    from dora_api.features.assistant.providers import get_provider_config
    active_provider = (
        get_provider_config(SqlAlchemyRepository(), user.id, user.llm_provider)
        if user.llm_provider else None
    )
    return ok(AuthenticatedUserDto.from_entity(user, active_provider))
