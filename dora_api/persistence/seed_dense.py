"""The **dense** dev dataset — small enough to read end to end, deep enough to
walk every path (owner request, 2026-08-31).

Two dev datasets now exist and they answer different questions:

* `seed.py::seed_dev_data()` — the **load** dataset. Its curated core plus
  `DORA_SEED_BULK_ITEMS` (default 500) generated items exists so N+1s and slow
  queries surface at volume. Kept as-is; select it with `DORA_SEED_DATASET=bulk`.
* **this module** — the **depth** dataset. No generated filler at all. Every
  row is hand-placed to put some surface into a state a walker needs to see,
  and the household reads like a real one rather than "Load item 0413".

The rule that decides what belongs here: *does the app render something
different because of this row?* A second nearly-identical stocked pantry item
renders the same card as the first, so it isn't here. A stock item with **no**
group, location, expiry, product, note or history is a completely different
render (every optional block collapses) — so that item is here, deliberately,
as `bicarb`. The same reasoning gives us a recipe with ten steps, sub-steps,
two sections and per-step tool links sitting next to a recipe that is a name
and nothing else.

**What "exercise every path" means concretely.** Each block below states which
surface it feeds. The intent is that a walker can open any screen in the app
and find it non-empty *and* find its edge cases without hand-editing the DB:

    stock overview    every level x expiry x open x essential x alerts combo
    stock detail      one item with every optional block filled, one with none,
                      one whose History tab overflows the per-kind cap
    cookbook          cookable / not / at-risk / unknown, all three step modes,
                      photo and no-photo cards, a version pair, an empty
                      collection, optional + sectioned + unlinked ingredients
    cook mode         freeform, structured (10 steps, 3 with sub-steps, hints,
                      per-step ingredients + tools) and image (5 real photos)
    meal planner      a past week fully consumed, this week part-cooked with a
                      cook batch and a shortfall, a future week forked from a
                      template, plus a rotating template set
    shopping lists    draft / mid-shop / two finished, both provenance states, a
                      planned-vs-purchased store split, a budget-deferred line,
                      a receipt attachment, and price observations harvested
                      from the finished lists exactly as /finish does
    stocktake         all three confidence ranks, so Review / Walk / Tidy-up
                      each have members, plus a Sweep drop-out
    products          offer history for sparklines, an unavailable product, a
                      multipack, barcodes (product-tied, item-direct, both),
                      a price alert
    alerts + Dora     a disabled kind, read / snoozed / dismissed interactions,
                      a dismissed and a snoozed suggestion
    settings          nutrition foods with portions + a linked and an ignored
                      item, a second household member, a deactivated account

Determinism: no RNG anywhere, same as the load seed. Everything is relative to
one `now` / `today` pair so a re-seed on a different day lands the same shapes.
"""
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from dora_api.app import db
from dora_api.domain.entities.app_setting import (BUDGET_PERIOD_WEEKLY,
                                                  NUTRITION_MODE_COMPLEX)
from dora_api.domain.entities.consumption_event import (
    CONSUMPTION_SOURCE_COOK, CONSUMPTION_SOURCE_MANUAL, ConsumptionEvent)
from dora_api.domain.entities.cook_batch import CookBatch
from dora_api.domain.entities.cook_event import CookEvent
from dora_api.domain.entities.dora_suggestion_suppression import (
    SUPPRESSION_DECISION_DISMISSED, SUPPRESSION_DECISION_SNOOZED,
    DoraSuggestionSuppression)
from dora_api.domain.entities.meal_plan import MealPlan
from dora_api.domain.entities.meal_plan_entry import MealPlanEntry
from dora_api.domain.entities.meal_plan_template import (
    MealPlanTemplate, MealPlanTemplateEntry, MealPlanTemplateSet,
    MealPlanTemplateSetItem)
from dora_api.domain.entities.nutrition_food import (
    NUTRITION_SOURCE_OFF, NUTRITION_SOURCE_USDA_FOUNDATION, NutritionFood)
from dora_api.domain.entities.nutrition_portion import NutritionPortion
from dora_api.domain.entities.recipe_collection import RecipeCollection
from dora_api.domain.entities.shopping_list import (
    SHOPPING_LIST_STATUS_DONE, SHOPPING_LIST_STATUS_SHOPPING, ShoppingList)
from dora_api.domain.entities.shopping_list_template import (
    ShoppingListTemplate, ShoppingListTemplateLine)
from dora_api.domain.entities.stock_group import StockGroup
from dora_api.domain.entities.stock_item_expiry_event import (
    EXPIRY_EVENT_PUSHED, EXPIRY_EVENT_SET, StockItemExpiryEvent)
from dora_api.domain.entities.stock_item_waste_event import StockItemWasteEvent
from dora_api.domain.entities.stock_level import StockLevel
from dora_api.domain.entities.stock_location import (LOCATION_KIND_AREA,
                                                     LOCATION_KIND_SECTION,
                                                     LOCATION_KIND_ZONE,
                                                     StockLocation)
from dora_api.domain.entities.store import Store
from dora_api.domain.entities.user import THEME_PESTO, User
from dora_api.features.alerts.alert_key import stock_alert_key
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.features.recipes.recipe_section_access import (
    SectionWrite, replace_sections_for_recipe)
from dora_api.features.recipes.recipe_step_access import (
    StepWrite, replace_steps_for_recipe)
from dora_api.features.recipes.recipe_step_image_access import (
    StepImageWrite, replace_step_images_for_recipe)
from dora_api.features.substitutes.canonical import canonical_pair
from dora_api.infrastructure.auth_helpers import hash_password
from dora_api.persistence.seed_builders import SeedBuilders
from dora_api.persistence.seed_dense_images import (FOCACCIA_STEP_IMAGES,
                                                    RECEIPT_PHOTO)
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


