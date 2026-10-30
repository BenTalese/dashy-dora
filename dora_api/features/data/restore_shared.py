"""Shared helpers for the inspect + restore endpoints.

Each in-scope table is described in `SECTIONS` as a single source of truth.
Adding a new section is a one-entry change here plus (if it carries FKs or
children) a line in HARD_FK_PULL_IN / SOFT_FK_NULLABLE / REQUIRED_FKS /
CHILD_AUTO_INCLUDE.

The exported maps (TABLE_NAME_BY_BACKUP_KEY, RESTORE_ORDER, etc.) are
derived from `SECTIONS` so callers don't need to be touched when new
sections land.
"""
import base64
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, LargeBinary, String
from sqlalchemy_utils import UUIDType

from dora_api.persistence.aware import as_utc


# ── Per-table key functions ─────────────────────────────────────────────

def _name_key(row: dict[str, Any]) -> Any:
    return (row.get("name") or "").strip().lower()


def _location_key(row: dict[str, Any]) -> Any:
    parent = row.get("parent_id")
    return (_name_key(row), str(parent) if parent else None)


def _product_key(row: dict[str, Any]) -> Any:
    # Real-world products have a stockcode-per-store; treat that pair as
    # the natural key. Fall back to name for rows missing stockcode (manually
    # entered products). FU-189 carve-out: `merchant_stockcode` is the
    # producer's SKU code, retained verbatim.
    stockcode = row.get("merchant_stockcode")
    store = row.get("store_id")
    if stockcode and store:
        return ("sku", str(store), str(stockcode).strip().lower())
    return ("name", _name_key(row))


def _username_key(row: dict[str, Any]) -> Any:
    return (row.get("username") or "").strip().lower()


def _singleton_key(_: dict[str, Any]) -> Any:
    # AppSetting is a single-row table. Any existing row makes any incoming
    # row a "duplicate" — the user already has app settings.
    return "singleton"


# ── Section catalogue ───────────────────────────────────────────────────

@dataclass(frozen=True)
class Section:
    backup_key: str          # output key inside the JSON document
    table_name: str          # physical table name in db.metadata
    label: str               # human label for the UI
    category: str            # display grouping ("Core data" / "Optional")
    default_on: bool = True
    duplicate_key_fn: Callable[[dict[str, Any]], Any] | None = None
    # Columns to drop on export AND skip on restore. Used for password
    # hashes and any other "exported should never be a credential" data.
    excluded_columns: frozenset[str] = field(default_factory=frozenset)
    # Flagged on the API access / backup page so an admin sees that a backup
    # carries data Dora doesn't want written to disk casually (accounts,
    # system settings, pricing history). Not blocked — a full-fidelity dump is
    # a legitimate migration need — just visible.
    sensitive: bool = False

    @property
    def pickable(self) -> bool:
        """Whether the restore tree offers this section's rows one by one.
        Sections with a natural duplicate key are the user-facing tables; the
        link/line tables ride along with their parents (CHILD_AUTO_INCLUDE)
        and are never picked directly."""
        return self.duplicate_key_fn is not None


