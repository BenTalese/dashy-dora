"""Systematic auth / permission enforcement sweep over the whole /api surface.

Three layers of defence-verification:

A. **Anonymous sweep** — every registered /api rule whose endpoint is not in
   `middleware.PUBLIC_ENDPOINTS` must return 401 to a session-less caller,
   for every HTTP method it accepts. The auth gate is a single global
   `before_app_request` (dora_api/infrastructure/middleware.py), so this
   catches both "route accidentally added to the allowlist" and "allowlist
   name rot" (a stale name in PUBLIC_ENDPOINTS that no longer matches a
   registered endpoint would silently gate nothing).

B. **Admin-only contract** — ADMIN gating is hand-rolled per handler (each
   admin handler calls `require_admin()` / `_require_admin()` from
   dora_api/features/auth/admin_gate.py, plus one local mirror in
   ingestion_source_admin.py). A handler that forgot the call is a real
   privilege-escalation hole. We register a fresh NON-admin user and hit a
   pinned list of every admin-only endpoint expecting exactly 403.
   Mutating endpoints are sent a *minimally valid* body: the middleware
   deserialises the request BEFORE the handler runs, so an invalid body
   would 400 in middleware and never exercise the admin gate at all —
   an ungated endpoint would be invisible to the sweep.

C. **Reverse check** — the pinned list is compared against a live count of
   `= require_admin()` / `= _require_admin()` call sites in the source
   tree, so a future admin endpoint whose author forgets to extend the
   pinned list fails this suite instead of silently going untested.

NOTE on structure: routes are registered inside `startup()` (called by the
session-scoped `api` fixture), NOT at `dora_api.app` import time. That means
`app.url_map` is empty at pytest collection time, so the sweep cannot be a
collection-time `@pytest.mark.parametrize` over `iter_rules()` (forcing
registration at import would make the fixture's later `register_routers()`
crash on duplicate blueprint names). Instead each sweep is a single test
that iterates at runtime and reports every failing (method, route) pair in
the assertion message.
"""
import re
import uuid
from pathlib import Path

import requests

from dora_api.app import app
from dora_api.infrastructure.middleware import PUBLIC_ENDPOINTS
from tests.support import open_registration

BASE = "http://localhost:5170"
_REPO_ROOT = Path(__file__).resolve().parents[3]

# One fixed dummy id for every path parameter. The entities never exist, but
# that's fine: the auth gate (layer A) and the admin gate (layer B) both run
# before any lookup, so the expected status is 401/403 — never 404.
_DUMMY_ID = "de919bc0-5bd6-4f9c-9a37-2b6e64d3f1aa"

_DUMMY_BY_CONVERTER = {
    "int": "1",
    "float": "1.0",
    "path": "dummy-path",
}


def _fill(rule_template: str) -> str:
    """Substitute concrete dummy values for the <converter:name> params of a
    werkzeug rule string. Default (string/uuid) converters get _DUMMY_ID so
    paths built here line up exactly with the pinned admin list below."""
    def _replace(match: re.Match) -> str:
        spec = match.group(1)
        converter = spec.split(":", 1)[0] if ":" in spec else "string"
        return _DUMMY_BY_CONVERTER.get(converter, _DUMMY_ID)

    return re.sub(r"<([^>]+)>", _replace, rule_template)


_SUPPORTED_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})


def _api_rules():
    """Every registered rule under /api/ (skips the SPA catch-all + static)."""
    return [rule for rule in app.url_map.iter_rules()
            if rule.rule.startswith("/api/")]


# ── A. Anonymous sweep ─────────────────────────────────────────────────


