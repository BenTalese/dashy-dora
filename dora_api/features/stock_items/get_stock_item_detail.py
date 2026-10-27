"""Rich single-stock-item endpoint.

The list endpoint at `GET /api/stock-items` returns a compact DTO suitable
for the overview grid. This one is used by the detail page and includes:
  * everything on the list DTO
  * notes, stocktake_alerts_are_enabled (Mute)
  * the stock-level name (the page edits location, group and usual store
    through id pickers, so only their ids ride along)
  * linked products with their store + current offer info
  * linked recipes (just id + name) — derived via the RecipeIngredient join
"""
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List
from uuid import UUID

from sqlalchemy import select

from dora_api.app import db
from dora_api.domain.entities.recipe import Recipe
from dora_api.domain.entities.recipe_ingredient import RecipeIngredient
from dora_api.domain.entities.shopping_list import (
    SHOPPING_LIST_STATUS_DONE, ShoppingList, ShoppingListLine,
)
from dora_api.domain.entities.preferred_buy import PreferredBuy
from dora_api.domain.entities.barcode import Barcode
from dora_api.domain.entities.cook_event import CookEvent
from dora_api.domain.entities.nutrition_food import NUTRITION_SOURCE_LABELS, NutritionFood
from dora_api.domain.entities.store import Store
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_item_expiry_event import StockItemExpiryEvent
from dora_api.domain.entities.stock_item_price_observation import StockItemPriceObservation
from dora_api.domain.entities.stock_item_waste_event import StockItemWasteEvent
from dora_api.domain.entities.stock_level import StockLevel
from dora_api.domain.entities.stock_level_change import StockLevelChange
from dora_api.features.nutrition.nutrients import display_rows
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.features.stock_items.your_prices import build_your_prices_for_item
from dora_api.infrastructure.api_response import not_found, ok
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LinkedProductDto:
    product_id: UUID
    name: str
    store_id: UUID
    store_name: str
    size: str | None
    web_url: str | None
    price_now: float | None
    price_was: float | None


@dataclass(frozen=True, slots=True)
class LinkedRecipeDto:
    recipe_id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class StockItemBarcodeDto:
    """FU-056 — one row in the stock-item-detail Barcodes section.

    `source` distinguishes two origins of the same lookup result:

    * `direct` — the user explicitly registered this EAN against this
      stock item (the Barcode row's `stock_item_id` points here).
    * `via_product` — the EAN is a linked Product's catalogue code,
      reaching this stock item through `StockItemProduct`. The SPA
      renders these read-only on the stock-item surface; editing
      lives on the Product.

    `product_id` / `product_name` are set only for `via_product` rows.
    """
    barcode_id: UUID
    barcode: str
    source: str   # 'direct' | 'via_product'
    product_id: UUID | None
    product_name: str | None


@dataclass(frozen=True, slots=True)
class SubstituteDto:
    stock_item_id: UUID
    name: str
    stock_level_id: UUID | None
    stock_level_name: str | None
    # The level's ladder position (0 stocked, 1 low, 2 out), so the row can
    # colour its dot without looking the substitute up in another store.
    stock_level_sequence: int | None
    # free-text hint. NULL when the user didn't set one.
    notes: str | None
    # optional structured ratio "qty_in of THIS item → qty_out of
    # the substitute". The four fields are stored in the canonical pair's
    # A→B direction; the handler inverts here so consumers always see the
    # ratio from the viewing item's perspective. All four are None or all
    # four are set (DB CHECK enforces it).
    ratio_quantity_in: float | None
    ratio_unit_in: str | None
    ratio_quantity_out: float | None
    ratio_unit_out: str | None


@dataclass(frozen=True, slots=True)
class LevelChangeDto:
    changed_at: datetime
    stock_level_name: str | None
    # The level's ladder position when it still exists (None once a level is
    # deleted). The timeline reads "restocked" / "dropped" off this, never off
    # the level's name, which a household can rename (R-068).
    stock_level_sequence: int | None


# lifecycle timeline inputs. The frontend merges these
# with `level_history` (and synthesises open/checked rows from current
# state) into a single date-sorted q-timeline. Keeping them as separate
# typed lists rather than a pre-merged union lets the client style each
# event kind on its own without re-parsing strings.
@dataclass(frozen=True, slots=True)
class WasteEventDto:
    occurred_at: datetime
    reason: str


@dataclass(frozen=True, slots=True)
class ListAddEventDto:
    added_at: datetime
    shopping_list_id: UUID
    shopping_list_name: str


# History tab — the "you actually bought this" surface. Projected from
# ShoppingListLine rows on lists with `status='done'` where the line
# was ticked at Finish. Purely read-side: no new table, no dedicated
# write path — the /finish handler already stamps
# `actual_unit_price` + `purchased_store_id` on the line, plus the
# parent list's `completed_at` gives us the "when." Store name is
# resolved server-side so the SPA renders a string, not the FK.
@dataclass(frozen=True, slots=True)
class PurchaseEventDto:
    occurred_at: datetime
    quantity: int
    actual_unit_price: float | None
    store_name: str | None
    shopping_list_id: UUID
    shopping_list_name: str


