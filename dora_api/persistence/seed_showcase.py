"""Curated showcase dataset for demo / sellable-showcase mode (FU-392).

This is the dataset a prospective user or reviewer sees when the install is
booted with ``DORA_DEMO_MODE=true``. It is deliberately *separate* from
``seed.py::seed_dev_data()``:

  * ``seed_dev_data()`` is a developer fixture — it packs in test artifacts
    ("Sriracha (chatty history test)" with 65 events, backdated overdue
    stocktake items, a real personal email address, admin creds ``dora``/
    ``dora``). Great for exercising every edge, wrong to show a stranger.
  * ``seed_showcase_data()`` (here) is a *curated storefront*: a believable
    single-household pantry with clean names, sensible prices, a coherent
    week's meal plan and shopping story, and no test-only noise. It is what a
    salesperson would want on screen.

The row builders the seeds share live in ``seed_builders`` (FU-556). What is
still duplicated across ``seed.py`` / ``seed_dense.py`` / this file — the three
``StockLevel`` rows, the substitute-pair loop, the belief-shop + cook-consume
helpers and the QA-cheese fixture — is tracked by finalisation 14-R11; the
datasets have different shapes and the dev seed must not be perturbed by
showcase changes (scope discipline).

The demo user is ``demo`` / ``demo`` (admin, so every settings/admin screen is
reachable in the showcase). The whole dataset is disposable — demo mode
re-seeds destructively on a schedule (see ``reset_showcase`` +
``startup.py``), so there is nothing precious here.
"""

from datetime import UTC, date, datetime, timedelta

from dora_api.app import app, db
from dora_api.domain.entities.consumption_event import (
    CONSUMPTION_SOURCE_COOK, ConsumptionEvent)
from dora_api.domain.entities.cook_event import CookEvent
from dora_api.domain.entities.meal_plan import MealPlan
from dora_api.domain.entities.meal_plan_entry import MealPlanEntry
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
from dora_api.domain.entities.stock_location import (
    LOCATION_KIND_AREA, LOCATION_KIND_SECTION, LOCATION_KIND_ZONE,
    StockLocation)
from dora_api.domain.entities.store import Store
from dora_api.domain.entities.user import User
from dora_api.infrastructure.auth_helpers import hash_password
from dora_api.persistence.seed_builders import SeedBuilders
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


def reset_showcase() -> None:
    """Destructively rebuild the showcase dataset in its own app context.

    Called both on boot (via ``startup.init_db``) and by the scheduled demo
    reset job. Wraps ``drop_all`` / ``create_all`` / ``seed_showcase_data`` so
    the caller (a background APScheduler thread) doesn't need to manage the
    Flask app context itself.
    """
    with app.app_context():
        db.drop_all()
        db.create_all()
        seed_showcase_data()


