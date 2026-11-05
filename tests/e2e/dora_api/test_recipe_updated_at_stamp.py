"""FU-730 — `Recipe.updated_at` moves on every write that edits a recipe, and
only those.

The stamp lives in the save path (`persistence/recipe_edit_stamp.py`), not in
the PATCH handler alone, so a second writer — here the bulk ingredient linker —
moves it too. Cooking and the favourite star record what happened to a recipe,
not what it is, and leave it alone.
"""
from uuid import UUID, uuid4

import requests

from dora_api.app import app, db
from dora_api.domain.entities.recipe import Recipe
from tests.factories import make_stock_item

BASE = "http://localhost:5170/api"
RECIPES = f"{BASE}/recipes"


def _updated_at(recipe_id: str):
    with app.app_context():
        value = db.session.get(Recipe, UUID(recipe_id)).updated_at
        db.session.remove()
    return value


def _make_recipe(raw_text: str) -> str:
    resp = requests.post(RECIPES, json={
        "name": f"Stamp recipe {uuid4().hex[:8]}",
        "ingredients": [{"raw_text": raw_text}],
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["recipe_id"]


def test__updated_at__cook_and_favourite_leave_it__an_edit_moves_it(api):
    recipe_id = _make_recipe(f"Stamp onion {uuid4().hex[:8]}")
    assert _updated_at(recipe_id) is None  # a new recipe has created_at only

    assert requests.patch(f"{RECIPES}/{recipe_id}", json={"is_favourite": True}).status_code == 204
    assert requests.post(f"{RECIPES}/{recipe_id}/cook", json={"meals_cooked": 1}).status_code == 200
    assert _updated_at(recipe_id) is None

    assert requests.patch(f"{RECIPES}/{recipe_id}", json={"notes": "halve the chilli"}).status_code == 204
    assert _updated_at(recipe_id) is not None


def test__updated_at__a_new_sectioned_recipe_is_not_stamped(api):
    # Create flushes the recipe, then back-fills its ingredients' section ids
    # before committing; that back-fill isn't an edit.
    resp = requests.post(RECIPES, json={
        "name": f"Stamp sectioned {uuid4().hex[:8]}",
        "sections": [{"client_id": "s-1", "sequence": 0, "name": "Sauce"}],
        "ingredients": [{"raw_text": f"Stamp basil {uuid4().hex[:8]}", "section_client_id": "s-1"}],
    })
    assert resp.status_code == 201, resp.text
    assert _updated_at(resp.json()["recipe_id"]) is None


def test__updated_at__bulk_ingredient_link_stamps_the_recipe(api):
    token = uuid4().hex[:8]
    recipe_id = _make_recipe(f"Stamp anise {token}")
    levels = requests.get(f"{BASE}/stock-levels").json()["items"]
    item = make_stock_item(
        stock_level_id=next(l["stock_level_id"] for l in levels if l["sequence"] == 0),
        name=f"Stamp Anise {token}",
    )

    resp = requests.post(f"{RECIPES}/unlinked-ingredients/bulk-link", json={
        "raw_text": f"Stamp anise {token}", "stock_item_id": item["stock_item_id"],
    })
    assert resp.status_code == 200 and resp.json()["linked_count"] == 1, resp.text
    assert _updated_at(recipe_id) is not None
