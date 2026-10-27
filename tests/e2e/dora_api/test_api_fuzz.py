"""Systematic "4xx, never 500" robustness fuzz over the whole /api surface.

Complements the three earlier sweeps (happy paths, auth enforcement, delete
integrity) with hostile-input probing. Four layers:

A. **Malformed-body sweep** — every POST/PATCH/PUT rule gets an empty JSON
   body, syntactically broken JSON, a JSON array where an object is
   expected, and `{}`. Body deserialisation happens in middleware
   (dora_api/infrastructure/middleware.py `deserialise_web_request`) BEFORE
   the handler, so schema'd endpoints should 400 there; schema-less action
   POSTs run their handler with no body. NOTE: the middleware does
   `request.get_json(silent=True) or {}`, so empty / broken / `[]` bodies
   all collapse to `{}` before validation — a schema where `{}` is valid
   will run the handler and may legitimately 2xx (state mutations are fine;
   the per-test DB snapshot rollback isolates them). The invariant asserted
   is therefore **never 5xx**, not "always 4xx".

B. **Garbage-query-param sweep** — every GET rule with hostile pagination,
   sort, and filter values. Never 5xx.

C. **Path-param garbage sweep** — every rule with path params, substituting
   a non-UUID string, a 2000-char string, and a well-formed-but-nonexistent
   UUID. Routes use plain string converters (`/<stock_item_id>`), so
   `UUID(...)` ValueErrors inside handlers leak as 500s — the FU-528
   str/UUID family this sweep exists to catch. Never 5xx. (Many handlers
   legitimately return 200 + a `*_not_found` flag for missing ids — that
   response-model idiom is why the sweep can't demand strict 404.)

D. **Wrong-type field fuzz on core creates** — for the core create
   endpoints, each field is sent with a deliberately wrong JSON type and the
   response must be the middleware's 400 problem-details envelope.
   ("Stock level" from the original brief has no create endpoint — stock
   levels are a fixed seeded vocabulary, GET-only — so stock-locations
   stands in as the eighth surface.)

Structure notes (mirrors test_route_auth_enforcement.py): routes register
inside `startup()` (run by the session-scoped `api` fixture), so
`app.url_map` is EMPTY at collection time. Each sweep is one test that
iterates the url_map at runtime and accumulates per-case failures into a
single assertion message.

Auth-surface hazards handled inline:
- the pre-auth rate limiter is in-memory per-IP (auth_helpers._buckets) and
  survives the per-test DB rollback — it is drained before/after touching
  /api/auth so later tests don't inherit 429s;
- POST /api/auth/logout with any body succeeds and kills the shared admin
  session the whole suite rides on — the sweeps re-login after fuzzing any
  /api/auth rule.
"""
import re
import time

import pytest
import requests

from dora_api.app import app
from dora_api.infrastructure.middleware import PUBLIC_ENDPOINTS

BASE = "http://localhost:5170"

# Fixed, well-formed, guaranteed-nonexistent UUID (same trick as the auth
# sweep — the seeded test DB only contains freshly generated uuid4 ids).
_MISSING_UUID = "0f0e0d0c-0b0a-4990-8877-665544332211"

_DUMMY_BY_CONVERTER = {
    "int": "1",
    "float": "1.0",
    "path": "dummy-path",
}

_SUPPORTED_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})
_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})

# Per-request wall-clock ceiling — "never a hang". In-process test-client
# dispatch is single-threaded and synchronous; anything that takes multiple
# seconds on the seeded test DB is a runaway (network call, unbounded scan).
_SLOW_SECONDS = 10.0


def _fill(rule_template: str, value: str = _MISSING_UUID) -> str:
    """Substitute a concrete dummy for every <converter:name> path param."""
    def _replace(match: re.Match) -> str:
        spec = match.group(1)
        converter = spec.split(":", 1)[0] if ":" in spec else "string"
        return _DUMMY_BY_CONVERTER.get(converter, value)

    return re.sub(r"<([^>]+)>", _replace, rule_template)


