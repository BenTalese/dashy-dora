"""FU-229 regression — spend-by-store honours the actual→picked ladder.

The K2 ladder (`shopping_lists._line_price.line_paid_unit_price`) is the
single source for "what did this line cost" (R-003). Before FU-229,
`reports/spend.py` `SpendByStoreHandler` projected `picked_offer_price` only and
ignored the user's `actual_unit_price` override, diverging from
budget / waste / assistant / suggestions. This test pins the fix: a line
with both a `picked_offer_price` snapshot and an `actual_unit_price`
override contributes the *actual* to spend-by-store, not the picked.

Savings is deliberately snapshot-based (RRP − picked, not what you paid)
and is **not** exercised here.
"""
import uuid

import requests

from tests.support import set_money_enabled

BASE = "http://localhost:5170/api"
STORES = f"{BASE}/stores"
PRODUCTS = f"{BASE}/products"
STOCK_ITEMS = f"{BASE}/stock-items"
SHOPPING_LISTS = f"{BASE}/shopping-lists"
SPEND = f"{BASE}/reports/spend-by-store"


def test__spend_by_store__honours_actual_unit_price_over_picked(api):
    # The report answers in dollars, so it 403s on a money-off install
    # (FU-816 / R-058) — and a fresh install is money-off.
    set_money_enabled(True)
    # Unique store + product so this test's spend is isolated from
    # whatever the dev seed already wrote against Woolworths/Coles/etc.
    suffix = uuid.uuid4().hex[:8]
    store_name = f"FU229Store-{suffix}"

    # product create no longer auto-spawns a Store; stores are
    # user-curated. Create the store explicitly first.
    store_resp = requests.post(STORES, json={"name": store_name})
    assert store_resp.status_code == 201, store_resp.text

    product_resp = requests.post(PRODUCTS, json={
        "name": f"FU229Product-{suffix}",
        "store_name": store_name,
        "merchant_stockcode": f"FU229-{suffix}",
        "brand": "Test",
        "price_now": 10.0,
        "price_was": 12.0,
        "is_active": True,
        "is_available": True,
        "size": "1L",
        "size_unit": "L",
        "size_value": 1.0,
    })
    assert product_resp.status_code == 201, product_resp.text
    # Location header shape: /api/products?filter=product_id:eq:<uuid>
    product_id = product_resp.headers["location"].rsplit(":", 1)[-1]

    # Resolve the store id (created above) so we can find our row in the
    # spend-by-store response.
    stores_body = requests.get(STORES).json()
    stores = stores_body["items"] if isinstance(stores_body, dict) else stores_body
    store_id = next(s["store_id"] for s in stores if s["name"] == store_name)

    # A stock item to anchor the line on. Spend-by-store requires
    # selected_product_id IS NOT NULL (store grouping needs a product).
    level = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    stock_resp = requests.post(STOCK_ITEMS, json={
        "name": f"FU229Item-{suffix}",
        "stock_level_id": level,
    })
    assert stock_resp.status_code == 201, stock_resp.text
    stock_item_id = stock_resp.json()["stock_item_id"]

    list_id = requests.post(
        SHOPPING_LISTS, json={"name": f"FU229List-{suffix}"},
    ).json()["shopping_list_id"]

    # Add the line selecting the product, then enter the till-receipt
    # price (7.0) and tick. Quantity defaults to 1.
    line_resp = requests.post(
        f"{SHOPPING_LISTS}/{list_id}/lines",
        json={"stock_item_id": stock_item_id, "selected_product_id": product_id},
    )
    assert line_resp.status_code in (200, 201), line_resp.text
    line_id = requests.get(f"{SHOPPING_LISTS}/{list_id}").json()["lines"][0]["line_id"]
    patch_resp = requests.patch(
        f"{SHOPPING_LISTS}/{list_id}/lines/{line_id}",
        json={"actual_unit_price": 7.0, "is_ticked": True},
    )
    assert patch_resp.status_code == 204, patch_resp.text

    # Archive — spend-by-store only counts SHOPPING_LIST_STATUS_DONE lists.
    finish_resp = requests.post(f"{SHOPPING_LISTS}/{list_id}/finish")
    assert finish_resp.status_code == 200, finish_resp.text

    # `range=all` so the test isn't sensitive to the default 30d window.
    rows = requests.get(f"{SPEND}?range=all").json()["rows"]
    our_row = next((r for r in rows if r["store_id"] == store_id), None)
    assert our_row is not None, (
        f"expected a row for {store_name!r} in spend-by-store; got {rows!r}"
    )
    # The ladder wins: actual (7.0) × qty (1) = 7.0, not picked (10.0).
    assert our_row["spend"] == 7.0, (
        f"spend-by-store ignored actual_unit_price; row={our_row!r}"
    )
    assert our_row["list_count"] == 1