def test__anonymous_request__gets_401_on_every_protected_api_route(api):
    anon = requests.Session()  # fresh test client — no session, no CSRF cookie
    failures: list[str] = []
    swept = 0

    for rule in _api_rules():
        endpoint_name = rule.endpoint.split(".")[-1]
        if endpoint_name in PUBLIC_ENDPOINTS:
            continue
        url = _fill(rule.rule)
        for method in sorted(rule.methods & _SUPPORTED_METHODS):
            swept += 1
            # No body on purpose: the auth gate runs BEFORE deserialisation,
            # so 401 must win even on mutating methods with schemas.
            response = getattr(anon, method.lower())(f"{BASE}{url}")
            if response.status_code != 401:
                failures.append(
                    f"{method} {rule.rule} (endpoint={rule.endpoint}) "
                    f"-> {response.status_code}, expected 401"
                )

    # Coverage sanity floor — if route registration ever moves and the sweep
    # silently iterates an empty url_map, fail loudly instead of passing.
    assert swept >= 80, (
        f"Anonymous sweep only covered {swept} (method, route) pairs — "
        "url_map looks under-populated; did route registration move out of "
        "startup()?"
    )
    assert not failures, (
        f"{len(failures)} protected /api route(s) did not 401 anonymously:\n"
        + "\n".join(failures)
    )


def test__public_endpoints_allowlist__every_name_is_a_registered_endpoint(api):
    """Allowlist-rot guard: a PUBLIC_ENDPOINTS entry that matches no
    registered endpoint gates nothing and silently rots. Every name must
    correspond to a real view function."""
    registered = {endpoint.split(".")[-1] for endpoint in app.view_functions}
    missing = PUBLIC_ENDPOINTS - registered
    assert not missing, (
        "PUBLIC_ENDPOINTS names with no registered endpoint (allowlist rot): "
        f"{sorted(missing)}"
    )


def test__public_endpoints__are_all_under_expected_surfaces(api):
    """Belt-and-braces: every rule whose endpoint IS public must live on an
    intentionally-public surface (auth flows, health, client logs, ingest).
    Catches someone adding e.g. a stock route name to the allowlist."""
    allowed_prefixes = (
        "/api/auth/",
        "/api/health",
        "/api/client-logs",
        "/api/ingest",  # POST /api/ingest — bearer-auth ingestion (no trailing slash)
    )
    offenders = [
        f"{rule.rule} (endpoint={rule.endpoint})"
        for rule in _api_rules()
        if rule.endpoint.split(".")[-1] in PUBLIC_ENDPOINTS
        and not rule.rule.startswith(allowed_prefixes)
    ]
    assert not offenders, (
        "Public (auth-exempt) routes outside the expected public surfaces:\n"
        + "\n".join(offenders)
    )


