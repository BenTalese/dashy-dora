"""FU-512 — `POST /shopping-list-templates/from-list/<id>` is a unit of work.

Pre-FU-512 committed twice (template row, then snapshot lines). Now: one
commit.
"""
from uuid import uuid4

import requests

BASE = "http://localhost:5170/api"
SL_TEMPLATES = f"{BASE}/shopping-list-templates"
LISTS = f"{BASE}/shopping-lists"


def _a_stock_item_id() -> str:
    return requests.get(f"{BASE}/stock-items?limit=1").json()["items"][0]["stock_item_id"]


def _make_product() -> str:
    suffix = uuid4().hex[:8]
    resp = requests.post(f"{BASE}/products", json={
        "name": f"SnapProduct-{suffix}",
        "store_name": "Woolworths",
        "merchant_stockcode": f"SNAP-{suffix}",
        "brand": "Test",
        "price_now": 4.5,
        "price_was": 6.0,
        "is_active": True,
        "is_available": True,
        "size": "1L",
        "size_unit": "L",
        "size_value": 1.0,
    })
    assert resp.status_code == 201, resp.text
    return resp.headers["location"].rsplit(":", 1)[-1]


def test__snapshot_shopping_list__product_only_line__round_trips_through_the_template(api):
    """FU-940 D1: a product-only line used to be skipped by "Save as template".
    It is kept, named by its product, and comes back on a list from the
    template."""
    src_id = requests.post(LISTS, json={"name": f"D1 src {uuid4()}"}).json()["shopping_list_id"]
    product_id = _make_product()
    assert requests.post(f"{LISTS}/{src_id}/lines", json={"stock_item_id": _a_stock_item_id()}).status_code in (200, 201)
    assert requests.post(f"{LISTS}/{src_id}/lines", json={"product_id": product_id}).status_code in (200, 201)

    resp = requests.post(f"{SL_TEMPLATES}/from-list/{src_id}", json={"include_ticked": True})
    assert resp.status_code in (200, 201), resp.text
    template_id = resp.json()["template_id"]
    assert resp.json()["line_count"] == 2

    lines = requests.get(f"{SL_TEMPLATES}/{template_id}").json()["lines"]
    product_line = next(l for l in lines if l["stock_item_id"] is None)
    assert product_line["product_id"] == product_id
    assert product_line["stock_item_name"].startswith("SnapProduct-")

    made = requests.post(f"{SL_TEMPLATES}/{template_id}/instantiate", json={}).json()
    new_lines = requests.get(f"{LISTS}/{made['shopping_list_id']}").json()["lines"]
    assert any(l["product_id"] == product_id and l["stock_item_id"] is None for l in new_lines)
    requests.delete(f"{SL_TEMPLATES}/{template_id}")


def test__snapshot_shopping_list__ItemWithPlainAndProductLine__OneTemplateLine(api):
    # An item on the list as a plain line plus a nested product line used to
    # snapshot as two template lines for the same item.
    item_id = requests.post(f"{BASE}/stock-items", json={
        "name": f"Snap dup {uuid4().hex[:8]}",
        "stock_level_id": requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"],
    }).json()["stock_item_id"]
    product_id = _make_product()
    assert requests.post(f"{BASE}/stock-items/{item_id}/products", json={"product_id": product_id}).status_code == 204
    src_id = requests.post(LISTS, json={"name": f"Snap dup src {uuid4()}"}).json()["shopping_list_id"]
    assert requests.post(f"{LISTS}/{src_id}/lines", json={"stock_item_id": item_id}).status_code in (200, 201)
    assert requests.post(f"{LISTS}/{src_id}/lines", json={"product_id": product_id}).status_code in (200, 201)
    assert len(requests.get(f"{LISTS}/{src_id}").json()["lines"]) == 2

    resp = requests.post(f"{SL_TEMPLATES}/from-list/{src_id}", json={"include_ticked": True})

    assert resp.status_code in (200, 201), resp.text
    assert resp.json()["line_count"] == 1
    lines = requests.get(f"{SL_TEMPLATES}/{resp.json()['template_id']}").json()["lines"]
    assert [l["stock_item_id"] for l in lines] == [item_id]


def test__snapshot_shopping_list__self_labelled_source__names_the_template_from_display_name(api):
    """A self-labelled list has `name=None`; the fallback read "Template from
    None" (finalisation 03-R2)."""
    src_id = requests.post(LISTS, json={}).json()["shopping_list_id"]
    display_name = requests.get(f"{LISTS}/{src_id}").json()["display_name"]
    assert display_name

    resp = requests.post(f"{SL_TEMPLATES}/from-list/{src_id}", json={"include_ticked": True})

    assert resp.status_code in (200, 201), resp.text
    template = requests.get(f"{SL_TEMPLATES}/{resp.json()['template_id']}").json()
    assert template["name"] == f"Template from {display_name}"
    assert "None" not in template["name"]
    requests.delete(f"{SL_TEMPLATES}/{resp.json()['template_id']}")


def test__snapshot_shopping_list__all_valid__commits_template_and_lines_together(api):
    src_id = requests.post(LISTS, json={"name": f"FU-512 src {uuid4()}"}).json()["shopping_list_id"]
    add_resp = requests.post(f"{LISTS}/{src_id}/lines", json={
        "stock_item_id": _a_stock_item_id(),
        "quantity": 3,
    })
    assert add_resp.status_code in (200, 201), add_resp.text

    template_id = None
    try:
        resp = requests.post(f"{SL_TEMPLATES}/from-list/{src_id}", json={
            "name": f"FU-512 snapshot {uuid4()}",
            "include_ticked": True,
        })
        assert resp.status_code in (200, 201), resp.text
        template_id = resp.json()["template_id"]
        assert resp.json()["line_count"] == 1

        detail = requests.get(f"{SL_TEMPLATES}/{template_id}")
        assert detail.status_code == 200, detail.text
        assert len(detail.json()["lines"]) == 1
    finally:
        if template_id:
            requests.delete(f"{SL_TEMPLATES}/{template_id}")
        requests.delete(f"{LISTS}/{src_id}")
