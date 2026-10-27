"""FU-725 — the shopping-list detail's money and store ladders, end to end.

The rung order is pinned as pure functions (`test_shopping_list_store_breakdown.py`,
`resolve_store_id`); these drive the real detail read so a regression in how
the handler *feeds* the ladders (the prior-purchase lookup, the picked offer,
the planned and bought-from stores) shows up as the wrong rung.

Money: actual → picked offer → last actual purchase → none.
Store: bought from → planned on this list → last actual purchase → chosen offer.
"""
import uuid

import requests

BASE = "http://localhost:5170/api"
LISTS = f"{BASE}/shopping-lists"


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def _store(name: str) -> str:
    assert requests.post(f"{BASE}/stores", json={"name": name}).status_code == 201
    return next(s["store_id"] for s in requests.get(f"{BASE}/stores").json()["items"] if s["name"] == name)


def _item() -> str:
    level = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    resp = requests.post(f"{BASE}/stock-items", json={"name": f"Ladder-{_suffix()}", "stock_level_id": level})
    assert resp.status_code == 201, resp.text
    return resp.json()["stock_item_id"]


def _linked_product(item_id: str, store_name: str, price: float) -> str:
    suffix = _suffix()
    resp = requests.post(f"{BASE}/products", json={
        "name": f"LadderProduct-{suffix}", "store_name": store_name,
        "merchant_stockcode": f"LADDER-{suffix}", "price_now": price,
        "is_active": True, "is_available": True,
        "size": "1L", "size_unit": "L", "size_value": 1.0,
    })
    assert resp.status_code == 201, resp.text
    product_id = resp.headers["location"].rsplit(":", 1)[-1]
    assert requests.post(f"{BASE}/stock-items/{item_id}/products", json={"product_id": product_id}).status_code in (200, 204)
    return product_id


def _list_with(item_id: str) -> tuple[str, str]:
    list_id = requests.post(LISTS, json={"name": f"Ladder-{_suffix()}"}).json()["shopping_list_id"]
    assert requests.post(f"{LISTS}/{list_id}/lines", json={"stock_item_id": item_id}).status_code in (200, 201)
    return list_id, requests.get(f"{LISTS}/{list_id}").json()["lines"][0]["line_id"]


def _patch(list_id: str, line_id: str, **body) -> None:
    resp = requests.patch(f"{LISTS}/{list_id}/lines/{line_id}", json=body)
    assert resp.status_code == 204, resp.text


def _line(list_id: str) -> dict:
    return requests.get(f"{LISTS}/{list_id}").json()["lines"][0]


def _bought_before(item_id: str, *, price: float, store_id: str) -> None:
    list_id, line_id = _list_with(item_id)
    _patch(list_id, line_id, actual_unit_price=price, purchased_store_id=store_id, is_ticked=True)
    assert requests.post(f"{LISTS}/{list_id}/finish").status_code == 200


def test__money_ladder__each_rung_in_order(api):
    item = _item()
    list_id, line_id = _list_with(item)
    assert _line(list_id)["estimate_source"] == "none"

    last_store = _store(f"LadderLast-{_suffix()}")
    _bought_before(item, price=4.0, store_id=last_store)
    line = _line(list_id)
    assert (line["estimate_source"], line["estimated_unit_price"]) == ("historic", 4.0)

    offer_store_name = f"LadderOffer-{_suffix()}"
    _store(offer_store_name)
    product = _linked_product(item, offer_store_name, price=3.0)
    # An unpicked offer never prices the line.
    assert _line(list_id)["estimate_source"] == "historic"
    _patch(list_id, line_id, selected_product_id=product)
    line = _line(list_id)
    assert (line["estimate_source"], line["estimated_unit_price"]) == ("offer", 3.0)

    _patch(list_id, line_id, actual_unit_price=2.5)
    line = _line(list_id)
    assert (line["estimate_source"], line["estimated_unit_price"]) == ("actual", 2.5)


def test__store_ladder__intent_beats_history_and_bought_from_beats_all(api):
    item = _item()
    last_store = _store(f"LadderLast-{_suffix()}")
    _bought_before(item, price=4.0, store_id=last_store)
    list_id, line_id = _list_with(item)
    line = _line(list_id)
    assert line["resolved_store_id"] == last_store
    assert line["last_paid_store_id"] == last_store

    planned = _store(f"LadderPlanned-{_suffix()}")
    _patch(list_id, line_id, planned_store_id=planned)
    assert _line(list_id)["resolved_store_id"] == planned

    bought = _store(f"LadderBought-{_suffix()}")
    _patch(list_id, line_id, purchased_store_id=bought)
    line = _line(list_id)
    assert line["resolved_store_id"] == bought
    assert line["purchased_store_name"].startswith("LadderBought-")
