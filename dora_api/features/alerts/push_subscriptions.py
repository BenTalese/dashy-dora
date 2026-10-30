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
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import UUID

from flask import request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from dora_api.domain.entities.push_subscription import PushSubscription
from dora_api.features.routers import ALERT_ROUTER
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  no_content,
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


def _require_https_endpoint(value: str) -> str:
    """The push job POSTs to this URL server-side, so an arbitrary URL is a
    blind SSRF primitive. Every browser push service is https-only."""
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("Push endpoint must be an https:// URL.")
    return value


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

    @field_validator("endpoint")
    @classmethod
    def _https_endpoint(cls, value: str) -> str:
        return _require_https_endpoint(value)


class UnsubscribeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str = Field(min_length=1, max_length=500)


@dataclass(slots=True)
class UpsertPushSubscriptionResponse:
    owned_by_another_user: bool = False


class PushSubscriptionHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def upsert(self, user_id: UUID, payload: SubscribeRequest) -> UpsertPushSubscriptionResponse:
        """Add or update the subscription keyed by endpoint. A row owned by another user moves to the caller only when the
        request also carries that row's exact key pair — i.e. it really is
        the same browser subscription, now signed in as someone else (a
        shared kitchen tablet). Knowing just the endpoint URL is not enough:
        that would let any member silently redirect another user's alerts."""
        now = datetime.now(timezone.utc)
        existing = self.repository.get(PushSubscription).one(
            EntityField(PushSubscription, PushSubscription.Fields.ENDPOINT).eq(payload.endpoint)
        )
        if existing is not None:
            if existing.user_id != user_id and (
                existing.p256dh != payload.keys.p256dh
                or existing.auth != payload.keys.auth
            ):
                return UpsertPushSubscriptionResponse(owned_by_another_user=True)
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
        return UpsertPushSubscriptionResponse()

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
    _Response = PushSubscriptionHandler(SqlAlchemyRepository()).upsert(user_id, _Request)
    if _Response.owned_by_another_user:
        _LOGGER.warning(
            "Push subscribe refused: endpoint already registered to another user "
            "(user=%s, endpoint=%s)", user_id, _Request.endpoint[:80],
        )
        return business_rule_violation(
            "This push endpoint is already registered to another account."
        )
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