# History tab — the "used in a recipe you actually cooked" surface.
# Written by POST /recipes/<id>/cook (see cook_recipe.py); projected
# here by walking the item's linked-recipe universe and pulling every
# CookEvent for those recipes. `meals_cooked` gives the SPA an
# optional badge ("Used 3× in Pasta Bake") on batch cooks.
@dataclass(frozen=True, slots=True)
class CookEventDto:
    occurred_at: datetime
    recipe_id: UUID | None
    recipe_name: str
    meals_cooked: int


# History tab — expiry-date change trail (set / pushed / cleared).
# Written by create_stock_item + update_stock_item on every date
# transition; the classifier assigns `kind` and (for pushes) a
# `delta_days`. Repeat pushes surface a "kept pushing this back"
# pattern the user can act on.
@dataclass(frozen=True, slots=True)
class ExpiryEventDto:
    occurred_at: datetime
    kind: str
    previous_expiry_date: date | None
    new_expiry_date: date | None
    delta_days: int | None


# free-text "what I actually buy" reminders (PROPOSAL_PRODUCTS_AS_OVERLAY
# §3.1). Everyday-user construct, separate from the Product overlay; always
# present, never gated by the products/money features.
@dataclass(frozen=True, slots=True)
class PreferredBuyDto:
    preferred_buy_id: UUID
    label: str


# folded shape (A1) `{total_price, total_measure, unit}`
# plus the A2 store surfacing ("Last seen at Coles") and A4-revised FK
# provenance ("from <list>" when harvested from a shopping line at /finish).
# Money-gated at the UI surfaces, not at the handler.
@dataclass(frozen=True, slots=True)
class PriceObservationDto:
    observation_id: UUID
    total_price: float
    total_measure: float
    unit: str
    observed_at: datetime
    # A2 — the store's resolved name for the chip on the detail page.
    store_name: str | None
    # A4 revised — provenance (LC-4: provenance only, not a sync link): a
    # small human label resolved server-side ("Wed's shopping list") so the
    # client renders a string, not the FK.
    shopping_list_name: str | None
    # Multipack metadata (FU-227 follow-up). When set, the obs list shows
    # "4 × 125g" instead of "500g flat"; math is unaffected.
    pack_count: int | None


# what the PriceEntry widget seeds itself with on open (F2 —
# "every field prefilled from latest observation so the common case is confirm
# one number"). Resolved server-side so the SPA renders a label, not derived
# logic. `source_label` is a short human string ("from your last log",
# "from your last receipt") — the widget shows it as a chip.
@dataclass(frozen=True, slots=True)
class PriceEntryPrefillDto:
    total_price: float
    total_measure: float
    unit: str
    store_id: UUID | None
    store_name: str | None
    source_label: str
    # When that observation was made. The label already says *where* the
    # prefill came from; without a date it can't say whether it is from
    # Tuesday or from March, which is the difference between confirming the
    # number and re-checking it (owner, 2026-09-17).
    observed_at: datetime


# populated by `build_your_prices_for_item`. R-003: every
# field is server-derived. `offers_sidecar` (LC-2) is a separate UI region
# in the widget — "Current shelf prices: $X at Y" — and never folded into
# the median.
@dataclass(frozen=True, slots=True)
class OfferSidecarDto:
    store_name: str
    price_per_unit: float
    unit: str


@dataclass(frozen=True, slots=True)
class YourPricesDto:
    baseline: float | None
    baseline_unit: str | None
    current: float | None
    above_baseline: bool
    sample_count: int
    last_observed_at: datetime | None
    last_seen_store_name: str | None
    offers_sidecar: list[OfferSidecarDto]


@dataclass(frozen=True, slots=True)
class NutrientRowDto:
    """One printed line of the per-100g table.

    Formatted server-side. The client used to hold its own copy of the label
    text, the row order, the units and the rounding policy, kept in step with
    `nutrients.py` by a comment asking the next person to remember — which is
    the duplication R-003 forbids, and it broke the moment the nutrient set
    grew. `group` is `panel` (the statement every pack carries, rendered
    inline) or `more` (the vitamins-and-minerals block, behind a disclosure);
    `indent` marks a sub-row like saturated fat under total fat."""
    label: str
    value: str
    group: str
    indent: bool


