"""End-to-end coverage for the audit log (I2 round B)."""
import time

import requests


AUDIT_URL = "http://localhost:5170/api/audit/events"
STOCK_GROUPS_URL = "http://localhost:5170/api/stock-groups"


def _list(**params) -> dict:
    response = requests.get(AUDIT_URL, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test__audit__listing_requires_admin(api):
    # The seeded "dora" account that conftest logs in as IS admin per
    # the first-user-is-admin convention. Hitting the endpoint should
    # succeed; this also verifies routing + DTO shape.
    body = _list(size=1)
    assert "items" in body and "total" in body


def test__audit__mutating_route_emits_event(api):
    # Pick a route guaranteed to mutate something — stock-groups create
    # uses a unique-by-name guard, so a uuid-suffixed name is safe.
    name = f"audit-probe-{int(time.time() * 1000)}"
    create_response = requests.post(STOCK_GROUPS_URL, json={"name": name})
    assert create_response.status_code in (200, 201), create_response.text
    request_id = create_response.headers.get("X-Request-Id")
    assert request_id, "middleware must echo X-Request-Id"

    # Audit row should be queryable by request_id.
    rows = _list(request_id=request_id)["items"]
    assert rows, f"expected at least one audit row for request_id={request_id}"
    actions = {r["action"] for r in rows}
    # The action is derived from the endpoint name `create_stock_group`
    # → `stock_group.created`.
    assert any("stock_group" in a for a in actions), actions


def test__audit__failed_login_emits_warn_event(api):
    fresh = requests.Session()
    fresh.post(
        "http://localhost:5170/api/auth/login",
        json={"username": "definitely-not-a-real-user", "password": "x"},
    )
    rows = _list(action="auth.login.failed", size=5)["items"]
    assert rows, "expected at least one auth.login.failed audit row"
    assert all(r["severity"] == "warn" for r in rows)


def test__audit__scrub_drops_password_keys(api):
    # Submit a client-log entry with a password-shaped key; the audit
    # row's payload should redact it.
    requests.post(
        "http://localhost:5170/api/client-logs",
        json={
            "level": "error",
            "message": "scrub probe",
            "context": {"password": "should-be-gone", "other": "ok"},
        },
    )
    rows = _list(action="client.error", size=5)["items"]
    assert rows, "expected at least one client.error audit row"
    payloads = [r["payload"] for r in rows]
    # The payload includes the outer message + context dict (scrubbed).
    relevant = next(
        (p for p in payloads if isinstance(p, dict) and p.get("message") == "scrub probe"),
        None,
    )
    assert relevant is not None, payloads
    ctx = relevant.get("context") or {}
    assert ctx.get("password") == "***redacted***", ctx
    assert ctx.get("other") == "ok"


def test__audit__get_returns_single_event(api):
    body = _list(size=1)
    if not body["items"]:
        return  # Empty install — nothing to fetch.
    event_id = body["items"][0]["audit_event_id"]
    detail = requests.get(f"{AUDIT_URL}/{event_id}").json()
    assert detail["audit_event_id"] == event_id


def test__audit_retention__deletes_rows_older_than_cutoff(api):
    """The retention helper unit-tests in isolation; here we exercise
    end-to-end that a forcibly-aged row is deleted by the prune call.
    """
    from datetime import datetime, timedelta, timezone
    import os
    from uuid import uuid4
    from sqlalchemy import insert, select

    from dora_api.app import app, db
    from dora_api.features.audit.prune_audit_events import prune_audit_events

    # Force a generous-but-finite retention window so we don't depend
    # on what the env says.
    os.environ["DORA_AUDIT_RETENTION_DAYS"] = "30"

    with app.app_context():
        table = db.metadata.tables["AuditEvent"]
        ancient = uuid4()
        db.session.execute(
            insert(table).values(
                id=ancient,
                occurred_at=datetime.now(timezone.utc) - timedelta(days=400),
                source="system",
                action="test.retention",
                severity="info",
            ),
        )
        db.session.commit()

    deleted = prune_audit_events()
    assert deleted >= 1

    with app.app_context():
        table = db.metadata.tables["AuditEvent"]
        gone = db.session.execute(
            select(table).where(table.c.id == ancient),
        ).first()
        assert gone is None
