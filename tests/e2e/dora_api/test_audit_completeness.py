"""FU-538 — audit-coverage completeness sweep.

WHY THIS MATTERS: test_audit.py proves ONE mutating route emits an audit event
and that scrubbing works — but there's no guarantee the OTHER ~160 mutating
method/route pairs do. Audit gaps are silent (nothing breaks; the trail is
just missing) and only discovered during an incident when the row you need
isn't there. This is the audit analogue of test_route_auth_enforcement.py's
sweep: pin the contract "every state-changing (POST/PATCH/PUT/DELETE) /api
endpoint either emits an AuditEvent or is on an explicit, commented
exempt-set".

HOW AUDIT ACTUALLY WORKS (read dora_api/infrastructure/audit.py +
middleware.py): auditing is a SINGLE global `after_app_request` hook
(`auto_audit_after_request`). It emits exactly one row for every mutating
/api/* request whose response status is < 400, EXCEPT endpoints named in
`audit._NO_AUDIT_ENDPOINTS`. So the skip logic lives in ONE place; this
sweep's exempt-set (`AUDIT_EXEMPT` below) is pinned to be the *mutating
subset* of that real set — we do NOT invent a parallel allowlist.

TWO complementary layers, mirroring the auth sweep's runtime-url_map shape
(routes register inside startup(), so app.url_map is empty at collection time
→ everything here is a RUNTIME loop, never a collection-time parametrize):

  * STRUCTURAL (covers all ~160 pairs): every mutating /api rule's endpoint
    is either middleware-audited (not in _NO_AUDIT_ENDPOINTS) or in the
    explicit AUDIT_EXEMPT set — and AUDIT_EXEMPT is kept in lockstep with the
    real _NO_AUDIT_ENDPOINTS (no rot, no parallel invention).
  * BEHAVIOURAL (a tractable subset): actually drive a broad set of mutating
    endpoints to a 2xx and diff the AuditEvent table before/after, asserting
    exactly one new row that carries the actor user_id, a non-empty action,
    and a scrubbed payload. This is what proves the middleware genuinely
    fires end-to-end (not just that the endpoint name isn't on the skip list).

WHAT'S EXCLUDED FROM THE BEHAVIOURAL SWEEP (and why) — these are still pinned
by the STRUCTURAL layer, they're just impractical to drive to a clean 2xx:
heavy/side-effecting or hard-to-build-a-valid-body routes (backups
create/inspect/restore, spreadsheet import, chunked uploads, ingestion batch,
reconcile, cook, assistant ask/act/confirm, tts synth/voice download, meal-
plan template application, auth email/password flows, admin user CRUD). See
`_EXCLUDED_FROM_BEHAVIOURAL` for the full annotated list.

CONVENTIONS: module-level `requests.*` = authenticated admin client (the
seeded "dora" account); per-test DB rollback is automatic. The behavioural
sweep is ONE test that loops many mutations — that's fine, rollback happens
once at teardown.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Callable

import requests
from sqlalchemy import select

from dora_api.app import app, db
from dora_api.infrastructure.audit import (SCRUBBED_KEYS, _NO_AUDIT_ENDPOINTS,
                                           _MUTATING_METHODS)

BASE = "http://localhost:5170/api"


# ── The exempt-set — pinned to audit._NO_AUDIT_ENDPOINTS ───────────────────
#
# These are the mutating endpoints the middleware deliberately does NOT
# auto-audit. Each entry names WHY it's legitimately exempt. This set is
# asserted (below) to be exactly the mutating subset of
# audit._NO_AUDIT_ENDPOINTS — so it can't drift from the real skip logic and
# can't rot (a name here that no longer maps to a route fails the guard).
#
# `health_check` is in _NO_AUDIT_ENDPOINTS too but is GET-only, so it never
# appears in the mutating rule set and is intentionally absent here.
AUDIT_EXEMPT: dict[str, str] = {
    "login": (
        "auth handler emits its own explicit auth.login.{succeeded,failed} "
        "rows (a 200-with-body can be a wrong-password failure the middleware "
        "can't distinguish); middleware skip avoids a duplicate."
    ),
    "submit_client_log": (
        "self-persists via its own client.* emit path; middleware skip avoids "
        "a duplicate row for the same request."
    ),
    "logout": (
        "handler emits an explicit auth.logout row before clearing the session "
        "(FU-548) — like login, it's in _NO_AUDIT_ENDPOINTS so the middleware "
        "doesn't also write a duplicate, actor-less row. See "
        "test__audit_coverage__logout_emits_an_explicit_event."
    ),
}


# ── url_map helpers (copied from test_route_auth_enforcement.py) ────────────

_DUMMY_ID = "de919bc0-5bd6-4f9c-9a37-2b6e64d3f1aa"
_DUMMY_BY_CONVERTER = {"int": "1", "float": "1.0", "path": "dummy-path"}


def _fill(rule_template: str) -> str:
    def _replace(match: re.Match) -> str:
        spec = match.group(1)
        converter = spec.split(":", 1)[0] if ":" in spec else "string"
        return _DUMMY_BY_CONVERTER.get(converter, _DUMMY_ID)

    return re.sub(r"<([^>]+)>", _replace, rule_template)


def _mutating_rules():
    """Every registered /api rule that accepts at least one mutating method,
    as (endpoint_name, rule_string, sorted-mutating-methods)."""
    out = []
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/api/"):
            continue
        methods = sorted(rule.methods & _MUTATING_METHODS)
        if methods:
            out.append((rule.endpoint.split(".")[-1], rule.rule, methods))
    return out


# ── AuditEvent table helpers (query pattern from test_audit.py's retention) ─

def _audit_rows() -> dict[str, dict]:
    """Snapshot every AuditEvent row keyed by str(id). Returns the columns the
    sweep asserts on. Fresh app_context so we read the just-committed rows the
    in-request middleware wrote."""
    with app.app_context():
        t = db.metadata.tables["AuditEvent"]
        result = db.session.execute(
            select(t.c.id, t.c.actor_user_id, t.c.action, t.c.payload,
                   t.c.source, t.c.severity)
        ).all()
        return {
            str(r[0]): {
                "actor_user_id": None if r[1] is None else str(r[1]),
                "action": r[2],
                "payload": r[3],
                "source": r[4],
                "severity": r[5],
            }
            for r in result
        }


def _payload_has_unredacted_secret(payload_json: str | None) -> str | None:
    """Return the offending key if any SCRUBBED_KEYS-matching key carries a
    value other than the redaction marker; else None."""
    if not payload_json:
        return None
    try:
        obj = json.loads(payload_json)
    except (TypeError, ValueError):
        return None

    def _walk(value) -> str | None:
        if isinstance(value, dict):
            for k, v in value.items():
                if any(bad in k.lower() for bad in SCRUBBED_KEYS):
                    if v != "***redacted***":
                        return k
                hit = _walk(v)
                if hit:
                    return hit
        elif isinstance(value, list):
            for item in value:
                hit = _walk(item)
                if hit:
                    return hit
        return None

    return _walk(obj)


def _me_user_id() -> str:
    body = requests.get(f"{BASE}/auth/me").json()
    return body["user_id"]


def _u(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ── The behavioural probe set ──────────────────────────────────────────────
#
# Each probe is a zero-arg function that does any PREREQUISITE seeding
# (unmeasured — those requests emit their own audit rows) and returns a
# `(label, do_mutation)` pair. `do_mutation()` is the single measured call:
# the sweep snapshots AuditEvent ids around it and asserts exactly one new
# row. Keeping seeding outside the measured window is what lets us assert
# *exactly one* new row for the endpoint under test.
#
# Prereq ids come from tests/factories-style seeding via the HTTP boundary
# (create-then-mutate) or a GET (e.g. stock_level_id) — GETs never audit.

Probe = Callable[[], tuple[str, Callable[[], "requests.Response"]]]


def _p_create(label: str, path: str, body: dict | None) -> Probe:
    def _probe():
        return label, (lambda: requests.post(f"{BASE}{path}", json=body))
    return _probe


def _seed_id(path: str, body: dict, id_key: str) -> str:
    resp = requests.post(f"{BASE}{path}", json=body)
    assert resp.status_code in (200, 201), f"seed {path} failed: {resp.text}"
    data = resp.json()
    return data.get(id_key) or data["id"]


def _probe_category_patch() -> tuple[str, Callable]:
    cid = _seed_id("/categories", {"name": _u("cat")}, "category_id")
    return "PATCH /categories/<id>", (
        lambda: requests.patch(f"{BASE}/categories/{cid}", json={"name": _u("cat")})
    )


def _probe_category_delete() -> tuple[str, Callable]:
    cid = _seed_id("/categories", {"name": _u("cat")}, "category_id")
    return "DELETE /categories/<id>", (lambda: requests.delete(f"{BASE}/categories/{cid}"))


def _probe_stock_group_delete() -> tuple[str, Callable]:
    gid = _seed_id("/stock-groups", {"name": _u("grp")}, "stock_group_id")
    return "DELETE /stock-groups/<id>", (lambda: requests.delete(f"{BASE}/stock-groups/{gid}"))


def _probe_stock_item_create() -> tuple[str, Callable]:
    level = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    return "POST /stock-items", (
        lambda: requests.post(f"{BASE}/stock-items",
                              json={"name": _u("item"), "stock_level_id": level})
    )


def _probe_shopping_list_line() -> tuple[str, Callable]:
    lid = _seed_id("/shopping-lists", {"name": _u("list")}, "shopping_list_id")
    level = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    sid = _seed_id("/stock-items", {"name": _u("item"), "stock_level_id": level},
                   "stock_item_id")
    return "POST /shopping-lists/<id>/lines", (
        lambda: requests.post(f"{BASE}/shopping-lists/{lid}/lines",
                              json={"stock_item_id": sid, "quantity": 1})
    )


# Simple creates that need no prerequisite entity — the bread-and-butter of
# the sweep. Unique names dodge duplicate-guard 422s.
_SIMPLE_CREATE_PROBES: list[Probe] = [
    _p_create("POST /categories", "/categories", {"name": _u("cat")}),
    _p_create("POST /cuisines", "/cuisines", {"name": _u("cui")}),
    _p_create("POST /dietary-tags", "/dietary-tags",
              {"name": _u("tag"), "category": "Allergen-free"}),
    _p_create("POST /tools", "/tools", {"name": _u("tool")}),
    _p_create("POST /stock-groups", "/stock-groups", {"name": _u("grp")}),
    _p_create("POST /stores", "/stores", {"name": _u("store")}),
    _p_create("POST /stock-locations", "/stock-locations", {"name": _u("loc")}),
    _p_create("POST /locations", "/locations",
              {"name": _u("zone"), "kind": "zone", "sequence": 0}),
    _p_create("POST /recipe-collections", "/recipe-collections", {"name": _u("coll")}),
    _p_create("POST /meal-slots", "/meal-slots", {"name": _u("slot")}),
    _p_create("POST /recipes", "/recipes", {"name": _u("recipe")}),
    _p_create("POST /shopping-lists", "/shopping-lists", {"name": _u("list")}),
    _p_create("POST /products", "/products", {
        "brand": "Test", "image": None, "is_active": True, "is_available": True,
        "store_name": "Woolworths", "merchant_stockcode": _u("sku"),
        "name": _u("prod"), "price_now": 4.5, "price_was": 10.5,
        "size": "500g", "size_unit": "g", "size_value": 5.0, "web_url": "https://www.example.test",
    }),
]

_SEEDED_PROBES: list[Probe] = [
    _probe_category_patch,
    _probe_category_delete,
    _probe_stock_group_delete,
    _probe_stock_item_create,
    _probe_shopping_list_line,
]

_BEHAVIOURAL_PROBES: list[Probe] = _SIMPLE_CREATE_PROBES + _SEEDED_PROBES


# Endpoints intentionally left out of the behavioural sweep — heavy side
# effects, external deps, or a body too fiddly to build cleanly. Each is still
# covered by the STRUCTURAL layer (they're all middleware-audited). Listed
# here only so the report is honest about what wasn't exercised end-to-end.
_EXCLUDED_FROM_BEHAVIOURAL: dict[str, str] = {
    "create_backup": "writes a real backup archive to disk",
    "inspect_backup": "requires an uploaded backup file",
    "restore_backup": "destructive full-DB restore",
    "restore_saved_backup": "destructive full-DB restore",
    "delete_backup": "requires a seeded backup on disk",
    "inspect_spreadsheet": "requires an uploaded spreadsheet",
    "commit_spreadsheet": "requires a staged spreadsheet upload",
    "start_upload": "chunked-upload state machine",
    "append_chunk": "chunked-upload state machine",
    "finish_upload": "chunked-upload state machine",
    "abort_upload": "chunked-upload state machine",
    "submit_ingestion_batch": "bearer-auth ingestion; heavy batch body",
    "submit_verb": "meal-plan reconcile — needs a live reconcile signal",
    "cook_recipe": "consumes stock; needs a fully-linked recipe",
    "ask_assistant": "calls the LLM",
    "commit_action": "assistant action needs a staged plan",
    "confirm_action": "assistant action needs a staged plan",
    "probe_assistant": "calls the LLM",
    "synthesize": "TTS synthesis (audio bytes / external engine)",
    "download_voice": "downloads a voice model",
    "apply_template": "needs a populated meal-plan template",
    "apply_template_recurring": "needs a populated meal-plan template",
    "clone_meal_plan_template": "needs a populated template",
    "instantiate_template": "needs a populated shopping-list template",
    "snapshot_from_list": "needs a source list with lines",
    "import_from_content": "recipe paste/parse pipeline",
    "bulk_link_unlinked_ingredients": "needs unlinked-ingredient state",
    "admin_create_user": "creates a real user (rate-limited auth surface)",
    "admin_update_user": "needs a seeded target user",
    "admin_delete_user": "needs a seeded target user",
    "reset_user_password": "needs a seeded target user",
    "change_password": "mutates the admin's own credentials mid-suite",
    "update_me": "mutates the admin's own profile mid-suite",
    "verify_email": "out-of-band token flow",
    "resend_verification": "sends verification email",
    "forgot_password": "sends reset email",
    "reset_password": "out-of-band token flow",
    "register_user": "rate-limited; covered by the auth sweep",
    "bootstrap_admin": "410s once any user exists",
}


# ── A. Behavioural sweep — every driven mutation emits exactly one event ────

def test__audit_coverage__every_mutating_probe_emits_exactly_one_event(api):
    # Coverage floor — if the probe list is gutted, fail loudly rather than
    # pass vacuously (mirrors the auth sweep's `swept >= 80`).
    assert len(_BEHAVIOURAL_PROBES) >= 15, (
        f"behavioural probe set shrank to {len(_BEHAVIOURAL_PROBES)} — "
        "did someone gut the sweep?"
    )

    failures: list[str] = []
    for make_probe in _BEHAVIOURAL_PROBES:
        label, do_mutation = make_probe()  # seeding here is UNMEASURED
        before = set(_audit_rows())
        resp = do_mutation()
        after = _audit_rows()
        new_ids = set(after) - before

        if resp.status_code >= 400:
            failures.append(
                f"{label}: mutation returned {resp.status_code} "
                f"(could not drive to 2xx): {resp.text[:160]}"
            )
            continue
        if len(new_ids) != 1:
            failures.append(
                f"{label}: expected exactly 1 new AuditEvent row, got "
                f"{len(new_ids)} (status {resp.status_code})"
            )
            continue

    assert not failures, (
        f"{len(failures)} mutating endpoint(s) did not emit exactly one audit "
        "event when driven to success (a missing row = a real audit gap):\n"
        + "\n".join(failures)
    )


# ── B. Every emitted event carries actor + non-empty action + scrubbed payload ─

def test__audit_coverage__events_carry_actor_and_scrubbed_payload(api):
    me = _me_user_id()
    failures: list[str] = []

    for make_probe in _BEHAVIOURAL_PROBES:
        label, do_mutation = make_probe()
        before = set(_audit_rows())
        resp = do_mutation()
        if resp.status_code >= 400:
            continue  # driveability is asserted by test A; skip here
        after = _audit_rows()
        new_ids = set(after) - before
        for rid in new_ids:
            row = after[rid]
            if row["actor_user_id"] != me:
                failures.append(
                    f"{label}: actor_user_id={row['actor_user_id']!r}, "
                    f"expected the logged-in admin {me!r}"
                )
            if not (row["action"] and row["action"].strip()):
                failures.append(f"{label}: empty/blank action {row['action']!r}")
            leaked = _payload_has_unredacted_secret(row["payload"])
            if leaked:
                failures.append(
                    f"{label}: payload key {leaked!r} carries an unredacted "
                    f"secret: {row['payload']}"
                )

    assert not failures, (
        "audit rows failed the actor/action/scrub contract:\n" + "\n".join(failures)
    )


def test__audit_coverage__scrub_redacts_secret_payload_keys(api):
    """Extends test_audit.py's scrub proof into the completeness suite: a
    request whose payload carries a password-shaped key must land in the audit
    log with that key redacted, never in the clear. Driven via the client-log
    path (the one mutating endpoint that persists a caller-supplied payload)."""
    before = set(_audit_rows())
    marker = _u("scrub-probe")
    requests.post(f"{BASE}/client-logs", json={
        "level": "error",
        "message": marker,
        "context": {"password": "should-be-gone", "api_key": "sk-leak", "other": "ok"},
    })
    after = _audit_rows()
    new = [after[rid] for rid in (set(after) - before)]
    assert new, "client-log POST wrote no audit row"

    relevant = [
        r for r in new
        if r["payload"] and marker in r["payload"]
    ]
    assert relevant, f"no audit row carried the probe marker; rows={new}"
    for row in relevant:
        obj = json.loads(row["payload"])
        ctx = obj.get("context", obj)
        assert ctx.get("password") == "***redacted***", ctx
        assert ctx.get("api_key") == "***redacted***", ctx
        assert ctx.get("other") == "ok", ctx
        assert _payload_has_unredacted_secret(row["payload"]) is None


# ── C. Structural contract — every mutating rule audited-or-exempt ─────────

def test__audit_coverage__every_mutating_rule_is_audited_or_exempt(api):
    """The whole /api mutating surface (~160 method/route pairs), not just the
    behavioural subset: every rule's endpoint is either middleware-audited
    (not in _NO_AUDIT_ENDPOINTS) or explicitly in AUDIT_EXEMPT with a reason.
    This is what pins the endpoints the behavioural sweep can't cheaply drive."""
    swept = 0
    unexplained: list[str] = []
    for endpoint, rule, methods in _mutating_rules():
        swept += 1
        if endpoint in _NO_AUDIT_ENDPOINTS and endpoint not in AUDIT_EXEMPT:
            unexplained.append(
                f"{'/'.join(methods)} {rule} (endpoint={endpoint}) is on the "
                "middleware's _NO_AUDIT_ENDPOINTS skip list but has no "
                "AUDIT_EXEMPT reason — either it should be audited (drop it "
                "from the skip list) or document why it's exempt."
            )

    assert swept >= 120, (
        f"structural sweep only saw {swept} mutating rules — url_map looks "
        "under-populated; did route registration move out of startup()?"
    )
    assert not unexplained, (
        "mutating endpoints skipped by the audit middleware without an "
        "AUDIT_EXEMPT reason:\n" + "\n".join(unexplained)
    )