def _strip_converters(rule: str) -> str:
    """`/x/<uuid:foo_id>` -> `/x/<foo_id>`. Lets the bare pinned templates in
    KNOWN_FU528_UUID_500_RULES match a url_map that now carries `<uuid:...>`
    converters (post FU-532). Leaves converter-less params (`<alert_id>`)
    untouched."""
    return re.sub(r"<[a-z]+:([^>]+)>", r"<\1>", rule)


def _api_rules():
    """Every registered rule under /api/ (skips the SPA catch-all + static)."""
    return sorted(
        (rule for rule in app.url_map.iter_rules()
         if rule.rule.startswith("/api/")),
        key=lambda rule: rule.rule,
    )


def _drain_auth_buckets() -> None:
    """Reset the in-memory pre-auth rate limiter. Same rationale as
    test_route_auth_enforcement._register_non_admin: process memory survives
    the per-test DB rollback, and repeated fuzz hits on /api/auth would 429
    both this sweep's later cases and every subsequent auth test."""
    from dora_api.infrastructure import auth_helpers
    with auth_helpers._buckets_lock:
        auth_helpers._buckets.clear()


def _relogin() -> None:
    """Restore the shared admin session on the conftest-adapted client.
    Needed after fuzzing /api/auth rules: POST /api/auth/logout treats any
    body as a plain logout and clears the session cookie the entire
    module-level `requests.*` adapter rides on."""
    _drain_auth_buckets()
    response = requests.post(
        f"{BASE}/api/auth/login", json={"username": "dora", "password": "dora"}
    )
    assert response.status_code == 200, (
        f"re-login after auth fuzz failed ({response.status_code}): "
        f"{response.text[:200]}"
    )


def _is_auth_rule(rule) -> bool:
    return rule.rule.startswith("/api/auth")


def _probe(method: str, url: str, failures: list[str], label: str, **kwargs):
    """Fire one fuzz case; record a failure line on 5xx or a hang."""
    started = time.perf_counter()
    response = getattr(requests, method.lower())(f"{BASE}{url}", **kwargs)
    elapsed = time.perf_counter() - started
    if response.status_code >= 500:
        failures.append(
            f"{method} {url} [{label}] -> {response.status_code}: "
            f"{response.text[:300]}"
        )
    elif elapsed > _SLOW_SECONDS:
        failures.append(
            f"{method} {url} [{label}] -> {response.status_code} but took "
            f"{elapsed:.1f}s (hang-adjacent; ceiling {_SLOW_SECONDS}s)"
        )
    return response


# ─────────────────────────────────────────────────────────────────────────
# KNOWN 500s — REAL BUGS, loudly excluded from the broad sweeps and pinned
# by dedicated strict-xfail tests further down. When a bug is fixed, its
# xfail test XPASSes (strict → suite failure) — delete the exclusion AND
# the xfail together so the broad sweep re-owns the case.
# ─────────────────────────────────────────────────────────────────────────

