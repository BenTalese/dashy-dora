"""PATCH / partial-update semantics across the core surfaces.

Every update handler in the app uses the same pydantic convention —
`model_fields_set` distinguishes *missing* from *explicitly null* — but
each surface applies it slightly differently. This suite pins the actual
contract per surface so a future refactor (e.g. a move to `exclude_unset`
dict-dumps) can't silently flip a "null clears" field into "null ignored"
or vice versa.

Covered here (only what the per-router suites DON'T already cover —
`test_stock_item_router.py` owns empty-PATCH / rename-only / dup-name /
extra-attrs for stock items, `test_stock_location_router.py` likewise,
`test_shopping_list_planned_shop_date.py` owns the planned_shop_date
set/clear round-trip):

  * stock items      — null-out semantics per field, cross-field 4xx
  * stock locations  — null name, unknown field
  * recipes          — partial isolation, null-out matrix, FK 4xx, vocab
  * shopping lists   — name clear, status=done guard, no-op
  * shopping lines   — null quantity / is_ticked / selected_product
  * stores           — rename-only isolation, image clear-vs-null, dup
  * meal plans       — partial isolation, null matrix, unknown field
  * auth/me          — partial isolation, null-out matrix, unknown field
  * users (admin)    — email null-out, last-admin guard, unknown field

Null-out contract summary (pinned by the tests below — product owner
should confirm this is the *intended* matrix, it is currently implicit):

  clears on explicit null : stock_item.notes / .stock_location_id /
                            .stock_group_id / .opened_on / .expiry_date,
                            recipe's plain nullable attrs + FK vocabs,
                            shopping_list.name, line.quantity,
                            user.dashboard_layout, admin-user.email
  ignored on explicit null: any non-nullable field (names, bools,
                            stock_level_id), store.image (clear_image
                            flag required), line.selected_product_id
                            (clear_selected_product flag required)
"""
from datetime import date, timedelta
from uuid import uuid4

import pytest
import requests

from dora_api.app import app
from dora_api.domain.entities.consumption_event import ConsumptionEvent
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.persistence.field import EntityField
from tests.factories import make_product, make_stock_item, make_stock_location

BASE = "http://localhost:5170/api"


# ── helpers ───────────────────────────────────────────────────────────────

def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _stock_level_ids() -> list[str]:
    body = requests.get(f"{BASE}/stock-levels").json()
    return [lvl["stock_level_id"] for lvl in body["items"]]


