from dataclasses import dataclass
from http.client import (BAD_REQUEST, CREATED, FORBIDDEN, INTERNAL_SERVER_ERROR,
                         NO_CONTENT, NOT_FOUND, OK, UNAUTHORIZED,
                         UNPROCESSABLE_ENTITY)
from typing import Any
from uuid import UUID

from flask import Response, jsonify, url_for


@dataclass
class ErrorEntry:
    """One field-level error. FU-099 — replaces the bare ``str`` that used
    to live inside ``ProblemDetails.errors[field]``. ``msg`` is the
    friendly copy shown to the user; ``code`` is the structured key
    (Pydantic's ``err["type"]`` for validation, ``"domain"`` for our own
    business-rule errors); ``raw`` preserves the raw Pydantic message for
    dev console / log inspection — ``None`` for domain errors authored
    by us (no raw form exists).
    """
    msg: str
    code: str
    raw: str | None = None


@dataclass
class ProblemDetails:
    detail: str
    status: int
    # ``dict[str, list[ErrorEntry]]`` after FU-099 (was ``dict[str, list[str]]``
    # — the helpers below accept either and lift bare strings into
    # ErrorEntry(code="domain", raw=None) so existing call sites in
    # feature code don't need per-site edits).
    errors: dict
    title: str
    type: str


def _lift_errors(
    errors: dict[str, list[str] | list[ErrorEntry]] | None,
    *,
    code: str = "domain",
) -> dict[str, list[ErrorEntry]]:
    """Normalise an errors map to ``dict[str, list[ErrorEntry]]``.

    Domain helpers (``bad_request``, ``business_rule_violation``, etc.)
    take ``dict[str, list[str]]`` for backward compat — every existing
    call site passes plain strings. This function lifts each string into
    an ``ErrorEntry`` so the wire shape is uniform regardless of who
    built the dict. Entries that are already ``ErrorEntry`` instances
    pass through unchanged (the middleware's Pydantic translator builds
    them directly).
    """
    if not errors:
        return {}
    lifted: dict[str, list[ErrorEntry]] = {}
    for field, entries in errors.items():
        out: list[ErrorEntry] = []
        for entry in entries:
            if isinstance(entry, ErrorEntry):
                out.append(entry)
            else:
                out.append(ErrorEntry(msg=str(entry), code=code, raw=None))
        lifted[field] = out
    return lifted


def business_rule_violation(error_message: str) -> Response:
    return unprocessable_entity(ProblemDetails(
        detail = "See errors property for more details.",
        status = UNPROCESSABLE_ENTITY,
        errors = _lift_errors({"": [error_message]}),
        title = "Business rule violation.",
        type = "https://datatracker.ietf.org/doc/html/rfc4918#section-11.2"))


def bad_request(
    title: str,
    detail: str | None = None,
    errors: dict[str, list[str] | list[ErrorEntry]] | None = None,
) -> Response:
    response = jsonify(ProblemDetails(
        detail = detail or "See errors property for more details.",
        errors = _lift_errors(errors),
        status = BAD_REQUEST,
        title = title,
        type = "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1"))
    response.content_type = 'application/problem+json'
    response.status_code = BAD_REQUEST
    return response


def created(
    resource_id: UUID,
    get_route: str,
    id_attribute_name: str,
    body: Any | None = None,
) -> Response:
    response = jsonify(body if body is not None else {'id': resource_id})
    response.status_code = CREATED
    response.headers['location'] = url_for(
        get_route,
        filter=f'{id_attribute_name}:eq:{resource_id}',
        _external=True,
    )
    return response


def entity_existence_failure(entity_name: str, property_in_error: str, id: UUID) -> Response:
    return unprocessable_entity(ProblemDetails(
        detail = "See errors property for more details.",
        errors = _lift_errors({property_in_error: [f"{entity_name} with the ID '{id}' was not found."]}),
        status = UNPROCESSABLE_ENTITY,
        title = "Entity was not found.",
        type = "https://datatracker.ietf.org/doc/html/rfc4918#section-11.2"))


def entity_existence_failures(entity_name: str, property_in_error: str, *ids: UUID) -> Response:
    return unprocessable_entity(ProblemDetails(
        detail = "See errors property for more details.",
        errors = _lift_errors({property_in_error: [f"{entity_name}(s) with the ID(s) '{', '.join(str(id) for id in ids)}' were not found."]}),
        status = UNPROCESSABLE_ENTITY,
        title = "Entity(s) were not found.",
        type = "https://datatracker.ietf.org/doc/html/rfc4918#section-11.2"))