# BUG 1 — the FU-528 str/UUID family, app-wide. FIXED by FU-532: every
# entity-id path param now uses Flask's built-in `<uuid:...>` converter, so a
# non-UUID segment 404s at routing before any handler/DB touch. Historically
# each (method, rule) below 500'd when its path param wasn't parseable as a
# UUID: routes used plain string converters, handlers/repositories bound the
# raw string straight into a UUID-typed column, and sqlalchemy_utils
# UUIDType._coerce fell back to `uuid.UUID(bytes=value)` → ValueError →
# StatementError → 500. This frozenset is retained as the iteration list for
# the live regression guard `test__non_uuid_path_params__return_4xx_not_500`
# below (templates stored bare; the guard strips the `<uuid:>` converter off
# the live url_map to match). Do not delete it.
KNOWN_FU528_UUID_500_RULES: frozenset[tuple[str, str]] = frozenset({
    ("DELETE", "/api/categories/<category_id>"),
    ("DELETE", "/api/cuisines/<cuisine_id>"),
    ("DELETE", "/api/data/barcodes/<barcode_id>"),
    ("DELETE", "/api/dietary-tags/<dietary_tag_id>"),
    ("PATCH", "/api/dietary-tags/<dietary_tag_id>"),
    ("DELETE", "/api/ingestion-sources/<source_id>"),
    ("PATCH", "/api/ingestion-sources/<source_id>"),
    ("GET", "/api/ingestion-sources/<source_id>/store-mappings"),
    ("DELETE", "/api/ingestion-sources/<source_id>/store-mappings/<mapping_id>"),
    ("DELETE", "/api/locations/<location_id>"),
    ("PATCH", "/api/locations/<location_id>"),
    ("DELETE", "/api/meal-plan-template-sets/<set_id>"),
    ("GET", "/api/meal-plan-template-sets/<set_id>"),
    ("PATCH", "/api/meal-plan-template-sets/<set_id>"),
    ("DELETE", "/api/meal-plan-templates/<template_id>"),
    ("GET", "/api/meal-plan-templates/<template_id>"),
    ("PATCH", "/api/meal-plan-templates/<template_id>"),
    ("POST", "/api/meal-plan-templates/<template_id>/clone"),
    ("DELETE", "/api/meal-plans/<meal_plan_id>"),
    ("PATCH", "/api/meal-plans/<meal_plan_id>"),
    ("GET", "/api/meal-plans/<meal_plan_id>/ingredients"),
    ("GET", "/api/meal-plans/<meal_plan_id>/print-view"),
    ("GET", "/api/meal-plans/<meal_plan_id>/swap-suggestions"),
    ("DELETE", "/api/meal-slots/<meal_slot_id>"),
    ("PATCH", "/api/products/<product_id>"),
    ("GET", "/api/products/<product_id>/image"),
    ("DELETE", "/api/recipe-collections/<recipe_collection_id>"),
    ("DELETE", "/api/recipes/<recipe_id>"),
    ("GET", "/api/recipes/<recipe_id>"),
    ("PATCH", "/api/recipes/<recipe_id>"),
    ("GET", "/api/recipes/<recipe_id>/export"),
    ("GET", "/api/recipes/<recipe_id>/image"),
    ("POST", "/api/recipes/<recipe_id>/new-version"),
    ("GET", "/api/recipes/<recipe_id>/print-view"),
    ("GET", "/api/recipes/<recipe_id>/step-images/<image_id>"),
    ("DELETE", "/api/shopping-list-templates/<template_id>"),
    ("GET", "/api/shopping-list-templates/<template_id>"),
    ("PATCH", "/api/shopping-list-templates/<template_id>"),
    ("POST", "/api/shopping-list-templates/<template_id>/instantiate"),
    ("DELETE", "/api/shopping-list-templates/<template_id>/lines/<line_id>"),
    ("PATCH", "/api/shopping-list-templates/<template_id>/lines/<line_id>"),
    ("POST", "/api/shopping-list-templates/from-list/<source_list_id>"),
    ("DELETE", "/api/shopping-lists/<shopping_list_id>"),
    ("GET", "/api/shopping-lists/<shopping_list_id>"),
    ("PATCH", "/api/shopping-lists/<shopping_list_id>"),
    ("DELETE", "/api/shopping-lists/<shopping_list_id>/attachments/<attachment_id>"),
    ("GET", "/api/shopping-lists/<shopping_list_id>/attachments/<attachment_id>"),
    ("POST", "/api/shopping-lists/<shopping_list_id>/clear"),
    ("POST", "/api/shopping-lists/<shopping_list_id>/copy"),
    ("POST", "/api/shopping-lists/<shopping_list_id>/finish"),
    ("DELETE", "/api/shopping-lists/<shopping_list_id>/lines/<line_id>"),
    ("PATCH", "/api/shopping-lists/<shopping_list_id>/lines/<line_id>"),
    ("DELETE", "/api/shopping-lists/<shopping_list_id>/lines/by-stock-item/<stock_item_id>"),
    ("GET", "/api/shopping-lists/<shopping_list_id>/print-view"),
    ("POST", "/api/shopping-lists/<shopping_list_id>/start"),
    ("POST", "/api/shopping-lists/<shopping_list_id>/trim-to-budget"),
    ("DELETE", "/api/stock-groups/<stock_group_id>"),
    ("DELETE", "/api/stock-items/<stock_item_id>"),
    ("PATCH", "/api/stock-items/<stock_item_id>"),
    ("GET", "/api/stock-items/<stock_item_id>/buy-verdict"),
    ("POST", "/api/stock-items/<stock_item_id>/check"),
    ("GET", "/api/stock-items/<stock_item_id>/detail"),
    ("PATCH", "/api/stock-items/<stock_item_id>/move"),
    ("DELETE", "/api/stock-items/<stock_item_id>/preferred-buys/<preferred_buy_id>"),
    ("GET", "/api/stock-items/<stock_item_id>/price-history"),
    ("DELETE", "/api/stock-items/<stock_item_id>/price-observations/<observation_id>"),
    ("GET", "/api/stock-items/<stock_item_id>/qr"),
    ("POST", "/api/stock-items/<stock_item_id>/snooze"),
    ("DELETE", "/api/stock-items/<stock_item_id>/substitutes/<substitute_id>"),
    ("DELETE", "/api/stock-locations/<stock_location_id>"),
    ("PATCH", "/api/stock-locations/<stock_location_id>"),
    ("DELETE", "/api/stores/<store_id>"),
    ("PATCH", "/api/stores/<store_id>"),
    ("GET", "/api/stores/<store_id>/image"),
    ("DELETE", "/api/tools/<tool_id>"),
    ("DELETE", "/api/users/<user_id>"),
    ("PATCH", "/api/users/<user_id>"),
    ("GET", "/api/users/<user_id>/image"),
    ("POST", "/api/users/<user_id>/reset-password"),
})
_FU528_LABELS = frozenset({"non-uuid", "very-long"})

