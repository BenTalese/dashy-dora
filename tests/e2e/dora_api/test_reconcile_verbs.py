"""FU-317 Chunk 3 — reconcile queue + per-entry verb endpoints.

Covers the surface Chunk 5 (SPA) will call — not the sweep itself
(that's Chunk 1's `test_reconcile_receipts.py`). Every test creates a
past-day plan, lets the sweep drop a receipt, then hits
`POST /api/meal-plans/reconcile/<entry_id>` with a verb and asserts
the pool + `consumed_at` + receipt state converged as the proposal §3.2
locked.
"""
from datetime import UTC, date, datetime, timedelta

import requests
from sqlalchemy import text

from dora_api.app import app, db
from tests.support import uuid_bind

BASE = "http://localhost:5170/api"
MEAL_PLANS = f"{BASE}/meal-plans"
APP_SETTINGS = f"{BASE}/app-settings"
RECIPES = f"{BASE}/recipes"


# ── helpers (mostly copied from test_reconcile_receipts.py) ─────────────

def _household_today() -> date:
    return date.fromisoformat(requests.get(f"{MEAL_PLANS}/today").json()["today"])


def _trigger_sweep() -> None:
    resp = requests.get(f"{MEAL_PLANS}/today")
    assert resp.status_code == 200, resp.text


def _set_auto_drain(value: bool) -> None:
    resp = requests.patch(APP_SETTINGS, json={"auto_drain_past_meals": value})
    assert resp.status_code == 200, resp.text


def _pick_recipe() -> dict:
    items = requests.get(f"{RECIPES}?limit=1").json()["items"]
    assert items, "seed expected to have at least one recipe"
    return items[0]


def _get_pool(recipe_id: str) -> int:
    resp = requests.get(f"{RECIPES}/{recipe_id}")
    assert resp.status_code == 200, resp.text
    return int(resp.json()["available_meals"])


def _bump_pool(recipe_id: str, target: int) -> None:
    current = _get_pool(recipe_id)
    delta = target - current
    if delta > 0:
        resp = requests.post(
            f"{RECIPES}/{recipe_id}/cook",
            json={"meals_cooked": delta},
        )
        assert resp.status_code == 200, resp.text


def _create_past_day_entry(recipe_id: str, days_ago: int, servings: int):
    """Create a plan entry that appears to have been scheduled `days_ago`.

    The `POST /api/meal-plans` validator refuses past `scheduled_for`
    values (correctly — the surface is for future planning). To seed
    something the reconcile sweep will pick up we create the entry for
    today, then backdate `scheduled_for` via raw SQL. The plan's
    `start_date` also moves so any downstream range checks stay
    consistent.
    """
    today = _household_today()
    past = today - timedelta(days=days_ago)
    created = requests.post(MEAL_PLANS, json={
        "start_date": today.isoformat(),
        "entries": [{
            "recipe_id": recipe_id,
            "scheduled_for": today.isoformat(),
            "servings": servings,
            "slot": "Dinner",
        }],
    })
    assert created.status_code in (200, 201), created.text
    body = created.json()
    plan_id = body["meal_plan_id"]
    entry_id = body["entries"][0]["meal_plan_entry_id"]
    with app.app_context(), db.engine.begin() as conn:
        conn.execute(
            text('UPDATE "MealPlanEntry" SET scheduled_for = :past WHERE id = :eid'),
            {"past": past.isoformat(), "eid": uuid_bind(entry_id)},
        )
        conn.execute(
            text('UPDATE "MealPlan" SET start_date = :past WHERE id = :pid'),
            {"past": past.isoformat(), "pid": uuid_bind(plan_id)},
        )
    return plan_id, entry_id


def _receipts_for(entry_id: str) -> list[dict]:
    with app.app_context(), db.engine.connect() as conn:
        rows = conn.execute(
            text(
                'SELECT state, original_servings, actual_servings, cooked_on '
                'FROM "MealPlanReconcileReceipt" '
                'WHERE meal_plan_entry_id = :eid '
                'ORDER BY created_at ASC'
            ),
            {"eid": uuid_bind(entry_id)},
        ).all()
    return [
        {"state": r[0], "original_servings": r[1], "actual_servings": r[2],
         "cooked_on": (r[3].isoformat() if hasattr(r[3], "isoformat") else r[3])}
        for r in rows
    ]