@dataclass(frozen=True, slots=True)
class LinkedNutritionFoodDto:
    """The nutrition-catalogue food a stock item is linked to. Carries its
    source so the detail page can say where the numbers came from — the same
    honesty the lookup picker applies (P3)."""
    nutrition_food_id: UUID
    name: str
    brand: str | None
    source: str
    source_label: str
    # Energy stays a first-class field: it's the one number the app treats as
    # load-bearing, and the summary line above the table renders it on its own.
    # NULL means "this source didn't say", never zero.
    kcal_per_100g: float | None
    # Everything the source knows, already formatted and in panel order. A
    # nutrient the source didn't state is simply absent — no row, no "0", no
    # em-dash (P12 No-invent).
    nutrient_rows: list[NutrientRowDto]


@dataclass(frozen=True, slots=True)
class SuggestedNutritionFoodDto:
    """A food the matcher thinks *might* describe this item. Nothing is stored
    — this is computed per read and disappears the moment the item is linked or
    ignored. `confidence` travels so the UI can visibly hedge a weak guess
    (P3 Honest); the client never re-derives the band from it (R-003)."""
    nutrition_food_id: UUID
    name: str
    brand: str | None
    source: str
    source_label: str
    kcal_per_100g: float | None
    confidence: float
    is_strong: bool


@dataclass(frozen=True, slots=True)
class StockItemDetailDto:
    stock_item_id: UUID
    name: str
    notes: str | None
    stocktake_alerts_are_enabled: bool
    stock_level_id: UUID | None
    stock_level_name: str | None
    stock_location_id: UUID | None
    stock_group_id: UUID | None
    stock_level_last_updated: datetime
    expiry_date: date | None
    is_open: bool
    opened_on: date | None
    is_essential: bool
    # usual store hint (nullable). Surfaced as a small picker on the
    # stock-item detail; drives the shopping-list grouping
    # (PROPOSAL_PRODUCTS_AS_OVERLAY §3.3) when set.
    usual_store_id: UUID | None
    products: List[LinkedProductDto]
    recipes: List[LinkedRecipeDto]
    substitutes: List[SubstituteDto]
    level_history: List[LevelChangeDto]
    # last-N lifecycle inputs for the History tab. Capped
    # at the handler so the JSON stays light on busy items; older history
    # is intentionally not surfaced here (it lives in the waste-insights /
    # spend reports surfaces instead).
    waste_events: List[WasteEventDto] = field(default_factory=list)
    recent_list_adds: List[ListAddEventDto] = field(default_factory=list)
    # 2026-06-30 — three new history-tab feeds. Capped per-kind at
    # `HISTORY_PER_KIND_CAP` (see below); older rows are counted, not
    # rendered.
    purchase_events: List[PurchaseEventDto] = field(default_factory=list)
    cook_events: List[CookEventDto] = field(default_factory=list)
    expiry_events: List[ExpiryEventDto] = field(default_factory=list)
    # 2026-06-30 — total number of history events that exist for this
    # item but were NOT included in the response because they fell past
    # the per-kind cap. Summed across every event kind (level_history +
    # waste + list-adds + purchase + cook + expiry). The SPA renders a
    # single honest footer — "N older events not shown" — instead of
    # silently truncating.
    history_older_count: int = 0
    # free-text "what I buy" reminders (always present; not gated).
    preferred_buys: List[PreferredBuyDto] = field(default_factory=list)
    # price observations. The current per-unit figure is `your_prices.current`
    # (the client never divides — R-003). Money-gated at the UI, not here.
    price_observations: List[PriceObservationDto] = field(default_factory=list)
    # what the shared PriceEntry widget should seed itself
    # with when opened (F2). Null when no prior observation exists. Resolved
    # server-side so the source label ("from your last log") stays consistent.
    price_entry_prefill: PriceEntryPrefillDto | None = None
    # None until enough price data has accrued — the widget renders the
    # "Not enough price data yet" state in that case.
    your_prices: YourPricesDto | None = None
    # every barcode that resolves to this stock item, whether
    # registered directly (source=='direct') or via a linked Product
    # (source=='via_product'). Always present; the SPA gates the surface
    # on `features.scanning`.
    barcodes: List['StockItemBarcodeDto'] = field(default_factory=list)
    # Last-checked timestamp — surfaced as a synthetic "Checked" entry in
    # the timeline whenever it differs from the most recent level change.
    last_checked_at: datetime | None = None
    # Nutrition complex-mode: the food this item is linked to, if any. Sent as
    # a resolved object rather than a bare id so the detail page can render the
    # link (name + source + per-100g) without a second round-trip. Null when
    # unlinked — which is the honest default, since a link only ever exists
    # because a human confirmed one.
    nutrition_food: 'LinkedNutritionFoodDto | None' = None
    # The auto-matcher's best guess, present only when the item is unlinked and
    # hasn't been waved off. Computed on the read rather than fetched by the SPA
    # so the suggestion arrives with the page instead of popping in after it.
    nutrition_suggestion: 'SuggestedNutritionFoodDto | None' = None
    # Whether the user has said "never suggest a food for this one". Drives the
    # detail page's undo affordance — without it, an ignored item looks
    # identical to one nothing has been suggested for.
    nutrition_ignored: bool = False


