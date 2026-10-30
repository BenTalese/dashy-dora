"""C-4 Chunk 8 — `POST /recipes/<id>/new-version` numbering + inheritance.

`test_new_recipe_version_unit_of_work.py` only pins the happy-path commit;
`test_recipe_notes.py` pins the note carry-over. This closes the two
behavioural gaps the browser checklist called out (DORA_VERIFY Cookbook
L199 / L200 / L201):

* version numbering — a singleton allocates a `version_group_id` that's
  back-filled onto the source, the copy is named `(v2)`, and the number is
  **one past the highest used in the group**, so a third version off the
  *copy* is `<base> (v4)` (not `(v2)` again, and not `(v2) (v4)`), and a
  deleted sibling's number is never reused;
* inheritance — the copy carries the source's scalar fields, ingredients,
  cuisine/category, and starts un-favourited with a fresh id;
* independence — editing the copy leaves the source untouched.
"""
from uuid import uuid4

import requests

from tests.factories import make_stock_item

BASE = "http://localhost:5170/api"
RECIPES = f"{BASE}/recipes"


def _stock_level_id(sequence: int) -> str:
    levels = requests.get(f"{BASE}/stock-levels").json()["items"]
    return next(l["stock_level_id"] for l in levels if l["sequence"] == sequence)


def _first_vocab_id(kind: str) -> str | None:
    """First seeded cuisine/category id, or None if the vocab is empty."""
    resp = requests.get(f"{BASE}/{kind}")
    if resp.status_code != 200:
        return None
    body = resp.json()
    items = body if isinstance(body, list) else body.get("items", [])
    if not items:
        return None
    row = items[0]
    return row.get(f"{kind[:-1]}_id") or row.get("id")


def _by_id(recipe_id: str) -> dict:
    items = requests.get(f"{RECIPES}?filter=recipe_id:eq:{recipe_id}").json()["items"]
    assert items, f"recipe {recipe_id} not found"
    return items[0]


def _new_version(recipe_id: str) -> str:
    resp = requests.post(f"{RECIPES}/{recipe_id}/new-version")
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["recipe_id"]


def test__new_version__numbering_counts_siblings_not_parent(api):
    base_name = f"Version Base {uuid4().hex[:8]}"
    source = requests.post(RECIPES, json={"name": base_name}).json()

    # Singleton → the source has no group yet.
    assert _by_id(source["recipe_id"])["version_group_id"] is None

    # First version: (v2), and the source is back-filled into a shared group.
    v2_id = _new_version(source["recipe_id"])
    v2 = _by_id(v2_id)
    assert v2["name"] == f"{base_name} (v2)"
    group = _by_id(source["recipe_id"])["version_group_id"]
    assert group is not None
    assert v2["version_group_id"] == group  # equal peers share the id

    # Second version off the SOURCE: (v3) — the group now has 2 siblings.
    v3_id = _new_version(source["recipe_id"])
    assert _by_id(v3_id)["name"] == f"{base_name} (v3)"
    assert _by_id(v3_id)["version_group_id"] == group

    # Version off the COPY: numbered over the whole group → (v4), NOT (v2)
    # again, and the copy's own "(v2)" suffix is replaced, not stacked.
    v4_id = _new_version(v2_id)
    assert _by_id(v4_id)["name"] == f"{base_name} (v4)"
    assert _by_id(v4_id)["version_group_id"] == group


def test__new_version__AfterSiblingDeleted__DoesNotReuseANumber(api):
    base_name = f"Version Gap {uuid4().hex[:8]}"
    source = requests.post(RECIPES, json={"name": base_name}).json()
    v2_id = _new_version(source["recipe_id"])
    _new_version(source["recipe_id"])  # (v3)
    assert requests.delete(f"{RECIPES}/{v2_id}").status_code == 204

    # Two siblings remain; counting them used to name this "(v3)" again.
    resp = requests.post(f"{RECIPES}/{source['recipe_id']}/new-version")

    assert resp.status_code in (200, 201), resp.text
    assert _by_id(resp.json()["recipe_id"])["name"] == f"{base_name} (v4)"


def test__new_version__SourceInACollection__CopyKeepsTheCollection(api):
    # R-032 — `recipe_collection` is noload; the clone read it off an
    # un-included load, so every new version dropped its collection.
    collection = requests.post(f"{BASE}/recipe-collections",
                               json={"name": f"Version Coll {uuid4().hex[:8]}"})
    assert collection.status_code == 201, collection.text
    collection_id = collection.json()["recipe_collection_id"]
    source = requests.post(RECIPES, json={
        "name": f"Version In Coll {uuid4().hex[:8]}",
        "recipe_collection_id": collection_id,
    }).json()

    copy = _by_id(_new_version(source["recipe_id"]))

    assert copy["recipe_collection_id"] == collection_id