# BUG 2 — GET /api/recipes/unlinked-ingredients 500s on EVERY request
# (garbage params irrelevant): unlinked_ingredients.py:103 queries
# `EntityField(RecipeIngredient, "stock_item_id")` but the imperative
# mapping (persistence/table_mappings.py:1288) names the attribute
# `_stock_item_id` → AttributeError at query build. The POST bulk-link
# path (:166) has the same bug but is shielded by middleware validation
# in this suite. Excluded from the query sweep for ALL labels.
_BROKEN_UNLINKED_INGREDIENTS = "/api/recipes/unlinked-ingredients"

# BUG 3 — GET /api/meal-plans/reconcile-queue 500s whenever the response
# paginates (rows > limit): reconcile.py:303 hands `_encode_cursor` the
# raw-SQL row's `scheduled_for`, which SQLite returns as a str →
# `AttributeError: 'str' object has no attribute 'isoformat'`
# (reconcile.py:243). `_row_to_dict` (:334) defends against exactly this;
# `_encode_cursor` doesn't. The sweep trips it via `limit=-3` → clamped
# to 1 < seeded queue size. Not garbage-specific: `?limit=1` (a perfectly
# valid request) reproduces. Excluded for the "surface-garbage" label.
_BROKEN_RECONCILE_QUEUE = "/api/meal-plans/reconcile-queue"


def _query_sweep_excluded(url: str, label: str) -> bool:
    if url == _BROKEN_UNLINKED_INGREDIENTS:
        return True  # BUG 2 — 500s regardless of params
    if url == _BROKEN_RECONCILE_QUEUE and label == "surface-garbage":
        return True  # BUG 3 — limit=-3 clamps to 1 and trips cursor encode
    return False


# ── A. Malformed-body sweep ────────────────────────────────────────────


_MALFORMED_BODIES: list[tuple[str, dict]] = [
    ("empty-body", {"data": b"", "content_type": "application/json"}),
    ("broken-json", {"data": b"{nope", "content_type": "application/json"}),
    ("array-not-object", {"json": []}),
    ("empty-object", {"json": {}}),
]


