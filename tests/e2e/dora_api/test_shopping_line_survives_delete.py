"""FU-883 — a finished list is a receipt and keeps its lines.

`ShoppingListLine.stock_item_id` / `product_id` were ON DELETE CASCADE, so
deleting a stock item erased its lines from *completed* lists — silent loss of
purchase history. They are now SET NULL, with the line's display name frozen at
`POST /finish` so the survivor is still readable.

Pinned here:

* finish snapshots every line's name, ticked or not;
* deleting a stock item keeps the line on a **done** list, still named;
* deleting a stock item removes the line from a **draft** list (owner call:
  a line you can no longer buy is noise on a list you're about to shop);
* the reworked CHECK tolerates a product-only line losing its only anchor —
  the trap that would fail loudly on Postgres and silently on SQLite.
"""
from uuid import uuid4

import requests

from tests.factories import make_stock_item

BASE = "http://localhost:5170/api"
LISTS = f"{BASE}/shopping-lists"


def _stock_level_id(sequence: int = 0) -> str:
    levels = requests.get(f"{BASE}/stock-levels").json()["items"]
    return next(l["stock_level_id"] for l in levels if l["sequence"] == sequence)


def _make_item(name: str) -> tuple[str, str]:
    """Returns (id, name). The name is generated here, so tests assert
    against it directly rather than re-fetching it."""
    full_name = f"{name}-{uuid4().hex[:8]}"
    created = make_stock_item(
        stock_level_id=_stock_level_id(), name=full_name,
    )
    return created["stock_item_id"], full_name


def _make_product() -> str:
    suffix = uuid4().hex[:8]
    resp = requests.post(f"{BASE}/products", json={
        "name": f"SurvivorProduct-{suffix}",
        "store_name": "Woolworths",
        "merchant_stockcode": f"SURV-{suffix}",
        "brand": "Test",
        "price_now": 3.0,
        "price_was": 4.0,
        "is_active": True,
        "is_available": True,
        "size": "1L",
        "size_unit": "L",
        "size_value": 1.0,
    })
    assert resp.status_code == 201, resp.text
    return resp.headers["location"].rsplit(":", 1)[-1]


def _make_list() -> str:
    resp = requests.post(LISTS, json={"name": f"Receipt-{uuid4().hex[:8]}"})
    assert resp.status_code == 201, resp.text
    return resp.json()["shopping_list_id"]


def _add_line(list_id: str, **anchor) -> str:
    resp = requests.post(f"{LISTS}/{list_id}/lines", json=anchor)
    assert resp.status_code == 200, resp.text
    return resp.json()["line_id"]


