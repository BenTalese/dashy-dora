"""Cross-entity delete / referential-integrity behaviour (bug-hunting suite).

Systematic coverage of "delete an entity that other entities reference":
every scenario builds the reference web through the HTTP boundary, deletes,
asserts the delete response, then walks every dependent read surface and
asserts it still answers without a 500 and shows a sensible state.

Cascade ground truth (dora_api/persistence/table_mappings.py; SQLite enforces
these because app.py issues `PRAGMA foreign_keys=ON` per connection):

  StockItem   ← RecipeIngredient.stock_item_id      RESTRICT (handler 422s first)
              ← ShoppingListLine.stock_item_id      CASCADE  (open-list line vanishes)
              ← StockLevelChange / PreferredBuy /
                StockItemPriceObservation / links   CASCADE
              ← Waste / Consumption / Expiry events SET NULL (denormalised name kept)
  Recipe      ← MealPlanEntry / TemplateEntry       CASCADE  (silent unschedule)
              ← CookEvent / ConsumptionEvent        SET NULL
  Store       ← Product.store_id                    RESTRICT (handler 422s first)
              ← usual_store / purchased_store /
                observation.store_id                SET NULL
  StockLocation ← child.parent_id                   CASCADE
                ← StockItem.stock_location_id       SET NULL
  MealPlan    ← MealPlanEntry → ReconcileReceipt    CASCADE (both hops)
  ShoppingList ← lines / attachments                CASCADE
               ← observation.shopping_list_line_id  SET NULL (provenance is lossy)
  RecipeCollection ← Recipe.recipe_collection_id    SET NULL
  Product     — has NO delete endpoint at all (pinned below); only unlink.

Determinism: dates derive from the household-today anchor
(GET /api/meal-plans/today), never a local wall-clock read.
"""
from datetime import timedelta
from uuid import uuid4

import requests
from sqlalchemy import text

from dora_api.app import app, db
from tests.factories import make_stock_item
from tests.support import (assert_envelope, assert_problem, set_money_enabled,
                           uuid_bind)

BASE = "http://localhost:5170/api"
STOCK_ITEMS = f"{BASE}/stock-items"
RECIPES = f"{BASE}/recipes"
STORES = f"{BASE}/stores"
PRODUCTS = f"{BASE}/products"
SHOPPING_LISTS = f"{BASE}/shopping-lists"
MEAL_PLANS = f"{BASE}/meal-plans"
LOCATIONS = f"{BASE}/locations"
STOCK_LOCATIONS = f"{BASE}/stock-locations"
COLLECTIONS = f"{BASE}/recipe-collections"
TEMPLATES = f"{BASE}/meal-plan-templates"

# 1x1 PNG data-URL for the attachment leg (same fixture shape as
# test_shopping_list_attachments.py).
PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+P+/HgAF"
    "hAJ/wlseKgAAAABJRU5ErkJggg=="
)

#region ---------------- setup ----------------


def _level_id() -> str:
    return requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]


def _make_item(prefix: str, **overrides) -> dict:
    return make_stock_item(
        stock_level_id=_level_id(),
        name=f"{prefix} {uuid4().hex[:8]}",
        **overrides,
    )


def _make_recipe(prefix: str = "DelInt Recipe", **body) -> dict:
    resp = requests.post(RECIPES, json={"name": f"{prefix} {uuid4().hex[:8]}", **body})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _recipe_detail(recipe_id: str):
    return requests.get(f"{RECIPES}/{recipe_id}")


def _make_store(prefix: str = "DelIntStore") -> str:
    name = f"{prefix}-{uuid4().hex[:8]}"
    resp = requests.post(STORES, json={"name": name})
    assert resp.status_code == 201, resp.text
    stores = requests.get(STORES).json()["items"]
    return next(s["store_id"] for s in stores if s["name"] == name)


def _make_product(store_name_less_store_id: str | None = None, *, store_name: str | None = None) -> str:
    """Create a product against an existing store (by name) and return its id."""
    assert store_name, "pass store_name="
    resp = requests.post(PRODUCTS, json={
        "name": f"DelIntProduct-{uuid4().hex[:8]}",
        "store_name": store_name,
        "merchant_stockcode": f"DELINT-{uuid4().hex[:8]}",
        "brand": "Test",
        "price_now": 4.0,
        "price_was": 5.0,
        "is_active": True,
        "is_available": True,
        "size": "1L",
        "size_unit": "L",
        "size_value": 1.0,
    })
    assert resp.status_code == 201, resp.text
    # Location header shape: /api/products?filter=product_id:eq:<uuid>
    return resp.headers["location"].rsplit(":", 1)[-1]


