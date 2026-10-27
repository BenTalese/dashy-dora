from datetime import UTC, date, datetime, timedelta

from dora_api.app import db
from dora_api.domain.entities.meal_plan import MealPlan
from dora_api.domain.entities.meal_plan_entry import MealPlanEntry
from dora_api.domain.entities.store import Store
from dora_api.domain.entities.recipe_collection import RecipeCollection
from dora_api.domain.entities.shopping_list import (
    SHOPPING_LIST_STATUS_DONE, SHOPPING_LIST_STATUS_SHOPPING, ShoppingList)
from dora_api.domain.entities.shopping_list_template import (
    ShoppingListTemplate, ShoppingListTemplateLine)
from dora_api.domain.entities.stock_group import StockGroup
from dora_api.domain.entities.stock_level import StockLevel
from dora_api.domain.entities.consumption_event import (
    CONSUMPTION_SOURCE_COOK, ConsumptionEvent)
from dora_api.domain.entities.cook_event import CookEvent
from dora_api.domain.entities.stock_item_expiry_event import (
    EXPIRY_EVENT_PUSHED, EXPIRY_EVENT_SET, StockItemExpiryEvent,
)
from dora_api.domain.entities.stock_item_waste_event import StockItemWasteEvent
from dora_api.domain.entities.stock_location import (
    LOCATION_KIND_AREA, LOCATION_KIND_SECTION, LOCATION_KIND_ZONE,
    StockLocation)
from dora_api.domain.entities.app_setting import NUTRITION_MODE_SIMPLE
from dora_api.domain.entities.user import User
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.infrastructure.auth_helpers import hash_password
from dora_api.persistence.seed_builders import SeedBuilders
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


