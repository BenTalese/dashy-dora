// The suggestion shape is owned by the nutrition API service — the matching
// page and this page render the same object, and a second declaration here
// would drift from it (R-002).
import type { NutritionFoodSuggestion } from 'src/services/api/nutritionApiService';

export type { NutritionFoodSuggestion };

export type LinkedProduct = {
    product_id: string;
    name: string;
    store_id: string;
    store_name: string;
    size: string | null;
    web_url: string | null;
    price_now: number | null;
    price_was: number | null;
};

export type LinkedRecipe = {
    recipe_id: string;
    name: string;
};

/** FU-056 — one barcode that resolves to this stock item. Surface gated on
 *  `features.scanning`. */
export type StockItemBarcode = {
    barcode_id: string;
    barcode: string;
    /** 'direct' — registered against this stock item. Editable on this
     *  surface. 'via_product' — reaches this item via a linked Product;
     *  read-only here (edit on the Product). */
    source: 'direct' | 'via_product';
    product_id: string | null;
    product_name: string | null;
};

export type Substitute = {
    stock_item_id: string;
    name: string;
    stock_level_id: string | null;
    stock_level_name: string | null;
    /** Ladder position (0 stocked, 1 low, 2 out); null when unlevelled. */
    stock_level_sequence: number | null;
    /** FU-034 — free-text hint shown in the substitute list and in the
     *  cook-mode swap picker. Null when the user didn't set one. */
    notes: string | null;
    /** FU-034 — optional structured ratio. Always returned from the API
     *  oriented "this item → substitute" — the server inverts canonical
     *  storage so the consumer never has to think about direction. All
     *  four fields are null, or all four are set. */
    ratio_quantity_in: number | null;
    ratio_unit_in: string | null;
    ratio_quantity_out: number | null;
    ratio_unit_out: string | null;
};

export type LevelChange = {
    changed_at: string; // ISO datetime
    stock_level_name: string | null;
    /** Ladder position when the level still exists; null once deleted. */
    stock_level_sequence: number | null;
};

// lifecycle timeline inputs. The History tab merges
// these with `level_history` (and synthesises Opened/Checked rows from
// current state) into a single date-sorted q-timeline.
export type WasteEvent = {
    occurred_at: string; // ISO datetime
    reason: string;
};

export type ListAddEvent = {
    added_at: string; // ISO datetime
    shopping_list_id: string;
    shopping_list_name: string;
};

// 2026-06-30 History tab — "you actually bought this on <date> at
// <store>." Server-side projection of ticked shopping-list lines on
// finished lists. `actual_unit_price` and `store_name` are both
// nullable — a Finish with the till-total field left blank still
// counts as a purchase for the timeline.
export type PurchaseEvent = {
    occurred_at: string; // ISO datetime (parent list's completed_at)
    quantity: number;
    actual_unit_price: number | null;
    store_name: string | null;
    shopping_list_id: string;
    shopping_list_name: string;
};

// 2026-06-30 History tab — "you cooked a recipe that uses this
// ingredient." Server-side join across the item's linked recipes
// and the CookEvent log. `meals_cooked` gives the timeline entry
// an optional badge ("×3") on batch cooks.
export type CookEvent = {
    occurred_at: string; // ISO datetime
    recipe_id: string | null;
    recipe_name: string;
    meals_cooked: number;
};

// 2026-06-30 History tab — expiry-date change trail. `kind` is one
// of 'set' | 'pushed' | 'cleared'; `delta_days` only populated on
// pushed entries.
export type ExpiryEvent = {
    occurred_at: string; // ISO datetime
    kind: 'set' | 'pushed' | 'cleared';
    previous_expiry_date: string | null; // ISO date (YYYY-MM-DD)
    new_expiry_date: string | null;      // ISO date (YYYY-MM-DD)
    delta_days: number | null;
};

// free-text "what I actually buy" reminders on a stock item
// (PROPOSAL_PRODUCTS_AS_OVERLAY §3.1). Everyday-user construct, separate from
// the Product overlay; always present, never gated.
export type PreferredBuy = {
    preferred_buy_id: string;
    label: string;
};

// folded shape (A1). Money-gated at the UI. Per-unit cost
// derived server-side (R-003) — client never divides total_price by total_measure.
// `store_name` populated when a store was attached at entry (A2). When the row
// was harvested from a finished shopping line at /finish (chunk 5),
// `shopping_list_name` carries the provenance label ("from Wed's shopping
// list"); null for manual entries.
export type PriceObservation = {
    observation_id: string;
    total_price: number;
    total_measure: number;
    unit: string;
    observed_at: string; // ISO datetime
    store_name: string | null;
    shopping_list_name: string | null;
    /** Multipack metadata (FU-227 follow-up). When set, the obs list
     *  renders "4 × 125g" instead of "500g flat". Math is unaffected —
     *  `total_measure` is still the TOTAL. */
    pack_count: number | null;
};

// what the PriceEntry widget seeds itself with on open (F2).
// Resolved server-side so the source_label stays consistent. Null when no
// prior observation exists for the item.
export type PriceEntryPrefill = {
    total_price: number;
    total_measure: number;
    unit: string;
    store_id: string | null;
    store_name: string | null;
    /** Short human chip ("from your last log" / "from your last receipt"). */
    source_label: string;
    /** When that observation was made. The label says where the number came
     *  from; this says when, which is what tells you whether to confirm it or
     *  re-check it. */
    observed_at: string;
};

