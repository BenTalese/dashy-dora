"""Shopping-list lifecycle (status model).

UX v5 merged draft and shopping into one `active` status: a list is active
until `/finish` makes it `done`, and once done it's done (FU-163 retired
Reopen). Ticking a line on an active list restocks its item; unticking puts
the item's level back.
"""
from uuid import uuid4

import requests

from tests.support import assert_problem

BASE = "http://localhost:5170/api"
SHOPPING_LISTS = f"{BASE}/shopping-lists"


def _create_list(name: str) -> str:
    resp = requests.post(SHOPPING_LISTS, json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["shopping_list_id"]


def _detail(list_id: str) -> dict:
    resp = requests.get(f"{SHOPPING_LISTS}/{list_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def test__create_shopping_list__defaults_to_active_status(api):
    list_id = _create_list(f"Lifecycle active {uuid4()}")
    detail = _detail(list_id)
    assert detail["status"] == "active"
    # Legacy flags are gone from the DTO entirely.
    assert "is_archived" not in detail
    assert "is_in_progress" not in detail


def test__start_and_back_to_draft__are_removed(api):
    # UX v5: no shopping mode to enter or leave.
    list_id = _create_list(f"Lifecycle no-start {uuid4()}")
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/start").status_code == 404
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/back-to-draft").status_code == 404
    assert _detail(list_id)["status"] == "active"


def test__update__status_field_is_rejected(api):
    # /finish is the only transition; PATCH no longer takes a status.
    list_id = _create_list(f"Lifecycle no status patch {uuid4()}")
    resp = requests.patch(f"{SHOPPING_LISTS}/{list_id}", json={"status": "done"})
    assert resp.status_code in (400, 422), resp.text
    assert _detail(list_id)["status"] == "active"


def test__summaries__expose_status_not_legacy_flags(api):
    _create_list(f"Lifecycle summary {uuid4()}")
    summaries = requests.get(SHOPPING_LISTS).json()
    assert summaries, "expected at least one shopping list"
    for s in summaries:
        assert "status" in s
        assert s["status"] in ("active", "done")
        assert "is_archived" not in s
        assert "is_in_progress" not in s


def test__unfinish_endpoint_is_removed(api):
    # undo posture retired — /unfinish (Reopen) no longer exists.
    list_id = _create_list(f"Lifecycle no-reopen {uuid4()}")
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/finish").status_code == 200
    assert _detail(list_id)["status"] == "done"
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/unfinish").status_code == 404


def _levels_by_sequence() -> dict[int, str]:
    levels = requests.get(f"{BASE}/stock-levels").json()["items"]
    return {l["sequence"]: l["stock_level_id"] for l in levels}


def _item_level(item_id: str) -> str:
    resp = requests.get(f"{BASE}/stock-items/{item_id}/detail")
    assert resp.status_code == 200, resp.text
    return resp.json()["stock_level_id"]


def test__tick__restocks_the_item__and_untick_restores_its_level(api):
    # UX v5 D1: a tick is "bought" for the pantry straight away, and an
    # untick (a mis-tap, or Cancel on the last-tick prompt) puts it back.
    levels = _levels_by_sequence()
    stocked, out = levels[min(levels)], levels[max(levels)]
    created = requests.post(f"{BASE}/stock-items", json={
        "name": f"Lifecycle restock {uuid4().hex[:8]}", "stock_level_id": out,
    })
    assert created.status_code == 201, created.text
    item_id = created.json()["stock_item_id"]
    list_id = _create_list(f"Lifecycle restock {uuid4()}")
    added = requests.post(f"{SHOPPING_LISTS}/{list_id}/lines", json={"stock_item_id": item_id})
    line_id = added.json()["line_id"]

    tick = requests.patch(f"{SHOPPING_LISTS}/{list_id}/lines/{line_id}", json={"is_ticked": True})
    assert tick.status_code == 204, tick.text
    assert _item_level(item_id) == stocked

    untick = requests.patch(f"{SHOPPING_LISTS}/{list_id}/lines/{line_id}", json={"is_ticked": False})
    assert untick.status_code == 204, untick.text
    assert _item_level(item_id) == out

    # Ticked again and finished: still Stocked, and finishing doesn't undo it.
    requests.patch(f"{SHOPPING_LISTS}/{list_id}/lines/{line_id}", json={"is_ticked": True})
    finish = requests.post(f"{SHOPPING_LISTS}/{list_id}/finish")
    assert finish.status_code == 200, finish.text
    assert finish.json() == {"items_restocked": 1}
    assert _item_level(item_id) == stocked


def _new_stock_item() -> str:
    level = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    resp = requests.post(f"{BASE}/stock-items", json={
        "name": f"Lifecycle item {uuid4().hex[:8]}", "stock_level_id": level,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["stock_item_id"]


def _finished_list() -> str:
    list_id = _create_list(f"Lifecycle done {uuid4()}")
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/finish").status_code == 200
    assert _detail(list_id)["status"] == "done"
    return list_id


def test__add_line__OnDoneList__Returns422AndAddsNothing(api):
    # A done list is a receipt — /finish already restocked from it.
    list_id = _finished_list()

    resp = requests.post(
        f"{SHOPPING_LISTS}/{list_id}/lines", json={"stock_item_id": _new_stock_item()},
    )

    assert_problem(resp, 422, title="Business rule violation.")
    assert _detail(list_id)["lines"] == []


def test__bulk_add__OnDoneList__IsRefusedForTheWholeList(api):
    list_id = _finished_list()
    item_id = _new_stock_item()

    resp = requests.post(
        f"{SHOPPING_LISTS}/{list_id}/lines/bulk-add", json={"lines": [{"stock_item_id": item_id}]},
    )

    # A finished list is a list-level answer (like a missing one), not a
    # per-item failure: 422 with the same copy as the single-line route.
    assert resp.status_code == 422, resp.text
    assert "finished" in resp.text
    assert _detail(list_id)["lines"] == []


def test__assistant_add__OnDoneList__IsTheListLevelRefusal(api):
    # FU-969 (4): the assistant's add paths give the same list-level answer
    # as bulk-add instead of counting every item as "couldn't be added".
    from dora_api.features.shopping_lists.manage_shopping_list_lines import LIST_DONE_REFUSAL

    list_id = _finished_list()
    item_id = _new_stock_item()

    act = requests.post(f"{BASE}/assistant/act", json={
        "shopping_list_id": list_id, "items": [{"stock_item_id": item_id, "quantity": 1}],
    })
    assert_problem(act, 422, title="Business rule violation.")
    assert LIST_DONE_REFUSAL in act.text

    confirm = requests.post(f"{BASE}/assistant/confirm", json={
        "type": "add_recipe_to_list",
        "payload": {
            "shopping_list_id": list_id, "list_name": "Done list", "recipe_name": "Toast",
            "stock_item_ids": [item_id], "ingredient_names": ["Bread"],
        },
    })
    assert confirm.status_code == 200, confirm.text
    assert confirm.json() == {"ok": False, "answer": LIST_DONE_REFUSAL}
    assert _detail(list_id)["lines"] == []


def test__quick_add__HintAtDoneList__Returns422(api):
    list_id = _finished_list()

    resp = requests.post(f"{SHOPPING_LISTS}/quick-add/lines", json={
        "stock_item_id": _new_stock_item(), "shopping_list_id": list_id,
    })

    assert_problem(resp, 422, title="Business rule violation.")
    assert _detail(list_id)["lines"] == []


def test__discard_unticked__MixedLines__RemovesOnlyTheUntickedOnes(api):
    # The finish dialog's "I didn't want them after all" branch: the ticked
    # line is what was bought and must survive; the unticked ones go.
    list_id = _create_list(f"Lifecycle discard {uuid4()}")
    for _ in range(3):
        added = requests.post(
            f"{SHOPPING_LISTS}/{list_id}/lines", json={"stock_item_id": _new_stock_item()},
        )
        assert added.status_code == 200, added.text
    lines = _detail(list_id)["lines"]
    kept = lines[0]["line_id"]
    ticked = requests.patch(
        f"{SHOPPING_LISTS}/{list_id}/lines/{kept}", json={"is_ticked": True},
    )
    assert ticked.status_code == 204, ticked.text

    resp = requests.post(f"{SHOPPING_LISTS}/{list_id}/discard-unticked")

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"removed_count": 2}
    assert [l["line_id"] for l in _detail(list_id)["lines"]] == [kept]


def test__discard_unticked__UnknownList__Returns404(api):
    resp = requests.post(f"{SHOPPING_LISTS}/{uuid4()}/discard-unticked")
    assert_problem(resp, 404)


def _out_item() -> tuple[str, str, str]:
    """A fresh item at Out, plus the Stocked and Out level ids."""
    levels = _levels_by_sequence()
    stocked, out = levels[min(levels)], levels[max(levels)]
    created = requests.post(f"{BASE}/stock-items", json={
        "name": f"Lifecycle restock {uuid4().hex[:8]}", "stock_level_id": out,
    })
    assert created.status_code == 201, created.text
    return created.json()["stock_item_id"], stocked, out


def _tick(list_id: str, line_id: str, value: bool) -> None:
    resp = requests.patch(f"{SHOPPING_LISTS}/{list_id}/lines/{line_id}", json={"is_ticked": value})
    assert resp.status_code == 204, resp.text


def _new_product() -> str:
    suffix = uuid4().hex[:8]
    resp = requests.post(f"{BASE}/products", json={
        "name": f"Lifecycle product {suffix}", "store_name": "Woolworths",
        "merchant_stockcode": f"LC-{suffix}", "is_active": True, "is_available": True,
        "price_now": 3.0, "size": "1L", "size_unit": "L", "size_value": 1.0,
    })
    assert resp.status_code == 201, resp.text
    return resp.headers["location"].rsplit(":", 1)[-1]


def test__parent_and_nested_lines__untick_both_puts_the_original_level_back(api):
    # A nested product line shares its parent's item: the item has one
    # pre-tick level, whichever line is ticked or unticked first.
    item_id, stocked, out = _out_item()
    list_id = _create_list(f"Lifecycle nested {uuid4()}")
    nested = requests.post(f"{SHOPPING_LISTS}/{list_id}/lines", json={
        "stock_item_id": item_id, "product_id": _new_product(),
    }).json()["line_id"]
    parent = requests.post(f"{SHOPPING_LISTS}/{list_id}/lines", json={
        "stock_item_id": item_id,
    }).json()["line_id"]

    _tick(list_id, parent, True)
    _tick(list_id, nested, True)
    assert _item_level(item_id) == stocked
    _tick(list_id, parent, False)
    assert _item_level(item_id) == stocked, "the nested line still holds the restock"
    _tick(list_id, nested, False)
    assert _item_level(item_id) == out

    # And the finish count is per item, not per line.
    _tick(list_id, parent, True)
    _tick(list_id, nested, True)
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/finish").json() == {"items_restocked": 1}


def test__deleting_a_ticked_line__gives_the_restock_back(api):
    item_id, _, out = _out_item()
    list_id = _create_list(f"Lifecycle delete {uuid4()}")
    line_id = requests.post(
        f"{SHOPPING_LISTS}/{list_id}/lines", json={"stock_item_id": item_id},
    ).json()["line_id"]
    _tick(list_id, line_id, True)

    assert requests.delete(f"{SHOPPING_LISTS}/{list_id}/lines/{line_id}").status_code == 204
    assert _item_level(item_id) == out


def test__clearing_a_list__gives_every_restock_back(api):
    item_id, _, out = _out_item()
    list_id = _create_list(f"Lifecycle clear {uuid4()}")
    line_id = requests.post(
        f"{SHOPPING_LISTS}/{list_id}/lines", json={"stock_item_id": item_id},
    ).json()["line_id"]
    _tick(list_id, line_id, True)

    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/clear").status_code == 200
    assert _item_level(item_id) == out


def test__untick_after_a_hand_edit__leaves_the_hand_edit(api):
    # Undoing a tick must not undo something else that happened since.
    item_id, _, _ = _out_item()
    low = _levels_by_sequence()[1]
    list_id = _create_list(f"Lifecycle hand edit {uuid4()}")
    line_id = requests.post(
        f"{SHOPPING_LISTS}/{list_id}/lines", json={"stock_item_id": item_id},
    ).json()["line_id"]
    _tick(list_id, line_id, True)
    assert requests.patch(
        f"{BASE}/stock-items/{item_id}", json={"stock_level_id": low},
    ).status_code == 204

    _tick(list_id, line_id, False)

    assert _item_level(item_id) == low


def test__ticking_a_done_list__moves_no_stock(api):
    item_id, _, out = _out_item()
    list_id = _create_list(f"Lifecycle done tick {uuid4()}")
    line_id = requests.post(
        f"{SHOPPING_LISTS}/{list_id}/lines", json={"stock_item_id": item_id},
    ).json()["line_id"]
    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/finish").status_code == 200

    _tick(list_id, line_id, True)

    assert _item_level(item_id) == out


def test__finish__restocks_a_tick_from_before_restock_on_tick(api):
    # Lines ticked before UX v5 carry no restock record; /finish restocks them.
    from sqlalchemy import text

    from dora_api.app import app, db
    from tests.support import uuid_bind

    item_id, stocked, out = _out_item()
    list_id = _create_list(f"Lifecycle legacy tick {uuid4()}")
    line_id = requests.post(
        f"{SHOPPING_LISTS}/{list_id}/lines", json={"stock_item_id": item_id},
    ).json()["line_id"]
    _tick(list_id, line_id, True)
    with app.app_context(), db.engine.begin() as conn:
        conn.execute(
            text('UPDATE "ShoppingListLine" SET restocked_at = NULL, '
                 'restock_from_level_id = NULL, restock_from_level_updated_at = NULL '
                 'WHERE id = :lid'),
            {"lid": uuid_bind(line_id)},
        )
        conn.execute(
            text('UPDATE "StockItem" SET stock_level_id = :out WHERE id = :sid'),
            {"out": uuid_bind(out), "sid": uuid_bind(item_id)},
        )
    assert _item_level(item_id) == out

    assert requests.post(f"{SHOPPING_LISTS}/{list_id}/finish").json() == {"items_restocked": 1}
    assert _item_level(item_id) == stocked
