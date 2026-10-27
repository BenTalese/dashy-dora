"""Settings rebuild Phase 4 (§2.9) — user profile-picture route.

  GET /api/users/<user_id>/image

Returns the user's profile picture bytes, or 404 when unset. Images are
stored as data-URL strings on the entity (`data:image/png;base64,…`) so the
SPA can point a plain `<img src>` at this route without inlining megabytes of
base64 into every user JSON. Same pattern as the store / stock-item / recipe
image routes.

Auth: any authenticated user can fetch any user's picture (used by the menu
bar, the Account header, and the admin Users list). The session middleware
already gates the route; we don't add a per-user check — the StockItem /
Store image endpoints set the same precedent.
"""
from dora_api.domain.entities.user import User
from dora_api.features.routers import USER_ROUTER
from dora_api.infrastructure.api_response import not_found
from dora_api.infrastructure.data_url import data_url_response
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


@USER_ROUTER.route("<uuid:user_id>/image", methods=["GET"])
def get_user_image(user_id):
    repository = SqlAlchemyRepository()
    user = repository.get(User).by_id(user_id)
    if user is None:
        return not_found(User.__name__, user_id)
    return data_url_response(user.image, lambda: not_found(User.__name__, user_id))