// server-derived baseline + signal (R-003). The widget
// reads booleans / numbers and renders; never re-computes. `offers_sidecar`
// (LC-2) is a separate UI region — never folded into the median or count.
export type OfferSidecar = {
    store_name: string;
    price_per_unit: number;
    unit: string;
};

export type YourPrices = {
    baseline: number | null;
    baseline_unit: string | null;
    current: number | null;
    above_baseline: boolean;
    sample_count: number;
    last_observed_at: string | null; // ISO datetime
    last_seen_store_name: string | null;
    offers_sidecar: OfferSidecar[];
};

export type StockItemDetail = {
    stock_item_id: string;
    name: string;
    notes: string | null;
    stocktake_alerts_are_enabled: boolean;
    stock_level_id: string | null;
    stock_level_name: string | null;
    stock_location_id: string | null;
    stock_group_id: string | null;
    stock_level_last_updated: string; // ISO datetime
    expiry_date: string | null;
    is_open: boolean;
    opened_on: string | null;
    is_essential: boolean;
    /** FU-189 — usual store hint (nullable). Drives the shopping-list
     *  grouping + a small picker on the stock-item detail. */
    usual_store_id: string | null;
    products: LinkedProduct[];
    recipes: LinkedRecipe[];
    substitutes: Substitute[];
    /** FU-056 — barcodes (direct + via-Product). Empty when scanning is off
     *  or none are registered. */
    barcodes: StockItemBarcode[];
    level_history: LevelChange[];
    /** C-1b.5 / INV-7 — append-only waste log entries for this item,
     *  newest first, capped on the server. Empty when nothing thrown
     *  out (the common case). */
    waste_events?: WasteEvent[];
    /** C-1b.5 / INV-7 — past shopping-list adds for this item (any list
     *  status), newest first, capped on the server. */
    recent_list_adds?: ListAddEvent[];
    /** 2026-06-30 — three new history-tab feeds: what you actually bought,
     *  which cooked recipes consumed this ingredient, and every expiry
     *  transition. All capped on the server (see HISTORY_PER_KIND_CAP). */
    purchase_events?: PurchaseEvent[];
    cook_events?: CookEvent[];
    expiry_events?: ExpiryEvent[];
    /** 2026-06-30 — total number of history events that exist for this
     *  item but were NOT included above because they fell past the
     *  per-kind cap. Summed across every event kind. Drives the honest
     *  "N older events not shown" footer under the timeline. */
    history_older_count?: number;
    /** FU-211 — free-text "what I buy" reminders, A–Z (server order).
     *  Always present (not gated by products/money). */
    preferred_buys?: PreferredBuy[];
    /** FU-213 — price observations (newest first). Money-gated at the UI. */
    price_observations?: PriceObservation[];
    /** FU-227 chunk 3 — what the PriceEntry widget should seed itself with
     *  on open (F2). Null when no prior observation exists for this item. */
    price_entry_prefill?: PriceEntryPrefill | null;
    /** FU-227 — the server-derived baseline / current / above-usual block
     *  the "Your prices" widget renders. */
    your_prices?: YourPrices | null;
    /** X1 — last "still correct" check; surfaced in the lifecycle
     *  timeline as a synthetic Checked entry when it differs from the
     *  most recent level change. Null = never checked. */
    last_checked_at?: string | null;
    /** Nutrition complex-mode — the catalogue food this item is linked to.
     *  Null when unlinked, which is the honest default: a link only exists
     *  because a human confirmed one in the picker. Carries its source so the
     *  page can say where the numbers came from. */
    nutrition_food?: LinkedNutritionFood | null;
    /** The matcher's best guess for an unlinked item, computed on the read and
     *  never stored. Present only in complex mode, only while the item is both
     *  unlinked and not ignored — so its absence means "nothing to offer", not
     *  "not loaded yet". */
    nutrition_suggestion?: NutritionFoodSuggestion | null;
    /** The user said "never suggest a food for this one" (dish soap). Distinct
     *  from simply being unlinked, and what stops the matcher re-asking. */
    nutrition_ignored?: boolean;
};

/** One printed line of the per-100g table, formatted by the server.
 *
 *  `group` splits the standard panel (`panel` — rendered inline) from the
 *  optional vitamins-and-minerals block (`more` — behind a disclosure);
 *  `indent` marks a sub-row, the way a pack prints saturated fat under total
 *  fat. Which nutrients exist, their order, their units and their rounding are
 *  all decided in `dora_api/features/nutrition/nutrients.py` — the client
 *  deliberately holds no copy of any of it (R-003). */
export type NutrientRow = {
    label: string;
    /** Already formatted, unit included: "2.6 g", "412 kcal". */
    value: string;
    group: 'panel' | 'more';
    indent: boolean;
};

export type LinkedNutritionFood = {
    nutrition_food_id: string;
    name: string;
    brand: string | null;
    source: string;
    source_label: string;
    /** Per 100g. `null` means the source didn't carry it — render as absent,
     *  never as zero. Energy is the one nutrient the app treats as
     *  load-bearing, so it stays a number here as well as a formatted row. */
    kcal_per_100g: number | null;
    /** Everything the source knows, in panel order. A nutrient it didn't state
     *  is simply not in the list. */
    nutrient_rows: NutrientRow[];
};
