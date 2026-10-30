"""FU-227 chunk 5 — /finish harvests price observations (the closed loop).

Entering a price at the till on a ticked line, then finishing the list, writes
one StockItemPriceObservation per priced line — provenance via the
`shopping_list_line_id` FK (A4). Idempotent under finish double-taps (LC-1).
And PATCH `status=done` is rejected: /finish is the only path to done (E3).

Sized-vs-count harvest math is covered exhaustively by the pure-function tests
in ``tests/test_line_price_harvest.py``; the count case is asserted here
end-to-end (a no-product line). The dev seed exercises the sized path.
"""
import uuid

import requests

BASE = "http://localhost:5170/api"
STOCK_ITEMS = f"{BASE}/stock-items"
SHOPPING_LISTS = f"{BASE}/shopping-lists"


def _new_stock_item() -> str:
    level = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    resp = requests.post(STOCK_ITEMS, json={
        "name": f"FU227h-{uuid.uuid4().hex[:8]}", "stock_level_id": level,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["stock_item_id"]


def _detail(item_id: str) -> dict:
    return requests.get(f"{STOCK_ITEMS}/{item_id}/detail").json()


def _list_with_priced_ticked_line(item_id: str, *, price: float):
    list_id = requests.post(
        SHOPPING_LISTS, json={"name": f"FU227h-{uuid.uuid4().hex[:8]}"}
    ).json()["shopping_list_id"]
    assert requests.post(
        f"{SHOPPING_LISTS}/{list_id}/lines", json={"stock_item_id": item_id}
    ).status_code in (200, 201)
    line_id = requests.get(f"{SHOPPING_LISTS}/{list_id}").json()["lines"][0]["line_id"]
    # Enter the actual price and tick it (the mid-shop capture).
    assert requests.patch(
        f"{SHOPPING_LISTS}/{list_id}/lines/{line_id}",
        json={"actual_unit_price": price, "is_ticked": True},
    ).status_code == 204
    return list_id, line_id


def test__finish__harvests_one_observation_per_priced_line(api):
    item = _new_stock_item()
    assert _detail(item)["price_observations"] == []
    list_id, line_id = _list_with_priced_ticked_line(item, price=5.0)

    resp = requests.post(f"{SHOPPING_LISTS}/{list_id}/finish")
    assert resp.status_code == 200, resp.text

    obs = _detail(item)["price_observations"]
    assert len(obs) == 1
    o = obs[0]
    # Sizeless line (no selected product) → count observation in ea.
    assert o["total_price"] == 5.0 and o["total_measure"] == 1.0 and o["unit"] == "ea"
    # Provenance via the FK, resolved server-side to the list's name.
    assert o["shopping_list_name"] == requests.get(f"{SHOPPING_LISTS}/{list_id}").json()["display_name"]


def test__finish__double_tap_is_idempotent(api):
    item = _new_stock_item()
    list_id, _ = _list_with_priced_ticked_line(item, price=3.25)

    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/finish").status_code == 200
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/finish").status_code == 200
    # LC-1 — the partial UNIQUE on the line FK means the second finish writes
    # nothing new.
    assert len(_detail(item)["price_observations"]) == 1


def test__finish__OnAlreadyDoneList__RestocksNothing(api):
    # A second /finish used to re-stock every ticked item, overwriting a level
    # the user had since lowered.
    item = _new_stock_item()
    list_id, _ = _list_with_priced_ticked_line(item, price=3.25)
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/finish").json()["items_restocked"] == 1
    out_level = max(
        requests.get(f"{BASE}/stock-levels").json()["items"], key=lambda l: l["sequence"],
    )["stock_level_id"]
    assert requests.patch(
        f"{STOCK_ITEMS}/{item}", json={"stock_level_id": out_level},
    ).status_code == 204

    resp = requests.post(f"{SHOPPING_LISTS}/{list_id}/finish")

    assert resp.status_code == 200, resp.text
    assert resp.json()["items_restocked"] == 0
    assert _detail(item)["stock_level_id"] == out_level


def test__finish__OnStaleNotDoneRead__LoserOfTheRaceRestocksNothing(api, monkeypatch):
    # Two devices finishing at the same instant both read `status != done`
    # before either committed, and both restocked + harvested (observed
    # `items_restocked` [1, 1]). The e2e client can't interleave real threads
    # (see test_concurrency.py), so reproduce the loser's view directly: the
    # list is already done in the DB, but the handler's read says it isn't.
    # The conditional UPDATE that claims the transition must then match no
    # row, and the loser must answer like an idempotent double-tap.
    from dora_api.domain.entities.shopping_list import ShoppingList

    item = _new_stock_item()
    list_id, _ = _list_with_priced_ticked_line(item, price=2.0)
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/finish").json()["items_restocked"] == 1
    out_level = max(
        requests.get(f"{BASE}/stock-levels").json()["items"], key=lambda l: l["sequence"],
    )["stock_level_id"]
    assert requests.patch(
        f"{STOCK_ITEMS}/{item}", json={"stock_level_id": out_level},
    ).status_code == 204
    completed_at = requests.get(f"{SHOPPING_LISTS}/{list_id}").json()["completed_at"]

    monkeypatch.setattr(ShoppingList, "is_done", property(lambda self: False))
    resp = requests.post(f"{SHOPPING_LISTS}/{list_id}/finish")
    monkeypatch.undo()

    assert resp.status_code == 200, resp.text
    assert resp.json()["items_restocked"] == 0
    assert _detail(item)["stock_level_id"] == out_level
    assert len(_detail(item)["price_observations"]) == 1
    assert requests.get(f"{SHOPPING_LISTS}/{list_id}").json()["completed_at"] == completed_at


def test__finish__unpriced_ticked_line_is_not_harvested(api):
    item = _new_stock_item()
    list_id = requests.post(
        SHOPPING_LISTS, json={"name": f"FU227h-{uuid.uuid4().hex[:8]}"}
    ).json()["shopping_list_id"]
    requests.post(f"{SHOPPING_LISTS}/{list_id}/lines", json={"stock_item_id": item})
    line_id = requests.get(f"{SHOPPING_LISTS}/{list_id}").json()["lines"][0]["line_id"]
    # Tick it but never set a price → no captured price → nothing to harvest.
    requests.patch(f"{SHOPPING_LISTS}/{list_id}/lines/{line_id}", json={"is_ticked": True})
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/finish").status_code == 200
    assert _detail(item)["price_observations"] == []


def test__prefill__draft_line_shows_last_receipt(api):
    """D3 — a draft line for an item bought before prefills the till editor with
    that per-item price, labelled 'from your last receipt'."""
    item = _new_stock_item()
    done_list, _ = _list_with_priced_ticked_line(item, price=4.50)
    assert requests.post(f"{SHOPPING_LISTS}/{done_list}/finish").status_code == 200

    draft = requests.post(
        SHOPPING_LISTS, json={"name": f"FU227pf-{uuid.uuid4().hex[:8]}"}
    ).json()["shopping_list_id"]
    requests.post(f"{SHOPPING_LISTS}/{draft}/lines", json={"stock_item_id": item})
    line = requests.get(f"{SHOPPING_LISTS}/{draft}").json()["lines"][0]
    assert line["estimated_unit_price"] == 4.50
    assert line["prefill_source_label"] == "from your last receipt"


def test__patch_status_done__is_rejected__use_finish(api):
    # E3 — the only path to done is POST /finish (it snapshots + restocks).
    list_id = requests.post(
        SHOPPING_LISTS, json={"name": f"FU227e3-{uuid.uuid4().hex[:8]}"}
    ).json()["shopping_list_id"]
    resp = requests.patch(f"{SHOPPING_LISTS}/{list_id}", json={"status": "done"})
    # The handler rejects this as a business-rule violation (422); the plan's
    # prose said "400s" but the implemented contract is 422 with a message
    # pointing at /finish. What matters is the rejection + the pointer.
    assert resp.status_code in (400, 422), resp.text
    assert "finish" in resp.text.lower()
    assert requests.get(f"{SHOPPING_LISTS}/{list_id}").json()["status"] == "draft"


def test__patch_status_shopping__still_allowed(api):
    # draft⇄shopping still flow through PATCH; only `done` is gated.
    list_id = requests.post(
        SHOPPING_LISTS, json={"name": f"FU227e3-{uuid.uuid4().hex[:8]}"}
    ).json()["shopping_list_id"]
    resp = requests.patch(f"{SHOPPING_LISTS}/{list_id}", json={"status": "shopping"})
    assert resp.status_code == 204, resp.text
    assert requests.get(f"{SHOPPING_LISTS}/{list_id}").json()["status"] == "shopping"


# ───── FU-726 — amending a finished list corrects the harvested observation ──
# Observations feed the money ladder's `historic` rung, so a price corrected on
# the receipt face has to reach the observation too — otherwise the typo keeps
# driving every future estimate for that item.

def test__amend_price_on_done_list__rewrites_the_observation(api):
    item = _new_stock_item()
    list_id, line_id = _list_with_priced_ticked_line(item, price=110.00)
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/finish").status_code == 200
    assert _detail(item)["price_observations"][0]["total_price"] == 110.00

    # The user spots the misplaced decimal on the receipt and amends it.
    assert requests.patch(
        f"{SHOPPING_LISTS}/{list_id}/lines/{line_id}",
        json={"actual_unit_price": 11.00},
    ).status_code == 204

    obs = _detail(item)["price_observations"]
    assert len(obs) == 1, "amend must correct in place, never add a second point"
    assert obs[0]["total_price"] == 11.00
    assert obs[0]["shopping_list_name"]


def test__amend_quantity_on_done_list__rescales_the_observation(api):
    item = _new_stock_item()
    list_id, line_id = _list_with_priced_ticked_line(item, price=4.00)
    requests.patch(f"{SHOPPING_LISTS}/{list_id}/lines/{line_id}", json={"quantity": 1})
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/finish").status_code == 200
    assert _detail(item)["price_observations"][0]["total_price"] == 4.00

    assert requests.patch(
        f"{SHOPPING_LISTS}/{list_id}/lines/{line_id}", json={"quantity": 3}
    ).status_code == 204

    obs = _detail(item)["price_observations"]
    assert len(obs) == 1
    # Sizeless line → count observation: 3 × $4.00 for 3 ea.
    assert obs[0]["total_price"] == 12.00 and obs[0]["total_measure"] == 3.0


def test__clearing_the_price_on_a_done_list__removes_the_observation(api):
    item = _new_stock_item()
    list_id, line_id = _list_with_priced_ticked_line(item, price=6.50)
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/finish").status_code == 200
    assert len(_detail(item)["price_observations"]) == 1

    assert requests.patch(
        f"{SHOPPING_LISTS}/{list_id}/lines/{line_id}",
        json={"clear_actual_unit_price": True},
    ).status_code == 204

    # A stale number is worse than no number when it drives future estimates.
    assert _detail(item)["price_observations"] == []


def test__amending_a_draft_line__writes_no_observation(api):
    """Only a finished list has observations to correct — editing a price while
    still planning must not invent purchase history."""
    item = _new_stock_item()
    _list_with_priced_ticked_line(item, price=9.99)
    assert _detail(item)["price_observations"] == []
