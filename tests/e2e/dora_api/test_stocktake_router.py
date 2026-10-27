"""FU-519 item 2 — stocktake HTTP lifecycle e2e
(`dora_api/features/stocktake/stocktake.py`).

  GET  /api/stocktake/queue                       — overdue items
  POST /api/stock-items/<id>/check                — confirm level (bumps
                                                    last_checked_at, clears Push)
  POST /api/stock-items/<id>/snooze               — Push 3 days
  POST /api/stocktake/bulk-check                  — body {ids}

The band/auto-tuning *logic* is unit-tested in `tests/test_stocktake_cadence.py`
— this file drives the HTTP lifecycle only. A fresh item's overdue baseline is
its creation moment (grace period = one band), so tests that need an overdue
item backdate `last_checked_at` via targeted SQL (the sanctioned state-setup
escape hatch, see `tests/support.uuid_bind`).
"""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import requests
from sqlalchemy import text

from dora_api.app import app, db
from tests.factories import make_stock_item
from tests.support import assert_problem, uuid_bind

BASE = "http://localhost:5170/api"
QUEUE = f"{BASE}/stocktake/queue"
BULK_CHECK = f"{BASE}/stocktake/bulk-check"

QUEUE_ITEM_KEYS = {
    "stock_item_id", "name", "stock_level_name", "stock_location_name",
    "cadence_band", "cadence_days", "last_checked_at", "overdue_days",
    # 2026-08-20: the Stocktake button's glow is gated on essentials, so the
    # flag has to travel with the queue rather than the client looking it up.
    "is_essential",
    # Chunk 5 / D-1: belief ranks the queue, so each row carries why it sits
    # where it does — the runner explains the order in place instead of the
    # user meeting a reshuffle with no cause.
    "check_rank", "belief_band", "belief_confidence", "belief_reason",
}


#region ---------------- helpers ----------------


def _token() -> str:
    return f"zqs{uuid4().hex[:8]}"


def _stocked_level_id() -> str:
    levels = requests.get(f"{BASE}/stock-levels").json()["items"]
    return next(l for l in levels if l["sequence"] == 0)["stock_level_id"]


def _queue_ids(limit: int = 500) -> dict[str, dict]:
    resp = requests.get(QUEUE, params={"limit": limit})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {"items", "total", "essential_total", "ranked_by"}
    return {item["stock_item_id"]: item for item in body["items"]}


def _unmute(stock_item_id: str) -> None:
    """Pin the Mute off explicitly. API-created items are born *unmuted*
    since 2026-08-17 (`stocktake_alerts_are_enabled=True` in
    create_stock_item.py), so this is now a guarantee rather than a flip —
    kept so these tests state the precondition they rely on instead of
    inheriting it from a default that has already moved once."""
    resp = requests.patch(
        f"{BASE}/stock-items/{stock_item_id}",
        json={"stocktake_alerts_are_enabled": True},
    )
    assert resp.status_code == 204, resp.text


def _backdate_last_checked(stock_item_id: str, days_ago: int) -> None:
    past = datetime.now(UTC) - timedelta(days=days_ago)
    with app.app_context(), db.engine.begin() as conn:
        conn.execute(
            text('UPDATE "StockItem" SET last_checked_at = :ts WHERE id = :id'),
            {
                "ts": past.replace(tzinfo=None).isoformat(" "),
                "id": uuid_bind(stock_item_id),
            },
        )


def _overdue_item(name: str, *, days_ago: int = 20) -> str:
    """An unmuted Stocked item last touched `days_ago` days ago — past the
    default fortnightly band (14d), so it queues with overdue = days_ago - 14."""
    item = make_stock_item(stock_level_id=_stocked_level_id(), name=name)
    _unmute(item["stock_item_id"])
    _backdate_last_checked(item["stock_item_id"], days_ago)
    return item["stock_item_id"]


#endregion helpers