# 2026-06-30 — one number, one policy. Every event-kind projection
# below caps at this many rows (newest first); the leftover count is
# summed into `history_older_count` on the DTO so the SPA can render a
# single honest "N older events not shown" footer.
HISTORY_PER_KIND_CAP = 50


# ── Builders (one per feed) ───────────────────────────────────────────────
#
# Each feed of the detail DTO is built by its own function, so the handler
# reads as a list of feeds and the slices other surfaces need (substitutes,
# the price-entry prefill, the buy choices) are served by small endpoints in
# `get_stock_item_parts.py` instead of a full detail read (finalisation
# 06-R10 / 06-R11).


def _level_lookup(repository: Repository) -> dict[UUID, StockLevel]:
    return {lvl.id: lvl for lvl in repository.get(StockLevel).all()}


def load_stock_item_with_products(repository: Repository, stock_item_id: UUID) -> StockItem | None:
    """The item with its level, location, group and linked products (each
    product with its store and current offer)."""
    return (
        repository
        .get(StockItem)
        .include(StockItem.Fields.STOCK_LEVEL)
        .include(StockItem.Fields.STOCK_LOCATION)
        .include(StockItem.Fields.STOCK_GROUP)
        # store and current_offer are siblings on Product, so each needs
        # its own include("products") branch — chaining then_include would
        # try to resolve current_offer on Store.
        .include(StockItem.Fields.PRODUCTS)
            .then_include("store")
        .include(StockItem.Fields.PRODUCTS)
            .then_include("current_offer")
        .one(EntityField(StockItem, "id").eq(stock_item_id))
    )


def build_linked_products(stock_item: StockItem) -> List[LinkedProductDto]:
    return sorted(
        (
            LinkedProductDto(
                product_id = p.id,
                name = p.name,
                store_id = p.store.id,
                store_name = p.store.name,
                size = p.size,
                web_url = p.web_url,
                price_now = p.current_offer.price_now if p.current_offer else None,
                price_was = p.current_offer.price_was if p.current_offer else None,
            )
            for p in (stock_item.products or [])
        ),
        key=lambda d: (d.store_name.lower(), d.name.lower()),
    )


def build_preferred_buys(repository: Repository, stock_item_id: UUID) -> List[PreferredBuyDto]:
    """Free-text preferred buys, A–Z case-insensitive. FU-225 dropped the
    `position` column and the manual reorder UI; the server owns the order."""
    return sorted(
        (
            PreferredBuyDto(preferred_buy_id = pb.id, label = pb.label)
            for pb in repository.get(PreferredBuy).all(
                EntityField(PreferredBuy, PreferredBuy.Fields.STOCK_ITEM_ID).eq(stock_item_id)
            )
        ),
        key=lambda d: d.label.lower(),
    )


def build_substitutes(
    repository: Repository, stock_item_id: UUID,
    levels: dict[UUID, StockLevel] | None = None,
) -> List[SubstituteDto]:
    """The item's substitutes, read straight from the association table (the
    generic repository can't self-join StockItem, R-005 carve-out). Pairs are
    undirected: the "other side" is whichever column is *not* this item, and
    the ratio is **inverted** when viewing from the B side so the consumer
    always sees `qty_in/unit_in` as "this item" and `qty_out/unit_out` as
    "the substitute" (FU-034)."""
    session = repository.session
    levels = levels if levels is not None else _level_lookup(repository)
    assoc = db.metadata.tables["StockItemSubstitute"]
    as_a = session.execute(
        select(
            assoc.c.stock_item_b_id,
            assoc.c.notes,
            assoc.c.ratio_quantity_in,
            assoc.c.ratio_unit_in,
            assoc.c.ratio_quantity_out,
            assoc.c.ratio_unit_out,
        ).where(assoc.c.stock_item_a_id == stock_item_id)
    ).all()
    as_b = session.execute(
        select(
            assoc.c.stock_item_a_id,
            assoc.c.notes,
            # Swap the in/out pair so we display from B's side.
            assoc.c.ratio_quantity_out.label("ratio_quantity_in"),
            assoc.c.ratio_unit_out.label("ratio_unit_in"),
            assoc.c.ratio_quantity_in.label("ratio_quantity_out"),
            assoc.c.ratio_unit_in.label("ratio_unit_out"),
        ).where(assoc.c.stock_item_b_id == stock_item_id)
    ).all()
    # other_id → metadata. If both directions returned the same row
    # (shouldn't happen with canonical storage), the later wins; both are
    # equivalent semantically.
    meta_by_other: dict = {}
    for row in list(as_a) + list(as_b):
        meta_by_other[row[0]] = {
            "notes": row[1],
            "ratio_quantity_in": row[2],
            "ratio_unit_in": row[3],
            "ratio_quantity_out": row[4],
            "ratio_unit_out": row[5],
        }
    if not meta_by_other:
        return []
    sub_items = list(session.execute(
        select(StockItem).where(StockItem.id.in_(list(meta_by_other)))
    ).scalars())
    out: List[SubstituteDto] = []
    for s in sub_items:
        level = levels.get(s._stock_level_id)
        meta = meta_by_other[s.id]
        out.append(SubstituteDto(
            stock_item_id = s.id,
            name = s.name,
            stock_level_id = s._stock_level_id,
            stock_level_name = level.name if level else None,
            stock_level_sequence = level.sequence if level else None,
            notes = meta["notes"],
            ratio_quantity_in = meta["ratio_quantity_in"],
            ratio_unit_in = meta["ratio_unit_in"],
            ratio_quantity_out = meta["ratio_quantity_out"],
            ratio_unit_out = meta["ratio_unit_out"],
        ))
    return sorted(out, key=lambda d: d.name.lower())


