"""Verify-campaign Batch 3 — 3-band StockLevel collapse (DORA_VERIFY L874–883).

The 2026-07-02 collapse axed the "Sufficient" middle band; three surfaces that
restock *to Stocked* were still untested server-side:

  - POST /shopping-lists/<id>/finish — every ticked line's item flips to
    Stocked by default (L875), or to the restock-review override the user
    picked (L876's server half), resolved by status identity via
    `level_for_status`, never by display name.
  - POST /alerts/<key>/action no longer takes `mark_restocked` (2026-10-15:
    the essential-low row offers the level picker itself, which writes through
    the stock-item endpoint) nor the older `acknowledge_stocktake`; both are
    refused rather than silently accepted.

The other collapse bullets already had homes: `review/complete`
`{set_stocked, checked}` in `test_stocktake_router.py` (L878), the assistant
"sufficient"→STOCKED aliases in `test_confirm_actions_resolve_level.py`
(L880), cookability Low-counts/Out-doesn't in `test_recipe_cookability.py`
(L881), and the import blank-Level→Stocked default in `test_data_router.py`
(L879, added alongside this file). Modal options / onboarding copy /
buy-verdict popover labels (L876-UI/882/883) are client renders — V-pack.
"""
from datetime import date, timedelta
from uuid import uuid4

import pytest
import requests

from dora_api.domain.stock_status import (LOW_STOCK_SEQUENCE,
                                          OUT_OF_STOCK_SEQUENCE,
                                          STOCKED_SEQUENCE)

BASE = "http://localhost:5170/api"
SHOPPING_LISTS = f"{BASE}/shopping-lists"
STOCK_ITEMS = f"{BASE}/stock-items"
STOCK_LEVELS = f"{BASE}/stock-levels"


#region ---------------- fixtures / helpers ----------------

@pytest.fixture
def levels_by_sequence():
    levels = requests.get(STOCK_LEVELS).json()["items"]
    return {l["sequence"]: l["stock_level_id"] for l in levels}


def _create_list(name: str) -> str:
    resp = requests.post(SHOPPING_LISTS, json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["shopping_list_id"]


def _create_item(level_id: str, *, expiry_date: str | None = None) -> str:
    body: dict = {"name": f"collapse-{uuid4()}", "stock_level_id": level_id}
    if expiry_date is not None:
        body["expiry_date"] = expiry_date
    resp = requests.post(STOCK_ITEMS, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["stock_item_id"]


def _add_ticked_line(list_id: str, item_id: str, *, ticked: bool = True) -> str:
    resp = requests.post(f"{SHOPPING_LISTS}/{list_id}/lines", json={"stock_item_id": item_id})
    assert resp.status_code == 200, resp.text
    line_id = resp.json()["line_id"]
    if ticked:
        r = requests.patch(
            f"{SHOPPING_LISTS}/{list_id}/lines/{line_id}", json={"is_ticked": True}
        )
        assert r.status_code in (200, 204), r.text
    return line_id


def _item_dto(item_id: str) -> dict:
    items = requests.get(
        f"{STOCK_ITEMS}?filter=stock_item_id:eq:{item_id}"
    ).json()["items"]
    assert len(items) == 1
    return items[0]

#endregion fixtures / helpers


#region ---------------- finish → restock (L875 / L876) ----------------

def test__finish__ticked_items_default_to_stocked(levels_by_sequence, api):
    # L875 — the one-click path: no overrides in the body, every ticked
    # item flips to Stocked (sequence identity, whatever its display name).
    list_id = _create_list(f"finish-default-{uuid4()}")
    out_item = _create_item(levels_by_sequence[OUT_OF_STOCK_SEQUENCE])
    low_item = _create_item(levels_by_sequence[LOW_STOCK_SEQUENCE])
    _add_ticked_line(list_id, out_item)
    _add_ticked_line(list_id, low_item)

    resp = requests.post(f"{SHOPPING_LISTS}/{list_id}/finish", json={})

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"items_restocked": 2}
    assert _item_dto(out_item)["stock_level_sequence"] == STOCKED_SEQUENCE
    assert _item_dto(low_item)["stock_level_sequence"] == STOCKED_SEQUENCE


def test__finish__unticked_items_keep_their_level(levels_by_sequence, api):
    # Untouched lines stay on the done list and their items keep their
    # level — finishing only restocks what you actually bought.
    list_id = _create_list(f"finish-unticked-{uuid4()}")
    bought = _create_item(levels_by_sequence[OUT_OF_STOCK_SEQUENCE])
    skipped = _create_item(levels_by_sequence[OUT_OF_STOCK_SEQUENCE])
    _add_ticked_line(list_id, bought)
    _add_ticked_line(list_id, skipped, ticked=False)

    resp = requests.post(f"{SHOPPING_LISTS}/{list_id}/finish", json={})

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"items_restocked": 1}
    assert _item_dto(bought)["stock_level_sequence"] == STOCKED_SEQUENCE
    assert _item_dto(skipped)["stock_level_sequence"] == OUT_OF_STOCK_SEQUENCE