#region ---------------- queue ----------------


def test__get_stocktake_queue__FreshItem__GracePeriodKeepsItOut(api):
    item = make_stock_item(stock_level_id=_stocked_level_id(), name=f"{_token()} salt")
    _unmute(item["stock_item_id"])

    queued = _queue_ids()

    # Baseline = creation moment; a brand-new item has a full band of grace,
    # never "top of the queue on turn zero".
    assert item["stock_item_id"] not in queued


def test__get_stocktake_queue__ItemPastFortnightlyBand__QueuedWithOverdueDays(api):
    token = _token()
    item_id = _overdue_item(f"{token} flour", days_ago=20)

    queued = _queue_ids()

    entry = queued[item_id]
    assert set(entry.keys()) == QUEUE_ITEM_KEYS
    assert entry["name"] == f"{token} flour"
    assert entry["cadence_band"] == "fortnightly"  # baseline default band
    assert entry["cadence_days"] == 14
    assert entry["overdue_days"] == 6  # 20 days elapsed - 14 day band
    assert entry["last_checked_at"] is not None
    assert entry["stock_level_name"] is not None
    assert entry["is_essential"] is False


def test__get_stocktake_queue__EssentialOverdue__CountedInEssentialTotal(api):
    """The Stocktake button glows only when an **essential** is due (owner call,
    2026-08-20), so `essential_total` is a real contract and not a convenience:
    it must count essentials across the whole overdue set, and stay separate
    from `total`."""
    token = _token()
    plain_id = _overdue_item(f"{token} plain", days_ago=20)
    essential_id = _overdue_item(f"{token} essential", days_ago=20)
    resp = requests.patch(
        f"{BASE}/stock-items/{essential_id}", json={"is_essential": True},
    )
    assert resp.status_code == 204, resp.text

    body = requests.get(QUEUE, params={"limit": 500}).json()
    queued = {item["stock_item_id"]: item for item in body["items"]}

    assert queued[essential_id]["is_essential"] is True
    assert queued[plain_id]["is_essential"] is False
    # Other tests share the database, so assert the relationship rather than a
    # literal: every essential in the queue is counted, and non-essentials are
    # not, which is the property the glow depends on.
    essentials_on_page = sum(
        1 for item in body["items"] if item["is_essential"]
    )
    assert body["essential_total"] >= essentials_on_page >= 1
    assert body["essential_total"] <= body["total"]


def test__get_stocktake_queue__EssentialItem__BandBumpedOneStepFaster(api):
    token = _token()
    item = make_stock_item(
        stock_level_id=_stocked_level_id(), name=f"{token} coffee", is_essential=True,
    )
    _unmute(item["stock_item_id"])
    _backdate_last_checked(item["stock_item_id"], 10)

    queued = _queue_ids()

    # Essential bumps fortnightly → weekly; 10 days elapsed - 7 = 3 overdue.
    entry = queued[item["stock_item_id"]]
    assert entry["cadence_band"] == "weekly"
    assert entry["cadence_days"] == 7
    assert entry["overdue_days"] == 3


def test__get_stocktake_queue__InvalidLimit__BadRequest(api):
    assert_problem(
        requests.get(QUEUE, params={"limit": "soon"}), 400,
        title="limit must be an integer.",
    )
    assert_problem(
        requests.get(QUEUE, params={"limit": 0}), 400,
        title="limit must be between 1 and 500.",
    )
    assert_problem(
        requests.get(QUEUE, params={"limit": 501}), 400,
        title="limit must be between 1 and 500.",
    )


#endregion queue

#region ---------------- check ----------------


def test__check_stock_item__OverdueItem__LeavesQueue(api):
    item_id = _overdue_item(f"{_token()} sugar")
    assert item_id in _queue_ids()

    resp = requests.post(f"{BASE}/stock-items/{item_id}/check")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["stock_item_id"] == item_id
    assert body["last_checked_at"] is not None
    assert item_id not in _queue_ids()


