"""End-to-end coverage for the audit log (I2 round B)."""
import time

import requests


AUDIT_URL = "http://localhost:5170/api/audit/events"
STOCK_GROUPS_URL = "http://localhost:5170/api/stock-groups"
APP_SETTINGS_URL = "http://localhost:5170/api/app-settings"


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
    # The seed writes no audit rows, so emit one first.
    created = requests.post(
        STOCK_GROUPS_URL, json={"name": f"audit-get-{int(time.time() * 1000)}"},
    )
    assert created.status_code in (200, 201), created.text
    rows = _list(request_id=created.headers["X-Request-Id"])["items"]
    assert rows, "the create must have emitted an audit event"
    event_id = rows[0]["audit_event_id"]
    detail = requests.get(f"{AUDIT_URL}/{event_id}").json()
    assert detail["audit_event_id"] == event_id


def test__prune_audit_events__RowOlderThanConfiguredRetention__IsDeleted(api):
    """End-to-end: a forcibly-aged row is deleted by the prune call, against
    the retention window set in Settings. 100 days old sits inside the 365-day
    fallback, so it only goes if the job really read the 30-day setting (it
    used to resolve it outside the app context and always fall back).
    """
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4
    from sqlalchemy import insert, select

    from dora_api.app import app, db
    from dora_api.features.audit.prune_audit_events import prune_audit_events

    previous = requests.get(APP_SETTINGS_URL).json()["audit_retention_days"]
    patched = requests.patch(APP_SETTINGS_URL, json={"audit_retention_days": 30})
    assert patched.status_code == 200, patched.text
    try:
        with app.app_context():
            table = db.metadata.tables["AuditEvent"]
            aged = uuid4()
            db.session.execute(
                insert(table).values(
                    id=aged,
                    occurred_at=datetime.now(timezone.utc) - timedelta(days=100),
                    source="system",
                    action="test.retention",
                    severity="info",
                ),
            )
            db.session.commit()

        deleted = prune_audit_events()
    finally:
        requests.patch(APP_SETTINGS_URL, json={"audit_retention_days": previous})

    assert deleted >= 1
    with app.app_context():
        table = db.metadata.tables["AuditEvent"]
        gone = db.session.execute(
            select(table).where(table.c.id == aged),
        ).first()
        assert gone is None


def test__audit_events__occurred_at_carries_a_utc_offset(api):
    """QA 2026-10-30 — SQLite hands the instant back naive; serialised without
    the offset the SPA parsed it as local time and the audit log read hours
    off (R-098)."""
    from datetime import datetime
    import uuid as _uuid
    created = requests.post(STOCK_GROUPS_URL, json={"name": f"Audit tz {_uuid.uuid4().hex[:6]}"})
    assert created.status_code in (200, 201), created.text
    body = requests.get(f"{AUDIT_URL}?size=5").json()
    rows = body.get("items") or []
    assert rows, "a write produces an auto-audit event"
    for row in rows:
        parsed = datetime.fromisoformat(row["occurred_at"])
        assert parsed.tzinfo is not None, row["occurred_at"]

