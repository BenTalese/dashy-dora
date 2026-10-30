from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, Date, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Table, Text, UniqueConstraint, false, true
from sqlalchemy.orm import deferred, registry as SARegistry, relationship
from sqlalchemy_utils import UUIDType

from dora_api.domain.entities.app_setting import AppSetting
from dora_api.domain.entities.idempotency_key import IdempotencyKey
from dora_api.domain.entities.ingestion_source import IngestionSource
from dora_api.domain.entities.ingestion_store_mapping import IngestionStoreMapping
from dora_api.domain.entities.audit_event import AuditEvent
from dora_api.domain.entities.auth_token import AuthToken
from dora_api.domain.entities.backup import Backup
from dora_api.domain.entities.category import Category
from dora_api.domain.entities.cuisine import Cuisine
from dora_api.domain.entities.dietary_tag import DietaryTag
from dora_api.domain.entities.cook_batch import CookBatch
from dora_api.domain.entities.meal_plan import MealPlan
from dora_api.domain.entities.meal_plan_entry import MealPlanEntry
from dora_api.domain.entities.meal_plan_reconcile_receipt import \
    MealPlanReconcileReceipt
from dora_api.domain.entities.meal_plan_swap_ledger import MealPlanSwapLedger
from dora_api.domain.entities.meal_plan_template import (MealPlanTemplate,
                                                         MealPlanTemplateEntry,
                                                         MealPlanTemplateSet,
                                                         MealPlanTemplateSetItem)
from dora_api.domain.entities.meal_slot import MealSlot
from dora_api.domain.entities.store import Store
from dora_api.domain.entities.price_alert import PriceAlert
from dora_api.domain.entities.preferred_buy import PreferredBuy
from dora_api.domain.entities.nutrition_food import NutritionFood
from dora_api.domain.entities.nutrition_portion import NutritionPortion
from dora_api.domain.entities.product import Product
from dora_api.domain.entities.barcode import Barcode
from dora_api.domain.entities.product_historic_offer import ProductHistoricOffer
from dora_api.domain.entities.product_offer import ProductOffer
from dora_api.domain.entities.recipe import Recipe
from dora_api.domain.entities.recipe_collection import RecipeCollection
from dora_api.domain.entities.recipe_ingredient import RecipeIngredient
from dora_api.domain.entities.recipe_section import RecipeSection
from dora_api.domain.entities.recipe_step import RecipeStep
from dora_api.domain.entities.recipe_step_image import RecipeStepImage
from dora_api.domain.entities.shopping_list import ShoppingList, ShoppingListLine
from dora_api.domain.entities.shopping_list_attachment import ShoppingListAttachment
from dora_api.domain.entities.shopping_list_template import (
    ShoppingListTemplate, ShoppingListTemplateLine,
)
from dora_api.domain.entities.stock_group import StockGroup
from dora_api.domain.entities.stock_item_price_observation import StockItemPriceObservation
from dora_api.domain.entities.tool import Tool
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.dora_suggestion_suppression import \
    DoraSuggestionSuppression
from dora_api.domain.entities.alert_interaction import AlertInteraction
from dora_api.domain.entities.alert_preference import AlertPreference
from dora_api.domain.entities.push_subscription import PushSubscription
from dora_api.domain.entities.cook_event import CookEvent
from dora_api.domain.entities.consumption_event import ConsumptionEvent
from dora_api.domain.entities.stock_item_expiry_event import StockItemExpiryEvent
from dora_api.domain.entities.stock_item_waste_event import StockItemWasteEvent
from dora_api.domain.entities.stock_level import StockLevel
from dora_api.domain.entities.stock_level_change import StockLevelChange
from dora_api.domain.entities.stock_location import StockLocation
from dora_api.domain.entities.user import User
from dora_api.domain.entities.user_llm_provider import UserLlmProvider

_mapper_registry = SARegistry()
_mappings_configured = False