# Order matters — both the export dump and the restore iterator walk this
# list top-to-bottom, so parents must precede children.
SECTIONS: tuple[Section, ...] = (
    # ── Core data (on by default) ──
    Section("stock_groups", "StockGroup", "Stock groups", "Core data", True, _name_key),
    Section("stock_levels", "StockLevel", "Stock levels", "Core data", True, _name_key),
    Section("stock_locations", "StockLocation", "Stock locations", "Core data", True, _location_key),
    Section("saved_products", "Product", "Saved products", "Core data", True, _product_key),
    Section("stock_items", "StockItem", "Stock items", "Core data", True, _name_key),
    Section("product_stock_item_links", "StockItemProduct", "Product ↔ stock-item links", "Core data", True),
    Section("stock_item_substitutes", "StockItemSubstitute", "Stock-item substitutes", "Core data", True),
    Section("shopping_lists", "ShoppingList", "Shopping lists", "Core data", True, _name_key),
    Section("shopping_list_items", "ShoppingListLine", "Shopping list items", "Core data", True),
    Section("shopping_list_templates", "ShoppingListTemplate", "Shopping list templates", "Core data", True, _name_key),
    Section("shopping_list_template_lines", "ShoppingListTemplateLine", "Template lines", "Core data", True),
    Section("recipe_collections", "RecipeCollection", "Recipe collections", "Core data", True, _name_key),
    # recipe vocabularies. Parents of Recipe (cuisine_id /
    # category_id FKs) so they precede it in restore order.
    Section("cuisines", "Cuisine", "Cuisines", "Core data", True, _name_key),
    Section("categories", "Category", "Recipe categories", "Core data", True, _name_key),
    Section("dietary_tags", "DietaryTag", "Dietary tags", "Core data", True, _name_key),
    Section("tools", "Tool", "Kitchen tools", "Core data", True, _name_key),
    Section("recipes", "Recipe", "Recipes", "Core data", True, _name_key),
    Section("recipe_ingredients", "RecipeIngredient", "Recipe ingredients", "Core data", True),
    Section("recipe_dietary_tags", "RecipeTag", "Recipe ↔ dietary-tag links", "Core data", True),
    Section("recipe_tools", "RecipeTool", "Recipe ↔ tool links", "Core data", True),
    # structured steps + their two link tables. Steps must be
    # inserted before their link rows; sub-steps reference parent_step_id on
    # the same table, but rows insert in any order on restore (the FK is
    # deferred by SQLite when reset+restored in one txn, and Postgres tolerates
    # the same-table reference once all rows are present).
    Section("recipe_steps", "RecipeStep", "Recipe steps", "Core data", True),
    Section("recipe_step_ingredients", "RecipeStepIngredient", "Recipe step ↔ ingredient links", "Core data", True),
    Section("recipe_step_tools", "RecipeStepTool", "Recipe step ↔ tool links", "Core data", True),
    Section("meal_plans", "MealPlan", "Meal plans", "Core data", True, _name_key),
    Section("meal_plan_entries", "MealPlanEntry", "Meal plan entries", "Core data", True),
    # ── Optional (off by default) ──
    Section(
        "app_settings", "AppSetting", "System settings", "Optional", False,
        _singleton_key,
        # FU-387 — never ship Fernet-wrapped operational secrets in a
        # backup. They're encrypted with the install's
        # `DORA_SECRET_ENCRYPTION_KEY`, so ciphertext alone isn't
        # compromise, but backup-plus-key is. Defence-in-depth: an
        # admin can't accidentally email a backup that contains their
        # own SMTP + push credentials. Restoring an install re-enters
        # these in Settings.
        excluded_columns=frozenset({
            "smtp_password_encrypted",
            "vapid_private_key_encrypted",
        }),
        sensitive=True,
    ),
    Section(
        "users", "User", "User accounts (no passwords)", "Optional", False,
        _username_key,
        # Never ship credentials. Restoring users without hashes means they
        # can't log in until an admin resets them — that's the explicit
        # trade-off for being able to back up account preferences.
        # The per-user LLM API key moved to the `UserLlmProvider` table
        # (2026-08-12), which is not a backup section at all — so the key
        # (and the rest of the provider config) never leaves the install
        # via a backup; there's nothing to exclude on User any more.
        excluded_columns=frozenset({
            "password_hash",
        }),
        sensitive=True,
    ),
    Section(
        "product_historic_offers", "ProductHistoricOffer", "Historic product offers", "Optional", False,
        sensitive=True,
    ),
    # Real-world barcodes (FU-056 hybrid — can attach to a Product, a
    # StockItem, or both). On by default; small table, useful to round-trip
    # so a restored install can still resolve scanned codes.
    Section(
        "barcodes", "Barcode", "Barcodes", "Core data", True,
    ),
)


# ── Derived maps ────────────────────────────────────────────────────────

# Sections whose duplicate-skipped rows re-point the backup's children at
# the existing row (backup pk → existing pk). Reference parents only: a stock
# item keeps its location and group, a recipe its cuisine, a tag link its tag.
# Aggregate roots (recipes, lists, templates, meal plans) are deliberately NOT
# here — remapping those would pour the backup's ingredients / lines / entries
# into the existing document, duplicating its contents.
REMAP_ON_DUPLICATE: frozenset[str] = frozenset({
    "stock_groups", "stock_levels", "stock_locations", "saved_products",
    "stock_items", "recipe_collections", "cuisines", "categories",
    "dietary_tags", "tools",
})

TABLE_NAME_BY_BACKUP_KEY: dict[str, str] = {s.backup_key: s.table_name for s in SECTIONS}
BACKUP_KEY_BY_TABLE_NAME: dict[str, str] = {s.table_name: s.backup_key for s in SECTIONS}
SECTION_BY_BACKUP_KEY: dict[str, Section] = {s.backup_key: s for s in SECTIONS}
RESTORE_ORDER: tuple[str, ...] = tuple(s.backup_key for s in SECTIONS)
DUPLICATE_KEY_BY_BACKUP_KEY: dict[str, Callable[[dict[str, Any]], Any]] = {
    s.backup_key: s.duplicate_key_fn for s in SECTIONS if s.duplicate_key_fn is not None
}


# ── FK classification ───────────────────────────────────────────────────

# Hard FKs: pull the target row into the selection if it's in the backup but
# wasn't picked. Keyed by (backup_key, column_name) → target backup_key.
HARD_FK_PULL_IN: dict[tuple[str, str], str] = {
    ("stock_items", "stock_location_id"): "stock_locations",
    ("stock_items", "stock_group_id"): "stock_groups",
    ("stock_items", "stock_level_id"): "stock_levels",
    ("stock_locations", "parent_id"): "stock_locations",
    ("recipes", "recipe_collection_id"): "recipe_collections",
    # pull the cuisine/category vocab row in if a selected
    # recipe references it.
    ("recipes", "cuisine_id"): "cuisines",
    ("recipes", "category_id"): "categories",
    # product-only / nested product lines carry a hard
    # `product_id`; the line's CHECK constraint requires either anchor.
    # Pull the referenced Product into the selection so the line survives
    # a "shopping list only" partial restore.
    ("shopping_list_items", "product_id"): "saved_products",
}

