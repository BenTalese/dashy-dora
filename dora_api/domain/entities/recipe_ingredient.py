from dataclasses import dataclass
from uuid import UUID

from dora_api.domain.entities.base_entity import BaseEntity
from dora_api.domain.entities.stock_item import StockItem


@dataclass
class RecipeIngredient(BaseEntity):
    notes: str | None
    quantity: float | None
    # IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 — an ingredient anchors on
    # either a linked StockItem OR a persisted ``raw_text`` label. The
    # CHECK constraint on the table enforces at-least-one; the parser
    # and importer flow may hand back either.
    stock_item: StockItem | None
    unit: str | None
    # nullable section grouping (DEC-3 option A). NULL means
    # the ingredient sits in the implicit "main" group; FK → RecipeSection
    # with ON DELETE SET NULL so deleting a section keeps its ingredients,
    # just unsectioned.
    section_id: UUID | None = None
    # Cookbook revision §1.9 — optional ingredients are ignored entirely by
    # the cookability rule (no `cookable_with_optional` half-state). They
    # still render in the recipe (with an "(optional)" hint) and appear in
    # the shopping-list picker under an Optional separator, unchecked by
    # default regardless of stock level.
    is_optional: bool = False
    # IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 — the ingredient text as the
    # user pasted / imported it. Backfilled from ``StockItem.name`` for
    # existing rows so pre-Chunk-4 recipes still render meaningful
    # labels even when their StockItem is later renamed / unlinked /
    # deleted. Preserved even when a row is linked — the raw text is
    # often more informative than the bare stock-item name.
    raw_text: str | None = None
    # Which one of the linked stock item this recipe means: a name of its own
    # ("tasty cheddar" under Cheese), one of the item's preferred buys, or a
    # linked product. All optional and independent of cookability, which stays
    # at the stock-item level. `preferred_buy_id` is reference-only like the
    # shopping line's; `selected_product_id` is cleared when the product is
    # unlinked from the item.
    label: str | None = None
    preferred_buy_id: UUID | None = None
    selected_product_id: UUID | None = None
    # The top of a range ("1 to 2 carrots"): `quantity` is the low end and
    # this the high end. Null for a single amount. Display only: costing,
    # nutrition, scaling maths and the planner's totals all read `quantity`,
    # so a range counts as its low end everywhere a number is needed.
    quantity_max: float | None = None

    class Fields(BaseEntity.Fields):
        NOTES = "notes"
        QUANTITY = "quantity"
        STOCK_ITEM = "stock_item"
        UNIT = "unit"
        SECTION_ID = "section_id"
        IS_OPTIONAL = "is_optional"
        RAW_TEXT = "raw_text"
        LABEL = "label"
        PREFERRED_BUY_ID = "preferred_buy_id"
        SELECTED_PRODUCT_ID = "selected_product_id"
        QUANTITY_MAX = "quantity_max"
