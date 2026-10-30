"""The bulk endpoints added 2026-08-22 for the stock overview's bulk bar.

Owner feedback: "might need a bulk action endpoint, bulk actions seem to be
performed one item at a time and it can be slow. noticed this on log waste."
Every action on that bar used to be an N-request loop from the browser.

What these pin is the *contract* each new endpoint offers the SPA — counts,
echoed ids, and the Undo payload — because the SPA's summary toasts and undo
handler read those fields directly. The per-item semantics underneath
(expiry-event emission, line de-duplication, nested product-line cascade) are
deliberately NOT re-tested here: these handlers delegate to the single-item
handlers precisely so those rules keep their existing coverage.
"""
from uuid import uuid4

import requests

from tests.factories import make_stock_item
from tests.support import assert_problem

BASE = "http://localhost:5170/api"
LISTS = f"{BASE}/shopping-lists"
STOCK_ITEMS = f"{BASE}/stock-items"
WASTE = f"{BASE}/waste"


def _levels() -> list[dict]:
    return requests.get(f"{BASE}/stock-levels").json()["items"]


def _stock_level_id(sequence: int = 0) -> str:
    return next(l["stock_level_id"] for l in _levels() if l["sequence"] == sequence)


def _make_item(**overrides) -> dict:
    return make_stock_item(
        stock_level_id=overrides.pop("stock_level_id", _stock_level_id()),
        name=overrides.pop("name", f"Bulk-{uuid4().hex[:8]}"),
        **overrides,
    )


def _make_draft() -> str:
    resp = requests.post(LISTS, json={"name": f"Bulk-{uuid4().hex[:8]}"})
    assert resp.status_code == 201, resp.text
    return resp.json()["shopping_list_id"]


def _get_item(stock_item_id: str) -> dict:
    resp = requests.get(f"{STOCK_ITEMS}/{stock_item_id}/detail")
    assert resp.status_code == 200, resp.text
    return resp.json()


# ───── Bulk move ──────────────────────────────────────────────────────────

