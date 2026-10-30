"""FU-227 chunk 2 — StockItemPriceObservation reshape.

Folded shape `{total_price, total_measure, unit}` (A1). Per-unit cost derived
server-side (R-003 — client never divides). Validation: unit must be on the
supported price list (volume / mass / count) via `domain/units.py`. Optional
`store_id` (A2). Provenance `shopping_list_line_id` FK set by `/finish`
harvest (chunk 5), not by this manual endpoint.
"""
import uuid

import requests

BASE = "http://localhost:5170/api"
STOCK_ITEMS = f"{BASE}/stock-items"


def _new_stock_item() -> str:
    level = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    resp = requests.post(STOCK_ITEMS, json={
        "name": f"FU227-{uuid.uuid4().hex[:8]}",
        "stock_level_id": level,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["stock_item_id"]


def _detail(item_id: str) -> dict:
    return requests.get(f"{STOCK_ITEMS}/{item_id}/detail").json()


def _current(detail: dict) -> float | None:
    """The detail's current per-unit figure (`your_prices.current`), in the
    install's display denominator: per 100 ml for volume (AU), each for count."""
    return (detail.get("your_prices") or {}).get("current")


def test__price_observation__add_derives_unit_cost(api):
    item = _new_stock_item()
    d = _detail(item)
    assert d["price_observations"] == []
    assert _current(d) is None

    resp = requests.post(
        f"{STOCK_ITEMS}/{item}/price-observations",
        json={"total_price": 6.0, "total_measure": 2.0, "unit": "L"},
    )
    assert resp.status_code == 204, resp.text
    d = _detail(item)
    assert len(d["price_observations"]) == 1
    obs = d["price_observations"][0]
    assert obs["total_price"] == 6.0 and obs["total_measure"] == 2.0 and obs["unit"] == "L"
    # Manual entries have no provenance line and no store unless supplied.
    assert obs["shopping_list_name"] is None
    assert obs["store_name"] is None
    # Server derives per-unit cost (6 / 2 L = 0.30 per 100 ml) — client never divides.
    assert _current(d) == 0.3


def test__price_observation__latest_wins_for_unit_cost(api):
    item = _new_stock_item()
    requests.post(f"{STOCK_ITEMS}/{item}/price-observations", json={
        "total_price": 10.0, "total_measure": 1.0, "unit": "L",
        "observed_at": "2026-01-01T00:00:00+00:00",
    })
    requests.post(f"{STOCK_ITEMS}/{item}/price-observations", json={
        "total_price": 6.0, "total_measure": 2.0, "unit": "L",
        "observed_at": "2026-06-01T00:00:00+00:00",
    })
    d = _detail(item)
    assert len(d["price_observations"]) == 2
    # The current figure comes from the most recent observation (0.30 per 100 ml),
    # not the older 1.00.
    assert _current(d) == 0.3


def test__price_observation__delete_clears_unit_cost(api):
    item = _new_stock_item()
    requests.post(
        f"{STOCK_ITEMS}/{item}/price-observations",
        json={"total_price": 5.0, "total_measure": 1.0, "unit": "ea"},
    )
    obs_id = _detail(item)["price_observations"][0]["observation_id"]
    resp = requests.delete(f"{STOCK_ITEMS}/{item}/price-observations/{obs_id}")
    assert resp.status_code == 204, resp.text
    d = _detail(item)
    assert d["price_observations"] == []
    assert _current(d) is None


def test__price_observation__non_positive_rejected(api):
    item = _new_stock_item()
    resp = requests.post(
        f"{STOCK_ITEMS}/{item}/price-observations",
        json={"total_price": 0, "total_measure": 1, "unit": "L"},
    )
    assert 400 <= resp.status_code < 500


def test__price_observation__count_dimension_accepted(api):
    """B1 — count dimension (ea / pack / dozen) is supported for price entry."""
    item = _new_stock_item()
    resp = requests.post(
        f"{STOCK_ITEMS}/{item}/price-observations",
        json={"total_price": 9.0, "total_measure": 3.0, "unit": "ea"},
    )
    assert resp.status_code == 204, resp.text
    d = _detail(item)
    assert d["price_observations"][0]["unit"] == "ea"
    assert _current(d) == 3.0


def test__price_observation__unsupported_unit_rejected(api):
    """B3 — only volume/mass/count units. Energy/temperature/length rejected
    even though the conversion engine knows them (they're recipe-side)."""
    item = _new_stock_item()
    for bad in ("kJ", "celsius", "mm", "nonsense"):
        resp = requests.post(
            f"{STOCK_ITEMS}/{item}/price-observations",
            json={"total_price": 1.0, "total_measure": 1.0, "unit": bad},
        )
        assert 400 <= resp.status_code < 500, f"{bad!r} should be rejected, got {resp.status_code}"


def test__price_observation__unit_alias_persists_canonical(api):
    """Submitting 'litre' / 'LITRES' persists as 'L' (the canonical form).
    Keeps the data tidy for the median/baseline path in chunk 4."""
    item = _new_stock_item()
    requests.post(
        f"{STOCK_ITEMS}/{item}/price-observations",
        json={"total_price": 3.0, "total_measure": 1.0, "unit": "litre"},
    )
    obs = _detail(item)["price_observations"][0]
    assert obs["unit"] == "L"


def test__price_observation__store_id_attached_and_resolved(api):
    """A2 — optional store_id; server resolves the name for the chip."""
    item = _new_stock_item()
    stores = requests.get(f"{BASE}/stores").json()["items"]
    assert stores, "the seed ships stores"
    store_id = stores[0]["store_id"]
    resp = requests.post(
        f"{STOCK_ITEMS}/{item}/price-observations",
        json={"total_price": 4.0, "total_measure": 1.0, "unit": "L", "store_id": store_id},
    )
    assert resp.status_code == 204, resp.text
    obs = _detail(item)["price_observations"][0]
    assert obs["store_name"] == stores[0]["name"]


def test__price_observation__unknown_store_rejected(api):
    item = _new_stock_item()
    resp = requests.post(
        f"{STOCK_ITEMS}/{item}/price-observations",
        json={
            "total_price": 1.0, "total_measure": 1.0, "unit": "L",
            "store_id": "11111111-1111-1111-1111-111111111111",
        },
    )
    assert resp.status_code == 404, resp.text
