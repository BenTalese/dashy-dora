"""FU-519 tail — the Dora Suggestions HTTP surface (P2-04).

`test_suggestions_snooze_prune.py` owns the FU-513 read-path invariant
(GET never mutates) and the scheduler prune job. This suite covers what
that one doesn't: the GET list contract itself (generator output over
seeded state, DTO shape, severity mapping, the horizon boundary, the
_MAX_SUGGESTIONS cap) and the dismiss / snooze / unsuppress round-trips
driven purely over HTTP.

Suggestions are generated on the fly from app state — the cheapest
deterministic generator to drive end-to-end is `use_soon` (expiry-driven,
3-day horizon), so every test seeds via stock-item expiry dates.
"""
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import requests

from dora_api.app import app
from dora_api.domain.entities.dora_suggestion_suppression import (
    SUPPRESSION_DECISION_DISMISSED, DoraSuggestionSuppression,
)
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from tests.factories import make_stock_item

BASE = "http://localhost:5170/api"


def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _stock_level_id() -> str:
    return requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]


def _household_today() -> date:
    return date.fromisoformat(
        requests.get(f"{BASE}/meal-plans/today").json()["today"]
    )


def _make_expiring_item(days_from_today: int) -> str:
    """Create a stock item expiring `days_from_today` days from the
    household's today. Returns its id (== the use_soon dedup_key)."""
    expiry = _household_today() + timedelta(days=days_from_today)
    item = make_stock_item(
        stock_level_id=_stock_level_id(),
        name=_uniq("sugg-item"),
        expiry_date=expiry.isoformat(),
    )
    return item["stock_item_id"]


