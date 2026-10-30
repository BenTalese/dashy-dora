"""B6 — bulk buy-verdicts for a shopping list's lines.

  GET /api/shopping-lists/<id>/buy-verdicts

The badge on each list line used to fetch `/stock-items/<id>/buy-verdict`
itself, so a 40-line list meant 40 requests. This endpoint answers for the
whole list at once. The contract that matters is that it says *the same thing*
as the per-item endpoint — a bulk path that quietly composes differently would
be worse than the N+1 it replaces.
"""
from uuid import uuid4

import pytest
import requests

from tests.factories import make_stock_item
from tests.support import set_money_enabled

BASE = "http://localhost:5170/api"
LISTS = f"{BASE}/shopping-lists"


@pytest.fixture(autouse=True)
def _money_on(api):
    """Buy verdicts are money-gated (R-058) and money is off on a fresh
    install. The flag is install-wide, so put it back afterwards."""
    original = requests.get(f"{BASE}/app-settings").json()["money_enabled"]
    set_money_enabled(True)
    yield
    set_money_enabled(original)


def _stock_level_id(sequence: int = 0) -> str:
    levels = requests.get(f"{BASE}/stock-levels").json()["items"]
    return next(l["stock_level_id"] for l in levels if l["sequence"] == sequence)


def _make_draft() -> str:
    resp = requests.post(LISTS, json={"name": f"Verdicts-{uuid4().hex[:8]}"})
    assert resp.status_code == 201, resp.text
    return resp.json()["shopping_list_id"]


def _add_item(list_id: str, *, sequence: int = 0) -> str:
    stock_item_id = make_stock_item(
        stock_level_id=_stock_level_id(sequence),
        name=f"Verdict-{uuid4().hex[:8]}",
    )["stock_item_id"]
    resp = requests.post(f"{LISTS}/{list_id}/lines", json={"stock_item_id": stock_item_id})
    assert resp.status_code == 200, resp.text
    return stock_item_id


def test__bulk_verdicts__one_entry_per_line_item(api):
    list_id = _make_draft()
    ids = {_add_item(list_id) for _ in range(3)}

    resp = requests.get(f"{LISTS}/{list_id}/buy-verdicts")
    assert resp.status_code == 200, resp.text
    verdicts = resp.json()["verdicts"]
    assert set(verdicts) == ids


def test__bulk_verdicts__match_the_per_item_endpoint(api):
    """The important one. Same composer, same gathered inputs — the bulk path
    exists to save round-trips, not to answer differently. Compared over an
    out-of-stock item so the verdict is a decisive `buy` rather than the
    `unsure` a history-less stocked item collapses to."""
    list_id = _make_draft()
    stock_item_id = _add_item(list_id, sequence=2)   # out of stock

    single = requests.get(f"{BASE}/stock-items/{stock_item_id}/buy-verdict")
    assert single.status_code == 200, single.text
    bulk = requests.get(f"{LISTS}/{list_id}/buy-verdicts")
    assert bulk.status_code == 200, bulk.text

    assert bulk.json()["verdicts"][stock_item_id] == single.json()
    assert single.json()["verdict"] == "buy"


def test__bulk_verdicts__empty_list_is_an_empty_map(api):
    list_id = _make_draft()
    resp = requests.get(f"{LISTS}/{list_id}/buy-verdicts")
    assert resp.status_code == 200, resp.text
    assert resp.json()["verdicts"] == {}


def test__bulk_verdicts__unknown_list_is_404(api):
    resp = requests.get(f"{LISTS}/{uuid4()}/buy-verdicts")
    assert resp.status_code == 404, resp.text


def _finished_list_with_priced_line(stock_item_id: str, *, ticked: bool) -> None:
    list_id = _make_draft()
    line_id = requests.post(
        f"{LISTS}/{list_id}/lines", json={"stock_item_id": stock_item_id},
    ).json()["line_id"]
    assert requests.patch(
        f"{LISTS}/{list_id}/lines/{line_id}",
        json={"actual_unit_price": 4.0, "is_ticked": ticked},
    ).status_code == 204
    assert requests.post(f"{LISTS}/{list_id}/finish").status_code == 200


def test__gather_verdict_inputs__PricedButUntickedLineOnDoneList__IsNotAPurchase(api):
    # R-061 — a stored price is not evidence of a purchase; only a ticked
    # (bought) line on a finished list is.
    from dora_api.app import app
    from dora_api.domain.entities.stock_item import StockItem
    from dora_api.features.stock_items.get_buy_verdict import \
        gather_verdict_inputs_for_items
    from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

    item_id = make_stock_item(stock_level_id=_stock_level_id(),
                              name=f"Verdict R-061 {uuid4().hex[:8]}")["stock_item_id"]
    _finished_list_with_priced_line(item_id, ticked=True)
    _finished_list_with_priced_line(item_id, ticked=False)

    with app.app_context():
        repo = SqlAlchemyRepository()
        item = repo.get(StockItem).by_id(item_id)
        inputs = gather_verdict_inputs_for_items(repo, [item])[item.id]

    assert len(inputs.price_samples) == 1