# ── B. Admin-only contract ─────────────────────────────────────────────
#
# Pinned list of every admin-only endpoint: (method, path, minimal-valid
# JSON body or None). Bodies must pass the endpoint's request schema —
# middleware deserialises BEFORE the handler, so an invalid body would 400
# in middleware and never reach the admin gate (masking a missing gate).
#
# TO REFRESH: grep the backend for admin-gate call sites —
#   rg -n "= _?require_admin\(\)" dora_api/features
# — then map each hit's enclosing function to its @*_ROUTER.route(...)
# decorator (blueprint url_prefixes live in dora_api/features/routers.py).
# One pinned row per call site, 1:1. The reverse check below fails when the
# call-site count and this list drift apart.
PINNED_ADMIN_ENDPOINTS: list[tuple[str, str, dict | None]] = [
    # users — dora_api/features/users/*.py
    ("GET",    "/api/users", None),                                     # get_users.py:85
    ("POST",   "/api/users", {"username": f"probe-{uuid.uuid4().hex[:8]}"}),  # create_user_as_admin.py:102
    ("PATCH",  f"/api/users/{_DUMMY_ID}", {}),                          # update_user_as_admin.py:108
    ("DELETE", f"/api/users/{_DUMMY_ID}", None),                        # delete_user_as_admin.py:83
    ("POST",   f"/api/users/{_DUMMY_ID}/reset-password", None),        # reset_user_password.py:52
    # app settings — dora_api/features/app_settings/*.py
    ("GET",    "/api/app-settings", None),                              # get_app_settings.py:134
    ("PATCH",  "/api/app-settings", {}),                                # update_app_settings.py:417
    # nutrition dataset import — dora_api/features/nutrition/nutrition_endpoints.py
    # (GET /api/nutrition/sources is deliberately NOT admin-gated: every member
    # needs to know whether a lookup can answer. Only the import is admin.)
    ("POST",   "/api/nutrition/datasets/import", {"source": "usda_sr_legacy"}),
    # audit — dora_api/features/audit/get_audit_events.py
    ("GET",    "/api/audit/events", None),                              # :168
    ("GET",    f"/api/audit/events/{_DUMMY_ID}", None),                 # :217
    # backup library — dora_api/features/data/backup_library.py
    ("POST",   "/api/data/backups", {}),                                # :182
    ("GET",    "/api/data/backups", None),                              # :242
    ("GET",    "/api/data/backup/sections", None),                      # list_backup_sections (18-R3)
    ("GET",    f"/api/data/backups/{_DUMMY_ID}/download", None),        # :283
    ("POST",   f"/api/data/backups/{_DUMMY_ID}/restore", None),         # :307
    ("DELETE", f"/api/data/backups/{_DUMMY_ID}", None),                 # :345
    # backup inspect / restore — dora_api/features/data/{inspect,restore}_backup.py
    ("POST",   "/api/data/backup/inspect", None),                       # inspect_backup.py:279
    ("POST",   "/api/data/backup/restore", {}),                         # restore_backup.py:368
    # spreadsheet import — dora_api/features/data/import_spreadsheet.py
    ("POST",   "/api/data/import/spreadsheet/inspect",
     {"upload_id": _DUMMY_ID, "filename": "probe.csv"}),                # :314
    ("POST",   "/api/data/import/spreadsheet/commit",
     {"upload_id": _DUMMY_ID, "filename": "probe.csv",
      "sheet": "Sheet1", "column_map": {}}),                            # :657
    ("GET",    "/api/data/import/templates", None),                     # :836
    ("GET",    f"/api/data/import/templates/{_DUMMY_ID}.csv", None),    # :854
    # chunked uploads — dora_api/features/data/uploads.py
    ("POST",   "/api/data/uploads/start", {}),                          # :106
    ("POST",   "/api/data/uploads/chunk", None),                        # :135
    ("POST",   "/api/data/uploads/finish", {"upload_id": _DUMMY_ID}),   # :207
    ("DELETE", f"/api/data/uploads/{_DUMMY_ID}", None),                 # :228
    # ingestion sources — dora_api/features/ingestion_sources/ingestion_source_admin.py
    ("GET",    "/api/ingestion-sources", None),                         # :197
    ("POST",   "/api/ingestion-sources", {"label": "probe"}),           # :207
    ("PATCH",  f"/api/ingestion-sources/{_DUMMY_ID}", {}),              # :224
    ("DELETE", f"/api/ingestion-sources/{_DUMMY_ID}", None),            # :236
    # ingestion store mappings — dora_api/features/ingestion_sources/store_mappings.py
    ("GET",    f"/api/ingestion-sources/{_DUMMY_ID}/store-mappings", None),   # :168
    ("PUT",    f"/api/ingestion-sources/{_DUMMY_ID}/store-mappings",
     {"external_name": "probe"}),                                       # :180
    ("DELETE", f"/api/ingestion-sources/{_DUMMY_ID}/store-mappings/{_DUMMY_ID}", None),  # :200
]


def _register_non_admin(session: requests.Session) -> None:
    """Create + auto-login a fresh non-admin account. Registration never
    grants admin (FU-200, proven by test_auth_flows), auto-login works
    without email verification, and the register response seeds the
    `dora_csrf` cookie so the conftest adapter auto-attaches the CSRF
    header on subsequent mutations."""
    # The auth rate limiter is in-memory per-IP (auth_helpers._buckets)
    # and every test-client request shares one remote_addr, so a full-suite
    # run's accumulated registrations 429 this call. The per-test DB
    # rollback can't reset process memory — drain the pre-auth buckets
    # directly (same isolation spirit as the snapshot-rollback fixture).
    from dora_api.infrastructure import auth_helpers
    with auth_helpers._buckets_lock:
        for key in list(auth_helpers._buckets):
            if key[0] in ("auth.register", "auth.login"):
                del auth_helpers._buckets[key]

    open_registration()
    username = f"sweep-nonadmin-{uuid.uuid4().hex[:8]}"
    response = session.post(f"{BASE}/api/auth/register", json={
        "username": username,
        "password": "Abcdefghij1",
        "email": f"{username}@example.com",
    })
    assert response.status_code == 200, (
        f"non-admin registration failed ({response.status_code}): {response.text}"
    )
    assert response.json()["is_admin"] is False
    me = session.get(f"{BASE}/api/auth/me")
    assert me.status_code == 200, "register did not establish a session"