def _entry_consumed_at(entry_id: str):
    with app.app_context(), db.engine.connect() as conn:
        row = conn.execute(
            text('SELECT consumed_at FROM "MealPlanEntry" WHERE id = :eid'),
            {"eid": uuid_bind(entry_id)},
        ).first()
    return None if row is None or row[0] is None else str(row[0])


# ── Queue endpoint ──────────────────────────────────────────────────────

def test__queue_lists_only_entries_with_unresolved_latest_receipt(api):
    # Manual mode: the sweep leaves the entry pending (unresolved_manual), which
    # is the queue-filter's job to surface. (Auto mode intentionally does NOT
    # queue its auto-drained entries — covered by the log test below.)
    _set_auto_drain(False)
    recipe = _pick_recipe()
    _bump_pool(recipe["recipe_id"], target=5)
    plan_id, entry_id = _create_past_day_entry(recipe["recipe_id"], days_ago=2, servings=1)
    try:
        _trigger_sweep()
        listing = requests.get(f"{MEAL_PLANS}/reconcile-queue").json()
        assert entry_id in {e["entry_id"] for e in listing["entries"]}, listing
        assert listing["total"] >= 1

        # Resolve the entry → it drops out of the queue.
        resp = requests.post(
            f"{MEAL_PLANS}/reconcile/{entry_id}",
            json={"verb": "cooked"},
        )
        assert resp.status_code == 200, resp.text

        listing_after = requests.get(f"{MEAL_PLANS}/reconcile-queue").json()
        assert entry_id not in {e["entry_id"] for e in listing_after["entries"]}, listing_after
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")


def test__auto_drained_entry_is_not_in_queue_but_appears_in_the_log(api):
    """Owner 2026-08-13 — in auto mode Dora silently drains past meals, so an
    auto-drained entry is NOT pending work (absent from the queue → no chip /
    no nudge), but it IS recorded in the read-only log (`include_resolved=true`)
    with its `unresolved_auto` state so the user can see what happened."""
    _set_auto_drain(True)
    recipe = _pick_recipe()
    _bump_pool(recipe["recipe_id"], target=5)
    plan_id, entry_id = _create_past_day_entry(recipe["recipe_id"], days_ago=2, servings=1)
    try:
        _trigger_sweep()
        queue = requests.get(f"{MEAL_PLANS}/reconcile-queue").json()
        assert entry_id not in {e["entry_id"] for e in queue["entries"]}, queue

        log = requests.get(f"{MEAL_PLANS}/reconcile-queue?include_resolved=true").json()
        assert entry_id in {e["entry_id"] for e in log["entries"]}, log
        assert log["total"] >= 1
        row = next(e for e in log["entries"] if e["entry_id"] == entry_id)
        assert row["receipt"]["state"] == "unresolved_auto", row
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")


def _walk_pages(query: str, limit: int) -> list[str]:
    seen: list[str] = []
    cursor = None
    for _ in range(500):
        url = f"{MEAL_PLANS}/reconcile-queue?limit={limit}{query}"
        page = requests.get(url + (f"&cursor={cursor}" if cursor else "")).json()
        seen.extend(e["entry_id"] for e in page["entries"])
        cursor = page["next_cursor"]
        if cursor is None:
            return seen
    raise AssertionError("pagination never ended")


def test__reconcile_queue__DayStraddlesPageBoundary__EveryEntryListedOnce(api):
    """The cursor used to be the last row's day alone, so the next page's
    `scheduled_for > day` skipped the rest of a day split across pages. It is a
    keyset on (day, id) now — both directions."""
    _set_auto_drain(False)
    recipe = _pick_recipe()
    created = [
        _create_past_day_entry(recipe["recipe_id"], days_ago=2, servings=1)
        for _ in range(3)
    ]
    mine = {entry_id for _, entry_id in created}
    _trigger_sweep()

    queue = _walk_pages("", limit=2)
    log = _walk_pages("&include_resolved=true", limit=2)

    assert mine <= set(queue)
    assert sorted(queue) == sorted(set(queue))
    assert len(queue) == requests.get(f"{MEAL_PLANS}/reconcile-queue").json()["total"]
    assert mine <= set(log)
    assert sorted(log) == sorted(set(log))
    assert len(log) == requests.get(
        f"{MEAL_PLANS}/reconcile-queue?include_resolved=true"
    ).json()["total"]