def test__bulk_move__moves_every_item_and_reports_missing_ids(api):
    location = requests.post(
        f"{BASE}/stock-locations", json={"name": f"Shelf-{uuid4().hex[:8]}"},
    )
    assert location.status_code == 201, location.text
    location_id = location.json()["stock_location_id"]

    ids = [_make_item()["stock_item_id"] for _ in range(3)]
    ghost = str(uuid4())

    resp = requests.post(f"{STOCK_ITEMS}/bulk-move", json={
        "stock_item_ids": ids + [ghost],
        "destination_location_id": location_id,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["moved_count"] == 3
    assert body["missing_ids"] == [ghost]

    for sid in ids:
        assert _get_item(sid)["stock_location_id"] == location_id


def test__bulk_move__null_destination_unassigns(api):
    location = requests.post(
        f"{BASE}/stock-locations", json={"name": f"Shelf-{uuid4().hex[:8]}"},
    )
    location_id = location.json()["stock_location_id"]
    sid = _make_item(stock_location_id=location_id)["stock_item_id"]

    resp = requests.post(f"{STOCK_ITEMS}/bulk-move", json={
        "stock_item_ids": [sid],
        "destination_location_id": None,
    })
    assert resp.status_code == 200, resp.text
    assert _get_item(sid)["stock_location_id"] is None


def test__bulk_move__unknown_destination_is_rejected(api):
    sid = _make_item()["stock_item_id"]
    resp = requests.post(f"{STOCK_ITEMS}/bulk-move", json={
        "stock_item_ids": [sid],
        "destination_location_id": str(uuid4()),
    })
    assert_problem(resp, 422, title="Business rule violation.")
    assert "Destination location was not found." in str(resp.json())


def test__bulk_move__empty_id_list_is_rejected(api):
    resp = requests.post(f"{STOCK_ITEMS}/bulk-move", json={
        "stock_item_ids": [], "destination_location_id": None,
    })
    assert_problem(resp, 400, field="stock_item_ids")


# ───── Bulk set level ─────────────────────────────────────────────────────

def test__bulk_set_level__puts_every_item_on_the_level(api):
    levels = sorted(_levels(), key=lambda l: l["sequence"])
    low, top = levels[-1]["stock_level_id"], levels[0]["stock_level_id"]

    ids = [_make_item(stock_level_id=low)["stock_item_id"] for _ in range(3)]
    resp = requests.post(f"{STOCK_ITEMS}/bulk-set-level", json={
        "stock_item_ids": ids, "stock_level_id": top,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated_count"] == 3

    for sid in ids:
        assert _get_item(sid)["stock_level_id"] == top


def test__bulk_set_level__unknown_item_is_reported_not_fatal(api):
    top = _stock_level_id(0)
    sid = _make_item()["stock_item_id"]
    ghost = str(uuid4())

    resp = requests.post(f"{STOCK_ITEMS}/bulk-set-level", json={
        "stock_item_ids": [sid, ghost], "stock_level_id": top,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["updated_count"] == 1
    assert body["failed_ids"] == [ghost]


def test__bulk_set_level__unknown_level_is_rejected(api):
    sid = _make_item()["stock_item_id"]
    resp = requests.post(f"{STOCK_ITEMS}/bulk-set-level", json={
        "stock_item_ids": [sid], "stock_level_id": str(uuid4()),
    })
    assert_problem(resp, 422, title="Business rule violation.")
    assert "Stock level was not found." in str(resp.json())


# ───── Bulk waste + undo ──────────────────────────────────────────────────

def test__bulk_log_waste__logs_events_clears_expiry_and_echoes_the_old_date(api):
    with_expiry = _make_item(expiry_date="2030-01-01")["stock_item_id"]
    without_expiry = _make_item()["stock_item_id"]

    resp = requests.post(f"{WASTE}/events/bulk", json={
        "stock_item_ids": [with_expiry, without_expiry],
        "reason": "expired",
    })
    assert resp.status_code == 200, resp.text
    events = {e["stock_item_id"]: e for e in resp.json()["events"]}
    assert len(events) == 2

    # The echoed expiry is what Undo needs; an item that had none must not
    # grow one when it's restored.
    assert events[with_expiry]["previous_expiry_date"] == "2030-01-01"
    assert events[without_expiry]["previous_expiry_date"] is None
    assert _get_item(with_expiry)["expiry_date"] is None

    logged = requests.get(f"{WASTE}/events?limit=200").json()["events"]
    logged_ids = {e["event_id"] for e in logged}
    for event in events.values():
        assert event["event_id"] in logged_ids


def test__bulk_log_waste__can_keep_the_expiry(api):
    sid = _make_item(expiry_date="2030-06-01")["stock_item_id"]
    resp = requests.post(f"{WASTE}/events/bulk", json={
        "stock_item_ids": [sid], "reason": "spoiled", "clear_expiry": False,
    })
    assert resp.status_code == 200, resp.text
    assert _get_item(sid)["expiry_date"] == "2030-06-01"


def test__bulk_log_waste__unknown_item_is_reported_not_fatal(api):
    sid = _make_item()["stock_item_id"]
    ghost = str(uuid4())
    resp = requests.post(f"{WASTE}/events/bulk", json={
        "stock_item_ids": [sid, ghost], "reason": "expired",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["events"]) == 1
    assert body["missing_ids"] == [ghost]


def test__bulk_log_waste__invalid_reason_is_rejected(api):
    sid = _make_item()["stock_item_id"]
    resp = requests.post(f"{WASTE}/events/bulk", json={
        "stock_item_ids": [sid], "reason": "eaten-by-a-bear",
    })
    assert resp.status_code == 400, resp.text


def test__bulk_delete_waste__undoes_the_batch_and_restores_expiry(api):
    with_expiry = _make_item(expiry_date="2030-01-01")["stock_item_id"]
    without_expiry = _make_item()["stock_item_id"]
    logged = requests.post(f"{WASTE}/events/bulk", json={
        "stock_item_ids": [with_expiry, without_expiry], "reason": "expired",
    }).json()["events"]

    resp = requests.post(f"{WASTE}/events/bulk-delete", json={
        "events": [
            {
                "event_id": e["event_id"],
                "restore_expiry_date": e["previous_expiry_date"],
            }
            for e in logged
        ],
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["deleted_count"] == 2
    assert body["restored_count"] == 1

    assert _get_item(with_expiry)["expiry_date"] == "2030-01-01"
    assert _get_item(without_expiry)["expiry_date"] is None

    remaining = {
        e["event_id"]
        for e in requests.get(f"{WASTE}/events?limit=200").json()["events"]
    }
    for event in logged:
        assert event["event_id"] not in remaining


def test__bulk_delete_waste__is_idempotent(api):
    sid = _make_item()["stock_item_id"]
    event_id = requests.post(f"{WASTE}/events/bulk", json={
        "stock_item_ids": [sid], "reason": "expired",
    }).json()["events"][0]["event_id"]

    payload = {"events": [{"event_id": event_id, "restore_expiry_date": None}]}
    first = requests.post(f"{WASTE}/events/bulk-delete", json=payload)
    second = requests.post(f"{WASTE}/events/bulk-delete", json=payload)
    assert first.json()["deleted_count"] == 1
    assert second.status_code == 200, second.text
    assert second.json()["deleted_count"] == 0


# ───── Bulk add / remove shopping-list lines ──────────────────────────────

def test__bulk_add_lines__counts_added_and_already_on_list(api):
    list_id = _make_draft()
    ids = [_make_item()["stock_item_id"] for _ in range(3)]

    first = requests.post(f"{LISTS}/{list_id}/lines/bulk-add", json={
        "stock_item_ids": ids,
    })
    assert first.status_code == 200, first.text
    assert first.json() == {"added": 3, "already_on_list": 0, "failed_ids": []}

    # Re-adding the same set must de-dupe rather than double the lines —
    # this is `AddLineHandler`'s rule, reached through the bulk path.
    second = requests.post(f"{LISTS}/{list_id}/lines/bulk-add", json={
        "stock_item_ids": ids,
    })
    assert second.status_code == 200, second.text
    assert second.json()["already_on_list"] == 3
    assert second.json()["added"] == 0

    detail = requests.get(f"{LISTS}/{list_id}").json()
    assert len([l for l in detail["lines"] if l["stock_item_id"] in ids]) == 3


def test__bulk_add_lines__unknown_list_is_404(api):
    sid = _make_item()["stock_item_id"]
    resp = requests.post(f"{LISTS}/{uuid4()}/lines/bulk-add", json={
        "stock_item_ids": [sid],
    })
    assert resp.status_code == 404, resp.text


def test__bulk_remove_by_stock_item__removes_only_what_is_on_the_list(api):
    list_id = _make_draft()
    on_list = [_make_item()["stock_item_id"] for _ in range(2)]
    never_added = _make_item()["stock_item_id"]

    requests.post(f"{LISTS}/{list_id}/lines/bulk-add", json={
        "stock_item_ids": on_list,
    })

    resp = requests.post(
        f"{LISTS}/{list_id}/lines/bulk-remove-by-stock-item",
        json={"stock_item_ids": on_list + [never_added]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["removed_count"] == 2

    detail = requests.get(f"{LISTS}/{list_id}").json()
    assert [l for l in detail["lines"] if l["stock_item_id"] in on_list] == []


def test__bulk_remove_by_stock_item__unknown_list_is_404(api):
    sid = _make_item()["stock_item_id"]
    resp = requests.post(
        f"{LISTS}/{uuid4()}/lines/bulk-remove-by-stock-item",
        json={"stock_item_ids": [sid]},
    )
    assert resp.status_code == 404, resp.text


# ───── Reorder lines ──────────────────────────────────────────────────────

def test__reorder_lines__UnknownList__IsNotFound(api):
    missing = uuid4()

    resp = requests.post(f"{LISTS}/{missing}/lines/reorder", json={"line_ids": []})

    assert_problem(resp, 404, detail=f"ShoppingList with the ID '{missing}' was not found.")


def test__reorder_lines__RepeatedLineId__KeepsFirstPosition(api):
    list_id = _make_draft()
    for _ in range(2):
        requests.post(f"{LISTS}/{list_id}/lines", json={"stock_item_id": _make_item()["stock_item_id"]})
    first, second = (l["line_id"] for l in requests.get(f"{LISTS}/{list_id}").json()["lines"])

    resp = requests.post(f"{LISTS}/{list_id}/lines/reorder",
                         json={"line_ids": [second, first, second]})

    assert resp.status_code == 204, resp.text
    by_seq = sorted(requests.get(f"{LISTS}/{list_id}").json()["lines"], key=lambda l: l["sequence"])
    assert [l["line_id"] for l in by_seq] == [second, first]
    assert [l["sequence"] for l in by_seq] == [0, 1]