def test__malformed_body_on_every_mutating_route__never_500s(api):
    failures: list[str] = []
    swept = 0

    for rule in _api_rules():
        methods = sorted(rule.methods & _BODY_METHODS)
        if not methods:
            continue
        url = _fill(rule.rule)
        for method in methods:
            for label, kwargs in _MALFORMED_BODIES:
                swept += 1
                if _is_auth_rule(rule):
                    _drain_auth_buckets()
                _probe(method, url, failures, label, **kwargs)
        if _is_auth_rule(rule):
            # logout / password-change fuzz may have dropped the session
            _relogin()

    assert swept >= 200, (
        f"Malformed-body sweep only covered {swept} cases — url_map looks "
        "under-populated; did route registration move out of startup()?"
    )
    assert not failures, (
        f"{len(failures)} mutating route case(s) 500'd on a malformed body "
        "(each is a handler-level validation gap — middleware collapses "
        "empty/broken/array bodies to {} before validation):\n"
        + "\n".join(failures)
    )


# ── B. Garbage-query-param sweep ───────────────────────────────────────


_GARBAGE_QUERIES = [
    ("negative-paging", "page=-1&page_size=0"),
    ("nonint-page", "page=notanint&page_size=notanint"),
    ("huge-page-size", "page=1&page_size=999999"),
    ("proto-sort", "sort=__proto__&order=sideways&sort_by=__proto__"),
    (
        "surface-garbage",
        "cookable=banana&expiring_within_days=-5&types=%3BDROP%20TABLE"
        "&status=;DROP&days=NaN&limit=-3&q=%00%27%22&search=%27--"
        "&from=13th-of-never&to=0000-00-00&window=-7&kind=42",
    ),
]


def test__garbage_query_params_on_every_get_route__never_500s(api):
    failures: list[str] = []
    swept = 0

    for rule in _api_rules():
        if "GET" not in rule.methods:
            continue
        url = _fill(rule.rule)
        for label, query in _GARBAGE_QUERIES:
            if _query_sweep_excluded(url, label):
                continue  # KNOWN BUG exclusion — see BUG 2 / BUG 3 above
            swept += 1
            _probe("GET", f"{url}?{query}", failures, label)

    assert swept >= 100, (
        f"Garbage-query sweep only covered {swept} cases — url_map looks "
        "under-populated; did route registration move out of startup()?"
    )
    assert not failures, (
        f"{len(failures)} GET route case(s) 500'd on garbage query params:\n"
        + "\n".join(failures)
    )


# ── C. Path-param garbage sweep ────────────────────────────────────────


_PATH_PARAM_VALUES = [
    ("non-uuid", "not-a-uuid"),
    ("very-long", "x" * 2000),
    ("missing-uuid", _MISSING_UUID),
]


def test__garbage_path_params_on_every_parameterised_route__never_500s(api):
    failures: list[str] = []
    swept = 0

    for rule in _api_rules():
        if "<" not in rule.rule:
            continue
        for method in sorted(rule.methods & _SUPPORTED_METHODS):
            for label, value in _PATH_PARAM_VALUES:
                if (label in _FU528_LABELS
                        and (method, rule.rule) in KNOWN_FU528_UUID_500_RULES):
                    continue  # KNOWN BUG exclusion — FU-528 family (BUG 1)
                url = _fill(rule.rule, value)
                swept += 1
                if _is_auth_rule(rule):
                    _drain_auth_buckets()
                # Mutating methods get `{}` — schemas where `{}` is invalid
                # will 400 in middleware before the handler touches the path
                # param (acceptable partial coverage; still must never 500).
                kwargs = {"json": {}} if method in _BODY_METHODS else {}
                _probe(method, url, failures, label, **kwargs)
        if _is_auth_rule(rule):
            _relogin()

    assert swept >= 150, (
        f"Path-param sweep only covered {swept} cases — url_map looks "
        "under-populated; did route registration move out of startup()?"
    )
    assert not failures, (
        f"{len(failures)} parameterised route case(s) 500'd on garbage path "
        "params (non-uuid / long-string leaks = the FU-528 str/UUID family):\n"
        + "\n".join(failures)
    )


# ── D. Wrong-type field fuzz on core creates ───────────────────────────
#
# For each core create endpoint: a known-valid baseline body, then one
# request per field with that field's value replaced by a wrong-typed
# value. The middleware deserialises against the handler's pydantic model
# and must answer 400 with the problem-details envelope — never 500, and
# never silently accept the wrong type on a required field.
#
# Baselines use nonexistent UUIDs for foreign keys — fine, because the
# wrong-type requests are rejected by pydantic BEFORE any lookup runs.

