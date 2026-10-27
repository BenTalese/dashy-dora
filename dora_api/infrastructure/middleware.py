import logging
import os
import time
from uuid import uuid4

from flask import Blueprint, current_app, g, request, session
from pydantic import ValidationError

from dora_api.infrastructure.api_response import (ErrorEntry, bad_request,
                                                  endpoint_not_found,
                                                  forbidden,
                                                  unauthorized)
from dora_api.infrastructure.profile import env_flag, is_production
from dora_api.infrastructure.session_user import SESSION_USER_ID_KEY
from dora_api.infrastructure.audit import auto_audit_after_request
from dora_api.infrastructure.csrf import (csrf_check_passed, ensure_cookie,
                                          request_is_mutating,
                                          request_under_api)
from dora_api.infrastructure.decorators import REQUEST_BODYS_BY_ENDPOINT
from dora_api.infrastructure.error_translation import translate_pydantic_error
from dora_api.infrastructure.log_context import (reset_context, set_request_id,
                                                 set_user_id)


_LOGGER = logging.getLogger(__name__)
MIDDLEWARE = Blueprint('MIDDLEWARE', __name__)


# Endpoints that don't require an authenticated session. Anything under /api/
# that isn't listed here is gated by the require_auth hook below.
PUBLIC_ENDPOINTS = frozenset({
    "login",
    "register_user",
    # first-admin bootstrap. `bootstrap_required` is the cheap
    # GET the SPA hits on cold-start to decide login-vs-setup; the POST
    # creates the first admin and 410s once any user exists.
    "bootstrap_required",
    "bootstrap_admin",
    # pre-auth capability probe (login page reads it to decide whether to
    # render "Forgot password?" — gated on outbound email being real).
    "get_auth_capabilities",
    "health_check",            # health probes must not require auth (used by container orchestrators)
    "submit_client_log",       # the SPA may need to ship errors before login completes
    # ── A1 out-of-band auth flows; reached from email links + login screen ──
    "verify_email",
    "resend_verification",
    "forgot_password",
    "reset_password",
    # the ingestion endpoint authenticates via `Authorization:
    # Bearer <key>` against IngestionSource, not the dora_session
    # cookie. Skipping the session gate here lets the bearer-check inside
    # the handler own auth. The admin CRUD over keys is NOT listed —
    # that page stays session+admin-gated.
    "submit_ingestion_batch",
    # C-10.5 / FU-422: read-side link-status lookup. Same bearer auth
    # as the batch endpoint; session cookie is not involved.
    "ingest_link_status",
    # The companion's "unsave" (products program PF-4). Bearer-authed front
    # door onto the same DeleteProductHandler the SPA's session-authed
    # DELETE /api/products/<id> uses — one behaviour, two auth schemes.
    "ingest_delete_product",
    # PF-7: the saved-product list a source pulls before refreshing offers.
    # Bearer-authed like its siblings.
    "ingest_list_products",
    # Dora's stores and their logos, for a source that maps its own scrapers
    # onto them (2026-10-15). Bearer-authed like its siblings.
    "ingest_list_stores",
    "ingest_store_image",
})


@MIDDLEWARE.before_app_request
def handle_incoming_request():
    # ── Logging context ──────────────────────────────────────────────
    # X-Request-Id from the caller is honoured (round-trips across our
    # axios client, which generates one per call) so client + server
    # log lines correlate. Falls back to a fresh uuid4 for ad-hoc curls.
    incoming = request.headers.get("X-Request-Id")
    request_id = incoming.strip() if incoming else uuid4().hex
    set_request_id(request_id)
    set_user_id(session.get(SESSION_USER_ID_KEY))
    g.request_started_at = time.perf_counter()
    g.request_id = request_id

    if _LOGGER.isEnabledFor(logging.INFO):
        _LOGGER.info(
            "→ %s %s",
            request.method,
            request.path,
        )
    if _LOGGER.isEnabledFor(logging.DEBUG):
        audit_incoming_request()

    # CORS preflights are anonymous by design — flask-cors handles them and
    # adds the appropriate Access-Control-* headers on the response. Let the
    # request through without auth-gating or body parsing.
    if request.method.upper() == "OPTIONS":
        return

    if not request.endpoint:
        return endpoint_not_found()

    _EndpointName = request.endpoint.split(".")[-1]

    # Auth gate runs before body deserialisation so unauthenticated callers
    # don't waste cycles having their payloads parsed.
    _AuthFailure = require_auth_if_protected(_EndpointName)
    if _AuthFailure is not None:
        return _AuthFailure

    # CSRF double-submit check. Runs after the auth gate so we
    # only enforce on session-authenticated, mutating, non-public
    # endpoints. The cookie itself is minted in `attach_csrf_cookie` on
    # the response, so cold-load GETs seed the pair before the SPA
    # tries its first POST.
    _CsrfFailure = require_csrf_if_protected(_EndpointName)
    if _CsrfFailure is not None:
        return _CsrfFailure

    if request.method.upper() in ["POST", "PATCH", "PUT", "DELETE"]:
        return deserialise_web_request(_EndpointName)

    return


