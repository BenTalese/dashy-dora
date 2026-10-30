"""GET /api/stock-items/recently-priced — the log-price picker's shortlist.

The contract is the ordering (most recently observed first) and the exclusion
(items with no observation never appear). Both are server-owned — the picker
renders the order it is given — so they're worth pinning here rather than
re-checking by hand every time the picker is touched.
"""
import uuid
from datetime import UTC, datetime, timedelta

import requests

BASE = "http://localhost:5170/api"
STOCK_ITEMS = f"{BASE}/stock-items"
RECENTLY_PRICED = f"{STOCK_ITEMS}/recently-priced"


def _new_stock_item(prefix: str = "RP") -> str:
    level = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    resp = requests.post(STOCK_ITEMS, json={
        "name": f"{prefix}-{uuid.uuid4().hex[:8]}",
        "stock_level_id": level,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["stock_item_id"]


def _log_price(item_id: str, observed_at: str) -> None:
    resp = requests.post(f"{STOCK_ITEMS}/{item_id}/price-observations", json={
        "total_price": 4.0, "total_measure": 1.0, "unit": "L",
        "observed_at": observed_at,
    })
    assert resp.status_code == 204, resp.text


def _days_ahead(days: int) -> str:
    # Ahead of now — and so of anything the today-relative seed holds — so
    # these rows sit at the head of the list however much price history the
    # database already has. Relative, so it never falls behind the seed.
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


def test__recently_priced__orders_by_most_recent_observation(api):
    oldest, middle, newest = (_new_stock_item() for _ in range(3))
    _log_price(middle, _days_ahead(60))
    _log_price(oldest, _days_ahead(30))
    _log_price(newest, _days_ahead(90))

    resp = requests.get(RECENTLY_PRICED, params={"limit": 50})
    assert resp.status_code == 200, resp.text
    ids = [row["stock_item_id"] for row in resp.json()]

    assert ids[:3] == [newest, middle, oldest]


def test__recently_priced__skips_items_with_no_observation(api):
    priced = _new_stock_item()
    unpriced = _new_stock_item()
    _log_price(priced, _days_ahead(91))

    rows = requests.get(RECENTLY_PRICED, params={"limit": 50}).json()
    ids = [row["stock_item_id"] for row in rows]

    assert priced in ids
    assert unpriced not in ids
    # Each row carries what the picker needs to look the item up + label it.
    row = next(r for r in rows if r["stock_item_id"] == priced)
    assert row["name"] and row["last_priced_at"]


def test__recently_priced__honours_the_limit(api):
    for _ in range(3):
        _log_price(_new_stock_item(), _days_ahead(92))

    rows = requests.get(RECENTLY_PRICED, params={"limit": 2}).json()
    assert len(rows) == 2
