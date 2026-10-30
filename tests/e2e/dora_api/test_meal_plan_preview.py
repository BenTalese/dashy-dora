"""Meal Plans C-2.J — preview ingredients for an unsaved selection."""
import requests

MEAL_PLANS = "http://localhost:5170/api/meal-plans"
RECIPES = "http://localhost:5170/api/recipes"


def _recipe_with_ingredients() -> str | None:
    items = requests.get(f"{RECIPES}?limit=50").json()["items"]
    return next((r["recipe_id"] for r in items if r.get("ingredients")), None)


def test_preview_ingredients_returns_aggregated_list():
    resp = requests.post(f"{MEAL_PLANS}/preview-ingredients", json={
        "recipes": [{"recipe_id": _recipe_with_ingredients() or requests.get(f"{RECIPES}?limit=1").json()["items"][0]["recipe_id"], "servings": 2}],
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, dict) and "items" in body and "unlinked" in body
    for ing in body["items"]:
        assert "stock_item_id" in ing
        assert "used_in_recipe_ids" in ing
        # Owner feedback 2026-08-27 — the shared add-to-list picker files
        # optional ingredients into their own unticked section, so the
        # aggregate has to say which items are optional.
        assert "is_optional" in ing


def test_preview_ingredients_summarises_bands_and_cost():
    """Owner 2026-09-12 — the builder's "What you'll need" says how many items
    are *low* vs *out* (a low one may not need buying at all), what those would
    cost, and what the whole selection is worth. All four are server-derived:
    the bands read the stock levels behind the aggregate, the money comes from
    the app's one pricing ladder."""
    recipe_id = _recipe_with_ingredients()
    assert recipe_id is not None, "the seed ships recipes with ingredients"
    body = requests.post(f"{MEAL_PLANS}/preview-ingredients", json={
        "recipes": [{"recipe_id": recipe_id, "servings": 2}],
    }).json()

    assert body["low_count"] + body["out_count"] <= len(body["items"])
    # A cost is either absent (money off / nothing priced) or a real figure —
    # never a zero standing in for "we couldn't work it out".
    for key in ("to_buy_cost", "meals_cost"):
        assert body[key] is None or body[key] > 0
    if body["to_buy_cost"] is not None:
        assert body["meals_cost"] is not None
        # The shop is a subset of the demand, so it can't cost more than it.
        assert body["to_buy_cost"] <= body["meals_cost"] + 0.01


def _recipe_with_unlinked_ingredient() -> str | None:
    """A paste-imported recipe carrying at least one ingredient that was never
    linked to a stock item (Chunk 4). The dev seed ships two."""
    items = requests.get(f"{RECIPES}?limit=50").json()["items"]
    return next(
        (r["recipe_id"] for r in items if r.get("unlinked_ingredient_count", 0) > 0),
        None,
    )


def test_preview_ingredients_with_unlinked_ingredient_reports_it():
    """Regression: the aggregator read `.id` off a None stock item, so ONE
    unlinked row anywhere in the selection 500'd the endpoint (and the saved
    plan's /ingredients with it). Unlinked rows still can't become lines — a
    shopping list is a list of stock items — but since 2026-08-27 they're
    *named* in `unlinked` rather than dropped, which is how the picker-driven
    add keeps FU-505's promise now that it no longer calls auto-generate."""
    recipe_id = _recipe_with_unlinked_ingredient()
    assert recipe_id is not None, "the seed ships a recipe with an unlinked ingredient"
    resp = requests.post(f"{MEAL_PLANS}/preview-ingredients", json={
        "recipes": [{"recipe_id": recipe_id, "servings": 2}],
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["unlinked"]) > 0
    for u in body["unlinked"]:
        assert u["recipe_name"] and u["ingredient_name"]


def test_preview_empty_selection_is_empty():
    resp = requests.post(f"{MEAL_PLANS}/preview-ingredients", json={"recipes": []})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "items": [], "unlinked": [],
        "low_count": 0, "out_count": 0, "to_buy_cost": None, "meals_cost": None,
    }
