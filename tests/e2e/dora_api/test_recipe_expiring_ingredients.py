"""Per-ingredient at-risk flags on the recipe DTO (owner feedback 2026-08-17).

The cookbook can filter to "uses expiring ingredients", but opening a result
didn't say *which* ingredient qualified — you were left comparing the list
against the pantry by hand. `RecipeIngredientDto.is_expiring` / `is_expired`
carry that answer.

The contract worth pinning is the agreement: an ingredient is flagged under
exactly the horizon the filter matched on (`EXPIRING_HORIZON_DAYS`), so a
recipe the filter returned can never open with nothing marked. The 8-to-13-day
band is the interesting one — it's inside the filter's 14 days but outside the
client's 7-day expiry *display* band, which is precisely where a client-side
re-derivation would silently disagree.
"""
from datetime import timedelta

import pytest
import requests

from dora_api.features.recipes.get_recipes import EXPIRING_HORIZON_DAYS

BASE = 'http://localhost:5170/api'
RECIPES = f"{BASE}/recipes"
STOCK_ITEMS = f"{BASE}/stock-items"


def _household_today():
    from datetime import date
    return date.fromisoformat(requests.get(f"{BASE}/meal-plans/today").json()["today"])


def _recipe_with_a_linked_ingredient() -> dict:
    """A seeded recipe whose ingredients include at least one linked row."""
    items = requests.get(f"{RECIPES}?limit=200").json()["items"]
    recipe = next(
        (r for r in items if any(i["stock_item_id"] for i in r["ingredients"])),
        None,
    )
    assert recipe is not None, "seed expected to have a recipe with a linked ingredient"
    return recipe