# ── Verb: cooked (as planned) ───────────────────────────────────────────

def test__verb_cooked_on_auto_drain_on__no_pool_change_and_writes_resolved_confirmed(api):
    """Under auto-drain ON, the sweep has already stamped consumed_at and
    decremented the pool. Cooked-as-planned just writes a resolved_confirmed
    receipt — the world state is already right."""
    _set_auto_drain(True)
    recipe = _pick_recipe()
    _bump_pool(recipe["recipe_id"], target=5)
    plan_id, entry_id = _create_past_day_entry(recipe["recipe_id"], days_ago=2, servings=2)
    try:
        _trigger_sweep()
        pool_after_sweep = _get_pool(recipe["recipe_id"])  # already decremented by 2

        resp = requests.post(
            f"{MEAL_PLANS}/reconcile/{entry_id}",
            json={"verb": "cooked"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["receipt"]["state"] == "resolved_confirmed"
        assert body["new_pool"] == pool_after_sweep, "no pool delta expected"
        assert _entry_consumed_at(entry_id) is not None
        # Two receipts: unresolved_auto (sweep) + resolved_confirmed (verb).
        states = [r["state"] for r in _receipts_for(entry_id)]
        assert states == ["unresolved_auto", "resolved_confirmed"], states
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")


def test__verb_cooked_on_auto_drain_off__stamps_consumed_and_decrements_pool(api):
    """Under auto-drain OFF, the sweep left everything untouched. Cooked
    now applies the drain."""
    _set_auto_drain(False)
    try:
        recipe = _pick_recipe()
        _bump_pool(recipe["recipe_id"], target=5)
        plan_id, entry_id = _create_past_day_entry(recipe["recipe_id"], days_ago=2, servings=2)
        try:
            _trigger_sweep()
            pool_before = _get_pool(recipe["recipe_id"])
            assert _entry_consumed_at(entry_id) is None

            resp = requests.post(
                f"{MEAL_PLANS}/reconcile/{entry_id}",
                json={"verb": "cooked"},
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["receipt"]["state"] == "resolved_confirmed"
            assert body["new_pool"] == pool_before - 2
            assert _entry_consumed_at(entry_id) is not None
        finally:
            requests.delete(f"{MEAL_PLANS}/{plan_id}")
    finally:
        _set_auto_drain(True)


# ── Verb: not_cooked ────────────────────────────────────────────────────

def test__verb_not_cooked_on_auto_drain_on__undoes_the_drain(api):
    """Under auto-drain ON, the sweep drained. `not_cooked` gives it
    back: pool += servings, consumed_at = NULL, receipt =
    resolved_not_cooked."""
    _set_auto_drain(True)
    recipe = _pick_recipe()
    _bump_pool(recipe["recipe_id"], target=5)
    plan_id, entry_id = _create_past_day_entry(recipe["recipe_id"], days_ago=2, servings=2)
    try:
        _trigger_sweep()
        pool_after_sweep = _get_pool(recipe["recipe_id"])  # 5 - 2 = 3

        resp = requests.post(
            f"{MEAL_PLANS}/reconcile/{entry_id}",
            json={"verb": "not_cooked"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["receipt"]["state"] == "resolved_not_cooked"
        assert body["new_pool"] == pool_after_sweep + 2, "drain undone"
        assert _entry_consumed_at(entry_id) is None
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")


# ── Verb: cooked_adjusted ───────────────────────────────────────────────

def test__verb_cooked_adjusted_on_auto_drain_on__reflows_the_pool_delta(api):
    """Sweep drained by original_servings=2. User says 'actually I made 5';
    pool needs to go DOWN by another 3."""
    _set_auto_drain(True)
    recipe = _pick_recipe()
    _bump_pool(recipe["recipe_id"], target=10)
    plan_id, entry_id = _create_past_day_entry(recipe["recipe_id"], days_ago=2, servings=2)
    try:
        _trigger_sweep()
        pool_after_sweep = _get_pool(recipe["recipe_id"])  # 10 - 2 = 8

        resp = requests.post(
            f"{MEAL_PLANS}/reconcile/{entry_id}",
            json={"verb": "cooked_adjusted", "actual_servings": 5},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["receipt"]["state"] == "resolved_adjusted"
        assert body["receipt"]["actual_servings"] == 5
        assert body["new_pool"] == pool_after_sweep - 3
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")


def test__verb_cooked_adjusted_requires_actual_servings(api):
    _set_auto_drain(True)
    recipe = _pick_recipe()
    _bump_pool(recipe["recipe_id"], target=5)
    plan_id, entry_id = _create_past_day_entry(recipe["recipe_id"], days_ago=2, servings=1)
    try:
        _trigger_sweep()
        resp = requests.post(
            f"{MEAL_PLANS}/reconcile/{entry_id}",
            json={"verb": "cooked_adjusted"},
        )
        assert resp.status_code == 400, resp.text
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")


# ── Verb: cooked_later ──────────────────────────────────────────────────

def test__verb_cooked_later_writes_cooked_on_on_receipt(api):
    _set_auto_drain(True)
    recipe = _pick_recipe()
    _bump_pool(recipe["recipe_id"], target=5)
    plan_id, entry_id = _create_past_day_entry(recipe["recipe_id"], days_ago=3, servings=1)
    try:
        _trigger_sweep()
        cooked_on = (_household_today() - timedelta(days=1)).isoformat()
        resp = requests.post(
            f"{MEAL_PLANS}/reconcile/{entry_id}",
            json={"verb": "cooked_later", "cooked_on": cooked_on},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["receipt"]["state"] == "resolved_confirmed"
        assert body["receipt"]["cooked_on"] == cooked_on
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")


# ── Verb: skip ──────────────────────────────────────────────────────────

def test__verb_skip_keeps_entry_in_queue_next_visit(api):
    """`skip` writes a resolved_deferred receipt (small side effect —
    the queue filter treats deferred as still-unresolved)."""
    _set_auto_drain(True)
    recipe = _pick_recipe()
    _bump_pool(recipe["recipe_id"], target=5)
    plan_id, entry_id = _create_past_day_entry(recipe["recipe_id"], days_ago=2, servings=1)
    try:
        _trigger_sweep()
        resp = requests.post(
            f"{MEAL_PLANS}/reconcile/{entry_id}",
            json={"verb": "skip"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["receipt"]["state"] == "resolved_deferred"
        listing = requests.get(f"{MEAL_PLANS}/reconcile-queue").json()
        assert entry_id in {e["entry_id"] for e in listing["entries"]}, listing
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")


def test__verb_skip_on_auto_drain_is_pool_neutral(api):
    """FU-594 — "Skip for now" must NOT touch the pool or consumed_at. The
    sweep already drained this auto-drain-ON entry; skipping it leaves the
    drain in place. The old bug treated skip like "didn't cook" and reversed
    the drain (pool 4 → 5, consumed_at cleared)."""
    _set_auto_drain(True)
    recipe = _pick_recipe()
    _bump_pool(recipe["recipe_id"], target=5)
    plan_id, entry_id = _create_past_day_entry(recipe["recipe_id"], days_ago=2, servings=1)
    try:
        _trigger_sweep()
        pool_after_sweep = _get_pool(recipe["recipe_id"])  # 5 - 1 = 4
        assert _entry_consumed_at(entry_id) is not None, "sweep should stamp consumed_at"

        resp = requests.post(f"{MEAL_PLANS}/reconcile/{entry_id}", json={"verb": "skip"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["new_pool"] == pool_after_sweep, "skip must not move the pool"
        assert _get_pool(recipe["recipe_id"]) == pool_after_sweep
        # consumed_at untouched — skip is not "didn't cook".
        assert _entry_consumed_at(entry_id) is not None
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")


def test__cooked_after_skip_does_not_double_drain(api):
    """FU-594 follow-through — because skip leaves the entry drained, a later
    `cooked` must be a pool no-op, not a second drain. Guards the
    `_effective_drained` deferred branch: reading a deferred entry as
    un-drained would make the following `cooked` drain again (4 → 3)."""
    _set_auto_drain(True)
    recipe = _pick_recipe()
    _bump_pool(recipe["recipe_id"], target=5)
    plan_id, entry_id = _create_past_day_entry(recipe["recipe_id"], days_ago=2, servings=1)
    try:
        _trigger_sweep()
        pool_after_sweep = _get_pool(recipe["recipe_id"])  # 4

        requests.post(f"{MEAL_PLANS}/reconcile/{entry_id}", json={"verb": "skip"})
        assert _get_pool(recipe["recipe_id"]) == pool_after_sweep  # still 4

        r = requests.post(f"{MEAL_PLANS}/reconcile/{entry_id}", json={"verb": "cooked"})
        assert r.status_code == 200, r.text
        assert r.json()["new_pool"] == pool_after_sweep, "cooked after skip must not re-drain"
        assert _get_pool(recipe["recipe_id"]) == pool_after_sweep
        states = [rr["state"] for rr in _receipts_for(entry_id)]
        assert states == ["unresolved_auto", "resolved_deferred", "resolved_confirmed"], states
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")


def test__not_cooked_after_skip_reverses_drain_once(api):
    """FU-594 follow-through — the honesty case. After a neutral skip the entry
    is still drained; saying "didn't cook" must put the servings back exactly
    once (4 → 5) and clear consumed_at."""
    _set_auto_drain(True)
    recipe = _pick_recipe()
    _bump_pool(recipe["recipe_id"], target=5)
    plan_id, entry_id = _create_past_day_entry(recipe["recipe_id"], days_ago=2, servings=1)
    try:
        _trigger_sweep()
        pool_after_sweep = _get_pool(recipe["recipe_id"])  # 4

        requests.post(f"{MEAL_PLANS}/reconcile/{entry_id}", json={"verb": "skip"})
        assert _get_pool(recipe["recipe_id"]) == pool_after_sweep  # still 4

        r = requests.post(f"{MEAL_PLANS}/reconcile/{entry_id}", json={"verb": "not_cooked"})
        assert r.status_code == 200, r.text
        assert r.json()["new_pool"] == pool_after_sweep + 1, "drain reversed exactly once"
        assert _get_pool(recipe["recipe_id"]) == pool_after_sweep + 1
        assert _entry_consumed_at(entry_id) is None
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")


# ── Idempotence + change-of-mind ────────────────────────────────────────

def test__same_verb_replay_is_idempotent(api):
    """Second `cooked` call returns 200 with `idempotent: true` and does
    not add another receipt."""
    _set_auto_drain(True)
    recipe = _pick_recipe()
    _bump_pool(recipe["recipe_id"], target=5)
    plan_id, entry_id = _create_past_day_entry(recipe["recipe_id"], days_ago=2, servings=1)
    try:
        _trigger_sweep()
        r1 = requests.post(f"{MEAL_PLANS}/reconcile/{entry_id}", json={"verb": "cooked"})
        assert r1.json()["idempotent"] is False
        r2 = requests.post(f"{MEAL_PLANS}/reconcile/{entry_id}", json={"verb": "cooked"})
        assert r2.json()["idempotent"] is True
        states = [r["state"] for r in _receipts_for(entry_id)]
        assert states == ["unresolved_auto", "resolved_confirmed"], states
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")


def test__replay_idempotent_when_latest_receipt_created_at_is_ahead(api):
    """FU-529 regression — the monotonic clamp. If the latest existing receipt
    carries a created_at *ahead* of the server clock (the clock-step-backwards
    flake: a fresh verb write stamped at real `now` would otherwise sort older
    than the sweep receipt), the correction must still become the newest
    receipt so a same-verb replay is a no-op, not a duplicate. Without the
    clamp the replay reads the stale `unresolved_auto` as latest and writes a
    third receipt (idempotent: false)."""
    _set_auto_drain(True)
    recipe = _pick_recipe()
    _bump_pool(recipe["recipe_id"], target=5)
    plan_id, entry_id = _create_past_day_entry(recipe["recipe_id"], days_ago=2, servings=1)
    try:
        _trigger_sweep()  # writes the unresolved_auto sweep receipt

        # Force the sweep receipt's created_at a day AHEAD of the server clock.
        ahead = datetime.now(UTC) + timedelta(days=1)
        with app.app_context(), db.engine.begin() as conn:
            conn.execute(
                text('UPDATE "MealPlanReconcileReceipt" SET created_at = :ahead '
                     'WHERE meal_plan_entry_id = :eid AND state = :s'),
                {"ahead": ahead, "eid": uuid_bind(entry_id), "s": "unresolved_auto"},
            )

        first = requests.post(f"{MEAL_PLANS}/reconcile/{entry_id}", json={"verb": "cooked"})
        assert first.status_code == 200, first.text
        assert first.json()["idempotent"] is False

        replay = requests.post(f"{MEAL_PLANS}/reconcile/{entry_id}", json={"verb": "cooked"})
        assert replay.status_code == 200, replay.text
        assert replay.json()["idempotent"] is True, replay.text
        # Exactly two receipts — the clamp kept the resolved one newest, so no
        # duplicate resolved_confirmed was written on replay.
        states = [r["state"] for r in _receipts_for(entry_id)]
        assert states == ["unresolved_auto", "resolved_confirmed"], states
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")


def test__change_of_mind_writes_new_receipt_and_reverses_pool(api):
    """Cooked → resolved_confirmed. Then user says Didn't cook → new
    resolved_not_cooked receipt, pool goes back up, consumed_at NULL."""
    _set_auto_drain(True)
    recipe = _pick_recipe()
    _bump_pool(recipe["recipe_id"], target=5)
    plan_id, entry_id = _create_past_day_entry(recipe["recipe_id"], days_ago=2, servings=1)
    try:
        _trigger_sweep()
        pool_after_sweep = _get_pool(recipe["recipe_id"])  # 5 - 1 = 4

        r1 = requests.post(f"{MEAL_PLANS}/reconcile/{entry_id}", json={"verb": "cooked"})
        assert r1.status_code == 200
        # No pool change vs sweep (still 4).
        assert _get_pool(recipe["recipe_id"]) == pool_after_sweep

        r2 = requests.post(f"{MEAL_PLANS}/reconcile/{entry_id}", json={"verb": "not_cooked"})
        assert r2.status_code == 200
        assert r2.json()["receipt"]["state"] == "resolved_not_cooked"
        # Pool restored (4 + 1 = 5).
        assert _get_pool(recipe["recipe_id"]) == pool_after_sweep + 1
        assert _entry_consumed_at(entry_id) is None
        states = [r["state"] for r in _receipts_for(entry_id)]
        assert states == ["unresolved_auto", "resolved_confirmed", "resolved_not_cooked"], states
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")


# ── Validation + auth ───────────────────────────────────────────────────

def test__unknown_verb_returns_400(api):
    _set_auto_drain(True)
    recipe = _pick_recipe()
    _bump_pool(recipe["recipe_id"], target=5)
    plan_id, entry_id = _create_past_day_entry(recipe["recipe_id"], days_ago=2, servings=1)
    try:
        _trigger_sweep()
        resp = requests.post(
            f"{MEAL_PLANS}/reconcile/{entry_id}",
            json={"verb": "hallucinate"},
        )
        assert resp.status_code == 400, resp.text
    finally:
        requests.delete(f"{MEAL_PLANS}/{plan_id}")


def test__unknown_entry_id_returns_404(api):
    resp = requests.post(
        f"{MEAL_PLANS}/reconcile/00000000-0000-0000-0000-000000000000",
        json={"verb": "cooked"},
    )
    assert resp.status_code == 404, resp.text