def _get_suggestions() -> list[dict]:
    resp = requests.get(f"{BASE}/suggestions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == len(body["suggestions"])
    return body["suggestions"]


def _use_soon_for(item_id: str) -> dict | None:
    return next(
        (s for s in _get_suggestions()
         if s["kind"] == "use_soon" and s["dedup_key"] == item_id),
        None,
    )


# ── GET list shape + generator behaviour ─────────────────────────────────

def test__get_suggestions__expiring_item__surfaces_use_soon_with_full_dto_shape(api):
    item_id = _make_expiring_item(0)
    sugg = _use_soon_for(item_id)
    assert sugg is not None, "an item expiring today must produce a use_soon"

    assert set(sugg.keys()) == {
        "kind", "dedup_key", "severity", "title", "body", "reason",
        "primary_action", "payload",
    }
    assert sugg["severity"] == "high"          # today == act now
    assert "today" in sugg["body"]
    assert sugg["primary_action"] == {
        "path": f"/stock/{item_id}", "label": "Open item",
    }
    assert sugg["payload"]["stock_item_id"] == item_id


def test__get_suggestions__severity_bands__match_days_to_expiry(api):
    expired = _make_expiring_item(-2)   # already expired → high
    tomorrow = _make_expiring_item(1)   # tomorrow → high
    later = _make_expiring_item(3)      # 2+ days inside horizon → medium

    assert _use_soon_for(expired)["severity"] == "high"
    assert "expired 2 days ago" in _use_soon_for(expired)["body"]
    assert _use_soon_for(tomorrow)["severity"] == "high"
    assert _use_soon_for(later)["severity"] == "medium"


def test__get_suggestions__expiry_past_the_3_day_horizon__not_suggested(api):
    inside = _make_expiring_item(3)    # boundary: exactly the horizon
    outside = _make_expiring_item(4)   # one past → silent

    assert _use_soon_for(inside) is not None
    assert _use_soon_for(outside) is None


def test__get_suggestions__capped_at_eight(api):
    # _MAX_SUGGESTIONS = 8 — the dashboard card is a glance, not a queue.
    # Nine imminent items guarantee the cap trips regardless of what the
    # seed data otherwise generates.
    for _ in range(9):
        _make_expiring_item(0)
    resp = requests.get(f"{BASE}/suggestions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 8
    assert len(body["suggestions"]) == 8


def test__get_suggestions__high_severity_sorts_before_medium(api):
    # Sort contract: severity rank first (high > medium > low), then
    # title. Seed one of each and check relative order in the response.
    high_item = _make_expiring_item(0)
    medium_item = _make_expiring_item(3)
    rows = _get_suggestions()
    keys = [s["dedup_key"] for s in rows]
    assert keys.index(high_item) < keys.index(medium_item)


# ── dismiss / snooze / unsuppress over HTTP ──────────────────────────────

def test__dismiss__hides_the_suggestion__unsuppress_brings_it_back(api):
    item_id = _make_expiring_item(0)
    assert _use_soon_for(item_id) is not None

    dismiss = requests.post(f"{BASE}/suggestions/dismiss", json={
        "kind": "use_soon", "dedup_key": item_id,
    })
    assert dismiss.status_code == 204, dismiss.text
    assert _use_soon_for(item_id) is None

    undo = requests.post(f"{BASE}/suggestions/unsuppress", json={
        "kind": "use_soon", "dedup_key": item_id,
    })
    assert undo.status_code == 204, undo.text
    assert _use_soon_for(item_id) is not None


def test__dismiss__is_idempotent(api):
    item_id = _make_expiring_item(0)
    for _ in range(2):
        resp = requests.post(f"{BASE}/suggestions/dismiss", json={
            "kind": "use_soon", "dedup_key": item_id,
        })
        assert resp.status_code == 204, resp.text
    assert _use_soon_for(item_id) is None


def test__snooze__hides_the_suggestion_for_the_window(api):
    item_id = _make_expiring_item(0)
    assert _use_soon_for(item_id) is not None

    resp = requests.post(f"{BASE}/suggestions/snooze", json={
        "kind": "use_soon", "dedup_key": item_id, "hours": 24,
    })
    assert resp.status_code == 204, resp.text
    assert _use_soon_for(item_id) is None


def test__snooze__does_not_downgrade_an_existing_dismiss(api):
    # "Never" beats "later": snoozing an already-dismissed key is a no-op
    # — the row keeps its dismissed decision (checked at the DB since the
    # two states are indistinguishable through GET alone).
    item_id = _make_expiring_item(0)
    requests.post(f"{BASE}/suggestions/dismiss", json={
        "kind": "use_soon", "dedup_key": item_id,
    })
    resp = requests.post(f"{BASE}/suggestions/snooze", json={
        "kind": "use_soon", "dedup_key": item_id, "hours": 1,
    })
    assert resp.status_code == 204, resp.text

    with app.app_context():
        row = SqlAlchemyRepository().get(DoraSuggestionSuppression).one(
            EntityField(DoraSuggestionSuppression, DoraSuggestionSuppression.Fields.DEDUP_KEY)
            .eq(item_id)
        )
    assert row is not None
    assert row.decision == SUPPRESSION_DECISION_DISMISSED
    assert row.snoozed_until is None


def test__snooze__replaces_an_earlier_snooze_window(api):
    # Re-snoozing updates the same row's window rather than stacking rows.
    item_id = _make_expiring_item(0)
    for hours in (1, 48):
        resp = requests.post(f"{BASE}/suggestions/snooze", json={
            "kind": "use_soon", "dedup_key": item_id, "hours": hours,
        })
        assert resp.status_code == 204, resp.text

    with app.app_context():
        rows = SqlAlchemyRepository().get(DoraSuggestionSuppression).all(
            EntityField(DoraSuggestionSuppression, DoraSuggestionSuppression.Fields.DEDUP_KEY)
            .eq(item_id)
        )
    assert len(rows) == 1
    until = rows[0].snoozed_until
    if until.tzinfo is None:  # SQLite drops tzinfo on read
        until = until.replace(tzinfo=timezone.utc)
    assert until > datetime.now(timezone.utc) + timedelta(hours=24)


def test__unsuppress__unknown_key__is_idempotent_204(api):
    resp = requests.post(f"{BASE}/suggestions/unsuppress", json={
        "kind": "use_soon", "dedup_key": str(uuid4()),
    })
    assert resp.status_code == 204, resp.text


# ── validation ───────────────────────────────────────────────────────────

def test__snooze__hours_out_of_range__rejected_400(api):
    for bad_hours in (0, 24 * 7 + 1):
        resp = requests.post(f"{BASE}/suggestions/snooze", json={
            "kind": "use_soon", "dedup_key": "whatever", "hours": bad_hours,
        })
        assert resp.status_code == 400, f"hours={bad_hours}: {resp.text}"
        assert "hours" in resp.json()["errors"]


def test__dismiss__missing_fields__rejected_400(api):
    resp = requests.post(f"{BASE}/suggestions/dismiss", json={})
    assert resp.status_code == 400, resp.text
    errors = resp.json()["errors"]
    assert "kind" in errors and "dedup_key" in errors


def test__dismiss__unknown_field__rejected_400(api):
    resp = requests.post(f"{BASE}/suggestions/dismiss", json={
        "kind": "use_soon", "dedup_key": "x", "definitely_not_a_field": 1,
    })
    assert resp.status_code == 400, resp.text


# ── over_budget (finalisation 09-R1 / 09-R3) ─────────────────────────────

_CURRENCY_SYMBOLS = ("$", "€", "£", "¥", "₹")


def test__suggestions__no_string_carries_a_currency_symbol(api):
    """Amounts ride `payload`; the prose never bakes in a symbol, so a EUR or
    GBP household never reads dollars (the buy-verdict precedent, D-006)."""
    from sqlalchemy import text

    from dora_api.app import db
    from tests.e2e.dora_api._spend_seeding import seed_purchase
    from tests.support import uuid_bind

    seeded = seed_purchase(actual_unit_price=9.0)
    period_start = date.fromisoformat(requests.get(f"{BASE}/budget/status").json()["period_start"])
    # Mid-window completion so the shop is in the current period whatever the clock says.
    with app.app_context(), db.engine.begin() as conn:
        conn.execute(
            text('UPDATE "ShoppingList" SET completed_at = :ts WHERE id = :id'),
            {
                "ts": datetime.combine(period_start + timedelta(days=1), datetime.min.time())
                .replace(hour=12).isoformat(" "),
                "id": uuid_bind(seeded["shopping_list_id"]),
            },
        )
    try:
        assert requests.patch(
            f"{BASE}/budget/settings", json={"amount": 1.0},
        ).status_code == 200
        _make_expiring_item(0)
        suggestions = _get_suggestions()
        over = next(s for s in suggestions if s["kind"] == "over_budget")
        assert over["primary_action"]["path"] == "/settings/budget"
        assert over["payload"]["amount"] == 1.0
        for sugg in suggestions:
            for field in ("title", "body", "reason"):
                assert not any(sym in sugg[field] for sym in _CURRENCY_SYMBOLS), (
                    f"{sugg['kind']}.{field} carries a currency symbol: {sugg[field]!r}"
                )
    finally:
        requests.patch(f"{BASE}/budget/settings", json={"amount": None})
