from datetime import datetime
from typing import Any
from uuid import UUID

import requests

from tests.db_backend import IS_POSTGRES


def set_money_enabled(enabled: bool) -> None:
    """Flip the install-wide money switch (`AppSetting.money_enabled`).

    FU-816 — the dollar-answering report endpoints refuse with 403 when money
    is off (R-058), and money is **off** on a fresh install, so any test that
    reads one has to turn it on first. Lives here rather than being re-typed
    per file because three e2e modules need it.
    """
    response = requests.patch(
        "http://localhost:5170/api/app-settings",
        json={"money_enabled": enabled},
    )
    assert response.status_code in (200, 204), response.text


# ── Shared response matchers (FU-169 / PROPOSAL_TEST_SUITE_IMPROVEMENTS §C)
# Centralises the two contract shapes every router test re-asserts:
#  - RFC-7807 problem-detail bodies (used for every 4xx / 5xx)
#  - the `{items, total, page, limit}` list envelope
# When the contract moves, one update here replaces ~40 inline dicts. New
# tests should reach for these matchers rather than re-typing the shape.


def assert_problem(
    response,
    status: int,
    *,
    field: str | None = None,
    detail: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Assert ``response`` is an RFC-7807 problem-detail body.

    Checks the status code, ``application/problem+json`` content type, and
    (optionally) that ``errors[field]`` exists and / or ``detail`` / ``title``
    contains the given substring.

    Returns the parsed JSON body so callers can drill deeper without
    re-parsing (``problem = assert_problem(resp, 400, field="name")``).
    """
    assert response.status_code == status, (
        f"expected {status}, got {response.status_code}: {response.text!r}"
    )
    content_type = response.headers.get("Content-Type", "")
    assert content_type.startswith("application/problem+json"), (
        f"expected application/problem+json, got {content_type!r}"
    )
    body = response.json()
    assert isinstance(body, dict), f"problem body must be an object, got {type(body).__name__}"
    if field is not None:
        errors = body.get("errors")
        assert isinstance(errors, dict), (
            f"expected errors dict, got {errors!r}"
        )
        assert field in errors, (
            f"expected field {field!r} in errors, got keys={list(errors)}"
        )
    if detail is not None:
        actual_detail = body.get("detail", "")
        assert detail in actual_detail, (
            f"expected detail to contain {detail!r}, got {actual_detail!r}"
        )
    if title is not None:
        actual_title = body.get("title", "")
        assert title in actual_title, (
            f"expected title to contain {title!r}, got {actual_title!r}"
        )
    return body


def assert_envelope(response, *, expect_total: int | None = None) -> list:
    """Assert ``response`` is a 200 list envelope and return ``items``.

    The list endpoints all return ``{items, total, page, limit}``; this
    matcher centralises the pagination-shape check. Pass ``expect_total``
    to also assert the count.

    Usage::

        items = assert_envelope(resp, expect_total=5)
        assert items[0]["name"] == "Foo"
    """
    assert response.status_code == 200, (
        f"expected 200, got {response.status_code}: {response.text!r}"
    )
    body = response.json()
    assert isinstance(body, dict), f"envelope must be an object, got {type(body).__name__}"
    for key in ("items", "total", "page", "limit"):
        assert key in body, f"envelope missing {key!r}; keys={list(body)}"
    items = body["items"]
    assert isinstance(items, list), f"envelope.items must be a list, got {type(items).__name__}"
    if expect_total is not None:
        assert body["total"] == expect_total, (
            f"expected total={expect_total}, got {body['total']}"
        )
    return items


def is_valid_datetime(value, format=None):
    # the API now serialises datetimes as ISO 8601
    # (`datetime.isoformat()`), which may carry microseconds and/or an offset.
    # With no explicit format, validate via `fromisoformat` (handles those);
    # an explicit `format` still uses strptime for callers that need it.
    try:
        if format is None:
            datetime.fromisoformat(value)
        else:
            datetime.strptime(value, format)
        return True
    except (ValueError, TypeError):
        return False


def is_valid_uuid(value):
    try:
        UUID(value)
        return True
    except ValueError:
        return False


def is_valid_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False


def uuid_bind(value) -> bytes | str:
    """Normalise a UUID (in any shape) to the raw-`text()` bind form the
    active backend's UUIDType column expects.

    Background: `sqlalchemy_utils.UUIDType` stores UUIDs as BINARY(16) on
    SQLite but as native `uuid` on Postgres. A raw `text('... WHERE id =
    :id')` bind bypasses SA's type layer, so the correct Python shape is
    backend-dependent:
      - **SQLite** wants `bytes` — binding `str(uuid)` compares a string
        against a BLOB and silently returns zero rows.
      - **Postgres** wants the canonical string — binding `bytes` raises
        `operator does not exist: uuid = bytea`.
    Tests reaching under the ORM (direct SQL for state assertions or
    targeted state setup) go through this helper so they don't
    re-discover the trap on either backend.
    """
    if isinstance(value, bytes):
        _Uuid = UUID(bytes=value)
    elif isinstance(value, UUID):
        _Uuid = value
    else:
        _Uuid = UUID(str(value))
    return str(_Uuid) if IS_POSTGRES else _Uuid.bytes


def open_registration() -> None:
    """Switch self-serve registration on for this test (SEC-3: off by default).

    Goes through the admin client (`requests` is rebound to the signed-in
    admin by the `api` fixture); the per-test DB rollback closes it again.
    """
    resp = requests.patch(
        "http://localhost:5170/api/app-settings",
        json={"registration_enabled": True},
    )
    assert resp.status_code == 200, resp.text
