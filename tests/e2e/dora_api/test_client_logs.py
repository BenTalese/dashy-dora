"""FU-519 tail — e2e for POST /api/client-logs.

The SPA's `useClientLogger` beacon endpoint. Pins:

  - it's PUBLIC (pre-login error shipping) — anonymous 204,
  - payload validation (level whitelist, required/oversize message,
    extra-field forbid),
  - persistence: warn/error land in the audit table as `client.warning` /
    `client.error`; info lands as `client.info` at INFO severity,
  - payload scrubbing (secret-ish context keys are redacted before the
    audit write),
  - the per-session token-bucket rate limit (10 events / 60 s): overflow
    still returns 204 but stops persisting.

The in-memory rate-limit buckets survive the per-test DB rollback, so an
autouse fixture resets them — otherwise earlier tests would starve later
ones of their 10-event allowance.
"""
import json
from uuid import uuid4

import pytest
import requests

from dora_api.features.client_logs import submit_client_log as _scl
from tests.support import assert_problem

BASE = "http://localhost:5170/api"
CLIENT_LOGS = f"{BASE}/client-logs"
AUDIT_EVENTS = f"{BASE}/audit/events"


@pytest.fixture(autouse=True)
def _reset_rate_limit_buckets():
    """The token buckets are module-level in-memory state — not covered by
    the DB-snapshot rollback. Start each test with a full allowance."""
    _scl._buckets.clear()
    yield
    _scl._buckets.clear()


def _token() -> str:
    return f"zq{uuid4().hex[:8]}"


def _audit_rows(action: str) -> list[dict]:
    """Admin read-back of persisted client events (newest first)."""
    resp = requests.get(AUDIT_EVENTS, params={"action": action, "size": 100})
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


#region ---------------- happy path + auth posture ----------------


def test__submit_client_log__Anonymous__204(api):
    # Public endpoint — a crash before login still ships.
    anon = requests.Session()
    resp = anon.post(CLIENT_LOGS, json={"level": "error", "message": f"{_token()} boom"})
    assert resp.status_code == 204, resp.text


def test__submit_client_log__EveryKnownLevel__204(api):
    for level in ("debug", "info", "warn", "warning", "error"):
        resp = requests.post(CLIENT_LOGS, json={
            "level": level, "message": f"{_token()} level probe",
        })
        assert resp.status_code == 204, f"{level}: {resp.status_code} {resp.text}"


def test__submit_client_log__LevelIsCaseAndWhitespaceInsensitive__204(api):
    resp = requests.post(CLIENT_LOGS, json={
        "level": "  ERROR ", "message": f"{_token()} shouty",
    })
    assert resp.status_code == 204, resp.text


#endregion happy path

#region ---------------- validation ----------------


def test__submit_client_log__UnknownLevel__400WithAllowedList(api):
    resp = requests.post(CLIENT_LOGS, json={"level": "fatal", "message": "x"})
    assert_problem(resp, 400, title="Unknown level 'fatal'")
    # The 400 names the allowed levels so the SPA dev sees the fix inline.
    assert "error" in resp.text and "warn" in resp.text


def test__submit_client_log__MissingFields__400(api):
    assert_problem(requests.post(CLIENT_LOGS, json={"level": "error"}), 400,
                   field="message")
    assert_problem(requests.post(CLIENT_LOGS, json={"message": "no level"}), 400,
                   field="level")


def test__submit_client_log__OversizeMessage__400(api):
    resp = requests.post(CLIENT_LOGS, json={
        "level": "error", "message": "x" * 2049,
    })
    assert_problem(resp, 400, field="message")


def test__submit_client_log__UnknownField__400(api):
    resp = requests.post(CLIENT_LOGS, json={
        "level": "error", "message": "x", "stacktrace": "not-a-field",
    })
    assert_problem(resp, 400, field="stacktrace")


#endregion validation

#region ---------------- audit persistence ----------------


def test__submit_client_log__ErrorLevel__PersistsClientErrorAuditEvent(api):
    marker = f"{_token()} exploded"
    resp = requests.post(CLIENT_LOGS, json={
        "level": "error",
        "message": marker,
        "context": {"route": "/stock", "component": "StockPage"},
    })
    assert resp.status_code == 204, resp.text

    rows = [r for r in _audit_rows("client.error") if r["payload"]["message"] == marker]
    assert len(rows) == 1
    row = rows[0]
    assert row["severity"] == "error"
    assert row["source"] == "web"
    assert row["payload"]["context"] == {"route": "/stock", "component": "StockPage"}


def test__submit_client_log__WarnLevel__PersistsClientWarningAuditEvent(api):
    marker = f"{_token()} wobbled"
    assert requests.post(CLIENT_LOGS, json={
        "level": "warn", "message": marker,
    }).status_code == 204

    rows = [r for r in _audit_rows("client.warning") if r["payload"]["message"] == marker]
    assert len(rows) == 1
    assert rows[0]["severity"] == "warn"