@dataclass(slots=True)
class _HistoryTally:
    """Running count of events dropped past the per-kind cap across every
    history feed, reported as `history_older_count`."""
    older: int = 0

    def capped(self, rows: list) -> list:
        self.older += max(0, len(rows) - HISTORY_PER_KIND_CAP)
        return rows[:HISTORY_PER_KIND_CAP]


def _linked_recipe_ids(repository: Repository, stock_item_id: UUID) -> List[UUID]:
    """Recipes that use this item, from the ingredient join. `_recipe_id` and
    `_stock_item_id` are the underscore-prefixed mapper properties on
    RecipeIngredient (see table_mappings.py) — that naming keeps the FK columns
    out of verify_mappings."""
    return list(repository.session.execute(
        select(RecipeIngredient._recipe_id)
        .where(RecipeIngredient._stock_item_id == stock_item_id)
        .distinct()
    ).scalars())


def _linked_recipes(repository: Repository, recipe_ids: List[UUID]) -> List[LinkedRecipeDto]:
    if not recipe_ids:
        return []
    recipes = list(repository.session.execute(
        select(Recipe).where(Recipe.id.in_(recipe_ids))
    ).scalars())
    recipes.sort(key=lambda r: r.name.lower())
    return [LinkedRecipeDto(recipe_id=r.id, name=r.name) for r in recipes]


def _level_history(
    repository: Repository, stock_item_id: UUID,
    levels: dict[UUID, StockLevel], tally: _HistoryTally,
) -> List[LevelChangeDto]:
    changes = repository.get(StockLevelChange).all(
        EntityField(StockLevelChange, StockLevelChange.Fields.STOCK_ITEM_ID).eq(stock_item_id)
    )
    changes.sort(key=lambda c: c.changed_at, reverse=True)
    out: List[LevelChangeDto] = []
    for c in tally.capped(changes):
        level = levels.get(c.stock_level_id)
        out.append(LevelChangeDto(
            changed_at = c.changed_at,
            stock_level_name = c.stock_level_name,
            stock_level_sequence = level.sequence if level else None,
        ))
    return out


def _waste_events(repository: Repository, stock_item_id: UUID, tally: _HistoryTally) -> List[WasteEventDto]:
    """Append-only waste log (P2-06), newest first."""
    wastes = repository.get(StockItemWasteEvent).all(
        EntityField(StockItemWasteEvent, StockItemWasteEvent.Fields.STOCK_ITEM_ID).eq(stock_item_id)
    )
    wastes.sort(key=lambda w: w.occurred_at, reverse=True)
    return [WasteEventDto(occurred_at=w.occurred_at, reason=w.reason) for w in tally.capped(wastes)]


def _list_adds(
    repository: Repository, item_lines: List[ShoppingListLine], tally: _HistoryTally,
) -> List[ListAddEventDto]:
    """Every line for this item with an `added_at` stamp. Lines on finished
    lists are included on purpose: the timeline is the *item's* history, not
    the current cart."""
    lines = sorted((l for l in item_lines if l.added_at is not None), key=lambda l: l.added_at, reverse=True)
    lines = tally.capped(lines)
    if not lines:
        return []
    lists = list(repository.session.execute(
        select(ShoppingList).where(ShoppingList.id.in_({l.shopping_list_id for l in lines}))
    ).scalars())
    name_by_id = {lst.id: lst.display_name for lst in lists}
    return [
        ListAddEventDto(
            added_at = l.added_at,
            shopping_list_id = l.shopping_list_id,
            shopping_list_name = name_by_id.get(l.shopping_list_id, '(deleted list)'),
        )
        for l in lines
    ]


