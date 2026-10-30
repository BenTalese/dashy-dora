"""End-to-end coverage for the N8 Price History Explorer endpoints."""
import uuid

import requests


BASE = "http://localhost:5170/api/price-history"


def test__price_history__missing_product_ids__is_400(api):
    response = requests.get(BASE)
    assert response.status_code == 400


def test__price_history__too_many_product_ids__is_400(api):
    ids = ",".join(str(uuid.uuid4()) for _ in range(6))
    response = requests.get(f"{BASE}?product_ids={ids}")
    assert response.status_code == 400


def test__price_history__unknown_product__returns_placeholder(api):
    bogus = uuid.uuid4()
    response = requests.get(f"{BASE}?product_ids={bogus}&range=30d")
    assert response.status_code == 200
    series = response.json()["series"]
    assert len(series) == 1
    assert series[0]["product_id"] == str(bogus)
    assert series[0]["points"] == []
    assert series[0]["name"] == "(unknown)"
    # placeholder still carries the new fields (no obs / no
    # baseline for a product that doesn't exist).
    assert series[0]["your_prices"] is None
    assert series[0]["observation_points"] == []


def _find_product_by_name(name: str) -> str | None:
    products = requests.get("http://localhost:5170/api/products").json().get("items") or []
    for p in products:
        if p.get("name") == name:
            return p["product_id"]
    return None


def test__price_history__series_carries_your_prices_and_observations(api):
    """FU-227 chunk 6 (F-3 + H2) — the per-product series now carries the
    user's baseline + their own observation points (transitively, via every
    linked stock item). The seeded Woolworths milk product links to the milk
    stock item, which has price observations in L."""
    product_id = _find_product_by_name("Woolworths Full Cream Milk 2L")
    if product_id is None:
        return  # seed shape changed
    response = requests.get(f"{BASE}?product_ids={product_id}&range=all")
    assert response.status_code == 200
    series = response.json()["series"]
    assert len(series) == 1
    s = series[0]

    # F-3 — baseline block present and computed (milk has 3+ obs in L).
    assert s["your_prices"] is not None
    assert s["your_prices"]["sample_count"] >= 3
    assert s["your_prices"]["baseline"] is not None
    assert s["your_prices"]["baseline_unit"] == "100ml"

    # H2 — observation points present + normalised per-unit.
    assert isinstance(s["observation_points"], list)
    assert len(s["observation_points"]) >= 3
    assert all(p["unit_price"] > 0 for p in s["observation_points"])


def test__price_alerts__crud_round_trip(api):
    # Pick any existing product from the search API or skip when none.
    products = requests.get("http://localhost:5170/api/products").json().get("items") or []
    if not products:
        return
    product_id = products[0]["product_id"]

    # Create
    create = requests.post(f"{BASE}/alerts", json={
        "product_id": product_id, "threshold_unit_price": 1.23,
    })
    assert create.status_code == 200, create.text
    alert_id = create.json()["price_alert_id"]

    # List
    listed = requests.get(f"{BASE}/alerts").json()["items"]
    assert any(a["price_alert_id"] == alert_id for a in listed)

    # Delete
    deleted = requests.delete(f"{BASE}/alerts/{alert_id}")
    assert deleted.status_code == 204

    # Subsequent delete → 404
    redel = requests.delete(f"{BASE}/alerts/{alert_id}")
    assert redel.status_code == 404


def test__price_alerts__create_for_unknown_product__is_404(api):
    response = requests.post(f"{BASE}/alerts", json={
        "product_id": str(uuid.uuid4()), "threshold_unit_price": 5.0,
    })
    assert response.status_code == 404


def test__price_alerts__zero_threshold__is_422(api):
    products = requests.get("http://localhost:5170/api/products").json().get("items") or []
    if not products:
        return
    response = requests.post(f"{BASE}/alerts", json={
        "product_id": products[0]["product_id"], "threshold_unit_price": 0,
    })
    # Pydantic gt=0 → 400/422 via the middleware.
    assert response.status_code in (400, 422)


def test__price_alerts__NoSessionUser__Returns401(api, monkeypatch):
    """No signed-in user is an authentication failure (401), not a malformed
    request (400). The auth gate normally stops this first, so the handler's
    own check is driven by blanking the session user."""
    import dora_api.features.price_history.price_history as module
    from tests.support import assert_problem

    monkeypatch.setattr(module, "current_user_id", lambda: None)

    assert_problem(requests.get(f"{BASE}/alerts"), 401)
    assert_problem(requests.delete(f"{BASE}/alerts/{uuid.uuid4()}"), 401)
