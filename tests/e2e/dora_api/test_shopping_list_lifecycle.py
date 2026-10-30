"""P6-01 Chunk 1 — shopping-list lifecycle (status model).

Covers the single `status` field (draft / shopping / done) that replaced the
old is_archived / is_in_progress boolean pair. Once a list is done, it's done —
FU-163 retired Reopen / /unfinish along with the rest of the app-wide undo
posture.
"""
from uuid import uuid4

import requests

from tests.support import assert_problem

BASE = "http://localhost:5170/api"
SHOPPING_LISTS = f"{BASE}/shopping-lists"


def _create_list(name: str) -> str:
    resp = requests.post(SHOPPING_LISTS, json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["shopping_list_id"]


def _detail(list_id: str) -> dict:
    resp = requests.get(f"{SHOPPING_LISTS}/{list_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def test__create_shopping_list__defaults_to_draft_status(api):
    list_id = _create_list(f"Lifecycle draft {uuid4()}")
    detail = _detail(list_id)
    assert detail["status"] == "draft"
    # Legacy flags are gone from the DTO entirely.
    assert "is_archived" not in detail
    assert "is_in_progress" not in detail


def test__start__transitions_status__and_stop_is_removed(api):
    list_id = _create_list(f"Lifecycle start {uuid4()}")

    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/start").status_code == 204
    assert _detail(list_id)["status"] == "shopping"

    # UX-v2: no pause — /stop was deleted with the shop-mode merge. The
    # lifecycle is start -> finish; once done, it's done (no /unfinish either).
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/stop").status_code == 404


def test__update_status__invalid_value_is_rejected(api):
    list_id = _create_list(f"Lifecycle bad status {uuid4()}")
    resp = requests.patch(f"{SHOPPING_LISTS}/{list_id}", json={"status": "bogus"})
    assert resp.status_code in (400, 422), resp.text
    # Status unchanged.
    assert _detail(list_id)["status"] == "draft"


def test__summaries__expose_status_not_legacy_flags(api):
    _create_list(f"Lifecycle summary {uuid4()}")
    summaries = requests.get(SHOPPING_LISTS).json()
    assert summaries, "expected at least one shopping list"
    for s in summaries:
        assert "status" in s
        assert s["status"] in ("draft", "shopping", "done")
        assert "is_archived" not in s
        assert "is_in_progress" not in s


def test__unfinish_endpoint_is_removed(api):
    # undo posture retired — /unfinish (Reopen) no longer exists.
    list_id = _create_list(f"Lifecycle no-reopen {uuid4()}")
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/start").status_code == 204
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/finish").status_code == 200
    assert _detail(list_id)["status"] == "done"
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/unfinish").status_code == 404


def _new_stock_item() -> str:
    level = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    resp = requests.post(f"{BASE}/stock-items", json={
        "name": f"Lifecycle item {uuid4().hex[:8]}", "stock_level_id": level,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["stock_item_id"]


def _finished_list() -> str:
    list_id = _create_list(f"Lifecycle done {uuid4()}")
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/finish").status_code == 200
    assert _detail(list_id)["status"] == "done"
    return list_id


def test__add_line__OnDoneList__Returns422AndAddsNothing(api):
    # A done list is a receipt — /finish already restocked from it.
    list_id = _finished_list()

    resp = requests.post(
        f"{SHOPPING_LISTS}/{list_id}/lines", json={"stock_item_id": _new_stock_item()},
    )

    assert_problem(resp, 422, title="Business rule violation.")
    assert _detail(list_id)["lines"] == []


def test__bulk_add__OnDoneList__IsRefusedForTheWholeList(api):
    list_id = _finished_list()
    item_id = _new_stock_item()

    resp = requests.post(
        f"{SHOPPING_LISTS}/{list_id}/lines/bulk-add", json={"stock_item_ids": [item_id]},
    )

    # A finished list is a list-level answer (like a missing one), not a
    # per-item failure: 422 with the same copy as the single-line route.
    assert resp.status_code == 422, resp.text
    assert "finished" in resp.text
    assert _detail(list_id)["lines"] == []


def test__quick_add__HintAtDoneList__Returns422(api):
    list_id = _finished_list()

    resp = requests.post(f"{SHOPPING_LISTS}/quick-add/lines", json={
        "stock_item_id": _new_stock_item(), "shopping_list_id": list_id,
    })

    assert_problem(resp, 422, title="Business rule violation.")
    assert _detail(list_id)["lines"] == []


def test__discard_unticked__MixedLines__RemovesOnlyTheUntickedOnes(api):
    # The finish dialog's "I didn't want them after all" branch: the ticked
    # line is what was bought and must survive; the unticked ones go.
    list_id = _create_list(f"Lifecycle discard {uuid4()}")
    for _ in range(3):
        added = requests.post(
            f"{SHOPPING_LISTS}/{list_id}/lines", json={"stock_item_id": _new_stock_item()},
        )
        assert added.status_code == 200, added.text
    lines = _detail(list_id)["lines"]
    kept = lines[0]["line_id"]
    ticked = requests.patch(
        f"{SHOPPING_LISTS}/{list_id}/lines/{kept}", json={"is_ticked": True},
    )
    assert ticked.status_code == 204, ticked.text

    resp = requests.post(f"{SHOPPING_LISTS}/{list_id}/discard-unticked")

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"removed_count": 2}
    assert [l["line_id"] for l in _detail(list_id)["lines"]] == [kept]


def test__discard_unticked__UnknownList__Returns404(api):
    resp = requests.post(f"{SHOPPING_LISTS}/{uuid4()}/discard-unticked")
    assert_problem(resp, 404)