def seed_dense_data(qa_fixtures: bool = False, money_on: bool = True):
    """Populate the dense dataset. See the module docstring for the shape.

    ``money_on`` (default **True**, unlike the load seed) turns on the
    install-wide optional surfaces — money + budget, nutrition, scanning, cook
    batches. A gated-off feature renders nothing, and a dataset whose whole
    purpose is "show me every path" that boots with four surfaces invisible is
    not doing its job. Pass ``False`` to boot the same data with money off and
    see the no-dollars rendering (the flags are read once at cold mount, so
    this has to be a boot-time choice — FU-592).

    ``qa_fixtures`` appends the same deterministic buy-verdict fixture the load
    seed builds, so the Playwright specs pass against either dataset.
    """
    repo = SqlAlchemyRepository()
    now = datetime.now(UTC)
    today = date.today()  # R-021 carve-out: dev fixture, server-local date is fine
    monday = today - timedelta(days=today.weekday())

    # Same autoflush choreography as the load seed: children are constructed
    # before their parents exist so they can be linked by object, and an
    # autoflush in that gap would try to insert with a null FK.
    db.session.autoflush = False

    builders = SeedBuilders(repo, now)
    make_product = builders.make_product
    make_item = builders.make_item
    level_change = builders.level_change
    price_obs = builders.price_obs
    ingredient = builders.ingredient
    unlinked = builders.unlinked_ingredient
    make_recipe = builders.make_recipe
    line = builders.make_line

    # ══ STORES ═══════════════════════════════════════════════════════════
    # Four, because the shopping list's planned-vs-purchased store split and
    # the price-observation store chip both need more than a token second one.
    woolworths = Store(name="Woolworths", brand_colour="#178841")
    coles = Store(name="Coles", brand_colour="#E01A22")
    aldi = Store(name="Aldi", brand_colour="#00285E")
    # No brand colour — the store chip's derived-initial fallback (_logo_colour)
    # only renders for a store that has neither logo nor colour.
    farmers = Store(name="Northside Farmers Market")
    for store in (woolworths, coles, aldi, farmers):
        repo.add(store)

    # ══ USERS ════════════════════════════════════════════════════════════
    # Three accounts so the admin Users page has all three of its states:
    # the admin you're signed in as, an active non-admin housemate, and a
    # deactivated ex-housemate (is_active=False — the "door locked, not
    # deleted" case, which is otherwise only reachable by deactivating
    # someone mid-walk).
    owner = User(
        email="dora@example.com",
        password_hash=hash_password("dora"),
        send_deals_on_day=5,
        username="dora",
        is_admin=True,
        onboarding_completed_at=now - timedelta(days=120),
        email_verified=True,
        theme=THEME_PESTO,
        # The three inference overlays default OFF (they annotate pages you
        # opened for another reason). On here, because the dataset below
        # deliberately builds a recipe Dora thinks is at risk and one she
        # thinks is cookable after all — with these off, both fixtures are
        # invisible and the seed silently wastes its own work (FU-653).
        inference_recipes_enabled=True,
        inference_shopping_enabled=True,
        inference_meal_plan_enabled=True,
        stocktake_last_session_at=now - timedelta(days=10),
    )
    housemate = User(
        email="sam@example.com",
        password_hash=hash_password("dora"),
        send_deals_on_day=6,
        username="sam",
        is_admin=False,
        onboarding_completed_at=now - timedelta(days=40),
        email_verified=True,
    )
    former = User(
        email="alex@example.com",
        password_hash=hash_password("dora"),
        send_deals_on_day=0,
        username="alex",
        is_admin=False,
        is_active=False,
        onboarding_completed_at=now - timedelta(days=300),
    )
    for user in (owner, housemate, former):
        repo.add(user)

    # ══ LOCATIONS ════════════════════════════════════════════════════════
    # A full three-level tree (zone → area → section) on one branch and a
    # bare zone on another, so the locations page shows both a deep and a
    # flat arrangement. `garage` stays EMPTY on purpose — a location with no
    # items is its own render and the only way to see it is to seed one.
    pantry = StockLocation(name="Pantry", kind=LOCATION_KIND_ZONE, sequence=0)
    fridge = StockLocation(name="Fridge", kind=LOCATION_KIND_ZONE, sequence=1)
    freezer = StockLocation(name="Freezer", kind=LOCATION_KIND_ZONE, sequence=2)
    garage = StockLocation(name="Garage shelf", kind=LOCATION_KIND_ZONE, sequence=3)
    for loc in (pantry, fridge, freezer, garage):
        repo.add(loc)
    repo.save_changes()  # children FK to these ids

    top_shelf = StockLocation(name="Top shelf", kind=LOCATION_KIND_AREA,
                              parent_id=pantry.id, sequence=0)
    middle_shelf = StockLocation(name="Middle shelf", kind=LOCATION_KIND_AREA,
                                 parent_id=pantry.id, sequence=1)
    door = StockLocation(name="Door", kind=LOCATION_KIND_AREA,
                         parent_id=fridge.id, sequence=0)
    crisper = StockLocation(name="Crisper drawer", kind=LOCATION_KIND_AREA,
                            parent_id=fridge.id, sequence=1)
    for loc in (top_shelf, middle_shelf, door, crisper):
        repo.add(loc)
    repo.save_changes()

    spice_rack = StockLocation(name="Spice rack", kind=LOCATION_KIND_SECTION,
                               parent_id=middle_shelf.id, sequence=0)
    baking_box = StockLocation(name="Baking box", kind=LOCATION_KIND_SECTION,
                               parent_id=middle_shelf.id, sequence=1)
    for loc in (spice_rack, baking_box):
        repo.add(loc)

    # ══ LEVELS + GROUPS ══════════════════════════════════════════════════
    stocked = StockLevel(name="Stocked", sequence=0)
    low = StockLevel(name="Low Stock", sequence=1)
    out = StockLevel(name="Out of Stock", sequence=2)
    for lvl in (stocked, low, out):
        repo.add(lvl)

    g_fruit = StockGroup(name="Fruit & Veg")
    g_dairy = StockGroup(name="Dairy & Eggs")
    g_pantry = StockGroup(name="Pantry staples")
    g_frozen = StockGroup(name="Frozen")
    g_meat = StockGroup(name="Meat & Seafood")
    g_baking = StockGroup(name="Baking")
    for grp in (g_fruit, g_dairy, g_pantry, g_frozen, g_meat, g_baking):
        repo.add(grp)

    # ══ PRODUCTS ═════════════════════════════════════════════════════════
    # Twelve, each with a *reason*: a two-store price race, a deep discount,
    # a slow climb, a multipack, one that's been delisted, one nobody has
    # linked to a stock item. `history` drives the detail-page sparkline, so
    # each list is shaped (falling / rising / flat / spiky) rather than random.
    milk_woolies = make_product(
        store=woolworths, name="Woolworths Full Cream Milk 2L", brand="Woolworths",
        size="2L", size_unit="L", size_value=2.0, stockcode="W-MILK-2L",
        price_now=3.10, price_was=3.10,
        history=[(28, 3.30, 3.30), (21, 3.30, 3.30), (14, 3.10, 3.30), (7, 3.10, 3.10)],
    )
    milk_coles = make_product(
        store=coles, name="Coles Full Cream Milk 2L", brand="Coles",
        size="2L", size_unit="L", size_value=2.0, stockcode="C-MILK-2L",
        price_now=2.90, price_was=3.30,
        history=[(28, 3.30, 3.30), (14, 3.30, 3.30), (7, 2.90, 3.30)],
    )
    eggs_woolies = make_product(
        store=woolworths, name="Woolworths Free Range Eggs 12pk", brand="Woolworths",
        size="700g", size_unit="g", size_value=700.0, stockcode="W-EGG-12",
        price_now=5.50, price_was=6.20,
        history=[(30, 6.20, 6.20), (15, 5.90, 6.20), (5, 5.50, 6.20)],
    )
    # Owner-reported 2026-09-03: "3 yolks" of this item priced at $16.50. The
    # product says "12pk" in its *name* and nowhere a query can read it, so the
    # cost estimator had nothing to divide by and (before the same day's fix)
    # billed three whole cartons. `pack_count` is where that fact belongs —
    # with it, a recipe calling for 3 eggs costs 3 × $0.46. Same idiom as the
    # yoghurt multipack below.
    eggs_woolies.pack_count = 12
    flour_coles = make_product(
        store=coles, name="Coles Plain Flour 1kg", brand="Coles",
        size="1kg", size_unit="kg", size_value=1.0, stockcode="C-FLOUR-1KG",
        price_now=2.20, price_was=2.20,
        history=[(60, 1.80, 1.80), (40, 1.95, 1.95), (20, 2.10, 2.10)],  # slow climb
    )
    pasta_barilla = make_product(
        store=coles, name="Barilla Spaghetti No.5 500g", brand="Barilla",
        size="500g", size_unit="g", size_value=500.0, stockcode="C-PASTA-500",
        price_now=1.50, price_was=3.00,  # 50% off — the deep-discount card
        history=[(30, 3.00, 3.00), (20, 2.50, 3.00), (10, 1.50, 3.00), (2, 1.50, 3.00)],
    )
    oil_aldi = make_product(
        store=aldi, name="Aldi Extra Virgin Olive Oil 1L", brand="Vialli",
        size="1L", size_unit="L", size_value=1.0, stockcode="A-OIL-1L",
        price_now=7.99, price_was=9.99,
        history=[(25, 9.99, 9.99), (12, 8.99, 9.99), (3, 7.99, 9.99)],
    )
    passata_aldi = make_product(
        store=aldi, name="Aldi Tomato Passata 700g", brand="Cucina",
        size="700g", size_unit="g", size_value=700.0, stockcode="A-PASS-700",
        price_now=1.35, price_was=1.35,
        history=[(45, 1.45, 1.45), (25, 1.35, 1.45), (8, 1.35, 1.35)],
    )
    parmesan_coles = make_product(
        store=coles, name="Coles Parmesan Wedge 200g", brand="Coles",
        size="200g", size_unit="g", size_value=200.0, stockcode="C-PARM-200",
        price_now=6.00, price_was=6.00,
        history=[(20, 6.50, 6.50), (8, 6.00, 6.50)],
    )
    # Multipack — `pack_count` is what makes the observation list render
    # "6 x 170g" instead of a single 1.02kg lump.
    yoghurt_woolies = make_product(
        store=woolworths, name="Chobani Greek Yoghurt 6x170g", brand="Chobani",
        size="1.02kg", size_unit="g", size_value=1020.0, stockcode="W-YOG-6PK",
        price_now=7.50, price_was=9.00,
        history=[(35, 9.00, 9.00), (18, 8.00, 9.00), (4, 7.50, 9.00)],
    )
    yoghurt_woolies.pack_count = 6
    coffee_farmers = make_product(
        store=farmers, name="Local Roast Coffee Beans 1kg", brand="Sideways Roasters",
        size="1kg", size_unit="kg", size_value=1.0, stockcode="F-COFFEE-1KG",
        price_now=32.00, price_was=38.00,
        history=[(40, 38.00, 38.00), (20, 35.00, 38.00), (5, 32.00, 38.00)],
    )
    # Delisted — is_active False + is_available False is the "this product is
    # gone" render, which nothing else in either dataset produces. Still linked
    # to a stock item, because that's the state that actually causes trouble.
    bread_discontinued = make_product(
        store=woolworths, name="Woolworths Sourdough Cob (discontinued)",
        brand="Woolworths", size="600g", size_unit="g", size_value=600.0,
        stockcode="W-SOUR-600", price_now=5.50, price_was=5.50,
        history=[(90, 4.90, 4.90), (60, 5.20, 5.20), (30, 5.50, 5.50)],
    )
    bread_discontinued.is_active = False
    bread_discontinued.is_available = False
    # Unlinked to any stock item — the products list needs a row that isn't
    # reachable from the pantry, which is how most of a real catalogue looks.
    _stray = make_product(
        store=aldi, name="Aldi Choceur Dark 70% 100g", brand="Choceur",
        size="100g", size_unit="g", size_value=100.0, stockcode="A-CHOC-100",
        price_now=2.29, price_was=2.99,
        history=[(22, 2.99, 2.99), (6, 2.29, 2.99)],
    )

    # ══ NUTRITION FOODS ══════════════════════════════════════════════════
    # Complex-mode needs cached foods + portion rows to convert "1 onion" or
    # "2 cups flour" into grams. Three foods: one whole food with two portion
    # rows (the convertible case), one with NO portion rows (the "not
    # convertible, reported honestly in the coverage line" case), and one
    # packaged good from Open Food Facts reached by barcode.
    food_egg = NutritionFood(
        source=NUTRITION_SOURCE_USDA_FOUNDATION, source_ref="748967",
        name="Egg, whole, raw, fresh", kcal_per_100g=143.0,
        protein_g_per_100g=12.6, carbs_g_per_100g=0.7, sugars_g_per_100g=0.4,
        fat_g_per_100g=9.5, saturated_fat_g_per_100g=3.1, fibre_g_per_100g=0.0,
        sodium_mg_per_100g=142.0, cholesterol_mg_per_100g=372.0,
        calcium_mg_per_100g=56.0, iron_mg_per_100g=1.8,
        vitamin_a_ug_per_100g=160.0, vitamin_d_ug_per_100g=2.0,
        vitamin_b12_ug_per_100g=1.1,
    )
    food_flour = NutritionFood(
        source=NUTRITION_SOURCE_USDA_FOUNDATION, source_ref="789890",
        name="Flour, wheat, all-purpose, enriched, bleached",
        kcal_per_100g=364.0, protein_g_per_100g=10.3, carbs_g_per_100g=76.3,
        sugars_g_per_100g=0.3, fat_g_per_100g=1.0, saturated_fat_g_per_100g=0.2,
        fibre_g_per_100g=2.7, sodium_mg_per_100g=2.0, iron_mg_per_100g=4.6,
    )
    food_yoghurt = NutritionFood(
        source=NUTRITION_SOURCE_OFF, source_ref="9300601234567",
        name="Greek Yoghurt, natural", brand="Chobani",
        barcode="9300601234567", kcal_per_100g=97.0, protein_g_per_100g=9.0,
        carbs_g_per_100g=4.0, sugars_g_per_100g=4.0, fat_g_per_100g=5.0,
        saturated_fat_g_per_100g=3.2, sodium_mg_per_100g=36.0,
        calcium_mg_per_100g=110.0,
    )
    for food in (food_egg, food_flour, food_yoghurt):
        repo.add(food)
    repo.save_changes()  # portions + item links FK to these ids

    for _food, _portions in (
        (food_egg, [(1.0, "large", 50.0), (1.0, "extra large", 56.0)]),
        (food_flour, [(1.0, "cup", 125.0), (1.0, "tbsp", 7.8)]),
        # food_yoghurt gets none — the not-convertible case.
    ):
        for amount, measure, grams in _portions:
            repo.add(NutritionPortion(
                nutrition_food_id=_food.id, amount=amount,
                measure=measure, gram_weight=grams,
            ))

    # ══ STOCK ITEMS ══════════════════════════════════════════════════════
    # The two poles first, because they're the point of this dataset.

    # ── Pole 1: NOTHING. Name + level, and that is the entire row. No group,
    # no location, no expiry, no note, no product, no history, no alerts. Every
    # optional block on the detail page collapses; the overview row shows its
    # minimum. Neither of the other datasets contains an item like this, so
    # "what does an empty item look like?" has never been answerable.
    bicarb = make_item(name="Bicarb Soda", group=None, level=stocked, location=None)

    # ── Pole 2: EVERYTHING. Group, deepest location, notes, expiry, essential,
    # opened, stocktake alerts on, checked recently, a usual store, two linked
    # products across two stores. Below it also collects: substitutes, preferred
    # buys, a barcode, four price observations, level-change history, waste,
    # cook and consumption events. If a block exists on the stock-item page,
    # this item fills it.
    olive_oil = make_item(
        name="Extra Virgin Olive Oil", group=g_pantry, level=low, location=top_shelf,
        notes=("Vialli from Aldi is the everyday one. The tin from the farmers "
               "market is for salads only. Decant into the small bottle by the "
               "stove; the tin lives up here."),
        expiry=today + timedelta(days=120), flagged=True, is_open=True,
        opened_on=today - timedelta(days=20), stocktake_alerts=True,
        updated_days_ago=6, last_checked_at=now - timedelta(days=6),
        usual_store_id=aldi.id, products=[oil_aldi],
    )

    # ── The expiry matrix. One item per state, so the overview's expiry chip
    # and the expiring-soon alert have every band represented at once.
    milk = make_item(name="Full Cream Milk", group=g_dairy, level=low, location=door,
                     expiry=today + timedelta(days=2), is_open=True,
                     opened_on=today - timedelta(days=2), updated_days_ago=1,
                     usual_store_id=coles.id, products=[milk_woolies, milk_coles])
    spinach = make_item(name="Baby Spinach", group=g_fruit, level=low, location=crisper,
                        expiry=today, notes="Use it or lose it.")  # expires TODAY
    ricotta = make_item(name="Ricotta", group=g_dairy, level=stocked, location=fridge,
                        expiry=today - timedelta(days=3),  # already EXPIRED
                        is_open=True, opened_on=today - timedelta(days=9))
    rice = make_item(name="Jasmine Rice", group=g_pantry, level=stocked,
                     location=middle_shelf,
                     expiry=today + timedelta(days=400))  # far future
    # (bicarb above covers "no expiry at all")

    # ── The essential / alert / snooze matrix.
    eggs = make_item(name="Free Range Eggs", group=g_dairy, level=stocked,
                     location=fridge, flagged=True, products=[eggs_woolies],
                     nutrition_food_id=food_egg.id, updated_days_ago=3)
    bread = make_item(name="Sourdough Loaf", group=g_pantry, level=out, location=None,
                      flagged=True, products=[bread_discontinued],
                      notes="Bakery one on Saturdays; the Woolies cob got delisted.")
    butter = make_item(name="Butter", group=g_dairy, level=stocked, location=fridge,
                       is_open=True, opened_on=today - timedelta(days=5),
                       flagged=True)
    # Alerts on, never checked — `last_checked_at` NULL falls back to the level
    # timestamp, which is the branch the stocktake baseline COALESCE exists for.
    chilli_flakes = make_item(name="Chilli Flakes", group=g_pantry, level=low,
                              location=spice_rack, stocktake_alerts=True,
                              updated_days_ago=26)
    # Alerts on but SNOOZED — in the queue's data, out of the queue's view.
    fish_sauce = make_item(name="Fish Sauce", group=g_pantry, level=stocked,
                           location=spice_rack, stocktake_alerts=True,
                           updated_days_ago=40,
                           snoozed_until=now + timedelta(days=9))
    # Nutrition explicitly ignored — a different state from "not linked yet",
    # and the only one that proves the opt-out sticks.
    stock_cubes = make_item(name="Stock Cubes", group=g_pantry, level=stocked,
                            location=middle_shelf, nutrition_ignored=True)

    # ── The rest of a working pantry. Enough to make recipes cookable and the
    # groups non-trivial, no more.
    flour = make_item(name="Plain Flour", group=g_baking, level=stocked,
                      location=baking_box, products=[flour_coles],
                      nutrition_food_id=food_flour.id)
    yeast = make_item(name="Dried Yeast", group=g_baking, level=stocked,
                      location=baking_box, expiry=today + timedelta(days=60))
    sugar = make_item(name="Caster Sugar", group=g_baking, level=stocked,
                      location=baking_box)
    salt = make_item(name="Flaky Sea Salt", group=g_pantry, level=stocked,
                     location=spice_rack)
    rosemary = make_item(name="Rosemary", group=g_fruit, level=stocked, location=None,
                         notes="The bush by the back door.")
    pasta = make_item(name="Spaghetti", group=g_pantry, level=stocked,
                      location=middle_shelf, products=[pasta_barilla])
    passata = make_item(name="Passata", group=g_pantry, level=stocked,
                        location=middle_shelf, products=[passata_aldi],
                        updated_days_ago=10, stocktake_alerts=True)
    garlic = make_item(name="Garlic", group=g_fruit, level=stocked, location=pantry)
    onions = make_item(name="Brown Onions", group=g_fruit, level=stocked, location=pantry)
    carrots = make_item(name="Carrots", group=g_fruit, level=stocked, location=crisper,
                        expiry=today + timedelta(days=12))
    celery = make_item(name="Celery", group=g_fruit, level=low, location=crisper,
                       expiry=today + timedelta(days=5))
    # Low, not Out: the ten-step Sunday Ragu is the recipe you most want to
    # actually walk in cook mode, and one Out ingredient makes it unenterable.
    # Its stocked→low history is still seeded below, and the →out leg lives on
    # the bread instead, so no transition is lost.
    parmesan = make_item(name="Parmesan", group=g_dairy, level=low, location=fridge,
                         products=[parmesan_coles])
    mince = make_item(name="Beef Mince", group=g_meat, level=stocked, location=freezer,
                      notes="500g blocks, frozen flat.")
    pancetta = make_item(name="Pancetta", group=g_meat, level=stocked, location=fridge)
    # Two Out cheeses that exist to block exactly one recipe each — a recipe
    # that can't be cooked is its own render and needs a real reason, not a
    # staple knocked out for the sake of it.
    pecorino = make_item(name="Pecorino Romano", group=g_dairy, level=out,
                         location=fridge)
    tasty_cheese = make_item(name="Tasty Cheese", group=g_dairy, level=out,
                             location=fridge, flagged=True)
    chicken = make_item(name="Chicken Thighs", group=g_meat, level=stocked, location=freezer)
    peas = make_item(name="Frozen Peas", group=g_frozen, level=stocked, location=freezer,
                     is_open=True, opened_on=today - timedelta(days=30))
    icecream = make_item(name="Vanilla Ice Cream", group=g_frozen, level=low,
                         location=freezer, is_open=True,
                         opened_on=today - timedelta(days=14),
                         expiry=today + timedelta(days=200))
    yoghurt = make_item(name="Greek Yoghurt", group=g_dairy, level=stocked,
                        location=fridge, products=[yoghurt_woolies],
                        nutrition_food_id=food_yoghurt.id,
                        expiry=today + timedelta(days=11))
    coffee = make_item(name="Coffee Beans", group=g_pantry, level=stocked,
                       location=top_shelf, flagged=True, is_open=True,
                       opened_on=today - timedelta(days=3),
                       usual_store_id=farmers.id, products=[coffee_farmers])
    soy = make_item(name="Soy Sauce", group=g_pantry, level=stocked, location=spice_rack)
    # The chatty-history item: seeded below with 65 expiry pushes, which is past
    # the per-kind cap (50) so the History tab's "N older events not shown"
    # footer fires on exactly one item without contaminating the rest.
    sriracha = make_item(
        name="Sriracha", group=g_pantry, level=stocked, location=door,
        is_open=True, opened_on=today - timedelta(days=90),
        expiry=today + timedelta(days=15),
        notes="Been in the door for a year and keeps getting a new date written on it.",
    )

    repo.save_changes()  # everything below FKs to stock-item ids

    # ══ BARCODES ═════════════════════════════════════════════════════════
    # All three shapes of the hybrid model, which no other seed produces:
    # product-tied, stock-item-direct (a raw EAN registered without bothering
    # with the products overlay), and both at once.
    barcode_table = db.metadata.tables["Barcode"]
    db.session.execute(barcode_table.insert(), [
        {"id": uuid4(), "barcode": "9300675024235",
         "product_id": milk_coles.id, "stock_item_id": None, "created_at": now},
        {"id": uuid4(), "barcode": "9310072020304",
         "product_id": None, "stock_item_id": stock_cubes.id, "created_at": now},
        {"id": uuid4(), "barcode": "4088600123456",
         "product_id": None, "stock_item_id": olive_oil.id,
         "created_at": now - timedelta(days=40)},
        {"id": uuid4(), "barcode": "9300601234567",
         "product_id": yoghurt_woolies.id, "stock_item_id": yoghurt.id,
         "created_at": now},
    ])

    # ══ PREFERRED BUYS ═══════════════════════════════════════════════════
    # The everyday-user counterpart to the products overlay. One item with a
    # single label, one with three (the list has to sort them), the rest with
    # none — which is the realistic distribution and the one that shows the
    # empty state next to the populated one.
    preferred_table = db.metadata.tables["PreferredBuy"]
    _preferred_rows = [
        (olive_oil, "Vialli EVOO 1L tin"),
        (bread, "Bakers Delight white sourdough"),
        (bread, "Woolies cob (if the bakery's out)"),
        (bread, "Anything seeded, not rye"),
        (coffee, "Sideways Roasters house blend, whole bean"),
    ]
    # `_preferred_ids` keeps the id of each item's FIRST label — that's the one
    # a shopping-list line points at via `preferred_buy_id` further down, so the
    # hint on the list reads as the buy you'd reach for by default rather than
    # whichever fallback happened to be inserted last.
    _preferred_ids: dict[str, object] = {}
    _preferred_inserts = []
    for _item, _label in _preferred_rows:
        _pid = uuid4()
        _preferred_ids.setdefault(_item.name, _pid)
        _preferred_inserts.append({
            "id": _pid, "stock_item_id": _item.id, "label": _label,
            "created_at": now - timedelta(days=30),
        })
    db.session.execute(preferred_table.insert(), _preferred_inserts)

    # ══ SUBSTITUTES ══════════════════════════════════════════════════════
    # Undirected pairs, written through the canonical ordering helper so the
    # rows match what the API would have written (R-017). Across the five:
    # a note without a ratio, a ratio without a note, both together, and
    # neither — every shape the substitute surfaces have to render.
    #
    # The **ratio is directional** (`_x` → `_y`) while the *row* is stored in
    # canonical id order, so it has to be flipped whenever `canonical_pair`
    # reverses the pair. The read side (`get_stock_item_detail`) flips it back
    # for whichever item you asked about; writing it un-flipped here would seed
    # every ratio backwards on roughly half the pairs, at random, depending on
    # how the uuid4()s sorted.
    substitute_table = db.metadata.tables["StockItemSubstitute"]
    _raw_pairs = [
        # (from, to, notes, ratio as (qty_from, unit_from, qty_to, unit_to))
        (olive_oil.id, butter.id, "Fine for frying, not for dressing",
         (1, "tbsp", 1, "tbsp")),
        (pasta.id, rice.id, "Carb base", (100, "g", 75, "g")),
        (parmesan.id, ricotta.id, None, (20, "g", 40, "g")),
        (mince.id, chicken.id, None, None),
        (yoghurt.id, ricotta.id, "In the bake, not on the granola", None),
    ]
    _seen: set[tuple] = set()
    _rows: list[dict] = []
    for _x, _y, _notes, _ratio in _raw_pairs:
        _a, _b = canonical_pair(_x, _y)
        if (_a, _b) in _seen:
            continue
        _seen.add((_a, _b))
        _row = {"stock_item_a_id": _a, "stock_item_b_id": _b,
                "notes": _notes, "created_at": now,
                "ratio_quantity_in": None, "ratio_unit_in": None,
                "ratio_quantity_out": None, "ratio_unit_out": None}
        if _ratio is not None:
            _qf, _uf, _qt, _ut = _ratio
            if _a != _x:
                _qf, _uf, _qt, _ut = _qt, _ut, _qf, _uf
            _row.update(ratio_quantity_in = _qf, ratio_unit_in = _uf,
                        ratio_quantity_out = _qt, ratio_unit_out = _ut)
        _rows.append(_row)
    db.session.execute(substitute_table.insert(), _rows)

    # ══ LEVEL-CHANGE HISTORY ═════════════════════════════════════════════
    # Every 3-band transition at least once: a full stocked→low→out slide, a
    # low→stocked restock, and a stocked→stocked refresh after a shop (which
    # is a real event even though the band didn't move).
    level_change(milk, stocked, 9)
    level_change(milk, low, 1)
    level_change(parmesan, stocked, 14)
    level_change(parmesan, low, 6)
    level_change(tasty_cheese, low, 8)
    level_change(tasty_cheese, out, 2)
    level_change(bread, low, 5)
    level_change(bread, out, 2)
    level_change(olive_oil, stocked, 30)
    level_change(olive_oil, low, 6)
    level_change(pasta, stocked, 12)
    level_change(pasta, stocked, 3)
    level_change(celery, stocked, 11)
    level_change(celery, low, 2)
    level_change(icecream, low, 4)

    # ══ PRICE OBSERVATIONS ═══════════════════════════════════════════════
    # The "your prices" widget has four distinct renders and this covers all
    # four on purpose: baseline-ready (>= MIN_SAMPLES), below-min (the "not
    # enough yet" copy), a latest above 1.15x the median (the above-usual
    # chip), and a store-tagged vs untagged split. Units span measure (L, ml,
    # g), count (ea) and a multipack.
    # Milk — 4 obs, store-tagged, baseline ~ $2.00/L, latest at baseline.
    price_obs(milk, total_price=4.20, total_measure=2.0, unit="L", days_ago=42, store=woolworths)
    price_obs(milk, total_price=2.00, total_measure=1.0, unit="L", days_ago=21, store=coles)
    price_obs(milk, total_price=4.10, total_measure=2.0, unit="L", days_ago=10, store=woolworths)
    price_obs(milk, total_price=2.00, total_measure=1.0, unit="L", days_ago=2, store=coles)
    # Olive oil — latest is 40% over the median → the above-usual chip.
    price_obs(olive_oil, total_price=8.00, total_measure=500.0, unit="ml", days_ago=120)
    price_obs(olive_oil, total_price=9.00, total_measure=500.0, unit="ml", days_ago=80)
    price_obs(olive_oil, total_price=8.50, total_measure=500.0, unit="ml", days_ago=40)
    price_obs(olive_oil, total_price=12.00, total_measure=500.0, unit="ml", days_ago=3)
    # Eggs — 3 obs in the count dimension.
    price_obs(eggs, total_price=7.50, total_measure=12.0, unit="ea", days_ago=30, store=woolworths)
    price_obs(eggs, total_price=8.00, total_measure=12.0, unit="ea", days_ago=14, store=coles)
    price_obs(eggs, total_price=7.50, total_measure=12.0, unit="ea", days_ago=5, store=woolworths)
    # Yoghurt — the multipack render ("6 x 170g").
    price_obs(yoghurt, total_price=7.50, total_measure=1020.0, unit="g",
              days_ago=18, store=woolworths, pack_count=6)
    price_obs(yoghurt, total_price=8.00, total_measure=1020.0, unit="g",
              days_ago=4, store=woolworths, pack_count=6)
    # Coffee — a single observation: enough for a current-price chip, not
    # enough for a baseline. The below-MIN_SAMPLES empty state.
    price_obs(coffee, total_price=32.00, total_measure=1.0, unit="kg", days_ago=7, store=farmers)

    # ══ RECIPE COLLECTIONS + VOCABULARIES ════════════════════════════════
    weeknight = RecipeCollection(name="Weeknight dinners")
    weekend = RecipeCollection(name="Weekend cooking")
    to_try = RecipeCollection(name="To try")
    # Empty on purpose — a collection with no recipes is its own render, and
    # nothing else in the dataset produces one.
    christmas = RecipeCollection(name="Christmas")
    for coll in (weeknight, weekend, to_try, christmas):
        repo.add(coll)

    builders.seed_vocabularies()
    tools = builders.tools
    dietary_tags = builders.dietary_tags

    # ══ RECIPES ══════════════════════════════════════════════════════════
    # Fourteen. Between them they cover all three step modes, all three
    # difficulties, all five meal slots, cookable / not-cookable / at-risk /
    # unknown, sectioned + optional + unlinked ingredients, a version pair, a
    # recipe with a photo and one with nothing but a name.

    # ── THE STRUCTURED ONE. Ten top-level steps, three of which have
    # sub-steps, two named sections, hints on the steps where a hint is
    # actually useful, and per-step ingredient + tool links. This is the
    # fixture the structured cook-mode face and the step editor have never
    # had (FU-754) — everything else in both seeds is a freeform blob.
    ragu_ings = {
        "oil": ingredient(olive_oil, 2, "tbsp"),
        "pancetta": ingredient(pancetta, 100, "g", notes="diced"),
        "onion": ingredient(onions, 1, "whole", notes="finely diced"),
        "carrot": ingredient(carrots, 1, "whole", notes="finely diced"),
        "celery": ingredient(celery, 2, "sticks", notes="finely diced"),
        "garlic": ingredient(garlic, 3, "cloves"),
        "mince": ingredient(mince, 500, "g"),
        "passata": ingredient(passata, 700, "g"),
        "milk": ingredient(milk, 200, "ml", notes="whole, warmed"),
        "pasta": ingredient(pasta, 400, "g"),
        "parmesan": ingredient(parmesan, 60, "g", notes="finely grated"),
        # Optional — the cookability rule ignores these, which is only
        # visible if a recipe has one whose item is Out.
        "chilli": ingredient(chilli_flakes, 1, "pinch", notes="if you like heat"),
    }
    ragu_ings["chilli"].is_optional = True
    ragu = make_recipe(
        name="Sunday Ragu", collection=weekend, cuisine="Italian", category="Pasta",
        favourite=True, difficulty="Medium", cook=180, prep=25, servings=6,
        kcal=680, time_of_day="Dinner", steps_mode="structured",
        last_made=(now - timedelta(days=11)).date(),
        source="https://example.com/sunday-ragu",
        notes=("Three hours is not negotiable. At two it tastes like bolognese. "
               "Double it and freeze half; it's better the second week."),
        ingredients=list(ragu_ings.values()),
        # The freeform blob is kept even though `steps_mode` is 'structured'.
        # All three payloads are allowed to coexist (the mode only declares
        # which one renders), and a recipe carrying two of them is exactly the
        # case the non-destructive mode switch was built for.
        instructions=("Soffritto, brown the mince, add passata, simmer three "
                      "hours, finish with milk and parmesan."),
        created_at=now - timedelta(days=200),
    )

    # ── THE IMAGE ONE. Five real photos, in order (FU-754's other half).
    focaccia_ings = [
        ingredient(flour, 500, "g"),
        ingredient(yeast, 7, "g"),
        ingredient(salt, 10, "g"),
        ingredient(olive_oil, 60, "ml"),
        ingredient(rosemary, 3, "sprigs"),
    ]
    focaccia = make_recipe(
        name="Weekend Focaccia", collection=weekend, cuisine="Italian",
        category="Bread", difficulty="Medium", cook=25, prep=180, servings=8,
        kcal=310, time_of_day="Snack", steps_mode="image", favourite=True,
        ingredients=focaccia_ings,
        instructions="See the photos.",
        notes="The overnight fridge rise is worth it. Don't skimp on the oil.",
        created_at=now - timedelta(days=90),
    )
    # A hero photo on one recipe and not the others — the cookbook card has a
    # photo render and a no-photo render, and both need to be on screen at once.
    focaccia.image = FOCACCIA_STEP_IMAGES[-1].encode("utf-8")

    # ── Freeform, cookable now. The everyday case.
    aglio = make_recipe(
        name="Spaghetti Aglio e Olio", collection=weeknight, cuisine="Italian",
        category="Pasta", difficulty="Easy", cook=15, prep=5, servings=2,
        kcal=520, favourite=True, last_made=(now - timedelta(days=3)).date(),
        ingredients=[
            ingredient(pasta, 250, "g"),
            ingredient(garlic, 4, "cloves", notes="thinly sliced"),
            ingredient(olive_oil, 60, "ml"),
            ingredient(chilli_flakes, 1, "pinch"),
        ],
        instructions=(
            "1. Boil a large pot of well-salted water and cook the spaghetti "
            "until al dente.\n"
            "2. Meanwhile, warm the olive oil with the sliced garlic over a low "
            "heat until it just turns blond, three or four minutes. Add the "
            "chilli flakes off the heat.\n"
            "3. Toss the drained pasta through the garlic oil with a splash of "
            "the pasta water and serve immediately."
        ),
        created_at=now - timedelta(days=150),
    )
    fried_rice = make_recipe(
        name="Egg Fried Rice", collection=weeknight, cuisine="Chinese",
        category="Rice", difficulty="Easy", cook=15, prep=5, servings=2,
        kcal=480,
        ingredients=[
            ingredient(rice, 300, "g", notes="cooked and chilled"),
            ingredient(eggs, 3, "whole"),
            ingredient(peas, 100, "g"),
            ingredient(soy, 20, "ml"),
            ingredient(onions, 1, "whole"),
        ],
        instructions=(
            "1. Scramble the eggs in a hot wok and set aside.\n"
            "2. Fry the onion, add the cold rice and the peas, and stir until "
            "everything is coated and steaming.\n"
            "3. Splash in the soy, fold the egg back through, serve."
        ),
        created_at=now - timedelta(days=140),
    )
    # ── Not cookable — the pecorino is Out. The blocked render.
    carbonara = make_recipe(
        name="Carbonara", collection=weeknight, cuisine="Italian", category="Pasta",
        difficulty="Medium", cook=15, prep=10, servings=2, kcal=740,
        ingredients=[
            ingredient(pasta, 200, "g"),
            ingredient(pancetta, 120, "g"),
            ingredient(eggs, 3, "yolks"),
            ingredient(pecorino, 50, "g"),    # Out → blocks the recipe
        ],
        instructions=(
            "1. Render the pancetta slowly until crisp.\n"
            "2. Beat the yolks with the parmesan.\n"
            "3. Off the heat, toss the drained pasta with the pancetta, then the "
            "egg mixture, loosening with pasta water until glossy."
        ),
        created_at=now - timedelta(days=100),
    )
    # ── Unknown cookability — the importer left rows it couldn't match. Two
    # recipes share "coconut milk" (spelled differently) so the Settings
    # bulk-linker has one group covering two recipes plus several singletons.
    green_curry = make_recipe(
        name="Thai Green Curry", collection=to_try, cuisine="Thai", category="Curry",
        difficulty="Medium", cook=25, prep=15, servings=4, kcal=610,
        source="https://example.com/thai-green-curry",
        ingredients=[
            ingredient(chicken, 500, "g"),
            ingredient(rice, 300, "g"),
            ingredient(fish_sauce, 1, "tbsp"),
            unlinked("Coconut milk", 400, "ml"),
            unlinked("Green curry paste", 3, "tbsp"),
            unlinked("Thai basil", None, None, notes="a handful, to finish"),
        ],
        instructions=(
            "1. Fry the curry paste in a little of the coconut cream until it "
            "splits and smells fragrant.\n"
            "2. Add the chicken and brown, then pour in the rest of the coconut "
            "milk.\n"
            "3. Simmer fifteen minutes, season with fish sauce, finish with basil."
        ),
        created_at=now - timedelta(days=30),
    )
    laksa = make_recipe(
        name="Weeknight Laksa", collection=to_try, cuisine="Asian", category="Soup",
        difficulty="Easy", cook=20, prep=10, servings=2, kcal=690,
        source="https://example.com/weeknight-laksa",
        ingredients=[
            ingredient(chicken, 300, "g"),
            unlinked("  coconut  milk ", 250, "ml"),  # same group, messy spelling
            unlinked("Laksa paste", 2, "tbsp"),
            unlinked("Rice noodles", 200, "g"),
        ],
        instructions=(
            "1. Loosen the laksa paste in a splash of oil.\n"
            "2. Add the coconut milk and chicken, simmer until cooked through.\n"
            "3. Serve over softened rice noodles."
        ),
        created_at=now - timedelta(days=25),
    )
    # ── The other slots, so the planner's five rows and the cookbook's
    # time-of-day filter are never empty.
    porridge = make_recipe(
        name="Overnight Oats", collection=weeknight, cuisine="Other",
        difficulty="Easy", cook=0, prep=5, servings=1,
        kcal=340, time_of_day="Breakfast",
        ingredients=[
            ingredient(yoghurt, 150, "g"),
            ingredient(milk, 100, "ml"),
            ingredient(sugar, 1, "tsp", notes="or honey"),
        ],
        instructions="Stir everything together in a jar. Fridge overnight. Eat cold.",
        created_at=now - timedelta(days=60),
    )
    toastie = make_recipe(
        name="Cheese Toastie", collection=weeknight, cuisine="Other",
        category="Side", difficulty="Easy", cook=8, prep=2, servings=1,
        kcal=430, time_of_day="Lunch",
        ingredients=[
            ingredient(bread, 2, "slices"),        # Out
            ingredient(butter, 20, "g"),
            ingredient(tasty_cheese, 40, "g"),     # Out — so this one is
        ],                                         # missing TWO, not one
        instructions="Butter the outsides. Cheese the insides. Low heat, be patient.",
        created_at=now - timedelta(days=55),
    )
    affogato = make_recipe(
        name="Affogato", collection=weekend, cuisine="Italian", difficulty="Easy",
        cook=0, prep=3, servings=2, kcal=210, time_of_day="Dessert",
        ingredients=[
            ingredient(icecream, 2, "scoops"),
            ingredient(coffee, 18, "g", notes="one double shot"),
        ],
        instructions="Scoop. Pull a shot. Pour it over. Eat before it melts.",
        created_at=now - timedelta(days=20),
    )
    # ── The hard one, so `difficulty` isn't two-valued in practice.
    sourdough = make_recipe(
        name="Sourdough Loaf", collection=weekend, cuisine="Other", category="Bread",
        difficulty="Hard", cook=45, prep=1200, servings=8, kcal=290,
        ingredients=[
            ingredient(flour, 900, "g"),
            ingredient(salt, 18, "g"),
        ],
        instructions=(
            "Feed the starter. Autolyse. Four sets of folds. Shape, cold retard "
            "overnight, bake in a hot Dutch oven: twenty minutes covered, "
            "twenty-five uncovered."
        ),
        notes="Still not as good as the bakery's, but it's a third of the price.",
        created_at=now - timedelta(days=45),
    )
    # ── A recipe that is a NAME and nothing else. No ingredients, no
    # instructions, no times, no collection. Someone typed a title and got
    # interrupted — the emptiest legal recipe, and every optional block on
    # the detail page collapses.
    stub = make_recipe(
        name="Mum's lemon slice", collection=None, cook=None, prep=None,
        servings=None, difficulty=None, time_of_day=None,
        ingredients=[], instructions=None,
        created_at=now - timedelta(days=2),
    )
    # ── A version pair: two recipes sharing a `version_group_id`. Equal peers
    # (there is no "current" pointer), which is the shape the version panel
    # renders and which neither other dataset contains.
    _version_group = uuid4()
    pizza_v1 = make_recipe(
        name="Pizza dough (60% hydration)", collection=weekend, cuisine="Italian",
        category="Bread", difficulty="Medium", cook=12, prep=90, servings=4,
        ingredients=[ingredient(flour, 600, "g"), ingredient(yeast, 3, "g"),
                     ingredient(salt, 12, "g")],
        instructions="Mix, knead, prove two hours, divide into four.",
        created_at=now - timedelta(days=80),
    )
    pizza_v2 = make_recipe(
        name="Pizza dough (70% hydration, cold prove)", collection=weekend,
        cuisine="Italian", category="Bread", difficulty="Hard", cook=10, prep=1440,
        servings=4,
        ingredients=[ingredient(flour, 600, "g"), ingredient(yeast, 2, "g"),
                     ingredient(salt, 14, "g"), ingredient(olive_oil, 15, "ml")],
        instructions="Same, but wetter, and 48 hours in the fridge. Better blister.",
        created_at=now - timedelta(days=12),
    )
    pizza_v1.version_group_id = _version_group
    pizza_v2.version_group_id = _version_group

    # `updated_at` is when the recipe was last *edited* — distinct from
    # `last_made_on` (cooked) and `created_at` (added), and the three are what
    # the version-information panel puts side by side. Two recipes carry one and
    # the rest don't, because "never edited since it was added" is the majority
    # state and the panel has to render both.
    ragu.updated_at = now - timedelta(days=11)      # tweaked after the last cook
    pizza_v2.updated_at = now - timedelta(days=3)

    repo.save_changes()  # recipes + ingredients need ids before steps/sections/links

    # ── The ragu's sections + ten structured steps ────────────────────────
    # Written through the same access helpers the PATCH endpoint uses rather
    # than hand-inserting rows (R-017): the seed then can't drift from the
    # write path, and the depth-1 / link-target validation runs over it.
    #
    # R-064 — those helpers are Core-level (`db.session.execute(select(...))`)
    # and this seed runs with autoflush OFF, so the `save_changes()` above is
    # load-bearing: without it `_validate_link_targets` selects zero of the
    # ragu's ingredient rows and rejects every step link as "not on this
    # recipe". Same seam as the recipe-save bug that established the rule.
    _ragu_sections = replace_sections_for_recipe(ragu.id, [
        SectionWrite(client_id="sauce", sequence=0, name="The sauce"),
        SectionWrite(client_id="finish", sequence=1, name="To finish"),
    ])
    _sauce = _ragu_sections["sauce"]
    _finish = _ragu_sections["finish"]

    # Pin the ingredients to their sections too, so the ingredient list
    # renders under the same two headers the steps do.
    for _key in ("oil", "pancetta", "onion", "carrot", "celery", "garlic",
                 "mince", "passata", "milk", "chilli"):
        ragu_ings[_key].section_id = _sauce
    for _key in ("pasta", "parmesan"):
        ragu_ings[_key].section_id = _finish
    repo.save_changes()

    def _step(client_id, sequence, text, *, parent=None, hint=None,
              ingredients=(), step_tools=(), section=None, timer=None):
        return StepWrite(
            client_id=client_id, parent_client_id=parent, sequence=sequence,
            text=text, hint=hint,
            ingredient_ids=[ragu_ings[k].id for k in ingredients],
            tool_ids=[tools[t].id for t in step_tools],
            section_id=section,
            timer_minutes=timer,
        )

    replace_steps_for_recipe(ragu.id, [
        _step("s1", 0, "Dice the onion, carrot and celery as finely as you can "
                       "be bothered; a food processor is fine here.",
              hint="Aim for 5mm. Bigger and they never disappear into the sauce.",
              ingredients=("onion", "carrot", "celery"),
              step_tools=("Knife & board", "Food processor"), section=_sauce),
        _step("s2", 1, "Render the pancetta in the oil over a medium-low heat.",
              ingredients=("oil", "pancetta"), step_tools=("Large pot",), section=_sauce),
        # Sub-steps under step 2 — the nesting the structured face exists for.
        _step("s2a", 0, "Start it in a cold pot so the fat comes out before the "
                        "meat colours.", parent="s2"),
        _step("s2b", 1, "Lift the pancetta out and set it aside once it's crisp; "
                        "it goes back in at the end.", parent="s2"),
        _step("s3", 2, "Sweat the soffritto in the pancetta fat until it's soft "
                       "and sweet, fifteen minutes, no colour.",
              hint="If it's browning, the heat is too high.",
              ingredients=("onion", "carrot", "celery"), section=_sauce,
              timer=15),
        _step("s4", 3, "Add the garlic and cook one minute more.",
              ingredients=("garlic", "chilli"), section=_sauce),
        _step("s4a", 0, "Add the chilli flakes here too if you want the heat.",
              parent="s4"),
        _step("s5", 4, "Turn the heat up, add the mince, and break it up as it "
                       "browns.",
              hint="Do it in two batches. A crowded pot steams the meat grey.",
              ingredients=("mince",), step_tools=("Frypan",), section=_sauce),
        _step("s6", 5, "Pour in the passata, half-fill the jar with water and add "
                       "that too. Bring it to a bare simmer.",
              ingredients=("passata",), section=_sauce),
        _step("s7", 6, "Simmer uncovered for three hours, stirring every half "
                       "hour or so.",
              hint="Barely a bubble. If it's spitting, it's too hot.",
              section=_sauce, timer=180),
        _step("s7a", 0, "Top up with a splash of water any time it looks tight.",
              parent="s7"),
        _step("s7b", 1, "Around the two-hour mark, stir the warmed milk through. "
                        "It takes the edge off the tomatoes.",
              parent="s7", ingredients=("milk",)),
        _step("s7c", 2, "Return the pancetta for the last twenty minutes.",
              parent="s7", ingredients=("pancetta",)),
        _step("s8", 7, "Taste and season. It will need more salt than you think.",
              section=_sauce),
        _step("s9", 8, "Cook the spaghetti until just short of al dente, then "
                       "finish it in the sauce with a ladle of pasta water.",
              ingredients=("pasta",), step_tools=("Large pot", "Colander"),
              section=_finish),
        _step("s10", 9, "Off the heat, stir the parmesan through and serve.",
              hint="Off the heat, or it goes stringy.",
              ingredients=("parmesan",), step_tools=("Grater",), section=_finish),
    ])

    # ── The focaccia's five step photos ──────────────────────────────────
    replace_step_images_for_recipe(focaccia.id, [
        StepImageWrite(sequence=i, image_data_url=data_url)
        for i, data_url in enumerate(FOCACCIA_STEP_IMAGES)
    ])

    # ── Tag + tool links (association tables, no standalone entity) ───────
    repo.save_changes()
    tag_table = db.metadata.tables["RecipeTag"]
    db.session.execute(tag_table.insert(), [
        {"recipe_id": r.id, "dietary_tag_id": dietary_tags[t].id}
        for r, t in [
            (aglio, "Vegetarian"), (aglio, "Dairy-free"),
            (fried_rice, "Vegetarian"), (fried_rice, "Dairy-free"),
            (focaccia, "Vegan"), (sourdough, "Vegan"),
            (green_curry, "Dairy-free"), (green_curry, "Gluten-free"),
            (laksa, "Dairy-free"),
            (porridge, "Vegetarian"),
            (affogato, "Vegetarian"), (affogato, "Gluten-free"),
        ]
    ])
    tool_table = db.metadata.tables["RecipeTool"]
    db.session.execute(tool_table.insert(), [
        {"recipe_id": r.id, "tool_id": tools[t].id}
        for r, t in [
            (ragu, "Large pot"), (ragu, "Knife & board"), (ragu, "Grater"),
            (focaccia, "Oven dish"), (focaccia, "Mixing bowl"),
            (aglio, "Large pot"), (aglio, "Frypan"), (aglio, "Colander"),
            (fried_rice, "Wok"), (carbonara, "Large pot"),
            (green_curry, "Wok"), (laksa, "Saucepan"),
            (sourdough, "Large pot"), (sourdough, "Mixing bowl"),
            (toastie, "Frypan"), (affogato, "Grater"),
            (pizza_v1, "Mixing bowl"), (pizza_v2, "Mixing bowl"),
        ]
    ])

    # ══ THE MEAL POOL ════════════════════════════════════════════════════
    # Cooked portions on hand. Some recipes have a pool, some don't — the
    # planner's shortfall panel only says anything when a planned meal has no
    # portions behind it.
    ragu.available_meals = 4
    aglio.available_meals = 2
    fried_rice.available_meals = 1

    # ══ HISTORY EVENTS ═══════════════════════════════════════════════════
    # The stock-item History tab renders four kinds — Bought (implicit, from
    # the finished lists below), Cooked, Wasted and Expiry. All four appear
    # here, and one item overflows the per-kind cap.
    repo.save_changes()  # CookEvent FKs Recipe.id with no ORM relationship

    for _recipe, _days_ago, _meals in [
        (ragu, 74, 6), (ragu, 46, 6), (ragu, 11, 6),
        (aglio, 40, 2), (aglio, 21, 2), (aglio, 9, 2), (aglio, 3, 2),
        (fried_rice, 33, 2), (fried_rice, 16, 2), (fried_rice, 5, 2),
        (carbonara, 52, 2),
        (focaccia, 28, 8), (focaccia, 7, 8),
        (porridge, 6, 1), (porridge, 2, 1),
        (sourdough, 60, 8),
    ]:
        repo.add(CookEvent(
            recipe_id=_recipe.id, recipe_name=_recipe.name, meals_cooked=_meals,
            cooked_by_user_id=None, occurred_at=now - timedelta(days=_days_ago),
        ))

    for _item, _days_ago, _reason in [
        (spinach, 34, "spoiled"),
        (ricotta, 21, "expired"),
        (celery, 15, "spoiled"),
        (icecream, 48, "did_not_like"),
        (passata, 9, "overbought"),
        (milk, 5, "spoiled"),
        (olive_oil, 60, "other"),  # the last of the good tin went rancid
    ]:
        repo.add(StockItemWasteEvent(
            stock_item_id=_item.id, stock_item_name=_item.name,
            reason=_reason, occurred_at=now - timedelta(days=_days_ago),
        ))

    # A manual consumption event alongside the cook-sourced ones below, so the
    # timeline shows both provenances.
    repo.add(ConsumptionEvent(
        stock_item_id=peas.id, stock_item_name=peas.name,
        recipe_id=None, recipe_name=None, source=CONSUMPTION_SOURCE_MANUAL,
        from_sequence=0, to_sequence=1, occurred_at=now - timedelta(days=7),
    ))

    # Expiry `set` events matching each perishable's current date, plus two
    # pushes on the milk (the "kept moving it" pattern, short of the cap).
    for _item, _set_days_ago in [
        (milk, 8), (spinach, 4), (ricotta, 12), (yoghurt, 6), (carrots, 10),
        (olive_oil, 20),  # the everything-item needs one of every event kind
    ]:
        if _item.expiry_date is not None:
            repo.add(StockItemExpiryEvent(
                stock_item_id=_item.id, kind=EXPIRY_EVENT_SET,
                previous_expiry_date=None, new_expiry_date=_item.expiry_date,
                delta_days=None, occurred_at=now - timedelta(days=_set_days_ago),
            ))
    _milk_expiry = milk.expiry_date
    if _milk_expiry is not None:
        for _prev_offset, _new_offset, _delta, _days_ago in [(7, 4, 3, 4), (4, 0, 4, 1)]:
            repo.add(StockItemExpiryEvent(
                stock_item_id=milk.id, kind=EXPIRY_EVENT_PUSHED,
                previous_expiry_date=_milk_expiry - timedelta(days=_prev_offset),
                new_expiry_date=_milk_expiry - timedelta(days=_new_offset),
                delta_days=_delta, occurred_at=now - timedelta(days=_days_ago),
            ))

    # Sriracha — one `set` plus 65 `pushed` events over 90 days. 65 is past the
    # per-kind cap (50), so the "N older events not shown" footer fires on this
    # one item and nowhere else.
    _sri_prev = today - timedelta(days=45)
    repo.add(StockItemExpiryEvent(
        stock_item_id=sriracha.id, kind=EXPIRY_EVENT_SET,
        previous_expiry_date=None, new_expiry_date=_sri_prev,
        delta_days=None, occurred_at=now - timedelta(days=90),
    ))
    for _i in range(65):
        _push_by = 1 + (_i % 3)
        _new_date = _sri_prev + timedelta(days=_push_by)
        repo.add(StockItemExpiryEvent(
            stock_item_id=sriracha.id, kind=EXPIRY_EVENT_PUSHED,
            previous_expiry_date=_sri_prev, new_expiry_date=_new_date,
            delta_days=_push_by,
            occurred_at=now - timedelta(days=max(1, 88 - int(_i * 88 / 65))),
        ))
        _sri_prev = _new_date
    repo.save_changes()

    # ══ INFERENCE / STOCKTAKE FIXTURES ═══════════════════════════════════
    # Dora's belief only says anything when it DISAGREES with the recorded
    # level, and it can only disagree when it has a purchase cadence to reason
    # from. Everything above has thin history on purpose (so the hint stays
    # quiet on most of the pantry); these seven carry engineered histories that
    # land in each visible state.
    #
    # Numbers are against `features/stock_items/pantry_belief.py`:
    #   cadence  = mean gap between purchase dates (needs >= 2)
    #   progress = days_since_last_purchase / cadence + 0.34 per cook since
    #   band     = stocked < 0.75 <= low < 1.15 <= out
    #   conf     = clamp((n-1)/3, .25, 1) * clamp(1.1 - .5*progress, .2, 1)
    #              with high >= 0.66, medium >= 0.33
    # Each fixture's arithmetic is spelled out beside it, because the numbers
    # are meaningless without it and the next person to move a date needs to
    # know which band they just left.
    #
    # All but the orange juice have `stocktake_alerts=True` and are >= 25 days
    # stale, so they are genuinely overdue and land in the queue at three
    # different confidence ranks — the only way the runner's three phases
    # (Review = the confident ones, Walk, Tidy-up) all have members in one
    # session. None is inside the model's 3-day fresh-hard-signal window,
    # which would otherwise make the belief defer to the recorded level.
    #
    # **Review carries four items, not one** (owner, 2026-09-03: the seed
    # "needs something to make the initial 'Dora's pretty sure about these'
    # screen"). One row is not a screen — it reads as a stray item rather than
    # a desk pass — and the phase's whole argument is that you can *scan a
    # column* of beliefs and untick the odd one. Four is enough for that, and
    # each says something different: Weet-Bix (~Low from the calendar), Peanut
    # Butter (~Low because a cook pushed it over), Rolled Oats (Stocked and
    # agreeing — most of a real pass is agreement), Tinned Tomatoes (Stocked
    # against a recorded Low: you restocked and never said so).
    #
    # Note the ceiling this phase has by construction: HIGH confidence needs
    # `1.1 - 0.5*progress >= 0.66`, i.e. progress <= 0.88, so a *confident*
    # belief can only ever be Stocked or Low. "Confidently Out" is unreachable
    # — being deep past a cycle is exactly when an unlogged restock is likely.
    # Don't try to seed one.
    #
    # **The purchase history is a shared shop schedule, not one list per item.**
    # The load seed gives each fixture its own single-line "Weet-Bix shop 3"
    # list, which works but leaves twenty junk lists in the archive and makes
    # the spend surfaces read as nonsense. Here, eight finished shops on a
    # fortnightly-with-top-ups rhythm carry all of it, and each one looks like
    # a shop someone actually did. Same signal, a tenth of the clutter, and the
    # reports/budget surfaces get a believable three months of history for free.

    def cook_consume(item, days_ago, from_seq, to_seq):
        """A cook-sourced depletion — draws the belief down faster than the
        calendar alone, which is the signal the two 'cooked down' fixtures show."""
        repo.add(ConsumptionEvent(
            stock_item_id=item.id, stock_item_name=item.name,
            recipe_id=None, recipe_name=None, source=CONSUMPTION_SOURCE_COOK,
            from_sequence=from_seq, to_sequence=to_seq,
            occurred_at=now - timedelta(days=days_ago),
        ))

    # Bought at 68/54/40/26/12 → cadence 14, 12 days in. progress 0.86 → LOW
    # against a recorded Stocked. n=5 → conf 1.00 * 0.67 = 0.67 → HIGH.
    # This one is the Review phase: Dora is confident enough to just ask.
    weetbix = make_item(name="Weet-Bix", group=g_pantry, level=stocked,
                        location=top_shelf, updated_days_ago=30,
                        stocktake_alerts=True, usual_store_id=woolworths.id)
    # Bought at 96/68/40/12 → cadence 28, 12 days in (0.43 on the calendar
    # alone) plus one cook since → 0.77 → LOW against a recorded Stocked.
    # n=4 → conf 1.00 * 0.72 = 0.72 → HIGH. Review, and the row that shows a
    # *cook* pushing a confident belief over the line.
    peanut_butter = make_item(name="Peanut Butter", group=g_pantry, level=stocked,
                              location=top_shelf, updated_days_ago=28,
                              stocktake_alerts=True)
    # Bought at 82/54/26/5 → cadence 25.7, 5 days in. progress 0.19 → STOCKED,
    # which is exactly what's recorded. n=4 → conf 0.95 (clamped) → HIGH.
    # Review's *agreeing* row: the screen is mostly "yes, still fine", and
    # without one of these it reads as a list of corrections.
    oats = make_item(name="Rolled Oats", group=g_pantry, level=stocked,
                     location=top_shelf, updated_days_ago=30,
                     stocktake_alerts=True, usual_store_id=woolworths.id)
    # Bought at 68/40/26/5 → cadence 21, 5 days in. progress 0.24 → STOCKED
    # against a recorded **Low** that's a month stale. n=4 → conf 0.95 → HIGH.
    # The confident *reassuring* disagreement — you restocked and never said
    # so — which is a different row again from the other three.
    tomatoes = make_item(name="Tinned Tomatoes", group=g_pantry, level=low,
                         location=middle_shelf, updated_days_ago=30,
                         stocktake_alerts=True)
    # Bought at 82/68/54/26 → cadence 18.7, 26 days in. progress 1.39 → OUT
    # against a recorded Stocked. n=4 → conf 1.00 * 0.40 = 0.40 → MEDIUM.
    tuna = make_item(name="Tuna Tins", group=g_pantry, level=stocked,
                     location=middle_shelf, updated_days_ago=30,
                     stocktake_alerts=True)
    # Bought at 96/68/40/12 → cadence 28, only 12 days in, so the calendar
    # alone says Stocked (0.43) — but two cooks since add 0.68, taking it to
    # 1.11 → LOW. This is the fixture that shows *cooking*, not the calendar,
    # moving the belief. n=4 → conf 1.00 * 0.55 = 0.55 → MEDIUM.
    coconut = make_item(name="Coconut Milk", group=g_pantry, level=stocked,
                        location=middle_shelf, updated_days_ago=25,
                        stocktake_alerts=True)
    # Bought at 54/26 → cadence 28, 26 days in (0.93, already Low) plus two
    # cooks (0.68) → 1.61 → OUT against a recorded Low. n=2 and deep
    # extrapolation → conf 0.33 * 0.30 = 0.10 → LOW. The Tidy-up phase.
    stirfry_veg = make_item(name="Stir-fry Veg", group=g_frozen, level=low,
                            location=freezer, updated_days_ago=25,
                            stocktake_alerts=True)
    # Bought at 40/5 → cadence 35, 5 days in. progress 0.14 → STOCKED against
    # a recorded Out that's 30 days stale. The *reassuring* disagreement —
    # you're covered — which is a different chip from the other four.
    orange_juice = make_item(name="Orange Juice", group=g_dairy, level=out,
                             location=door, updated_days_ago=30)
    # Bought at 40/26/12 → cadence 14, 12 days in. progress 0.86 → LOW, which
    # is exactly what's recorded, so the hint stays SILENT. The control: without
    # it there's no evidence the overlay is anything but always-on.
    crackers = make_item(name="Water Crackers", group=g_pantry, level=low,
                         location=middle_shelf, updated_days_ago=25,
                         stocktake_alerts=True)
    # The Sweep phase needs an item that *just* fell out of rotation — four
    # conditions at once, none of which occur by accident: Out and never opened
    # (fails the engagement test), last activity 65 days ago (so it dropped out
    # of the 60-day window 5 days ago), the user's last session 10 days ago (so
    # 5 days ago counts as "since then"), and not muted. Its last shop is 68
    # days ago and its last level change 65, so 65 is the watermark. Without
    # this fixture the phase is unreachable in a fresh DB.
    swept = make_item(name="Rice Wine Vinegar", group=g_pantry, level=out,
                      location=spice_rack, stocktake_alerts=True,
                      updated_days_ago=65)
    repo.save_changes()  # shop lines FK to these ids

    cook_consume(peanut_butter, 6, 0, 0)
    cook_consume(coconut, 8, 0, 0)
    cook_consume(coconut, 4, 0, 1)
    cook_consume(stirfry_veg, 15, 1, 1)
    cook_consume(stirfry_veg, 6, 1, 2)
    level_change(swept, out, 65)

    # ── The shared shop history ──────────────────────────────────────────
    # (days_ago, [(item, unit_price), ...]). The belief fixtures' dates are
    # load-bearing — see the arithmetic above before moving one. The other
    # items on each shop are filler in the honest sense: they make the list
    # read like a real shop and they give the reports/spend surfaces real
    # rows, and none of them is an item whose price-observation matrix was
    # hand-authored above (milk / olive oil / eggs / yoghurt / coffee are
    # deliberately absent so those stay exactly as designed).
    shop_history = [
        (96, [(coconut, 2.00), (swept, 3.50), (rice, 4.20), (salt, 3.00),
              (peanut_butter, 5.50)]),
        (82, [(tuna, 1.20), (flour, 2.00), (sugar, 2.40), (oats, 4.00)]),
        (68, [(weetbix, 6.50), (tuna, 1.20), (coconut, 2.00), (swept, 3.50),
              (onions, 2.50), (peanut_butter, 5.50), (tomatoes, 1.10)]),
        (54, [(weetbix, 6.50), (tuna, 1.10), (stirfry_veg, 7.00), (peas, 3.00),
              (garlic, 1.20), (oats, 4.20)]),
        (40, [(weetbix, 6.00), (coconut, 2.20), (orange_juice, 4.00),
              (crackers, 3.00), (rice, 4.50), (soy, 3.20),
              (peanut_butter, 5.80), (tomatoes, 1.20)]),
        (26, [(weetbix, 6.00), (tuna, 1.20), (stirfry_veg, 7.50),
              (crackers, 3.00), (carrots, 2.00), (flour, 2.20), (oats, 4.20),
              (tomatoes, 1.20)]),
        (12, [(weetbix, 6.50), (coconut, 2.00), (crackers, 3.20), (sugar, 2.60),
              (peas, 3.00), (peanut_butter, 5.80)]),
        (5, [(orange_juice, 4.20), (onions, 2.80), (garlic, 1.30),
             (oats, 4.50), (tomatoes, 1.30)]),
    ]
    history_lists = []
    for _days_ago, _contents in shop_history:
        # Nameless — the API serves a date-derived display name, which is what
        # a real archive looks like and what an unnamed list is *supposed* to
        # render as. (The two named lists below cover the named case.)
        _sl = ShoppingList(
            name=None,
            created_at=now - timedelta(days=_days_ago + 1),
            completed_at=now - timedelta(days=_days_ago),
            status=SHOPPING_LIST_STATUS_DONE,
        )
        repo.add(_sl)
        history_lists.append((_sl, _contents))
    repo.save_changes()  # lines FK to persisted list ids
    for _sl, _contents in history_lists:
        for _seq, (_item, _price) in enumerate(_contents):
            line(_sl.id, _item, _seq, ticked=True, actual_unit_price=_price)
    repo.save_changes()  # line ids on the wire before the harvest FK
    builders.harvest_price_observations(
        {_sl.id: _sl.completed_at for _sl, _ in history_lists}
    )
    repo.save_changes()

    # Two recipes built ON the belief items, so the recipe + planner overlays
    # have something to show. Without these the belief fixtures are pantry-only
    # and no recipe can ever be flagged (FU-653 found this the hard way).
    #   * Tuna Bake — every ingredient recorded Stocked, but Dora thinks the
    #     tuna has run out → "at risk" while the recipe still reads cookable.
    #   * Juice + Yoghurt — the OJ is recorded Out (so it reads not-cookable)
    #     but Dora thinks it was restocked → "may be cookable after all".
    tuna_bake = make_recipe(
        name="Tuna Mornay", collection=weeknight, cuisine="Other", category="Bake",
        difficulty="Easy", cook=25, prep=10, servings=4, kcal=560,
        ingredients=[
            ingredient(tuna, 2, "tins"),
            ingredient(pasta, 250, "g"),
            ingredient(peas, 100, "g"),
            ingredient(milk, 300, "ml"),
        ],
        instructions="Cook the pasta. Make a white sauce. Fold everything through. Bake.",
        created_at=now - timedelta(days=70),
    )
    make_recipe(
        name="Juice and Yoghurt", collection=weeknight, cuisine="Other",
        difficulty="Easy", cook=0, prep=5, servings=1, kcal=180,
        time_of_day="Breakfast",
        ingredients=[
            ingredient(orange_juice, 200, "ml"),
            ingredient(yoghurt, 150, "g"),
        ],
        instructions="Pour. Stir. Done.",
        created_at=now - timedelta(days=65),
    )
    repo.save_changes()

    # ══ MEAL PLANS ═══════════════════════════════════════════════════════
    # Three weeks, each in a different state, because the planner's calendar,
    # rail and reconcile prompt all read different things:
    #   last week — every meal consumed (the reconciled, finished week)
    #   this week — part cooked, part planned, one cook batch, one shortfall
    #   next week — partial, forked from a template (carries its provenance)
    def entry(recipe, day, slot, servings=2, consumed=False, batch=None):
        """`consumed` stamps the meal as eaten **on the evening of the day it was
        scheduled**, derived from `day` rather than passed as a days-ago offset.
        The offset form was wrong and looked right: `monday` moves with the real
        weekday, so on a Monday a fixed `consumed_days_ago=11` stamped last
        week's Monday dinner as eaten four days *before* it was scheduled. A meal
        consumed before its own date is not a state the app can produce, and
        anything reading the pair (the reconcile sweep, the planner's cooked
        markers) would have been reasoning about impossible data."""
        row = MealPlanEntry(
            recipe=recipe, scheduled_for=day, servings=servings, slot=slot,
            # R-021 carve-out: dev fixture, a 19:00 UTC stamp is fine
            consumed_at=(datetime(day.year, day.month, day.day, 19, 0, tzinfo=UTC)
                         if consumed else None),
            cook_batch_id=batch,
        )
        repo.add(row)  # assigns the id; without it every entry shares EMPTY_UUID
        return row

    last_monday = monday - timedelta(days=7)
    last_week_entries = [
        entry(ragu, last_monday, "Dinner", 4, consumed=True),
        entry(porridge, last_monday + timedelta(days=1), "Breakfast", 1, consumed=True),
        entry(aglio, last_monday + timedelta(days=2), "Dinner", 2, consumed=True),
        entry(fried_rice, last_monday + timedelta(days=4), "Dinner", 2, consumed=True),
        entry(affogato, last_monday + timedelta(days=5), "Dessert", 2, consumed=True),
    ]
    repo.add(MealPlan(name=None, start_date=last_monday, entries=last_week_entries))

    # This week. `batch` is filled in after the plan has an id.
    this_week_entries = [
        entry(aglio, monday, "Dinner", 2),
        entry(porridge, monday + timedelta(days=1), "Breakfast", 1),
        entry(tuna_bake, monday + timedelta(days=1), "Dinner", 4),
        entry(toastie, monday + timedelta(days=2), "Lunch", 1),
        # Ragu three nights running off one cook — the cook-batch shape.
        entry(ragu, monday + timedelta(days=2), "Dinner", 2),
        entry(ragu, monday + timedelta(days=3), "Dinner", 2),
        entry(ragu, monday + timedelta(days=4), "Dinner", 2),
        # Carbonara has two Out ingredients and no pool → the shortfall the
        # planner is supposed to warn about.
        entry(carbonara, monday + timedelta(days=5), "Dinner", 2),
        entry(focaccia, monday + timedelta(days=5), "Snack", 4),
    ]
    this_week = MealPlan(name=None, start_date=monday, entries=this_week_entries)
    repo.add(this_week)
    repo.save_changes()

    batch = CookBatch(meal_plan_id=this_week.id, recipe_id=ragu.id)
    repo.add(batch)
    repo.save_changes()
    for _entry in this_week_entries[4:7]:
        _entry.cook_batch_id = batch.id

    # ══ MEAL-PLAN TEMPLATES + A ROTATING SET ═════════════════════════════
    # Two saved week shapes and a set that alternates them, so "apply a
    # template" and "apply a set over a range" both have real input.
    quiet_week = MealPlanTemplate(
        name="Quiet week", description="Cheap, fast, nothing that needs a plan.",
        created_at=now - timedelta(days=50), updated_at=now - timedelta(days=8),
    )
    big_week = MealPlanTemplate(
        name="Cook-once week",
        description="One big Sunday cook, then coast on it.",
        created_at=now - timedelta(days=50), updated_at=now - timedelta(days=50),
    )
    repo.add(quiet_week)
    repo.add(big_week)
    repo.save_changes()

    for _template, _rows in (
        (quiet_week, [(aglio, 0, "Dinner", 2), (fried_rice, 2, "Dinner", 2),
                      (toastie, 3, "Lunch", 1), (porridge, 4, "Breakfast", 1),
                      (laksa, 4, "Dinner", 2)]),
        (big_week, [(ragu, 6, "Dinner", 6), (ragu, 0, "Dinner", 2),
                    (ragu, 1, "Dinner", 2), (focaccia, 6, "Snack", 8),
                    (affogato, 6, "Dessert", 2)]),
    ):
        for _recipe, _offset, _slot, _servings in _rows:
            repo.add(MealPlanTemplateEntry(
                template_id=_template.id, recipe_id=_recipe.id,
                offset_from_monday=_offset, slot=_slot, servings=_servings,
            ))

    rotation = MealPlanTemplateSet(
        name="Fortnight rotation",
        description="Big week, quiet week, repeat.",
        created_at=now - timedelta(days=45), updated_at=now - timedelta(days=45),
    )
    repo.add(rotation)
    repo.save_changes()
    for _position, _template in enumerate((big_week, quiet_week)):
        repo.add(MealPlanTemplateSetItem(
            set_id=rotation.id, template_id=_template.id, position=_position,
        ))

    # Next week, forked from `quiet_week` — `source_template_id` is provenance
    # only, and a plan carrying it renders differently from a hand-built one.
    next_monday = monday + timedelta(days=7)
    next_week_entries = [
        entry(aglio, next_monday, "Dinner", 2),
        entry(fried_rice, next_monday + timedelta(days=2), "Dinner", 2),
        entry(porridge, next_monday + timedelta(days=4), "Breakfast", 1),
    ]
    repo.add(MealPlan(
        name=None, start_date=next_monday, entries=next_week_entries,
        source_template_id=quiet_week.id, source_template_set_id=rotation.id,
        rotation_index=1,
    ))
    repo.save_changes()

    # ══ SHOPPING LISTS ═══════════════════════════════════════════════════
    # Five, covering every status and every line shape.
    draft = ShoppingList(name=None, created_at=now - timedelta(hours=6))
    mid_shop = ShoppingList(
        name="Saturday big shop", created_at=now - timedelta(days=1),
        status=SHOPPING_LIST_STATUS_SHOPPING,
    )
    done_recent = ShoppingList(
        name=None, created_at=now - timedelta(days=4),
        completed_at=now - timedelta(days=3), status=SHOPPING_LIST_STATUS_DONE,
    )
    done_older = ShoppingList(
        name="Fortnight top-up", created_at=now - timedelta(days=17),
        completed_at=now - timedelta(days=16), status=SHOPPING_LIST_STATUS_DONE,
    )
    # Empty draft — the zero-line render, which is otherwise only reachable by
    # creating a list and immediately leaving.
    empty = ShoppingList(name="Butcher", created_at=now - timedelta(hours=2))
    for sl in (draft, mid_shop, done_recent, done_older, empty):
        repo.add(sl)
    repo.save_changes()  # lines FK to list ids

    # Draft — both provenance states (hand-added vs. dropped on by the
    # low-stock trigger), a planned-store split across two shops, a
    # preferred-buy hint, and one line the budget defence pushed to next week.
    line(draft.id, milk, 0, qty=2, selected_product=milk_coles,
         planned_store=coles, is_auto_added=True,
         added_at=now - timedelta(hours=6))
    line(draft.id, bread, 1, is_auto_added=True,
         added_at=now - timedelta(hours=6),
         preferred_buy_id=_preferred_ids.get(bread.name), planned_store=woolworths)
    line(draft.id, parmesan, 2, selected_product=parmesan_coles,
         planned_store=coles, added_at=now - timedelta(hours=5))
    line(draft.id, pancetta, 3, added_at=now - timedelta(hours=5))
    line(draft.id, celery, 4, added_at=now - timedelta(hours=4))
    line(draft.id, coffee, 5, planned_store=farmers,
         added_at=now - timedelta(hours=4),
         preferred_buy_id=_preferred_ids.get(coffee.name))
    # Deferred by the budget defence — present on the list, deliberately not
    # counted in this week's spend.
    line(draft.id, olive_oil, 6, selected_product=oil_aldi, planned_store=aldi,
         is_auto_added=True, added_at=now - timedelta(hours=4),
         deferred_by_budget=True,
         deferred_reason="Would put the week $12 over; the tin can wait.")

    # Mid-shop — some ticked and priced, some not, one bought at a different
    # store than planned (which is the whole reason planned/purchased split).
    line(mid_shop.id, eggs, 0, ticked=True, selected_product=eggs_woolies,
         actual_unit_price=5.50, planned_store=woolworths, purchased_store=woolworths)
    line(mid_shop.id, yoghurt, 1, ticked=True, selected_product=yoghurt_woolies,
         actual_unit_price=7.50, planned_store=woolworths, purchased_store=woolworths)
    line(mid_shop.id, passata, 2, qty=3, selected_product=passata_aldi,
         planned_store=aldi)
    line(mid_shop.id, spinach, 3, planned_store=woolworths)
    line(mid_shop.id, mince, 4, qty=2, ticked=True, actual_unit_price=9.00,
         planned_store=woolworths, purchased_store=coles)  # bought elsewhere

    # Finished lists — their priced ticked lines harvest into observations via
    # the same helper POST /finish uses, so the "from your last receipt"
    # prefill on the draft above has real provenance behind it.
    line(done_recent.id, milk, 0, qty=2, ticked=True, selected_product=milk_coles,
         actual_unit_price=2.90, purchased_store=coles)
    line(done_recent.id, pasta, 1, ticked=True, selected_product=pasta_barilla,
         actual_unit_price=1.50, purchased_store=coles)
    line(done_recent.id, bread, 2, ticked=True, actual_unit_price=6.50,
         purchased_store=farmers)
    line(done_recent.id, carrots, 3, ticked=True, actual_unit_price=2.20,
         purchased_store=farmers)
    line(done_older.id, flour, 0, ticked=True, selected_product=flour_coles,
         actual_unit_price=2.20, purchased_store=coles)
    line(done_older.id, coffee, 1, ticked=True, selected_product=coffee_farmers,
         actual_unit_price=32.00, purchased_store=farmers)
    line(done_older.id, rice, 2, ticked=True, actual_unit_price=4.00,
         purchased_store=aldi)
    # A ticked but UNPRICED line on a finished list — someone ticked it off
    # without recording what they paid, which is the common real case and the
    # one the spend total has to tolerate. It also harvests nothing, which is
    # the branch `line_paid_unit_price() is None` exists for.
    line(done_older.id, salt, 3, ticked=True)
    # The everything-item needs a Bought event too, so it goes on this shop at
    # its usual price. Deliberately BELOW the observation matrix's spike so the
    # harvested row can't unseat the above-usual chip that matrix exists to show.
    line(done_older.id, olive_oil, 4, ticked=True, selected_product=oil_aldi,
         actual_unit_price=7.99, purchased_store=aldi, planned_store=aldi)
    repo.save_changes()  # line ids before the harvest FK

    builders.harvest_price_observations({
        done_recent.id: done_recent.completed_at,
        done_older.id: done_older.completed_at,
    })

    # A receipt photo on the finished shop — pure record-keeping, no OCR.
    attachment_table = db.metadata.tables["ShoppingListAttachment"]
    db.session.execute(attachment_table.insert(), [{
        "id": uuid4(), "shopping_list_id": done_recent.id, "sequence": 0,
        "image": RECEIPT_PHOTO.encode("utf-8"),
        "created_at": done_recent.completed_at,
    }])
    repo.save_changes()

    # ══ SHOPPING-LIST TEMPLATES ══════════════════════════════════════════
    staples = ShoppingListTemplate(name="Weekly staples", created_at=now, updated_at=now)
    baking_kit = ShoppingListTemplate(
        name="Baking restock", created_at=now - timedelta(days=20),
        updated_at=now - timedelta(days=3),
    )
    repo.add(staples)
    repo.add(baking_kit)
    repo.save_changes()
    for _template, _items in (
        (staples, (milk, eggs, bread, butter, coffee, spinach)),
        (baking_kit, (flour, yeast, sugar, butter)),
    ):
        for _seq, _item in enumerate(_items):
            repo.add(ShoppingListTemplateLine(
                template_id=_template.id, stock_item_id=_item.id,
                quantity=1, sequence=_seq,
            ))

    # ══ ALERTS + SUGGESTION STATE ════════════════════════════════════════
    # The alerts surface has two per-user states (snoozed / dismissed)
    # and a per-kind off switch, none of which exist in either other dataset —
    # so the bell has only ever been seen in its "everything untouched" form.
    alert_pref_table = db.metadata.tables["AlertPreference"]
    db.session.execute(alert_pref_table.insert(), [
        # One kind turned off, so the badge count and the list visibly differ
        # from the household truth.
        {"id": uuid4(), "user_id": owner.id, "kind": "shopping_day",
         "enabled": False},
    ])
    # Keys are built with the app's own helper, never hand-formatted here. The
    # scoped form is `<scope>:<id>:<discriminator>`, and the discriminator is the
    # per-item *variant*, which is not always the alert kind (an essential item
    # that is Out has discriminator `essential_out` but kind `essential_low`).
    # A hand-written key looks perfectly plausible, matches nothing, and leaves a
    # fixture that silently does nothing — which is what the first draft of this
    # block did (`expiring_soon:<id>`, scope missing, order reversed). R-003.
    interaction_table = db.metadata.tables["AlertInteraction"]
    # Keys carry the episode (owner 2026-10-15): the expiry date, or the day
    # the level changed. Built from the same fields the evaluator reads.
    db.session.execute(interaction_table.insert(), [
        # Pushed, not yet acted on.
        {"id": uuid4(), "user_id": owner.id,
         "alert_key": stock_alert_key(
             milk.id, f"expiring_soon:{milk.expiry_date.isoformat()}"),
         "created_at": now - timedelta(days=1), "snoozed_until": None,
         "dismissed_at": None, "last_pushed_at": now - timedelta(hours=21)},
        # Snoozed for two more days.
        {"id": uuid4(), "user_id": owner.id,
         "alert_key": stock_alert_key(
             ricotta.id, f"expired:{ricotta.expiry_date.isoformat()}"),
         "created_at": now - timedelta(days=2),
         "snoozed_until": now + timedelta(days=2),
         "dismissed_at": None, "last_pushed_at": None},
        # Dismissed outright — on an essential item that is Out, so its
        # discriminator is `essential_out:<date>` while its *kind* is
        # `essential_low`. That's the discriminator ≠ kind case, pinned by a
        # real fixture.
        {"id": uuid4(), "user_id": owner.id,
         "alert_key": stock_alert_key(
             tasty_cheese.id,
             f"essential_out:{tasty_cheese.stock_level_last_updated.date().isoformat()}"),
         "created_at": now - timedelta(days=5), "snoozed_until": None,
         "dismissed_at": now - timedelta(days=5), "last_pushed_at": None},
    ])

    # Dora's suggestions are generated fresh each call and never stored — only
    # the user's negative decisions are. One dismissed and one snoozed, so the
    # suppression path is exercised without hiding the whole suggestion rail.
    repo.add(DoraSuggestionSuppression(
        kind="frequent_waster", dedup_key=celery.name,
        decision=SUPPRESSION_DECISION_DISMISSED, snoozed_until=None,
        created_at=now - timedelta(days=6),
    ))
    repo.add(DoraSuggestionSuppression(
        kind="use_soon", dedup_key=str(spinach.id),
        decision=SUPPRESSION_DECISION_SNOOZED,
        snoozed_until=now + timedelta(days=3),
        created_at=now - timedelta(days=1),
    ))

    # Price watches on two products, so the explorer's watch state renders.
    price_alert_table = db.metadata.tables["PriceAlert"]
    db.session.execute(price_alert_table.insert(), [
        {"id": uuid4(), "user_id": owner.id, "product_id": coffee_farmers.id,
         "threshold_unit_price": 30.00, "created_at": now - timedelta(days=25)},
        {"id": uuid4(), "user_id": owner.id, "product_id": pasta_barilla.id,
         "threshold_unit_price": 2.00, "created_at": now - timedelta(days=30)},
    ])
    repo.save_changes()

    # ══ QA FIXTURES ══════════════════════════════════════════════════════
    # The same deterministic buy-verdict item the load seed builds, so the
    # Playwright specs pass against either dataset: 3 priced purchases 90/60/30
    # days ago ($5/$6/$7 → avg $6, latest above usual) + 2 waste events (2 of 3
    # purchases wasted) + level Stocked set 31 days ago → the oracle returns
    # skip/high with the mark_stocked one-tap. Keep in sync with
    # web_app/e2e/buy-verdict.spec.ts.
    if qa_fixtures:
        qa_cheese = make_item(
            name="QA Verdict Cheese", group=g_dairy, level=stocked,
            location=fridge, updated_days_ago=31,
        )
        repo.save_changes()
        qa_lists = []
        for _n, _days_ago, _price in [(1, 90, 5.00), (2, 60, 6.00), (3, 30, 7.00)]:
            qa_list = ShoppingList(
                name=f"QA verdict shop {_n}",
                created_at=now - timedelta(days=_days_ago + 1),
                completed_at=now - timedelta(days=_days_ago),
                status=SHOPPING_LIST_STATUS_DONE,
            )
            repo.add(qa_list)
            qa_lists.append((qa_list, _price))
        repo.save_changes()
        for _seq, (_l, _price) in enumerate(qa_lists):
            line(_l.id, qa_cheese, _seq, ticked=True, actual_unit_price=_price)
        repo.save_changes()
        builders.harvest_price_observations(
            {_l.id: _l.completed_at for _l, _ in qa_lists}
        )
        for _days_ago, _reason in [(45, "spoiled"), (20, "expired")]:
            repo.add(StockItemWasteEvent(
                stock_item_id=qa_cheese.id, stock_item_name=qa_cheese.name,
                reason=_reason, occurred_at=now - timedelta(days=_days_ago),
            ))
        repo.save_changes()

    # ══ INSTALL SETTINGS ═════════════════════════════════════════════════
    # The dense dataset turns the optional install surfaces ON, because a
    # gated-off feature renders nothing and this dataset exists to show every
    # path. Each one below has fixtures above that are invisible without it:
    # money → the observations + spend totals; nutrition complex → the
    # NutritionFood links; scanning → the three barcodes; batch features →
    # the cook batch. Boot with `money_on=False` to see the money-off render
    # (the gate is read once at cold mount — FU-592).
    settings = get_or_create_app_setting(repo)
    settings.timezone = "Australia/Brisbane"
    settings.household_headcount = 2
    settings.expiring_soon_window_days = 7
    settings.scanning_enabled = True
    settings.batch_features_enabled = True
    settings.stocktake_enabled = True
    # Complex, not simple: the three NutritionFood rows + their portions above
    # only mean anything at this depth, and simple mode (a typed kcal per
    # recipe) is already covered by the `kcal` values on the recipes.
    settings.nutrition_mode = NUTRITION_MODE_COMPLEX
    if money_on:
        settings.money_enabled = True
        settings.budget_amount = 220.0
        settings.budget_period = BUDGET_PERIOD_WEEKLY

    db.session.autoflush = True
    repo.save_changes()