_CORE_CREATE_FUZZ: list[tuple[str, dict, dict]] = [
    # (path, valid-baseline-body, {field: wrong-typed value})
    (
        "/api/stock-items",
        {"name": "fuzz item", "stock_level_id": _MISSING_UUID},
        {
            "name": 12345,
            "stock_level_id": {"unexpected": "object"},
            "stock_location_id": 3.14,
            "expiry_date": {"y": 2026},
            "is_essential": "banana",
            "is_open": [],
        },
    ),
    (
        "/api/recipes",
        {"name": "fuzz recipe"},
        {
            "name": None,
            "servings": "lots",
            "cook_time_minutes": {"m": 5},
            "kcal": "many",
            "ingredients": "not-a-list",
            "steps": {"not": "a-list"},
            "dietary_tag_ids": "not-a-list",
            "image": 42,
        },
    ),
    (
        "/api/shopping-lists",
        {"name": "fuzz list"},
        {
            "name": {"nested": True},
            "planned_shop_date": "13th of never",
        },
    ),
    (
        "/api/meal-plans",
        {"start_date": "2026-07-13"},
        {
            "start_date": {"not": "a-date"},
            "name": ["list", "not", "string"],
            "entries": "not-a-list",
        },
    ),
    (
        "/api/stores",
        {"name": "fuzz store"},
        {
            "name": 99,
            "image": {"blob": True},
        },
    ),
    (
        "/api/locations",
        {"name": "fuzz zone", "kind": "zone"},
        {
            "name": [],
            "kind": 42,
            "parent_id": "definitely-not-a-uuid",
            "sequence": "first",
        },
    ),
    (
        "/api/products",
        {
            "is_active": True, "is_available": True, "store_name": "Fuzz Mart",
            "name": "fuzz product", "price_now": 1.5, "price_was": 2.0,
            "size": "500g", "size_unit": "g", "size_value": 500.0,
        },
        {
            "name": {"x": 1},
            "store_name": None,
            "price_now": "free",
            "price_was": [2],
            "size_value": "big",
            "is_active": "banana",
            "is_available": {"y": True},
        },
    ),
    # "stock level" has no create endpoint (fixed seeded vocabulary,
    # GET-only) — stock-locations is the eighth core create surface.
    (
        "/api/stock-locations",
        {"name": "fuzz shelf"},
        {"name": 7},
    ),
]


def test__wrong_typed_fields_on_core_creates__reject_with_400_problem_details(api):
    failures: list[str] = []
    swept = 0

    for path, baseline, wrong_fields in _CORE_CREATE_FUZZ:
        for field, bad_value in wrong_fields.items():
            swept += 1
            body = dict(baseline)
            body[field] = bad_value
            response = requests.post(f"{BASE}{path}", json=body)
            if response.status_code >= 500:
                failures.append(
                    f"POST {path} field={field} value={bad_value!r} -> "
                    f"{response.status_code}: {response.text[:300]}"
                )
                continue
            if response.status_code not in (400, 422):
                failures.append(
                    f"POST {path} field={field} value={bad_value!r} -> "
                    f"{response.status_code} (wrong type silently accepted?)"
                )
                continue
            # problem-details contract: application/problem+json with a
            # per-field errors map naming the offending field.
            content_type = response.headers.get("Content-Type", "")
            payload = response.json() or {}
            if "problem+json" not in content_type or "errors" not in payload:
                failures.append(
                    f"POST {path} field={field} -> {response.status_code} but "
                    f"not a problem-details body (Content-Type={content_type}, "
                    f"keys={sorted(payload)})"
                )
            elif not any(field in key for key in payload["errors"]):
                failures.append(
                    f"POST {path} field={field} -> 400 but errors map "
                    f"doesn't name the field: {sorted(payload['errors'])}"
                )

    assert swept >= 30
    assert not failures, (
        f"{len(failures)} wrong-typed-field case(s) escaped the 400 "
        "problem-details contract:\n" + "\n".join(failures)
    )


