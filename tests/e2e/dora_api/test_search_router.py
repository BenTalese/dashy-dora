"""FU-519 / PROPOSAL_TEST_SUITE_IMPROVEMENTS §5.D — global search e2e.

GET /api/search?q=…&types=…&limit=N — the last of the four ⚠️ priority
surfaces (the 2026-07-10 sweep shipped recipes / meal_plans / dashboard).
Pins the unified-results contract: result shape, per-type scoring order
(exact > prefix > contains > fuzzy), subtitle derivation per type, the
types filter, and the limit clamp semantics (per *type*, not global).
"""
from uuid import uuid4

import requests

from tests.factories import make_stock_item

BASE = "http://localhost:5170/api"
SEARCH = f"{BASE}/search"

RESULT_KEYS = {"type", "id", "title", "subtitle", "icon", "score", "match_spans"}


def _token() -> str:
    """A collision-proof, letters-only search token. Hex can collide with
    fuzzy matches against seed data; a `zq` prefix keeps it improbable."""
    return f"zq{uuid4().hex[:8]}"


def _search(q: str, **params) -> list[dict]:
    resp = requests.get(SEARCH, params={"q": q, **params})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {"results"}
    return body["results"]


def _stock_level_id() -> str:
    levels = requests.get(f"{BASE}/stock-levels").json()["items"]
    return levels[0]["stock_level_id"]