def test__check_stock_item__UnknownItem__NotFound(api):
    missing_id = uuid4()

    resp = requests.post(f"{BASE}/stock-items/{missing_id}/check")

    assert_problem(
        resp, 404, detail=f"StockItem with the ID '{missing_id}' was not found.",
    )


#endregion check

#region ---------------- snooze (Push) ----------------


def test__snooze_stock_item__OverdueItem__ThreeDayPushWithoutCheckClaim(api):
    item_id = _overdue_item(f"{_token()} pasta")
    assert item_id in _queue_ids()
    before = requests.get(f"{BASE}/stock-items/{item_id}/detail").json()

    resp = requests.post(f"{BASE}/stock-items/{item_id}/snooze")

    assert resp.status_code == 200, resp.text
    snoozed_until = datetime.fromisoformat(resp.json()["snoozed_until"])
    delta = snoozed_until - datetime.now(UTC).replace(tzinfo=snoozed_until.tzinfo)
    assert timedelta(days=2, hours=23) < delta <= timedelta(days=3)
    # Push makes no claim the stock is right — last_checked_at untouched.
    after = requests.get(f"{BASE}/stock-items/{item_id}/detail").json()
    assert after["last_checked_at"] == before["last_checked_at"]


def test__snooze_stock_item__SnoozedOverdueItem__HiddenFromQueue(api):
    # Regression for the FU-526 fix (2026-07-12): an active snooze made
    # resolve_overdue_map compare a tz-naive (SQLite) snoozed_until against a
    # tz-aware now_ → TypeError → GET /api/stocktake/queue 500'd. `_queue_ids`
    # asserts the 200, so this now proves the queue survives an active snooze.
    item_id = _overdue_item(f"{_token()} noodles")
    assert requests.post(f"{BASE}/stock-items/{item_id}/snooze").status_code == 200

    assert item_id not in _queue_ids()

    # The alerts feed shares resolve_overdue_map, so the same TypeError broke
    # the alerts bell while any snooze was active. Confirm it stays healthy.
    alerts = requests.get(f"{BASE}/alerts")
    assert alerts.status_code == 200, alerts.text


def test__snooze_stock_item__ThenCheck__CheckClearsTheSnooze(api):
    item_id = _overdue_item(f"{_token()} lentils")
    assert requests.post(f"{BASE}/stock-items/{item_id}/snooze").status_code == 200

    check = requests.post(f"{BASE}/stock-items/{item_id}/check")

    assert check.status_code == 200, check.text
    # A Check is a stronger claim than a Push; snooze is gone and the item
    # stays out of the queue on the *checked* baseline instead.
    _backdate_last_checked(item_id, 20)
    assert item_id in _queue_ids()


def test__snooze_stock_item__UnknownItem__NotFound(api):
    missing_id = uuid4()

    resp = requests.post(f"{BASE}/stock-items/{missing_id}/snooze")

    assert_problem(
        resp, 404, detail=f"StockItem with the ID '{missing_id}' was not found.",
    )


#endregion snooze

#region ---------------- bulk-check ----------------


def test__bulk_check__TwoOverdueItems__BothCheckedAndDequeued(api):
    token = _token()
    first = _overdue_item(f"{token} oats")
    second = _overdue_item(f"{token} honey")

    resp = requests.post(BULK_CHECK, json={"ids": [first, second]})

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"checked": 2}
    queued = _queue_ids()
    assert first not in queued
    assert second not in queued


def test__bulk_check__UnknownIds__CountsZeroRows(api):
    resp = requests.post(BULK_CHECK, json={"ids": [str(uuid4())]})

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"checked": 0}


def test__bulk_check__EmptyIds__ValidationFailure(api):
    resp = requests.post(BULK_CHECK, json={"ids": []})

    assert_problem(resp, 400, field="ids")


#endregion bulk-check

