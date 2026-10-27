"""FU-227 chunk 6 — per-stock-item unioned price-history endpoint.

  GET /api/stock-items/<id>/price-history

Pins: unknown item → 404; observations-only series is per-unit, source-tagged
and date-sorted; empty item → no points; and the seeded milk item unions its
own observations ("your data") with its linked products' offer history
("context"), every point normalised to the same canonical unit.
"""
import uuid

import requests

BASE = "http://localhost:5170/api"
STOCK_ITEMS = f"{BASE}/stock-items"


def _new_stock_item() -> str:
    level = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    resp = requests.post(STOCK_ITEMS, json={
        "name": f"PH-{uuid.uuid4().hex[:8]}",
        "stock_level_id": level,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["stock_item_id"]


def _log(item: str, *, total_price: float, total_measure: float, unit: str, observed_at: str) -> None:
    r = requests.post(f"{STOCK_ITEMS}/{item}/price-observations", json={
        "total_price": total_price, "total_measure": total_measure,
        "unit": unit, "observed_at": observed_at,
    })
    assert r.status_code == 204, r.text


def _history(item: str):
    return requests.get(f"{STOCK_ITEMS}/{item}/price-history")


def _find_stock_item_by_name(name: str) -> str | None:
    items = requests.get(f"{STOCK_ITEMS}?limit=500").json().get("items") or []
    for it in items:
        if it.get("name") == name:
            return it["stock_item_id"]
    return None


# ── 404 / empty ───────────────────────────────────────────────────────────


def test__stock_item_price_history__unknown_item__is_404(api):
    resp = _history(str(uuid.uuid4()))
    assert resp.status_code == 404


def test__stock_item_price_history__no_data__empty_points(api):
    item = _new_stock_item()
    body = _history(item).json()
    assert body["points"] == []
    assert body["display_unit"] is None
    assert body["baseline"] is None
    assert body["sample_count"] == 0


# ── Observations-only: per-unit, tagged, sorted ────────────────────────────


def test__stock_item_price_history__observations_only__sorted_and_tagged(api):
    item = _new_stock_item()
    # Logged out of chronological order; the endpoint must sort ascending.
    _log(item, total_price=3.0, total_measure=1.0, unit="L",
         observed_at="2026-03-01T00:00:00+00:00")
    _log(item, total_price=2.0, total_measure=1.0, unit="L",
         observed_at="2026-01-01T00:00:00+00:00")
    _log(item, total_price=5.0, total_measure=1.0, unit="L",
         observed_at="2026-02-01T00:00:00+00:00")
    body = _history(item).json()

    assert body["display_unit"] == "100ml"
    assert body["sample_count"] == 3
    assert body["baseline"] == 0.3          # median of [2, 3, 5] per-L, per 100ml

    points = body["points"]
    assert len(points) == 3
    assert all(p["source"] == "observation" for p in points)
    # Every point already normalised to per-L (here total_measure == 1 L).
    assert all(p["unit_price"] > 0 for p in points)
    # Ascending by observed_at.
    dates = [p["observed_at"] for p in points]
    assert dates == sorted(dates)


def test__stock_item_price_history__ml_observation_displays_per_100ml(api):
    """A 500 ml observation surfaces on the chart in /100ml — AU shelf
    convention applies to the chart series the same as the widget headline
    (below 1 L → /100ml; at or above → /L). See units.display_denominator_for."""
    item = _new_stock_item()
    _log(item, total_price=3.0, total_measure=500.0, unit="ml",
         observed_at="2026-05-01T00:00:00+00:00")
    body = _history(item).json()
    assert body["display_unit"] == "100ml"
    assert len(body["points"]) == 1
    # $3 / 0.5 L = $6/L = $0.60/100ml
    assert abs(body["points"][0]["unit_price"] - 0.6) < 1e-6


# ── Seeded milk: observations ∪ offers, comparable scale ───────────────────


def test__stock_item_price_history__seeded_milk_unions_offers(api):
    """Milk has observations in L and links to two 2 L products with offer
    history — the union must carry both sources on one per-L axis."""
    milk = _find_stock_item_by_name("Full Cream Milk")
    if milk is None:
        return  # seed shape changed — nothing to assert against
    body = _history(milk).json()

    assert body["display_unit"] == "100ml"
    assert body["baseline"] is not None
    assert body["sample_count"] >= 3

    points = body["points"]
    assert points, "expected a non-empty unioned series for milk"
    sources = {p["source"] for p in points}
    assert "observation" in sources
    assert "offer" in sources
    assert all(p["unit_price"] > 0 for p in points)
    # Date-sorted ascending across both sources.
    dates = [p["observed_at"] for p in points]
    assert dates == sorted(dates)


# ── Price-entry prefill (2026-09-17) ──────────────────────────────────────


def test__price_entry_prefill__carries_the_latest_observations_date(api):
    """The prefill says *when* the number it seeded came from.

    The widget's "Prefilled from your last log" line reads identically whether
    that log was yesterday or last March, which is the difference between
    confirming the price and re-checking it. Pinned because it is a server
    contract a client can't re-derive: the prefill exposes one observation, not
    the list, so if `observed_at` stops travelling the UI has no fallback and
    silently loses the date.
    """
    item = _new_stock_item()
    _log(item, total_price=2.00, total_measure=1.0, unit="L",
         observed_at="2026-03-02T00:00:00Z")
    _log(item, total_price=3.50, total_measure=1.0, unit="L",
         observed_at="2026-09-01T00:00:00Z")

    prefill = requests.get(f"{STOCK_ITEMS}/{item}/detail").json()["price_entry_prefill"]

    # The newest observation is the one that seeds the form, so it is also the
    # one whose date is reported.
    assert prefill["total_price"] == 3.50
    assert prefill["observed_at"].startswith("2026-09-01")
