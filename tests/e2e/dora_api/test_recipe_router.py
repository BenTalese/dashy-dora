"""FU-519 / PROPOSAL_TEST_SUITE_IMPROVEMENTS §5.D — recipe router e2e coverage.

CRUD round-trips, list filters (cookability axes, ingredient_exclude,
expiring_within_days), cookability fields on list + detail DTOs, and the
key 400/404/422 error paths. Complements (does not duplicate) the
existing pinned suites: test_recipes_query_count.py,
test_recipe_is_planned.py, test_recipe_notes.py,
test_create_recipe_unit_of_work.py, test_new_recipe_version_unit_of_work.py.

Determinism: any date used (expiry windows) is derived from the single
household-today anchor exposed by GET /api/meal-plans/today — never from
a local wall-clock read (see the 2026-07-10 timezone-flake rule).
"""
from datetime import date, timedelta
from uuid import uuid4

import pytest
import requests

from tests.e2e.dora_api._error_assertions import domain_err, validation_err
from tests.factories import make_stock_item
from tests.support import assert_envelope, assert_problem, is_valid_uuid

BASE = "http://localhost:5170/api"
RECIPES = f"{BASE}/recipes"

# Cookability contract fields every list/detail DTO must carry
# (state-ownership §3.2 + IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 tri-state).
COOKABILITY_KEYS = {
    "cookable",
    "missing_count",
    "missing_stock_item_names",
    "unlinked_ingredient_count",
}

# Identity / core fields the cookbook list render depends on. A subset
# check (not full-set equality) so additive DTO growth doesn't break this
# suite; the cookability contract above is the part we pin hard.
LIST_DTO_CORE_KEYS = {
    "recipe_id",
    "name",
    "available_meals",
    "unallocated_meals",
    "committed_meals",
    "is_planned",
    "is_favourite",
    "ingredients",
    "has_image",
    "created_at",
    "servings",
    "kcal",
    "notes",
} | COOKABILITY_KEYS

#region ---------------- setup ----------------


def _stock_level_id(sequence: int) -> str:
    """Resolve a stock-level id by its canonical status sequence
    (0 Stocked / 1 Low / 2 Out — see dora_api.domain.stock_status)."""
    levels = requests.get(f"{BASE}/stock-levels").json()["items"]
    return next(l["stock_level_id"] for l in levels if l["sequence"] == sequence)


def _make_item(name_prefix: str, sequence: int, **overrides) -> dict:
    """Create a stock item at the given stock-status sequence with a
    collision-proof name. Returns the created DTO."""
    return make_stock_item(
        stock_level_id=_stock_level_id(sequence),
        name=f"{name_prefix} {uuid4().hex[:8]}",
        **overrides,
    )