def test__submit_client_log__InfoLevel__PersistsClientInfoAtInfoSeverity(api):
    marker = f"{_token()} noted"
    assert requests.post(CLIENT_LOGS, json={
        "level": "info", "message": marker,
    }).status_code == 204

    rows = [r for r in _audit_rows("client.info") if r["payload"]["message"] == marker]
    assert len(rows) == 1
    assert rows[0]["severity"] == "info"


def test__submit_client_log__SecretishContextKeys__RedactedInAuditPayload(api):
    # The audit scrubber must strip credential-shaped keys before persisting.
    marker = f"{_token()} leaky"
    assert requests.post(CLIENT_LOGS, json={
        "level": "error",
        "message": marker,
        "context": {"auth_token": "super-secret", "route": "/settings"},
    }).status_code == 204

    rows = [r for r in _audit_rows("client.error") if r["payload"]["message"] == marker]
    assert len(rows) == 1
    context = rows[0]["payload"]["context"]
    assert context["auth_token"] == "***redacted***"
    assert context["route"] == "/settings"


#endregion audit persistence

#region ---------------- rate limit ----------------


def test__submit_client_log__EleventhEventInWindow__204ButNotPersisted(api):
    # 10 events per 60 s per session. The overflow response is still a 204
    # (the SPA shouldn't error-loop on its own error shipper) but nothing
    # is logged or persisted for it.
    token = _token()
    for i in range(11):
        resp = requests.post(CLIENT_LOGS, json={
            "level": "error", "message": f"{token} flood {i}",
        })
        assert resp.status_code == 204, f"event {i}: {resp.status_code} {resp.text}"

    rows = [
        r for r in _audit_rows("client.error")
        if r["payload"]["message"].startswith(f"{token} flood")
    ]
    assert len(rows) == 10, f"expected exactly 10 persisted events, got {len(rows)}"


def test__submit_client_log__AnonymousAndAuthedSessions__BucketedSeparately(api):
    # Authed traffic buckets on the session user id, anonymous on the
    # remote IP — draining one allowance must not starve the other.
    token = _token()
    for i in range(10):
        assert requests.post(CLIENT_LOGS, json={
            "level": "error", "message": f"{token} authed {i}",
        }).status_code == 204

    anon = requests.Session()
    marker = f"{token} anon still fine"
    assert anon.post(CLIENT_LOGS, json={
        "level": "error", "message": marker,
    }).status_code == 204

    rows = [r for r in _audit_rows("client.error") if r["payload"]["message"] == marker]
    assert len(rows) == 1, "anonymous bucket was starved by the authed session's flood"


#endregion rate limit


def test__rate_limit_buckets__keys_whose_window_passed_are_evicted():
    """Finalisation 20-R9: one deque per session-id / IP, created on first
    sight and never removed — a slow leak under anonymous crawlers. A key
    whose newest stamp is older than the window goes on the next call."""
    import time
    from collections import deque

    stale = time.monotonic() - _scl._BUCKET_WINDOW_SECONDS - 1
    _scl._buckets["old-visitor"] = deque([stale, stale])
    _scl._buckets["empty-visitor"] = deque()

    assert _scl._allow("fresh-visitor") is True

    assert "old-visitor" not in _scl._buckets
    assert "empty-visitor" not in _scl._buckets
    assert "fresh-visitor" in _scl._buckets


#region ---------------- context bounding ----------------


def test__bound_client_context__SmallContext__Unchanged():
    ctx = {"route": "/stock", "nested": {"a": [1, 2, {"b": "c"}]}}
    assert _scl.bound_client_context(ctx) == ctx


def test__bound_client_context__DeepNesting__ClippedWithMarker():
    deep: dict = {"leaf": "x"}
    for _ in range(50):
        deep = {"d": deep}
    bounded = _scl.bound_client_context(deep)
    assert bounded["d"]["d"]["d"]["d"] == "[truncated]"


def test__bound_client_context__OversizeContext__StaysUnderCapAndKeepsKeys():
    ctx = {f"k{i}": "v" * 500 for i in range(200)}
    ctx["stack"] = "s" * 50_000
    bounded = _scl.bound_client_context(ctx)
    size = len(json.dumps(bounded).encode("utf-8"))
    assert size <= _scl._CONTEXT_MAX_BYTES
    assert bounded["_truncated"] is True
    assert bounded["k0"] == "v" * 500


def test__submit_client_log__OversizeContext__PersistedBounded(api):
    marker = f"{_token()} big context"
    resp = requests.post(CLIENT_LOGS, json={
        "level": "error",
        "message": marker,
        "context": {"route": "/stock", "blob": ["x" * 1000] * 500},
    })
    assert resp.status_code == 204, resp.text

    rows = [r for r in _audit_rows("client.error") if r["payload"]["message"] == marker]
    assert len(rows) == 1
    stored = rows[0]["payload"]["context"]
    assert len(json.dumps(stored).encode("utf-8")) <= _scl._CONTEXT_MAX_BYTES
    assert stored["route"] == "/stock"
    assert stored["_truncated"] is True
