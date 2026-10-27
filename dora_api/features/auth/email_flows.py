"""All the out-of-band auth flows in one file so the shared imports +
rate-limit/scrub boilerplate doesn't get duplicated six times.

Endpoints:
  POST /api/auth/verify-email           — body {token}
  POST /api/auth/resend-verification    — body {email}; anti-enumeration
  POST /api/auth/forgot-password        — body {email}; anti-enumeration
  POST /api/auth/reset-password         — body {token, new_password}

Note: the verified email-change flow (POST /me/email + /email-change/confirm)
was retired 2026-08-12 (FU-620) — the Account page now edits email directly via
PATCH /auth/me. See DORA_FOLLOWUPS_RESOLVED.md FU-620.
"""
import logging
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.audit_event import SEVERITY_AUDIT
from dora_api.domain.entities.auth_token import (
    PURPOSE_RESET_PASSWORD, PURPOSE_VERIFY_EMAIL,
)
from dora_api.domain.entities.user import User
from dora_api.features.routers import AUTH_ROUTER
from dora_api.infrastructure.api_response import (bad_request, no_content, ok,
                                                  too_many_requests, validation_failed)
from dora_api.infrastructure.audit import emit as audit_emit
from dora_api.infrastructure.auth_helpers import (
    RESET_PASSWORD_TTL, VERIFY_EMAIL_TTL,
    build_reset_url, build_verify_url, consume_token, find_active_token,
    hash_password, is_valid_email, issue_token, normalise_email, rate_limit,
    rate_limit_remaining_seconds, revoke_tokens_for_user, try_send,
    validate_password,
)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.email_sender import render_template, send_email
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


_LOGGER = logging.getLogger(__name__)


def _validation_failure(errors: dict):
    return validation_failed(errors)


# ── /verify-email ──────────────────────────────────────────────────────

class VerifyEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=1, max_length=255)


@AUTH_ROUTER.route("/verify-email", methods=["POST"])
@has_request_body(VerifyEmailRequest)
def verify_email():
    body: VerifyEmailRequest = get_request_body()
    if not rate_limit("auth.verify_email", max_per_minute=10):
        return too_many_requests(rate_limit_remaining_seconds("auth.verify_email", 10))

    token_row = find_active_token(body.token, PURPOSE_VERIFY_EMAIL)
    if token_row is None:
        return bad_request("This verification link is invalid or expired.")
    repo = SqlAlchemyRepository()
    user = repo.get(User).by_id(token_row.user_id)
    if user is None:
        return bad_request("This verification link is invalid or expired.")

    user.email_verified = True
    repo.save_changes()
    consume_token(token_row.id)

    audit_emit(
        "auth.email.verified",
        severity=SEVERITY_AUDIT,
        actor_user_id=user.id,
        entity_type="User", entity_id=user.id,
    )
    _LOGGER.info("Email verified for user %s", user.id)
    return ok({"email_verified": True})


# ── /resend-verification ───────────────────────────────────────────────

class ResendVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=1, max_length=255)


@AUTH_ROUTER.route("/resend-verification", methods=["POST"])
@has_request_body(ResendVerificationRequest)
def resend_verification():
    body: ResendVerificationRequest = get_request_body()
    # Brief: "1/min per IP + email". One bucket per email-on-this-IP combo.
    if not rate_limit(f"auth.resend.{normalise_email(body.email)}", max_per_minute=1):
        # Stay anti-enumeration even when rate-limited.
        return no_content()

    email_norm = normalise_email(body.email)
    if not email_norm or not is_valid_email(email_norm):
        return no_content()  # Don't leak that the address is malformed.

    repo = SqlAlchemyRepository()
    user = repo.get(User).one(EntityField(User, User.Fields.EMAIL).eq(email_norm))
    if user is not None and not user.email_verified:
        raw = issue_token(user.id, PURPOSE_VERIFY_EMAIL, VERIFY_EMAIL_TTL)
        try_send(
            send_email,
            to=email_norm,
            subject="Verify your Dashy Dora account",
            html_body=render_template(
                "verify_email.html",
                subject="Verify your Dashy Dora account",
                username=user.username,
                verify_url=build_verify_url(raw),
            ),
            text_body=f"Verify: {build_verify_url(raw)} (expires in 24h)",
        )

    # Always 204 — same response regardless of whether the email exists,
    # is verified, or not.
    return no_content()


# ── /forgot-password ───────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=1, max_length=255)


@AUTH_ROUTER.route("/forgot-password", methods=["POST"])
@has_request_body(ForgotPasswordRequest)
def forgot_password():
    body: ForgotPasswordRequest = get_request_body()
    if not rate_limit(f"auth.forgot.{normalise_email(body.email)}", max_per_minute=5):
        return no_content()

    email_norm = normalise_email(body.email)
    if not email_norm or not is_valid_email(email_norm):
        return no_content()

    repo = SqlAlchemyRepository()
    user = repo.get(User).one(EntityField(User, User.Fields.EMAIL).eq(email_norm))
    if user is not None:
        raw = issue_token(user.id, PURPOSE_RESET_PASSWORD, RESET_PASSWORD_TTL)
        try_send(
            send_email,
            to=email_norm,
            subject="Reset your Dashy Dora password",
            html_body=render_template(
                "reset_password.html",
                subject="Reset your Dashy Dora password",
                username=user.username,
                reset_url=build_reset_url(raw),
            ),
            text_body=f"Reset: {build_reset_url(raw)} (expires in 1h, single-use)",
        )
        audit_emit(
            "auth.password.reset_requested",
            severity=SEVERITY_AUDIT,
            actor_user_id=user.id,
            entity_type="User", entity_id=user.id,
        )
    return no_content()


# ── /reset-password ────────────────────────────────────────────────────

class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=1, max_length=255)


@AUTH_ROUTER.route("/reset-password", methods=["POST"])
@has_request_body(ResetPasswordRequest)
def reset_password():
    body: ResetPasswordRequest = get_request_body()
    if not rate_limit("auth.reset_password", max_per_minute=5):
        return too_many_requests(rate_limit_remaining_seconds("auth.reset_password", 5))

    pwd_error = validate_password(body.new_password)
    if pwd_error:
        return _validation_failure({"new_password": [pwd_error]})

    token_row = find_active_token(body.token, PURPOSE_RESET_PASSWORD)
    if token_row is None:
        return bad_request("This reset link is invalid or expired.")
    repo = SqlAlchemyRepository()
    user = repo.get(User).by_id(token_row.user_id)
    if user is None:
        return bad_request("This reset link is invalid or expired.")

    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    repo.save_changes()
    consume_token(token_row.id)
    # Anyone else holding an unused reset link is now out of luck — that's
    # the intent.
    revoke_tokens_for_user(user.id, PURPOSE_RESET_PASSWORD)

    audit_emit(
        "auth.password.reset",
        severity=SEVERITY_AUDIT,
        actor_user_id=user.id,
        entity_type="User", entity_id=user.id,
    )
    if user.email:
        try_send(
            send_email,
            to=user.email,
            subject="Your Dashy Dora password was reset",
            html_body=render_template(
                "password_changed.html",
                subject="Your Dashy Dora password was reset",
                username=user.username,
            ),
            text_body=f"Hi {user.username}, your Dashy Dora password was just reset.",
        )

    _LOGGER.info("Password reset for user %s", user.id)
    return ok({"password_reset": True})
