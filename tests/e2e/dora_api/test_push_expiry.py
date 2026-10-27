"""`POST /stock-items/<id>/push-expiry` — the one "+N days" rule (finalisation
05-R2 / 06-R1): from the later of the household's today and the current
expiry, recorded on the History tab like every other expiry change."""
import uuid
from datetime import date, timedelta

import requests

BASE = "http://localhost:5170/api"
STOCK_ITEMS = f"{BASE}/stock-items"


def _today() -> date:
    return date.fromisoformat(requests.get(f"{BASE}/meal-plans/today").json()["today"])


def _item(expiry: date | None) -> str:
    level = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    body = {"name": f"push-{uuid.uuid4().hex[:8]}", "stock_level_id": level}
    if expiry is not None:
        body["expiry_date"] = expiry.isoformat()
    resp = requests.post(STOCK_ITEMS, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["stock_item_id"]


def _push(item_id: str, days: int) -> date:
    resp = requests.post(f"{STOCK_ITEMS}/{item_id}/push-expiry", json={"days": days})
    assert resp.status_code == 200, resp.text
    return date.fromisoformat(resp.json()["expiry_date"])


def test__push_expiry__an_expired_item_pushes_from_today(api):
    today = _today()
    assert _push(_item(today - timedelta(days=5)), 1) == today + timedelta(days=1)


def test__push_expiry__a_future_expiry_moves_by_the_days(api):
    today = _today()
    assert _push(_item(today + timedelta(days=10)), 7) == today + timedelta(days=17)


def test__push_expiry__no_expiry_counts_from_today_and_records_the_event(api):
    today = _today()
    item_id = _item(None)
    assert _push(item_id, 14) == today + timedelta(days=14)
    events = requests.get(f"{STOCK_ITEMS}/{item_id}/detail").json()["expiry_events"]
    assert events[0]["new_expiry_date"] == (today + timedelta(days=14)).isoformat()


def test__push_expiry__days_out_of_range_is_400(api):
    item_id = _item(None)
    for days in (0, 366):
        assert requests.post(f"{STOCK_ITEMS}/{item_id}/push-expiry", json={"days": days}).status_code == 400