def test__audit_coverage__exempt_set_matches_real_skip_logic(api):
    """AUDIT_EXEMPT must equal the *mutating* subset of the middleware's real
    _NO_AUDIT_ENDPOINTS — so this test's allowlist can't invent a parallel
    exemption and can't silently diverge from production skip logic. If the
    middleware starts/stops skipping a mutating endpoint, this fails until
    AUDIT_EXEMPT (and its documented reasons) are updated to match."""
    mutating_endpoints = {ep for ep, _, _ in _mutating_rules()}
    real_mutating_skips = {
        ep for ep in _NO_AUDIT_ENDPOINTS if ep in mutating_endpoints
    }
    assert set(AUDIT_EXEMPT) == real_mutating_skips, (
        "AUDIT_EXEMPT drifted from audit._NO_AUDIT_ENDPOINTS' mutating subset.\n"
        f"  in AUDIT_EXEMPT only: {sorted(set(AUDIT_EXEMPT) - real_mutating_skips)}\n"
        f"  in _NO_AUDIT_ENDPOINTS only: {sorted(real_mutating_skips - set(AUDIT_EXEMPT))}"
    )


def test__audit_coverage__exempt_set_has_no_stale_rules(api):
    """Reverse guard (mirrors the PUBLIC_ENDPOINTS allowlist-rot check in the
    auth sweep): every AUDIT_EXEMPT name must still map to a registered
    mutating /api endpoint. A stale name here would silently exempt nothing."""
    registered_mutating = {ep for ep, _, _ in _mutating_rules()}
    stale = set(AUDIT_EXEMPT) - registered_mutating
    assert not stale, (
        "AUDIT_EXEMPT names with no matching registered mutating route "
        f"(allowlist rot): {sorted(stale)}"
    )


