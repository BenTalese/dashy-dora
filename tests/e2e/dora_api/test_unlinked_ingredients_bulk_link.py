"""IMPL_PLAN_RECIPE_IMPORTER §Chunk 6 — bulk-linker endpoint e2e.

`tests/test_unlinked_ingredients.py` pins the *pure* grouper; its own
docstring notes the endpoints themselves are only exercised via the SPA
browser walk. This closes that gap (DORA_VERIFY Cookbook L136): the GET
grouping over real persisted rows and the
``POST /recipes/unlinked-ingredients/bulk-link`` mutation — including the
server-owned cookability re-derive, only-matching-rows, and the
not-found / empty-key error paths.

Unlinked ingredients are created directly via ``POST /recipes`` with a
``raw_text``-only ingredient (the shape a paste import lands when
RapidFuzz misses a match). Every recipe uses a unique token so the group
under test is isolated from any seed unlinked rows.
"""
from uuid import uuid4

import requests

from tests.factories import make_stock_item
from tests.support import assert_problem

BASE = "http://localhost:5170/api"
RECIPES = f"{BASE}/recipes"
UNLINKED = f"{RECIPES}/unlinked-ingredients"
BULK_LINK = f"{UNLINKED}/bulk-link"


def _stock_level_id(sequence: int) -> str:
    levels = requests.get(f"{BASE}/stock-levels").json()["items"]
    return next(l["stock_level_id"] for l in levels if l["sequence"] == sequence)


def _make_recipe_with_unlinked(raw_text: str) -> dict:
    resp = requests.post(RECIPES, json={
        "name": f"BulkLink recipe {uuid4().hex[:8]}",
        "ingredients": [{"raw_text": raw_text}],
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def _by_id(recipe_id: str) -> dict | None:
    items = requests.get(f"{RECIPES}?filter=recipe_id:eq:{recipe_id}").json()["items"]
    return items[0] if items else None


def _find_group(token: str) -> dict | None:
    """The unlinked group whose display text carries our unique token."""
    groups = requests.get(UNLINKED).json()["unlinked"]
    return next((g for g in groups if token.lower() in g["raw_text"].lower()), None)


def test__bulk_link__links_matching_rows_across_recipes_and_rederives_cookability(api):
    token = uuid4().hex[:8]
    stocked = make_stock_item(
        stock_level_id=_stock_level_id(0), name=f"BulkLink Anise {token}",
    )

    # Two recipes pin the same ingredient with different casing/whitespace →
    # one normalised group of count 2.
    a = _make_recipe_with_unlinked(f"Star Anise {token}")
    b = _make_recipe_with_unlinked(f"  star   anise   {token} ")

    # Both start tri-state Unknown (a required ingredient is unlinked).
    row_a = _by_id(a["recipe_id"])
    assert row_a["cookable"] is None
    assert row_a["unlinked_ingredient_count"] == 1

    group = _find_group(token)
    assert group is not None
    assert group["count"] == 2
    assert set(group["used_in_recipe_ids"]) == {a["recipe_id"], b["recipe_id"]}

    # Link the whole group in one call.
    resp = requests.post(BULK_LINK, json={
        "raw_text": f"Star Anise {token}",
        "stock_item_id": stocked["stock_item_id"],
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["linked_count"] == 2

    # Both recipes' rows now point at the item; raw_text is preserved; the
    # Stocked link makes cookability re-derive to a real True.
    for created in (a, b):
        row = _by_id(created["recipe_id"])
        assert row["cookable"] is True
        assert row["unlinked_ingredient_count"] == 0
        ing = row["ingredients"][0]
        assert ing["stock_item_id"] == stocked["stock_item_id"]
        assert token.lower() in (ing["raw_text"] or "").lower()

    # The group has left the unlinked list.
    assert _find_group(token) is None


def test__bulk_link__only_the_matching_group_is_linked(api):
    token = uuid4().hex[:8]
    stocked = make_stock_item(
        stock_level_id=_stock_level_id(0), name=f"BulkLink Fennel {token}",
    )
    target = _make_recipe_with_unlinked(f"Fennel {token}")
    bystander = _make_recipe_with_unlinked(f"Cardamom {token}")

    resp = requests.post(BULK_LINK, json={
        "raw_text": f"Fennel {token}",
        "stock_item_id": stocked["stock_item_id"],
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["linked_count"] == 1

    # Target linked; the different-text bystander stays unlinked.
    assert _by_id(target["recipe_id"])["ingredients"][0]["stock_item_id"] == stocked["stock_item_id"]
    bystander_row = _by_id(bystander["recipe_id"])
    assert bystander_row["ingredients"][0]["stock_item_id"] is None
    assert bystander_row["unlinked_ingredient_count"] == 1


def test__bulk_link__unknown_stock_item__entity_existence_failure(api):
    token = uuid4().hex[:8]
    _make_recipe_with_unlinked(f"Mace {token}")
    resp = requests.post(BULK_LINK, json={
        "raw_text": f"Mace {token}",
        "stock_item_id": str(uuid4()),
    })
    assert_problem(resp, 422, field="stock_item_id")


def test__bulk_link__raw_text_normalising_to_empty__bad_request(api):
    stocked = make_stock_item(
        stock_level_id=_stock_level_id(0), name=f"BulkLink Empty {uuid4().hex[:8]}",
    )
    # min_length=1 lets a whitespace-only string past validation, but it
    # normalises to an empty key → the handler rejects it rather than
    # silently linking every unlinked row in the install.
    resp = requests.post(BULK_LINK, json={
        "raw_text": "   ",
        "stock_item_id": stocked["stock_item_id"],
    })
    assert resp.status_code == 400, resp.text


def test__unlinked_ingredient_count__matches_the_list(api):
    # FU-858: the settings badge reads the count, not the list.
    listed = len(requests.get(f"{BASE}/recipes/unlinked-ingredients").json()["unlinked"])
    assert requests.get(f"{BASE}/recipes/unlinked-ingredients/count").json() == {"count": listed}
    assert requests.get(f"{BASE}/nutrition/unmatched-items/count").status_code == 200