def test__finish__every_ticked_item_restocks_to_stocked(levels_by_sequence, api):
    # Buying something means it's Stocked — there is no per-item choice at
    # finish time. Both items land on Stocked regardless of where they were.
    list_id = _create_list(f"finish-all-stocked-{uuid4()}")
    was_out = _create_item(levels_by_sequence[OUT_OF_STOCK_SEQUENCE])
    was_low = _create_item(levels_by_sequence[LOW_STOCK_SEQUENCE])
    _add_ticked_line(list_id, was_out)
    _add_ticked_line(list_id, was_low)

    resp = requests.post(f"{SHOPPING_LISTS}/{list_id}/finish", json={})

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"items_restocked": 2}
    assert _item_dto(was_out)["stock_level_sequence"] == STOCKED_SEQUENCE
    assert _item_dto(was_low)["stock_level_sequence"] == STOCKED_SEQUENCE


def test__finish__level_overrides_are_rejected(levels_by_sequence, api):
    # FU-582: the per-item level picker was cut on purpose. The finish body
    # takes no options, so a caller still sending the old `level_overrides`
    # is refused outright rather than silently ignored.
    list_id = _create_list(f"finish-no-overrides-{uuid4()}")
    item = _create_item(levels_by_sequence[OUT_OF_STOCK_SEQUENCE])
    _add_ticked_line(list_id, item)

    resp = requests.post(f"{SHOPPING_LISTS}/{list_id}/finish", json={
        "level_overrides": [{
            "stock_item_id": item,
            "stock_level_id": levels_by_sequence[LOW_STOCK_SEQUENCE],
        }],
    })

    assert resp.status_code == 400, resp.text
    assert "level_overrides" in resp.json()["errors"]
    detail = requests.get(f"{SHOPPING_LISTS}/{list_id}").json()
    assert detail["status"] != "done"
    # The tick already restocked it (UX v5); the refused finish moved nothing.
    assert _item_dto(item)["stock_level_sequence"] == STOCKED_SEQUENCE

#endregion finish → restock


#region ---------------- alert actions (L877) ----------------

def _alert_id_for(name: str) -> str:
    data = requests.get(f"{BASE}/alerts").json()
    alert = next(
        (a for a in data["items"]
         if a["stock_item_name"] == name and a["kind"] == "expired"),
        None,
    )
    assert alert is not None, f"expected an expired alert for {name}"
    return alert["alert_id"]


@pytest.mark.parametrize("retired", ["acknowledge_stocktake", "mark_restocked"])
def test__alert_action__retired_actions_are_refused(levels_by_sequence, api, retired):
    # `acknowledge_stocktake` went with the `stocktake_overdue` kind at Step-0
    # Q1; `mark_restocked` went 2026-10-15. Pinned as rejections rather than
    # deleted outright: silently 204-ing an unknown action would be worse than
    # refusing it.
    today = date.fromisoformat(requests.get(f"{BASE}/meal-plans/today").json()["today"])
    resp = requests.post(STOCK_ITEMS, json={
        "name": f"collapse-{retired}-{uuid4()}",
        "stock_level_id": levels_by_sequence[OUT_OF_STOCK_SEQUENCE],
        # Expired yesterday: inside the alert discard window, so it shows.
        "expiry_date": (today - timedelta(days=1)).isoformat(),
    })
    assert resp.status_code == 201, resp.text
    item_id = resp.json()["stock_item_id"]
    alert_id = _alert_id_for(resp.json()["name"])

    action = requests.post(f"{BASE}/alerts/{alert_id}/action", json={"action": retired})

    assert action.status_code == 422, action.text
    after = _item_dto(item_id)
    assert after["stock_level_sequence"] == OUT_OF_STOCK_SEQUENCE

#endregion alert actions