def seed_showcase_data():
    """Populate the curated single-household showcase dataset.

    Coherent storefront: two supermarkets with a handful of products (current
    + historic offers for sparklines), a tidy pantry/fridge/freezer with items
    across every stock level and a couple of near-expiry perishables, a small
    recipe book (mostly cookable), this week's meal plan, an active + a
    finished shopping list, and enough price/cook history that the dashboard
    and stock-item timelines feel lived-in — without any developer test noise.
    """
    repo = SqlAlchemyRepository()
    now = datetime.now(UTC)
    today = date.today()  # R-021 carve-out: dev fixture, server-local date is fine

    # See seed_dev_data() for why autoflush is disabled during the build.
    db.session.autoflush = False

    # FU-556 — shared row builders live in seed_builders.SeedBuilders. Bind the
    # methods to the local names the dataset below already uses, so the dataset
    # + call sites stay unchanged; only the builder *bodies* are now shared.
    builders = SeedBuilders(repo, now)
    make_product = builders.make_product
    make_item = builders.make_item
    level_change = builders.level_change
    price_obs = builders.price_obs
    ingredient = builders.ingredient
    make_recipe = builders.make_recipe
    line = builders.make_line

    # ---------------- STORES ---------------- #
    woolworths = Store(name="Woolworths")
    coles = Store(name="Coles")
    for s in (woolworths, coles):
        repo.add(s)

    # ---------------- PRODUCTS ---------------- #
    milk_woolies = make_product(
        store=woolworths, name="Woolworths Full Cream Milk 2L", brand="Woolworths",
        size="2L", size_unit="L", size_value=2.0, stockcode="W-MILK-2L",
        price_now=3.10, price_was=3.10,
        history=[(28, 3.30, 3.30), (14, 3.10, 3.30), (7, 3.10, 3.10)],
    )
    milk_coles = make_product(
        store=coles, name="Coles Full Cream Milk 2L", brand="Coles",
        size="2L", size_unit="L", size_value=2.0, stockcode="C-MILK-2L",
        price_now=2.90, price_was=3.30,
        history=[(28, 3.30, 3.30), (7, 2.90, 3.30)],
    )
    eggs_woolies = make_product(
        store=woolworths, name="Woolworths Free Range Eggs 12pk", brand="Woolworths",
        size="700g", size_unit="g", size_value=700.0, stockcode="W-EGG-12",
        price_now=5.50, price_was=6.20,
        history=[(30, 6.20, 6.20), (5, 5.50, 6.20)],
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
        history=[(30, 3.00, 3.00), (10, 1.50, 3.00)],
    )
    oil_coles = make_product(
        store=coles, name="Coles Extra Virgin Olive Oil 1L", brand="Coles",
        size="1L", size_unit="L", size_value=1.0, stockcode="C-OIL-1L",
        price_now=7.99, price_was=9.99,
        history=[(25, 9.99, 9.99), (3, 7.99, 9.99)],
    )
    parmesan_coles = make_product(
        store=coles, name="Coles Parmesan Wedge 200g", brand="Coles",
        size="200g", size_unit="g", size_value=200.0, stockcode="C-PARM-200",
        price_now=6.00, price_was=6.50, history=[(20, 6.50, 6.50), (8, 6.00, 6.50)],
    )
    coffee_woolies = make_product(
        store=woolworths, name="Vittoria Coffee Beans 1kg", brand="Vittoria",
        size="1kg", size_unit="kg", size_value=1.0, stockcode="W-COFFEE-1KG",
        price_now=28.00, price_was=40.00,
        history=[(40, 40.00, 40.00), (5, 28.00, 40.00)],
    )

    # ---------------- USER ---------------- #
    # Showcase user. Username `demo`, password `demo`, admin so every
    # settings/admin screen is reachable in the demo.
    demo_user = User(
        email="demo@dashydora.app",
        password_hash=hash_password("demo"),
        send_deals_on_day=6,
        username="demo",
        is_admin=True,
    )
    repo.add(demo_user)

    # ---------------- LOCATION HIERARCHY ---------------- #
    pantry = StockLocation(name="Pantry", kind=LOCATION_KIND_ZONE, sequence=0)
    fridge = StockLocation(name="Fridge", kind=LOCATION_KIND_ZONE, sequence=1)
    freezer = StockLocation(name="Freezer", kind=LOCATION_KIND_ZONE, sequence=2)
    for loc in (pantry, fridge, freezer):
        repo.add(loc)
    repo.save_changes()

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
    g_meat = StockGroup(name="Meat & seafood")
    for grp in (g_fruit, g_dairy, g_pantry, g_frozen, g_meat):
        repo.add(grp)

    # ---------------- STOCK ITEMS ---------------- #
    # A believable pantry: mostly stocked, a couple low or out (so the
    # shopping list has a reason to exist), a few near-expiry perishables.
    milk = make_item(name="Full Cream Milk", group=g_dairy, level=low, location=fridge,
                     expiry=today + timedelta(days=3), is_open=True,
                     opened_on=today - timedelta(days=2),
                     products=[milk_woolies, milk_coles], updated_days_ago=1)
    eggs = make_item(name="Free Range Eggs", group=g_dairy, level=stocked, location=fridge,
                     flagged=True, products=[eggs_woolies])
    butter = make_item(name="Butter", group=g_dairy, level=stocked, location=fridge,
                       is_open=True, opened_on=today - timedelta(days=5))
    parmesan = make_item(name="Parmesan Cheese", group=g_dairy, level=out, location=fridge,
                         products=[parmesan_coles])
    pasta = make_item(name="Spaghetti", group=g_pantry, level=stocked, location=top_shelf,
                      products=[pasta_barilla])
    rice = make_item(name="Jasmine Rice", group=g_pantry, level=stocked, location=middle_right)
    tomatoes = make_item(name="Canned Tomatoes", group=g_pantry, level=stocked, location=middle_right)
    olive_oil = make_item(name="Olive Oil", group=g_pantry, level=stocked, location=top_shelf,
                          flagged=True, is_open=True, opened_on=today - timedelta(days=20),
                          products=[oil_coles])
    soy = make_item(name="Soy Sauce", group=g_pantry, level=stocked, location=middle_left)
    bread = make_item(name="Sourdough Bread", group=g_pantry, level=out, location=None,
                      flagged=True)
    coffee = make_item(name="Coffee Beans", group=g_pantry, level=stocked, location=top_shelf,
                       flagged=True, is_open=True, opened_on=today - timedelta(days=3),
                       products=[coffee_woolies])
    onions = make_item(name="Brown Onions", group=g_fruit, level=stocked, location=pantry)
    garlic = make_item(name="Garlic", group=g_fruit, level=stocked, location=pantry)
    broccoli = make_item(name="Broccoli", group=g_fruit, level=low, location=crisper,
                         expiry=today + timedelta(days=2), stocktake_alerts=True,
                         updated_days_ago=8)
    mangoes = make_item(name="Kensington Pride Mangoes", group=g_fruit, level=stocked,
                        location=crisper, expiry=today + timedelta(days=4))
    chicken = make_item(name="Chicken Breast", group=g_meat, level=stocked, location=freezer)
    peas = make_item(name="Frozen Peas", group=g_frozen, level=stocked, location=freezer)

    repo.save_changes()

    # ---------------- STOCKTAKE ROTATION ---------------- #
    # Owner feedback 2026-08-27: *"[stocktake] needs better test data — all of
    # the items say Dora isn't sure on this one."*
    #
    # The showcase had exactly one item in the stocktake rotation (Broccoli)
    # and no purchase history behind it, so the runner could only ever say the
    # same thing about the same single row — and the Review and Tidy-up phases
    # were unreachable, since those are defined by evidence the dataset didn't
    # contain. This block gives the showcase a believable, complete session.
    #
    # The numbers are read straight off `pantry_belief.py`: cadence is the mean
    # gap between purchase dates, progress = days-since-last-buy / cadence plus
    # 0.34 per cook since, and confidence rises with more purchase dates and
    # with being closer to a fresh buy (high ≥ 0.66, medium ≥ 0.33). What each
    # line is *for* is noted against it, because a fixture whose intent isn't
    # written down is a fixture nobody dares change.
    def demo_shops(item, offsets_prices):
        # One finished, priced shop per (days_ago, price) — each is a
        # purchase date the belief model reads.
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
        repo.save_changes()  # lines FK to persisted list ids
        for _sl, (_days_ago, _price) in zip(shops, offsets_prices):
            line(_sl.id, item, 0, ticked=True, actual_unit_price=_price)
        repo.save_changes()  # line ids on the wire before the harvest FK
        builders.harvest_price_observations(
            {_sl.id: _sl.completed_at for _sl in shops}
        )
        repo.save_changes()

    def demo_cook(item, days_ago, from_seq, to_seq):
        repo.add(ConsumptionEvent(
            stock_item_id=item.id, stock_item_name=item.name,
            recipe_id=None, recipe_name=None, source=CONSUMPTION_SOURCE_COOK,
            from_sequence=from_seq, to_sequence=to_seq,
            occurred_at=now - timedelta(days=days_ago),
        ))

    # Review phase — 5 regular buys, 16 days into a ~20-day cycle. Rich
    # history + shallow extrapolation = HIGH confidence, so Dora offers it
    # pre-ticked from the couch instead of sending you to the pantry.
    st_flour = make_item(name="Plain Flour", group=g_pantry, level=stocked,
                         location=top_shelf, stocktake_alerts=True,
                         updated_days_ago=30)
    # Walk, least-certain first — 3 buys on a ~14-day cycle, a full cycle in.
    # MEDIUM confidence: enough to have an opinion, not enough to act on.
    st_yoghurt = make_item(name="Greek Yoghurt", group=g_dairy, level=stocked,
                           location=fridge, stocktake_alerts=True,
                           updated_days_ago=25)
    # Walk — the cooking signal, not the calendar: bought 10 days into a
    # 30-day cycle, but cooked with twice since, which is what draws it down.
    st_passata = make_item(name="Tomato Passata", group=g_pantry, level=stocked,
                           location=middle_left, stocktake_alerts=True,
                           updated_days_ago=25)
    # Walk — no purchase history at all. Kept on purpose: "no evidence, just
    # overdue" is a real and common state, and the runner should be seen
    # handling it. It just shouldn't be the *only* state, which it was.
    st_baking_soda = make_item(name="Bicarb Soda", group=g_pantry, level=stocked,
                               location=middle_right, stocktake_alerts=True,
                               updated_days_ago=40)
    # Tidy-up phase — see the four conditions below.
    st_vinegar = make_item(name="Rice Wine Vinegar", group=g_pantry, level=out,
                           location=middle_left, stocktake_alerts=True,
                           updated_days_ago=65)
    repo.save_changes()  # items need ids before their shops / cooks

    demo_shops(st_flour, [(96, 2.20), (76, 2.20), (56, 2.00), (36, 2.20), (16, 2.40)])
    demo_shops(st_yoghurt, [(42, 5.00), (28, 5.50), (14, 5.00)])
    demo_shops(st_passata, [(70, 2.00), (40, 2.20), (10, 2.00)])
    demo_cook(st_passata, 8, 0, 0)
    demo_cook(st_passata, 4, 0, 1)

    # The Tidy-up (Sweep) phase shows items that have *just* fallen out of
    # rotation, which needs four things true at once — none of which happens
    # by accident, which is why the phase was never visible in the showcase:
    #   • level Out and never opened        → fails the engagement gate
    #   • last activity 65 days ago         → dropped out 5 days ago (60d window)
    #   • last session 10 days ago          → 5 days ago counts as "since then"
    #   • not muted                         → mute means the user already said
    level_change(st_vinegar, out, 65)
    demo_shops(st_vinegar, [(95, 3.50), (65, 3.50)])
    demo_user.stocktake_last_session_at = now - timedelta(days=10)
    repo.save_changes()

    # ---------------- SUBSTITUTES ---------------- #
    from dora_api.features.substitutes.canonical import canonical_pair
    assoc = db.metadata.tables["StockItemSubstitute"]
    raw_pairs = [
        (olive_oil.id, butter.id, "Cooking fat"),
        (pasta.id, rice.id, "Carb base"),
    ]
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
    level_change(milk, stocked, 9)
    level_change(milk, low, 1)
    level_change(parmesan, low, 6)
    level_change(parmesan, out, 1)
    level_change(bread, low, 5)
    level_change(bread, out, 1)

    # ---------------- PRICE OBSERVATIONS ---------------- #
    # Milk — a clean price history across both stores.
    price_obs(milk, total_price=3.30, total_measure=2.0, unit="L", days_ago=42, store=woolworths)
    price_obs(milk, total_price=3.10, total_measure=2.0, unit="L", days_ago=21, store=woolworths)
    price_obs(milk, total_price=2.90, total_measure=2.0, unit="L", days_ago=7, store=coles)
    # Eggs — count-dimension observations.
    price_obs(eggs, total_price=6.20, total_measure=12.0, unit="ea", days_ago=30, store=woolworths)
    price_obs(eggs, total_price=5.90, total_measure=12.0, unit="ea", days_ago=14, store=coles)
    price_obs(eggs, total_price=5.50, total_measure=12.0, unit="ea", days_ago=5, store=woolworths)
    # Coffee — a single observation (widget renders current chip, no baseline).
    price_obs(coffee, total_price=28.00, total_measure=1.0, unit="kg", days_ago=5, store=woolworths)

    # ---------------- RECIPE COLLECTIONS ---------------- #
    weeknight = RecipeCollection(name="Weeknight Dinners")
    to_try = RecipeCollection(name="To Try")
    for c in (weeknight, to_try):
        repo.add(c)

    # ---------------- RECIPE VOCABULARIES ---------------- #
    # FU-556 — fixed vocab (cuisines/categories/dietary tags/tools/meal slots)
    # is shared; the dicts land on `builders` for make_recipe + the tag/tool
    # links below.
    builders.seed_vocabularies()
    dietary_tags = builders.dietary_tags
    tools = builders.tools

    # ---------------- RECIPES ---------------- #
    aglio = make_recipe(
        name="Spaghetti Aglio e Olio", collection=weeknight, cuisine="Italian",
        category="Pasta", favourite=True, cook=15, prep=5, servings=2,
        ingredients=[
            ingredient(pasta, 250, "g"),
            ingredient(garlic, 4, "cloves"),
            ingredient(olive_oil, 60, "ml"),
        ],
        instructions=(
            "1. Boil a large pot of salted water and cook the Spaghetti until al dente.\n"
            "2. Meanwhile, gently heat the Olive Oil and sliced Garlic until fragrant, about 3 minutes.\n"
            "3. Toss the drained pasta through the garlic oil and serve."
        ),
    )
    tomato_pasta = make_recipe(
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
            "1. Cook the Spaghetti in salted boiling water.\n"
            "2. Soften the Garlic in Olive Oil, then add the Canned Tomatoes and simmer 10 minutes.\n"
            "3. Toss the pasta through the sauce and finish with grated Parmesan Cheese."
        ),
    )
    stir_fry = make_recipe(
        name="Chicken Stir Fry", collection=weeknight, cuisine="Asian", category="Stir fry",
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
            ingredient(peas, 100, "g"),
        ],
        instructions=(
            "1. Scramble the Free Range Eggs and set aside.\n"
            "2. Fry the Brown Onions, add the Jasmine Rice, Frozen Peas and Soy Sauce.\n"
            "3. Fold the egg back through and serve hot."
        ),
    )
    # Not cookable now — Sourdough Bread and Parmesan Cheese are Out.
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

    # ---------------- MEAL POOL ---------------- #
    aglio.available_meals = 4
    stir_fry.available_meals = 2
    fried_rice.available_meals = 2

    repo.save_changes()

    # ---------------- HISTORY-TAB EVENTS ---------------- #
    _cook_history = [
        (aglio, 40, 2),
        (aglio, 22, 4),
        (aglio, 8, 2),
        (tomato_pasta, 30, 2),
        (tomato_pasta, 12, 3),
        (tomato_pasta, 4, 2),
        (stir_fry, 25, 2),
        (stir_fry, 10, 3),
        (fried_rice, 15, 2),
        (fried_rice, 3, 2),
    ]
    for _recipe, _days_ago, _meals in _cook_history:
        repo.add(CookEvent(
            recipe_id=_recipe.id,
            recipe_name=_recipe.name,
            meals_cooked=_meals,
            cooked_by_user_id=None,
            occurred_at=now - timedelta(days=_days_ago),
        ))

    for _item, _days_ago, _reason in [
        (milk, 45, "spoiled"),
        (broccoli, 20, "spoiled"),
    ]:
        repo.add(StockItemWasteEvent(
            stock_item_id=_item.id,
            stock_item_name=_item.name,
            reason=_reason,
            occurred_at=now - timedelta(days=_days_ago),
        ))

    for _item, _set_days_ago in [
        (mangoes, 5),
        (milk, 8),
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
    _milk_expiry = milk.expiry_date
    if _milk_expiry is not None:
        repo.add(StockItemExpiryEvent(
            stock_item_id=milk.id,
            kind=EXPIRY_EVENT_PUSHED,
            previous_expiry_date=_milk_expiry - timedelta(days=4),
            new_expiry_date=_milk_expiry,
            delta_days=4,
            occurred_at=now - timedelta(days=1),
        ))

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
        plan_entry(stir_fry, 2, "Dinner", servings=3),
        plan_entry(tomato_pasta, 3, "Dinner", servings=2),
        plan_entry(fried_rice, 4, "Dinner", servings=2),
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
    for sl in (primary, in_progress, archived):
        repo.add(sl)
    repo.save_changes()

    # Primary: the out/low essentials that need buying.
    line(primary.id, milk, 0, qty=2, selected_product=milk_coles)
    line(primary.id, parmesan, 1, selected_product=parmesan_coles)
    line(primary.id, bread, 2)
    line(primary.id, broccoli, 3)

    # In-progress: mid-shop, a couple already ticked.
    line(in_progress.id, eggs, 0, ticked=True, selected_product=eggs_woolies)
    line(in_progress.id, olive_oil, 1, selected_product=oil_coles)
    line(in_progress.id, coffee, 2, ticked=True, selected_product=coffee_woolies)

    # Archived: completed last week, priced + harvested into observations.
    line(archived.id, pasta, 0, ticked=True, selected_product=pasta_barilla,
         actual_unit_price=1.50, purchased_store=coles)
    line(archived.id, milk, 1, qty=2, ticked=True, selected_product=milk_coles,
         actual_unit_price=2.90, purchased_store=coles)

    repo.save_changes()

    # FU-556 — harvest finished priced lines into observations (shared logic).
    builders.harvest_price_observations({archived.id: archived.completed_at})
    repo.save_changes()

    # ---------------- SHOPPING LIST TEMPLATES ---------------- #
    staples = ShoppingListTemplate(name="Weekly staples", created_at=now, updated_at=now)
    repo.add(staples)
    repo.save_changes()

    for seq, item in enumerate((milk, eggs, bread, pasta, butter)):
        repo.add(ShoppingListTemplateLine(
            template_id=staples.id, stock_item_id=item.id, quantity=1, sequence=seq,
        ))

    # ---------------- RECIPE DIETARY TAGS ---------------- #
    repo.save_changes()
    recipe_tag_assoc = db.metadata.tables["RecipeTag"]
    _tag_links = [
        (aglio, "Vegetarian"),
        (stir_fry, "Dairy-free"),
        (fried_rice, "Vegetarian"),
        (garlic_bread, "Vegetarian"),
    ]
    db.session.execute(
        recipe_tag_assoc.insert(),
        [
            {"recipe_id": recipe.id, "dietary_tag_id": dietary_tags[tag].id}
            for recipe, tag in _tag_links
        ],
    )

    # ---------------- RECIPE TOOLS ---------------- #
    recipe_tool_assoc = db.metadata.tables["RecipeTool"]
    _tool_links = [
        (aglio, "Large pot"), (aglio, "Frypan"),
        (stir_fry, "Wok"), (fried_rice, "Wok"),
        (garlic_bread, "Baking tray"), (tomato_pasta, "Large pot"),
    ]
    db.session.execute(
        recipe_tool_assoc.insert(),
        [
            {"recipe_id": recipe.id, "tool_id": tools[tool].id}
            for recipe, tool in _tool_links
        ],
    )

    db.session.autoflush = True
    repo.save_changes()