def _item_detail(stock_item_id: str) -> dict:
    resp = requests.get(f"{BASE}/stock-items/{stock_item_id}/detail")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _recipe(recipe_id: str) -> dict:
    resp = requests.get(f"{BASE}/recipes/{recipe_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _make_recipe(**overrides) -> str:
    body = {"name": _uniq("patch-recipe"), **overrides}
    resp = requests.post(f"{BASE}/recipes", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["recipe_id"]


def _list_detail(list_id: str) -> dict:
    resp = requests.get(f"{BASE}/shopping-lists/{list_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _make_list(**overrides) -> str:
    resp = requests.post(f"{BASE}/shopping-lists", json=overrides)
    assert resp.status_code == 201, resp.text
    return resp.json()["shopping_list_id"]


def _make_store(**overrides) -> str:
    body = {"name": _uniq("patch-store"), **overrides}
    resp = requests.post(f"{BASE}/stores", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["store_id"]


def _store_row(store_id: str) -> dict:
    body = requests.get(
        f"{BASE}/stores", params={"filter": f"store_id:eq:{store_id}"}
    ).json()
    assert body["items"], f"store {store_id} not found in list"
    return body["items"][0]


def _me() -> dict:
    resp = requests.get(f"{BASE}/auth/me")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _household_today() -> date:
    return date.fromisoformat(
        requests.get(f"{BASE}/meal-plans/today").json()["today"]
    )


def _any_recipe_id() -> str:
    items = requests.get(f"{BASE}/recipes", params={"limit": 1}).json()["items"]
    assert items, "seed data should include at least one recipe"
    return items[0]["recipe_id"]


def _make_meal_plan() -> str:
    today = _household_today()
    resp = requests.post(f"{BASE}/meal-plans", json={
        "name": _uniq("patch-plan"),
        "start_date": today.isoformat(),
        "entries": [{
            "recipe_id": _any_recipe_id(),
            "scheduled_for": (today + timedelta(days=1)).isoformat(),
            "servings": 2,
            "slot": "Dinner",
        }],
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["meal_plan_id"]


def _meal_plan(plan_id: str) -> dict:
    body = requests.get(
        f"{BASE}/meal-plans", params={"filter": f"meal_plan_id:eq:{plan_id}"}
    ).json()
    assert body["items"], f"meal plan {plan_id} not in list"
    return body["items"][0]


# tiny valid data-URL for image fields
_IMG = "data:image/png;base64,iVBORw0KGgo="


# ═══ Stock items ══════════════════════════════════════════════════════════

def test__patch_stock_item__notes_only__leaves_every_other_detail_field_unchanged(api):
    level_id = _stock_level_ids()[0]
    item = make_stock_item(stock_level_id=level_id, name=_uniq("iso-item"))
    item_id = item["stock_item_id"]
    before = _item_detail(item_id)

    resp = requests.patch(f"{BASE}/stock-items/{item_id}", json={"notes": "just a note"})
    assert resp.status_code == 204, resp.text

    after = _item_detail(item_id)
    assert after["notes"] == "just a note"
    # Everything else — including the stock_level_last_updated stamp —
    # must be byte-identical to the pre-PATCH DTO.
    before.pop("notes"), after.pop("notes")
    assert after == before


def test__patch_stock_item__same_value_noop__changes_nothing(api):
    level_id = _stock_level_ids()[0]
    item = make_stock_item(stock_level_id=level_id, name=_uniq("noop-item"))
    item_id = item["stock_item_id"]
    requests.patch(f"{BASE}/stock-items/{item_id}", json={"notes": "same note"})
    before = _item_detail(item_id)

    # Re-send the same notes/flag values: succeeds, and the full DTO
    # (including stock_level_last_updated) is untouched. NOTE: a
    # same-value *name* is NOT usable here — rename-to-own-name 422s
    # (real bug, xfail-pinned below); nor is a same-value
    # stock_level_id (bumps stamps + appends a phantom history row,
    # also xfail-pinned below).
    resp = requests.patch(
        f"{BASE}/stock-items/{item_id}",
        json={"notes": "same note", "is_essential": False},
    )
    assert resp.status_code == 204, resp.text
    assert _item_detail(item_id) == before


# Regression for the FU-528-family self-exemption fix (2026-07-12): all five
# rename handlers compared a UUID `.id` against the raw str path param, so
# renaming any entity to its OWN name was rejected as a duplicate. Fixed with
# `str(...)` on both sides at each site; these five tests guard the fix.
def test__patch_stock_item__rename_to_own_name__is_accepted(api):
    level_id = _stock_level_ids()[0]
    name = _uniq("self-rename-item")
    item = make_stock_item(stock_level_id=level_id, name=name)
    resp = requests.patch(
        f"{BASE}/stock-items/{item['stock_item_id']}", json={"name": name}
    )
    assert resp.status_code == 204, resp.text


def test__patch_stock_item__same_stock_level__bumps_the_checked_stamps(api):
    """Pinned behaviour: re-sending the CURRENT stock_level_id is treated
    as "the user checked the level" — stock_level_last_updated and
    last_checked_at both move. Defensible: the SPA's level widget uses
    this as its confirm path. (The phantom history row the same write
    currently appends is a separate xfail-pinned bug below.)"""
    level_id = _stock_level_ids()[0]
    item = make_stock_item(stock_level_id=level_id, name=_uniq("stamp-item"))
    item_id = item["stock_item_id"]
    before = _item_detail(item_id)

    resp = requests.patch(f"{BASE}/stock-items/{item_id}", json={"stock_level_id": level_id})
    assert resp.status_code == 204, resp.text

    after = _item_detail(item_id)
    assert after["stock_level_id"] == before["stock_level_id"]
    assert after["stock_level_last_updated"] >= before["stock_level_last_updated"]
    assert after["last_checked_at"] is not None


# Regression for the FU-533 noload fix (2026-07-12): the handler now
# `.include(STOCK_LEVEL)` on load, so the previous level resolves and a
# same-level PATCH no longer appends a phantom history row.
def test__patch_stock_item__same_stock_level__does_not_append_history_row(api):
    level_id = _stock_level_ids()[0]
    item = make_stock_item(stock_level_id=level_id, name=_uniq("hist-item"))
    item_id = item["stock_item_id"]
    before = _item_detail(item_id)

    resp = requests.patch(f"{BASE}/stock-items/{item_id}", json={"stock_level_id": level_id})
    assert resp.status_code == 204, resp.text
    after = _item_detail(item_id)
    assert len(after["level_history"]) == len(before["level_history"])


# Regression for the FU-533 noload fix (2026-07-12): with the previous level
# now eager-loaded, a sourced DROP records its ConsumptionEvent — the P8-07/
# FU-449 depletion leg (cook-mode finish) writes again instead of silently
# losing the event.
def test__patch_stock_item__sourced_level_drop__records_consumption_event(api):
    # Higher `sequence` = more depleted; go top -> bottom so this is a DROP.
    levels = sorted(
        requests.get(f"{BASE}/stock-levels").json()["items"],
        key=lambda l: l["sequence"],
    )
    assert len(levels) >= 2
    top, bottom = levels[0], levels[-1]
    item = make_stock_item(
        stock_level_id=top["stock_level_id"], name=_uniq("consume-item")
    )
    item_id = item["stock_item_id"]

    resp = requests.patch(f"{BASE}/stock-items/{item_id}", json={
        "stock_level_id": bottom["stock_level_id"],
        "consumption_source": "manual",
    })
    assert resp.status_code in (200, 204), resp.text

    with app.app_context():
        events = SqlAlchemyRepository().get(ConsumptionEvent).all(
            EntityField(ConsumptionEvent, "stock_item_id").eq(item_id)
        )
    assert len(events) == 1, (
        "a sourced level drop should persist exactly one ConsumptionEvent"
    )


def test__patch_stock_item__null_name__is_ignored(api):
    # Pinned: `name` is non-nullable on the entity; the handler applies
    # it only when non-None, so an explicit null is silently ignored
    # (not a 400).
    level_id = _stock_level_ids()[0]
    name = _uniq("null-name-item")
    item = make_stock_item(stock_level_id=level_id, name=name)

    resp = requests.patch(
        f"{BASE}/stock-items/{item['stock_item_id']}", json={"name": None}
    )
    assert resp.status_code == 204, resp.text
    assert _item_detail(item["stock_item_id"])["name"] == name


def test__patch_stock_item__null_stock_level_id__is_ignored_and_stamps_untouched(api):
    # Pinned: an item always has a level; explicit null on stock_level_id
    # is ignored and does NOT bump stock_level_last_updated.
    level_id = _stock_level_ids()[0]
    item = make_stock_item(stock_level_id=level_id, name=_uniq("null-level-item"))
    before = _item_detail(item["stock_item_id"])

    resp = requests.patch(
        f"{BASE}/stock-items/{item['stock_item_id']}", json={"stock_level_id": None}
    )
    assert resp.status_code == 204, resp.text
    after = _item_detail(item["stock_item_id"])
    assert after["stock_level_id"] == before["stock_level_id"]
    assert after["stock_level_last_updated"] == before["stock_level_last_updated"]


def test__patch_stock_item__null_stock_location_id__clears_location(api):
    # Pinned asymmetry with stock_level_id: location is optional, so an
    # explicit null CLEARS it (same effect as clear_stock_location=true).
    level_id = _stock_level_ids()[0]
    loc = make_stock_location(name=_uniq("null-loc"))
    item = make_stock_item(
        stock_level_id=level_id,
        stock_location_id=loc["location_id"],
        name=_uniq("null-loc-item"),
    )
    assert _item_detail(item["stock_item_id"])["stock_location_id"] is not None

    resp = requests.patch(
        f"{BASE}/stock-items/{item['stock_item_id']}", json={"stock_location_id": None}
    )
    assert resp.status_code == 204, resp.text
    assert _item_detail(item["stock_item_id"])["stock_location_id"] is None


def test__patch_stock_item__null_notes__clears_notes(api):
    # Pinned: notes is nullable → explicit null clears.
    level_id = _stock_level_ids()[0]
    item = make_stock_item(stock_level_id=level_id, name=_uniq("null-notes-item"))
    item_id = item["stock_item_id"]
    requests.patch(f"{BASE}/stock-items/{item_id}", json={"notes": "to be removed"})
    assert _item_detail(item_id)["notes"] == "to be removed"

    resp = requests.patch(f"{BASE}/stock-items/{item_id}", json={"notes": None})
    assert resp.status_code == 204, resp.text
    assert _item_detail(item_id)["notes"] is None


def test__patch_stock_item__nonexistent_stock_level__is_clean_422_not_500(api):
    level_id = _stock_level_ids()[0]
    item = make_stock_item(stock_level_id=level_id, name=_uniq("bad-level-item"))
    before = _item_detail(item["stock_item_id"])

    resp = requests.patch(
        f"{BASE}/stock-items/{item['stock_item_id']}",
        json={"stock_level_id": str(uuid4())},
    )
    assert resp.status_code == 422, resp.text
    assert "stock_level_id" in resp.json()["errors"]
    # Rejected atomically — nothing changed.
    assert _item_detail(item["stock_item_id"]) == before


def test__patch_stock_item__nonexistent_stock_group__is_clean_422_not_500(api):
    level_id = _stock_level_ids()[0]
    item = make_stock_item(stock_level_id=level_id, name=_uniq("bad-group-item"))

    resp = requests.patch(
        f"{BASE}/stock-items/{item['stock_item_id']}",
        json={"stock_group_id": str(uuid4())},
    )
    assert resp.status_code == 422, resp.text
    assert "stock_group_id" in resp.json()["errors"]


# ═══ Locations ═══════════════════════════════════════════════════════════

def test__patch_location__null_name__is_ignored(api):
    # Pinned: name is non-nullable, so an explicit null is a silent no-op.
    loc = make_stock_location(name=_uniq("null-name-loc"))
    resp = requests.patch(f"{BASE}/locations/{loc['location_id']}", json={"name": None})
    assert resp.status_code == 204, resp.text
    tree = requests.get(f"{BASE}/locations").json()
    assert next(n for n in tree if n["location_id"] == loc["location_id"])["name"] == loc["name"]


def test__patch_location__rename_to_own_name__is_accepted(api):
    loc = make_stock_location(name=_uniq("self-rename-loc"))
    resp = requests.patch(f"{BASE}/locations/{loc['location_id']}", json={"name": loc["name"]})
    assert resp.status_code == 204, resp.text


def test__patch_location__unknown_field__rejected_400(api):
    loc = make_stock_location(name=_uniq("extra-loc"))
    resp = requests.patch(
        f"{BASE}/locations/{loc['location_id']}",
        json={"definitely_not_a_field": 1},
    )
    # extra="forbid" on every request model → unknown keys are hard 400s.
    assert resp.status_code == 400, resp.text
    assert "definitely_not_a_field" in resp.json()["errors"]


# ═══ Recipes ══════════════════════════════════════════════════════════════

def test__patch_recipe__notes_only__leaves_every_other_field_unchanged(api):
    recipe_id = _make_recipe(servings=4, cook_time_minutes=25, instructions="stir")
    before = _recipe(recipe_id)

    resp = requests.patch(f"{BASE}/recipes/{recipe_id}", json={"notes": "cook's note"})
    assert resp.status_code == 204, resp.text

    after = _recipe(recipe_id)
    assert after["notes"] == "cook's note"
    # `updated_at` is the edit stamp (2026-08-24); every successful PATCH
    # moves it by design, so it is compared separately rather than pinned
    # as "unchanged".
    assert after["updated_at"] is not None
    before.pop("notes"), after.pop("notes")
    before.pop("updated_at"), after.pop("updated_at")
    assert after == before


def test__patch_recipe__empty_body__succeeds_and_changes_nothing(api):
    recipe_id = _make_recipe(servings=2)
    before = _recipe(recipe_id)

    resp = requests.patch(f"{BASE}/recipes/{recipe_id}", json={})
    assert resp.status_code == 204, resp.text
    after = _recipe(recipe_id)
    # An empty PATCH still counts as an edit attempt and stamps
    # `updated_at`; nothing else may move.
    before.pop("updated_at"), after.pop("updated_at")
    assert after == before


def test__patch_recipe__null_servings__clears_servings(api):
    # Pinned: the plain nullable attrs (servings, cook/prep time,
    # instructions, notes, source, kcal, difficulty, time_of_day) all
    # accept explicit null as "clear".
    recipe_id = _make_recipe(servings=6)
    resp = requests.patch(f"{BASE}/recipes/{recipe_id}", json={"servings": None})
    assert resp.status_code == 204, resp.text
    assert _recipe(recipe_id)["servings"] is None


def test__patch_recipe__null_name_and_null_is_favourite__are_ignored(api):
    # Pinned: name (non-nullable, uniqueness-checked) and is_favourite
    # (bool NOT NULL) ignore explicit nulls instead of erroring.
    recipe_id = _make_recipe()
    requests.patch(f"{BASE}/recipes/{recipe_id}", json={"is_favourite": True})
    before = _recipe(recipe_id)

    resp = requests.patch(
        f"{BASE}/recipes/{recipe_id}", json={"name": None, "is_favourite": None}
    )
    assert resp.status_code == 204, resp.text
    after = _recipe(recipe_id)
    assert after["name"] == before["name"]
    assert after["is_favourite"] is True


# Regression for the FU-533 noload fix (2026-07-12): the clear path now writes
# the underscore FK column (`_cuisine_id = None`) directly, so an explicit-null
# PATCH actually clears the link instead of silently no-op'ing.
# (category_id + recipe_collection_id share the same fix.)
def test__patch_recipe__null_cuisine_id__clears_the_link(api):
    cuisine = requests.post(f"{BASE}/cuisines", json={"name": _uniq("cuisine")})
    assert cuisine.status_code == 201, cuisine.text
    cuisine_id = cuisine.json()["cuisine_id"]
    recipe_id = _make_recipe()

    set_resp = requests.patch(f"{BASE}/recipes/{recipe_id}", json={"cuisine_id": cuisine_id})
    assert set_resp.status_code == 204, set_resp.text
    assert _recipe(recipe_id)["cuisine_id"] == cuisine_id

    clear_resp = requests.patch(f"{BASE}/recipes/{recipe_id}", json={"cuisine_id": None})
    assert clear_resp.status_code == 204, clear_resp.text
    assert _recipe(recipe_id)["cuisine_id"] is None


def test__patch_recipe__null_category_and_collection__clear_the_links(api):
    # Same FU-533 underscore-FK fix as cuisine, for the other two vocab FKs.
    cat = requests.post(f"{BASE}/categories", json={"name": _uniq("cat")})
    coll = requests.post(f"{BASE}/recipe-collections", json={"name": _uniq("coll")})
    assert cat.status_code == 201 and coll.status_code == 201, (cat.text, coll.text)
    recipe_id = _make_recipe()

    requests.patch(f"{BASE}/recipes/{recipe_id}", json={
        "category_id": cat.json()["category_id"],
        "recipe_collection_id": coll.json()["recipe_collection_id"],
    })
    assert _recipe(recipe_id)["category_id"] is not None

    clear = requests.patch(f"{BASE}/recipes/{recipe_id}", json={
        "category_id": None, "recipe_collection_id": None,
    })
    assert clear.status_code == 204, clear.text
    after = _recipe(recipe_id)
    assert after["category_id"] is None
    assert after.get("recipe_collection_id") is None


def test__patch_recipe__rename_to_own_name__is_accepted(api):
    recipe_id = _make_recipe()
    name = _recipe(recipe_id)["name"]
    resp = requests.patch(f"{BASE}/recipes/{recipe_id}", json={"name": name})
    assert resp.status_code == 204, resp.text


def test__patch_recipe__nonexistent_cuisine__is_clean_422_not_500(api):
    recipe_id = _make_recipe()
    resp = requests.patch(
        f"{BASE}/recipes/{recipe_id}", json={"cuisine_id": str(uuid4())}
    )
    assert resp.status_code == 422, resp.text
    assert "cuisine_id" in resp.json()["errors"]


def test__patch_recipe__invalid_difficulty__rejected_400(api):
    recipe_id = _make_recipe()
    resp = requests.patch(
        f"{BASE}/recipes/{recipe_id}", json={"difficulty": "impossible"}
    )
    assert resp.status_code == 400, resp.text
    assert "difficulty" in resp.text.lower()


def test__patch_recipe__unknown_field__rejected_400(api):
    recipe_id = _make_recipe()
    resp = requests.patch(
        f"{BASE}/recipes/{recipe_id}", json={"definitely_not_a_field": 1}
    )
    assert resp.status_code == 400, resp.text


# ═══ Shopping lists ═══════════════════════════════════════════════════════

def test__patch_shopping_list__name_only__leaves_status_and_dates_unchanged(api):
    list_id = _make_list(name="before-name", planned_shop_date="2030-01-01")
    before = _list_detail(list_id)

    resp = requests.patch(f"{BASE}/shopping-lists/{list_id}", json={"name": "after-name"})
    assert resp.status_code == 204, resp.text

    after = _list_detail(list_id)
    assert after["name"] == "after-name"
    for key in ("status", "created_at", "completed_at", "planned_shop_date", "lines"):
        assert after[key] == before[key], key


def test__patch_shopping_list__null_name__clears_custom_name(api):
    # Pinned: explicit null (or blank string) clears the custom name and
    # the list falls back to its date-derived display_name.
    list_id = _make_list(name="my custom name")
    resp = requests.patch(f"{BASE}/shopping-lists/{list_id}", json={"name": None})
    assert resp.status_code == 204, resp.text
    after = _list_detail(list_id)
    assert after["name"] is None
    assert after["display_name"]  # self-labelled fallback still present


def test__patch_shopping_list__empty_body__succeeds_and_changes_nothing(api):
    list_id = _make_list(name="noop-list")
    before = _list_detail(list_id)
    resp = requests.patch(f"{BASE}/shopping-lists/{list_id}", json={})
    assert resp.status_code == 204, resp.text
    assert _list_detail(list_id) == before


def test__patch_shopping_list__status__is_rejected_use_finish(api):
    # /finish is the only transition (UX v5): PATCH has no status field.
    list_id = _make_list(name="guard-list")
    resp = requests.patch(f"{BASE}/shopping-lists/{list_id}", json={"status": "done"})
    assert resp.status_code == 400, resp.text
    assert _list_detail(list_id)["status"] == "active"


def test__patch_shopping_list__unknown_field__rejected_400(api):
    list_id = _make_list()
    resp = requests.patch(
        f"{BASE}/shopping-lists/{list_id}", json={"definitely_not_a_field": 1}
    )
    assert resp.status_code == 400, resp.text


# ═══ Shopping list lines ══════════════════════════════════════════════════

def _make_list_with_line() -> tuple[str, str, str]:
    """Returns (list_id, line_id, stock_item_id)."""
    level_id = _stock_level_ids()[0]
    item = make_stock_item(stock_level_id=level_id, name=_uniq("line-item"))
    list_id = _make_list(name=_uniq("line-list"))
    resp = requests.post(
        f"{BASE}/shopping-lists/{list_id}/lines",
        json={"stock_item_id": item["stock_item_id"], "quantity": 3},
    )
    assert resp.status_code == 200, resp.text
    return list_id, resp.json()["line_id"], item["stock_item_id"]


def _line(list_id: str, line_id: str) -> dict:
    lines = _list_detail(list_id)["lines"]
    line = next(l for l in lines if l["line_id"] == line_id)
    return line


def test__patch_line__null_quantity__clears_quantity(api):
    # Pinned: `if "quantity" in set_fields: line.quantity = request.quantity`
    # — an explicit null WRITES null (the column is nullable, meaning
    # "unspecified amount"). Missing field leaves it alone.
    list_id, line_id, _ = _make_list_with_line()
    resp = requests.patch(
        f"{BASE}/shopping-lists/{list_id}/lines/{line_id}", json={"quantity": None}
    )
    assert resp.status_code == 204, resp.text
    assert _line(list_id, line_id)["quantity"] is None


def test__patch_line__null_is_ticked__is_ignored(api):
    list_id, line_id, _ = _make_list_with_line()
    requests.patch(f"{BASE}/shopping-lists/{list_id}/lines/{line_id}", json={"is_ticked": True})
    resp = requests.patch(
        f"{BASE}/shopping-lists/{list_id}/lines/{line_id}", json={"is_ticked": None}
    )
    assert resp.status_code == 204, resp.text
    assert _line(list_id, line_id)["is_ticked"] is True


def test__patch_line__null_selected_product__is_ignored_without_clear_flag(api):
    # Pinned clear-vs-unset contract: `selected_product_id: null` is a
    # documented no-op; only `clear_selected_product: true` clears.
    list_id, line_id, item_id = _make_list_with_line()
    product = make_product(name=_uniq("line-prod"), merchant_stockcode=_uniq("sku"))
    product_id = product["id"]
    set_resp = requests.patch(
        f"{BASE}/shopping-lists/{list_id}/lines/{line_id}",
        json={"selected_product_id": product_id},
    )
    assert set_resp.status_code == 204, set_resp.text
    assert _line(list_id, line_id)["selected_product_id"] == product_id

    null_resp = requests.patch(
        f"{BASE}/shopping-lists/{list_id}/lines/{line_id}",
        json={"selected_product_id": None},
    )
    assert null_resp.status_code == 204, null_resp.text
    assert _line(list_id, line_id)["selected_product_id"] == product_id  # untouched

    clear_resp = requests.patch(
        f"{BASE}/shopping-lists/{list_id}/lines/{line_id}",
        json={"clear_selected_product": True},
    )
    assert clear_resp.status_code == 204, clear_resp.text
    assert _line(list_id, line_id)["selected_product_id"] is None


def test__patch_line__empty_body__succeeds_and_changes_nothing(api):
    list_id, line_id, _ = _make_list_with_line()
    before = _line(list_id, line_id)
    resp = requests.patch(f"{BASE}/shopping-lists/{list_id}/lines/{line_id}", json={})
    assert resp.status_code == 204, resp.text
    assert _line(list_id, line_id) == before


def test__patch_line__on_wrong_parent_list__404(api):
    # Cross-entity ownership guard: a valid line id under a different
    # (also valid) list id must 404, not mutate.
    list_id, line_id, _ = _make_list_with_line()
    other_list = _make_list(name=_uniq("other-list"))
    resp = requests.patch(
        f"{BASE}/shopping-lists/{other_list}/lines/{line_id}", json={"quantity": 9}
    )
    assert resp.status_code == 404, resp.text
    assert _line(list_id, line_id)["quantity"] == 3


# ═══ Stores ═══════════════════════════════════════════════════════════════

def test__patch_store__rename_only__image_preserved(api):
    store_id = _make_store(image=_IMG)
    assert _store_row(store_id)["has_image"] is True

    new_name = _uniq("renamed-store")
    resp = requests.patch(f"{BASE}/stores/{store_id}", json={"name": new_name})
    assert resp.status_code == 204, resp.text
    row = _store_row(store_id)
    assert row["name"] == new_name
    assert row["has_image"] is True


def test__patch_store__null_image__is_ignored__clear_image_flag_clears(api):
    # Pinned clear-vs-unset contract (documented on UpdateStoreRequest):
    # `image: null` leaves the image untouched; `clear_image: true` clears.
    store_id = _make_store(image=_IMG)

    null_resp = requests.patch(f"{BASE}/stores/{store_id}", json={"image": None})
    assert null_resp.status_code == 204, null_resp.text
    assert _store_row(store_id)["has_image"] is True

    clear_resp = requests.patch(f"{BASE}/stores/{store_id}", json={"clear_image": True})
    assert clear_resp.status_code == 204, clear_resp.text
    assert _store_row(store_id)["has_image"] is False


def test__patch_store__empty_body__succeeds_and_changes_nothing(api):
    store_id = _make_store()
    before = _store_row(store_id)
    resp = requests.patch(f"{BASE}/stores/{store_id}", json={})
    assert resp.status_code == 204, resp.text
    assert _store_row(store_id) == before


def test__patch_store__duplicate_name_case_insensitive__rejected_422(api):
    a_name = _uniq("dupe-a")
    _make_store(name=a_name)
    store_b = _make_store(name=_uniq("dupe-b"))

    resp = requests.patch(f"{BASE}/stores/{store_b}", json={"name": a_name.upper()})
    assert resp.status_code == 422, resp.text
    assert "already exists" in resp.text


def test__patch_store__rename_to_own_name__is_accepted(api):
    name = _uniq("self-rename-store")
    store_id = _make_store(name=name)
    resp = requests.patch(f"{BASE}/stores/{store_id}", json={"name": name})
    assert resp.status_code == 204, resp.text


def test__patch_store__unknown_field__rejected_400(api):
    store_id = _make_store()
    resp = requests.patch(
        f"{BASE}/stores/{store_id}", json={"definitely_not_a_field": 1}
    )
    assert resp.status_code == 400, resp.text


def test__patch_store__missing_store__404(api):
    resp = requests.patch(f"{BASE}/stores/{uuid4()}", json={"name": "ghost"})
    assert resp.status_code == 404, resp.text


# ═══ Meal plans ═══════════════════════════════════════════════════════════

def test__patch_meal_plan__name_only__entries_and_start_date_unchanged(api):
    plan_id = _make_meal_plan()
    before = _meal_plan(plan_id)

    resp = requests.patch(f"{BASE}/meal-plans/{plan_id}", json={"name": "renamed plan"})
    assert resp.status_code == 204, resp.text

    after = _meal_plan(plan_id)
    assert after["name"] == "renamed plan"
    assert after["start_date"] == before["start_date"]
    assert after["entries"] == before["entries"]


def test__patch_meal_plan__null_fields__all_ignored(api):
    # Pinned: name / start_date / entries all ignore explicit null —
    # a meal plan has no clearable-by-null field (entry clearing goes
    # through entries=[] + confirm_clear_entries).
    plan_id = _make_meal_plan()
    before = _meal_plan(plan_id)

    resp = requests.patch(
        f"{BASE}/meal-plans/{plan_id}",
        json={"name": None, "start_date": None, "entries": None},
    )
    assert resp.status_code == 204, resp.text
    assert _meal_plan(plan_id) == before


def test__patch_meal_plan__empty_body__succeeds_and_changes_nothing(api):
    plan_id = _make_meal_plan()
    before = _meal_plan(plan_id)
    resp = requests.patch(f"{BASE}/meal-plans/{plan_id}", json={})
    assert resp.status_code == 204, resp.text
    assert _meal_plan(plan_id) == before


def test__patch_meal_plan__unknown_field__rejected_400(api):
    plan_id = _make_meal_plan()
    resp = requests.patch(
        f"{BASE}/meal-plans/{plan_id}", json={"definitely_not_a_field": 1}
    )
    assert resp.status_code == 400, resp.text


# ═══ Auth /me ═════════════════════════════════════════════════════════════

def test__patch_me__single_field__leaves_every_other_field_unchanged(api):
    before = _me()
    new_day = (before["send_deals_on_day"] + 1) % 7

    resp = requests.patch(f"{BASE}/auth/me", json={"send_deals_on_day": new_day})
    assert resp.status_code == 200, resp.text

    after = _me()
    assert after["send_deals_on_day"] == new_day
    before.pop("send_deals_on_day"), after.pop("send_deals_on_day")
    assert after == before


def test__patch_me__empty_body__succeeds_and_changes_nothing(api):
    before = _me()
    resp = requests.patch(f"{BASE}/auth/me", json={})
    # PATCH /me echoes the DTO (200), unlike the 204-returning surfaces.
    assert resp.status_code == 200, resp.text
    assert _me() == before


def test__patch_me__null_username__is_ignored(api):
    before = _me()
    resp = requests.patch(f"{BASE}/auth/me", json={"username": None})
    assert resp.status_code == 200, resp.text
    assert _me()["username"] == before["username"]


# FU-612 — the `meals_per_week` per-user preference was deleted end-to-end
# (its only consumer, the sequential builder's target-count, was removed in the
# day×slot builder rework). No /auth/me field remains to null-out or bounds-check.


# FU-615 — `household_headcount` moved off /auth/me to the install-wide
# AppSetting; its null-clear round-trip now lives in test_onboarding_flags.py
# (`test__app_settings__household_headcount_roundtrips`).


def test__patch_me__unknown_field__rejected_400(api):
    resp = requests.patch(f"{BASE}/auth/me", json={"definitely_not_a_field": 1})
    assert resp.status_code == 400, resp.text


def test__patch_me__email__updates_directly(api):
    # The verified POST /auth/me/email flow was retired as overengineered;
    # PATCH /auth/me now accepts `email` and updates it in place. Invalid
    # formats still hard-reject.
    original = requests.get(f"{BASE}/auth/me").json().get("email")
    try:
        bad = requests.patch(f"{BASE}/auth/me", json={"email": "not-an-email"})
        assert bad.status_code == 422, bad.text

        resp = requests.patch(f"{BASE}/auth/me", json={"email": "Fresh@Example.com"})
        assert resp.status_code == 200, resp.text
        # normalise_email lower-cases the stored value.
        assert resp.json()["email"] == "fresh@example.com", resp.text
    finally:
        requests.patch(f"{BASE}/auth/me", json={"email": original or ""})


# ═══ Users (admin PATCH) ══════════════════════════════════════════════════

def _make_user(**overrides) -> str:
    body = {"username": _uniq("patch-user"), **overrides}
    resp = requests.post(f"{BASE}/users", json=body)
    # admin_create_user returns 200 + {user_id, new_password} (the one-time
    # password travels in the body, so it isn't the created() 201 shape).
    assert resp.status_code == 200, resp.text
    return resp.json()["user_id"]


def _user_row(user_id: str) -> dict:
    body = requests.get(
        f"{BASE}/users", params={"filter": f"user_id:eq:{user_id}"}
    ).json()
    assert body["items"], f"user {user_id} not found"
    return body["items"][0]


def test__admin_patch_user__username_only__email_and_flags_unchanged(api):
    user_id = _make_user(email=f"{_uniq('mail')}@example.com")
    before = _user_row(user_id)

    new_name = _uniq("renamed-user")
    resp = requests.patch(f"{BASE}/users/{user_id}", json={"username": new_name})
    assert resp.status_code == 204, resp.text

    after = _user_row(user_id)
    assert after["username"] == new_name
    assert after["email"] == before["email"]
    assert after["is_admin"] == before["is_admin"]


def test__admin_patch_user__null_email__clears_email(api):
    # Pinned: unlike /auth/me (which forbids email entirely), the admin
    # PATCH applies `email` unconditionally when present — explicit null
    # CLEARS the address, no verification flow involved.
    user_id = _make_user(email=f"{_uniq('mail')}@example.com")
    resp = requests.patch(f"{BASE}/users/{user_id}", json={"email": None})
    assert resp.status_code == 204, resp.text
    assert _user_row(user_id)["email"] is None


def test__admin_patch_user__null_is_admin__is_ignored(api):
    user_id = _make_user(is_admin=True)
    resp = requests.patch(f"{BASE}/users/{user_id}", json={"is_admin": None})
    assert resp.status_code == 204, resp.text
    assert _user_row(user_id)["is_admin"] is True


def test__admin_patch_user__demoting_last_admin__rejected_422(api):
    # The seeded "dora" account is the only admin in the test DB —
    # demoting it must trip the last-admin guard.
    me = _me()
    assert me["is_admin"] is True
    resp = requests.patch(f"{BASE}/users/{me['user_id']}", json={"is_admin": False})
    assert resp.status_code == 422, resp.text
    assert "last admin" in resp.text.lower()
    assert _me()["is_admin"] is True


def test__admin_patch_user__duplicate_username__rejected_422(api):
    user_a = _make_user()
    user_b = _make_user()
    taken = _user_row(user_a)["username"]
    resp = requests.patch(f"{BASE}/users/{user_b}", json={"username": taken})
    assert resp.status_code == 422, resp.text
    assert "already taken" in resp.text


def test__admin_patch_user__resubmit_own_username__is_accepted(api):
    user_id = _make_user()
    username = _user_row(user_id)["username"]
    resp = requests.patch(f"{BASE}/users/{user_id}", json={"username": username})
    assert resp.status_code == 204, resp.text


def test__admin_patch_user__unknown_field__rejected_400(api):
    user_id = _make_user()
    resp = requests.patch(
        f"{BASE}/users/{user_id}", json={"definitely_not_a_field": 1}
    )
    assert resp.status_code == 400, resp.text