def _lines(list_id: str) -> list[dict]:
    resp = requests.get(f"{LISTS}/{list_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()["lines"]


def _finish(list_id: str) -> None:
    resp = requests.post(f"{LISTS}/{list_id}/finish", json={})
    assert resp.status_code == 200, resp.text


def test__finish__keeps_the_line_readable_after_its_stock_item_is_deleted():
    item_id, name = _make_item("Receipt Milk")
    list_id = _make_list()
    _add_line(list_id, stock_item_id=item_id, quantity=2)
    _finish(list_id)

    deleted = requests.delete(f"{BASE}/stock-items/{item_id}")
    assert deleted.status_code == 204, deleted.text

    lines = _lines(list_id)
    assert len(lines) == 1, "the receipt lost its line"
    assert lines[0]["stock_item_id"] is None, "anchor should be nulled, not kept"
    assert lines[0]["stock_item_name"] == name, "the line forgot what it was"
    assert lines[0]["quantity"] == 2


def test__finish__snapshots_unticked_lines_too():
    """Unticked lines stay on a finished list, so they are just as orphanable
    as the ticked ones — snapshotting only what was bought would still lose
    half a receipt."""
    ticked_item, _ = _make_item("Bought")
    unticked_item, _ = _make_item("Skipped")
    list_id = _make_list()
    ticked_line = _add_line(list_id, stock_item_id=ticked_item)
    _add_line(list_id, stock_item_id=unticked_item)
    requests.patch(
        f"{LISTS}/{list_id}/lines/{ticked_line}", json={"is_ticked": True},
    )
    _finish(list_id)

    for item_id in (ticked_item, unticked_item):
        assert requests.delete(
            f"{BASE}/stock-items/{item_id}",
        ).status_code == 204

    names = sorted(l["stock_item_name"] for l in _lines(list_id))
    assert len(names) == 2
    assert all(not n.startswith("(missing") for n in names), names


def test__draft_list__loses_the_line_when_the_stock_item_goes():
    item_id, _ = _make_item("Planned")
    list_id = _make_list()
    _add_line(list_id, stock_item_id=item_id)

    assert requests.delete(f"{BASE}/stock-items/{item_id}").status_code == 204

    assert _lines(list_id) == [], "a draft line outlived its stock item"


def test__done_and_draft_lists__are_treated_differently_in_one_delete():
    """The same stock item on both a receipt and a live list: one keeps its
    line, the other drops it."""
    item_id, name = _make_item("Both")
    done_list = _make_list()
    _add_line(done_list, stock_item_id=item_id)
    _finish(done_list)

    draft_list = _make_list()
    _add_line(draft_list, stock_item_id=item_id)

    assert requests.delete(f"{BASE}/stock-items/{item_id}").status_code == 204

    kept = _lines(done_list)
    assert len(kept) == 1 and kept[0]["stock_item_name"] == name
    assert _lines(draft_list) == []


def test__done_line_that_never_went_through_finish__still_survives():
    """Not every done list passes through `POST /finish` — the dev seed writes
    finished lists directly, and so does a restore. Such a line has no
    snapshot, so nulling its anchor would leave it with neither, violating
    `ck_shopping_list_line_anchor` and 500-ing the whole delete. The delete
    path backfills the name as a backstop; this pins that.

    Regression: the first cut relied on finish-time stamping alone and broke
    `test__delete_stock_item__DeletingStockItem__StockItemDeleted` against
    seeded data.
    """
    from uuid import UUID

    from dora_api.app import app, db
    from dora_api.domain.entities.shopping_list import ShoppingListLine

    item_id, name = _make_item("Unsnapshotted")
    list_id = _make_list()
    line_id = _add_line(list_id, stock_item_id=item_id)
    _finish(list_id)

    # Rewind to the pre-finish state a seed-written line would be in.
    with app.app_context():
        line = db.session.get(ShoppingListLine, UUID(line_id))
        line.display_name_snapshot = None
        db.session.commit()

    assert requests.delete(f"{BASE}/stock-items/{item_id}").status_code == 204

    lines = _lines(list_id)
    assert len(lines) == 1
    assert lines[0]["stock_item_name"] == name


def test__product_only_line__survives_losing_its_only_anchor():
    """The CHECK-constraint trap. A product-only line has no stock item to
    fall back on, so nulling `product_id` leaves both anchors NULL — which the
    old `ck_shopping_list_line_anchor` forbade. Deleting the product row
    directly because Dora has no product-delete endpoint until batch C; this
    is exactly the schema behaviour that batch C will rely on.
    """
    from uuid import UUID

    from dora_api.app import app, db
    from dora_api.domain.entities.product import Product

    product_id = _make_product()
    product_name = next(
        p["name"] for p in requests.get(f"{BASE}/products").json()["items"]
        if p["product_id"] == product_id
    )
    list_id = _make_list()
    _add_line(list_id, product_id=product_id)
    _finish(list_id)

    # Through the ORM, not raw `text()`: `UUIDType` is 16-byte binary on
    # SQLite, so a string-bound literal matches zero rows and the "delete"
    # silently does nothing (the dialect trap recorded in R-032's lineage).
    with app.app_context():
        product = db.session.get(Product, UUID(product_id))
        assert product is not None
        db.session.delete(product)
        db.session.commit()

    lines = _lines(list_id)
    assert len(lines) == 1, "the receipt lost its product-only line"
    assert lines[0]["product_id"] is None
    assert lines[0]["stock_item_name"] == product_name