def _purchase_events(
    repository: Repository, item_lines: List[ShoppingListLine], tally: _HistoryTally,
) -> List[PurchaseEventDto]:
    """"You actually bought this on <date> at <store>": every line ticked on a
    list that is genuinely finished (`done` + `completed_at`; a ticked line
    on an in-flight list is mid-shop). The list's `completed_at` is the when
    (a line has no per-tick timestamp)."""
    bought = [l for l in item_lines if l.is_ticked]
    if not bought:
        return []
    session = repository.session
    list_by_id = {
        lst.id: lst for lst in session.execute(
            select(ShoppingList).where(ShoppingList.id.in_({l.shopping_list_id for l in bought}))
        ).scalars()
    }
    store_ids = {l.purchased_store_id for l in bought if l.purchased_store_id is not None}
    store_name_by_id: dict[UUID, str] = {}
    if store_ids:
        store_name_by_id = {
            s.id: s.name for s in session.execute(select(Store).where(Store.id.in_(store_ids))).scalars()
        }
    purchases = []
    for line in bought:
        lst = list_by_id.get(line.shopping_list_id)
        if lst is None or lst.status != SHOPPING_LIST_STATUS_DONE or lst.completed_at is None:
            continue
        purchases.append((lst, line))
    purchases.sort(key=lambda pair: pair[0].completed_at, reverse=True)
    return [
        PurchaseEventDto(
            occurred_at = lst.completed_at,
            quantity = line.quantity,
            actual_unit_price = line.actual_unit_price,
            store_name = (
                store_name_by_id.get(line.purchased_store_id)
                if line.purchased_store_id is not None else None
            ),
            shopping_list_id = lst.id,
            shopping_list_name = lst.display_name,
        )
        for lst, line in tally.capped(purchases)
    ]


def _cook_events(
    repository: Repository, recipe_ids: List[UUID], tally: _HistoryTally,
) -> List[CookEventDto]:
    """"You cooked a recipe that uses this ingredient", over exactly the
    linked-recipe set; `recipe_id IN (…)` rides the `cook_event_recipe_id`
    index."""
    if not recipe_ids:
        return []
    rows = list(repository.session.execute(
        select(CookEvent).where(CookEvent.recipe_id.in_(recipe_ids))
    ).scalars())
    rows.sort(key=lambda e: e.occurred_at, reverse=True)
    return [
        CookEventDto(
            occurred_at = e.occurred_at,
            recipe_id = e.recipe_id,
            recipe_name = e.recipe_name,
            meals_cooked = e.meals_cooked,
        )
        for e in tally.capped(rows)
    ]


def _expiry_events(repository: Repository, stock_item_id: UUID, tally: _HistoryTally) -> List[ExpiryEventDto]:
    """Every set / pushed / cleared expiry transition, newest first."""
    rows = repository.get(StockItemExpiryEvent).all(
        EntityField(StockItemExpiryEvent, StockItemExpiryEvent.Fields.STOCK_ITEM_ID).eq(stock_item_id)
    )
    rows.sort(key=lambda e: e.occurred_at, reverse=True)
    return [
        ExpiryEventDto(
            occurred_at = e.occurred_at,
            kind = e.kind,
            previous_expiry_date = e.previous_expiry_date,
            new_expiry_date = e.new_expiry_date,
            delta_days = e.delta_days,
        )
        for e in tally.capped(rows)
    ]


def _observations_newest_first(repository: Repository, stock_item_id: UUID) -> List[StockItemPriceObservation]:
    rows = repository.get(StockItemPriceObservation).all(
        EntityField(StockItemPriceObservation, StockItemPriceObservation.Fields.STOCK_ITEM_ID).eq(stock_item_id)
    )
    rows.sort(key=lambda o: o.observed_at, reverse=True)
    return rows


def _store_names(repository: Repository, store_ids: set) -> dict[UUID, str]:
    if not store_ids:
        return {}
    return {s.id: s.name for s in repository.get(Store).all(EntityField(Store, "id").in_(list(store_ids)))}


def _prefill_from(latest: StockItemPriceObservation, store_names: dict[UUID, str]) -> PriceEntryPrefillDto:
    """Seed the PriceEntry widget from the newest observation. A harvested
    one (it has a shopping line) says "your last receipt"; a manual one says
    "your last log"."""
    return PriceEntryPrefillDto(
        total_price = latest.total_price,
        total_measure = latest.total_measure,
        unit = latest.unit,
        store_id = latest.store_id,
        store_name = store_names.get(latest.store_id) if latest.store_id is not None else None,
        source_label = (
            "from your last receipt" if latest.shopping_list_line_id is not None else "from your last log"
        ),
        observed_at = latest.observed_at,
    )


def build_price_entry_prefill(repository: Repository, stock_item_id: UUID) -> PriceEntryPrefillDto | None:
    observations = _observations_newest_first(repository, stock_item_id)
    if not observations:
        return None
    latest = observations[0]
    return _prefill_from(latest, _store_names(repository, {latest.store_id} - {None}))