# Soft FKs (nullable in schema): if the target is missing at insert time and
# isn't in the pull-in set, null the column and emit a warning.
SOFT_FK_NULLABLE: set[tuple[str, str]] = {
    ("shopping_list_items", "selected_product_id"),
}

# Required FKs: target must exist (in DB or restored alongside) or the row is
# skipped with a warning.
REQUIRED_FKS: set[tuple[str, str]] = {
    ("saved_products", "store_id"),
    ("shopping_list_items", "shopping_list_id"),
    # `stock_item_id` is now NULLABLE (product-only lines
    # leave it null). Only enforced as required when the source row carries
    # a non-null value: the restore decoder skips the FK check entirely
    # when the column is null, so this entry behaves as "if set, must
    # resolve" rather than "must be set".
    ("shopping_list_items", "stock_item_id"),
    # `product_id` is also NULLABLE. When set, the target
    # Product must resolve; otherwise drop the row rather than silently
    # nulling the column (a product-only line with both anchors null
    # would violate the CHECK constraint on insert). HARD_FK_PULL_IN
    # above usually drags the Product in; this is the belt-and-braces
    # for the "user opted out of saved_products" partial restore.
    ("shopping_list_items", "product_id"),
    ("shopping_list_template_lines", "template_id"),
    ("shopping_list_template_lines", "stock_item_id"),
    ("recipe_ingredients", "recipe_id"),
    ("recipe_ingredients", "stock_item_id"),
    ("recipe_dietary_tags", "recipe_id"),
    ("recipe_dietary_tags", "dietary_tag_id"),
    ("recipe_tools", "recipe_id"),
    ("recipe_tools", "tool_id"),
    ("recipe_steps", "recipe_id"),
    ("recipe_step_ingredients", "step_id"),
    ("recipe_step_ingredients", "recipe_ingredient_id"),
    ("recipe_step_tools", "step_id"),
    ("recipe_step_tools", "tool_id"),
    # `meal_id` → `recipe_id` with the meals→recipes rework; the `Meal` /
    # `MealRecipe` sections went with it. `restore_backup.validate_fk_maps`
    # now refuses to import with a stale entry here (finalisation 18-R1).
    ("meal_plan_entries", "recipe_id"),
    ("meal_plan_entries", "meal_plan_id"),
    ("product_stock_item_links", "stock_item_id"),
    ("product_stock_item_links", "product_id"),
    ("stock_item_substitutes", "stock_item_a_id"),
    ("stock_item_substitutes", "stock_item_b_id"),
    ("product_historic_offers", "product_id"),
    ("barcodes", "product_id"),
    ("barcodes", "stock_item_id"),
}

# Children that ride along when their parent is selected (partial mode UX).
CHILD_AUTO_INCLUDE: tuple[tuple[str, str, str], ...] = (
    ("shopping_lists", "shopping_list_items", "shopping_list_id"),
    ("shopping_list_templates", "shopping_list_template_lines", "template_id"),
    ("recipes", "recipe_ingredients", "recipe_id"),
    ("recipes", "recipe_steps", "recipe_id"),
    ("meal_plans", "meal_plan_entries", "meal_plan_id"),
    ("saved_products", "product_historic_offers", "product_id"),
    ("saved_products", "barcodes", "product_id"),
)


# ── Value decoding ──────────────────────────────────────────────────────

def decode_value(value: Any, column_type: Any) -> Any:
    """Reverse the encoding done by backup.py. Falls through unrecognised
    types so future column kinds don't silently get corrupted — they just
    arrive as-is from the JSON.
    """
    if value is None:
        return None
    if isinstance(column_type, UUIDType):
        return UUID(value) if not isinstance(value, UUID) else value
    if isinstance(column_type, DateTime):
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
        # A backup taken from SQLite holds naive instants (it drops tzinfo on
        # read); they are UTC, and an aware value is what a Postgres
        # `timestamptz` needs to store them as such (R-098).
        return as_utc(parsed) if column_type.timezone else parsed
    if isinstance(column_type, Date):
        return date.fromisoformat(value) if isinstance(value, str) else value
    if isinstance(column_type, LargeBinary):
        return base64.b64decode(value) if isinstance(value, str) else value
    if isinstance(column_type, Boolean):
        return bool(value)
    if isinstance(column_type, (Integer, Float, String)):
        return value
    return value


def primary_key_columns(table) -> list[str]:
    return [c.name for c in table.primary_key.columns]


def composite_key(row: dict[str, Any], pk_columns: list[str]) -> tuple:
    """Stable tuple key for tables with composite PKs (the m2m join tables)."""
    return tuple(str(row.get(c)) if row.get(c) is not None else None for c in pk_columns)