def _store_name(store_id: str) -> str:
    stores = requests.get(STORES).json()["items"]
    return next(s["name"] for s in stores if s["store_id"] == store_id)


def _make_list(prefix: str = "DelIntList") -> str:
    resp = requests.post(SHOPPING_LISTS, json={"name": f"{prefix}-{uuid4().hex[:8]}"})
    assert resp.status_code == 201, resp.text
    return resp.json()["shopping_list_id"]


def _add_line(list_id: str, **body) -> str:
    resp = requests.post(f"{SHOPPING_LISTS}/{list_id}/lines", json=body)
    assert resp.status_code in (200, 201), resp.text
    lines = requests.get(f"{SHOPPING_LISTS}/{list_id}").json()["lines"]
    return lines[-1]["line_id"]


def _list_detail(list_id: str):
    return requests.get(f"{SHOPPING_LISTS}/{list_id}")


def _household_today():
    from datetime import date
    return date.fromisoformat(requests.get(f"{MEAL_PLANS}/today").json()["today"])


def _slot() -> str:
    return requests.get(f"{BASE}/meal-slots").json()[0]["name"]


def _make_plan(entries: list[dict] | None = None, start_date=None) -> dict:
    body = {
        "name": f"DelInt Plan {uuid4().hex[:8]}",
        "start_date": (start_date or _household_today()).isoformat(),
    }
    if entries is not None:
        body["entries"] = entries
    resp = requests.post(MEAL_PLANS, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _plan_by_id(meal_plan_id: str) -> dict | None:
    items = assert_envelope(
        requests.get(f"{MEAL_PLANS}?filter=meal_plan_id:eq:{meal_plan_id}")
    )
    return items[0] if items else None


def _assert_dashboard_reads(context: str) -> None:
    resp = requests.get(f"{BASE}/dashboard/summary")
    assert resp.status_code == 200, f"dashboard broke after {context}: {resp.text[:300]}"


def _sql_count(table: str, column: str, entity_id: str) -> int:
    with app.app_context(), db.engine.begin() as conn:
        return conn.execute(
            text(f'SELECT COUNT(*) FROM "{table}" WHERE {column} = :id'),
            {"id": uuid_bind(entity_id)},
        ).scalar_one()

#endregion setup

#region ---------------- 1. stock item ----------------


def test__delete_stock_item__linked_as_recipe_ingredient__blocked_422_listing_recipes(api):
    _Item = _make_item("DelInt Flour")
    _Recipe = _make_recipe("DelInt Bread", ingredients=[
        {"stock_item_id": _Item["stock_item_id"], "quantity": 2, "unit": "cup"},
    ])

    _Response = requests.delete(f"{STOCK_ITEMS}/{_Item['stock_item_id']}")

    # RecipeIngredient.stock_item_id is ON DELETE RESTRICT; the handler
    # pre-empts the FK error with a structured 422 (delete_stock_item.py).
    _Body = assert_problem(_Response, 422, title="Stock item is in use.")
    assert _Body["blocked_by_recipes"] == [
        {"recipe_id": _Recipe["recipe_id"], "name": _Recipe["name"]},
    ]
    # Item survives the refused delete.
    assert requests.get(f"{STOCK_ITEMS}/{_Item['stock_item_id']}/detail").status_code == 200


def test__delete_stock_item__full_reference_web__cascades_and_history_survives(api):
    # The web: substitute pair, open shopping-list line, level history,
    # waste event, manual price observation, preferred buy.
    _Item = _make_item("DelInt Milk")
    _ItemId = _Item["stock_item_id"]
    _Partner = _make_item("DelInt Oat Milk")
    assert requests.post(
        f"{STOCK_ITEMS}/{_ItemId}/substitutes",
        json={"substitute_id": _Partner["stock_item_id"]},
    ).status_code in (200, 201, 204)

    _ListId = _make_list()
    _add_line(_ListId, stock_item_id=_ItemId)

    # level history (StockLevelChange) via a level flip
    _Levels = requests.get(f"{BASE}/stock-levels").json()["items"]
    assert requests.patch(
        f"{STOCK_ITEMS}/{_ItemId}",
        json={"stock_level_id": _Levels[-1]["stock_level_id"]},
    ).status_code == 204

    _Waste = requests.post(f"{BASE}/waste/events", json={
        "stock_item_id": _ItemId, "reason": "expired",
    })
    assert _Waste.status_code == 200, _Waste.text
    _WasteEventId = _Waste.json()["event_id"]

    assert requests.post(f"{STOCK_ITEMS}/{_ItemId}/price-observations", json={
        "total_price": 3.5, "total_measure": 1.0, "unit": "L",
    }).status_code == 204
    assert requests.post(f"{STOCK_ITEMS}/{_ItemId}/preferred-buys", json={
        "label": "the blue carton",
    }).status_code in (200, 201, 204)

    _Response = requests.delete(f"{STOCK_ITEMS}/{_ItemId}")
    assert _Response.status_code == 204, _Response.text

    # Open list still reads; the line vanished silently (DB CASCADE).
    # Pinned actual behaviour: no warning, no tombstone line.
    _List = _list_detail(_ListId)
    assert _List.status_code == 200, _List.text
    assert _List.json()["lines"] == []

    # Waste history survives the item (SET NULL + denormalised name).
    _Events = requests.get(f"{BASE}/waste/events?limit=200").json()["events"]
    _Mine = next(e for e in _Events if e["event_id"] == _WasteEventId)
    assert _Mine["stock_item_id"] is None
    assert _Mine["stock_item_name"] == _Item["name"]

    # Substitute pair rows cascaded; the partner reads clean.
    _PartnerDetail = requests.get(
        f"{STOCK_ITEMS}/{_Partner['stock_item_id']}/detail"
    )
    assert _PartnerDetail.status_code == 200, _PartnerDetail.text
    assert _PartnerDetail.json()["substitutes"] == []

    # Owned children are actually gone (no orphan rows under the ORM's radar).
    assert _sql_count("StockItemPriceObservation", "stock_item_id", _ItemId) == 0
    assert _sql_count("PreferredBuy", "stock_item_id", _ItemId) == 0
    assert _sql_count("StockLevelChange", "stock_item_id", _ItemId) == 0
    assert _sql_count("ShoppingListLine", "stock_item_id", _ItemId) == 0

    assert requests.get(f"{STOCK_ITEMS}/{_ItemId}/detail").status_code == 404
    _assert_dashboard_reads("stock item delete")


def test__delete_stock_item__ingredient_downgraded_to_raw_text__delete_allowed_and_recipe_reads(api):
    _Item = _make_item("DelInt Saffron")
    _Recipe = _make_recipe("DelInt Paella", ingredients=[
        {"stock_item_id": _Item["stock_item_id"], "quantity": 1, "unit": "tsp"},
    ])

    # Unlink by replacing the ingredient set with a raw_text-only row —
    # the RESTRICT no longer bites because the FK is now NULL.
    assert requests.patch(f"{RECIPES}/{_Recipe['recipe_id']}", json={
        "ingredients": [{"raw_text": "1 tsp saffron threads"}],
    }).status_code == 204

    assert requests.delete(f"{STOCK_ITEMS}/{_Item['stock_item_id']}").status_code == 204

    _Detail = _recipe_detail(_Recipe["recipe_id"])
    assert _Detail.status_code == 200, _Detail.text
    _Ingredients = _Detail.json()["ingredients"]
    assert len(_Ingredients) == 1
    assert _Ingredients[0]["stock_item_id"] is None
    assert _Ingredients[0]["raw_text"] == "1 tsp saffron threads"

#endregion

#region ---------------- 2. recipe ----------------


def test__delete_recipe__scheduled_on_meal_plan__entry_cascades_silently_and_plan_reads(api):
    _Recipe = _make_recipe("DelInt Planned")
    _Today = _household_today()
    _Plan = _make_plan(entries=[{
        "recipe_id": _Recipe["recipe_id"],
        "scheduled_for": _Today.isoformat(),
        "servings": 2,
        "slot": _slot(),
    }])
    assert len(_Plan["entries"]) == 1

    assert requests.delete(f"{RECIPES}/{_Recipe['recipe_id']}").status_code == 204

    # Pinned actual behaviour: MealPlanEntry.recipe_id is ON DELETE CASCADE,
    # so the slot silently empties — the plan survives with no trace the
    # meal was ever scheduled (no tombstone, no warning to the planner).
    _PlanAfter = _plan_by_id(_Plan["meal_plan_id"])
    assert _PlanAfter is not None
    assert _PlanAfter["entries"] == []
    _assert_dashboard_reads("recipe delete with plan entry")


def test__delete_recipe__in_collection_with_cook_history__collection_and_reports_read(api):
    _Collection = requests.post(COLLECTIONS, json={"name": f"DelInt Coll {uuid4().hex[:8]}"})
    assert _Collection.status_code == 201
    _CollectionId = _Collection.json()["recipe_collection_id"]
    _Recipe = _make_recipe("DelInt Cooked", recipe_collection_id=_CollectionId)
    assert requests.post(
        f"{RECIPES}/{_Recipe['recipe_id']}/cook", json={"meals_cooked": 3},
    ).status_code == 200

    assert requests.delete(f"{RECIPES}/{_Recipe['recipe_id']}").status_code == 204

    # Collection survives (the FK points recipe -> collection, not back).
    _Collections = assert_envelope(requests.get(
        COLLECTIONS, params={"filter": f"recipe_collection_id:eq:{_CollectionId}"},
    ))
    assert len(_Collections) == 1
    # Cook history survives via SET NULL + denormalised recipe_name: the
    # meals-cooked report must still answer and still count the cook.
    _Report = requests.get(f"{BASE}/reports/meals-cooked")
    assert _Report.status_code == 200, _Report.text
    assert _Report.json()["meals_total"] >= 3
    assert any(
        r["recipe_name"] == _Recipe["name"] for r in _Report.json()["top_recipes"]
    ), "cooked recipe's denormalised name should survive its deletion"


def test__delete_recipe__referenced_by_meal_plan_template__template_entry_cascades(api):
    _Recipe = _make_recipe("DelInt Templated")
    _Today = _household_today()
    _Plan = _make_plan(entries=[{
        "recipe_id": _Recipe["recipe_id"],
        "scheduled_for": _Today.isoformat(),
        "slot": _slot(),
    }])
    _Template = requests.post(TEMPLATES, json={
        "name": f"DelInt Template {uuid4().hex[:8]}",
        "source_meal_plan_id": _Plan["meal_plan_id"],
    })
    assert _Template.status_code == 201, _Template.text
    _TemplateId = _Template.json()["meal_plan_template_id"]

    assert requests.delete(f"{RECIPES}/{_Recipe['recipe_id']}").status_code == 204

    # Pinned actual behaviour: MealPlanTemplateEntry.recipe_id is ON DELETE
    # CASCADE — the template survives but silently loses the entry (it can
    # quietly become an empty template).
    _Detail = requests.get(f"{TEMPLATES}/{_TemplateId}")
    assert _Detail.status_code == 200, _Detail.text
    assert _Detail.json()["entries"] == []

#endregion

#region ---------------- 3. store ----------------


def test__delete_store__with_linked_products__blocked_422_with_count(api):
    _StoreId = _make_store()
    _make_product(store_name=_store_name(_StoreId))

    _Response = requests.delete(f"{STORES}/{_StoreId}")

    _Body = assert_problem(_Response, 422, title="Business rule violation.")
    assert "1 linked product(s)" in str(_Body["errors"])
    # Store survives the refused delete.
    assert any(
        s["store_id"] == _StoreId
        for s in requests.get(STORES).json()["items"]
    )


def test__delete_store__hint_references__nulled_with_counts_and_reads_survive(api):
    _StoreId = _make_store("DelIntHints")
    # (a) usual-store hint on an item
    _Item = _make_item("DelInt Hinted")
    assert requests.patch(
        f"{STOCK_ITEMS}/{_Item['stock_item_id']}",
        json={"usual_store_id": _StoreId},
    ).status_code == 204
    # (b) price observation at that store
    assert requests.post(f"{STOCK_ITEMS}/{_Item['stock_item_id']}/price-observations", json={
        "total_price": 2.0, "total_measure": 1.0, "unit": "L", "store_id": _StoreId,
    }).status_code == 204
    # (c) purchased-store on a shopping-list line
    _ListId = _make_list()
    _LineId = _add_line(_ListId, stock_item_id=_Item["stock_item_id"])
    assert requests.patch(
        f"{SHOPPING_LISTS}/{_ListId}/lines/{_LineId}",
        json={"purchased_store_id": _StoreId},
    ).status_code == 204

    _Response = requests.delete(f"{STORES}/{_StoreId}")

    assert _Response.status_code == 200, _Response.text
    assert _Response.json() == {"items_affected": 1, "lines_affected": 1}
    # Every referencing surface reads back, hint degraded not broken.
    _History = requests.get(f"{STOCK_ITEMS}/{_Item['stock_item_id']}/price-history")
    assert _History.status_code == 200, _History.text
    assert _History.json()["sample_count"] == 1  # the observation itself survives
    assert _list_detail(_ListId).status_code == 200
    assert requests.get(f"{STOCK_ITEMS}/{_Item['stock_item_id']}/detail").status_code == 200


def test__delete_store__purchased_on_finished_list__spend_by_store_still_reads(api):
    _StoreId = _make_store("DelIntSpend")
    _Item = _make_item("DelInt Spent")
    _ListId = _make_list()
    _LineId = _add_line(_ListId, stock_item_id=_Item["stock_item_id"])
    assert requests.patch(
        f"{SHOPPING_LISTS}/{_ListId}/lines/{_LineId}",
        json={"is_ticked": True, "actual_unit_price": 6.5, "purchased_store_id": _StoreId},
    ).status_code == 204
    assert requests.post(f"{SHOPPING_LISTS}/{_ListId}/finish").status_code == 200

    assert requests.delete(f"{STORES}/{_StoreId}").status_code == 200

    # The spend report must still answer after the store behind a finished
    # purchase disappears (line FK is SET NULL). Money on first — the report
    # refuses with 403 otherwise (FU-816).
    set_money_enabled(True)
    _Spend = requests.get(f"{BASE}/reports/spend-by-store")
    assert _Spend.status_code == 200, _Spend.text
    _assert_dashboard_reads("store delete after finished shopping")

#endregion

#region ---------------- 4. location ----------------


def test__delete_location_subtree__items_in_descendants_unassigned_and_tree_reads(api):
    _Zone = requests.post(LOCATIONS, json={"name": f"DelInt Zone {uuid4().hex[:8]}", "kind": "zone"})
    assert _Zone.status_code == 201, _Zone.text
    _ZoneId = _Zone.json()["location_id"] if "location_id" in _Zone.json() else _Zone.json().get("stock_location_id")
    assert _ZoneId, f"unexpected create-location DTO: {_Zone.json()}"
    _Area = requests.post(LOCATIONS, json={
        "name": f"DelInt Area {uuid4().hex[:8]}", "kind": "area", "parent_id": _ZoneId,
    })
    assert _Area.status_code == 201, _Area.text
    _AreaId = _Area.json()["location_id"] if "location_id" in _Area.json() else _Area.json().get("stock_location_id")

    _ItemInZone = _make_item("DelInt InZone", stock_location_id=_ZoneId)
    _ItemInArea = _make_item("DelInt InArea", stock_location_id=_AreaId)

    assert requests.delete(f"{LOCATIONS}/{_ZoneId}").status_code == 204

    # Whole subtree gone; items survive unassigned (handler nulls + FK SET NULL).
    _Tree = requests.get(LOCATIONS)
    assert _Tree.status_code == 200, _Tree.text
    assert _ZoneId not in _Tree.text and str(_AreaId) not in _Tree.text
    for item in (_ItemInZone, _ItemInArea):
        _Row = assert_envelope(requests.get(
            f"{STOCK_ITEMS}?filter=stock_item_id:eq:{item['stock_item_id']}"
        ))[0]
        assert _Row["stock_location_id"] is None


def test__delete_stock_location__legacy_router__items_unassigned_via_fk(api):
    _Loc = requests.post(STOCK_LOCATIONS, json={"name": f"DelInt Legacy {uuid4().hex[:8]}"})
    assert _Loc.status_code == 201, _Loc.text
    _LocId = _Loc.json()["stock_location_id"]
    _Item = _make_item("DelInt LegacyLoc", stock_location_id=_LocId)

    assert requests.delete(f"{STOCK_LOCATIONS}/{_LocId}").status_code == 204

    # This router does a bare remove — the item's FK degrade is pure
    # DB-level ON DELETE SET NULL. Pinned: both delete routers converge on
    # the same end state (item survives, unassigned).
    _Row = assert_envelope(requests.get(
        f"{STOCK_ITEMS}?filter=stock_item_id:eq:{_Item['stock_item_id']}"
    ))[0]
    assert _Row["stock_location_id"] is None

#endregion

#region ---------------- 5. product ----------------


def test__delete_product__hard_deletes(api):
    _StoreId = _make_store("DelIntProdStore")
    _ProductId = _make_product(store_name=_store_name(_StoreId))

    # Was pinned as "no delete endpoint exists — 404": the overlay used to be
    # prunable only by unlinking or deactivating, because the companion pushed
    # bulk scrape results and anything deleted came straight back. The
    # companion now pushes only what the user saved (products program
    # PF-1/PF-3), so Dora owns what is saved and feedback L197 ("no way to
    # remove a saved product") is answered with a real delete — owner decision
    # D-1. Cascade + shopping-line retention live in `test_delete_product.py`.
    assert requests.delete(f"{PRODUCTS}/{_ProductId}").status_code == 204
    assert requests.delete(f"{PRODUCTS}/{_ProductId}").status_code == 404


def test__unlink_product_from_stock_item__both_sides_read_back(api):
    _StoreId = _make_store("DelIntLinkStore")
    _ProductId = _make_product(store_name=_store_name(_StoreId))
    _Item = _make_item("DelInt Linked")
    assert requests.post(
        f"{STOCK_ITEMS}/{_Item['stock_item_id']}/products",
        json={"product_id": _ProductId},
    ).status_code == 204
    _Detail = requests.get(f"{STOCK_ITEMS}/{_Item['stock_item_id']}/detail").json()
    assert len(_Detail["products"]) == 1

    assert requests.delete(
        f"{STOCK_ITEMS}/{_Item['stock_item_id']}/products/{_ProductId}"
    ).status_code == 204

    _DetailAfter = requests.get(f"{STOCK_ITEMS}/{_Item['stock_item_id']}/detail")
    assert _DetailAfter.status_code == 200
    assert _DetailAfter.json()["products"] == []
    # Unlink never deletes the product itself.
    _Products = assert_envelope(requests.get(
        f"{PRODUCTS}?filter=product_id:eq:{_ProductId}"
    ))
    assert len(_Products) == 1
    assert requests.get(
        f"{STOCK_ITEMS}/{_Item['stock_item_id']}/price-history"
    ).status_code == 200

#endregion

#region ---------------- 6. meal plan ----------------


def _backdate_entry(plan_id: str, entry_id: str, days_ago: int) -> None:
    """The create endpoint refuses past scheduled_for (correct); backdate via
    SQL to seed reconcile state — same seam as test_reconcile_receipts.py."""
    past = (_household_today() - timedelta(days=days_ago)).isoformat()
    with app.app_context(), db.engine.begin() as conn:
        conn.execute(
            text('UPDATE "MealPlanEntry" SET scheduled_for = :past WHERE id = :eid'),
            {"past": past, "eid": uuid_bind(entry_id)},
        )
        conn.execute(
            text('UPDATE "MealPlan" SET start_date = :past WHERE id = :pid'),
            {"past": past, "pid": uuid_bind(plan_id)},
        )


def test__delete_meal_plan__with_reconcile_receipts__receipts_cascade_and_queues_read(api):
    _Recipe = _make_recipe("DelInt Reconciled")
    _Plan = _make_plan(entries=[{
        "recipe_id": _Recipe["recipe_id"],
        "scheduled_for": _household_today().isoformat(),
        "servings": 1,
        "slot": _slot(),
    }])
    _PlanId = _Plan["meal_plan_id"]
    _EntryId = _Plan["entries"][0]["meal_plan_entry_id"]
    _backdate_entry(_PlanId, _EntryId, days_ago=2)
    # Any meal-plan GET fires the before_request reconcile sweep.
    assert requests.get(f"{MEAL_PLANS}/today").status_code == 200
    assert _sql_count("MealPlanReconcileReceipt", "meal_plan_entry_id", _EntryId) == 1

    assert requests.delete(f"{MEAL_PLANS}/{_PlanId}").status_code == 204

    # Two-hop cascade: plan -> entries -> receipts. No orphan receipts.
    assert _sql_count("MealPlanReconcileReceipt", "meal_plan_entry_id", _EntryId) == 0
    assert _sql_count("MealPlanEntry", "meal_plan_id", _PlanId) == 0
    assert requests.get(f"{MEAL_PLANS}/reconcile-queue").status_code == 200
    assert _plan_by_id(_PlanId) is None
    _assert_dashboard_reads("meal plan delete with receipts")


def test__delete_meal_plan__template_snapshotted_from_it__template_survives_independent(api):
    _Recipe = _make_recipe("DelInt PlanSource")
    _Plan = _make_plan(entries=[{
        "recipe_id": _Recipe["recipe_id"],
        "scheduled_for": _household_today().isoformat(),
        "slot": _slot(),
    }])
    _Template = requests.post(TEMPLATES, json={
        "name": f"DelInt FromPlan {uuid4().hex[:8]}",
        "source_meal_plan_id": _Plan["meal_plan_id"],
    })
    assert _Template.status_code == 201, _Template.text
    _TemplateId = _Template.json()["meal_plan_template_id"]

    assert requests.delete(f"{MEAL_PLANS}/{_Plan['meal_plan_id']}").status_code == 204

    # Decision 1 (C-2.F): a template is a snapshot, not a live link — it
    # keeps its entries after the source plan dies, and stays appliable.
    _Detail = requests.get(f"{TEMPLATES}/{_TemplateId}")
    assert _Detail.status_code == 200, _Detail.text
    assert len(_Detail.json()["entries"]) == 1
    _Applied = requests.post(f"{MEAL_PLANS}/from-template", json={
        "template_id": _TemplateId,
        "monday_of_week": (
            _household_today()
            + timedelta(days=7 - _household_today().weekday())
        ).isoformat(),
    })
    assert _Applied.status_code == 200, _Applied.text
    assert _Applied.json()["added_count"] == 1

#endregion

#region ---------------- 7. shopping list ----------------


def test__delete_shopping_list__with_lines_and_attachments__cascade_clean(api):
    _Item = _make_item("DelInt Listed")
    _ListId = _make_list()
    _add_line(_ListId, stock_item_id=_Item["stock_item_id"])
    assert requests.post(f"{SHOPPING_LISTS}/{_ListId}/start").status_code == 204
    _Attach = requests.post(
        f"{SHOPPING_LISTS}/{_ListId}/attachments",
        json={"image_data_url": PNG_DATA_URL},
    )
    assert _Attach.status_code == 200, _Attach.text
    _AttachmentId = _Attach.json()["attachment_id"]

    assert requests.delete(f"{SHOPPING_LISTS}/{_ListId}").status_code == 204

    assert requests.get(f"{SHOPPING_LISTS}/{_ListId}").status_code == 404
    assert requests.get(
        f"{SHOPPING_LISTS}/{_ListId}/attachments/{_AttachmentId}"
    ).status_code == 404
    # No orphan child rows behind the noload relationships.
    assert _sql_count("ShoppingListLine", "shopping_list_id", _ListId) == 0
    assert _sql_count("ShoppingListAttachment", "shopping_list_id", _ListId) == 0
    # Item itself untouched.
    assert requests.get(f"{STOCK_ITEMS}/{_Item['stock_item_id']}/detail").status_code == 200
    _assert_dashboard_reads("shopping list delete")


def test__delete_shopping_list__after_finish_harvest__observation_survives_with_null_provenance(api):
    _Item = _make_item("DelInt Harvested")
    _ListId = _make_list()
    _LineId = _add_line(_ListId, stock_item_id=_Item["stock_item_id"])
    assert requests.patch(
        f"{SHOPPING_LISTS}/{_ListId}/lines/{_LineId}",
        json={"actual_unit_price": 5.0, "is_ticked": True},
    ).status_code == 204
    assert requests.post(f"{SHOPPING_LISTS}/{_ListId}/finish").status_code == 200
    _Obs = requests.get(f"{STOCK_ITEMS}/{_Item['stock_item_id']}/detail").json()["price_observations"]
    assert len(_Obs) == 1 and _Obs[0]["shopping_list_name"] is not None

    assert requests.delete(f"{SHOPPING_LISTS}/{_ListId}").status_code == 204

    # Provenance is lossy by design (FK SET NULL) — the price data point
    # must outlive the receipt that produced it.
    _Detail = requests.get(f"{STOCK_ITEMS}/{_Item['stock_item_id']}/detail")
    assert _Detail.status_code == 200, _Detail.text
    _ObsAfter = _Detail.json()["price_observations"]
    assert len(_ObsAfter) == 1
    assert _ObsAfter[0]["shopping_list_name"] is None
    _History = requests.get(f"{STOCK_ITEMS}/{_Item['stock_item_id']}/price-history")
    assert _History.status_code == 200
    assert _History.json()["sample_count"] == 1

#endregion

#region ---------------- 8. double delete ----------------


def test__delete_stock_item__twice__second_is_404(api):
    _Item = _make_item("DelInt Twice")
    assert requests.delete(f"{STOCK_ITEMS}/{_Item['stock_item_id']}").status_code == 204
    assert_problem(
        requests.delete(f"{STOCK_ITEMS}/{_Item['stock_item_id']}"), 404,
    )


def test__delete_recipe__twice__second_is_404(api):
    _Recipe = _make_recipe("DelInt Twice")
    assert requests.delete(f"{RECIPES}/{_Recipe['recipe_id']}").status_code == 204
    assert_problem(requests.delete(f"{RECIPES}/{_Recipe['recipe_id']}"), 404)


def test__delete_shopping_list__twice__second_is_404(api):
    _ListId = _make_list()
    assert requests.delete(f"{SHOPPING_LISTS}/{_ListId}").status_code == 204
    assert_problem(requests.delete(f"{SHOPPING_LISTS}/{_ListId}"), 404)


def test__delete_meal_plan__twice__second_is_404(api):
    _Plan = _make_plan()
    assert requests.delete(f"{MEAL_PLANS}/{_Plan['meal_plan_id']}").status_code == 204
    assert_problem(requests.delete(f"{MEAL_PLANS}/{_Plan['meal_plan_id']}"), 404)


def test__delete_store__twice__second_is_404(api):
    _StoreId = _make_store("DelIntTwice")
    assert requests.delete(f"{STORES}/{_StoreId}").status_code == 200
    assert_problem(requests.delete(f"{STORES}/{_StoreId}"), 404)


def test__delete_location__twice__second_is_404_on_both_routers(api):
    _Zone = requests.post(LOCATIONS, json={"name": f"DelInt Twice {uuid4().hex[:8]}", "kind": "zone"})
    assert _Zone.status_code == 201, _Zone.text
    _ZoneId = _Zone.json()["location_id"] if "location_id" in _Zone.json() else _Zone.json().get("stock_location_id")
    assert requests.delete(f"{LOCATIONS}/{_ZoneId}").status_code == 204
    assert_problem(requests.delete(f"{LOCATIONS}/{_ZoneId}"), 404)
    # The legacy router agrees the row is gone (no 500 on the miss).
    assert_problem(requests.delete(f"{STOCK_LOCATIONS}/{_ZoneId}"), 404)

#endregion

#region ---------------- 9. recipe collection ----------------


def test__delete_recipe_collection__member_recipes_unlinked_and_read_back(api):
    _Collection = requests.post(COLLECTIONS, json={"name": f"DelInt Home {uuid4().hex[:8]}"})
    assert _Collection.status_code == 201
    _CollectionId = _Collection.json()["recipe_collection_id"]
    _Recipe = _make_recipe("DelInt Member", recipe_collection_id=_CollectionId)
    assert _Recipe["recipe_collection_id"] == _CollectionId

    assert requests.delete(f"{COLLECTIONS}/{_CollectionId}").status_code == 204

    # FK is SET NULL — recipe silently drops out of the (now dead)
    # collection but keeps everything else.
    _Detail = _recipe_detail(_Recipe["recipe_id"])
    assert _Detail.status_code == 200, _Detail.text
    assert _Detail.json()["recipe_collection_id"] is None

#endregion