def test__new_version__inherits_source_content_and_starts_unfavourited(api):
    item = make_stock_item(stock_level_id=_stock_level_id(0),
                           name=f"Version Ingredient {uuid4().hex[:8]}")
    payload = {
        "name": f"Version Rich {uuid4().hex[:8]}",
        "servings": 4,
        "prep_time_minutes": 15,
        "cook_time_minutes": 30,
        "kcal": 500,
        "difficulty": "Easy",
        "instructions": "Chop.\nSimmer.",
        "notes": "Add extra chilli.",
        "source": "https://example.com/original",
        "ingredients": [{"stock_item_id": item["stock_item_id"], "quantity": 2, "unit": "cup"}],
    }
    cuisine_id = _first_vocab_id("cuisines")
    category_id = _first_vocab_id("categories")
    if cuisine_id:
        payload["cuisine_id"] = cuisine_id
    if category_id:
        payload["category_id"] = category_id

    source = requests.post(RECIPES, json=payload).json()
    # Favourite the source so we can prove the copy resets it.
    requests.patch(f"{RECIPES}/{source['recipe_id']}", json={"is_favourite": True})

    copy = _by_id(_new_version(source["recipe_id"]))

    assert copy["recipe_id"] != source["recipe_id"]
    assert copy["is_favourite"] is False  # a fresh version is never favourited
    for field in ("servings", "prep_time_minutes", "cook_time_minutes",
                  "kcal", "difficulty", "instructions", "notes", "source"):
        assert copy[field] == payload[field], field
    if cuisine_id:
        assert copy["cuisine_id"] == cuisine_id
    if category_id:
        assert copy["category_id"] == category_id
    # Ingredient set carried across (linked to the same stock item).
    assert len(copy["ingredients"]) == 1
    assert copy["ingredients"][0]["stock_item_id"] == item["stock_item_id"]
    assert copy["ingredients"][0]["quantity"] == 2
    assert copy["ingredients"][0]["unit"] == "cup"


def test__new_version__carries_unlinked_and_optional_ingredients(api):
    """The other anchor kind: an unlinked (raw_text-only) ingredient must
    carry its text across (or the copy's row violates the anchor CHECK), and
    the `is_optional` flag must survive. This is the FU-590 regression: the
    clone read the noload `stock_item` relationship and copied neither the
    link nor raw_text, so new-version of any real recipe 500'd."""
    token = uuid4().hex[:8]
    source = requests.post(RECIPES, json={
        "name": f"Version Unlinked {token}",
        "ingredients": [
            {"raw_text": f"a pinch of magic {token}", "is_optional": True},
            {"raw_text": f"2 cups flour {token}"},
        ],
    }).json()

    copy = _by_id(_new_version(source["recipe_id"]))
    assert len(copy["ingredients"]) == 2
    by_text = {i["raw_text"]: i for i in copy["ingredients"]}
    magic = by_text[f"a pinch of magic {token}"]
    assert magic["stock_item_id"] is None
    assert magic["is_optional"] is True
    flour = by_text[f"2 cups flour {token}"]
    assert flour["stock_item_id"] is None
    assert flour["is_optional"] is False


def test__new_version__carries_sections_and_their_ingredient_links(api):
    """Owner feedback 2026-08-26 — "new version doesn't copy all fields
    properly". Sections were the field: they were never cloned, so a
    sectioned recipe came back with every group flattened into the implicit
    main list. Pins both halves — the section rows themselves, and the
    ingredient `section_id` that points at them (a copied section nobody's
    ingredients belong to is the same bug wearing a hat)."""
    token = uuid4().hex[:8]
    source = requests.post(RECIPES, json={
        "name": f"Version Sections {token}",
        "sections": [
            {"client_id": "s1", "sequence": 0, "name": f"For the sauce {token}"},
            {"client_id": "s2", "sequence": 1, "name": f"To serve {token}"},
        ],
        "ingredients": [
            {"raw_text": f"tomatoes {token}", "section_client_id": "s1"},
            {"raw_text": f"basil {token}", "section_client_id": "s2"},
            {"raw_text": f"salt {token}"},
        ],
    }).json()

    # Detail endpoint, not `_by_id`: the list endpoint carries only
    # `section_count`, the hydrated `sections[]` is detail-only.
    copy = requests.get(f"{RECIPES}/{_new_version(source['recipe_id'])}").json()
    original = requests.get(f"{RECIPES}/{source['recipe_id']}").json()

    # Sections cloned, in order, with fresh ids of their own.
    assert [s["name"] for s in copy["sections"]] == [
        f"For the sauce {token}", f"To serve {token}",
    ]
    copy_section_ids = {s["section_id"] for s in copy["sections"]}
    assert copy_section_ids.isdisjoint({s["section_id"] for s in original["sections"]})

    # Each ingredient landed back in its own group — and the unsectioned one
    # stayed unsectioned.
    by_name = {i["raw_text"]: i for i in copy["ingredients"]}
    section_by_id = {s["section_id"]: s["name"] for s in copy["sections"]}
    assert section_by_id[by_name[f"tomatoes {token}"]["section_id"]] == f"For the sauce {token}"
    assert section_by_id[by_name[f"basil {token}"]["section_id"]] == f"To serve {token}"
    assert by_name[f"salt {token}"]["section_id"] is None


def test__new_version__editing_the_copy_leaves_the_source_untouched(api):
    base_name = f"Version Indep {uuid4().hex[:8]}"
    source = requests.post(RECIPES, json={
        "name": base_name, "instructions": "Original method.",
    }).json()
    copy_id = _new_version(source["recipe_id"])

    upd = requests.patch(f"{RECIPES}/{copy_id}", json={"instructions": "Changed method."})
    assert upd.status_code in (200, 204), upd.text

    assert _by_id(copy_id)["instructions"] == "Changed method."
    assert _by_id(source["recipe_id"])["instructions"] == "Original method."