# The shopping-list review/complete region went with its endpoint (finalisation 05-R7).

#region ---------------- session (Chunk 6 / D-4) ----------------

SESSION = f"{BASE}/stocktake/session"
SESSION_COMPLETE = f"{SESSION}/complete"

SESSION_ITEM_KEYS = {
    "stock_item_id", "name", "stock_level_id", "stock_level_name",
    "stock_location_name", "stock_location_breadcrumb",
    "cadence_band", "overdue_days", "is_essential",
    "check_rank", "belief_band", "belief_confidence", "belief_reason",
}


def _set_inference(enabled: bool) -> None:
    resp = requests.patch(
        f"{BASE}/auth/me", json={"inferred_pantry_enabled": enabled},
    )
    assert resp.status_code in (200, 204), resp.text


def test__get_stocktake_session__OverdueItem__LandsInWalkPhase(api):
    """The three phases arrive in one read, and an ordinary overdue item — no
    purchase history, so no belief signal — belongs in the Walk."""
    token = _token()
    item_id = _overdue_item(f"{token} rice", days_ago=20)

    body = requests.get(SESSION).json()

    assert set(body.keys()) == {
        "review", "walk", "sweep", "ranked_by", "last_session_at",
    }
    walk = {row["stock_item_id"]: row for row in body["walk"]}
    assert item_id in walk
    entry = walk[item_id]
    assert set(entry.keys()) == SESSION_ITEM_KEYS
    assert entry["check_rank"] == "overdue"
    assert entry["overdue_days"] == 6
    # A row can only be in Review because belief is confident about it, so
    # nothing without a belief may appear there.
    assert item_id not in {row["stock_item_id"] for row in body["review"]}


def test__get_stocktake_session__InferenceOff__RankedByCadenceAndReviewEmpty(api):
    """D-4's edge case: a user who opted out of Dora's guesses must not be
    shown a Review phase built from them. Review is empty by construction —
    the ranking returns everything as `overdue` — so the client skips the
    phase without needing its own gate."""
    token = _token()
    _overdue_item(f"{token} oats", days_ago=20)
    _set_inference(False)
    try:
        body = requests.get(SESSION).json()

        assert body["ranked_by"] == "cadence"
        assert body["review"] == []
        assert len(body["walk"]) >= 1
        assert all(row["check_rank"] == "overdue" for row in body["walk"])
        assert all(row["belief_reason"] is None for row in body["walk"])
    finally:
        _set_inference(True)


def test__complete_stocktake_session__StampsTheWatermark__AndIsReadBack(api):
    """The Sweep phase is the only thing here that can't be recovered later —
    once the watermark passes a departure, that item is indistinguishable from
    the long-dead ones. So the stamp is its own explicit call, made when the
    run finishes rather than as a side effect of any check."""
    before = requests.get(SESSION).json()["last_session_at"]

    resp = requests.post(SESSION_COMPLETE, json={})
    assert resp.status_code == 200, resp.text
    stamped = resp.json()["last_session_at"]
    assert stamped is not None

    after = requests.get(SESSION).json()["last_session_at"]
    assert after == stamped
    assert after != before


def test__get_stocktake_session__MutedUnengagedItem__StaysOutOfSweep(api):
    """Mute already says "don't nag me about this one" — reporting that Dora
    has stopped tracking it would be telling the user something they said
    first. (Also pins that a fresh, engaged item never appears in Sweep.)"""
    token = _token()
    item = make_stock_item(stock_level_id=_stocked_level_id(), name=f"{token} salt")
    item_id = item["stock_item_id"]
    resp = requests.patch(
        f"{BASE}/stock-items/{item_id}",
        json={"stocktake_alerts_are_enabled": False},
    )
    assert resp.status_code == 204, resp.text

    body = requests.get(SESSION).json()

    assert item_id not in {row["stock_item_id"] for row in body["sweep"]}


#endregion session
