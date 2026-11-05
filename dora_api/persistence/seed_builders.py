"""Shared entity builders + fixed reference data for the two seeds (FU-556).

Both ``seed.py::seed_dev_data()`` and ``seed_showcase.py::seed_showcase_data()``
build the same *kinds* of rows — products with offer history, stock items,
recipes, price observations, shopping-list lines — and seed the same fixed
recipe vocabularies (cuisines / categories / dietary tags / tools / meal slots).
Only the *dataset* (which specific rows, in what arrangement) differs. Before
FU-556 each seed carried its own private copy of these builders and vocab
blocks; this module owns the shared scaffolding so the two can't drift, leaving
each ``seed_*_data()`` as just its dataset definition.

The builders close over a repository + a single ``now`` timestamp (both seeds
already thread these), so they live as methods on ``SeedBuilders(repo, now)``
rather than free functions with a repeated ``repo``/``now`` argument. What stays
in each seed: the dataset rows themselves, the autoflush/``save_changes`` flush
choreography, and the location/level/group structure (which differs between the
two — e.g. the dev seed has a "Snacks & treats" group the showcase doesn't).
"""
from datetime import UTC, datetime, timedelta

from dora_api.domain.entities.category import Category
from dora_api.domain.entities.cuisine import Cuisine
from dora_api.domain.entities.dietary_tag import DietaryTag
from dora_api.domain.entities.meal_slot import MealSlot
from dora_api.domain.entities.product import Product
from dora_api.domain.entities.product_historic_offer import ProductHistoricOffer
from dora_api.domain.entities.product_offer import ProductOffer
from dora_api.domain.entities.recipe import Recipe
from dora_api.domain.entities.recipe_ingredient import RecipeIngredient
from dora_api.domain.entities.shopping_list import ShoppingListLine
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_item_price_observation import \
    StockItemPriceObservation
from dora_api.domain.entities.stock_level_change import StockLevelChange
from dora_api.domain.entities.tool import Tool

# ── Fixed reference data (identical across both seeds) ──────────────────────
# Mirrors the migration's default seed so a create_all dev/test/showcase DB
# matches a migrated prod DB. Only the values a seed's recipes reference need
# binding to locals by the caller; the rest still exist so the settings editor
# shows a full set.
CUISINE_NAMES: list[str] = [
    "Italian", "Asian", "Chinese", "Japanese", "Thai", "Indian",
    "Mexican", "Mediterranean", "American", "French", "Middle Eastern",
    "Other",
]
# Category is a **dish type** and nothing else. It used to include
# "Breakfast", "Dessert" and "Snack", which are MEAL_SLOT_NAMES values below —
# so the cookbook's Category dropdown read as a second time-of-day picker and a
# recipe could carry the same word on both facets. Owner feedback 2026-08-20;
# swapped for three dish types by migration c8b3e5f0a712, whose _CATEGORIES_AFTER
# must stay identical to this list (same names, same order).
CATEGORY_NAMES: list[str] = [
    "Main", "Pasta", "Rice", "Stir fry", "Curry", "Soup", "Salad", "Side",
    "Bake", "Bread", "Drink", "Sauce",
]
DIETARY_TAGS: list[tuple[str, str]] = [
    ("Vegetarian", "Dietary pattern"), ("Vegan", "Dietary pattern"),
    ("Pescatarian", "Dietary pattern"), ("Gluten-free", "Allergen-free"),
    ("Dairy-free", "Allergen-free"), ("Nut-free", "Allergen-free"),
    ("Egg-free", "Allergen-free"), ("Soy-free", "Allergen-free"),
    ("Shellfish-free", "Allergen-free"), ("Low-carb", "Nutritional"),
    ("Low-fat", "Nutritional"), ("Low-sugar", "Nutritional"),
    ("Low-sodium", "Nutritional"), ("Keto", "Diet pattern"),
    ("Paleo", "Diet pattern"), ("Whole30", "Diet pattern"),
    ("Halal", "Religious"), ("Kosher", "Religious"),
]
TOOL_NAMES: list[str] = [
    "Frypan", "Saucepan", "Large pot", "Baking tray", "Oven dish",
    "Mixing bowl", "Food processor", "Blender", "Stand mixer",
    "Hand mixer", "Wok", "Slow cooker", "Air fryer", "Grater",
    "Whisk", "Colander", "Rolling pin", "Knife & board",
]
MEAL_SLOT_NAMES: list[str] = ["Breakfast", "Lunch", "Dinner", "Snack", "Dessert"]


