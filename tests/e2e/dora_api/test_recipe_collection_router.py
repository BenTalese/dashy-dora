"""FU-519 item 2 — recipe collection router e2e
(`dora_api/features/recipe_collections/`).

Unlike the taxonomy routers (bare list + count-reporting deletes), this is a
paginated `{items,total,page,limit}` envelope with 204 update/delete — pinned
as such. Deleting a collection nulls referencing recipes' FK silently.
"""
from uuid import uuid4

import pytest
import requests

from tests.e2e.dora_api._error_assertions import domain_err, validation_err
from tests.support import assert_envelope, assert_problem, is_valid_uuid

BASE = "http://localhost:5170/api"
COLLECTIONS = f"{BASE}/recipe-collections"


def _name(prefix: str = "Collection") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _create(name: str) -> str:
    resp = requests.post(COLLECTIONS, json={"name": name})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # Create echoes the full DTO.
    assert body["name"] == name
    assert is_valid_uuid(body["recipe_collection_id"])
    assert f"filter=recipe_collection_id:eq:{body['recipe_collection_id']}" \
        in resp.headers["location"]
    return body["recipe_collection_id"]


def _get_by_id(collection_id: str) -> dict | None:
    resp = requests.get(
        COLLECTIONS, params={"filter": f"recipe_collection_id:eq:{collection_id}"},
    )
    items = assert_envelope(resp)
    return items[0] if items else None


def test__create_recipe_collection__NewName__CreatedAndListed(api):
    name = _name("Weeknight")

    collection_id = _create(name)

    row = _get_by_id(collection_id)
    assert row == {"recipe_collection_id": collection_id, "name": name, "recipe_count": 0}


def test__create_recipe_collection__DuplicateName__IsBusinessRuleViolation(api):
    name = _name("Sunday")
    _create(name)

    resp = requests.post(COLLECTIONS, json={"name": name})

    body = assert_problem(resp, 422, title="Business rule violation.")
    assert body["errors"] == {
        "": [domain_err(f"A recipe collection with the name '{name}' already exists.")],
    }


def test__create_recipe_collection__EmptyRequest__IsValidationFailure(api):
    resp = requests.post(COLLECTIONS, json={})

    body = assert_problem(resp, 400, field="name", title="Malformed request.")
    assert body["errors"]["name"] == [validation_err("missing", "Field required")]


def test__get_recipe_collections__PaginatedEnvelope__PageAndLimitRespected(api):
    for i in range(2):
        _create(_name(f"Page{i}"))

    resp = requests.get(COLLECTIONS, params={"page": 1, "limit": 1})

    items = assert_envelope(resp)
    assert len(items) == 1
    assert resp.json()["page"] == 1
    assert resp.json()["limit"] == 1
    assert resp.json()["total"] >= 2


@pytest.mark.parametrize(
    "query,invalid_field",
    [
        ("page=true&limit=2", "page"),
        ("page=1&limit=true", "limit"),
    ],
    ids=["page-is-not-integer", "limit-is-not-integer"],
)
def test__get_recipe_collections__PaginationValueIsNotInteger__IsBadRequest(
    api, query, invalid_field,
):
    resp = requests.get(f"{COLLECTIONS}?{query}")

    assert_problem(resp, 400, title=f"'{invalid_field}' must be an integer.")


def test__update_recipe_collection__Rename__NewNameListed(api):
    collection_id = _create(_name("Summer"))
    new_name = _name("Winter")

    resp = requests.patch(f"{COLLECTIONS}/{collection_id}", json={"name": new_name})

    assert resp.status_code == 204
    assert _get_by_id(collection_id)["name"] == new_name


def test__update_recipe_collection__RenameToExistingName__IsBusinessRuleViolation(api):
    taken = _name("Feasts")
    _create(taken)
    other_id = _create(_name("Snacks"))

    resp = requests.patch(f"{COLLECTIONS}/{other_id}", json={"name": taken})

    body = assert_problem(resp, 422, title="Business rule violation.")
    assert body["errors"] == {
        "": [domain_err(f"A recipe collection with the name '{taken}' already exists.")],
    }


def test__delete_recipe_collection__WithRecipeAttached__RecipeSurvivesUnlinked(api):
    collection_id = _create(_name("Doomed"))
    recipe = requests.post(f"{BASE}/recipes", json={
        "name": _name("Orphan pie"), "recipe_collection_id": collection_id,
    })
    assert recipe.status_code == 201, recipe.text

    resp = requests.delete(f"{COLLECTIONS}/{collection_id}")

    assert resp.status_code == 204
    assert _get_by_id(collection_id) is None
    # The recipe outlives its collection (FK → NULL).
    still_there = requests.get(f"{BASE}/recipes/{recipe.json()['recipe_id']}")
    assert still_there.status_code == 200


def test__recipe_collection_endpoints__UnknownId__NotFound(api):
    missing_id = uuid4()
    detail = f"RecipeCollection with the ID '{missing_id}' was not found."

    assert_problem(
        requests.patch(f"{COLLECTIONS}/{missing_id}", json={"name": "Ghost"}),
        404, detail=detail,
    )
    assert_problem(requests.delete(f"{COLLECTIONS}/{missing_id}"), 404, detail=detail)


def test__get_recipe_collections__RecipeAttached__CountsIt(api):
    # The Collections settings page shows "used by N recipes" from this.
    collection_id = _create(_name("Counted"))
    assert _get_by_id(collection_id)["recipe_count"] == 0
    recipe = requests.post(f"{BASE}/recipes", json={
        "name": _name("Counted pie"), "recipe_collection_id": collection_id,
    })
    assert recipe.status_code == 201, recipe.text

    assert _get_by_id(collection_id)["recipe_count"] == 1