def _price_observations(
    repository: Repository, observations: List[StockItemPriceObservation], store_names: dict[UUID, str],
) -> List[PriceObservationDto]:
    """Folded-shape observations, newest first, with the store and the
    provenance list resolved to names so the SPA renders strings, not FKs."""
    line_ids = {o.shopping_list_line_id for o in observations if o.shopping_list_line_id is not None}
    list_name_by_line: dict[UUID, str] = {}
    if line_ids:
        lines = repository.get(ShoppingListLine).all(EntityField(ShoppingListLine, "id").in_(list(line_ids)))
        list_ids = {ln.shopping_list_id for ln in lines}
        lists_by_id = {
            sl.id: sl for sl in (
                repository.get(ShoppingList).all(EntityField(ShoppingList, "id").in_(list(list_ids)))
                if list_ids else []
            )
        }
        for ln in lines:
            sl = lists_by_id.get(ln.shopping_list_id)
            if sl is not None:
                list_name_by_line[ln.id] = sl.name or "shopping list"
    return [
        PriceObservationDto(
            observation_id = o.id,
            total_price = o.total_price,
            total_measure = o.total_measure,
            unit = o.unit,
            observed_at = o.observed_at,
            store_name = store_names.get(o.store_id) if o.store_id is not None else None,
            shopping_list_name = (
                list_name_by_line.get(o.shopping_list_line_id)
                if o.shopping_list_line_id is not None else None
            ),
            pack_count = o.pack_count,
        )
        for o in observations
    ]


def _your_prices(repository: Repository, stock_item_id: UUID) -> YourPricesDto:
    """The server-derived baseline + signal (R-003: the client renders it)."""
    raw = build_your_prices_for_item(repository, stock_item_id)
    return YourPricesDto(
        baseline = raw.baseline,
        baseline_unit = raw.baseline_unit,
        current = raw.current,
        above_baseline = raw.above_baseline,
        sample_count = raw.sample_count,
        last_observed_at = raw.last_observed_at,
        last_seen_store_name = raw.last_seen_store_name,
        offers_sidecar = [
            OfferSidecarDto(store_name=o.store_name, price_per_unit=o.price_per_unit, unit=o.unit)
            for o in raw.offers_sidecar
        ],
    )


def _barcodes(repository: Repository, stock_item: StockItem) -> List[StockItemBarcodeDto]:
    """Every barcode that resolves to this item: direct registrations and,
    read-only here, those on a linked product. Two targeted fetches, not a
    full-table scan (06-R8)."""
    linked_ids = {p.id for p in stock_item.products or []}
    product_names = {p.id: p.name for p in stock_item.products or []}
    rows = list(repository.get(Barcode).all(
        EntityField(Barcode, Barcode.Fields.STOCK_ITEM_ID).eq(stock_item.id)
    ))
    if linked_ids:
        seen = {b.id for b in rows}
        rows += [
            b for b in repository.get(Barcode).all(
                EntityField(Barcode, Barcode.Fields.PRODUCT_ID).in_(list(linked_ids))
            )
            if b.id not in seen
        ]
    out: List[StockItemBarcodeDto] = []
    for b in rows:
        if b.stock_item_id == stock_item.id:
            source = "direct"
        elif b.product_id is not None and b.product_id in linked_ids:
            source = "via_product"
        else:
            continue
        out.append(StockItemBarcodeDto(
            barcode_id = b.id,
            barcode = b.barcode,
            source = source,
            product_id = b.product_id,
            product_name = product_names.get(b.product_id),
        ))
    out.sort(key=lambda b: (b.source != "direct", b.barcode))
    return out


def _nutrition_food(repository: Repository, stock_item: StockItem) -> LinkedNutritionFoodDto | None:
    """The linked food, one targeted fetch. The FK is a plain UUID with no
    relationship object (R-032), so nothing is loaded implicitly."""
    if stock_item.nutrition_food_id is None:
        return None
    food = repository.get(NutritionFood).by_id(stock_item.nutrition_food_id)
    if food is None:
        return None
    return LinkedNutritionFoodDto(
        nutrition_food_id = food.id,
        name = food.name,
        brand = food.brand,
        source = food.source,
        source_label = NUTRITION_SOURCE_LABELS.get(food.source, food.source),
        kcal_per_100g = food.kcal_per_100g,
        nutrient_rows = [
            NutrientRowDto(label=row.label, value=row.value, group=row.group, indent=row.indent)
            for row in display_rows(food)
        ],
    )


def _nutrition_suggestion(repository: Repository, stock_item: StockItem) -> SuggestedNutritionFoodDto | None:
    from dora_api.features.nutrition.suggestions import suggest_for_name
    suggested = suggest_for_name(repository, stock_item.name)
    if suggested is None:
        return None
    return SuggestedNutritionFoodDto(
        nutrition_food_id = suggested.nutrition_food_id,
        name = suggested.name,
        brand = suggested.brand,
        source = suggested.source,
        source_label = suggested.source_label,
        kcal_per_100g = suggested.kcal_per_100g,
        confidence = suggested.confidence,
        is_strong = suggested.is_strong,
    )


class GetStockItemDetailHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def _nutrition_is_complex(self) -> bool:
        """Whether this install runs complex nutrition — gates the suggestion
        below, so off/simple installs don't pay a catalogue query per read.

        **Must be called before the stock item is loaded.** `get_or_create_app_
        setting` can commit, and a commit expires every object in the session;
        the StockItem's `stock_level` / `stock_location` relationships are
        mapped `lazy="noload"`, so a re-fetch after expiry silently yields None
        rather than reloading. Calling this mid-handler blanked the level and
        location on every detail read (caught by `test_patch_semantics`).
        """
        from dora_api.domain.entities.app_setting import NUTRITION_MODE_COMPLEX
        from dora_api.features.app_settings.access import get_or_create_app_setting
        setting = get_or_create_app_setting(self.repository)
        return setting.nutrition_mode == NUTRITION_MODE_COMPLEX

    def handle(self, stock_item_id: UUID) -> StockItemDetailDto | None:
        repo = self.repository
        # Read before the entity load — see the docstring above.
        nutrition_is_complex = self._nutrition_is_complex()
        stock_item = load_stock_item_with_products(repo, stock_item_id)
        if not stock_item:
            return None

        levels = _level_lookup(repo)
        recipe_ids = _linked_recipe_ids(repo, stock_item_id)
        tally = _HistoryTally()
        # One fetch of this item's lines serves both the list-adds and the
        # purchases feed (06-R7).
        item_lines: List[ShoppingListLine] = repo.get(ShoppingListLine).all(
            EntityField(ShoppingListLine, ShoppingListLine.Fields.STOCK_ITEM_ID).eq(stock_item_id)
        )
        observations = _observations_newest_first(repo, stock_item_id)
        store_names = _store_names(repo, {o.store_id for o in observations if o.store_id is not None})
        nutrition_food = _nutrition_food(repo, stock_item)
        # A suggestion only when there's nothing linked yet, the user hasn't
        # waved the item off, and complex mode has a catalogue to match.
        nutrition_ignored = bool(stock_item.nutrition_ignored)
        nutrition_suggestion = (
            _nutrition_suggestion(repo, stock_item)
            if nutrition_food is None and not nutrition_ignored and nutrition_is_complex
            else None
        )

        return StockItemDetailDto(
            stock_item_id = stock_item.id,
            name = stock_item.name,
            notes = stock_item.notes,
            stocktake_alerts_are_enabled = stock_item.stocktake_alerts_are_enabled,
            stock_level_id = stock_item.stock_level.id if stock_item.stock_level else None,
            stock_level_name = stock_item.stock_level.name if stock_item.stock_level else None,
            stock_location_id = stock_item.stock_location.id if stock_item.stock_location else None,
            stock_group_id = stock_item.stock_group.id if stock_item.stock_group else None,
            stock_level_last_updated = stock_item.stock_level_last_updated,
            expiry_date = stock_item.expiry_date,
            is_open = bool(stock_item.is_open),
            opened_on = stock_item.opened_on,
            is_essential = bool(stock_item.is_essential),
            usual_store_id = stock_item.usual_store_id,
            products = build_linked_products(stock_item),
            recipes = _linked_recipes(repo, recipe_ids),
            substitutes = build_substitutes(repo, stock_item_id, levels),
            level_history = _level_history(repo, stock_item_id, levels, tally),
            waste_events = _waste_events(repo, stock_item_id, tally),
            recent_list_adds = _list_adds(repo, item_lines, tally),
            purchase_events = _purchase_events(repo, item_lines, tally),
            cook_events = _cook_events(repo, recipe_ids, tally),
            expiry_events = _expiry_events(repo, stock_item_id, tally),
            history_older_count = tally.older,
            preferred_buys = build_preferred_buys(repo, stock_item_id),
            price_observations = _price_observations(repo, observations, store_names),
            price_entry_prefill = _prefill_from(observations[0], store_names) if observations else None,
            your_prices = _your_prices(repo, stock_item_id),
            barcodes = _barcodes(repo, stock_item),
            last_checked_at = stock_item.last_checked_at,
            nutrition_food = nutrition_food,
            nutrition_suggestion = nutrition_suggestion,
            nutrition_ignored = nutrition_ignored,
        )


@STOCK_ITEM_ROUTER.route("<uuid:stock_item_id>/detail")
def get_stock_item_detail(stock_item_id: UUID):
    _Detail = GetStockItemDetailHandler(SqlAlchemyRepository()).handle(stock_item_id)
    if _Detail is None:
        return not_found(StockItem.__name__, stock_item_id)
    _LOGGER.debug(
        "Stock item %s detail: %d products, %d recipes",
        stock_item_id, len(_Detail.products), len(_Detail.recipes),
    )
    return ok(_Detail)