class SeedBuilders:
    """Row builders shared by the dev + showcase seeds. Instantiate once per
    seed run with the seed's repository + ``now`` timestamp, then call the
    methods in place of the old local closures."""

    def __init__(self, repo, now: datetime):
        self.repo = repo
        self.now = now
        # (line, selected_product, store) for finished priced lines, harvested
        # into observations by harvest_price_observations() exactly as
        # POST /finish would. Populated by make_line().
        self.harvest_jobs: list[tuple] = []
        # Every observation seeded so far, per stock item, so a finished line
        # can freeze the usual price the household had *before* it (FU-831),
        # as POST /finish does, without a flush per line.
        self.observations_by_item: dict = {}
        # Populated by seed_vocabularies(); recipes + tag/tool links read these.
        self.cuisines: dict[str, Cuisine] = {}
        self.categories: dict[str, Category] = {}
        self.dietary_tags: dict[str, DietaryTag] = {}
        self.tools: dict[str, Tool] = {}

    # ── Products ────────────────────────────────────────────────────────
    def make_product(self, *, store, name, brand, size, size_unit, size_value,
                     stockcode, price_now, price_was, history):
        """history: list of (days_ago, price_now, price_was)."""
        current = ProductOffer(offered_on=self.now, price_now=price_now, price_was=price_was)
        self.repo.add(current)
        historic = []
        for days_ago, h_now, h_was in history:
            offer = ProductHistoricOffer(
                offered_on=self.now - timedelta(days=days_ago),
                price_now=h_now,
                price_was=h_was,
            )
            self.repo.add(offer)
            historic.append(offer)
        product = Product(
            brand=brand,
            current_offer=current,
            historic_offers=historic,
            image=None,
            is_active=True,
            is_available=True,
            store=store,
            merchant_stockcode=stockcode,
            name=name,
            size=size,
            size_unit=size_unit,
            size_value=size_value,
            web_url=f"https://example.com/p/{stockcode}",
        )
        self.repo.add(product)
        return product

    # ── Stock items ─────────────────────────────────────────────────────
    def make_item(self, *, name, group, level, location, **kw):
        item = StockItem(
            name=name,
            notes=kw.get("notes"),
            stock_group=group,
            stock_level_last_updated=self.now - timedelta(days=kw.get("updated_days_ago", 0)),
            stock_level=level,
            stock_location=location,
            stocktake_alerts_are_enabled=kw.get("stocktake_alerts", False),
            expiry_date=kw.get("expiry"),
            is_essential=kw.get("flagged", False),
            is_open=kw.get("is_open", False),
            opened_on=kw.get("opened_on"),
            products=kw.get("products", []),
            # The remaining nullable columns, defaulted so both seeds' existing
            # calls are unchanged. Only the dense seed sets them today: the
            # stocktake watermark pair (`last_checked_at` / `snoozed_until`),
            # the "where I usually buy this" hint, and the nutrition link +
            # its explicit opt-out (an item the user has said not to ask about
            # again, which is a different state from "not linked yet").
            last_checked_at=kw.get("last_checked_at"),
            snoozed_until=kw.get("snoozed_until"),
            usual_store_id=kw.get("usual_store_id"),
            nutrition_food_id=kw.get("nutrition_food_id"),
            nutrition_ignored=kw.get("nutrition_ignored", False),
        )
        self.repo.add(item)
        return item

    # ── Stock-level history ─────────────────────────────────────────────
    def level_change(self, item, level, days_ago):
        self.repo.add(StockLevelChange(
            stock_item_id=item.id,
            stock_level_id=level.id,
            stock_level_name=level.name,
            changed_at=self.now - timedelta(days=days_ago),
        ))

    # ── Price observations ──────────────────────────────────────────────
    def price_obs(self, item, *, total_price, total_measure, unit, days_ago,
                  store=None, pack_count=None):
        self._add_observation(StockItemPriceObservation(
            stock_item_id=item.id,
            total_price=float(total_price),
            total_measure=float(total_measure),
            unit=unit,
            observed_at=self.now - timedelta(days=days_ago),
            store_id=(store.id if store is not None else None),
            shopping_list_line_id=None,
            created_at=self.now - timedelta(days=days_ago),
            pack_count=pack_count,
        ))

    def _add_observation(self, obs) -> None:
        self.repo.add(obs)
        self.observations_by_item.setdefault(obs.stock_item_id, []).append(obs)

    # ── Recipes ─────────────────────────────────────────────────────────
    def ingredient(self, item, qty, unit, notes=None):
        ri = RecipeIngredient(notes=notes, quantity=qty, stock_item=item, unit=unit)
        self.repo.add(ri)
        return ri

    def unlinked_ingredient(self, raw_text, qty=None, unit=None, notes=None):
        """An ingredient the importer couldn't match to a StockItem.

        Anchors on ``raw_text`` with a NULL stock-item FK — the exact shape
        the paste importer lands when RapidFuzz finds no match, and the only
        shape the Settings → Unlinked ingredients bulk-linker lists. Seeding
        a few gives that page (and the recipes' unknown-cookability state)
        something real to work against.
        """
        ri = RecipeIngredient(
            notes=notes, quantity=qty, stock_item=None, unit=unit, raw_text=raw_text,
        )
        self.repo.add(ri)
        return ri

    def make_recipe(self, *, name, collection, ingredients, instructions, **kw):
        recipe = Recipe(
            available_meals=kw.get("available_meals", 0),
            category=self.categories.get(kw["category"]) if kw.get("category") else None,
            cook_time_minutes=kw.get("cook", 20),
            cuisine=self.cuisines.get(kw["cuisine"]) if kw.get("cuisine") else None,
            difficulty=kw.get("difficulty", "Easy"),
            image=None,
            ingredients=ingredients,
            instructions=instructions,
            is_favourite=kw.get("favourite", False),
            last_made_on=kw.get("last_made"),
            name=name,
            prep_time_minutes=kw.get("prep", 10),
            recipe_collection=collection,
            servings=kw.get("servings", 2),
            source=kw.get("source"),
            time_of_day=kw.get("time_of_day", "Dinner"),
            version_group_id=None,
            kcal=kw.get("kcal"),
            steps_mode=kw.get("steps_mode", "freeform"),
            # seed recipes get the same now() stamp the real create handlers
            # use; the "Recently added" axis sorts them by name within the tick.
            created_at=kw.get("created_at", datetime.now(UTC)),
        )
        self.repo.add(recipe)
        return recipe

    # ── Shopping-list lines ─────────────────────────────────────────────
    def make_line(self, list_id, item, seq, qty=1, ticked=False,
                  selected_product=None, actual_unit_price=None, purchased_store=None,
                  **kw):
        """`kw` carries the line columns only the dense seed exercises —
        provenance (`is_auto_added` / `added_at`), the planning-vs-recording store
        split (`planned_store`, R-063), the preferred-buy hint, and the
        budget-defer pair. Defaulted rather than positional so the existing
        call sites in both seeds stay unchanged (R-003 — one builder, not a
        second near-copy for the newer columns)."""
        _planned_store = kw.get("planned_store")
        sl_line = ShoppingListLine(
            shopping_list_id=list_id,
            stock_item_id=item.id,
            quantity=qty,
            is_ticked=ticked,
            sequence=seq,
            selected_product_id=selected_product.id if selected_product else None,
            actual_unit_price=actual_unit_price,
            purchased_store_id=purchased_store.id if purchased_store else None,
            is_auto_added=kw.get("is_auto_added", False),
            added_at=kw.get("added_at"),
            planned_store_id=_planned_store.id if _planned_store else None,
            preferred_buy_id=kw.get("preferred_buy_id"),
            deferred_by_budget=kw.get("deferred_by_budget", False),
            deferred_reason=kw.get("deferred_reason"),
        )
        self.repo.add(sl_line)
        if ticked and actual_unit_price is not None:
            self.harvest_jobs.append((sl_line, selected_product, purchased_store))
        return sl_line

    # ── Fixed recipe vocabularies ───────────────────────────────────────
    def seed_vocabularies(self) -> None:
        """Create the fixed cuisine/category/dietary-tag/tool/meal-slot rows and
        stash the name→entity dicts on ``self`` (recipes + tag/tool links read
        them). Mirrors the migration default seed so a create_all DB matches a
        migrated prod DB."""
        self.cuisines = {n: Cuisine(name=n, sequence=i) for i, n in enumerate(CUISINE_NAMES)}
        for c in self.cuisines.values():
            self.repo.add(c)

        self.categories = {n: Category(name=n, sequence=i) for i, n in enumerate(CATEGORY_NAMES)}
        for c in self.categories.values():
            self.repo.add(c)

        self.dietary_tags = {
            name: DietaryTag(name=name, category=cat, sequence=i)
            for i, (name, cat) in enumerate(DIETARY_TAGS)
        }
        for t in self.dietary_tags.values():
            self.repo.add(t)

        self.tools = {n: Tool(name=n, sequence=i) for i, n in enumerate(TOOL_NAMES)}
        for t in self.tools.values():
            self.repo.add(t)

        for i, n in enumerate(MEAL_SLOT_NAMES):
            self.repo.add(MealSlot(name=n, sequence=i))

    # ── Finished-list price-observation harvest ─────────────────────────
    def harvest_price_observations(self, completed_at: dict) -> None:
        """Harvest one observation per finished priced line (populated by
        make_line), via the same shared helper the /finish handler uses
        (R-017). ``completed_at`` maps a finished list id → its completed_at
        timestamp; lines on other lists fall back to ``now``."""
        from dora_api.features.shopping_lists._line_price import (
            harvest_observation_fields, line_paid_unit_price)
        from dora_api.features.shopping_lists._usual_price import \
            usual_price_for_one
        # Drain the queue so a later batch of lines (e.g. the QA-fixture
        # block) can harvest again without re-processing — and duplicating —
        # everything harvested here.
        jobs, self.harvest_jobs = self.harvest_jobs, []
        # Oldest shop first, so each line's usual price is built only from the
        # shops before it.
        # The seeds mix naive (UTC) and aware completion times.
        def _shop_time(job) -> datetime:
            at = completed_at.get(job[0].shopping_list_id, self.now)
            return at if at.tzinfo is not None else at.replace(tzinfo=UTC)
        jobs.sort(key=_shop_time)
        for sl_line, product, store in jobs:
            unit_price = line_paid_unit_price(sl_line)
            if unit_price is None:
                continue
            _at = completed_at.get(sl_line.shopping_list_id, self.now)
            if sl_line.actual_unit_price is not None:
                sl_line.usual_price_at_pick = usual_price_for_one(
                    self.observations_by_item.get(sl_line.stock_item_id, []), product, now=_at,
                )
            _tp, _tm, _unit, _pc, _sizeless = harvest_observation_fields(
                unit_price=unit_price,
                quantity=sl_line.quantity,
                size_value=product.size_value if product else None,
                size_unit=product.size_unit if product else None,
                product_pack_count=product.pack_count if product else None,
            )
            self._add_observation(StockItemPriceObservation(
                stock_item_id=sl_line.stock_item_id,
                total_price=_tp, total_measure=_tm, unit=_unit,
                observed_at=_at, store_id=(store.id if store else None),
                shopping_list_line_id=sl_line.id, created_at=_at,
                pack_count=_pc, is_sizeless=_sizeless,
            ))
