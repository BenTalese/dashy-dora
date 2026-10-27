"""C-9.8 — Web-push subscription management.

  GET    /api/alerts/push/vapid-public-key  — application-server key for
                                              `pushManager.subscribe()`.
                                              Returns 404 if VAPID isn't
                                              configured (the SPA treats
                                              that as "channel disabled").
  POST   /api/alerts/push/subscribe         — upsert this browser's
                                              subscription on the user.
                                              Body mirrors the structure
                                              the browser hands back from
                                              `pushManager.subscribe()`.
  POST   /api/alerts/push/unsubscribe       — drop this browser's
                                              subscription (by endpoint).
                                              POST rather than DELETE so
                                              we can carry the endpoint
                                              in the body (DELETE-with-
                                              body isn't supported by
                                              the SPA's http client).

The endpoint URL is the natural key — re-subscribes from the same
browser produce the same value, so the POST is idempotent and only
mutates the `p256dh`/`auth`/`last_seen_at` fields on conflict.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from flask import request
from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.push_subscription import PushSubscription
from dora_api.features.routers import ALERT_ROUTER
from dora_api.infrastructure.api_response import (no_content,
                                                  not_found_detail, ok,
                                                  unauthorized)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.push_sender import vapid_public_key
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.session_user import current_user_id

_LOGGER = logging.getLogger(__name__)


class SubscribeKeys(BaseModel):
    model_config = ConfigDict(extra="forbid")
    p256dh: str = Field(min_length=1, max_length=255)
    auth: str = Field(min_length=1, max_length=64)


class SubscribeRequest(BaseModel):
    """Mirror of the JS `PushSubscription.toJSON()` shape so the SPA can
    forward the value verbatim — apart from `user_agent` which the SPA
    fills in from `navigator.userAgent`."""
    model_config = ConfigDict(extra="forbid")

    endpoint: str = Field(min_length=1, max_length=500)
    keys: SubscribeKeys
    user_agent: str | None = Field(default=None, max_length=255)


class UnsubscribeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str = Field(min_length=1, max_length=500)


class PushSubscriptionHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def upsert(self, user_id: UUID, payload: SubscribeRequest) -> None:
        """Add or update the subscription keyed by endpoint. If an
        existing row carries a different `user_id` (e.g. the device was
        previously signed in as another user), we **reassign** rather
        than refusing — the natural read of "this browser now belongs to
        user X." Mirrors how cookie-based session login itself works."""
        now = datetime.now(timezone.utc)
        existing = self.repository.get(PushSubscription).one(
            EntityField(PushSubscription, PushSubscription.Fields.ENDPOINT).eq(payload.endpoint)
        )
        if existing is not None:
            existing.user_id = user_id
            existing.p256dh = payload.keys.p256dh
            existing.auth = payload.keys.auth
            existing.user_agent = payload.user_agent
            existing.last_seen_at = now
        else:
            self.repository.add(PushSubscription(
                user_id=user_id,
                endpoint=payload.endpoint,
                p256dh=payload.keys.p256dh,
                auth=payload.keys.auth,
                user_agent=payload.user_agent,
                created_at=now,
                last_seen_at=now,
            ))
        self.repository.save_changes()

    def remove(self, user_id: UUID, endpoint: str) -> bool:
        """Delete the row keyed by (user_id, endpoint). Returns True if
        a row was removed, False if there was nothing to remove (an
        idempotent unsubscribe from a stale client)."""
        row = self.repository.get(PushSubscription).one(
            EntityField(PushSubscription, PushSubscription.Fields.ENDPOINT).eq(endpoint)
            & EntityField(PushSubscription, PushSubscription.Fields.USER_ID).eq(user_id)
        )
        if row is None:
            return False
        self.repository.remove(row)
        self.repository.save_changes()
        return True


@ALERT_ROUTER.route("/push/vapid-public-key", methods=["GET"])
def get_vapid_public_key():
    """The SPA fetches this once before calling `pushManager.subscribe`.
    404 means VAPID isn't configured on this install — the SPA flips
    the toggle into its disabled state with the "ask an admin" caption
    (R-014)."""
    key = vapid_public_key()
    if not key:
        return not_found_detail("Web push is not configured on this install.")
    return ok({"public_key": key})


@ALERT_ROUTER.route("/push/subscribe", methods=["POST"])
@has_request_body(SubscribeRequest)
def subscribe_to_push():
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()
    _Request: SubscribeRequest = get_request_body()
    # `user_agent` is honoured if the SPA sends it; fall back to the
    # request header so we don't lose the breadcrumb on older clients.
    if not _Request.user_agent:
        _Request.user_agent = (request.headers.get("User-Agent") or "")[:255] or None
    PushSubscriptionHandler(SqlAlchemyRepository()).upsert(user_id, _Request)
    _LOGGER.info(
        "Push subscription upserted for user %s (ua=%s)",
        user_id, _Request.user_agent or "?",
    )
    return no_content()


@ALERT_ROUTER.route("/push/unsubscribe", methods=["POST"])
@has_request_body(UnsubscribeRequest)
def unsubscribe_from_push():
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()
    _Request: UnsubscribeRequest = get_request_body()
    removed = PushSubscriptionHandler(SqlAlchemyRepository()).remove(
        user_id, _Request.endpoint,
    )
    _LOGGER.info(
        "Push subscription %s for user %s (endpoint=%s)",
        "removed" if removed else "not-found-no-op",
        user_id, _Request.endpoint[:80],
    )
    return no_content()