# ── C2. Explicit emitters don't also write a generic row (FU-599) ──────────

def test__audit_coverage__explicit_emit_suppresses_the_generic_row(api):
    """FU-599 — an endpoint whose handler emits an explicit (domain-named)
    audit event must NOT also get the middleware's generic row. Before the
    request-scoped dedup flag, `admin_create_user` produced BOTH
    `user.created_by_admin` (explicit, carrying actor + entity + payload) and
    `admin_create_user` (generic, bare) for a single operation — the same
    double-log the FU observed on the email-change flow. Pin exactly one row
    for the request, and that it's the richer explicit one."""
    before = set(_audit_rows())
    resp = requests.post(f"{BASE}/users", json={"username": _u("audit-dedup")})
    assert resp.status_code in (200, 201), resp.text

    after = _audit_rows()
    new_actions = sorted(after[rid]["action"] for rid in (set(after) - before))
    assert new_actions == ["user.created_by_admin"], (
        f"expected exactly one explicit audit row, got {new_actions} — the "
        "generic middleware row must be suppressed when the handler already "
        "emitted explicitly (FU-599)"
    )


# ── D. Pin the one deliberate zero-audit endpoint ──────────────────────────

def test__audit_coverage__logout_emits_an_explicit_event(api):
    """FU-548 — session termination is now audited. logout stays in
    _NO_AUDIT_ENDPOINTS (like login) but its handler emits an explicit
    `auth.logout` row BEFORE clearing the session, so the actor is captured.
    Pins that logout leaves exactly one audit row naming the actor."""
    s = requests.Session()  # fresh authed client
    login = s.post(f"{BASE}/auth/login", json={"username": "dora", "password": "dora"})
    assert login.status_code == 200, login.text
    actor_id = login.json()["user_id"]

    before = set(_audit_rows())
    logout = s.post(f"{BASE}/auth/logout")
    assert logout.status_code in (200, 204), logout.text

    rows = _audit_rows()
    new_ids = set(rows) - before
    assert len(new_ids) == 1, (
        f"logout should emit exactly one audit row, got {len(new_ids)}: {new_ids}"
    )
    row = rows[new_ids.pop()]
    assert row["action"] == "auth.logout", row
    assert row["actor_user_id"] == actor_id, (
        f"logout audit must name the actor ({actor_id}), got {row['actor_user_id']}"
    )