def internal_server_error(error_message: str) -> Response:
    response = jsonify(ProblemDetails(
        detail = error_message,
        errors = {},
        status = INTERNAL_SERVER_ERROR,
        title = "Internal server error.",
        type = "https://datatracker.ietf.org/doc/html/rfc7231#section-6.6.1"))
    response.content_type = 'application/problem+json'
    response.status_code = INTERNAL_SERVER_ERROR
    return response


def no_content() -> Response:
    response = Response(status = NO_CONTENT)
    response.status_code = NO_CONTENT
    return response


def conflict(detail: str) -> Response:
    """409 — the request conflicts with current server state (e.g. a stale
    optimistic action). FU-451 uses it for a swap card that drifted since it
    was fetched."""
    response = jsonify(ProblemDetails(
        detail = detail,
        errors = _lift_errors({"": [detail]}),
        status = 409,
        title = "Conflict.",
        type = "https://datatracker.ietf.org/doc/html/rfc9110#section-15.5.10"))
    response.content_type = 'application/problem+json'
    response.status_code = 409
    return response


def unauthorized(detail: str = "Authentication required.") -> Response:
    response = jsonify(ProblemDetails(
        detail = detail,
        errors = {},
        status = UNAUTHORIZED,
        title = "Unauthenticated.",
        type = "https://datatracker.ietf.org/doc/html/rfc7235#section-3.1"))
    response.content_type = 'application/problem+json'
    response.status_code = UNAUTHORIZED
    return response


def forbidden(detail: str = "You do not have permission to perform this action.") -> Response:
    response = jsonify(ProblemDetails(
        detail = detail,
        errors = {},
        status = FORBIDDEN,
        title = "Forbidden.",
        type = "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.3"))
    response.content_type = 'application/problem+json'
    response.status_code = FORBIDDEN
    return response


def endpoint_not_found():
    """404 for an unknown/retired URL (no matching API endpoint). Plain
    `application/json` (not problem+json) to match what the request middleware
    already returns for no-route paths — shared so the SPA catch-all's
    `/api/...` branch produces the identical body for unmatched GETs (FU-167)
    instead of falling through to the default HTML 404."""
    return jsonify(ProblemDetails(
        detail = "Endpoint was not found.",
        status = NOT_FOUND,
        errors = {},
        title = "Endpoint was not found.",
        type = "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.4")), NOT_FOUND


def not_found(entity_name: str, id: UUID) -> Response:
    response = jsonify(ProblemDetails(
        detail = f"{entity_name} with the ID '{id}' was not found.",
        errors = {},
        status = NOT_FOUND,
        title = "Entity was not found.",
        type = "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.4"))
    response.content_type = 'application/problem+json'
    response.status_code = NOT_FOUND
    return response


def too_many_requests(retry_after: int) -> Response:
    """429 (RFC 6585 §4) with a `Retry-After` header: the one shape every
    rate-limited endpoint answers with."""
    response = jsonify(ProblemDetails(
        detail = f"Too many requests. Try again in {retry_after}s.",
        errors = {},
        status = 429,
        title = "Rate limit exceeded.",
        type = "https://datatracker.ietf.org/doc/html/rfc6585#section-4"))
    response.content_type = 'application/problem+json'
    response.status_code = 429
    response.headers["Retry-After"] = str(max(retry_after, 1))
    return response


def not_found_detail(detail: str) -> Response:
    """404 for something that is not an entity row, such as an install-level
    feature that isn't configured. Same problem+json shape as `not_found`."""
    response = jsonify(ProblemDetails(
        detail = detail,
        errors = {},
        status = NOT_FOUND,
        title = "Not found.",
        type = "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.4"))
    response.content_type = 'application/problem+json'
    response.status_code = NOT_FOUND
    return response


def ok(result: Any) -> Response:
    response = jsonify(result)
    response.status_code = OK
    return response


def paginated(items: list, total: int, page: int, limit: int) -> Response:
    response = jsonify({
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
    })
    response.status_code = OK
    return response


def unprocessable_entity(problem_details: ProblemDetails) -> Response:
    response = jsonify(problem_details)
    response.content_type = 'application/problem+json'
    response.status_code = UNPROCESSABLE_ENTITY
    return response