def _make_recipe(name: str) -> dict:
    resp = requests.post(f"{BASE}/recipes", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _make_tree_location(name: str, kind: str, parent_id: str | None = None) -> str:
    """Create a location through the tree API (`POST /api/locations`).
    Returns the new id."""
    body: dict = {"name": name, "kind": kind}
    if parent_id is not None:
        body["parent_id"] = parent_id
    resp = requests.post(f"{BASE}/locations", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["location_id"]


#region ---------------- basic contract ----------------


def test__search__EmptyQuery__EmptyResults(api):
    assert _search("") == []
    assert _search("   ") == []


def test__search__NoMatches__EmptyResults(api):
    assert _search(_token()) == []


def test__search__MatchingStockItem__FullResultShape(api):
    token = _token()
    item = make_stock_item(stock_level_id=_stock_level_id(), name=f"{token} paste")

    results = _search(token)

    hits = [r for r in results if r["id"] == item["stock_item_id"]]
    assert len(hits) == 1
    hit = hits[0]
    assert set(hit.keys()) == RESULT_KEYS
    assert hit["type"] == "stock_item"
    assert hit["title"] == f"{token} paste"
    # `token` starts the title → prefix score band (150+), above threshold.
    assert hit["score"] >= 150
    # Spans mark where the query sits in the title for highlight rendering.
    assert hit["match_spans"] == [[0, len(token)]]

#endregion basic contract

#region ---------------- scoring order ----------------


def test__search__ExactBeatsPrefixBeatsContains__OrderedByScore(api):
    token = _token()
    level = _stock_level_id()
    exact = make_stock_item(stock_level_id=level, name=token)
    prefix = make_stock_item(stock_level_id=level, name=f"{token} sauce")
    contains = make_stock_item(stock_level_id=level, name=f"organic {token} sauce")

    results = _search(token, types="stock_item")

    ordered = [r["id"] for r in results]
    assert ordered.index(exact["stock_item_id"]) \
        < ordered.index(prefix["stock_item_id"]) \
        < ordered.index(contains["stock_item_id"])


def test__search__TypoTolerance__FuzzyMatchStillFound(api):
    # partial_ratio must clear the 75 threshold for a one-letter typo of a
    # long-ish word ("blueberrie" vs "blueberries yoghurt").
    token = _token()
    item = make_stock_item(
        stock_level_id=_stock_level_id(), name=f"blueberries yoghurt {token}",
    )

    results = _search("bluberries yoghurt")

    assert any(r["id"] == item["stock_item_id"] for r in results)
    # A fuzzy (non-substring) match carries no highlight spans.
    hit = next(r for r in results if r["id"] == item["stock_item_id"])
    assert hit["match_spans"] == []

#endregion scoring order

#region ---------------- per-type subtitles ----------------


def test__search__StockItemWithLocation__SubtitleIsBreadcrumb(api):
    token = _token()
    parent_id = _make_tree_location(f"Pantry {token}", "zone")
    child_id = _make_tree_location(f"Top shelf {token}", "area", parent_id)
    item = make_stock_item(
        stock_level_id=_stock_level_id(),
        name=f"{token} beans",
        stock_location_id=child_id,
    )

    results = _search(f"{token} beans", types="stock_item")

    hit = next(r for r in results if r["id"] == item["stock_item_id"])
    assert hit["subtitle"] == f"Pantry {token} › Top shelf {token}"


def test__search__Location__SubtitleIsParentPathWithoutSelf(api):
    token = _token()
    parent_id = _make_tree_location(f"Garage {token}", "zone")
    child_id = _make_tree_location(f"Chest freezer {token}", "area", parent_id)

    results = _search(f"Chest freezer {token}", types="location")

    hit = next(r for r in results if r["id"] == child_id)
    assert hit["type"] == "location"
    # Breadcrumb excludes the location itself; a root location gets None.
    assert hit["subtitle"] == f"Garage {token}"
    root_hit = next(
        r for r in _search(f"Garage {token}", types="location")
        if r["id"] == parent_id
    )
    assert root_hit["subtitle"] is None


def test__search__ActiveShoppingList__SubtitleIsListLabel(api):
    token = _token()
    created = requests.post(
        f"{BASE}/shopping-lists", json={"name": f"{token} shop"},
    )
    assert created.status_code == 201, created.text
    list_id = created.json()["shopping_list_id"]

    results = _search(token, types="shopping_list")

    hit = next(r for r in results if r["id"] == list_id)
    assert hit["subtitle"] == "Shopping list"


def test__search__Recipe__FoundWithRecipeType(api):
    token = _token()
    recipe = _make_recipe(f"{token} curry")

    results = _search(token, types="recipe")

    hit = next(r for r in results if r["id"] == recipe["recipe_id"])
    assert hit["type"] == "recipe"
    assert hit["title"] == f"{token} curry"

#endregion subtitles

#region ---------------- types filter + limit ----------------


def test__search__TypesFilter__OnlyRequestedTypesReturned(api):
    token = _token()
    make_stock_item(stock_level_id=_stock_level_id(), name=f"{token} twin")
    _make_recipe(f"{token} twin")

    only_recipes = _search(f"{token} twin", types="recipe")
    both = _search(f"{token} twin", types="recipe,stock_item")

    assert {r["type"] for r in only_recipes} == {"recipe"}
    assert {r["type"] for r in both} == {"recipe", "stock_item"}


def test__search__UnknownTypesValue__FallsBackToAllTypes(api):
    # Contract pin: invalid entries are dropped, and an all-invalid `types`
    # behaves like no filter at all (rather than matching nothing).
    token = _token()
    item = make_stock_item(stock_level_id=_stock_level_id(), name=f"{token} relish")

    results = _search(f"{token} relish", types="poopusgoopus")

    assert any(r["id"] == item["stock_item_id"] for r in results)


def test__search__Limit__AppliesPerTypeAndClampsToRange(api):
    token = _token()
    level = _stock_level_id()
    for i in range(3):
        make_stock_item(stock_level_id=level, name=f"{token} jar {i}")
    _make_recipe(f"{token} jar recipe")

    limited = _search(token, types="stock_item", limit=2)
    assert len(limited) == 2

    # The limit is per type: 2 stock items + the recipe can coexist.
    mixed = _search(token, types="stock_item,recipe", limit=2)
    assert len([r for r in mixed if r["type"] == "stock_item"]) == 2
    assert len([r for r in mixed if r["type"] == "recipe"]) == 1

    # Zero / negative / non-numeric limits stay within [1, 25] or fall
    # back to the default — never a 500, never an unbounded page.
    assert len(_search(token, types="stock_item", limit=0)) == 1
    assert len(_search(token, types="stock_item", limit=-5)) == 1
    assert len(_search(token, types="stock_item", limit="true")) == 3

#endregion types filter + limit
