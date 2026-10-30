from dora_api.features.auth.register_user import AuthenticatedUserDto
from dora_api.features.routers import AUTH_ROUTER
from dora_api.infrastructure.api_response import ok, unauthorized
from dora_api.infrastructure.session_user import (SESSION_DEACTIVATED,
                                                  resolve_session_user)
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


@AUTH_ROUTER.route("/me")
def get_me():
    # Existence, deactivation and the password-change staleness check are the
    # shared session rule (SEC-4), applied by the middleware to every
    # protected route; this is the same resolver, read for the row itself.
    user, reason = resolve_session_user(SqlAlchemyRepository())
    if user is None:
        if reason == SESSION_DEACTIVATED:
            return unauthorized(
                "This account has been deactivated. Ask an admin to switch it back on."
            )
        return unauthorized()

    from dora_api.features.assistant.providers import get_provider_config
    active_provider = (
        get_provider_config(SqlAlchemyRepository(), user.id, user.llm_provider)
        if user.llm_provider else None
    )
    return ok(AuthenticatedUserDto.from_entity(user, active_provider))