@MIDDLEWARE.after_app_request
def emit_audit_event(response):
    """Best-effort audit emit for mutating routes. Runs before
    `stamp_request_id` so the audit row already has `request_id` from
    contextvars. Never raises."""
    return auto_audit_after_request(response)


@MIDDLEWARE.after_app_request
def attach_csrf_cookie(response):
    """FU-197 — seed the `dora_csrf` cookie on any response when the
    incoming request didn't carry one. This makes the cookie present
    after the SPA's first GET so the follow-up POST has both halves of
    the double-submit pair. Secure flag mirrors the session cookie
    (`SESSION_COOKIE_SECURE`) so dev (HTTP) and prod (HTTPS) behave
    consistently."""
    if not request_under_api():
        return response
    secure = bool(current_app.config.get("SESSION_COOKIE_SECURE", False))
    ensure_cookie(response, secure=secure)
    return response


#  Content-Security-Policy: permissive-but-honest starter policy.
#
#  - `default-src 'self'` fences everything to same-origin by default.
#  - `script-src` needs `'unsafe-inline'` and `'unsafe-eval'` for now: Quasar's
#    runtime uses eval-style paths and Vue injects small inline scripts on the
#    HTML shell. Tightening these requires either a nonce-per-response scheme
#    or a build-time change; either is a bigger job than the header itself.
#  - `style-src 'unsafe-inline'` covers Vue's scoped-style injection and
#    Quasar's dynamic theming.
#  - `img-src` allows `data:` (our base64 image blobs) and `blob:` (fresh
#    uploads) alongside `https:` for legitimate external product/store images.
#  - `connect-src` allows `https:` so a self-hosted install can point the
#    assistant at an external LLM without a header edit.
#  - `frame-ancestors 'none'` is the CSP-native companion to
#    `X-Frame-Options: DENY` — modern browsers prefer this one but the legacy
#    header is still sent for older UA coverage.
_DEFAULT_CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: https:",
    # No `media-src` meant `default-src 'self'` governed audio, which blocked
    # `audioUnlock.ts`'s silent `data:` WAV — the iOS/WKWebView autoplay primer
    # speech output relies on — on every load (FU-853 / finalisation 04-R2).
    # `blob:` is Piper's synthesised clip; the timer chime is WebAudio.
    "media-src 'self' blob: data:",
    "font-src 'self' data:",
    "connect-src 'self' https:",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
])
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer-when-downgrade",
    "Content-Security-Policy": _DEFAULT_CSP,
}


@MIDDLEWARE.after_app_request
def attach_security_headers(response):
    """FU-459 — app-wide security headers.

    Runs on every response (API + any static served through Flask) but
    yields to headers already set upstream: if a reverse proxy owns the
    CSP, we don't stomp on it. `DORA_DISABLE_SECURITY_HEADERS=1` opts
    out entirely (escape hatch when a specific proxy/CDN configuration
    conflicts — not for production use)."""
    if os.environ.get("DORA_DISABLE_SECURITY_HEADERS", "").lower() in ("1", "true", "yes"):
        return response
    for name, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


@MIDDLEWARE.after_app_request
def stamp_request_id(response):
    """Echo X-Request-Id on every response so the SPA can correlate its
    own log lines with the server's, and log the request-end summary."""
    started = getattr(g, "request_started_at", None)
    request_id = getattr(g, "request_id", None)
    if request_id:
        response.headers["X-Request-Id"] = request_id
    if started is not None and _LOGGER.isEnabledFor(logging.INFO):
        duration_ms = (time.perf_counter() - started) * 1000.0
        _LOGGER.info(
            "← %d %s %s (%.1fms)",
            response.status_code,
            request.method,
            request.path,
            duration_ms,
        )
    return response