# ── Known-bug pins (strict xfail — XPASS when fixed, then delete the
#    matching exclusion above so the broad sweep re-owns the case) ──────


def test__non_uuid_path_params__return_4xx_not_500(api):
    """Live regression guard for the FU-532 fix. Loops the (formerly) FU-528
    rule list with `not-a-uuid` and demands 4xx (never 5xx). The fix converted
    every entity-id path param to Flask's built-in `<uuid:...>` converter, so a
    non-UUID segment now 404s at routing before any handler/DB touch. This test
    was a strict xfail while the family 500'd; it is now a standing guard.
    KNOWN_FU528_UUID_500_RULES is retained purely as the iteration list of the
    routes this guard exercises — do not delete it."""
    still_500: list[str] = []
    # KNOWN_FU528_UUID_500_RULES stores bare templates (e.g.
    # `/api/categories/<category_id>`), but the FU-532 fix means url_map now
    # carries the converter (`/api/categories/<uuid:category_id>`). Strip the
    # converter prefix off each live rule so the pinned bare templates still
    # resolve — the guard's job is to prove the family 4xxes, not to track the
    # converter spelling.
    rules_by_key = {
        (method, _strip_converters(rule.rule)): rule
        for rule in _api_rules()
        for method in rule.methods & _SUPPORTED_METHODS
    }
    for method, template in sorted(KNOWN_FU528_UUID_500_RULES):
        assert (method, template) in rules_by_key, (
            f"pinned FU-528 rule vanished from url_map: {method} {template} "
            "— refresh KNOWN_FU528_UUID_500_RULES"
        )
        url = _fill(template, "not-a-uuid")
        kwargs = {"json": {}} if method in _BODY_METHODS else {}
        response = getattr(requests, method.lower())(f"{BASE}{url}", **kwargs)
        if response.status_code >= 500:
            still_500.append(f"{method} {url} -> {response.status_code}")
    assert not still_500, (
        f"{len(still_500)}/{len(KNOWN_FU528_UUID_500_RULES)} FU-528 routes "
        "still 500 on a non-UUID path param:\n" + "\n".join(still_500)
    )


def test__unlinked_ingredients__does_not_500(api):
    """Regression for the BUG-2 fix (2026-07-12): the endpoint 500'd on
    every request because unlinked_ingredients.py referenced the FK as
    `stock_item_id`, but the imperative mapping binds it to `_stock_item_id`
    → AttributeError. Fixed to `_stock_item_id`; this guards the fix."""
    response = requests.get(f"{BASE}{_BROKEN_UNLINKED_INGREDIENTS}")
    assert response.status_code < 500, (
        f"GET {_BROKEN_UNLINKED_INGREDIENTS} -> {response.status_code}: "
        f"{response.text[:300]}"
    )
    assert response.status_code == 200, response.text
    # Shape sanity: the DTO must carry the unlinked set (was never reachable
    # before the fix, so no prior test ever exercised the response body).
    body = response.json()
    assert isinstance(body, dict)


def test__reconcile_queue__paginates_without_500(api):
    """Regression for the BUG-3 fix (2026-07-12): _encode_cursor called
    .isoformat() on `scheduled_for`, which the raw-SQL row hands back as a
    str on SQLite → AttributeError → 500 whenever the queue paginated
    (limit=1 with >1 seeded row forces the next_cursor branch; any real
    household with >50 unresolved entries hits it). Fixed by coercing str →
    date at the boundary (R-005 portability). This guards the fix."""
    response = requests.get(f"{BASE}{_BROKEN_RECONCILE_QUEUE}?limit=1")
    assert response.status_code < 500, (
        f"GET {_BROKEN_RECONCILE_QUEUE}?limit=1 -> {response.status_code}: "
        f"{response.text[:300]}"
    )
    assert response.status_code == 200, response.text
    # The next_cursor must be present + round-trip decodable when the queue
    # has more rows than the page limit — proving the cursor actually encoded.
    body = response.json()
    if body.get("next_cursor"):
        follow = requests.get(
            f"{BASE}{_BROKEN_RECONCILE_QUEUE}?limit=1&cursor={body['next_cursor']}"
        )
        assert follow.status_code == 200, follow.text
