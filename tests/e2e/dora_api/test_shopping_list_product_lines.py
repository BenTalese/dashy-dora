"""Cart Button Chunk 3 (FU-132) — standalone product lines + rules 1–3.

DORA_VERIFY Shopping-lists L533–536. A shopping-list line anchors on a stock
item, a product, or both (CHECK `ck_shopping_list_line_anchor`). This pins the
server rules that have no coverage:

* Rule 1 — a `product_id`-only line is created; a no-anchor body is a 400.
* Rule 2 — linking that product to a stock item upgrades the orphan line
  (convert-in-place when there's no stock-item line yet; fold into the existing
  stock-item line when there is).
* Rule 3 — deleting a stock-item line cascade-removes the nested product line.
"""
from uuid import uuid4

import pytest
import requests

from tests.factories import make_stock_item
from tests.support import assert_problem

BASE = "http://localhost:5170/api"
LISTS = f"{BASE}/shopping-lists"


def _stock_level_id(sequence: int = 0) -> str:
    levels = requests.get(f"{BASE}/stock-levels").json()["items"]
    return next(l["stock_level_id"] for l in levels if l["sequence"] == sequence)


def _make_product() -> str:
    suffix = uuid4().hex[:8]
    resp = requests.post(f"{BASE}/products", json={
        "name": f"CartProduct-{suffix}",
        "store_name": "Woolworths",
        "merchant_stockcode": f"CART-{suffix}",
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


def _make_draft() -> str:
    resp = requests.post(LISTS, json={"name": f"CartList-{uuid4().hex[:8]}"})
    assert resp.status_code == 201, resp.text
    return resp.json()["shopping_list_id"]


def _add_line(list_id: str, **anchor) -> requests.Response:
    return requests.post(f"{LISTS}/{list_id}/lines", json=anchor)


def _lines(list_id: str) -> list:
    return requests.get(f"{LISTS}/{list_id}").json()["lines"]


def _link(stock_item_id: str, product_id: str) -> None:
    resp = requests.post(f"{BASE}/stock-items/{stock_item_id}/products",
                         json={"product_id": product_id})
    assert resp.status_code in (200, 204), resp.text


def test__rule1__product_only_line_is_created(api):
    list_id = _make_draft()
    product_id = _make_product()
    resp = _add_line(list_id, product_id=product_id)
    assert resp.status_code in (200, 201), resp.text

    lines = _lines(list_id)
    assert len(lines) == 1
    assert lines[0]["product_id"] == product_id
    assert lines[0]["stock_item_id"] is None


def test__move_unticked__product_only_lines_move_too(api):
    """Finalisation 03-R3: the move dedupe keyed on `stock_item_id` alone, so a
    NULL-item product line was "a duplicate" of any other and every product-only
    line stayed behind. Keyed on (stock_item_id, product_id) they move."""
    source = _make_draft()
    target = _make_draft()
    first, second = _make_product(), _make_product()
    assert _add_line(source, product_id=first).status_code in (200, 201)
    assert _add_line(source, product_id=second).status_code in (200, 201)

    resp = requests.post(f"{LISTS}/{source}/move-unticked-to/{target}")

    assert resp.status_code == 200, resp.text
    assert resp.json()["moved_count"] == 2
    assert resp.json()["skipped_duplicates"] == 0
    assert {l["product_id"] for l in _lines(target)} == {first, second}
    assert _lines(source) == []


def test__membership__ignores_product_only_lines(api):
    """Finalisation 03-R4: a product-only line is not a stock item's
    membership; bucketing it under `None` serialised a DTO with
    `stock_item_id: null`, which no caller could match."""
    draft = _make_draft()
    assert _add_line(draft, product_id=_make_product()).status_code in (200, 201)

    body = requests.get(f"{LISTS}/membership").json()

    assert all(item["stock_item_id"] is not None for item in body["items"])
    requests.delete(f"{LISTS}/{draft}")


def test__rule1__no_anchor_is_rejected(api):
    # DORA_VERIFY L533 guessed "400 before DB"; the server actually returns a
    # 422 business-rule violation with a clear message (the DB CHECK is the
    # backstop, not the surfaced error). 422 is correct for a domain rule.
    list_id = _make_draft()
    resp = _add_line(list_id)  # neither stock_item_id nor product_id
    body = assert_problem(resp, 422)
    assert "at least one of stock_item_id or product_id" in resp.text


def test__rule2__linking_converts_the_orphan_line_in_place(api):
    # A product-only line, no stock-item line yet → linking the product to a
    # stock item converts the orphan in place (gains stock_item_id, keeps
    # product_id) — one nested row, not two.
    list_id = _make_draft()
    product_id = _make_product()
    item = make_stock_item(stock_level_id=_stock_level_id(),
                           name=f"CartItem {uuid4().hex[:8]}")
    _add_line(list_id, product_id=product_id)

    _link(item["stock_item_id"], product_id)

    lines = _lines(list_id)
    assert len(lines) == 1
    assert lines[0]["stock_item_id"] == item["stock_item_id"]
    assert lines[0]["product_id"] == product_id


def test__rule2__linking_folds_into_an_existing_stock_item_line(api):
    # A stock-item line AND a separate product-only line → linking folds the
    # product anchor into the stock-item line and drops the orphan.
    list_id = _make_draft()
    product_id = _make_product()
    item = make_stock_item(stock_level_id=_stock_level_id(),
                           name=f"CartItem {uuid4().hex[:8]}")
    _add_line(list_id, stock_item_id=item["stock_item_id"])
    _add_line(list_id, product_id=product_id)
    assert len(_lines(list_id)) == 2

    _link(item["stock_item_id"], product_id)

    lines = _lines(list_id)
    assert len(lines) == 1
    assert lines[0]["stock_item_id"] == item["stock_item_id"]
    assert lines[0]["product_id"] == product_id


def test__rule3__deleting_the_stock_item_line_cascades_to_the_nested_product(api):
    # Stock-item line for S + a nested product-only line for P (P linked to S)
    # → deleting the stock-item line removes the nested product line too.
    list_id = _make_draft()
    product_id = _make_product()
    item = make_stock_item(stock_level_id=_stock_level_id(),
                           name=f"CartItem {uuid4().hex[:8]}")
    _link(item["stock_item_id"], product_id)
    _add_line(list_id, stock_item_id=item["stock_item_id"])
    _add_line(list_id, product_id=product_id)  # nested product-only line

    lines = _lines(list_id)
    stock_line = next(l for l in lines if l["stock_item_id"] == item["stock_item_id"]
                      and l["product_id"] is None)

    resp = requests.delete(f"{LISTS}/{list_id}/lines/{stock_line['line_id']}")
    assert resp.status_code in (200, 204), resp.text

    assert _lines(list_id) == []


# ── Unlinking clears a line's chosen offer (2026-09-17) ───────────────────


def test__unlinking_a_product__clears_it_as_a_lines_chosen_offer(api):
    """The selection is tidied where the fact changes, not on demand.

    This replaces `POST /shopping-lists/<id>/refresh-deals`, which swept every
    line of one list whenever a user thought to press a button. Pinned because
    the cleanup is now invisible: the detail read falls back to the cheapest
    linked offer either way, so a regression here leaves a dangling FK that
    nothing on screen would reveal — until the same product is linked again and
    a selection the user never made comes back to life.
    """
    list_id = _make_draft()
    product_id = _make_product()
    item = make_stock_item(stock_level_id=_stock_level_id(),
                           name=f"CartItem {uuid4().hex[:8]}")
    _link(item["stock_item_id"], product_id)
    _add_line(list_id, stock_item_id=item["stock_item_id"])

    line = _lines(list_id)[0]
    chosen = requests.patch(f"{LISTS}/{list_id}/lines/{line['line_id']}",
                            json={"selected_product_id": product_id})
    assert chosen.status_code in (200, 204), chosen.text
    assert _lines(list_id)[0]["selected_product_id"] == product_id

    unlink = requests.delete(
        f"{BASE}/stock-items/{item['stock_item_id']}/products/{product_id}")
    assert unlink.status_code == 204, unlink.text

    assert _lines(list_id)[0]["selected_product_id"] is None


# ── Back to draft (2026-09-17) ────────────────────────────────────────────


def test__back_to_draft__reverts_the_status_and_unticks_every_line(api):
    """The undo for pressing Start shopping by accident.

    Pinned on the untick, not just the status: a draft has no tick model (the
    picker shows a plain count for one), so a revert that left `is_ticked` set
    would leave a draft holding state no surface can show or clear.
    """
    list_id = _make_draft()
    item = make_stock_item(stock_level_id=_stock_level_id(),
                           name=f"CartItem {uuid4().hex[:8]}")
    _add_line(list_id, stock_item_id=item["stock_item_id"])
    assert requests.post(f"{LISTS}/{list_id}/start").status_code == 204

    line = _lines(list_id)[0]
    requests.patch(f"{LISTS}/{list_id}/lines/{line['line_id']}", json={"is_ticked": True})
    assert _lines(list_id)[0]["is_ticked"] is True

    resp = requests.post(f"{LISTS}/{list_id}/back-to-draft")
    assert resp.status_code == 200, resp.text
    assert resp.json()["unticked_count"] == 1

    detail = requests.get(f"{LISTS}/{list_id}").json()
    assert detail["status"] == "draft"
    assert detail["lines"][0]["is_ticked"] is False


def test__back_to_draft__refuses_a_finished_list(api):
    """`done` is final. The restock a finish drove has already moved stock, and
    undoing that is a different question from "I mis-tapped Start shopping"."""
    list_id = _make_draft()
    item = make_stock_item(stock_level_id=_stock_level_id(),
                           name=f"CartItem {uuid4().hex[:8]}")
    _add_line(list_id, stock_item_id=item["stock_item_id"])
    requests.post(f"{LISTS}/{list_id}/start")
    requests.post(f"{LISTS}/{list_id}/finish", json={})

    resp = requests.post(f"{LISTS}/{list_id}/back-to-draft")
    assert_problem(resp, 422)
    assert requests.get(f"{LISTS}/{list_id}").json()["status"] == "done"


def test__quick_add__nested_product_line_does_not_count_as_already_on_list(api):
    """Finalisation 03-R5: quick-add re-implemented the add-line dedupe without
    the `product_id is None` guard, so a product line nested under the item
    made the item itself read as "already on the list". It now delegates to
    `AddLineHandler`, whose rule is: a plain item line is a duplicate only of
    a plain item line."""
    draft = _make_draft()
    product_id = _make_product()
    item_id = requests.post(f"{BASE}/stock-items", json={
        "name": f"QuickAddNested-{uuid4().hex[:8]}",
        "stock_level_id": _stock_level_id(),
    }).json()["stock_item_id"]
    _link(item_id, product_id)
    # Nested product line: both anchors set.
    assert _add_line(draft, stock_item_id=item_id, product_id=product_id).status_code in (200, 201)

    resp = requests.post(f"{LISTS}/quick-add/lines", json={
        "stock_item_id": item_id, "shopping_list_id": draft,
    })

    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    assert body["result"] == "added"
    assert body["already_on_list"] is False
    plain = [l for l in _lines(draft) if l["stock_item_id"] == item_id and l["product_id"] is None]
    assert len(plain) == 1
    requests.delete(f"{LISTS}/{draft}")


def test__frequently_added__returns_ranked_ids_only(api):
    """Finalisation 03-R6 / 03-R14 (R-057): the endpoint hands the sheet the
    ranked ids; `name` / `stock_level_id` / `add_count` had no reader and
    `stock_level_id` was always None (a `noload` relationship read)."""
    draft = _make_draft()
    item_id = requests.post(f"{BASE}/stock-items", json={
        "name": f"Frequent-{uuid4().hex[:8]}",
        "stock_level_id": _stock_level_id(),
    }).json()["stock_item_id"]
    assert _add_line(draft, stock_item_id=item_id).status_code in (200, 201)

    rows = requests.get(f"{LISTS}/frequently-added", params={"limit": 50}).json()

    assert rows, "a list line makes its item frequently-added"
    assert all(set(row.keys()) == {"stock_item_id"} for row in rows)
    assert item_id in {row["stock_item_id"] for row in rows}
    requests.delete(f"{LISTS}/{draft}")


def test__copy__product_only_line_keeps_its_product_anchor(api):
    """03-R1 — the copy used to drop `product_id`, leaving a line with no anchor (500)."""
    list_id = _make_draft()
    product_id = _make_product()
    assert _add_line(list_id, product_id=product_id).status_code in (200, 201)
    copy_id = None
    try:
        resp = requests.post(f"{LISTS}/{list_id}/copy", json={"include": "all"})
        assert resp.status_code == 200, resp.text
        copy_id = resp.json()["shopping_list_id"]
        lines = _lines(copy_id)
        assert len(lines) == 1
        assert lines[0]["product_id"] == product_id
        assert lines[0]["stock_item_id"] is None
    finally:
        if copy_id:
            requests.delete(f"{LISTS}/{copy_id}")
        requests.delete(f"{LISTS}/{list_id}")


# ── Unknown ids on a line PATCH are refused, not 500s ────────────────────


@pytest.mark.parametrize(
    "field, entity",
    [
        ("selected_product_id", "Product"),
        ("purchased_store_id", "Store"),
        ("planned_store_id", "Store"),
    ],
)
def test__update_line__UnknownForeignKeyId__IsNotFound(api, field, entity):
    list_id = _make_draft()
    item = make_stock_item(stock_level_id=_stock_level_id(),
                           name=f"CartItem {uuid4().hex[:8]}")
    _add_line(list_id, stock_item_id=item["stock_item_id"])
    line_id = _lines(list_id)[0]["line_id"]
    missing = str(uuid4())

    resp = requests.patch(f"{LISTS}/{list_id}/lines/{line_id}", json={field: missing})

    assert_problem(resp, 404, detail=f"{entity} with the ID '{missing}' was not found.")