@MIDDLEWARE.teardown_app_request
def clear_context(_exc):
    # Reset contextvars so APScheduler / cleanup logs after the request
    # don't get tagged with the previous user's id.
    reset_context()


def require_auth_if_protected(endpoint_name: str):
    """Return an unauthorized response if the endpoint requires a session and
    the caller doesn't have one. Returns None when the request may proceed.
    """
    if not request.path.startswith("/api/"):
        return None
    if endpoint_name in PUBLIC_ENDPOINTS:
        return None
    if SESSION_USER_ID_KEY in session:
        return None
    return unauthorized()


# endpoints exempt from the CSRF double-submit check. Mirrors
# Anything pre-session is exempt, since the cookie may not exist yet. The
# bearer-authenticated ingestion endpoints are *in* PUBLIC_ENDPOINTS (public
# by session, bearer-checked in-handler) — a Bearer token can't be replayed
# CSRF-style because the browser never holds it ambient — so this is the
# same set, not a superset (finalisation 15-R13).
CSRF_EXEMPT_ENDPOINTS = PUBLIC_ENDPOINTS


def require_csrf_if_protected(endpoint_name: str):
    """Return a 403 if the request is a mutating call on a protected
    endpoint and the CSRF cookie / header pair is missing or mismatched.
    Returns None when the request may proceed."""
    if not request_under_api():
        return None
    if not request_is_mutating():
        return None
    if endpoint_name in CSRF_EXEMPT_ENDPOINTS:
        return None
    # dev-only escape hatch for ad-hoc curl / shell drivers
    # that can't easily echo the cookie as a header. Refused outside
    # the development profile so it cannot weaken a production deploy.
    if env_flag("DORA_CSRF_DISABLED") and not is_production():
        return None
    if csrf_check_passed():
        return None
    return forbidden(
        "Missing or invalid CSRF token. Reload the page and try again."
    )


# Body keys whose values never reach a log line. Matched case-insensitively
# as substrings so `password`, `new_password`, `current_password`,
# `smtp_password`, `api_key`, `vapid_private_key`, `token`, `secret` and the
# raw ingestion `key` are all covered without listing every field. The DEBUG
# body dump below is the dev default (`logging_setup`: DEBUG when `debug=True`)
# and used to print `/auth/login` bodies — username *and* password — into the
# rotating log file (finalisation 15-R2).
_SENSITIVE_KEY_FRAGMENTS = ("password", "secret", "token", "key", "authorization")
REDACTED = "***"


def redact_sensitive(value):
    """A copy of `value` with every secret-looking key's value replaced by
    `***`, recursing into nested dicts and lists. Non-container values pass
    through unchanged."""
    if isinstance(value, dict):
        return {
            k: (REDACTED if isinstance(k, str) and any(f in k.lower() for f in _SENSITIVE_KEY_FRAGMENTS)
                else redact_sensitive(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(v) for v in value]
    return value


def audit_incoming_request():
    _LOGGER.debug(
        "Incoming request | method=%s path=%s endpoint=%s ip=%s",
        request.method,
        request.path,
        request.endpoint,
        request.remote_addr,
    )
    if request.is_json and _LOGGER.isEnabledFor(logging.DEBUG):
        _LOGGER.debug("body: %s", redact_sensitive(request.get_json(silent=True)))


def deserialise_web_request(request_endpoint: str):
    # Endpoints without a registered schema accept no body (e.g. action POSTs).
    if request_endpoint not in REQUEST_BODYS_BY_ENDPOINT:
        return

    _RequestBodySchema = REQUEST_BODYS_BY_ENDPOINT[request_endpoint]
    try:
        _Parsed = _RequestBodySchema.model_validate(request.get_json(silent=True) or {})
    except ValidationError as e:
        # each Pydantic error is lifted into an ErrorEntry carrying
        # the friendly translation (msg), the structured code (Pydantic's
        # err["type"]), and the raw developer-facing string (raw). The client
        # renders msg; devs see code + raw in console.warn.
        _Errors: dict[str, list[ErrorEntry]] = {}
        for err in e.errors():
            field = ".".join(str(loc) for loc in err["loc"])
            code = err["type"]
            _Errors.setdefault(field, []).append(ErrorEntry(
                msg=translate_pydantic_error(code),
                code=code,
                raw=err["msg"],
            ))
        return bad_request("Malformed request.", errors=_Errors)

    setattr(request, "request_body", _Parsed)
