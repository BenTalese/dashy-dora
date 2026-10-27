"""The stock-item detail slices other surfaces read on their own
(`get_stock_item_parts.py`, finalisation 06-R10): each must answer exactly
what the full detail carries for that feed, through the same builders."""
import uuid

import requests

BASE = "http://localhost:5170/api"
STOCK_ITEMS = f"{BASE}/stock-items"


def _new_item(level_id: str) -> str:
    resp = requests.post(STOCK_ITEMS, json={"name": f"parts-{uuid.uuid4().hex[:8]}", "stock_level_id": level_id})
    assert resp.status_code == 201, resp.text
    return resp.json()["stock_item_id"]


def test__parts__each_slice_matches_the_detail_feed(api):
    level_id = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    item, sub = _new_item(level_id), _new_item(level_id)
    assert requests.post(f"{STOCK_ITEMS}/{item}/substitutes", json={"substitute_id": sub}).status_code in (200, 201, 204)
    assert requests.post(f"{STOCK_ITEMS}/{item}/preferred-buys", json={"label": "Brand B"}).status_code in (200, 201, 204)
    assert requests.post(
        f"{STOCK_ITEMS}/{item}/price-observations",
        json={"total_price": 4.0, "total_measure": 1.0, "unit": "kg"},
    ).status_code == 204

    detail = requests.get(f"{STOCK_ITEMS}/{item}/detail").json()
    substitutes = requests.get(f"{STOCK_ITEMS}/{item}/substitutes").json()["items"]
    prefill = requests.get(f"{STOCK_ITEMS}/{item}/price-entry-prefill").json()["prefill"]
    choices = requests.get(f"{STOCK_ITEMS}/{item}/buy-choices").json()

    assert substitutes == detail["substitutes"] and substitutes[0]["stock_item_id"] == sub
    assert prefill == detail["price_entry_prefill"] and prefill["source_label"] == "from your last log"
    assert choices["preferred_buys"] == detail["preferred_buys"]
    assert choices["products"] == detail["products"]


def test__parts__unknown_item_is_404(api):
    missing = uuid.uuid4()
    for part in ("substitutes", "price-entry-prefill", "buy-choices"):
        assert requests.get(f"{STOCK_ITEMS}/{missing}/{part}").status_code == 404, part