def test__non_admin_user__gets_403_on_every_admin_endpoint(api):
    # One registration for the whole sweep (register is rate-limited
    # per-IP and the per-test DB rollback would drop the user between
    # tests anyway — so this is a single test looping the pinned list).
    s = requests.Session()
    _register_non_admin(s)

    failures: list[str] = []
    for method, path, body in PINNED_ADMIN_ENDPOINTS:
        kwargs = {"json": body} if body is not None else {}
        response = getattr(s, method.lower())(f"{BASE}{path}", **kwargs)
        if response.status_code != 403:
            failures.append(
                f"{method} {path} -> {response.status_code}, expected 403 "
                f"(body sent: {body!r}; response: {response.text[:200]})"
            )

    assert not failures, (
        f"{len(failures)} admin endpoint(s) did not 403 for a non-admin "
        "user (200 = privilege escalation, 400/404 = the admin gate never "
        "ran or runs after other logic, 500 = crash before the gate):\n"
        + "\n".join(failures)
    )


def test__pinned_admin_routes__all_exist_in_url_map(api):
    """Refresh guard: every pinned (method, path) must still match a
    registered rule — catches renamed/removed admin routes leaving stale
    pinned rows that would 404→fail the 403 sweep with a confusing message."""
    registered = {
        (method, _fill(rule.rule))
        for rule in _api_rules()
        for method in (rule.methods & _SUPPORTED_METHODS)
    }
    stale = [
        f"{method} {path}"
        for method, path, _ in PINNED_ADMIN_ENDPOINTS
        if (method, path) not in registered
    ]
    assert not stale, (
        "Pinned admin endpoints with no matching registered route "
        "(refresh PINNED_ADMIN_ENDPOINTS):\n" + "\n".join(stale)
    )


# ── C. Reverse check — pinned list vs. admin-gate call sites ───────────

# Matches the codebase's admin-gate idiom: `_, err = require_admin()`,
# `_, err = _require_admin()`, `user_id, err = require_admin()`,
# `_, admin_err = require_admin()`. Definitions (`def require_admin()`)
# and the alias line (`_require_admin = require_admin`) don't match.
_ADMIN_GATE_CALL_SITE = re.compile(r"=\s*_?require_admin\(\)")


def test__pinned_admin_list__covers_every_require_admin_call_site():
    """A future admin endpoint whose author calls the gate but forgets to
    extend PINNED_ADMIN_ENDPOINTS fails here instead of going untested.
    (And a pinned row whose handler dropped its gate call fails too.)"""
    features_dir = _REPO_ROOT / "dora_api" / "features"
    assert features_dir.is_dir(), f"features dir moved? {features_dir}"

    sites: list[str] = []
    for pyfile in sorted(features_dir.rglob("*.py")):
        # admin_gate.py defines the gate (and shows the idiom in its
        # docstring) but registers no routes — exclude it.
        if pyfile.name == "admin_gate.py":
            continue
        text = pyfile.read_text(encoding="utf-8")
        hits = len(_ADMIN_GATE_CALL_SITE.findall(text))
        if hits:
            sites.append(f"{pyfile.relative_to(_REPO_ROOT)}: {hits}")
    total = sum(int(entry.rsplit(": ", 1)[1]) for entry in sites)

    assert total == len(PINNED_ADMIN_ENDPOINTS), (
        f"Admin-gate call sites in source ({total}) != pinned admin "
        f"endpoints ({len(PINNED_ADMIN_ENDPOINTS)}). Either a new admin "
        "endpoint needs a PINNED_ADMIN_ENDPOINTS row (+ the 403 sweep), or "
        "a pinned handler lost its require_admin() call. Call sites found:\n"
        + "\n".join(sites)
    )