def seed_dev_data(
    bulk_stock_items: int = 0, qa_fixtures: bool = False, money_on: bool = False,
):
    """Populate a rich dev dataset that exercises every screen.

    ``money_on`` (FU-592 — verify tooling) boots the dataset with the money +
    nutrition features already enabled: the install money flag
    (``AppSetting.money_enabled``) plus a household grocery budget, and
    ``AppSetting.nutrition_mode = "simple"``. Both are single install-wide
    concerns now (no per-user opt-in for either). Those surfaces (Chunk 9
    cost/kcal cards, buy-verdict, budget) read
    their gating layer once at cold mount, so an agent verifying them in the
    hidden browser pane needs them on from boot — flipping
    mid-session doesn't re-render. Off by default (env ``DORA_SEED_MONEY_ON``; the
    ``dora-verify-backend-money`` launch profile sets it).

    Covers: multiple stores and products (with current + historic offers
    for sparklines), product↔stock-item links, a deep
    location hierarchy, stock items across all levels / expiry states / flags /
    open markers, substitutes, level-change history, recipes (cookable and
    not) across collections, meals, a full week's meal plan, primary /
    in-progress / archived shopping lists with selected offers, and templates.

    ``qa_fixtures`` (browser-E2E layer, FU-540) appends deterministic items
    whose *state* the Playwright specs assert against — currently the
    buy-verdict "skip + mark_stocked" item, which needs backdated purchase +
    waste history that no API call can create. Off by default (env
    DORA_SEED_QA_FIXTURES; the Playwright webServer sets it).

    ``bulk_stock_items`` (FU-388) appends that many extra deterministic
    "load" stock items — plus a proportional set of products/offers,
    level-change + price history, recipes, and one large shopping list — so
    an interactive dev session runs against a realistic pantry and N+1s /
    slow queries surface naturally. Defaults to 0 (curated set only); the
    dev boot passes ~500 and the e2e suite passes 0 (see startup.init_db).
    The load reuses the same builder closures as the curated data, so the
    two never drift.
    """
    repo = SqlAlchemyRepository()
    now = datetime.now(UTC)
    today = date.today()  # R-021 carve-out: dev fixture, server-local date is fine

    # Build with autoflush off: we add child rows (e.g. RecipeIngredient) before
    # their parent exists to link them, and an autoflush in that gap would try to
    # insert with a null FK. The explicit save_changes() calls below flush with
    # every relationship resolved. Restored before the final commit.
    db.session.autoflush = False

    # FU-556 — shared row builders live in seed_builders.SeedBuilders. Bind the
    # methods to the local names the dataset below already uses, so the dataset
    # + call sites (incl. the FU-388 bulk block) stay unchanged; only the
    # builder *bodies* are now shared with seed_showcase.
    builders = SeedBuilders(repo, now)
    make_product = builders.make_product
    make_item = builders.make_item
    level_change = builders.level_change
    price_obs = builders.price_obs
    ingredient = builders.ingredient
    make_recipe = builders.make_recipe
    line = builders.make_line

    # ---------------- STORES (dev fixtures only) ---------------- #
    # production ships zero pre-seeded stores; these exist only
    # so the dev seed dataset has products to render.
    woolworths = Store(name="Woolworths")
    coles = Store(name="Coles")
    aldi = Store(name="Aldi")
    iga = Store(name="IGA")
    for s in (woolworths, coles, aldi, iga):
        repo.add(s)

    # ---------------- PRODUCTS ---------------- #
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
    pasta_barilla = make_product(
        store=coles, name="Barilla Spaghetti No.5 500g", brand="Barilla",
        size="500g", size_unit="g", size_value=500.0, stockcode="C-PASTA-500",
        price_now=1.50, price_was=3.00,
        history=[(30, 3.00, 3.00), (20, 2.50, 3.00), (10, 1.50, 3.00), (2, 1.50, 3.00)],
    )
    oil_aldi = make_product(
        store=aldi, name="Aldi Extra Virgin Olive Oil 1L", brand="Vialli",
        size="1L", size_unit="L", size_value=1.0, stockcode="A-OIL-1L",
        price_now=7.99, price_was=9.99,
        history=[(25, 9.99, 9.99), (12, 8.99, 9.99), (3, 7.99, 9.99)],
    )
    parmesan_coles = make_product(
        store=coles, name="Coles Parmesan Wedge 200g", brand="Coles",
        size="200g", size_unit="g", size_value=200.0, stockcode="C-PARM-200",
        price_now=6.00, price_was=6.00, history=[(20, 6.50, 6.50), (8, 6.00, 6.50)],
    )
    coffee_iga = make_product(
        store=iga, name="Vittoria Coffee Beans 1kg", brand="Vittoria",
        size="1kg", size_unit="kg", size_value=1.0, stockcode="I-COFFEE-1KG",
        price_now=28.00, price_was=40.00,
        history=[(40, 40.00, 40.00), (20, 34.00, 40.00), (5, 28.00, 40.00)],
    )
    freddo = make_product(
        store=woolworths, name="Cadbury Freddo Cake", brand="Cadbury",
        size="1.5L", size_unit="L", size_value=1.0, stockcode="51741",
        price_now=2.82, price_was=3.52, history=[(15, 3.52, 3.52), (4, 2.82, 3.52)],
    )
    cupcake = make_product(
        store=coles, name="Betty Crocker Gluten Free Vanilla Cupcake Mix", brand="Betty Crocker",
        size="460g", size_unit="g", size_value=460.0, stockcode="3056737",
        price_now=22.15, price_was=32.16, history=[(18, 32.16, 32.16), (6, 22.15, 32.16)],
    )

    # ---------------- USER ---------------- #
    # Default dev user. Username `dora`, password `dora`. Onboarding is
    # marked complete — this dataset is an established household, and a
    # fresh-seed boot shouldn't trap dev/e2e sessions in the first-run
    # wizard (the wizard itself is exercised by registering a new user).
    dev_user = User(
        email="ben.talese@gmail.com",
        password_hash=hash_password("dora"),
        send_deals_on_day=6,
        username="dora",
        is_admin=True,
        onboarding_completed_at=now,
    )
    repo.add(dev_user)

    # ---------------- LOCATION HIERARCHY ---------------- #
    pantry = StockLocation(name="Pantry", kind=LOCATION_KIND_ZONE, sequence=0)
    fridge = StockLocation(name="Fridge", kind=LOCATION_KIND_ZONE, sequence=1)
    freezer = StockLocation(name="Freezer", kind=LOCATION_KIND_ZONE, sequence=2)
    for loc in (pantry, fridge, freezer):
        repo.add(loc)
    repo.save_changes()  # need ids before children FK to them

    top_shelf = StockLocation(name="Top shelf", kind=LOCATION_KIND_AREA, parent_id=pantry.id, sequence=0)
    middle_shelf = StockLocation(name="Middle shelf", kind=LOCATION_KIND_AREA, parent_id=pantry.id, sequence=1)
    for loc in (top_shelf, middle_shelf):
        repo.add(loc)
    repo.save_changes()

    middle_left = StockLocation(name="Left side", kind=LOCATION_KIND_SECTION, parent_id=middle_shelf.id, sequence=0)
    middle_right = StockLocation(name="Right side", kind=LOCATION_KIND_SECTION, parent_id=middle_shelf.id, sequence=1)
    crisper = StockLocation(name="Crisper drawer", kind=LOCATION_KIND_AREA, parent_id=fridge.id, sequence=0)
    for loc in (middle_left, middle_right, crisper):
        repo.add(loc)

    # ---------------- STOCK LEVELS ---------------- #
    # 3-band scheme (see dora_api/domain/stock_status.py). The middle
    # "Sufficient" band was axed 2026-07-02 — semantically dead + clashed
    # with P8-07 Zero-Input Pantry's Out/Low/Stocked inference.
    stocked = StockLevel(name="Stocked", sequence=0)
    low = StockLevel(name="Low Stock", sequence=1)
    out = StockLevel(name="Out of Stock", sequence=2)
    for lvl in (stocked, low, out):
        repo.add(lvl)

    # ---------------- STOCK GROUPS ---------------- #
    g_fruit = StockGroup(name="Fruit & Veg")
    g_dairy = StockGroup(name="Dairy")
    g_pantry = StockGroup(name="Pantry staples")
    g_frozen = StockGroup(name="Frozen")
    g_snacks = StockGroup(name="Snacks & treats")
    g_meat = StockGroup(name="Meat & seafood")
    for grp in (g_fruit, g_dairy, g_pantry, g_frozen, g_snacks, g_meat):
        repo.add(grp)

    # ---------------- STOCK ITEMS ---------------- #
    # Stocktake demo — a handful of alerts-enabled items are seeded with
    # a backdated `stock_level_last_updated` so the post-rework overdue
    # baseline (COALESCE(last_checked_at, stock_level_last_updated)) lands
    # past the fortnightly band and the runner has something to show
    # immediately. Days chosen to exercise every state: mildly overdue,
    # very overdue, and an essential (flagged) item on the weekly band.
    mangoes = make_item(name="Kensington Pride Mangoes", group=g_fruit, level=stocked,
                        location=crisper, expiry=today + timedelta(days=4))
    pizza = make_item(name="Super Awesome Pizza", group=g_frozen, level=stocked, location=freezer)
    chips = make_item(name="Hot Crispy Chippies", group=g_snacks, level=low, location=None,
                      stocktake_alerts=True, updated_days_ago=20)  # ~6 days overdue @ fortnightly
    brazil = make_item(name="Brazil Nuts", group=g_snacks, level=low, location=middle_left,
                       flagged=True, stocktake_alerts=True, updated_days_ago=15)  # essential → weekly, ~8 overdue
    icecream = make_item(name="Vanilla Ice Cream", group=g_frozen, level=low, location=freezer,
                         stocktake_alerts=True, expiry=today - timedelta(days=3),
                         updated_days_ago=32)  # very overdue @ fortnightly
    pasta = make_item(name="Barilla Pasta", group=g_pantry, level=stocked, location=top_shelf,
                      products=[pasta_barilla])
    milk = make_item(name="Full Cream Milk", group=g_dairy, level=low, location=fridge,
                     expiry=today + timedelta(days=2), is_open=True,
                     opened_on=today - timedelta(days=2), products=[milk_woolies, milk_coles],
                     updated_days_ago=1)
    eggs = make_item(name="Free Range Eggs", group=g_dairy, level=stocked, location=fridge,
                     flagged=True, products=[eggs_woolies])
    butter = make_item(name="Butter", group=g_dairy, level=stocked, location=fridge,
                       is_open=True, opened_on=today - timedelta(days=5))
    tomatoes = make_item(name="Canned Tomatoes", group=g_pantry, level=stocked, location=middle_right)
    onions = make_item(name="Brown Onions", group=g_fruit, level=stocked, location=pantry)
    garlic = make_item(name="Garlic", group=g_fruit, level=stocked, location=pantry)
    olive_oil = make_item(name="Olive Oil", group=g_pantry, level=stocked, location=top_shelf,
                          flagged=True, is_open=True, opened_on=today - timedelta(days=20),
                          products=[oil_aldi])
    parmesan = make_item(name="Parmesan Cheese", group=g_dairy, level=out, location=fridge,
                         products=[parmesan_coles])
    chicken = make_item(name="Chicken Breast", group=g_meat, level=stocked, location=freezer)
    rice = make_item(name="Jasmine Rice", group=g_pantry, level=stocked, location=middle_right)
    soy = make_item(name="Soy Sauce", group=g_pantry, level=stocked, location=middle_left)
    broccoli = make_item(name="Broccoli", group=g_fruit, level=low, location=crisper,
                         expiry=today + timedelta(days=1), stocktake_alerts=True,
                         updated_days_ago=18)  # ~4 days overdue @ fortnightly
    bread = make_item(name="Sourdough Bread", group=g_pantry, level=out, location=None,
                      flagged=True)
    coffee = make_item(name="Coffee Beans", group=g_pantry, level=stocked, location=top_shelf,
                       flagged=True, is_open=True, opened_on=today - timedelta(days=3),
                       products=[coffee_iga])
    # 2026-06-30 — dedicated test item for the History-tab truncation
    # footer. Gets 60+ expiry-push events seeded below so the "N older
    # events not shown" copy fires reliably on this one item. Named so
    # a browser tester can find it without spelunking.
    sriracha = make_item(
        name="Sriracha (chatty history test)", group=g_pantry, level=stocked,
        location=middle_left, is_open=True,
        opened_on=today - timedelta(days=90),
        expiry=today + timedelta(days=15),
    )

    repo.save_changes()  # items need ids before substitutes / history / lines

    # ---------------- SUBSTITUTES (undirected pairs) ---------------- #
    from dora_api.features.substitutes.canonical import canonical_pair
    assoc = db.metadata.tables["StockItemSubstitute"]
    raw_pairs = [
        (olive_oil.id, butter.id, "Cooking fat"),
        (pasta.id, rice.id, "Carb base"),
        (parmesan.id, butter.id, None),
        (milk.id, butter.id, None),
    ]
    now = datetime.now(UTC)
    seen: set[tuple] = set()
    rows: list[dict] = []
    for x, y, notes in raw_pairs:
        a, b = canonical_pair(x, y)
        if (a, b) in seen:
            continue
        seen.add((a, b))
        rows.append({
            "stock_item_a_id": a,
            "stock_item_b_id": b,
            "notes": notes,
            "created_at": now,
        })
    db.session.execute(assoc.insert(), rows)

    # ---------------- STOCK-LEVEL HISTORY ---------------- #
    # Demo history exercising every 3-band transition (stocked → low →
    # out on parmesan; stocked ⇄ low bounce on milk/icecream; a
    # stocked-only refresh on pasta after a shop). Post-2026-07-02 the
    # Sufficient middle-band is gone, so old stocked→sufficient
    # transitions collapse into single stocked entries.
    level_change(milk, stocked, 9)
    level_change(milk, low, 1)
    level_change(pasta, stocked, 12)
    level_change(pasta, stocked, 3)
    level_change(icecream, stocked, 8)
    level_change(icecream, low, 2)
    level_change(parmesan, low, 6)
    level_change(parmesan, out, 1)

    # ---------------- PRICE OBSERVATIONS (FU-227 chunk 2) ---------------- #
    # Exercises the full state matrix the "Your prices" widget (chunk 3) will
    # render: ≥3 items with 3+ observations (baseline-ready), ≥1 below
    # MIN_SAMPLES (the empty-state copy), ≥1 with current > 1.15× median
    # (above-usual chip), ≥1 with store_id set + ≥1 without (store chip).
    # These are all *manual* observations (no FK); the chunk-5 harvest below
    # adds FK-provenance ones from finished lists (milk, pasta, pizza, chips,
    # bread).
    # Milk — 4 obs in L, store-tagged, baseline ≈ $2.00/L, latest at baseline.
    price_obs(milk, total_price=4.20, total_measure=2.0, unit="L", days_ago=42, store=woolworths)
    price_obs(milk, total_price=2.00, total_measure=1.0, unit="L", days_ago=21, store=coles)
    price_obs(milk, total_price=4.10, total_measure=2.0, unit="L", days_ago=10, store=woolworths)
    price_obs(milk, total_price=2.00, total_measure=1.0, unit="L", days_ago=2, store=coles)
    # Yoghurt-style multipack observation on butter (FU-227 follow-up:
    # exercises the pack_count column + the obs list's "4 × 125g" render).
    # "$4.20 for 4 × 125g pack of yoghurt" — keeps butter at 3 obs so the
    # widget flips from empty-state to baseline-ready.
    price_obs(butter, total_price=4.20, total_measure=500.0, unit="g",
              days_ago=10, store=woolworths, pack_count=4)

    # Olive oil — 4 obs in ml, no store, latest 30% above median → above-usual chip.
    price_obs(olive_oil, total_price=8.00, total_measure=500.0, unit="ml", days_ago=120)
    price_obs(olive_oil, total_price=9.00, total_measure=500.0, unit="ml", days_ago=80)
    price_obs(olive_oil, total_price=8.50, total_measure=500.0, unit="ml", days_ago=40)
    price_obs(olive_oil, total_price=12.00, total_measure=500.0, unit="ml", days_ago=3)  # spike

    # Eggs — 3 obs in ea (count dim), store-tagged.
    price_obs(eggs, total_price=7.50, total_measure=12.0, unit="ea", days_ago=30, store=woolworths)
    price_obs(eggs, total_price=8.00, total_measure=12.0, unit="ea", days_ago=14, store=coles)
    price_obs(eggs, total_price=7.50, total_measure=12.0, unit="ea", days_ago=5, store=woolworths)

    # Butter — 2 obs (below MIN_SAMPLES — drives the "not enough data" empty state).
    price_obs(butter, total_price=6.50, total_measure=250.0, unit="g", days_ago=18)
    price_obs(butter, total_price=6.80, total_measure=250.0, unit="g", days_ago=4)

    # Coffee — 1 obs (also empty-state side; lets the widget render with a single
    # current-price chip but no baseline).
    price_obs(coffee, total_price=22.00, total_measure=1.0, unit="kg", days_ago=7, store=aldi)

    # ---------------- RECIPE COLLECTIONS ---------------- #
    weeknight = RecipeCollection(name="Weeknight Dinners")
    to_try = RecipeCollection(name="To Try")
    breakfast = RecipeCollection(name="Quick Breakfasts")
    for c in (weeknight, to_try, breakfast):
        repo.add(c)

    # ---------------- RECIPE VOCABULARIES (C-4 Chunk 2) ---------------- #
    # FU-556 — fixed vocab is shared (see seed_builders). The dicts land on
    # `builders`; alias them locally because the recipes below + the FU-388
    # bulk block (cuisines/categories) + the tag/tool links all reference them.
    builders.seed_vocabularies()
    cuisines = builders.cuisines
    categories = builders.categories
    dietary_tags = builders.dietary_tags
    tools = builders.tools

    # ---------------- RECIPES ---------------- #
    # Cookable now (all ingredients stocked).
    aglio = make_recipe(
        name="Spaghetti Aglio e Olio", collection=weeknight, cuisine="Italian",
        category="Pasta", favourite=True, cook=15, prep=5, servings=2,
        ingredients=[
            ingredient(pasta, 250, "g"),
            ingredient(garlic, 4, "cloves"),
            ingredient(olive_oil, 60, "ml"),
        ],
        instructions=(
            "1. Boil a large pot of salted water and cook the Barilla Pasta until al dente.\n"
            "2. Meanwhile, gently heat the Olive Oil and sliced Garlic until fragrant, about 3 minutes.\n"
            "3. Toss the drained pasta through the garlic oil and serve."
        ),
    )
    # Missing an ingredient (Parmesan is Out).
    simple_pasta = make_recipe(
        name="Tomato Pasta", collection=weeknight, cuisine="Italian", category="Pasta",
        cook=20, prep=10, servings=2, last_made=(now - timedelta(days=4)).date(),
        ingredients=[
            ingredient(pasta, 250, "g"),
            ingredient(tomatoes, 1, "can"),
            ingredient(garlic, 2, "cloves"),
            ingredient(olive_oil, 30, "ml"),
            ingredient(parmesan, 30, "g", notes="to serve"),
        ],
        instructions=(
            "1. Cook the Barilla Pasta in salted boiling water.\n"
            "2. Soften the Garlic in Olive Oil, then add the Canned Tomatoes and simmer 10 minutes.\n"
            "3. Toss the pasta through the sauce and finish with grated Parmesan Cheese."
        ),
    )
    stir_fry = make_recipe(
        name="Veggie Stir Fry", collection=weeknight, cuisine="Asian", category="Stir fry",
        cook=15, prep=10, servings=3,
        ingredients=[
            ingredient(rice, 300, "g"),
            ingredient(broccoli, 1, "head"),
            ingredient(soy, 30, "ml"),
            ingredient(garlic, 2, "cloves"),
            ingredient(chicken, 400, "g"),
        ],
        instructions=(
            "1. Cook the Jasmine Rice according to packet directions.\n"
            "2. Stir-fry the Chicken Breast until golden, then add Garlic and Broccoli.\n"
            "3. Splash in the Soy Sauce, toss for 2 minutes and serve over rice."
        ),
    )
    fried_rice = make_recipe(
        name="Egg Fried Rice", collection=weeknight, cuisine="Asian", category="Rice",
        cook=15, prep=5, servings=2,
        ingredients=[
            ingredient(rice, 300, "g"),
            ingredient(eggs, 3, "whole"),
            ingredient(soy, 20, "ml"),
            ingredient(onions, 1, "whole"),
        ],
        instructions=(
            "1. Scramble the Free Range Eggs and set aside.\n"
            "2. Fry the Brown Onions, add the Jasmine Rice and Soy Sauce.\n"
            "3. Fold the egg back through and serve hot."
        ),
    )
    # Missing (Bread is Out, Parmesan is Out).
    garlic_bread = make_recipe(
        name="Cheesy Garlic Bread", collection=to_try, cuisine="Italian", category="Side",
        cook=12, prep=8, servings=4,
        ingredients=[
            ingredient(bread, 1, "loaf"),
            ingredient(butter, 50, "g"),
            ingredient(garlic, 3, "cloves"),
            ingredient(parmesan, 40, "g"),
        ],
        instructions=(
            "1. Mash the Butter with crushed Garlic.\n"
            "2. Spread over sliced Sourdough Bread and top with Parmesan Cheese.\n"
            "3. Bake at 200C for 10 minutes until golden."
        ),
    )
    icecream_bowl = make_recipe(
        # No `category`: "Dessert" is a time of day, and it is already on
        # `time_of_day`. Carrying it on both facets is what put meal-slot names
        # in the cookbook's Category filter (owner feedback 2026-08-20).
        name="Vanilla Ice Cream Bowl", collection=to_try,
        difficulty="Easy", cook=0, prep=2, servings=1, time_of_day="Dessert",
        ingredients=[ingredient(icecream, 2, "scoops", notes="for serving")],
        instructions="1. Scoop the Vanilla Ice Cream into a bowl.\n2. Enjoy.",
    )

    # ---------------- IMPORTED RECIPES WITH UNLINKED ROWS ---------------- #
    # Two recipes in the state the paste importer leaves behind: some rows
    # matched a StockItem, some only carry `raw_text`. This is what gives
    # Settings → Unlinked ingredients real groups to bulk-link, and what puts
    # both recipes into the unknown-cookability tri-state until they're
    # resolved. "Coconut milk" is deliberately shared by both (and spelled
    # with different casing/whitespace) so one group covers 2 recipes and
    # exercises the normaliser; the rest are single-recipe groups.
    unlinked = builders.unlinked_ingredient
    green_curry = make_recipe(
        name="Thai Green Curry", collection=to_try, cuisine="Asian", category="Rice",
        cook=25, prep=15, servings=4, source="https://example.com/thai-green-curry",
        ingredients=[
            ingredient(chicken, 500, "g"),
            ingredient(rice, 300, "g"),
            unlinked("Coconut milk", 400, "ml"),
            unlinked("Green curry paste", 3, "tbsp"),
            unlinked("Fish sauce", 1, "tbsp"),
            unlinked("Thai basil", None, None, notes="a handful, to finish"),
        ],
        instructions=(
            "1. Fry the green curry paste until fragrant.\n"
            "2. Add the Chicken Breast and brown, then pour in the coconut milk.\n"
            "3. Simmer 15 minutes, season with fish sauce and serve over Jasmine Rice."
        ),
    )
    laksa = make_recipe(
        name="Weeknight Laksa", collection=to_try, cuisine="Asian", category="Side",
        cook=20, prep=10, servings=2, source="https://example.com/weeknight-laksa",
        ingredients=[
            ingredient(chicken, 300, "g"),
            unlinked("  coconut  milk ", 250, "ml"),
            unlinked("Laksa paste", 2, "tbsp"),
            unlinked("Rice noodles", 200, "g"),
        ],
        instructions=(
            "1. Loosen the laksa paste in a splash of oil.\n"
            "2. Add the coconut milk and Chicken Breast, simmer until cooked through.\n"
            "3. Serve over softened rice noodles."
        ),
    )

    # ---------------- MEAL POOL ---------------- #
    # Seed `available_meals` directly on the recipes that the plan will
    # draw from, so the dashboard "meals on hand" card and the planner
    # shortfall panel both have something to show.
    aglio.available_meals = 4
    stir_fry.available_meals = 2
    fried_rice.available_meals = 2

    # ---------------- HISTORY-TAB EVENTS (2026-06-30) ---------------- #
    # Enough events to make the Stock Item detail History tab feel
    # populated across three kinds — Cook, Waste, and Expiry — and to
    # trip the per-kind cap's "N older events not shown" footer on the
    # dedicated `sriracha` item. Purchase (Bought) events are already
    # emitted implicitly by the finished-shopping-list seed below.
    # R-017 — seed exercises every new surface introduced this round.

    # Flush the recipes so the CookEvent inserts below (FK → Recipe.id)
    # can rely on the parent rows already existing. CookEvent has no ORM
    # `relationship(Recipe, ...)` — only a table-level FK — so SA's
    # unit-of-work topo sort can't order Recipe before CookEvent on its
    # own, and without this flush the FK check fails on commit.
    repo.save_changes()

    # Cook events across the last 60 days. Recipes are referenced by
    # id/name — the projection joins each cook to its
    # RecipeIngredient stock items, so every ingredient on these
    # recipes gets a "Used in <recipe>" timeline entry.
    _cook_history = [
        # (recipe, days_ago, meals_cooked)
        (aglio, 55, 2),
        (aglio, 40, 2),
        (aglio, 22, 4),
        (aglio, 8, 2),
        (aglio, 2, 2),
        (simple_pasta, 45, 2),
        (simple_pasta, 30, 2),
        (simple_pasta, 12, 3),
        (simple_pasta, 4, 2),
        (stir_fry, 50, 3),
        (stir_fry, 25, 2),
        (stir_fry, 10, 3),
        (fried_rice, 35, 2),
        (fried_rice, 15, 2),
        (fried_rice, 3, 2),
        (garlic_bread, 20, 4),
    ]
    for _recipe, _days_ago, _meals in _cook_history:
        repo.add(CookEvent(
            recipe_id=_recipe.id,
            recipe_name=_recipe.name,
            meals_cooked=_meals,
            cooked_by_user_id=None,
            occurred_at=now - timedelta(days=_days_ago),
        ))

    # A scatter of waste events so the History tab shows the negative-
    # coloured row alongside the positive ones. Reasons are drawn from
    # the WASTE_REASON_* sentinel set (see waste_event entity).
    for _item, _days_ago, _reason in [
        (icecream, 30, "expired"),
        (milk, 45, "spoiled"),
        (broccoli, 20, "spoiled"),
        (brazil, 12, "did_not_like"),
    ]:
        repo.add(StockItemWasteEvent(
            stock_item_id=_item.id,
            stock_item_name=_item.name,
            reason=_reason,
            occurred_at=now - timedelta(days=_days_ago),
        ))

    # Expiry events on the natural perishables — a `set` (matching the
    # date the item was created with) plus a couple of pushes on milk
    # to demonstrate the "kept pushing back" pattern short of the cap.
    for _item, _set_days_ago in [
        (mangoes, 5),
        (milk, 8),
        (icecream, 30),
        (broccoli, 4),
    ]:
        if _item.expiry_date is not None:
            repo.add(StockItemExpiryEvent(
                stock_item_id=_item.id,
                kind=EXPIRY_EVENT_SET,
                previous_expiry_date=None,
                new_expiry_date=_item.expiry_date,
                delta_days=None,
                occurred_at=now - timedelta(days=_set_days_ago),
            ))
    # Two extra pushes on milk that walk the date forward to its
    # current value.
    _milk_expiry = milk.expiry_date
    if _milk_expiry is not None:
        repo.add(StockItemExpiryEvent(
            stock_item_id=milk.id,
            kind=EXPIRY_EVENT_PUSHED,
            previous_expiry_date=_milk_expiry - timedelta(days=7),
            new_expiry_date=_milk_expiry - timedelta(days=4),
            delta_days=3,
            occurred_at=now - timedelta(days=4),
        ))
        repo.add(StockItemExpiryEvent(
            stock_item_id=milk.id,
            kind=EXPIRY_EVENT_PUSHED,
            previous_expiry_date=_milk_expiry - timedelta(days=4),
            new_expiry_date=_milk_expiry,
            delta_days=4,
            occurred_at=now - timedelta(days=1),
        ))

    # Sriracha chatty test — one `set` plus 65 `pushed` events across
    # the last 90 days. 65 > HISTORY_PER_KIND_CAP (50), so the
    # projection drops 15+ events past the cap and the SPA's
    # "N older events not shown" footer trips reliably on this one
    # item without contaminating the rest of the dataset.
    _sri_start_expiry = today - timedelta(days=45)
    repo.add(StockItemExpiryEvent(
        stock_item_id=sriracha.id,
        kind=EXPIRY_EVENT_SET,
        previous_expiry_date=None,
        new_expiry_date=_sri_start_expiry,
        delta_days=None,
        occurred_at=now - timedelta(days=90),
    ))
    _sri_prev = _sri_start_expiry
    for _i in range(65):
        _push_by = 1 + (_i % 3)
        _new_date = _sri_prev + timedelta(days=_push_by)
        # Space pushes evenly across the last 88 days (older to newer
        # as `_i` grows, mirroring real user behaviour).
        _days_ago = max(1, 88 - int(_i * 88 / 65))
        repo.add(StockItemExpiryEvent(
            stock_item_id=sriracha.id,
            kind=EXPIRY_EVENT_PUSHED,
            previous_expiry_date=_sri_prev,
            new_expiry_date=_new_date,
            delta_days=_push_by,
            occurred_at=now - timedelta(days=_days_ago),
        ))
        _sri_prev = _new_date

    # ---------------- MEAL PLAN (this week) ---------------- #
    monday = today - timedelta(days=today.weekday())

    def plan_entry(recipe, day_offset, slot, servings=2):
        entry = MealPlanEntry(
            recipe=recipe,
            scheduled_for=monday + timedelta(days=day_offset),
            servings=servings,
            slot=slot,
        )
        repo.add(entry)
        return entry

    entries = [
        plan_entry(aglio, 0, "Dinner"),
        plan_entry(fried_rice, 1, "Dinner"),
        plan_entry(aglio, 2, "Lunch", servings=1),
        # `simple_pasta` and `icecream_bowl` aren't in the pool, so the
        # planner surfaces a shortfall the user has to cook before then.
        plan_entry(simple_pasta, 3, "Dinner", servings=2),
        plan_entry(fried_rice, 4, "Dinner", servings=3),
        plan_entry(aglio, 5, "Dinner", servings=4),
    ]
    repo.add(MealPlan(name="This Week", start_date=monday, entries=entries))

    # ---------------- SHOPPING LISTS ---------------- #
    primary = ShoppingList(name="This week", created_at=now)
    in_progress = ShoppingList(
        name="Saturday shop", created_at=now - timedelta(days=1),
        status=SHOPPING_LIST_STATUS_SHOPPING,
    )
    archived = ShoppingList(
        name="Last week", created_at=now - timedelta(days=7),
        completed_at=now - timedelta(days=5), status=SHOPPING_LIST_STATUS_DONE,
    )
    # a second finished list whose priced ticked lines get
    # harvested into observations (provenance via FK). Its items overlap the
    # draft `primary` list, so those draft lines surface a "from your last
    # receipt" prefill; the rest fall back to the chosen-offer prefill.
    weekend = ShoppingList(
        name="Weekend shop", created_at=now - timedelta(days=4),
        completed_at=now - timedelta(days=3), status=SHOPPING_LIST_STATUS_DONE,
    )
    for sl in (primary, in_progress, archived, weekend):
        repo.add(sl)
    repo.save_changes()  # lines need persisted list ids

    # Primary: a mix of low/out essentials, one with a chosen offer.
    line(primary.id, milk, 0, qty=2, selected_product=milk_coles)
    line(primary.id, parmesan, 1, selected_product=parmesan_coles)
    line(primary.id, bread, 2)
    line(primary.id, brazil, 3)
    line(primary.id, broccoli, 4)

    # In-progress: mid-shop, a couple already ticked.
    line(in_progress.id, eggs, 0, ticked=True, selected_product=eggs_woolies)
    line(in_progress.id, olive_oil, 1, selected_product=oil_aldi)
    line(in_progress.id, coffee, 2, ticked=True, selected_product=coffee_iga)

    # Archived: completed last week — now priced + harvested. A sized product
    # (pasta → measure obs in g) and two sizeless lines (count obs in ea).
    line(archived.id, pasta, 0, ticked=True, selected_product=pasta_barilla,
         actual_unit_price=1.30, purchased_store=coles)
    line(archived.id, pizza, 1, ticked=True, actual_unit_price=6.00, purchased_store=woolworths)
    line(archived.id, chips, 2, ticked=True, actual_unit_price=3.20)

    # Weekend shop: finished 3 days ago. milk is a sized product (→ measure obs
    # in L, sitting alongside its manual observations with FK provenance);
    # bread is sizeless (→ count obs). Both overlap `primary`.
    line(weekend.id, milk, 0, qty=2, ticked=True, selected_product=milk_coles,
         actual_unit_price=4.00, purchased_store=coles)
    line(weekend.id, bread, 1, ticked=True, actual_unit_price=4.40, purchased_store=woolworths)

    repo.save_changes()  # line ids needed for the harvest FK

    # FU-556 — harvest finished priced lines into observations (shared logic;
    # R-017 — seed exercises the same path the /finish handler uses).
    builders.harvest_price_observations(
        {archived.id: archived.completed_at, weekend.id: weekend.completed_at}
    )
    repo.save_changes()

    # ---------------- SHOPPING LIST TEMPLATES ---------------- #
    staples = ShoppingListTemplate(name="Weekly staples", created_at=now, updated_at=now)
    taco = ShoppingListTemplate(name="Pantry restock", created_at=now, updated_at=now)
    repo.add(staples)
    repo.add(taco)
    repo.save_changes()

    def template_line(template_id, item, seq, qty=1):
        repo.add(ShoppingListTemplateLine(
            template_id=template_id, stock_item_id=item.id, quantity=qty, sequence=seq,
        ))

    for seq, item in enumerate((milk, eggs, bread, pasta, butter)):
        template_line(staples.id, item, seq)
    for seq, item in enumerate((rice, soy, olive_oil, garlic, tomatoes)):
        template_line(taco.id, item, seq)

    # ---------------- RECIPE DIETARY TAGS (C-4 Chunk 2) ---------------- #
    # Recipes + dietary tags both have ids by now (saved above). Write the
    # association directly — RecipeTag has no standalone entity.
    repo.save_changes()
    recipe_tag_assoc = db.metadata.tables["RecipeTag"]
    _tag_links = [
        (aglio, "Vegetarian"),
        (stir_fry, "Dairy-free"),
        (fried_rice, "Vegetarian"),
        (fried_rice, "Dairy-free"),
        (garlic_bread, "Vegetarian"),
        (green_curry, "Dairy-free"),
        (laksa, "Dairy-free"),
    ]
    db.session.execute(
        recipe_tag_assoc.insert(),
        [
            {"recipe_id": recipe.id, "dietary_tag_id": dietary_tags[tag].id}
            for recipe, tag in _tag_links
        ],
    )

    # ---------------- RECIPE TOOLS (C-4 Chunk 5) ---------------- #
    recipe_tool_assoc = db.metadata.tables["RecipeTool"]
    _tool_links = [
        (aglio, "Large pot"), (aglio, "Frypan"),
        (stir_fry, "Wok"), (fried_rice, "Wok"),
        (garlic_bread, "Baking tray"), (simple_pasta, "Large pot"),
        (green_curry, "Large pot"), (laksa, "Large pot"),
    ]
    db.session.execute(
        recipe_tool_assoc.insert(),
        [
            {"recipe_id": recipe.id, "tool_id": tools[tool].id}
            for recipe, tool in _tool_links
        ],
    )

    # ---------------- ZERO-INPUT PANTRY BELIEF DEMO (P8-07) ------------------ #
    # The belief hint only surfaces when Dora's inference DISAGREES with the
    # recorded level, so the curated items above (no purchase cadence → thin
    # data → belief just echoes the recorded level) stay silent. These items
    # carry tailored purchase histories (+ some cook-consumption) engineered to
    # land in every visible state: Dora thinking out / low / stocked against the
    # recorded level, across high / medium / low confidence, including two
    # cases where cooking (not the calendar) is what draws the belief down. One
    # agreeing control is included to prove the hint stays silent when it agrees.
    #
    # Numbers are chosen against the model in
    # dora_api/features/stock_items/pantry_belief.py — cadence = mean gap of the
    # purchase dates; progress = days-since-last-buy / cadence + 0.34 per cook
    # since; band cut-points 0.75 (low) / 1.15 (out); confidence rises with more
    # purchases and with being closer to a fresh buy.
    def belief_shops(item, offsets_prices):
        """Give `item` one finished, priced shop per (days_ago, price) — each a
        purchase date the belief model reads. Mirrors the QA-cheese fixture."""
        shops = []
        for _i, (_days_ago, _price) in enumerate(offsets_prices):
            _sl = ShoppingList(
                name=f"{item.name} shop {_i + 1}",
                created_at=now - timedelta(days=_days_ago + 1),
                completed_at=now - timedelta(days=_days_ago),
                status=SHOPPING_LIST_STATUS_DONE,
            )
            repo.add(_sl)
            shops.append(_sl)
        repo.save_changes()  # list lines FK to persisted ids
        for _sl, (_days_ago, _price) in zip(shops, offsets_prices):
            line(_sl.id, item, 0, ticked=True, actual_unit_price=_price)
        repo.save_changes()  # line ids on the wire before the harvest FK (classic mapper won't order the child insert after its parent — see repo.flush docstring)
        builders.harvest_price_observations({_sl.id: _sl.completed_at for _sl in shops})
        repo.save_changes()  # observations committed before the next item's batch

    def cook_consume(item, days_ago, from_seq, to_seq):
        """A cook-sourced consumption event — the depletion leg (P6-07) that
        draws the belief down faster than the calendar alone."""
        repo.add(ConsumptionEvent(
            stock_item_id=item.id, stock_item_name=item.name,
            recipe_id=None, recipe_name=None, source=CONSUMPTION_SOURCE_COOK,
            from_sequence=from_seq, to_sequence=to_seq,
            occurred_at=now - timedelta(days=days_ago),
        ))

    # 2026-08-27 — every one of these now has `stocktake_alerts=True`.
    #
    # Owner feedback: *"[stocktake] needs better test data — all of the items
    # say Dora isn't sure on this one."* They did, and the seed was the reason.
    # The stocktake queue only admits items with alerts enabled, and until now
    # the only such items (Chippies, Brazil Nuts, Ice Cream, Broccoli) had no
    # purchase history at all — so every row ranked `overdue`/no-evidence and
    # the runner had exactly one thing it could say about any of them. These
    # fixtures already carried engineered histories spanning high / medium /
    # low confidence; they were just never in the rotation. Putting them in
    # gives the runner all three ranks in one session, which is also the only
    # way the three-phase shape (Review → Walk → Tidy-up) is visible at all:
    # the Review phase is *by definition* the confident items, and there were
    # none.
    #
    # Each item's `updated_days_ago` is ≥ 25, well past the fortnightly band,
    # so they are genuinely overdue rather than being forced into the queue.
    # None is within the model's 3-day fresh-hard-signal window, so the
    # beliefs below are unchanged by this.
    #
    # recorded Stocked · bought every ~20d, 16d in (progress ~0.8) → Dora
    # thinks LOW at HIGH confidence (5 buys = rich history). ← the Review phase.
    b_weetbix = make_item(name="Belief: Weet-Bix", group=g_pantry, level=stocked,
                          location=top_shelf, updated_days_ago=30,
                          stocktake_alerts=True)
    # recorded Stocked · every ~14d, 17d in (past a full cycle) → Dora thinks
    # OUT at MEDIUM confidence.
    b_tuna = make_item(name="Belief: Tuna Tins", group=g_pantry, level=stocked,
                       location=middle_right, updated_days_ago=30,
                       stocktake_alerts=True)
    # recorded Stocked · every ~14d, exactly one cycle in → Dora thinks LOW,
    # MEDIUM confidence.
    b_yoghurt = make_item(name="Belief: Greek Yoghurt", group=g_dairy, level=stocked,
                          location=fridge, updated_days_ago=25,
                          stocktake_alerts=True)
    # recorded Stocked · only 10d since a buy (calendar alone = stocked) but
    # cooked with 2× since → belief drawn down to LOW. Shows the cooking signal.
    b_passata = make_item(name="Belief: Passata (cooked down)", group=g_pantry,
                          level=stocked, location=middle_left, updated_days_ago=25,
                          stocktake_alerts=True)
    # recorded Low · calendar ~2/3 through, plus 2 cooks → belief pushed all the
    # way to OUT. LOW confidence (thin history, deep extrapolation).
    b_stirfry = make_item(name="Belief: Stir-fry Veg (cooked out)", group=g_frozen,
                          level=low, location=freezer, updated_days_ago=25,
                          stocktake_alerts=True)
    # recorded Out (stale, 30d ago) but bought again 5d ago → Dora thinks
    # STOCKED. A reassuring disagreement — you're covered.
    b_oj = make_item(name="Belief: Orange Juice (just restocked)", group=g_dairy,
                     level=out, location=fridge, updated_days_ago=30)
    # recorded Low and Dora agrees it's Low → hint stays SILENT (the control).
    b_crackers = make_item(name="Belief: Crackers (agrees, silent)", group=g_pantry,
                           level=low, location=middle_left, updated_days_ago=25,
                           stocktake_alerts=True)
    repo.save_changes()  # items need ids before their shops / consumption

    belief_shops(b_weetbix, [(96, 6.50), (76, 6.50), (56, 6.00), (36, 6.00), (16, 6.50)])
    belief_shops(b_tuna, [(59, 1.20), (45, 1.20), (31, 1.10), (17, 1.20)])
    belief_shops(b_yoghurt, [(42, 5.00), (28, 5.50), (14, 5.00)])
    belief_shops(b_passata, [(70, 2.00), (40, 2.20), (10, 2.00)])
    cook_consume(b_passata, 8, 0, 0)
    cook_consume(b_passata, 4, 0, 1)
    belief_shops(b_stirfry, [(50, 7.00), (20, 7.50)])
    cook_consume(b_stirfry, 15, 1, 1)
    cook_consume(b_stirfry, 6, 1, 2)
    belief_shops(b_oj, [(40, 4.00), (5, 4.20)])
    belief_shops(b_crackers, [(42, 3.00), (28, 3.00), (14, 3.20)])
    repo.save_changes()

    # ── Sweep-phase fixture (Chunk 6 / D-4) ──────────────────────────────
    # The third phase needs an item that *just* fell out of rotation, which is
    # a narrow state to be in and so never occurred by accident: the engagement
    # gate drops an item ENGAGEMENT_WINDOW_DAYS (60) after its last level change
    # or shopping-list appearance, and the Sweep only shows drop-outs that
    # happened *since the user's last session*. So the fixture needs all four of
    # these at once, and the seed is the only place they can be arranged:
    #
    #   • level Out + never opened            → fails `_is_engaged` outright
    #   • last activity 65 days ago           → dropped out 5 days ago
    #   • user's last session 10 days ago     → 5 days ago is "since then"
    #   • not muted                           → mute means "you already said"
    #
    # Without it the phase is unreachable in a fresh dev DB and can only be
    # verified by hand-editing timestamps, which is how it stayed unwalked.
    b_swept = make_item(
        name="Belief: Rice Wine Vinegar (fell out of rotation)", group=g_pantry,
        level=out, location=middle_left, stocktake_alerts=True,
        updated_days_ago=65,
    )
    repo.save_changes()
    builders.level_change(b_swept, out, 65)
    belief_shops(b_swept, [(95, 3.50), (65, 3.50)])
    dev_user.stocktake_last_session_at = now - timedelta(days=10)
    repo.save_changes()

    # FU-653 — two recipes built ON the belief items above, so the recipe /
    # meal-planner overlays have something to show. Without these the belief
    # fixtures were pantry-only and no recipe could ever be flagged (found the
    # hard way: the surfaces were correct and the dataset simply never
    # exercised them).
    #   • Tuna Bake  — every ingredient recorded Stocked, but Dora believes the
    #     tuna has run out → "at risk" (the recipe still reads cookable).
    #   • Juice Bowl — the OJ is recorded Out (so the recipe reads not-cookable)
    #     but Dora believes it was restocked → "may be cookable after all".
    belief_bake = make_recipe(
        name="Belief demo: Tuna Bake", collection=weeknight, cuisine="Italian",
        category="Pasta", cook=25, prep=10, servings=2,
        ingredients=[
            ingredient(b_tuna, 2, "tins"),
            ingredient(pasta, 250, "g"),
        ],
        instructions="Cook the pasta. Stir the tuna through. Bake.",
    )
    make_recipe(
        # `category` dropped — see the ice-cream recipe above; "Breakfast"
        # is a time of day, which `time_of_day` already says.
        name="Belief demo: Juice Bowl", collection=weeknight,
        cook=0, prep=5, servings=1, time_of_day="Breakfast",
        ingredients=[
            ingredient(b_oj, 200, "ml"),
            ingredient(b_yoghurt, 150, "g"),
        ],
        instructions="Pour. Stir. Done.",
    )
    repo.save_changes()

    # NOT planned into "This Week" on purpose. Adding a seventh entry there
    # changed the week's aggregate ingredient demand, which two e2e tests
    # (`test_meal_plan_preview`, `test_cook_batches`) legitimately assert on —
    # they were right to fail. To see the meal-planner overlay, drop
    # "Belief demo: Tuna Bake" onto any day from the planner (one tap), which
    # is also the more honest walk: it's a meal you planned, then Dora noticed
    # the tuna had likely run out.
    _ = belief_bake

    # ---------------- QA FIXTURES (browser-E2E deterministic states) --------- #
    # Mirrors the hand-engineered "QA Verdict Cheese" fixture the 2026-07-17
    # verify session proved live: 3 priced purchases on done lists 90/60/30
    # days ago ($5/$6/$7 → avg $6, last $7 = above-usual) + 2 waste events
    # (2 wasted vs 3 purchased = 67%) + level Stocked set 31 days ago →
    # the oracle returns skip/high with the mark_stocked one-tap, and an
    # in-app add-to-list flips it to remove_from_list. The Playwright
    # buy-verdict spec asserts this exact state — keep the numbers in sync
    # with web_app/e2e/buy-verdict.spec.ts.
    if qa_fixtures:
        qa_cheese = make_item(
            name="QA Verdict Cheese", group=g_dairy, level=stocked,
            location=fridge, updated_days_ago=31,
        )
        repo.save_changes()  # list lines + events FK to the item id

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
        repo.save_changes()  # line ids on the wire before the harvest FK (classic mapper won't order the child insert after its parent)
        builders.harvest_price_observations(
            {_l.id: _l.completed_at for _l, _ in qa_lists}
        )

        for _days_ago, _reason in [(45, "spoiled"), (20, "expired")]:
            repo.add(StockItemWasteEvent(
                stock_item_id=qa_cheese.id,
                stock_item_name=qa_cheese.name,
                reason=_reason,
                occurred_at=now - timedelta(days=_days_ago),
            ))
        repo.save_changes()

    # ---------------- BULK LOAD (FU-388 — dev-only scale data) ---------------- #
    # So every interactive dev session runs against a realistic pantry
    # (default 500 items via DORA_SEED_BULK_ITEMS) instead of the ~22 curated
    # fixtures, and N+1s / slow queries surface naturally rather than only
    # under a paying user's data. Skipped entirely when bulk_stock_items == 0
    # (the e2e suite passes 0 so its boot stays fast). Reuses the curated
    # builder closures above — no duplicate entity construction (R-001/R-003).
    # Distributions are index-based (no RNG) so the dataset is reproducible.
    if bulk_stock_items > 0:
        _bulk_levels = [stocked, stocked, stocked, low, out]  # ~60/20/20 spread
        _bulk_locations = [
            pantry, fridge, freezer, top_shelf, middle_shelf,
            middle_left, middle_right, crisper,
        ]
        _bulk_groups = [g_fruit, g_dairy, g_pantry, g_frozen, g_snacks, g_meat]
        _bulk_stores = [woolworths, coles, aldi, iga]
        # expiry spread: none / soon / far / already-expired.
        _bulk_expiry = {
            0: None,
            1: today + timedelta(days=3),
            2: today + timedelta(days=200),
            3: today - timedelta(days=6),
        }

        bulk_items: list = []
        for i in range(bulk_stock_items):
            grp = _bulk_groups[i % len(_bulk_groups)]
            lvl = _bulk_levels[i % len(_bulk_levels)]
            loc = _bulk_locations[i % len(_bulk_locations)]
            is_open = (i % 5 == 0)
            # ~1 in 5 items carry a linked product (offers + short history),
            # exercising the product-join / sparkline / buy-verdict / My
            # Products surfaces under load.
            products = []
            if i % 5 == 0:
                store = _bulk_stores[(i // 5) % len(_bulk_stores)]
                base = round(2.0 + (i % 50) * 0.1, 2)
                products = [make_product(
                    store=store,
                    name=f"{store.name} Load Product {i:04d}",
                    brand=store.name, size="1ea", size_unit="ea", size_value=1.0,
                    stockcode=f"LOAD-{i:05d}",
                    price_now=round(base * 0.9, 2), price_was=base,
                    history=[
                        (30, base, base),
                        (14, round(base * 0.95, 2), base),
                        (5, round(base * 0.9, 2), base),
                    ],
                )]
            bulk_items.append(make_item(
                name=f"Load item {i:04d} · {grp.name}",
                group=grp, level=lvl, location=loc,
                expiry=_bulk_expiry[i % 4],
                flagged=(i % 7 == 0),
                is_open=is_open,
                opened_on=(today - timedelta(days=(i % 20) + 1)) if is_open else None,
                stocktake_alerts=(i % 6 == 0),
                updated_days_ago=(i % 25),
                products=products,
            ))
        repo.save_changes()  # ids before history / lines FK to them

        # Level-change history on ~1 in 3 (drives the History tab + any
        # change-log aggregation query under volume).
        for i in range(0, bulk_stock_items, 3):
            it = bulk_items[i]
            level_change(it, stocked, 20 + (i % 10))
            level_change(it, _bulk_levels[i % len(_bulk_levels)], 2 + (i % 5))

        # Price observations on ~1 in 4 (drives the "your prices" widget +
        # baseline maths across many items).
        for i in range(0, bulk_stock_items, 4):
            it = bulk_items[i]
            unit_price = round(3.0 + (i % 40) * 0.1, 2)
            price_obs(it, total_price=unit_price, total_measure=1.0, unit="ea",
                      days_ago=30, store=_bulk_stores[i % len(_bulk_stores)])
            price_obs(it, total_price=round(unit_price * 1.05, 2), total_measure=1.0,
                      unit="ea", days_ago=14)
            price_obs(it, total_price=round(unit_price * 0.98, 2), total_measure=1.0,
                      unit="ea", days_ago=3)

        # Bulk recipes referencing the load items — stresses the cookbook
        # list + the cross-recipe cookability computation (a prime N+1
        # candidate). Ingredients span every stock level, so cookability is
        # a genuine mix.
        _bulk_cuisines = list(cuisines.values())
        _bulk_categories = list(categories.values())
        for r in range(min(bulk_stock_items // 8, 80)):
            recipe_ings = [
                ingredient(bulk_items[(r * 5 + k) % bulk_stock_items], 100 + k * 25, "g")
                for k in range(3 + (r % 3))  # 3–5 ingredients each
            ]
            make_recipe(
                name=f"Load recipe {r:03d}", collection=weeknight,
                cuisine=_bulk_cuisines[r % len(_bulk_cuisines)].name,
                category=_bulk_categories[r % len(_bulk_categories)].name,
                cook=15 + (r % 30), prep=5 + (r % 15), servings=2 + (r % 4),
                ingredients=recipe_ings,
                instructions="1. Combine the ingredients.\n2. Cook.\n3. Serve.",
            )

        # One large draft shopping list — stresses the list-detail render +
        # its per-line prefill/offer lookups.
        big_list = ShoppingList(name="Big load list", created_at=now)
        repo.add(big_list)
        repo.save_changes()
        for s in range(min(bulk_stock_items // 10, 60)):
            line(big_list.id, bulk_items[(s * 3) % bulk_stock_items], s, qty=1 + (s % 3))
        repo.save_changes()

    # FU-592 — verify-seed knob: turn money + nutrition on so the flag-gated UI
    # (Chunk 9 cost/kcal cards, buy-verdict, budget) is agent-verifiable in a
    # cold-mount browser pane, where mid-session flips don't re-render. Both are
    # install-wide now; nutrition seeds to `simple` (the depth that needs no
    # dataset, so a fresh verify box has a working nutrition surface offline).
    if money_on:
        app_setting = get_or_create_app_setting(repo)
        app_setting.money_enabled = True
        app_setting.nutrition_mode = NUTRITION_MODE_SIMPLE
        app_setting.budget_amount = 200.0
        app_setting.budget_period = "weekly"
        repo.save_changes()

    db.session.autoflush = True
    repo.save_changes()