def _detail(recipe_id: str) -> dict:
    resp = requests.get(f"{RECIPES}/{recipe_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _ingredient(recipe: dict, stock_item_id: str) -> dict:
    return next(i for i in recipe["ingredients"] if i["stock_item_id"] == stock_item_id)


# FU-676 — every test in this module PATCHes `expiry_date` onto *seeded* stock
# items, because the flags under test are only reachable through real expiry
# dates. Left unrestored those mutations leak forward: in full-suite order they
# broke `test_update_stock_item_auto_add.py::
# test__auto_add__already_on_target_draft__does_not_fire`, which passes in
# isolation. `_set_expiry` snapshots each item's pre-test value the first time
# it touches it and `_restore_expiries` puts them all back, so the module is
# self-cleaning however many items a test mutates.
_ORIGINAL_EXPIRIES: dict[str, str | None] = {}


def _set_expiry(stock_item_id: str, expiry) -> None:
    if stock_item_id not in _ORIGINAL_EXPIRIES:
        # There is no bare `GET /stock-items/{id}` — `/detail` is the
        # single-item read, and it carries `expiry_date`.
        before = requests.get(f"{STOCK_ITEMS}/{stock_item_id}/detail")
        assert before.status_code == 200, before.text
        _ORIGINAL_EXPIRIES[stock_item_id] = before.json().get("expiry_date")
    resp = requests.patch(
        f"{STOCK_ITEMS}/{stock_item_id}",
        json={"expiry_date": expiry.isoformat() if expiry else None},
    )
    assert resp.status_code in (200, 204), resp.text


@pytest.fixture(autouse=True)
def _restore_expiries():
    """Undo this module's expiry mutations after each test (FU-676)."""
    _ORIGINAL_EXPIRIES.clear()
    try:
        yield
    finally:
        for stock_item_id, original in _ORIGINAL_EXPIRIES.items():
            requests.patch(
                f"{STOCK_ITEMS}/{stock_item_id}",
                json={"expiry_date": original},
            )
        _ORIGINAL_EXPIRIES.clear()


def test__recipe_detail__flags_the_ingredient_that_is_expiring(api):
    """An ingredient inside the horizon is flagged, and its expiry is echoed
    so the UI can say when. Ingredients that aren't at risk stay unflagged."""
    recipe = _recipe_with_a_linked_ingredient()
    target = next(i["stock_item_id"] for i in recipe["ingredients"] if i["stock_item_id"])
    expiry = _household_today() + timedelta(days=10)

    _set_expiry(target, expiry)

    detail = _detail(recipe["recipe_id"])
    flagged = _ingredient(detail, target)
    assert flagged["is_expiring"] is True, flagged
    assert flagged["is_expired"] is False, flagged
    assert flagged["expiry_date"] == expiry.isoformat(), flagged

    # Everything else on the recipe is untouched — the chip marks one row,
    # it doesn't paint the whole list.
    others = [
        i for i in detail["ingredients"]
        if i["stock_item_id"] and i["stock_item_id"] != target and not i["expiry_date"]
    ]
    assert all(i["is_expiring"] is False for i in others), others


def test__recipe_detail__flag_agrees_with_the_cookbook_filter(api):
    """The defect this exists to prevent: a recipe the "uses expiring
    ingredients" filter returned, opening with nothing marked. Uses a date
    inside the filter's horizon but outside the client's 7-day display band."""
    recipe = _recipe_with_a_linked_ingredient()
    target = next(i["stock_item_id"] for i in recipe["ingredients"] if i["stock_item_id"])
    assert EXPIRING_HORIZON_DAYS > 7, "the interesting band only exists above the display band"

    _set_expiry(target, _household_today() + timedelta(days=EXPIRING_HORIZON_DAYS - 1))

    filtered = requests.get(
        f"{RECIPES}?limit=200&expiring_within_days={EXPIRING_HORIZON_DAYS}"
    ).json()["items"]
    matched = next((r for r in filtered if r["recipe_id"] == recipe["recipe_id"]), None)
    assert matched is not None, "recipe should match the filter it was set up for"

    # Whatever the filter counted, the detail page can point at.
    detail = _detail(recipe["recipe_id"])
    assert any(i["is_expiring"] for i in detail["ingredients"]), detail["ingredients"]
    assert _ingredient(detail, target)["is_expiring"] is True


def test__recipe_detail__separates_expired_from_expiring(api):
    """Past its date reads as expired (red), not merely soon (amber)."""
    recipe = _recipe_with_a_linked_ingredient()
    target = next(i["stock_item_id"] for i in recipe["ingredients"] if i["stock_item_id"])

    _set_expiry(target, _household_today() - timedelta(days=1))

    flagged = _ingredient(_detail(recipe["recipe_id"]), target)
    assert flagged["is_expiring"] is True, flagged
    assert flagged["is_expired"] is True, flagged


def test__recipe_detail__ignores_expiry_beyond_the_horizon(api):
    """Well outside the horizon is not flagged — the chip has to stay rare
    enough to mean something."""
    recipe = _recipe_with_a_linked_ingredient()
    target = next(i["stock_item_id"] for i in recipe["ingredients"] if i["stock_item_id"])

    _set_expiry(target, _household_today() + timedelta(days=EXPIRING_HORIZON_DAYS + 30))

    flagged = _ingredient(_detail(recipe["recipe_id"]), target)
    assert flagged["is_expiring"] is False, flagged
    assert flagged["is_expired"] is False, flagged


def test__recipe_list__carries_the_same_flags_as_the_detail(api):
    """List and detail are one contract — the cookbook card, the picker and
    cook mode all read the same DTO."""
    recipe = _recipe_with_a_linked_ingredient()
    target = next(i["stock_item_id"] for i in recipe["ingredients"] if i["stock_item_id"])

    _set_expiry(target, _household_today() + timedelta(days=3))

    listed = next(
        r for r in requests.get(f"{RECIPES}?limit=200").json()["items"]
        if r["recipe_id"] == recipe["recipe_id"]
    )
    assert _ingredient(listed, target)["is_expiring"] is True
    assert _ingredient(_detail(recipe["recipe_id"]), target)["is_expiring"] is True


def test__cookbook_filter__reports_the_soonest_expiry_per_recipe(api):
    """`expiring_soonest_date` is the EARLIEST at-risk date in the recipe.

    This is what the cookbook ranks on (owner feedback 2026-08-18): ordering by
    the raw count put "4 ingredients expiring next week" above "2 expiring
    today", which is backwards for a filter whose whole job is rescuing food
    that's about to be binned. Pinning "soonest, not last-seen, not the count"
    is the part that would regress silently — a max/last-write bug still looks
    plausible in the UI.
    """
    items = requests.get(f"{RECIPES}?limit=200").json()["items"]
    recipe = next(
        (r for r in items
         if len([i for i in r["ingredients"] if i["stock_item_id"]]) >= 2),
        None,
    )
    assert recipe is not None, "seed expected to have a recipe with 2+ linked ingredients"
    linked = [i["stock_item_id"] for i in recipe["ingredients"] if i["stock_item_id"]][:2]

    today = _household_today()
    far = today + timedelta(days=EXPIRING_HORIZON_DAYS - 1)
    near = today + timedelta(days=2)
    # Set the FAR one first, so a naive "last one wins" implementation would
    # report `far` and fail here.
    _set_expiry(linked[0], far)
    _set_expiry(linked[1], near)

    filtered = requests.get(
        f"{RECIPES}?limit=200&expiring_within_days={EXPIRING_HORIZON_DAYS}"
    ).json()["items"]
    matched = next((r for r in filtered if r["recipe_id"] == recipe["recipe_id"]), None)
    assert matched is not None, "recipe should match the filter it was set up for"

    assert matched["expiring_soonest_date"] == near.isoformat(), matched
    assert matched["expiring_ingredient_count"] >= 2, matched


def test__cookbook_filter__soonest_date_is_absent_without_the_filter(api):
    """The urgency field rides the same opt-in as the count: the default
    cookbook load doesn't pay for the expiry query, so it stays null."""
    recipe = _recipe_with_a_linked_ingredient()
    target = next(i["stock_item_id"] for i in recipe["ingredients"] if i["stock_item_id"])
    _set_expiry(target, _household_today() + timedelta(days=2))

    unfiltered = requests.get(f"{RECIPES}?limit=200").json()["items"]
    row = next(r for r in unfiltered if r["recipe_id"] == recipe["recipe_id"])
    assert row["expiring_soonest_date"] is None, row
    assert row["expiring_ingredient_count"] == 0, row


def test__uses_expiring__resolves_to_the_server_horizon(api):
    # FU-669: the cookbook filter names no number; the server's horizon decides.
    import requests as _r
    base = "http://localhost:5170/api/recipes"
    by_flag = {r["recipe_id"] for r in _r.get(f"{base}?uses_expiring=true&limit=500").json()["items"]}
    by_days = {r["recipe_id"] for r in _r.get(f"{base}?expiring_within_days=14&limit=500").json()["items"]}
    assert by_flag == by_days