def configure_mappings(db: SQLAlchemy):
    global _mappings_configured
    if _mappings_configured:
        return

    metadata = db.metadata

    # ── Tables ────────────────────────────────────────────────────────────────

    # user-curated stores (was `Merchant`). `image` mirrors the
    # StockItem/Product/Recipe pattern: a large blob, deferred at the mapper
    # so list endpoints don't drag bytes; a dedicated `/stores/<id>/image`
    # route hydrates on demand. Zero logos ship — Dora has no prefilled
    # rows here (no-auto-create, FU-190).
    store_table = Table(
        "Store", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("name", String(255), nullable=False),
        Column("image", LargeBinary, nullable=True),
        # Derived from `image` at write time (see features/stores/_logo_colour.py),
        # never entered by hand. `#rrggbb`, so 7 chars.
        Column("brand_colour", String(7), nullable=True),
    )

    app_setting_table = Table(
        "AppSetting", metadata,
        Column("id", UUIDType, primary_key=True),
        # AI mode is per-user only — no install-wide master kill-switch.
        # Per-user URL / model / provider / API key live on the User table.
        Column("scanning_enabled", Boolean, nullable=False, server_default=false()),
        Column("registration_enabled", Boolean, nullable=False, server_default=false()),
        Column("nutrition_rating_scheme", String(32), nullable=False, server_default="none"),
        # buy-verdict oracle. Defaults on because it's pure-personal;
        # admin can turn off from Settings → System.
        # C-cross Chunk 1 — install-wide feature flags (proposal §2.6).
        Column("money_enabled", Boolean, nullable=False, server_default=false()),
        # `products_enabled` column dropped (migration f1a2b3c4d5e6) —
        # products is a data-presence overlay (PROPOSAL_PRODUCTS_AS_OVERLAY).
        # Nutrition, install-wide (owner call 2026-08-14). Replaces the
        # `nutrition_enabled` bool + the per-user `User.nutrition_mode`, and
        # retires the dead `nutrition_db_source` seam — complex-mode
        # availability is derived from what's actually installed/configured
        # now, not asserted by a magic string.
        Column("nutrition_mode", String(10), nullable=False, server_default="off"),
        Column("nutrition_usda_api_key", String(255), nullable=False, server_default=""),
        Column("nutrition_off_lookup_enabled", Boolean, nullable=False, server_default=true()),
        # Meal Plans C-2.K — household IANA timezone for the "today" boundary.
        Column("timezone", String(64), nullable=False, server_default="UTC"),
        # Alerts C-9.2 — household-wide alert thresholds (PROPOSAL_ALERTS §3.3).
        Column("expiring_soon_window_days", Integer, nullable=False, server_default="7"),
        # Phase D / FU-186 — admin-set URL the Product Search nav opens.
        # Empty string ⇒ unset; see entity comment.
        Column("product_search_url", String(500), nullable=False, server_default=""),
        # AU vs US per-unit display convention. Compute
        # math is locale-independent; only the rendered denominator changes.
        Column("measurement_system", String(16), nullable=False, server_default="metric"),
        # install-wide currency + display
        # locale for money rendering. Read via /api/health so every client
        # session pulls the same values; the client formatter is a thin
        # wrapper around Intl.NumberFormat(locale, {style:'currency', currency}).
        # Household-scoped by design (see entity comment).
        Column("currency", String(3), nullable=False, server_default="AUD"),
        Column("locale", String(35), nullable=False, server_default="en-AU"),
        # backup library: retention cap + storage path.
        # Retention 5 (not 10) is disk-conscious for Pi self-hosts.
        # Empty storage_path ⇒ resolved to `$DORA_DATA_DIR/backups/`
        # at runtime by the config helper — see backup_library.py.
        Column("backup_retention_count", Integer, nullable=False, server_default="5"),
        Column("backup_storage_path", String(1024), nullable=False, server_default=""),
        # install-wide image compression knobs. Client-side
        # `processImageFile` reads these on load and applies them at
        # upload time to every image surface.
        Column("image_quality", Integer, nullable=False, server_default="85"),
        Column("image_max_dimension", Integer, nullable=False, server_default="1920"),
        # PROPOSAL_STOCKTAKE_MODE §4 + §8 — the two global stocktake knobs.
        # `stocktake_default_cadence_band` = 'weekly' | 'fortnightly' |
        # 'monthly'. `stocktake_auto_tuning_enabled` = master switch for
        # the movement-history self-tuner ("auto = speed"), on by default.
        Column("stocktake_default_cadence_band", String(16), nullable=False, server_default="fortnightly"),
        Column("stocktake_auto_tuning_enabled", Boolean, nullable=False, server_default=true()),
        # 2026-08-20 owner feedback — the install-wide stocktake master switch
        # plus the default it hands new items. `stocktake_enabled` False hides
        # the whole surface (overview button, per-item mute toggle, queue) and
        # makes the server resolve an empty overdue map, so the bell can't
        # nag about a feature nobody can open.
        Column("stocktake_enabled", Boolean, nullable=False, server_default=true()),
        Column("stocktake_new_items_opt_in", Boolean, nullable=False, server_default=true()),
        # FU-317 — install-wide meal-plan reconcile posture (D5 install-wide,
        # FU-517 resolved 2026-07-09). Default TRUE keeps today's silent
        # auto-drain; FALSE flips the sweep to write receipts but leave
        # the pool + entries untouched (see reconcile_consumed_meals.py).
        Column("auto_drain_past_meals", Boolean, nullable=False, server_default=true()),
        # FU-511 — install-wide auto-add mode ('off' | 'essential_only' | 'all').
        # Replaces the per-item StockItem.auto_add_when_low column.
        Column("auto_add_mode", String(16), nullable=False, server_default="essential_only"),
        # FU-615 — household cooking config, install-wide (moved off User).
        # `household_headcount` NULL = not set (cook mode uses recipe servings);
        # `batch_features_enabled` default False ("fresh"). Read by every client
        # via /api/health.cooking_policy; edited in Settings → System → Cooking.
        Column("household_headcount", Integer, nullable=True),
        Column("batch_features_enabled", Boolean, nullable=False, server_default=false()),
        # household grocery budget (moved off User). NULL/≤0 amount = off.
        Column("budget_amount", Float, nullable=True),
        Column("budget_period", String(16), nullable=False, server_default="weekly"),
        # operational config promoted from `DORA_*`
        # env vars. `resolved_operational_config()` is now a straight
        # AppSetting projection (env fallbacks dropped 2026-07-06 —
        # pre-release, no operators to preserve). Bucket C secrets
        # (`smtp_password_encrypted`, `vapid_private_key_encrypted`) hold
        # Fernet ciphertext wrapped by `DORA_SECRET_ENCRYPTION_KEY`; the
        # DTO surfaces a `<field>_configured: bool` instead of the ciphertext.
        Column("smtp_host", String(255), nullable=False, server_default=""),
        Column("smtp_port", Integer, nullable=False, server_default="587"),
        Column("smtp_username", String(255), nullable=False, server_default=""),
        Column("smtp_password_encrypted", String(1024), nullable=False, server_default=""),
        Column("smtp_from", String(255), nullable=False, server_default=""),
        Column("smtp_use_tls", Boolean, nullable=False, server_default=true()),
        Column("vapid_public_key", String(255), nullable=False, server_default=""),
        Column("vapid_private_key_encrypted", String(4096), nullable=False, server_default=""),
        Column("vapid_subject", String(255), nullable=False, server_default="mailto:admin@dora.local"),
        Column("piper_bin", String(1024), nullable=False, server_default=""),
        Column("piper_bundled_voice_dir", String(1024), nullable=False, server_default=""),
        Column("email_enabled", Boolean, nullable=False, server_default=false()),
        Column("audit_retention_days", Integer, nullable=False, server_default="365"),
        Column("public_url", String(500), nullable=False, server_default=""),
    )

    product_offer_table = Table(
        "ProductOffer", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("offered_on", DateTime(timezone=True)),
        Column("price_now", Float),
        Column("price_was", Float),
        Column("product_id", UUIDType, ForeignKey("Product.id", ondelete="CASCADE"), nullable=False),
    )

    product_historic_offer_table = Table(
        "ProductHistoricOffer", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("offered_on", DateTime(timezone=True)),
        Column("price_now", Float),
        Column("price_was", Float),
        Column("product_id", UUIDType, ForeignKey("Product.id", ondelete="CASCADE"), nullable=False),
        # provenance string. Nullable: historic points minted by
        # the pre-C-10 `create_product` path predate this column.
        Column("source", String(64), nullable=True),
    )

    product_table = Table(
        "Product", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("brand", String(255), nullable=True),
        Column("image", LargeBinary, nullable=True),
        Column("is_active", Boolean, nullable=False),
        Column("is_available", Boolean, nullable=False),
        Column("store_id", UUIDType, ForeignKey("Store.id", ondelete="RESTRICT"), nullable=False),
        # `merchant_stockcode` retained verbatim — it's the
        # producer's SKU code on the offer, not a reference to the renamed
        # entity. The runbook explicitly excludes it from the rename.
        Column("merchant_stockcode", String(255), nullable=True),
        Column("name", String(255), nullable=False),
        Column("size", String(255)),
        Column("size_unit", String(255)),
        Column("size_value", Float),
        Column("web_url", String(255), nullable=True),
        # Multipack metadata (FU-227 follow-up). NULL = single pack /
        # free-weight. ``size_value`` stays as the total measure of the
        # whole bundle (existing convention); pack_count is informational.
        Column("pack_count", Integer, nullable=True),
        # OD-2 — hand-entered product. Excluded from the ingestion sync list
        # and from ingest dedupe; see the entity for why both matter.
        Column("is_custom", Boolean, nullable=False, server_default=false()),
    )

    stock_group_table = Table(
        "StockGroup", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("name", String(255)),
    )

    stock_level_table = Table(
        "StockLevel", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("name", String(255)),
        Column("sequence", Integer),
    )

    stock_location_table = Table(
        "StockLocation", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("name", String(255), nullable=False),
        Column("kind", String(20), nullable=False, server_default="zone"),
        Column("parent_id", UUIDType, ForeignKey("StockLocation.id", ondelete="CASCADE"), nullable=True),
        Column("sequence", Integer, nullable=False, server_default="0"),
    )

    stock_item_table = Table(
        "StockItem", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("expiry_date", Date, nullable=True),
        Column("is_essential", Boolean, nullable=False, server_default=false()),
        Column("is_open", Boolean, nullable=False, server_default=false()),
        Column("opened_on", Date, nullable=True),
        Column("name", String(255)),
        Column("notes", String(255), nullable=True),
        Column("stock_group_id", UUIDType, ForeignKey("StockGroup.id", ondelete="SET NULL"), nullable=True),
        Column("stock_level_id", UUIDType, ForeignKey("StockLevel.id", ondelete="SET NULL"), nullable=True),
        Column("stock_level_last_updated", DateTime(timezone=True)),
        Column("stock_location_id", UUIDType, ForeignKey("StockLocation.id", ondelete="SET NULL"), nullable=True),
        Column("stocktake_alerts_are_enabled", Boolean),
        Column("last_checked_at", DateTime(timezone=True), nullable=True),
        # PROPOSAL_STOCKTAKE_MODE §5 — Push (3-day snooze). Queue filter
        # excludes items where snoozed_until > now. Indexed to keep the
        # filter cheap on big pantries.
        Column("snoozed_until", DateTime(timezone=True), nullable=True),
        # usual store hint. SET NULL on store delete so the item
        # survives the store going away (R-005 referential safety).
        Column("usual_store_id", UUIDType, ForeignKey("Store.id", ondelete="SET NULL"), nullable=True),
        # Nutrition complex-mode link. SET NULL so dropping/re-importing a
        # dataset can't cascade into the pantry (R-005 referential safety).
        Column(
            "nutrition_food_id", UUIDType,
            ForeignKey("NutritionFood.id", ondelete="SET NULL"), nullable=True,
        ),
        # "Never suggest a food for this one" — the opt-out behind the
        # auto-matcher. Indexed because the unmatched-items query filters on
        # it on every load of the matching page.
        Column(
            "nutrition_ignored", Boolean,
            nullable=False, server_default=false(), index=True,
        ),
    )

    # Nutrition catalogue — a cache of foods from the configured sources.
    # `(source, source_ref)` is unique so re-importing a dataset updates rows
    # in place rather than duplicating the catalogue. `name` and `barcode` are
    # indexed because every lookup keystroke hits one or the other.
    nutrition_food_table = Table(
        "NutritionFood", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("source", String(32), nullable=False, index=True),
        Column("source_ref", String(64), nullable=False),
        Column("name", String(512), nullable=False, index=True),
        Column("brand", String(255), nullable=True),
        Column("barcode", String(64), nullable=True, index=True),
        Column("kcal_per_100g", Float, nullable=True),
        Column("protein_g_per_100g", Float, nullable=True),
        Column("carbs_g_per_100g", Float, nullable=True),
        Column("sugars_g_per_100g", Float, nullable=True),
        Column("fat_g_per_100g", Float, nullable=True),
        Column("saturated_fat_g_per_100g", Float, nullable=True),
        Column("fibre_g_per_100g", Float, nullable=True),
        Column("sodium_mg_per_100g", Float, nullable=True),
        # The optional vitamins-and-minerals block (2026-08-17). Same shape as
        # the macros above — nullable, per 100g, unit in the name — and the
        # same authority: `features/nutrition/nutrients.py` decides which of
        # these exist and how each source names them.
        Column("trans_fat_g_per_100g", Float, nullable=True),
        Column("monounsaturated_fat_g_per_100g", Float, nullable=True),
        Column("polyunsaturated_fat_g_per_100g", Float, nullable=True),
        Column("cholesterol_mg_per_100g", Float, nullable=True),
        Column("potassium_mg_per_100g", Float, nullable=True),
        Column("calcium_mg_per_100g", Float, nullable=True),
        Column("iron_mg_per_100g", Float, nullable=True),
        Column("magnesium_mg_per_100g", Float, nullable=True),
        Column("zinc_mg_per_100g", Float, nullable=True),
        Column("vitamin_a_ug_per_100g", Float, nullable=True),
        Column("vitamin_c_mg_per_100g", Float, nullable=True),
        Column("vitamin_d_ug_per_100g", Float, nullable=True),
        Column("vitamin_e_mg_per_100g", Float, nullable=True),
        Column("vitamin_b12_ug_per_100g", Float, nullable=True),
        Column("folate_ug_per_100g", Float, nullable=True),
        Column("food_category", String(128), nullable=True),
        Column("imported_at", DateTime(timezone=True), nullable=True),
        UniqueConstraint("source", "source_ref", name="uq_nutrition_food_source_ref"),
    )

    # Household measures → gram weights, from USDA's `food_portion`. This is
    # what lets a recipe's "2 cups flour" become grams; without a matching row
    # an ingredient is reported unconvertible rather than guessed.
    nutrition_portion_table = Table(
        "NutritionPortion", metadata,
        Column("id", UUIDType, primary_key=True),
        Column(
            "nutrition_food_id", UUIDType,
            ForeignKey("NutritionFood.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        Column("amount", Float, nullable=False),
        Column("measure", String(255), nullable=False),
        Column("gram_weight", Float, nullable=False),
    )

    # hybrid `Barcode` table: real EANs can attach to a Product
    # (1:1, the catalogue case) AND/OR a StockItem (m:n, the
    # lightweight-install + direct-registration case). At least one of the
    # two FKs must be set; both being set is fine and useful (the same
    # row carries both linkages). See `domain/entities/barcode.py` for
    # the full semantics. Replaces the old Product-only `ProductBarcode`.
    barcode_table = Table(
        "Barcode", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("barcode", String(255), nullable=False, unique=True),
        Column(
            "product_id", UUIDType,
            ForeignKey("Product.id", ondelete="CASCADE"),
            nullable=True, unique=True,
        ),
        Column(
            "stock_item_id", UUIDType,
            ForeignKey("StockItem.id", ondelete="CASCADE"),
            nullable=True,
        ),
        Column("created_at", DateTime(timezone=True), nullable=False),
        CheckConstraint(
            "product_id IS NOT NULL OR stock_item_id IS NOT NULL",
            name="ck_barcode_target_at_least_one",
        ),
    )

    price_alert_table = Table(
        "PriceAlert", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("user_id", UUIDType, ForeignKey("User.id", ondelete="CASCADE"), nullable=False),
        Column("product_id", UUIDType, ForeignKey("Product.id", ondelete="CASCADE"), nullable=False),
        Column("threshold_unit_price", Float, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )

    audit_event_table = Table(
        "AuditEvent", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("occurred_at", DateTime(timezone=True), nullable=False),
        Column("source", String(16), nullable=False),
        Column("actor_user_id", UUIDType, nullable=True),
        Column("actor_ip", String(64), nullable=True),
        Column("action", String(128), nullable=False),
        Column("entity_type", String(64), nullable=True),
        Column("entity_id", UUIDType, nullable=True),
        Column("request_id", String(64), nullable=True),
        Column("payload", String, nullable=True),
        Column("severity", String(16), nullable=False),
    )

    shopping_list_table = Table(
        "ShoppingList", metadata,
        Column("id", UUIDType, primary_key=True),
        # NULL = no custom name; the API serves a date-derived display_name
        # (UX-v2 — custom name is clearable, lists self-label from dates).
        Column("name", String(255), nullable=True),
        # replaces the old
        # is_archived / is_in_progress flag pair. "Primary" is inferred from
        # DRAFT-count at read time (Chunk 2), not stored.
        Column("status", String(16), nullable=False, server_default="draft"),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("completed_at", DateTime(timezone=True), nullable=True),
        # Optional shop day the user is planning this list
        # for. Nullable because most lists don't have one — null reads as
        # "no shop day set", not "today".
        Column("planned_shop_date", Date, nullable=True),
    )

    shopping_list_line_table = Table(
        "ShoppingListLine", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("shopping_list_id", UUIDType, ForeignKey("ShoppingList.id", ondelete="CASCADE"), nullable=False),
        # a line is anchored by `stock_item_id` OR
        # `product_id` (or both, when a product is nested under a
        # stock item). Both columns are nullable individually; a
        # CHECK enforces that at least one is set.
        # Both anchors are SET NULL, not CASCADE (FU-883). A finished list is
        # a receipt: deleting a stock item or product must not reach back and
        # erase what you bought, for the same reason `purchased_store_id`
        # below has always been SET NULL. Lines on *draft/shopping* lists are
        # still removed when their anchor goes — that's done in the delete
        # handlers (`shopping_lists._line_retention`), because a FK rule can't
        # be conditional on the parent list's status.
        Column("stock_item_id", UUIDType, ForeignKey("StockItem.id", ondelete="SET NULL"), nullable=True),
        Column("product_id", UUIDType, ForeignKey("Product.id", ondelete="SET NULL"), nullable=True),
        # The display name frozen at finish. Lets an orphaned historic line
        # still say what it was.
        Column("display_name_snapshot", String(255), nullable=True),
        # A live line needs an anchor; a finished one may instead carry only
        # its snapshot. Without the third clause, nulling the last anchor of a
        # product-only line would violate this and the delete would fail —
        # loudly on Postgres, silently on SQLite (which doesn't enforce FKs
        # by default).
        CheckConstraint(
            "stock_item_id IS NOT NULL OR product_id IS NOT NULL "
            "OR display_name_snapshot IS NOT NULL",
            name="ck_shopping_list_line_anchor",
        ),
        Column("quantity", Integer, nullable=True),
        Column("is_ticked", Boolean, nullable=False, server_default=false()),
        Column("selected_product_id", UUIDType, ForeignKey("Product.id", ondelete="SET NULL"), nullable=True),
        Column("sequence", Integer, nullable=False, server_default="0"),
        Column("is_auto_added", Boolean, nullable=False, server_default=false()),
        Column("added_at", DateTime(timezone=True), nullable=True),
        Column("picked_offer_price", Float, nullable=True),
        Column("list_price_at_pick", Float, nullable=True),
        # what the shopper actually paid / where
        # they bought it. NULL when the user didn't override the planned
        # offer; reports & the assistant fall back to picked_offer_price.
        Column("actual_unit_price", Float, nullable=True),
        Column(
            "purchased_store_id", UUIDType,
            ForeignKey("Store.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # where the user *plans* to buy this line, as opposed to
        # `purchased_store_id` above, which is where they did. SET NULL on
        # store delete for the same reason: losing a store must not take the
        # line with it.
        Column(
            "planned_store_id", UUIDType,
            ForeignKey("Store.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # optional PreferredBuy hint. Plain UUID, NO ForeignKey:
        # adding an FK to ShoppingListLine in SQLite batch mode breaks the
        # migration path; SQLite doesn't enforce FKs anyway, and a dangling
        # id after a PreferredBuy delete is tolerated (the SPA shows no hint).
        Column("preferred_buy_id", UUIDType, nullable=True),
        # trim-to-budget optimiser. True when the line was set
        # aside by the "Trim to fit" pass (PROPOSAL_BUDGET_AWARE_LISTS §7.2).
        # `deferred_reason` freezes the chip vocab (brief §5) at trim time.
        Column("deferred_by_budget", Boolean, nullable=False, server_default=false()),
        Column("deferred_reason", String(64), nullable=True),
    )

    # receipt-photo record-keeping. One row per attached photo on a
    # shopping list (status='shopping' or 'done'). Image blob is the same
    # `data:image/...;base64,...` UTF-8 bytes shape as Recipe.image /
    # RecipeStepImage (so processImageFile → server → bytes endpoint stays
    # identical across upload sites). Deferred at the mapper so detail reads
    # never inline blob bytes.
    shopping_list_attachment_table = Table(
        "ShoppingListAttachment", metadata,
        Column("id", UUIDType, primary_key=True),
        Column(
            "shopping_list_id", UUIDType,
            ForeignKey("ShoppingList.id", ondelete="CASCADE"),
            nullable=False,
        ),
        Column("sequence", Integer, nullable=False, server_default="0"),
        Column("image", LargeBinary, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )

    shopping_list_template_table = Table(
        "ShoppingListTemplate", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("name", String(255), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )

    shopping_list_template_line_table = Table(
        "ShoppingListTemplateLine", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("template_id", UUIDType, ForeignKey("ShoppingListTemplate.id", ondelete="CASCADE"), nullable=False),
        Column("stock_item_id", UUIDType, ForeignKey("StockItem.id", ondelete="CASCADE"), nullable=False),
        Column("quantity", Integer, nullable=True),
        Column("sequence", Integer, nullable=False, server_default="0"),
        Column("selected_product_id", UUIDType, ForeignKey("Product.id", ondelete="SET NULL"), nullable=True),
        # Plain UUID, no FK, for the same reason as `ShoppingListLine`'s.
        Column("preferred_buy_id", UUIDType, nullable=True),
    )

    # the m:n relation is asymmetric: many Products can satisfy
    # one StockItem (e.g. Coles + Pauls + Vitasoy all linked to "Milk"),
    # but a Product satisfies exactly one StockItem (a specific SKU has a
    # specific pantry purpose). `UNIQUE(product_id)` enforces the second
    # half. Drops the lookup ambiguity that `product_multi_linked` was
    # papering over: barcode → Product → at most one StockItem.
    stock_item_product_table = Table(
        "StockItemProduct", metadata,
        Column("stock_item_id", UUIDType, ForeignKey("StockItem.id", ondelete="CASCADE"), primary_key=True),
        Column("product_id", UUIDType, ForeignKey("Product.id", ondelete="CASCADE"), primary_key=True),
        UniqueConstraint("product_id", name="uq_stock_item_product_product_id"),
    )

    # Self-referential m2m: a stock item's substitutes. Undirected — pairs
    # are stored in canonical order (a_id < b_id) so each unordered pair has
    # exactly one row. Callers must canonicalise via `canonical_pair()` from
    # dora_api.features.substitutes.canonical before insert/delete/query.
    # CASCADE both FKs so deleting an item cleans up its pairs.
    stock_item_substitute_table = Table(
        "StockItemSubstitute", metadata,
        Column("stock_item_a_id", UUIDType, ForeignKey("StockItem.id", ondelete="CASCADE"), primary_key=True),
        Column("stock_item_b_id", UUIDType, ForeignKey("StockItem.id", ondelete="CASCADE"), primary_key=True),
        # free-text hint ("don't use in baking", "1:1 in soups", …).
        # Bounded to 255 chars at the API layer; column stays untyped-length
        # because the original migration set it that way.
        Column("notes", String, nullable=True),
        # optional structured ratio, all-or-none (DB CHECK + API
        # validation). Stored in the canonical A→B direction; readers (e.g.
        # get_stock_item_detail) invert when displaying from B's side.
        Column("ratio_quantity_in", Float, nullable=True),
        Column("ratio_unit_in", String(32), nullable=True),
        Column("ratio_quantity_out", Float, nullable=True),
        Column("ratio_unit_out", String(32), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        CheckConstraint("stock_item_a_id < stock_item_b_id", name="ck_substitute_canonical"),
        CheckConstraint(
            "(ratio_quantity_in IS NULL AND ratio_unit_in IS NULL "
            " AND ratio_quantity_out IS NULL AND ratio_unit_out IS NULL) "
            "OR (ratio_quantity_in IS NOT NULL AND ratio_unit_in IS NOT NULL "
            " AND ratio_quantity_out IS NOT NULL AND ratio_unit_out IS NOT NULL)",
            name="ck_substitute_ratio_all_or_none",
        ),
    )

    stock_level_change_table = Table(
        "StockLevelChange", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("stock_item_id", UUIDType, ForeignKey("StockItem.id", ondelete="CASCADE"), nullable=False),
        Column("stock_level_id", UUIDType, ForeignKey("StockLevel.id", ondelete="SET NULL"), nullable=True),
        Column("stock_level_name", String(255), nullable=True),
        Column("changed_at", DateTime(timezone=True), nullable=False),
    )

    # free-text "what I actually buy" reminders on a stock item
    # (PROPOSAL_PRODUCTS_AS_OVERLAY §3.1). Owned child rows; CASCADE when the
    # stock item is deleted. FU-225 dropped the `position` column — manual
    # reorder retired; SPA sorts alphabetically client-side.
    preferred_buy_table = Table(
        "PreferredBuy", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("stock_item_id", UUIDType, ForeignKey("StockItem.id", ondelete="CASCADE"), nullable=False),
        Column("label", String(255), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )

    # reshaped from FU-213. Folded `{total_price, total_measure,
    # unit}` (A1); nullable `store_id` (A2 — "Last seen at Coles"); nullable
    # `shopping_list_line_id` provenance FK (A4 revised — replaces the old
    # `source` enum). Partial UNIQUE on the FK lives in the Alembic migration
    # (LC-1 — makes /finish harvest idempotent under double-tap). CASCADE with
    # the stock item; SET NULL when the linked line or store is deleted
    # (provenance is lossy, not load-bearing).
    stock_item_price_observation_table = Table(
        "StockItemPriceObservation", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("stock_item_id", UUIDType, ForeignKey("StockItem.id", ondelete="CASCADE"), nullable=False),
        Column("total_price", Float, nullable=False),
        Column("total_measure", Float, nullable=False),
        Column("unit", String(32), nullable=False),
        Column("observed_at", DateTime(timezone=True), nullable=False),
        Column("store_id", UUIDType, ForeignKey("Store.id", ondelete="SET NULL"), nullable=True),
        Column("shopping_list_line_id", UUIDType, ForeignKey("ShoppingListLine.id", ondelete="SET NULL"), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        # Multipack metadata (FU-227 follow-up). NULL = single pack /
        # free-weight. ``total_measure`` stays as the total the user got;
        # pack_count is informational so the obs row can render
        # "4 × 125g" instead of "500g flat".
        Column("pack_count", Integer, nullable=True),
    )

    # user's negative decisions on Dora suggestions. One row per
    # (kind, dedup_key) the user has dismissed or snoozed. The generator
    # filters proposed suggestions against this table on every call.
    dora_suggestion_suppression_table = Table(
        "DoraSuggestionSuppression", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("kind", String(64), nullable=False),
        Column("dedup_key", String(255), nullable=False),
        Column("decision", String(16), nullable=False),
        Column("snoozed_until", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )

    # per-user interaction state for derived alerts (read / snooze /
    # dismiss). One row per (user_id, alert_key); absence = untouched. The
    # alerts themselves are never stored — only the user's decisions.
    alert_interaction_table = Table(
        "AlertInteraction", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("user_id", UUIDType, nullable=False),
        Column("alert_key", String(255), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("snoozed_until", DateTime(timezone=True), nullable=True),
        Column("dismissed_at", DateTime(timezone=True), nullable=True),
        # web-push delivery dedup. (The email-digest sibling
        # `last_emailed_at` went with the digest itself — Step-0 Q4.)
        Column("last_pushed_at", DateTime(timezone=True), nullable=True),
    )

    # one row per browser+device push registration (PROPOSAL_
    # ALERTS §3.5 / §4.4). `endpoint` is unique — the same browser
    # re-subscribing produces the same endpoint, so the API does an
    # upsert keyed on it. Capped string length covers the longest
    # endpoints in the wild (Mozilla / FCM / Apple are all <500 chars).
    push_subscription_table = Table(
        "PushSubscription", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("user_id", UUIDType, nullable=False),
        Column("endpoint", String(500), nullable=False, unique=True),
        Column("p256dh", String(255), nullable=False),
        Column("auth", String(64), nullable=False),
        Column("user_agent", String(255), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("last_seen_at", DateTime(timezone=True), nullable=True),
    )

    # per-user, per-kind alert preference (enable/disable + tier
    # override). One row per (user_id, kind); absence = default (enabled +
    # the kind's default tier, PROPOSAL_ALERTS §5).
    alert_preference_table = Table(
        "AlertPreference", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("user_id", UUIDType, nullable=False),
        Column("kind", String(64), nullable=False),
        Column("enabled", Boolean, nullable=False, server_default=true()),
    )

    # per-user LLM-provider config. One row per (user_id, provider) —
    # a user configures several providers and flips the active one via
    # `User.llm_provider`. Single source of truth for provider details;
    # `verified` is flipped True only by a successful live probe and reset
    # by any edit. `api_key_encrypted` is Fernet ciphertext, deferred at
    # the mapper (same shape as `User.image`) so list reads don't haul it.
    user_llm_provider_table = Table(
        "UserLlmProvider", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("user_id", UUIDType, ForeignKey("User.id", ondelete="CASCADE"), nullable=False),
        Column("provider", String(16), nullable=False),
        Column("base_url", String(500), nullable=True),
        Column("model", String(255), nullable=True),
        Column("api_key_encrypted", LargeBinary, nullable=True),
        Column("verified", Boolean, nullable=False, server_default=false()),
        Column("verified_at", DateTime(timezone=True), nullable=True),
        UniqueConstraint("user_id", "provider", name="uq_user_llm_provider_user_provider"),
    )

    # C-waste — append-only log of discarded food. FK is SET NULL (not
    # CASCADE) so deleting a stock item doesn't wipe waste history; the
    # denormalised name on the row keeps insights readable. Capture is
    # reason-only (no quantity/value/note) per PROPOSAL_WASTE_MINIMISATION.
    stock_item_waste_event_table = Table(
        "StockItemWasteEvent", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("stock_item_id", UUIDType, ForeignKey("StockItem.id", ondelete="SET NULL"), nullable=True),
        Column("stock_item_name", String(255), nullable=False),
        Column("reason", String(32), nullable=False),
        Column("occurred_at", DateTime(timezone=True), nullable=False),
    )

    # History-tab feed — "the user cooked this recipe today." Written by
    # POST /recipes/<id>/cook alongside the Recipe.available_meals bump.
    # FKs are SET NULL so deleting a recipe / user leaves the historical
    # timeline entries readable via the denormalised `recipe_name`.
    cook_event_table = Table(
        "CookEvent", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("recipe_id", UUIDType, ForeignKey("Recipe.id", ondelete="SET NULL"), nullable=True),
        Column("recipe_name", String(255), nullable=False),
        Column("meals_cooked", Integer, nullable=False),
        Column("cooked_by_user_id", UUIDType, ForeignKey("User.id", ondelete="SET NULL"), nullable=True),
        Column("occurred_at", DateTime(timezone=True), nullable=False),
    )

    # append-only log of a stock item being drawn DOWN
    # (by cooking, manual level-drop, or waste). The missing depletion leg
    # of the loop: purchases record intake, this records outflow, so
    # run-out prediction + the P8-07 belief blend consumption rhythm with
    # purchase rhythm. FKs SET NULL so history survives item/recipe delete;
    # denormalised names keep rows legible. See entity docstring.
    consumption_event_table = Table(
        "ConsumptionEvent", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("stock_item_id", UUIDType, ForeignKey("StockItem.id", ondelete="SET NULL"), nullable=True),
        Column("stock_item_name", String(255), nullable=False),
        Column("recipe_id", UUIDType, ForeignKey("Recipe.id", ondelete="SET NULL"), nullable=True),
        Column("recipe_name", String(255), nullable=True),
        Column("source", String(16), nullable=False),
        Column("from_sequence", Integer, nullable=True),
        Column("to_sequence", Integer, nullable=True),
        Column("occurred_at", DateTime(timezone=True), nullable=False),
    )

    # persisted backup library. One row per generated backup;
    # `storage_path` points at the file on disk. See entity docstring.
    backup_table = Table(
        "Backup", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("created_by_user_id", UUIDType, ForeignKey("User.id", ondelete="SET NULL"), nullable=True),
        Column("size_bytes", BigInteger, nullable=False),
        # JSON-encoded list[str] of section backup_keys this file carries.
        Column("sections", Text, nullable=False),
        Column("sha256", String(64), nullable=False),
        Column("status", String(16), nullable=False),
        Column("trigger_kind", String(16), nullable=False),
        Column("storage_path", String(1024), nullable=False),
    )

    # History-tab feed — "the user set / pushed / cleared this item's
    # expiry date." Written by create_stock_item + update_stock_item on
    # every date transition. FK is SET NULL so history survives item
    # deletion.
    stock_item_expiry_event_table = Table(
        "StockItemExpiryEvent", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("stock_item_id", UUIDType, ForeignKey("StockItem.id", ondelete="SET NULL"), nullable=True),
        Column("kind", String(16), nullable=False),
        Column("previous_expiry_date", Date, nullable=True),
        Column("new_expiry_date", Date, nullable=True),
        Column("delta_days", Integer, nullable=True),
        Column("occurred_at", DateTime(timezone=True), nullable=False),
    )

    recipe_collection_table = Table(
        "RecipeCollection", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("name", String(255), nullable=False),
    )

    # user-configurable recipe vocabularies (cuisine, category,
    # dietary tags). Each is a simple {id, name, sequence} lookup edited in
    # settings; recipes link to them by FK (cuisine/category single-select,
    # dietary tags many-to-many).
    cuisine_table = Table(
        "Cuisine", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("name", String(255), nullable=False),
        Column("sequence", Integer, nullable=False, server_default="0"),
    )

    category_table = Table(
        "Category", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("name", String(255), nullable=False),
        Column("sequence", Integer, nullable=False, server_default="0"),
    )

    dietary_tag_table = Table(
        "DietaryTag", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("name", String(255), nullable=False),
        Column("category", String(255), nullable=False),
        Column("sequence", Integer, nullable=False, server_default="0"),
    )

    # user-configurable kitchen-tool vocabulary.
    tool_table = Table(
        "Tool", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("name", String(255), nullable=False),
        Column("sequence", Integer, nullable=False, server_default="0"),
    )

    # household-wide meal-slot vocabulary. Same {id, name, sequence}
    # lookup shape as the recipe vocabs, but NOT an FK target:
    # `MealPlanEntry.slot` / `Recipe.time_of_day` hold the slot name as free
    # text, validated against this table at write-time. Deleting a row leaves
    # those labels intact (no cascade).
    meal_slot_table = Table(
        "MealSlot", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("name", String(255), nullable=False),
        Column("sequence", Integer, nullable=False, server_default="0"),
    )

    recipe_table = Table(
        "Recipe", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("available_meals", Integer, nullable=False, server_default="0"),
        Column("category_id", UUIDType, ForeignKey("Category.id", ondelete="SET NULL"), nullable=True),
        Column("cook_time_minutes", Integer, nullable=True),
        Column("cuisine_id", UUIDType, ForeignKey("Cuisine.id", ondelete="SET NULL"), nullable=True),
        Column("difficulty", String(50), nullable=True),
        Column("image", LargeBinary, nullable=True),
        Column("instructions", String, nullable=True),
        Column("is_favourite", Boolean, nullable=False),
        # R-021 — "last made on" is a calendar day (the household's), not a
        # wall-clock instant. Stored as Date; the time portion was always
        # meaningless. Migration `9f3a2c6e1b08` truncates legacy datetimes.
        Column("last_made_on", Date, nullable=True),
        Column("name", String(255), nullable=False),
        Column("prep_time_minutes", Integer, nullable=True),
        Column("recipe_collection_id", UUIDType, ForeignKey("RecipeCollection.id", ondelete="SET NULL"), nullable=True),
        Column("servings", Integer, nullable=True),
        # origin URL for imported recipes.
        Column("source", String(2048), nullable=True),
        Column("time_of_day", String(50), nullable=True),
        # version sibling grouping (DEC-2). NULL = singleton.
        # Indexed because every detail load asks "who else has this id?".
        Column("version_group_id", UUIDType, nullable=True, index=True),
        # simple nutrition (kcal). NULL when unset.
        Column("kcal", Integer, nullable=True),
        # PROPOSAL_RECIPE_IMAGE_STEPS — explicit steps payload selector
        # ('structured' | 'freeform' | 'image'). Server-default 'freeform'
        # so new recipes start in the dumbest mode; backfill migration
        # promotes existing recipes with RecipeStep rows to 'structured'.
        Column("steps_mode", String(16), nullable=False, server_default="freeform"),
        # when the recipe row was added to this household. Powers
        # the cookbook "Recently added" sort axis (IMPL_PLAN_COOKBOOK
        # Chunk 1's missing fifth axis). The create handlers stamp this at
        # write time; historical rows were backfilled from last_made_on
        # (else now()) by migration f9d3a7c2b5e8.
        Column("created_at", DateTime(timezone=True), nullable=False),
        # when the recipe was last edited (PATCH /recipes/<id>). NULL until the
        # first edit; the recipe page's version-information panel prints it
        # next to created_at.
        Column("updated_at", DateTime(timezone=True), nullable=True),
        # RD-29 — free-text personal notes (the cook's own commentary, shown
        # in cook mode under the steps). Distinct from `instructions`.
        Column("notes", Text, nullable=True),
    )

    # recipe → dietary-tag association. The tag vocabulary is
    # now the `DietaryTag` entity (was an in-code catalogue); this table pins
    # which tag(s) belong to a recipe. No standalone mapping is registered
    # (matching the StockItemProduct/StockItemSubstitute pattern); handlers
    # read/write rows via the recipe_tag_access helpers.
    recipe_tag_table = Table(
        "RecipeTag", metadata,
        Column("recipe_id", UUIDType, ForeignKey("Recipe.id", ondelete="CASCADE"), primary_key=True),
        Column("dietary_tag_id", UUIDType, ForeignKey("DietaryTag.id", ondelete="CASCADE"), primary_key=True),
    )

    # recipe → tool association (pure link, no standalone
    # mapping; accessed via recipe_tool_access helpers).
    recipe_tool_table = Table(
        "RecipeTool", metadata,
        Column("recipe_id", UUIDType, ForeignKey("Recipe.id", ondelete="CASCADE"), primary_key=True),
        Column("tool_id", UUIDType, ForeignKey("Tool.id", ondelete="CASCADE"), primary_key=True),
    )

    # named groups within a recipe (DEC-3 option A). Optional;
    # ingredients/steps with NULL section_id are the implicit "main" group.
    recipe_section_table = Table(
        "RecipeSection", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("recipe_id", UUIDType, ForeignKey("Recipe.id", ondelete="CASCADE"), nullable=False),
        Column("sequence", Integer, nullable=False, server_default="0"),
        Column("name", String(255), nullable=False),
    )

    recipe_ingredient_table = Table(
        "RecipeIngredient", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("notes", String(255), nullable=True),
        Column("quantity", Float, nullable=True),
        Column("recipe_id", UUIDType, ForeignKey("Recipe.id", ondelete="CASCADE"), nullable=False),
        # IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 — nullable so unlinked rows
        # (parser couldn't fuzzy-match a StockItem) persist. The FK stays
        # ondelete=RESTRICT: for LINKED rows, deleting the StockItem still
        # blocks; unlinked rows have NULL and don't touch the FK. The
        # anchor CHECK below requires at least one of stock_item_id /
        # raw_text to be set per row.
        Column("stock_item_id", UUIDType, ForeignKey("StockItem.id", ondelete="RESTRICT"), nullable=True),
        Column("unit", String(50), nullable=True),
        # nullable section grouping (ON DELETE SET NULL so
        # removing a section keeps its ingredients, just unsectioned).
        Column("section_id", UUIDType, ForeignKey("RecipeSection.id", ondelete="SET NULL"), nullable=True),
        # Cookbook revision §1.9 — optional ingredients are ignored by the
        # cookability rule (no second cookable value). Server-default `0`
        # keeps existing rows valid through the migration.
        Column("is_optional", Boolean, nullable=False, server_default=false()),
        # IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 — the ingredient text as the
        # user pasted / imported it. Backfilled from ``StockItem.name`` for
        # pre-Chunk-4 rows so labels survive unlinking / renaming.
        Column("raw_text", String(500), nullable=True),
        # Which one of the stock item the recipe means (see the entity).
        Column("label", String(255), nullable=True),
        Column("preferred_buy_id", UUIDType, nullable=True),
        Column("selected_product_id", UUIDType, ForeignKey("Product.id", ondelete="SET NULL"), nullable=True),
        CheckConstraint(
            "stock_item_id IS NOT NULL OR raw_text IS NOT NULL",
            name="recipe_ingredient_anchor",
        ),
    )

    # structured recipe steps. Self-referential `parent_step_id`
    # enables one level of sub-steps (a sub-step's parent must itself be a
    # top-level step; depth>1 is rejected in the access helper). Two link
    # tables: which of the recipe's own ingredients this step uses, and which
    # tools (from the Chunk 5 vocabulary). Both are pure (step_id, x_id) pairs
    # accessed via the `recipe_step_access` helpers — no standalone mapping.
    recipe_step_table = Table(
        "RecipeStep", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("recipe_id", UUIDType, ForeignKey("Recipe.id", ondelete="CASCADE"), nullable=False),
        Column("parent_step_id", UUIDType, ForeignKey("RecipeStep.id", ondelete="CASCADE"), nullable=True),
        Column("sequence", Integer, nullable=False, server_default="0"),
        Column("text", String, nullable=False),
        Column("hint", String, nullable=True),
        # nullable section grouping. Top-level steps may
        # belong to a section; sub-steps inherit visually but the FK is
        # stored per-row to keep reads flat.
        Column("section_id", UUIDType, ForeignKey("RecipeSection.id", ondelete="SET NULL"), nullable=True),
        # Owner feedback 2026-09-01 — an explicit per-step timer, in minutes.
        # NULL means "no timer declared"; cook mode then falls back to sniffing
        # the step text, which is all a free-text method can ever offer.
        Column("timer_minutes", Integer, nullable=True),
    )

    recipe_step_ingredient_table = Table(
        "RecipeStepIngredient", metadata,
        Column("step_id", UUIDType, ForeignKey("RecipeStep.id", ondelete="CASCADE"), primary_key=True),
        Column("recipe_ingredient_id", UUIDType, ForeignKey("RecipeIngredient.id", ondelete="CASCADE"), primary_key=True),
    )

    recipe_step_tool_table = Table(
        "RecipeStepTool", metadata,
        Column("step_id", UUIDType, ForeignKey("RecipeStep.id", ondelete="CASCADE"), primary_key=True),
        Column("tool_id", UUIDType, ForeignKey("Tool.id", ondelete="CASCADE"), primary_key=True),
    )

    # PROPOSAL_RECIPE_IMAGE_STEPS — ordered photo-mode step images. One row
    # per uploaded image; `sequence` orders them. Image blob is the same
    # `data:image/...;base64,...` UTF-8 bytes shape as Recipe.image (so the
    # client picker -> server -> bytes-endpoint pipeline is identical
    # across upload sites). Deferred at the mapper so the list/detail
    # endpoints never inline blob bytes.
    recipe_step_image_table = Table(
        "RecipeStepImage", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("recipe_id", UUIDType, ForeignKey("Recipe.id", ondelete="CASCADE"), nullable=False),
        Column("sequence", Integer, nullable=False, server_default="0"),
        Column("image", LargeBinary, nullable=False),
    )

    meal_plan_table = Table(
        "MealPlan", metadata,
        Column("id", UUIDType, primary_key=True),
        # instances are nameless (UI shows "Week starting <date>").
        Column("name", String(255), nullable=True),
        Column("start_date", Date, nullable=False),
        # provenance only (plain ids, no DB FK; see entity).
        Column("source_template_id", UUIDType, nullable=True),
        Column("source_template_set_id", UUIDType, nullable=True),
        Column("rotation_index", Integer, nullable=True),
    )

    # FU-451 — append-only ledger of applied budget-defense swaps (undo trail).
    meal_plan_swap_ledger_table = Table(
        "MealPlanSwapLedger", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("meal_plan_id", UUIDType, ForeignKey("MealPlan.id", ondelete="CASCADE"), nullable=False),
        Column("applied_by_user_id", UUIDType, ForeignKey("User.id", ondelete="SET NULL"), nullable=True),
        Column("applied_at", DateTime(timezone=True), nullable=False),
        Column("kind", String(16), nullable=False),
        Column("payload_json", Text, nullable=False),
        Column("undone", Boolean, nullable=False, server_default=false()),
        Column("undone_at", DateTime(timezone=True), nullable=True),
    )

    # FU-317 Chunk 1 — append-only reconcile-receipt table. One row per
    # reconcile event per MealPlanEntry; states in
    # `domain.entities.meal_plan_reconcile_receipt.RECONCILE_STATE_VALUES`.
    # Never mutated in place; corrective decisions write a new row against
    # the same entry (same idiom as MealPlanSwapLedger above).
    meal_plan_reconcile_receipt_table = Table(
        "MealPlanReconcileReceipt", metadata,
        Column("id", UUIDType, primary_key=True),
        Column(
            "meal_plan_entry_id", UUIDType,
            ForeignKey("MealPlanEntry.id", ondelete="CASCADE"),
            nullable=False,
        ),
        Column("state", String(32), nullable=False),
        Column("original_servings", Integer, nullable=False),
        Column("actual_servings", Integer, nullable=True),
        Column("cooked_on", Date, nullable=True),
        Column(
            "resolved_by_user_id", UUIDType,
            ForeignKey("User.id", ondelete="SET NULL"),
            nullable=True,
        ),
        Column("resolved_at", DateTime(timezone=True), nullable=True),
        Column("note", Text, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )

    # PROPOSAL_MEAL_PLANS_PART_2 — a planned single cook feeding several linked
    # entries (same recipe + slot, distinct days). Thin by design: cook-day /
    # total yield / span are derived from the entries, never stored. Plan-scoped
    # (CASCADE with the week); the recipe FK is the integrity anchor.
    cook_batch_table = Table(
        "CookBatch", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("meal_plan_id", UUIDType, ForeignKey("MealPlan.id", ondelete="CASCADE"), nullable=False),
        Column("recipe_id", UUIDType, ForeignKey("Recipe.id", ondelete="CASCADE"), nullable=False),
    )

    meal_plan_entry_table = Table(
        "MealPlanEntry", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("recipe_id", UUIDType, ForeignKey("Recipe.id", ondelete="CASCADE"), nullable=False),
        Column("meal_plan_id", UUIDType, ForeignKey("MealPlan.id", ondelete="CASCADE"), nullable=False),
        Column("scheduled_for", Date, nullable=False),
        Column("servings", Integer, nullable=False, server_default="1"),
        Column("slot", String(50), nullable=False),
        Column("consumed_at", DateTime(timezone=True), nullable=True),
        # PROPOSAL_MEAL_PLANS_PART_2 — links this meal to a shared CookBatch.
        # SET NULL: deleting a batch un-links its meals rather than deleting them.
        Column("cook_batch_id", UUIDType, ForeignKey("CookBatch.id", ondelete="SET NULL"), nullable=True),
        # Owner 2026-09-04 — this meal is cooked on the day, outside the pool.
        Column("cook_fresh", Boolean, nullable=False, server_default=false()),
    )

    meal_plan_template_table = Table(
        "MealPlanTemplate", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("name", String(255), nullable=False),
        Column("description", String(2000), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )

    meal_plan_template_entry_table = Table(
        "MealPlanTemplateEntry", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("template_id", UUIDType, ForeignKey("MealPlanTemplate.id", ondelete="CASCADE"), nullable=False),
        Column("recipe_id", UUIDType, ForeignKey("Recipe.id", ondelete="CASCADE"), nullable=False),
        Column("offset_from_monday", Integer, nullable=False),
        Column("slot", String(50), nullable=False),
        Column("servings", Integer, nullable=False, server_default="1"),
    )

    meal_plan_template_set_table = Table(
        "MealPlanTemplateSet", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("name", String(255), nullable=False),
        Column("description", String(2000), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )

    meal_plan_template_set_item_table = Table(
        "MealPlanTemplateSetItem", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("set_id", UUIDType, ForeignKey("MealPlanTemplateSet.id", ondelete="CASCADE"), nullable=False),
        # Plain id (no DB FK) so deleting a template doesn't blow up a set row;
        # the set CRUD validates membership at write-time instead.
        Column("template_id", UUIDType, nullable=False),
        Column("position", Integer, nullable=False, server_default="0"),
    )

    user_table = Table(
        "User", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("email", String(255), nullable=True),
        Column("password_hash", String(255), nullable=True),
        Column("send_deals_on_day", Integer),
        # NOT NULL + unique here is the intended model, and the app enforces both
        # on insert — but the PROD (migrated) column is deliberately left nullable
        # and non-unique: the `add_user_auth` migration (4b1d9c2e7a31) couldn't
        # safely rewrite pre-existing rows in place. This is a documented, tracked
        # drift (FU-564) — `test_migrations.py` allowlists `User.username` in
        # `_KNOWN_NULLABILITY_DRIFT` / `_KNOWN_UNIQUE_DRIFT` so it can't grow.
        Column("username", String(255), nullable=False, unique=True),
        Column("is_admin", Boolean, nullable=False, default=False, server_default=false()),
        # Deactivate-instead-of-delete (owner, 2026-08-17). Default TRUE so
        # every existing row — and every future insert that doesn't mention
        # it — is a normal, usable account; only an explicit admin action
        # switches it off. See the entity comment for where it's enforced.
        Column("is_active", Boolean, nullable=False, default=True, server_default=true()),
        # Opt-in — a fresh install has no SMTP,
        # so nobody should land pre-subscribed to mail the server can't send.
        # (Was `true()` to carry pre-existing subscribers over the column's
        # introducing migration; pre-release, that no longer applies.)
        Column("deals_email_enabled", Boolean, nullable=False, server_default=false()),
        Column("deals_email_compact", Boolean, nullable=False, server_default=false()),
        Column("theme", String(20), nullable=False, server_default="system"),
        Column("font_family", String(20), nullable=False, server_default="default"),
        Column("font_size", String(2), nullable=False, server_default="md"),
        # wall-clock event; the `timezone=True` flag was missing
        # so DoraJSONProvider had to retag naive reads as UTC. Now declared
        # consistently with every other wall-clock column (R-021).
        Column("onboarding_completed_at", DateTime(timezone=True), nullable=True),
        Column("email_verified", Boolean, nullable=False, server_default=false()),
        Column("password_changed_at", DateTime(timezone=True), nullable=True),
        # grocery budget moved off User to AppSetting (install-wide household
        # budget — spend is shared, so the target must be too).
        # voice opt-ins. Off by default; SPA seeds the in-page
        # toggles from these and the user can override per session.
        Column("voice_input_enabled", Boolean, nullable=False, server_default=false()),
        Column("voice_output_enabled", Boolean, nullable=False, server_default=false()),
        # Voice engine ('browser' | 'piper') + Piper voice id. Default piper/amy
        # — Dora uses the bundled neural voice when available, browser fallback
        # otherwise (resolved client-side).
        Column("voice_engine", String(16), nullable=False, server_default="piper"),
        Column("voice_id", String(32), nullable=False, server_default="amy"),
        # money opt-in removed: money is a single install-wide flag
        # (AppSetting.money_enabled); there is no per-user money layer.
        # FU-615 — `batch_features_enabled` moved off User to AppSetting
        # (install-wide cook-style; a household has one cook-style).
        # Zero-Input Pantry opt-out. Default True (inference is the
        # headline experience); users switch it off for purely manual levels.
        Column("inferred_pantry_enabled", Boolean, nullable=False, server_default=true()),
        # D-12 — moved off AppSetting 2026-08-19 (see the entity comment):
        # a display-only overlay belongs to the person reading it.
        Column("buy_verdict_enabled", Boolean, nullable=False, server_default=true()),
        # FU-653 — per-surface belief overlays (recipes / shopping lists / meal
        # planner). Default FALSE: they annotate pages the user opened for
        # another reason, so they're opt-in, unlike the stock overlay above.
        Column("inference_recipes_enabled", Boolean, nullable=False, server_default=false()),
        Column("inference_shopping_enabled", Boolean, nullable=False, server_default=false()),
        Column("inference_meal_plan_enabled", Boolean, nullable=False, server_default=false()),
        # `nutrition_mode` moved to AppSetting (2026-08-14) — install-wide,
        # see the nutrition block in the AppSetting table above.
        # `show_recipe_images` dropped 2026-08-29 (migration
        # `e3b1d7f5a904`) — see the entity for why. FU-508 had already
        # dropped its stock-image companion column.
        # FU-615 — `household_headcount` moved off User to AppSetting
        # (install-wide; a household has one headcount).
        # alerts email digest channel (PROPOSAL_ALERTS §3.5 / §4.4).
        # Off by default; cadence values 'off' | 'daily' | 'weekly'; day is
        # the weekly send day Mon=0…Sun=6 (ignored on the daily cadence).
        # Settings rebuild Phase 4 — profile picture blob, deferred below.
        Column("image", LargeBinary, nullable=True),
        # Dashboard rebuild Phase 2 — per-user dashboard layout JSON (card
        # order + hidden set). Small opaque client view-state; Text for
        # Postgres/SQLite portability (R-005/006). Not deferred — it's tiny and
        # read on the /me path; never selected on user-list rows in practice.
        Column("dashboard_layout", Text, nullable=True),
        # per-user assistant config. `llm_enabled` is the AI-mode opt-in and
        # `llm_provider` the active provider (closed-set sentinel 'ollama' |
        # 'openai' | 'anthropic' | 'gemini', validated at update_me). The
        # per-provider *details* (base URL / model / API key) live in the
        # `UserLlmProvider` child table — a user configures several providers
        # and this column just points at the one in use.
        Column("llm_enabled", Boolean, nullable=False, server_default=false()),
        Column("llm_provider", String(16), nullable=True),
        # FU-360.6 — per-user "show the Dora helper bubble" opt-out. Default
        # True; when False the SPA never mounts the assistant launcher.
        Column("show_assistant", Boolean, nullable=False, server_default=true()),
        Column("daily_brief_enabled", Boolean, nullable=False, server_default=false()),
        Column("alert_discard_after_days", Integer, nullable=True, server_default="14"),
        # Chunk 6 / D-4 — per-user watermark for the stocktake Sweep phase.
        # Nullable: NULL means "never run a session", which the Sweep reads as
        # "show nothing" rather than "show everything ever excluded".
        Column("stocktake_last_session_at", DateTime(timezone=True), nullable=True),
    )

    # admin-minted bearer credential for `POST /api/ingest`. The
    # raw key is only shown once at creation; rest holds the SHA-256 hash
    # (mirrors AuthToken). Counters + last_used feed the API access page's
    # observability (C-10.3). `trust` is captured per PROPOSAL_INGESTION_API
    # §2.6 (enforcement deferred). `label` is admin free-text — the
    # invisibility rule forbids naming any specific producer.
    ingestion_source_table = Table(
        "IngestionSource", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("label", String(255), nullable=False),
        Column("key_hash", String(64), nullable=False, unique=True),
        Column("enabled", Boolean, nullable=False, server_default=true()),
        Column("trust", String(16), nullable=False, server_default="high"),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("last_used_at", DateTime(timezone=True), nullable=True),
        Column("accepted_count", Integer, nullable=False, server_default="0"),
        Column("skipped_count", Integer, nullable=False, server_default="0"),
        Column("failed_count", Integer, nullable=False, server_default="0"),
    )

    # consumed `Idempotency-Key`s from `POST /api/ingest`
    # batches. Re-sending the same key under the same source is a no-op
    # (PROPOSAL_INGESTION_API §2.3). TTL via `expires_at` lets the table
    # stay bounded.
    idempotency_key_table = Table(
        "IdempotencyKey", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("key", String(255), nullable=False),
        Column("source_id", String(36), nullable=False),
        Column("expires_at", DateTime(timezone=True), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )

    # external store name → Dora Store mapping
    # per IngestionSource. Quarantined when `store_id` is NULL; the
    # admin maps or rejects on the API access page.
    ingestion_store_mapping_table = Table(
        "IngestionStoreMapping", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("source_id", UUIDType,
               ForeignKey("IngestionSource.id", ondelete="CASCADE"),
               nullable=False),
        Column("external_name", String(255), nullable=False),
        Column("store_id", UUIDType,
               ForeignKey("Store.id", ondelete="SET NULL"),
               nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("last_seen_at", DateTime(timezone=True), nullable=True),
    )

    auth_token_table = Table(
        "AuthToken", metadata,
        Column("id", UUIDType, primary_key=True),
        Column("user_id", UUIDType, ForeignKey("User.id", ondelete="CASCADE"), nullable=False),
        Column("token_hash", String(64), nullable=False, unique=True),
        Column("purpose", String(32), nullable=False),
        Column("payload", String(255), nullable=True),
        Column("expires_at", DateTime(timezone=True), nullable=False),
        Column("consumed_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )

    # ── FU-563: index / unique reconciliation + FK covering indexes ──
    # The ORM model is the source of truth for the schema (R-003), but for years
    # every secondary index lived ONLY in the Alembic chain and was never mirrored
    # back here — so `create_all()` (dev + the whole e2e suite) built a near-
    # unindexed schema that didn't match the migrated production one (FU-393
    # Finding 1). This block mirrors all 32 pre-existing prod indexes/uniques
    # verbatim (names copied from the migrations so autogenerate stays a no-op on
    # them) AND adds a covering index on every foreign-key column that lacked one
    # (Finding 2 — 43 of them; unindexed FKs mean a parent delete full-scans the
    # child table). The 43 new indexes are created in prod by migration
    # b9d4f2a7c3e1; the 32 already exist there. `test_migrations.py` now compares
    # column + nullability + index/unique colsets so this can't silently re-drift.
    _t = metadata.tables

    # Pre-existing prod indexes, previously only in the migrations (Finding 1):
    Index("ix_alert_interaction_user_key", _t["AlertInteraction"].c.user_id, _t["AlertInteraction"].c.alert_key)
    Index("ix_AuditEvent_action_occurred", _t["AuditEvent"].c.action, _t["AuditEvent"].c.occurred_at)
    Index("ix_AuditEvent_actor_occurred", _t["AuditEvent"].c.actor_user_id, _t["AuditEvent"].c.occurred_at)
    Index("ix_AuditEvent_entity_occurred", _t["AuditEvent"].c.entity_type, _t["AuditEvent"].c.entity_id, _t["AuditEvent"].c.occurred_at)
    Index("ix_AuditEvent_occurred_at", _t["AuditEvent"].c.occurred_at)
    Index("ix_AuthToken_expires_at", _t["AuthToken"].c.expires_at)
    Index("ix_AuthToken_user_purpose", _t["AuthToken"].c.user_id, _t["AuthToken"].c.purpose)
    Index("backup_created_at", _t["Backup"].c.created_at)
    Index("consumption_event_stock_item_id", _t["ConsumptionEvent"].c.stock_item_id)
    Index("cook_event_recipe_id", _t["CookEvent"].c.recipe_id)
    Index("ix_dora_suggestion_suppression_kind_key", _t["DoraSuggestionSuppression"].c.kind, _t["DoraSuggestionSuppression"].c.dedup_key)
    Index("ix_mealplanentry_reconcile", _t["MealPlanEntry"].c.scheduled_for, _t["MealPlanEntry"].c.consumed_at)
    Index("ix_meal_plan_entry_cook_batch_id", _t["MealPlanEntry"].c.cook_batch_id)
    Index("ix_cook_batch_meal_plan_id", _t["CookBatch"].c.meal_plan_id)
    Index("ix_cook_batch_recipe_id", _t["CookBatch"].c.recipe_id)
    Index("ix_meal_reconcile_receipt_state_created_at", _t["MealPlanReconcileReceipt"].c.state, _t["MealPlanReconcileReceipt"].c.created_at)
    Index("ix_PriceAlert_product", _t["PriceAlert"].c.product_id)
    Index("ix_PriceAlert_user_product", _t["PriceAlert"].c.user_id, _t["PriceAlert"].c.product_id)
    Index("ix_push_subscription_user_id", _t["PushSubscription"].c.user_id)
    Index("ix_recipe_section_recipe_id", _t["RecipeSection"].c.recipe_id)
    Index("ix_recipe_step_parent_id", _t["RecipeStep"].c.parent_step_id)
    Index("ix_recipe_step_recipe_id", _t["RecipeStep"].c.recipe_id)
    Index("ix_recipe_step_image_recipe_id", _t["RecipeStepImage"].c.recipe_id)
    Index("ix_recipe_step_ingredient_ingredient_id", _t["RecipeStepIngredient"].c.recipe_ingredient_id)
    Index("ix_recipe_step_tool_tool_id", _t["RecipeStepTool"].c.tool_id)
    Index("ix_recipe_tag_dietary_tag_id", _t["RecipeTag"].c.dietary_tag_id)
    Index("ix_recipe_tool_tool_id", _t["RecipeTool"].c.tool_id)
    Index("ix_shopping_list_attachment_shopping_list_id", _t["ShoppingListAttachment"].c.shopping_list_id)
    Index("ix_StockItem_last_checked_at", _t["StockItem"].c.last_checked_at)
    Index("ix_StockItem_snoozed_until", _t["StockItem"].c.snoozed_until)
    Index("stock_item_expiry_event_stock_item_id", _t["StockItemExpiryEvent"].c.stock_item_id)

    # Pre-existing prod UNIQUE constraints, previously only in the migrations:
    Index("ix_alert_preference_user_kind", _t["AlertPreference"].c.user_id, _t["AlertPreference"].c.kind, unique=True)
    Index("ix_idempotency_key_source_key", _t["IdempotencyKey"].c.source_id, _t["IdempotencyKey"].c.key, unique=True)
    Index("uq_ingestion_store_mapping_source_external", _t["IngestionStoreMapping"].c.source_id, _t["IngestionStoreMapping"].c.external_name, unique=True)
    Index("uq_stock_item_price_observation_shopping_list_line_id", _t["StockItemPriceObservation"].c.shopping_list_line_id, unique=True)

    # FK covering indexes — new, created in prod by migration b9d4f2a7c3e1 (Finding 2):
    Index("ix_Backup_created_by_user_id", _t["Backup"].c.created_by_user_id)
    Index("ix_Barcode_stock_item_id", _t["Barcode"].c.stock_item_id)
    Index("ix_ConsumptionEvent_recipe_id", _t["ConsumptionEvent"].c.recipe_id)
    Index("ix_CookEvent_cooked_by_user_id", _t["CookEvent"].c.cooked_by_user_id)
    Index("ix_IngestionStoreMapping_store_id", _t["IngestionStoreMapping"].c.store_id)
    Index("ix_MealPlanEntry_meal_plan_id", _t["MealPlanEntry"].c.meal_plan_id)
    Index("ix_MealPlanEntry_recipe_id", _t["MealPlanEntry"].c.recipe_id)
    Index("ix_MealPlanReconcileReceipt_meal_plan_entry_id", _t["MealPlanReconcileReceipt"].c.meal_plan_entry_id)
    Index("ix_MealPlanReconcileReceipt_resolved_by_user_id", _t["MealPlanReconcileReceipt"].c.resolved_by_user_id)
    Index("ix_MealPlanSwapLedger_applied_by_user_id", _t["MealPlanSwapLedger"].c.applied_by_user_id)
    Index("ix_MealPlanSwapLedger_meal_plan_id", _t["MealPlanSwapLedger"].c.meal_plan_id)
    Index("ix_MealPlanTemplateEntry_recipe_id", _t["MealPlanTemplateEntry"].c.recipe_id)
    Index("ix_MealPlanTemplateEntry_template_id", _t["MealPlanTemplateEntry"].c.template_id)
    Index("ix_MealPlanTemplateSetItem_set_id", _t["MealPlanTemplateSetItem"].c.set_id)
    Index("ix_PreferredBuy_stock_item_id", _t["PreferredBuy"].c.stock_item_id)
    Index("ix_Product_store_id", _t["Product"].c.store_id)
    Index("ix_ProductHistoricOffer_product_id", _t["ProductHistoricOffer"].c.product_id)
    Index("ix_ProductOffer_product_id", _t["ProductOffer"].c.product_id)
    Index("ix_Recipe_category_id", _t["Recipe"].c.category_id)
    Index("ix_Recipe_cuisine_id", _t["Recipe"].c.cuisine_id)
    Index("ix_Recipe_recipe_collection_id", _t["Recipe"].c.recipe_collection_id)
    Index("ix_RecipeIngredient_recipe_id", _t["RecipeIngredient"].c.recipe_id)
    Index("ix_RecipeIngredient_section_id", _t["RecipeIngredient"].c.section_id)
    Index("ix_RecipeIngredient_selected_product_id", _t["RecipeIngredient"].c.selected_product_id)
    Index("ix_RecipeIngredient_stock_item_id", _t["RecipeIngredient"].c.stock_item_id)
    Index("ix_RecipeStep_section_id", _t["RecipeStep"].c.section_id)
    Index("ix_ShoppingListLine_product_id", _t["ShoppingListLine"].c.product_id)
    Index("ix_ShoppingListLine_purchased_store_id", _t["ShoppingListLine"].c.purchased_store_id)
    Index("ix_ShoppingListLine_selected_product_id", _t["ShoppingListLine"].c.selected_product_id)
    Index("ix_ShoppingListLine_shopping_list_id", _t["ShoppingListLine"].c.shopping_list_id)
    Index("ix_ShoppingListLine_stock_item_id", _t["ShoppingListLine"].c.stock_item_id)
    Index("ix_ShoppingListTemplateLine_selected_product_id", _t["ShoppingListTemplateLine"].c.selected_product_id)
    Index("ix_ShoppingListTemplateLine_stock_item_id", _t["ShoppingListTemplateLine"].c.stock_item_id)
    Index("ix_ShoppingListTemplateLine_template_id", _t["ShoppingListTemplateLine"].c.template_id)
    Index("ix_StockItem_stock_group_id", _t["StockItem"].c.stock_group_id)
    Index("ix_StockItem_stock_level_id", _t["StockItem"].c.stock_level_id)
    Index("ix_StockItem_stock_location_id", _t["StockItem"].c.stock_location_id)
    Index("ix_StockItem_usual_store_id", _t["StockItem"].c.usual_store_id)
    Index("ix_StockItemPriceObservation_stock_item_id", _t["StockItemPriceObservation"].c.stock_item_id)
    Index("ix_StockItemPriceObservation_store_id", _t["StockItemPriceObservation"].c.store_id)
    Index("ix_StockItemSubstitute_stock_item_b_id", _t["StockItemSubstitute"].c.stock_item_b_id)
    Index("ix_StockItemWasteEvent_stock_item_id", _t["StockItemWasteEvent"].c.stock_item_id)
    Index("ix_StockLevelChange_stock_item_id", _t["StockLevelChange"].c.stock_item_id)
    Index("ix_StockLevelChange_stock_level_id", _t["StockLevelChange"].c.stock_level_id)
    Index("ix_StockLocation_parent_id", _t["StockLocation"].c.parent_id)

    # ── Mappings ──────────────────────────────────────────────────────────────

    _mapper_registry.map_imperatively(Store, store_table, properties={
        "_id_col": store_table.c.id,
        "id": store_table.c.id,
        # defer the logo blob so list endpoints don't drag bytes
        # per row just to render the Stores grid. The dedicated
        # `/stores/<id>/image` route triggers the load on attribute access;
        # `has_image: bool` on StoreDto is hydrated from a separate
        # `IS NOT NULL` check (mirrors the StockItem / Product pattern).
        "image": deferred(store_table.c.image),
    })

    _mapper_registry.map_imperatively(StockGroup, stock_group_table, properties={
        "_id_col": stock_group_table.c.id,
        "id": stock_group_table.c.id,
    })

    _mapper_registry.map_imperatively(AppSetting, app_setting_table, properties={
        "_id_col": app_setting_table.c.id,
        "id": app_setting_table.c.id,
    })

    _mapper_registry.map_imperatively(StockLevel, stock_level_table, properties={
        "_id_col": stock_level_table.c.id,
        "id": stock_level_table.c.id,
    })

    # Children are loaded manually by repository queries (matching the rest
    # of the codebase's noload+manual fetch pattern). Cascade-delete is
    # handled at the FK level via ondelete="CASCADE" on parent_id.
    _mapper_registry.map_imperatively(StockLocation, stock_location_table, properties={
        "_id_col": stock_location_table.c.id,
        "id": stock_location_table.c.id,
    })

    _mapper_registry.map_imperatively(User, user_table, properties={
        "_id_col": user_table.c.id,
        "id": user_table.c.id,
        # Settings rebuild Phase 4 — defer the profile-picture blob so the
        # user-list endpoint never pulls bytes per row just to set
        # `has_image`. The `/users/<id>/image` route loads it on access;
        # list `has_image` is hydrated via a separate IS-NOT-NULL select.
        "image": deferred(user_table.c.image),
    })

    _mapper_registry.map_imperatively(UserLlmProvider, user_llm_provider_table, properties={
        "_id_col": user_llm_provider_table.c.id,
        "id": user_llm_provider_table.c.id,
        # Defer the api-key ciphertext; only the assistant request path +
        # probe need the bytes. Reads surface a derived `has_api_key: bool`.
        "api_key_encrypted": deferred(user_llm_provider_table.c.api_key_encrypted),
    })

    _mapper_registry.map_imperatively(ProductOffer, product_offer_table, properties={
        "_id_col": product_offer_table.c.id,
        "_product_id": product_offer_table.c.product_id,
        "id": product_offer_table.c.id,
    })

    _mapper_registry.map_imperatively(ProductHistoricOffer, product_historic_offer_table, properties={
        "_id_col": product_historic_offer_table.c.id,
        "_product_id": product_historic_offer_table.c.product_id,
        "id": product_historic_offer_table.c.id,
    })

    _mapper_registry.map_imperatively(Product, product_table, properties={
        "_id_col": product_table.c.id,
        "_store_id": product_table.c.store_id,
        "id": product_table.c.id,
        # defer the image blob so list endpoints (get_products,
        # best-deals) never pull megabytes per row. The dedicated
        # `/products/<id>/image` route triggers the load on attribute
        # access; `has_image` on ProductDto is derived from a separate
        # `IS NOT NULL` check. Mirrors the stock-item / recipe pattern.
        "image": deferred(product_table.c.image),
        "store": relationship(Store, lazy="noload"),
        "current_offer": relationship(ProductOffer, lazy="noload", uselist=False),
        "historic_offers": relationship(ProductHistoricOffer, lazy="noload"),
    })

    _mapper_registry.map_imperatively(StockItem, stock_item_table, properties={
        "_id_col": stock_item_table.c.id,
        "_stock_group_id": stock_item_table.c.stock_group_id,
        "_stock_level_id": stock_item_table.c.stock_level_id,
        "_stock_location_id": stock_item_table.c.stock_location_id,
        "id": stock_item_table.c.id,
        # usual_store_id is a real domain attribute on the entity,
        # mapped publicly so it round-trips through generic CRUD.
        "usual_store_id": stock_item_table.c.usual_store_id,
        # Plain UUID like usual_store_id — no relationship object. The
        # nutrition rollup batch-loads foods by id rather than walking a
        # per-item relationship (R-032: nothing reads a noload relationship
        # off an un-included load).
        "nutrition_food_id": stock_item_table.c.nutrition_food_id,
        "stock_group": relationship(StockGroup, lazy="noload"),
        "stock_level": relationship(StockLevel, lazy="noload"),
        "stock_location": relationship(StockLocation, lazy="noload"),
        "products": relationship(Product, secondary=stock_item_product_table, lazy="noload"),
        # Substitutes (StockItemSubstitute) are a self-referential m2m accessed
        # via the association table directly — no relationship is mapped because
        # the generic query builder can't self-join StockItem to itself.
    })

    _mapper_registry.map_imperatively(NutritionFood, nutrition_food_table, properties={
        "_id_col": nutrition_food_table.c.id,
        "id": nutrition_food_table.c.id,
    })

    _mapper_registry.map_imperatively(NutritionPortion, nutrition_portion_table, properties={
        "_id_col": nutrition_portion_table.c.id,
        "id": nutrition_portion_table.c.id,
        "nutrition_food_id": nutrition_portion_table.c.nutrition_food_id,
    })

    _mapper_registry.map_imperatively(StockLevelChange, stock_level_change_table, properties={
        "_id_col": stock_level_change_table.c.id,
        "id": stock_level_change_table.c.id,
    })

    _mapper_registry.map_imperatively(PreferredBuy, preferred_buy_table, properties={
        "_id_col": preferred_buy_table.c.id,
        "id": preferred_buy_table.c.id,
    })

    _mapper_registry.map_imperatively(StockItemPriceObservation, stock_item_price_observation_table, properties={
        "_id_col": stock_item_price_observation_table.c.id,
        "id": stock_item_price_observation_table.c.id,
    })

    _mapper_registry.map_imperatively(StockItemWasteEvent, stock_item_waste_event_table, properties={
        "_id_col": stock_item_waste_event_table.c.id,
        "id": stock_item_waste_event_table.c.id,
    })

    _mapper_registry.map_imperatively(CookEvent, cook_event_table, properties={
        "_id_col": cook_event_table.c.id,
        "id": cook_event_table.c.id,
    })

    _mapper_registry.map_imperatively(ConsumptionEvent, consumption_event_table, properties={
        "_id_col": consumption_event_table.c.id,
        "id": consumption_event_table.c.id,
    })

    _mapper_registry.map_imperatively(Backup, backup_table, properties={
        "_id_col": backup_table.c.id,
        "id": backup_table.c.id,
    })

    _mapper_registry.map_imperatively(StockItemExpiryEvent, stock_item_expiry_event_table, properties={
        "_id_col": stock_item_expiry_event_table.c.id,
        "id": stock_item_expiry_event_table.c.id,
    })

    _mapper_registry.map_imperatively(DoraSuggestionSuppression, dora_suggestion_suppression_table, properties={
        "_id_col": dora_suggestion_suppression_table.c.id,
        "id": dora_suggestion_suppression_table.c.id,
    })

    _mapper_registry.map_imperatively(AlertInteraction, alert_interaction_table, properties={
        "_id_col": alert_interaction_table.c.id,
        "id": alert_interaction_table.c.id,
    })

    _mapper_registry.map_imperatively(AlertPreference, alert_preference_table, properties={
        "_id_col": alert_preference_table.c.id,
        "id": alert_preference_table.c.id,
    })

    _mapper_registry.map_imperatively(PushSubscription, push_subscription_table, properties={
        "_id_col": push_subscription_table.c.id,
        "id": push_subscription_table.c.id,
    })

    _mapper_registry.map_imperatively(Barcode, barcode_table, properties={
        "_id_col": barcode_table.c.id,
        "id": barcode_table.c.id,
    })

    _mapper_registry.map_imperatively(AuditEvent, audit_event_table, properties={
        "_id_col": audit_event_table.c.id,
        "id": audit_event_table.c.id,
    })

    _mapper_registry.map_imperatively(AuthToken, auth_token_table, properties={
        "_id_col": auth_token_table.c.id,
        "id": auth_token_table.c.id,
    })

    _mapper_registry.map_imperatively(IngestionSource, ingestion_source_table, properties={
        "_id_col": ingestion_source_table.c.id,
        "id": ingestion_source_table.c.id,
    })

    _mapper_registry.map_imperatively(IdempotencyKey, idempotency_key_table, properties={
        "_id_col": idempotency_key_table.c.id,
        "id": idempotency_key_table.c.id,
    })

    _mapper_registry.map_imperatively(IngestionStoreMapping, ingestion_store_mapping_table, properties={
        "_id_col": ingestion_store_mapping_table.c.id,
        "id": ingestion_store_mapping_table.c.id,
    })

    _mapper_registry.map_imperatively(PriceAlert, price_alert_table, properties={
        "_id_col": price_alert_table.c.id,
        "id": price_alert_table.c.id,
    })

    _mapper_registry.map_imperatively(RecipeCollection, recipe_collection_table, properties={
        "_id_col": recipe_collection_table.c.id,
        "id": recipe_collection_table.c.id,
    })

    _mapper_registry.map_imperatively(RecipeIngredient, recipe_ingredient_table, properties={
        "_id_col": recipe_ingredient_table.c.id,
        # FK columns are bound to underscore-prefixed properties so they're
        # ignored by verify_mappings (which compares the entity's dataclass
        # fields against publicly-mapped properties).
        "_recipe_id": recipe_ingredient_table.c.recipe_id,
        "_stock_item_id": recipe_ingredient_table.c.stock_item_id,
        "id": recipe_ingredient_table.c.id,
        # section_id is a real domain attribute (nullable),
        # mapped publicly so it round-trips through `from_entity`.
        "section_id": recipe_ingredient_table.c.section_id,
        # Cookbook revision §1.9 — optional flag.
        "is_optional": recipe_ingredient_table.c.is_optional,
        "stock_item": relationship(StockItem, lazy="noload"),
    })

    # recipe sections (named groups). No relationship from
    # Recipe; sections are loaded directly by the access helper (matches
    # the RecipeStep pattern).
    _mapper_registry.map_imperatively(RecipeSection, recipe_section_table, properties={
        "_id_col": recipe_section_table.c.id,
        "id": recipe_section_table.c.id,
        "recipe_id": recipe_section_table.c.recipe_id,
        "sequence": recipe_section_table.c.sequence,
        "name": recipe_section_table.c.name,
    })

    # PROPOSAL_RECIPE_IMAGE_STEPS — step image rows. Image blob deferred so
    # list reads never drag bytes; the dedicated
    # `/recipes/<id>/step-images/<image_id>` route triggers the load on
    # attribute access.
    _mapper_registry.map_imperatively(RecipeStepImage, recipe_step_image_table, properties={
        "_id_col": recipe_step_image_table.c.id,
        "id": recipe_step_image_table.c.id,
        "recipe_id": recipe_step_image_table.c.recipe_id,
        "sequence": recipe_step_image_table.c.sequence,
        "image": deferred(recipe_step_image_table.c.image),
    })

    # structured step rows. Ingredient + tool links are not
    # mapped as SQLAlchemy relationships; the access helper queries the link
    # tables directly when hydrating the DTO (matches the dietary-tag/tool
    # pattern). All entity fields are publicly mapped (recipe_id/
    # parent_step_id are real domain attributes, not internal FKs).
    _mapper_registry.map_imperatively(RecipeStep, recipe_step_table, properties={
        "_id_col": recipe_step_table.c.id,
        "id": recipe_step_table.c.id,
        "recipe_id": recipe_step_table.c.recipe_id,
        "parent_step_id": recipe_step_table.c.parent_step_id,
        "sequence": recipe_step_table.c.sequence,
        "text": recipe_step_table.c.text,
        "hint": recipe_step_table.c.hint,
        # nullable section grouping for top-level steps.
        "section_id": recipe_step_table.c.section_id,
        "timer_minutes": recipe_step_table.c.timer_minutes,
    })

    _mapper_registry.map_imperatively(Cuisine, cuisine_table, properties={
        "_id_col": cuisine_table.c.id,
        "id": cuisine_table.c.id,
    })

    _mapper_registry.map_imperatively(Category, category_table, properties={
        "_id_col": category_table.c.id,
        "id": category_table.c.id,
    })

    _mapper_registry.map_imperatively(DietaryTag, dietary_tag_table, properties={
        "_id_col": dietary_tag_table.c.id,
        "id": dietary_tag_table.c.id,
    })

    _mapper_registry.map_imperatively(Tool, tool_table, properties={
        "_id_col": tool_table.c.id,
        "id": tool_table.c.id,
    })

    _mapper_registry.map_imperatively(MealSlot, meal_slot_table, properties={
        "_id_col": meal_slot_table.c.id,
        "id": meal_slot_table.c.id,
    })

    _mapper_registry.map_imperatively(Recipe, recipe_table, properties={
        "_id_col": recipe_table.c.id,
        "_recipe_collection_id": recipe_table.c.recipe_collection_id,
        "_cuisine_id": recipe_table.c.cuisine_id,
        "_category_id": recipe_table.c.category_id,
        "id": recipe_table.c.id,
        "steps_mode": recipe_table.c.steps_mode,
        # C-cross Chunk 5 / FU-090 — defer the image blob so the list
        # endpoint doesn't load every recipe's image bytes into memory
        # just to compute `has_image`. The detail endpoint (and the
        # dedicated `/recipes/<id>/image` route) trigger the load
        # on-demand via attribute access; everywhere else gets the
        # `has_image: bool` DTO field from a separate SELECT.
        "image": deferred(recipe_table.c.image),
        "recipe_collection": relationship(RecipeCollection, lazy="noload"),
        # R-019 / ADR-014 — no lazy overrides. Callers that read
        # `recipe.cuisine` / `recipe.category` must chain
        # `.include(Recipe.Fields.CUISINE)` /
        # `.include(Recipe.Fields.CATEGORY)` on the query. FU-314 walked
        # every read site; the FU-138 e2e query-count test guards the
        # list handler against N+1 regressions from a missed include.
        "cuisine": relationship(Cuisine, lazy="noload"),
        "category": relationship(Category, lazy="noload"),
        "ingredients": relationship(
            RecipeIngredient,
            lazy="noload",
            cascade="all, delete-orphan",
            foreign_keys=[recipe_ingredient_table.c.recipe_id],
        ),
    })

    _mapper_registry.map_imperatively(MealPlanEntry, meal_plan_entry_table, properties={
        "_id_col": meal_plan_entry_table.c.id,
        "_recipe_id": meal_plan_entry_table.c.recipe_id,
        # See RecipeIngredient above — FK columns hidden from verify_mappings.
        "_meal_plan_id": meal_plan_entry_table.c.meal_plan_id,
        "id": meal_plan_entry_table.c.id,
        "recipe": relationship(Recipe, lazy="noload"),
    })

    _mapper_registry.map_imperatively(MealPlanSwapLedger, meal_plan_swap_ledger_table, properties={
        "_id_col": meal_plan_swap_ledger_table.c.id,
        "id": meal_plan_swap_ledger_table.c.id,
    })

    _mapper_registry.map_imperatively(
        MealPlanReconcileReceipt, meal_plan_reconcile_receipt_table, properties={
            "_id_col": meal_plan_reconcile_receipt_table.c.id,
            "id": meal_plan_reconcile_receipt_table.c.id,
        },
    )

    # PROPOSAL_MEAL_PLANS_PART_2 — no relationships: managed explicitly by the
    # meal-plan write path (flush contract), same plain-FK-id idiom as the
    # reconcile receipt above. `meal_plan_id` / `recipe_id` auto-map to the
    # same-named entity fields.
    _mapper_registry.map_imperatively(CookBatch, cook_batch_table, properties={
        "_id_col": cook_batch_table.c.id,
        "id": cook_batch_table.c.id,
    })

    _mapper_registry.map_imperatively(MealPlan, meal_plan_table, properties={
        "_id_col": meal_plan_table.c.id,
        "id": meal_plan_table.c.id,
        "entries": relationship(
            MealPlanEntry,
            lazy="noload",
            cascade="all, delete-orphan",
            foreign_keys=[meal_plan_entry_table.c.meal_plan_id],
        ),
    })

    _mapper_registry.map_imperatively(
        MealPlanTemplateEntry, meal_plan_template_entry_table, properties={
            "_id_col": meal_plan_template_entry_table.c.id,
            "id": meal_plan_template_entry_table.c.id,
        }
    )

    _mapper_registry.map_imperatively(
        MealPlanTemplate, meal_plan_template_table, properties={
            "_id_col": meal_plan_template_table.c.id,
            "id": meal_plan_template_table.c.id,
            "entries": relationship(
                MealPlanTemplateEntry,
                primaryjoin=(
                    meal_plan_template_table.c.id
                    == meal_plan_template_entry_table.c.template_id
                ),
                cascade="all",
                lazy="noload",
            ),
        }
    )

    _mapper_registry.map_imperatively(
        MealPlanTemplateSetItem, meal_plan_template_set_item_table, properties={
            "_id_col": meal_plan_template_set_item_table.c.id,
            "id": meal_plan_template_set_item_table.c.id,
        }
    )

    _mapper_registry.map_imperatively(
        MealPlanTemplateSet, meal_plan_template_set_table, properties={
            "_id_col": meal_plan_template_set_table.c.id,
            "id": meal_plan_template_set_table.c.id,
            "items": relationship(
                MealPlanTemplateSetItem,
                primaryjoin=(
                    meal_plan_template_set_table.c.id
                    == meal_plan_template_set_item_table.c.set_id
                ),
                cascade="all",
                lazy="noload",
            ),
        }
    )

    # ShoppingListLine exposes its FK columns directly as `shopping_list_id`,
    # `stock_item_id`, and `selected_product_id` on the dataclass (raw UUIDs,
    # not relationship objects). They auto-map from the table columns of the
    # same name, so we only need to explicitly map `id` for the verify check.
    _mapper_registry.map_imperatively(ShoppingListLine, shopping_list_line_table, properties={
        "_id_col": shopping_list_line_table.c.id,
        "id": shopping_list_line_table.c.id,
    })

    _mapper_registry.map_imperatively(ShoppingList, shopping_list_table, properties={
        "_id_col": shopping_list_table.c.id,
        "id": shopping_list_table.c.id,
        # Lines are added directly via `repo.add(line)` rather than appended
        # through `list.lines`. Using `delete-orphan` would implicitly require
        # `single_parent=True` and complain about lines added outside the
        # collection. Plain "all" cascade is enough — the DB-level FK has
        # ON DELETE CASCADE so a deleted list takes its lines with it.
        "lines": relationship(
            ShoppingListLine,
            primaryjoin=shopping_list_table.c.id == shopping_list_line_table.c.shopping_list_id,
            cascade="all",
            lazy="noload",
        ),
    })

    # receipt attachments. Bytes deferred so list/detail JSON never
    # drags blob payloads; the dedicated
    # `/shopping-lists/<id>/attachments/<attachment_id>` route triggers the
    # load on attribute access.
    _mapper_registry.map_imperatively(
        ShoppingListAttachment, shopping_list_attachment_table, properties={
            "_id_col": shopping_list_attachment_table.c.id,
            "id": shopping_list_attachment_table.c.id,
            "shopping_list_id": shopping_list_attachment_table.c.shopping_list_id,
            "sequence": shopping_list_attachment_table.c.sequence,
            "image": deferred(shopping_list_attachment_table.c.image),
            "created_at": shopping_list_attachment_table.c.created_at,
        }
    )

    # Template line — same pattern as ShoppingListLine. FK columns map by
    # name (template_id, stock_item_id); only `id` needs the explicit alias.
    _mapper_registry.map_imperatively(
        ShoppingListTemplateLine, shopping_list_template_line_table, properties={
            "_id_col": shopping_list_template_line_table.c.id,
            "id": shopping_list_template_line_table.c.id,
        }
    )

    _mapper_registry.map_imperatively(
        ShoppingListTemplate, shopping_list_template_table, properties={
            "_id_col": shopping_list_template_table.c.id,
            "id": shopping_list_template_table.c.id,
            "lines": relationship(
                ShoppingListTemplateLine,
                primaryjoin=(
                    shopping_list_template_table.c.id
                    == shopping_list_template_line_table.c.template_id
                ),
                cascade="all",
                lazy="noload",
            ),
        }
    )

    verify_mappings()
    _mappings_configured = True


def verify_mappings():
    from dataclasses import fields as dc_fields
    from dora_api.domain.exceptions import PersistenceError

    for mapper in _mapper_registry.mappers:
        entity_class = mapper.class_
        mapped_attrs = {
            prop.key for prop in mapper.iterate_properties
            if not prop.key.startswith("_")
        }
        entity_fields = {f.name for f in dc_fields(entity_class)}

        unmapped = entity_fields - mapped_attrs
        if unmapped:
            raise PersistenceError(f"{entity_class.__name__} has fields not mapped to persistence: {unmapped}")

        extra = mapped_attrs - entity_fields
        if extra:
            raise PersistenceError(f"{entity_class.__name__} has mapped attributes not present on entity: {extra}")