def _make_recipe(name_prefix: str = "E2E Recipe", **body) -> dict:
    """Create a recipe via POST /api/recipes and return the echoed detail
    DTO. Name is collision-proof unless the caller pins one."""
    payload = {"name": f"{name_prefix} {uuid4().hex[:8]}", **body}
    resp = requests.post(RECIPES, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _list_items(query: str = "") -> list:
    return assert_envelope(requests.get(f"{RECIPES}{query}"))


def _by_id(recipe_id: str) -> dict | None:
    items = _list_items(f"?filter=recipe_id:eq:{recipe_id}")
    return items[0] if items else None


def _household_today() -> date:
    return date.fromisoformat(
        requests.get(f"{BASE}/meal-plans/today").json()["today"]
    )

#endregion setup

#region ---------------- create ----------------


def test__create_recipe__AllCoreAttributes__RecipeCreatedAndDetailDtoEchoed(api):
    _Item = _make_item("Recipe Router Flour", 0)
    _Name = f"Router Full Recipe {uuid4().hex[:8]}"

    _Response = requests.post(RECIPES, json={
        "name": _Name,
        "servings": 4,
        "prep_time_minutes": 10,
        "cook_time_minutes": 25,
        "kcal": 650,
        "difficulty": "Easy",
        "instructions": "Mix.\nBake.",
        "notes": "Family favourite.",
        "ingredients": [
            {"stock_item_id": _Item["stock_item_id"], "quantity": 2, "unit": "cup"},
        ],
    })

    assert _Response.status_code == 201, _Response.text
    assert _Response.headers["Content-Type"] == "application/json"
    assert f"/api/recipes?filter=recipe_id:eq:" in _Response.headers["location"]
    _Body = _Response.json()
    assert is_valid_uuid(_Body["recipe_id"])
    assert _Body["name"] == _Name
    assert _Body["servings"] == 4
    assert _Body["prep_time_minutes"] == 10
    assert _Body["cook_time_minutes"] == 25
    assert _Body["kcal"] == 650
    assert _Body["difficulty"] == "Easy"
    assert _Body["notes"] == "Family favourite."
    assert len(_Body["ingredients"]) == 1
    assert _Body["ingredients"][0]["stock_item_id"] == _Item["stock_item_id"]
    assert _Body["ingredients"][0]["quantity"] == 2
    assert _Body["ingredients"][0]["unit"] == "cup"


def test__create_recipe__NameOnly__CreatesFreeformEmptyStub(api):
    """DORA_VERIFY Cookbook L128 (FU-095) — the "New Recipe" modal now only
    collects Name/Cuisine/Category/Collection and creates a stub the user
    fleshes out on the detail page. Pin the server contract: a name-only
    create defaults to a freeform, instruction-less, ingredient-less stub."""
    _Name = f"Router Stub Recipe {uuid4().hex[:8]}"
    _Response = requests.post(RECIPES, json={"name": _Name})

    assert _Response.status_code == 201, _Response.text
    _Body = _Response.json()
    assert _Body["name"] == _Name
    assert _Body["steps_mode"] == "freeform"
    assert _Body["instructions"] is None
    assert _Body["ingredients"] == []
    assert _Body["steps"] == []

    # And the same shape survives a fresh GET (not just the create echo).
    detail = requests.get(f"{RECIPES}/{_Body['recipe_id']}")
    assert detail.status_code == 200, detail.text
    _Detail = detail.json()
    assert _Detail["steps_mode"] == "freeform"
    assert _Detail["instructions"] is None
    assert _Detail["ingredients"] == []


def test__create_recipe__WhitespaceOnlyStepText__IsBadRequestWithDomainMessage(api):
    """DORA_VERIFY Cookbook Chunk-6 L179 — a structured step whose text is
    whitespace-only slips past the Pydantic `min_length=1` (it's 3 chars) but
    is rejected by the step validator with a 400 and the exact domain message,
    so no half-built recipe is left behind."""
    _Response = requests.post(RECIPES, json={
        "name": f"Router Blank Step {uuid4().hex[:8]}",
        "steps_mode": "structured",
        "steps": [{"client_id": "s1", "sequence": 0, "text": "   "}],
    })
    assert_problem(_Response, 400, title="Every step must have non-empty text.")


def test__create_recipe__EmptyStepText__IsValidationFailure(api):
    """The Pydantic floor: a truly empty string is a 422 validation error
    (distinct from the whitespace-only domain-400 above)."""
    _Response = requests.post(RECIPES, json={
        "name": f"Router Empty Step {uuid4().hex[:8]}",
        "steps_mode": "structured",
        "steps": [{"client_id": "s1", "sequence": 0, "text": ""}],
    })
    assert_problem(_Response, 400, title="Malformed request.")


def test__create_recipe__EmptyRequest__IsRequiredInputsValidationFailure(api):
    _Response = requests.post(RECIPES, json={})

    assert_problem(_Response, 400, title="Malformed request.")
    assert _Response.json()["errors"] == {
        "name": [validation_err("missing", "Field required")],
    }


def test__create_recipe__DuplicateName__IsBusinessRuleViolation(api):
    _Name = f"Router Duplicate Recipe {uuid4().hex[:8]}"
    assert requests.post(RECIPES, json={"name": _Name}).status_code == 201

    _Response = requests.post(RECIPES, json={"name": _Name})

    _Body = assert_problem(_Response, 422, title="Business rule violation.")
    assert _Body["errors"] == {
        "": [domain_err(f"A recipe with the name '{_Name}' already exists.")],
    }


def test__create_recipe__UnknownStockItemInIngredients__IsEntityExistenceFailure(api):
    _FakeID = uuid4()

    _Response = requests.post(RECIPES, json={
        "name": f"Router Ghost Ingredient {uuid4().hex[:8]}",
        "ingredients": [{"stock_item_id": str(_FakeID)}],
    })

    _Body = assert_problem(_Response, 422, field="ingredients")
    assert _Body["errors"]["ingredients"] == [
        domain_err(f"StockItem(s) with the ID(s) '{_FakeID}' were not found."),
    ]


def test__create_recipe__UnknownCuisine__IsEntityExistenceFailure(api):
    _FakeID = uuid4()

    _Response = requests.post(RECIPES, json={
        "name": f"Router Ghost Cuisine {uuid4().hex[:8]}",
        "cuisine_id": str(_FakeID),
    })

    _Body = assert_problem(_Response, 422, field="cuisine_id", title="Entity was not found.")
    assert _Body["errors"]["cuisine_id"] == [
        domain_err(f"Cuisine with the ID '{_FakeID}' was not found."),
    ]


def test__create_recipe__InvalidDifficulty__IsBadRequest(api):
    _Response = requests.post(RECIPES, json={
        "name": f"Router Bad Difficulty {uuid4().hex[:8]}",
        "difficulty": "impossible",
    })

    _Body = assert_problem(_Response, 400)
    assert "Invalid difficulty 'impossible'" in _Body["title"]


def test__create_recipe__IngredientWithNoStockItemAndNoRawText__IsValidationFailure(api):
    # Chunk 4 invariant: every ingredient row needs an anchor — a linked
    # stock_item_id or non-blank raw_text.
    _Response = requests.post(RECIPES, json={
        "name": f"Router Anchorless Ingredient {uuid4().hex[:8]}",
        "ingredients": [{"quantity": 1}],
    })

    assert_problem(_Response, 400, title="Malformed request.")


def test__create_recipe__ExtraAttributes__IsBadRequest(api):
    _Response = requests.post(RECIPES, json={
        "name": f"Router Extra Attr {uuid4().hex[:8]}",
        "poopusgoopus": "aaaa",
    })

    _Body = assert_problem(_Response, 400, field="poopusgoopus")
    assert _Body["errors"]["poopusgoopus"] == [
        validation_err("extra_forbidden", "Extra inputs are not permitted"),
    ]

#endregion create

#region ---------------- estimated cost (Chunk 9 / DEC-5) ----------------


def _link_priced_item(
    *, price_now: float, size_value: float, level: int = 0, size_unit: str = "L",
) -> dict:
    """A Stocked item linked to an active product whose current offer gives a
    unit price of `price_now / size_value`. Exercises the real cost join
    (StockItemProduct → Product → ProductOffer)."""
    _Item = _make_item("Cost Item", level)
    _Suffix = uuid4().hex[:8]
    _ProductResp = requests.post(f"{BASE}/products", json={
        "name": f"CostProduct-{_Suffix}",
        "store_name": "Woolworths",
        "merchant_stockcode": f"COST-{_Suffix}",
        "brand": "Test",
        "price_now": price_now,
        "price_was": price_now + 5,
        "is_active": True,
        "is_available": True,
        "size": f"{size_value}{size_unit}",
        "size_unit": size_unit,
        "size_value": size_value,
    })
    assert _ProductResp.status_code == 201, _ProductResp.text
    _ProductId = _ProductResp.headers["location"].rsplit(":", 1)[-1]
    _Link = requests.post(
        f"{BASE}/stock-items/{_Item['stock_item_id']}/products",
        json={"product_id": _ProductId},
    )
    assert _Link.status_code in (200, 204), _Link.text
    return _Item


def _detail(recipe_id: str) -> dict:
    resp = requests.get(f"{RECIPES}/{recipe_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def test__estimated_cost__converts_the_ingredient_quantity_into_the_priced_unit(api):
    # The product is 2 L for $6.00 → $3.00 per L. The recipe asks for 2 cups
    # = 500 ml = 0.5 L → $1.50.
    #
    # This test asserted 6.00 until 2026-08-19, which was the bug, not the
    # contract: it multiplied "2 cups" by "$3 per litre" as if a cup were a
    # litre. Same defect, at seed scale, reported a $1590 two-ingredient
    # recipe. The unit is now reconciled or the ingredient is left unpriced.
    _Priced = _link_priced_item(price_now=6.0, size_value=2.0)
    _Recipe = _make_recipe("Cost Full", ingredients=[
        {"stock_item_id": _Priced["stock_item_id"], "quantity": 2, "unit": "cup"},
    ])
    _Detail = _detail(_Recipe["recipe_id"])
    assert _Detail["estimated_cost"] == 1.5
    assert _Detail["estimated_cost_priced_count"] == 1
    assert _Detail["estimated_cost_total_count"] == 1


def test__estimated_cost__counted_ingredient_is_priced_per_item(api):
    # "2 tins" against a product sized as a count of one: "tins" is not a unit
    # we know, and doesn't need to be — a count means whole items, so 2 × $6.00.
    _Priced = _link_priced_item(price_now=6.0, size_value=1.0, size_unit="ea")
    _Recipe = _make_recipe("Cost Counted", ingredients=[
        {"stock_item_id": _Priced["stock_item_id"], "quantity": 2, "unit": "tins"},
    ])
    _Detail = _detail(_Recipe["recipe_id"])
    assert _Detail["estimated_cost"] == 12.0
    assert _Detail["estimated_cost_priced_count"] == 1


def test__estimated_cost__count_against_a_measured_pack_is_unpriced(api):
    # Owner-reported 2026-09-03: "3 yolks" of Free Range Eggs (a 700 g carton
    # at $5.50) was billed as three whole cartons — $16.50 — because a measured
    # pack was assumed to hold exactly one countable thing. It holds twelve,
    # and nothing in the data said so, so the honest answer is that we can't
    # price it. Same shape with the unit dropped ("3" on its own), which is the
    # second half of the same report.
    _Priced = _link_priced_item(price_now=5.50, size_value=700.0, size_unit="g")
    _Recipe = _make_recipe("Cost Yolks", ingredients=[
        {"stock_item_id": _Priced["stock_item_id"], "quantity": 3, "unit": "yolks"},
    ])
    _Detail = _detail(_Recipe["recipe_id"])
    assert _Detail["estimated_cost"] is None
    assert _Detail["estimated_cost_priced_count"] == 0
    _Lines = _Detail["estimated_cost_lines"]
    assert _Lines[0]["reason"] == "unit_no_pack_count"
    assert _Lines[0]["line_cost"] is None


def test__estimated_cost__unbridgeable_units_are_unpriced_not_guessed(api):
    # A product with no size prices per item ("ea"). An ingredient measured in
    # grams can't be converted into items — the pack's weight is unknown — so
    # it contributes nothing and says so, instead of billing 250 whole packs.
    _Priced = _link_priced_item(price_now=4.0, size_value=1, size_unit="ea")
    _Recipe = _make_recipe("Cost Mismatch", ingredients=[
        {"stock_item_id": _Priced["stock_item_id"], "quantity": 250, "unit": "g"},
    ])
    _Detail = _detail(_Recipe["recipe_id"])
    assert _Detail["estimated_cost"] is None
    assert _Detail["estimated_cost_priced_count"] == 0
    _Lines = _Detail["estimated_cost_lines"]
    assert len(_Lines) == 1
    assert _Lines[0]["reason"] == "unit_no_pack_size"
    assert _Lines[0]["line_cost"] is None
    assert _Lines[0]["priced_unit"] == "ea"


def test__estimated_cost__breakdown_lines_show_the_working_per_ingredient(api):
    _Priced = _link_priced_item(price_now=6.0, size_value=2.0)
    _Unlinked = _make_item("Cost Unlinked Line", 0)
    _Recipe = _make_recipe("Cost Lines", ingredients=[
        {"stock_item_id": _Priced["stock_item_id"], "quantity": 1, "unit": "L"},
        {"stock_item_id": _Unlinked["stock_item_id"], "quantity": 3},
    ])
    _Detail = _detail(_Recipe["recipe_id"])
    _Lines = _Detail["estimated_cost_lines"]
    assert len(_Lines) == 2
    assert _Lines[0]["line_cost"] == 3.0        # 1 L × $3.00/L
    assert _Lines[0]["unit_price"] == 3.0
    assert _Lines[0]["priced_unit"] == "L"
    assert _Lines[0]["reason"] is None
    assert _Lines[1]["reason"] == "no_price"
    assert _Lines[1]["line_cost"] is None


def test__estimated_cost__partial_coverage_prices_only_linked_products(api):
    # One priced ingredient (3.00 unit × 1) + one linked-but-unpriced ingredient
    # → cost counts only the priced one; the ratio surfaces "1 of 2" (L216).
    _Priced = _link_priced_item(price_now=3.0, size_value=1.0)
    _Unpriced = _make_item("Cost Unpriced", 0)  # linked to no product / no offers
    _Recipe = _make_recipe("Cost Partial", ingredients=[
        # Measured, so the 1 L product can price it. (It used to be a bare
        # count, which only worked while a measured pack was assumed to be one
        # countable item — see the yolks test above.)
        {"stock_item_id": _Priced["stock_item_id"], "quantity": 1, "unit": "L"},
        {"stock_item_id": _Unpriced["stock_item_id"], "quantity": 5},
    ])
    _Detail = _detail(_Recipe["recipe_id"])
    assert _Detail["estimated_cost"] == 3.0
    assert _Detail["estimated_cost_priced_count"] == 1
    assert _Detail["estimated_cost_total_count"] == 2


def test__estimated_cost__none_when_no_ingredient_is_priced(api):
    # No linked products and no price observations → estimate is None, not 0
    # (the card is hidden client-side — L215).
    _Bare = _make_item("Cost Bare", 0)
    _Recipe = _make_recipe("Cost None", ingredients=[
        {"stock_item_id": _Bare["stock_item_id"], "quantity": 1},
    ])
    _Detail = _detail(_Recipe["recipe_id"])
    assert _Detail["estimated_cost"] is None
    assert _Detail["estimated_cost_priced_count"] == 0


#endregion estimated cost

#region ---------------- read: detail + list shape ----------------


def test__get_recipe__ById__ReturnsFullDetailDto(api):
    _Created = _make_recipe("Router Detail Read", instructions="Step one.")

    _Response = requests.get(f"{RECIPES}/{_Created['recipe_id']}")

    assert _Response.status_code == 200
    _Detail = _Response.json()
    assert _Detail["recipe_id"] == _Created["recipe_id"]
    assert _Detail["name"] == _Created["name"]
    # Detail-only surfaces must exist (lists may be empty).
    assert isinstance(_Detail["steps"], list)
    assert isinstance(_Detail["sections"], list)
    assert isinstance(_Detail["version_siblings"], list)
    assert isinstance(_Detail["step_images"], list)
    assert "estimated_cost" in _Detail
    assert COOKABILITY_KEYS <= _Detail.keys()


def test__get_recipe__DoesNotExist__RecipeNotFound(api):
    _FakeID = uuid4()

    _Response = requests.get(f"{RECIPES}/{_FakeID}")

    _Body = assert_problem(_Response, 404, title="Entity was not found.")
    assert _Body["detail"] == f"Recipe with the ID '{_FakeID}' was not found."


def test__get_recipes__ListDto__CarriesCoreAndCookabilityKeys(api):
    _Created = _make_recipe("Router List Shape")

    _Row = _by_id(_Created["recipe_id"])

    assert _Row is not None
    assert LIST_DTO_CORE_KEYS <= _Row.keys()


def test__get_recipes__FilterByIdForUnknownRecipe__EmptyResult(api):
    _Response = requests.get(f"{RECIPES}?filter=recipe_id:eq:{uuid4()}")

    assert_envelope(_Response, expect_total=0)


def test__get_recipes__FilteringOnNonExistentAttribute__IsBadRequest(api):
    _Response = requests.get(f"{RECIPES}?filter=poopusgoopus:eq:1")

    _Body = assert_problem(_Response, 400)
    assert _Body["title"] == "Field 'poopusgoopus' is not filterable on 'Recipe'."


# FU-169 Phase 2 reference shape — parametrized pagination-validation matrix.
@pytest.mark.parametrize(
    "query,invalid_field",
    [
        ("page=true&limit=2", "page"),
        ("page=1&limit=true", "limit"),
    ],
    ids=["page-is-not-integer", "limit-is-not-integer"],
)
def test__get_recipes__pagination_value_is_not_integer__IsBadRequest(api, query, invalid_field):
    _Response = requests.get(f"{RECIPES}?{query}")

    assert_problem(_Response, 400)
    assert _Response.json() == {
        "detail": "See errors property for more details.",
        "errors": {},
        "status": 400,
        "title": f"'{invalid_field}' must be an integer.",
        "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1",
    }


def test__get_recipes__PagingWithLimit__RespectsPageSize(api):
    for _i in range(3):
        _make_recipe("Router Page Probe")

    _Response = requests.get(f"{RECIPES}?page=1&limit=2")

    assert _Response.status_code == 200
    _Body = _Response.json()
    assert _Body["page"] == 1
    assert _Body["limit"] == 2
    assert len(_Body["items"]) == 2
    assert _Body["total"] >= 3

#endregion read

#region ---------------- cookability surfacing + filters ----------------


def test__get_recipes__AllIngredientsStocked__CookableTrueWithNothingMissing(api):
    _Item = _make_item("Cookable Stocked", 0)
    _Created = _make_recipe("Router Cookable", ingredients=[
        {"stock_item_id": _Item["stock_item_id"]},
    ])

    _Row = _by_id(_Created["recipe_id"])

    assert _Row["cookable"] is True
    assert _Row["missing_count"] == 0
    assert _Row["missing_stock_item_names"] == []
    assert _Row["unlinked_ingredient_count"] == 0


def test__get_recipes__OutOfStockIngredient__CookableFalseAndMissingNamed(api):
    _Item = _make_item("Cookable OutOfStock", 2)
    _Created = _make_recipe("Router Uncookable", ingredients=[
        {"stock_item_id": _Item["stock_item_id"]},
    ])

    _Row = _by_id(_Created["recipe_id"])

    assert _Row["cookable"] is False
    assert _Row["missing_count"] == 1
    assert _Row["missing_stock_item_names"] == [_Item["name"]]
    # Ingredient-level status flags mirror the server-owned rule (§3.1).
    assert _Row["ingredients"][0]["is_missing"] is True


def test__get_recipes__UnlinkedRequiredIngredient__CookableIsTriStateNull(api):
    # IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 — raw_text-only rows make
    # cookability unknown, not false.
    _Created = _make_recipe("Router Unlinked", ingredients=[
        {"raw_text": "1 pound ground turkey"},
    ])

    _Row = _by_id(_Created["recipe_id"])

    assert _Row["cookable"] is None
    assert _Row["unlinked_ingredient_count"] == 1
    assert _Row["missing_count"] == 0
    assert _Row["ingredients"][0]["stock_item_id"] is None
    assert _Row["ingredients"][0]["raw_text"] == "1 pound ground turkey"


def test__get_recipes__OptionalMissingIngredient__DoesNotBlockCookable(api):
    # Cookbook revision §1.9 — optional rows are ignored by the rollup.
    _Stocked = _make_item("Optional Stocked", 0)
    _Out = _make_item("Optional OutOfStock", 2)
    _Created = _make_recipe("Router Optional", ingredients=[
        {"stock_item_id": _Stocked["stock_item_id"]},
        {"stock_item_id": _Out["stock_item_id"], "is_optional": True},
    ])

    _Row = _by_id(_Created["recipe_id"])

    assert _Row["cookable"] is True
    assert _Row["missing_count"] == 0
    assert _Row["missing_stock_item_names"] == []


def test__get_recipes__CookableTrueFilter__KeepsCookableExcludesFalseAndUnknown(api):
    _Stocked = _make_item("Filter Stocked", 0)
    _Out = _make_item("Filter OutOfStock", 2)
    _CookableId = _make_recipe("Filter Cookable", ingredients=[
        {"stock_item_id": _Stocked["stock_item_id"]},
    ])["recipe_id"]
    _UncookableId = _make_recipe("Filter Uncookable", ingredients=[
        {"stock_item_id": _Out["stock_item_id"]},
    ])["recipe_id"]
    _UnknownId = _make_recipe("Filter Unknown", ingredients=[
        {"raw_text": "mystery spice"},
    ])["recipe_id"]

    _Ids = {r["recipe_id"] for r in _list_items("?cookable=true&limit=500")}

    assert _CookableId in _Ids
    assert _UncookableId not in _Ids
    # Tri-state None is excluded from BOTH cookable axes.
    assert _UnknownId not in _Ids


def test__get_recipes__CookableFalseFilter__KeepsOnlyDefinitelyUncookable(api):
    _Stocked = _make_item("FilterF Stocked", 0)
    _Out = _make_item("FilterF OutOfStock", 2)
    _CookableId = _make_recipe("FilterF Cookable", ingredients=[
        {"stock_item_id": _Stocked["stock_item_id"]},
    ])["recipe_id"]
    _UncookableId = _make_recipe("FilterF Uncookable", ingredients=[
        {"stock_item_id": _Out["stock_item_id"]},
    ])["recipe_id"]
    _UnknownId = _make_recipe("FilterF Unknown", ingredients=[
        {"raw_text": "mystery spice"},
    ])["recipe_id"]

    _Ids = {r["recipe_id"] for r in _list_items("?cookable=false&limit=500")}

    assert _UncookableId in _Ids
    assert _CookableId not in _Ids
    assert _UnknownId not in _Ids


def test__get_recipes__MaxMissingFilter__ExcludesRecipesOverThreshold(api):
    _OutA = _make_item("MaxMissing A", 2)
    _OutB = _make_item("MaxMissing B", 2)
    _OneMissingId = _make_recipe("MaxMissing One", ingredients=[
        {"stock_item_id": _OutA["stock_item_id"]},
    ])["recipe_id"]
    _TwoMissingId = _make_recipe("MaxMissing Two", ingredients=[
        {"stock_item_id": _OutA["stock_item_id"]},
        {"stock_item_id": _OutB["stock_item_id"]},
    ])["recipe_id"]

    _Ids = {r["recipe_id"] for r in _list_items("?max_missing=1&limit=500")}

    assert _OneMissingId in _Ids
    assert _TwoMissingId not in _Ids


def test__get_recipes__IngredientExcludeFilter__DropsRecipesUsingTheIngredient(api):
    _Token = uuid4().hex[:8]
    _Egg = make_stock_item(
        stock_level_id=_stock_level_id(0),
        name=f"Excludable Egg {_Token}",
    )
    _Safe = _make_item("Exclude Safe", 0)
    _WithEggId = _make_recipe("Exclude WithEgg", ingredients=[
        {"stock_item_id": _Egg["stock_item_id"]},
    ])["recipe_id"]
    _WithoutEggId = _make_recipe("Exclude WithoutEgg", ingredients=[
        {"stock_item_id": _Safe["stock_item_id"]},
    ])["recipe_id"]

    _Ids = {
        r["recipe_id"]
        for r in _list_items(f"?ingredient_exclude=excludable egg {_Token}&limit=500")
    }

    assert _WithEggId not in _Ids
    assert _WithoutEggId in _Ids


def test__get_recipes__ExpiringWithinDaysFilter__KeepsRecipesUsingAtRiskStock(api):
    # C-waste W4 — both the restriction and the per-recipe count. Dates are
    # relative to the single household-today anchor (determinism rule).
    _Today = _household_today()
    _Expiring = make_stock_item(
        stock_level_id=_stock_level_id(0),
        name=f"Expiring Soon Cream {uuid4().hex[:8]}",
        expiry_date=(_Today + timedelta(days=3)).isoformat(),
    )
    _Stable = _make_item("Never Expires", 0)
    _UsesExpiringId = _make_recipe("Expiring User", ingredients=[
        {"stock_item_id": _Expiring["stock_item_id"]},
    ])["recipe_id"]
    _StableOnlyId = _make_recipe("Expiring NonUser", ingredients=[
        {"stock_item_id": _Stable["stock_item_id"]},
    ])["recipe_id"]

    _Rows = _list_items("?expiring_within_days=7&limit=500")
    _ById = {r["recipe_id"]: r for r in _Rows}

    assert _UsesExpiringId in _ById
    assert _ById[_UsesExpiringId]["expiring_ingredient_count"] == 1
    assert _StableOnlyId not in _ById

#endregion cookability

#region ---------------- update ----------------


def test__update_recipe__RenameOnly__OnlyNameChanges(api):
    _Created = _make_recipe("Router Rename", servings=3)
    _NewName = f"Router Renamed {uuid4().hex[:8]}"

    _PatchResponse = requests.patch(
        f"{RECIPES}/{_Created['recipe_id']}", json={"name": _NewName},
    )
    _After = _by_id(_Created["recipe_id"])

    assert _PatchResponse.status_code == 204
    assert _After["name"] == _NewName
    assert _After["servings"] == 3


def test__update_recipe__TogglingFavourite__FavouritePersisted(api):
    _Created = _make_recipe("Router Favourite")
    assert _Created["is_favourite"] is False

    _PatchResponse = requests.patch(
        f"{RECIPES}/{_Created['recipe_id']}", json={"is_favourite": True},
    )

    assert _PatchResponse.status_code == 204
    assert _by_id(_Created["recipe_id"])["is_favourite"] is True


def test__update_recipe__ReplacingIngredients__IngredientSetReplaced(api):
    _First = _make_item("Update Ing First", 0)
    _Second = _make_item("Update Ing Second", 0)
    _Created = _make_recipe("Router ReplaceIngredients", ingredients=[
        {"stock_item_id": _First["stock_item_id"]},
    ])

    _PatchResponse = requests.patch(
        f"{RECIPES}/{_Created['recipe_id']}",
        json={"ingredients": [
            {"stock_item_id": _Second["stock_item_id"], "quantity": 5, "unit": "g"},
        ]},
    )
    _After = _by_id(_Created["recipe_id"])

    assert _PatchResponse.status_code == 204
    assert len(_After["ingredients"]) == 1
    assert _After["ingredients"][0]["stock_item_id"] == _Second["stock_item_id"]
    assert _After["ingredients"][0]["quantity"] == 5


def test__update_recipe__OtherRecipeHasSameName__CannotUpdateToDuplicateName(api):
    _Existing = _make_recipe("Router Name Holder")
    _Victim = _make_recipe("Router Name Wanter")

    _PatchResponse = requests.patch(
        f"{RECIPES}/{_Victim['recipe_id']}", json={"name": _Existing["name"]},
    )

    _Body = assert_problem(_PatchResponse, 422, title="Business rule violation.")
    assert _Body["errors"] == {
        "": [domain_err(f"A recipe with the name '{_Existing['name']}' already exists.")],
    }


def test__update_recipe__RecipeDoesNotExist__RecipeNotFound(api):
    _FakeID = uuid4()

    _Response = requests.patch(f"{RECIPES}/{_FakeID}", json={})

    _Body = assert_problem(_Response, 404, title="Entity was not found.")
    assert _Body["detail"] == f"Recipe with the ID '{_FakeID}' was not found."

#endregion update

#region ---------------- delete ----------------


def test__delete_recipe__DeletingRecipe__RecipeGoneFromListAndDetail(api):
    _Created = _make_recipe("Router Delete Me")

    _DeleteResponse = requests.delete(f"{RECIPES}/{_Created['recipe_id']}")

    assert _DeleteResponse.status_code == 204
    assert _by_id(_Created["recipe_id"]) is None
    assert requests.get(f"{RECIPES}/{_Created['recipe_id']}").status_code == 404


def test__delete_recipe__RecipeDoesNotExist__RecipeNotFound(api):
    _FakeID = uuid4()

    _Response = requests.delete(f"{RECIPES}/{_FakeID}")

    _Body = assert_problem(_Response, 404, title="Entity was not found.")
    assert _Body["detail"] == f"Recipe with the ID '{_FakeID}' was not found."

#endregion delete


def test__get_recipe_image__a_non_image_mimetype_is_never_served(api):
    """QA2-01 — a recipe "image" declared as text/html must not come back as
    HTML from the image route."""
    html = "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg=="
    resp = requests.post("http://localhost:5170/api/recipes", json={"name": f"xss-{uuid4().hex[:8]}", "image": html})
    assert resp.status_code == 201, resp.text
    image = requests.get(f"http://localhost:5170/api/recipes/{resp.json()['recipe_id']}/image")
    assert image.status_code == 404
    assert "text/html" not in image.headers.get("Content-Type", "")


#region ---------------- step images: keep-by-id on PATCH ----------------

# Three distinct tiny "images" — the bytes endpoint decodes the base64
# payload, so each is told apart by its served body.
_IMG_A = "data:image/png;base64,QUFBQQ=="
_IMG_B = "data:image/png;base64,QkJCQg=="
_IMG_C = "data:image/png;base64,Q0NDQw=="


def _step_image_ids(recipe_id: str) -> list[str]:
    return [img["image_id"] for img in _detail(recipe_id)["step_images"]]


def _step_image_bodies(recipe_id: str) -> list[bytes]:
    return [
        requests.get(f"{RECIPES}/{recipe_id}/step-images/{image_id}").content
        for image_id in _step_image_ids(recipe_id)
    ]


def test__update_recipe__StepImagesReorderedById__KeepsBytesInNewOrder(api):
    _Recipe = _make_recipe("Step Img Reorder", steps_mode="image", step_images=[_IMG_A, _IMG_B])
    _First, _Second = _step_image_ids(_Recipe["recipe_id"])

    _Response = requests.patch(
        f"{RECIPES}/{_Recipe['recipe_id']}", json={"step_images": [_Second, _First]},
    )

    assert _Response.status_code == 204, _Response.text
    assert _step_image_bodies(_Recipe["recipe_id"]) == [b"BBBB", b"AAAA"]


def test__update_recipe__StepImagesMixKeptAndNew__KeepsSavedAndAddsNew(api):
    _Recipe = _make_recipe("Step Img Mix", steps_mode="image", step_images=[_IMG_A, _IMG_B])
    _First, _ = _step_image_ids(_Recipe["recipe_id"])

    _Response = requests.patch(
        f"{RECIPES}/{_Recipe['recipe_id']}", json={"step_images": [_IMG_C, _First]},
    )

    assert _Response.status_code == 204, _Response.text
    assert _step_image_bodies(_Recipe["recipe_id"]) == [b"CCCC", b"AAAA"]


def test__update_recipe__StepImageIdFromAnotherRecipe__IsValidationFailureAndNothingChanges(api):
    _Other = _make_recipe("Step Img Other", steps_mode="image", step_images=[_IMG_C])
    _Recipe = _make_recipe("Step Img Foreign", steps_mode="image", step_images=[_IMG_A])
    (_ForeignId,) = _step_image_ids(_Other["recipe_id"])

    _Response = requests.patch(
        f"{RECIPES}/{_Recipe['recipe_id']}", json={"step_images": [_ForeignId]},
    )

    assert_problem(_Response, 422, field="step_images", title="Validation failed.")
    assert _step_image_bodies(_Recipe["recipe_id"]) == [b"AAAA"]

#endregion step images


#region ---------------- write-path validation ----------------


@pytest.mark.parametrize(
    "field, value",
    [("cook_time_minutes", -1), ("prep_time_minutes", -1), ("servings", 0)],
)
def test__update_recipe__OutOfRangeNumber__IsBadRequest(api, field, value):
    # PATCH carries the same bounds as create.
    _Recipe = _make_recipe("Patch Bounds")

    _Response = requests.patch(f"{RECIPES}/{_Recipe['recipe_id']}", json={field: value})

    assert_problem(_Response, 400, field=field)


def test__create_recipe__UnknownStepsMode__IsBadRequest(api):
    # Was silently coerced to "freeform"; PATCH already rejected it.
    _Response = requests.post(RECIPES, json={
        "name": f"Bad Mode {uuid4().hex[:8]}", "steps_mode": "carousel",
    })

    assert_problem(_Response, 400, title="Invalid steps_mode 'carousel'")


def test__create_recipe__DuplicateStepClientId__IsBadRequest(api):
    # Both steps collapsed onto one generated id → PK IntegrityError (500).
    _Response = requests.post(RECIPES, json={
        "name": f"Dup Step {uuid4().hex[:8]}", "steps_mode": "structured",
        "steps": [
            {"client_id": "s1", "sequence": 0, "text": "One."},
            {"client_id": "s1", "sequence": 1, "text": "Two."},
        ],
    })

    assert_problem(_Response, 400)


def test__create_recipe__DuplicateSectionClientId__IsBadRequest(api):
    _Response = requests.post(RECIPES, json={
        "name": f"Dup Section {uuid4().hex[:8]}",
        "sections": [
            {"client_id": "a", "sequence": 0, "name": "Sauce"},
            {"client_id": "a", "sequence": 1, "name": "Garnish"},
        ],
    })

    assert_problem(_Response, 400)


def test__create_recipe__StepRepeatsAnIngredientLink__StoresOneLink(api):
    _Response = requests.post(RECIPES, json={
        "name": f"Dup Link {uuid4().hex[:8]}", "steps_mode": "structured",
        "ingredients": [{"raw_text": "bread", "client_id": "i1"}],
        "steps": [{
            "client_id": "s1", "sequence": 0, "text": "Slice.",
            "ingredient_client_ids": ["i1", "i1"],
        }],
    })
    assert _Response.status_code == 201, _Response.text

    _Step = _detail(_Response.json()["recipe_id"])["steps"][0]

    assert len(_Step["ingredient_ids"]) == 1


def test__get_recipes__TagsIncludeHasAnUnknownTag__MatchesNothing(api):
    # An unresolved tag used to be dropped, widening "vegan AND <unknown>"
    # to "vegan".
    _TagId = requests.get(f"{RECIPES}/tags").json()["tags"][0]["value"]
    _Recipe = _make_recipe("Tagged", dietary_tag_ids=[_TagId])
    _ById = f"filter=recipe_id:eq:{_Recipe['recipe_id']}"

    assert len(_list_items(f"?{_ById}&tags_include={_TagId}")) == 1
    assert _list_items(f"?{_ById}&tags_include={_TagId},no-such-tag-{uuid4().hex[:6]}") == []

#endregion write-path validation
