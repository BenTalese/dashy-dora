"""FU-169 Phase 2 — hand-rolled test data factories.

Small builders that let tests declare *only the fields they care about*,
so a test asserting price-boundary behaviour doesn't spell out 13 unrelated
attributes just to make the create request pass validation.

Design notes:

* Kept hand-rolled (not `factory_boy`) — the dependency-graph of the
  entities involved is shallow enough that a builder function per entity
  reads better than a Meta / SubFactory chain.
* Every factory returns the response body (or a subset the caller
  usually needs) so tests can chain without re-fetching.
* Defaults are chosen to *pass* validation for the "happy path" every
  factory serves; overrides let error-path tests keep using the same
  builder to exercise a single-field variation.
* Nothing here talks to the DB directly — every factory goes through
  the HTTP boundary the tests already use. Keeps R-005 (repository
  portability) honest and makes the factories work on both SQLite
  (dev) and Postgres (prod-like) without shape changes.
"""
from __future__ import annotations

from typing import Any

import requests

_BASE = "http://localhost:5170/api"


# ── Stock locations ────────────────────────────────────────────────────

def make_stock_location(name: str = "Cellar", **overrides: Any) -> dict:
    """Create a StockLocation via `POST /api/stock-locations`. Returns
    the created DTO (`{name, stock_location_id}`). Idempotent-ish: a
    duplicate name returns a 422; callers who want that behaviour should
    use the direct call, not the factory."""
    body = {"name": name, **overrides}
    resp = requests.post(f"{_BASE}/stock-locations", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Products ───────────────────────────────────────────────────────────

_PRODUCT_DEFAULTS = {
    "brand": "Test",
    "image": None,
    "is_active": True,
    "is_available": True,
    "store_name": "Woolworths",
    "merchant_stockcode": "50332BA",
    "name": "Banana Mangoes",
    "price_now": 4.5,
    "price_was": 10.5,
    "size": "500g",
    "size_unit": "g",
    "size_value": 5.0,
    "web_url": "https://www.example.test",
}


def make_product(**overrides: Any) -> dict:
    """Create a Product via `POST /api/products`. Merges `overrides` over
    the happy-path defaults (Banana Mangoes @ Woolworths). Returns the
    parsed response body."""
    body = {**_PRODUCT_DEFAULTS, **overrides}
    resp = requests.post(f"{_BASE}/products", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Stock items ────────────────────────────────────────────────────────

def make_stock_item(*, stock_level_id: str,
                    name: str = "Freddo Brownie Ice Cream",
                    stock_location_id: str | None = None,
                    **overrides: Any) -> dict:
    """Create a StockItem via `POST /api/stock-items`. `stock_level_id`
    is required (there's no sensible default across suites); everything
    else is optional. Returns the parsed response body."""
    body: dict[str, Any] = {"name": name, "stock_level_id": stock_level_id, **overrides}
    if stock_location_id is not None:
        body["stock_location_id"] = stock_location_id
    resp = requests.post(f"{_BASE}/stock-items", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()
