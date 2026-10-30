"""QR label endpoints e2e (`dora_api/features/data/barcodes.py`).

  GET /api/stock-items/<id>/qr          — PNG of one item's dora:// label
  GET /api/stock-items/qr/sheet         — printable HTML sheet of many

Written to close **FU-648**, which has sat open because the owner's report
("QR button gives 'couldn't load', Print one errors") was twice fixed without
the failure ever being reproduced — the previous investigation was a static
read, and a static read is not evidence about a running server.

These endpoints qualify for an automated pin under the lean verification
stance: the contract is stable (two GETs, fixed shapes), and re-checking it by
hand means clicking through the SPA with devtools open every time. What it can
prove is that the *server* half answers correctly under a real session. What it
can't prove is how the browser reaches it — so the base-URL half of FU-648 is
still the owner's browser walk.

The sheet's QRs must be inlined as data: URIs: the SPA opens the sheet as a
blob, from which a relative `/api/...` back-reference cannot resolve and an
absolute one would be an unauthenticated subresource. That's the exact shape of
the original breakage, so it gets its own assertion.
"""
import re
from uuid import uuid4

import requests

from tests.factories import make_stock_item

BASE = "http://localhost:5170/api"
SHEET = f"{BASE}/stock-items/qr/sheet"

# 8-byte PNG signature. Enough to prove we got an image and not an HTML error
# page with a 200 on it.
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _stocked_level_id() -> str:
    levels = requests.get(f"{BASE}/stock-levels").json()["items"]
    return next(level for level in levels if level["sequence"] == 0)["stock_level_id"]


def _make_item(name: str) -> str:
    return make_stock_item(stock_level_id=_stocked_level_id(), name=name)["stock_item_id"]


#region ---------------- single-item PNG ----------------


def test__qr__returns_a_png_for_a_real_item():
    item_id = _make_item(f"QR subject {uuid4().hex[:6]}")

    resp = requests.get(f"{BASE}/stock-items/{item_id}/qr")

    assert resp.status_code == 200, resp.text
    assert resp.headers["Content-Type"] == "image/png"
    assert resp.content.startswith(_PNG_MAGIC)


def test__qr__honours_the_requested_size_and_rejects_absurd_ones():
    item_id = _make_item(f"QR sized {uuid4().hex[:6]}")

    # 512 is what the detail page's dialog asks for — the size the owner's
    # "couldn't load" report was against.
    assert requests.get(f"{BASE}/stock-items/{item_id}/qr?size=512").status_code == 200
    assert requests.get(f"{BASE}/stock-items/{item_id}/qr?size=63").status_code == 400
    assert requests.get(f"{BASE}/stock-items/{item_id}/qr?size=2048").status_code == 400
    assert requests.get(f"{BASE}/stock-items/{item_id}/qr?size=big").status_code == 400


def test__qr__unknown_item_is_404_not_a_broken_image():
    resp = requests.get(f"{BASE}/stock-items/{uuid4()}/qr")

    assert resp.status_code == 404


#region ---------------- print sheet ----------------


def test__qr_sheet__prints_the_requested_item_with_its_qr_inlined():
    name = f"QR sheet subject {uuid4().hex[:6]}"
    item_id = _make_item(name)

    resp = requests.get(SHEET, params={"ids": item_id})

    assert resp.status_code == 200, resp.text
    assert resp.headers["Content-Type"].startswith("text/html")
    html = resp.text
    assert name in html
    assert "1 label(s)" in html
    # The load-bearing property: self-contained. No back-reference to /api,
    # which is what made the sheet blank when opened as a blob.
    assert 'src="data:image/png;base64,' in html
    assert "/api/stock-items" not in html


def test__qr_sheet__honours_the_caller_s_order_and_skips_unknown_ids():
    first = f"QR order A {uuid4().hex[:6]}"
    second = f"QR order B {uuid4().hex[:6]}"
    first_id = _make_item(first)
    second_id = _make_item(second)

    resp = requests.get(SHEET, params={"ids": f"{second_id},{uuid4()},{first_id}"})

    assert resp.status_code == 200, resp.text
    html = resp.text
    assert "2 label(s)" in html
    assert html.index(second) < html.index(first)


def test__qr_sheet__no_ids_prints_every_item():
    name = f"QR print-all {uuid4().hex[:6]}"
    _make_item(name)

    resp = requests.get(SHEET)

    assert resp.status_code == 200, resp.text
    assert name in resp.text
    # "print all" means more than the one we just made — the seed has stock.
    count = int(re.search(r"(\d+) label\(s\)", resp.text).group(1))
    assert count > 1


def test__qr_sheet__unknown_layout_is_a_named_400():
    resp = requests.get(SHEET, params={"layout": "avery-9999"})

    assert resp.status_code == 400
    assert "a4-21up" in resp.text  # the error names the available layouts


#region ---------------- print sheet, POST door ----------------
# A big selection's ids overflow the request line (gunicorn: 8190 bytes, ~200
# uuids), so the SPA POSTs them as a JSON body. Same sheet, same semantics.


def test__qr_sheet_post__honours_order_and_carries_a_selection_too_big_for_a_get():
    first = f"QR post A {uuid4().hex[:6]}"
    second = f"QR post B {uuid4().hex[:6]}"
    first_id = _make_item(first)
    second_id = _make_item(second)
    # 400 unknown uuids ≈ 15 KB — a GET of this would be refused upstream.
    filler = [str(uuid4()) for _ in range(400)]

    resp = requests.post(
        SHEET, json={"ids": [second_id, *filler, first_id], "layout": "a4-21up"},
    )

    assert resp.status_code == 200, resp.text
    assert resp.headers["Content-Type"].startswith("text/html")
    html = resp.text
    assert "2 label(s)" in html
    assert html.index(second) < html.index(first)
    assert 'src="data:image/png;base64,' in html
    assert "/api/stock-items" not in html


def test__qr_sheet_post__empty_ids_prints_every_item():
    name = f"QR post print-all {uuid4().hex[:6]}"
    _make_item(name)

    resp = requests.post(SHEET, json={"ids": []})

    assert resp.status_code == 200, resp.text
    assert name in resp.text


def test__qr_sheet_post__unknown_layout_is_a_named_400():
    resp = requests.post(SHEET, json={"ids": [], "layout": "avery-9999"})

    assert resp.status_code == 400
    assert "a4-21up" in resp.text


def test__qr_sheet_post__over_the_id_cap_is_400():
    resp = requests.post(SHEET, json={"ids": [str(uuid4()) for _ in range(5001)]})

    assert resp.status_code == 400
