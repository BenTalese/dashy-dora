import { ICONS } from 'src/style/icons';

// Mirrors DTOs in dora_api/features/shopping_lists/.

// single source of truth for where a list is in the
// shop loop (mirrors SHOPPING_LIST_STATUS_* on the server). Replaces the old
// is_archived / is_in_progress boolean pair.
export type ShoppingListStatus = 'draft' | 'shopping' | 'done';

/** The one glyph per list state, shared by the status pill, the rail and the
 *  phone's list picker so the three can't drift (D-013: the state is never
 *  colour alone). */
export function listStatusIcon(status: ShoppingListStatus): string {
    switch (status) {
        case 'shopping': return ICONS.shopping_cart;
        case 'done': return ICONS.check;
        default: return ICONS.listDraft;
    }
}

export type ShoppingListSummary = {
    shopping_list_id: string;
    /** The user's custom name; `null` = self-labelled from dates. Use
     *  `display_name` for rendering — this field only prefills rename. */
    name: string | null;
    /** UX-v2, server-owned (R-003): custom name > planned shop date >
     *  creation date. Always render this one. */
    display_name: string;
    status: ShoppingListStatus;
    created_at: string;
    completed_at: string | null;
    /** P6-01 Chunk 7 — optional ISO date (YYYY-MM-DD) this list is planned
     *  for. Drives landing-page pick, selector sort, and shopping-day
     *  banner. `null` = unscheduled. */
    planned_shop_date: string | null;
    /** UX-v2, server-owned: finalised shop date > planned shop date >
     *  created. The summaries response arrives sorted **descending** by this
     *  (newest first, 2026-08-28) — render the rail/dropdown in payload
     *  order. */
    effective_date: string;
    /** UX-v2, server-owned: exactly one summary is flagged as the list the
     *  UI should land on / mark "next up" (§3.3 rule lives server-side). */
    is_next_up: boolean;
    line_count: number;
    ticked_count: number;
};

export type LineProductOffer = {
    product_id: string;
    name: string;
    brand: string | null;
    store_id: string;
    store_name: string;
    size: string | null;
    price_now: number | null;
    price_was: number | null;
    is_selected: boolean;
};

export type LinePreferredBuy = { preferred_buy_id: string; label: string };

/** The "which one" choice a list row and a template line both carry. One
 *  source per install, never both: offers with `features.products`, preferred
 *  buys without. */
export type LineChoice = {
    itemName: string;
    offers: LineProductOffer[];
    preferredBuys: LinePreferredBuy[];
    selectedProductId: string | null;
    preferredBuyId: string | null;
};

export function hasLineChoices(choice: LineChoice, productsEnabled: boolean): boolean {
    return productsEnabled ? choice.offers.length > 0 : choice.preferredBuys.length > 0;
}

/** Only an offer the user picked, never the cheapest-offer fallback, which
 *  prices nothing and so must not look chosen. */
export function pickedLineChoice(
    choice: LineChoice,
    productsEnabled: boolean,
): { id: string; label: string } | null {
    if (productsEnabled) {
        const offer = choice.offers.find((o) => o.product_id === choice.selectedProductId);
        return offer ? { id: offer.product_id, label: offer.name } : null;
    }
    const pb = choice.preferredBuys.find((p) => p.preferred_buy_id === choice.preferredBuyId);
    return pb ? { id: pb.preferred_buy_id, label: pb.label } : null;
}

export type ShoppingListLine = {
    line_id: string;
    /** C-7 Chunk 3 — a line is anchored by `stock_item_id` OR
     *  `product_id` (or both, when a product is nested under a stock
     *  item). NULL `stock_item_id` ⇒ standalone "product only" line. */
    stock_item_id: string | null;
    product_id: string | null;
    stock_item_name: string;
    /** The put-away dialog groups by it. */
    stock_location_id: string | null;
    stock_location_breadcrumb: string[];
    quantity: number | null;
    is_ticked: boolean;
    selected_product_id: string | null;
    sequence: number;
    /** True only when the low-stock trigger dropped this line here on its
     *  own — nothing the user did put it on the list directly. Lines from
     *  the New list dialog's auto-fill are False: the user picked those
     *  sources. Clears when the user edits the line. */
    is_auto_added: boolean;
    /** P2-02 — actual unit price the shopper typed in (override of the
     *  picked offer's price). `null` = no override; use the offer instead. */
    actual_unit_price: number | null;
    /** P2-02 — store the shopper actually bought from. `null` = use the
     *  selected_product's store (if any). */
    purchased_store_id: string | null;
    /** Resolved name for `purchased_store_id`, populated by the detail
     *  endpoint. */
    purchased_store_name: string | null;
    /** Where the user *plans* to buy this line, chosen on the plan face.
     *  Distinct from `purchased_store_id`, which records where they did.
     *  Rung 2 of the store ladder, below bought-from and above the item's
     *  standing `usual_store_id`. */
    planned_store_id: string | null;
    planned_store_name: string | null;
    /** The stock item's standing "I always buy this here". Read only to *mark*
     *  it in the store picker ("Coles (usual)"); the line's own choice is
     *  `planned_store_id`, which is prefilled from this when the line is
     *  added. */
    usual_store_id: string | null;
    /** Where the till editor's suggestion (`estimated_unit_price`) comes from,
     *  as a human label ("from your last receipt"), or null. */
    prefill_source_label: string | null;
    offers: LineProductOffer[];
    /** FU-215 — optional PreferredBuy hint on the line + the item's available
     *  labels for the picker. */
    preferred_buy_id?: string | null;
    preferred_buys?: LinePreferredBuy[];
    /** FU-448 — trim-to-budget optimiser (PROPOSAL_BUDGET_AWARE_LISTS §7.2).
     *  When true, this line was set aside by "Trim to fit" and renders under
     *  the collapsible Deferred-to-fit-budget section, not the active list.
     *  Server-owned; totals already skip these lines. */
    deferred_by_budget: boolean;
    /** Chip label frozen at trim time (one of the seven strings in brief §5).
     *  Null on non-deferred lines. */
    deferred_reason: string | null;
    /** The item's group, for the "Order by → Group" sectioning mode.
     *  `null` ⇒ the line falls into the trailing "Unsorted" section. */
    stock_group_id: string | null;
    stock_group_name: string | null;
    /** Server-resolved money ladder (R-003, never re-derive this client-side):
     *  `actual_unit_price` → the offer the user picked on the row → the last
     *  actual purchase → nothing. An unpicked offer never prices a line.
     *  `estimate_source` names the rung so the UI can label the number
     *  ("~$5.50, what you last paid"). */
    estimated_unit_price: number | null;
    estimate_source: 'actual' | 'historic' | 'offer' | 'none';
    last_paid_store_id: string | null;
    last_paid_store_name: string | null;
    /** Server-resolved store ladder: bought-this-trip → **this list's planned
     *  store** → the item's standing usual store → the store of the last actual
     *  purchase → the chosen offer's store. Intent beats history here — the
     *  reverse of the money ladder — because this answers "where do I *plan* to
     *  buy it", and the two intent rungs are ordered by specificity: a choice
     *  made for *this* list outranks a preference for the item.
     *  `null` ⇒ the "No store set" bucket. */
    resolved_store_id: string | null;
    resolved_store_name: string | null;
};

/** One bucket of the plan-face store breakdown. `store_id` is null for the
 *  catch-all. `subtotal` sums only lines that resolved a price and
 *  `priced_line_count` says how many did, so the card can admit "3 items
 *  unpriced, not counted" rather than showing a confidently short total. */
export type StoreSpend = {
    store_id: string | null;
    store_name: string;
    line_count: number;
    priced_line_count: number;
    subtotal: number;
    /** The store's own `#rrggbb`, derived from its uploaded logo. Null when
     *  it has no logo (or a greyscale one) — the card falls back to the
     *  deterministic hash swatch so a bucket always has a colour. */
    brand_colour: string | null;
};

/** Server-owned list-level money/count aggregates (state-ownership Type B).
 *  The client reads these instead of summing `priceOfLine` across the lines
 *  itself. Per-line display price stays a client concern. */
export type ShoppingListTotals = {
    total_price: number;
    remaining_price: number;
    /** Price of the ticked lines only — what's in the trolley. */
    picked_price: number;
    total_savings: number;
    unticked_count: number;
    ticked_count: number;
    line_count: number;
    /** Ordered subtotal-desc with "No store set" forced last. Empty when no
     *  active line resolved a real store — the card hides entirely rather than
     *  rendering one meaningless row. Server-owned because it sums across the
     *  collection (R-003). */
    by_store: StoreSpend[];
};

/** FU-334 — receipt-photo attachment metadata. Bytes are never inlined;
 *  the SPA loads each through `ShoppingListReceiptImage` (authed fetch, R-045). */
export type ShoppingListAttachment = {
    attachment_id: string;
    sequence: number;
};

export type ShoppingListDetail = {
    shopping_list_id: string;
    /** Custom name (`null` = self-labelled) — see ShoppingListSummary. */
    name: string | null;
    /** Resolved label to render — see ShoppingListSummary. */
    display_name: string;
    status: ShoppingListStatus;
    created_at: string;
    completed_at: string | null;
    /** P6-01 Chunk 7 — see ShoppingListSummary. */
    planned_shop_date: string | null;
    totals: ShoppingListTotals;
    lines: ShoppingListLine[];
    /** FU-334 — receipt-photo attachments, ordered by sequence. Empty array
     *  on draft lists or lists with no attachments yet. */
    attachments: ShoppingListAttachment[];
    /** FU-653 — items Dora believes you've run out of that aren't on this list.
     *  Suggestions only: nothing is added for you, and the list is the same
     *  whether or not you look at them. Empty unless the user opted the
     *  shopping surface in (Settings → Assistant), and always empty on a
     *  finished list. Capped server-side. */
    inferred_suggestions: InferredSuggestion[];
};

export type InferredSuggestion = {
    stock_item_id: string;
    name: string;
    /** The belief's own plain-English "why", e.g. "Bought about every 9 days;
     *  12 days since the last one." */
    reason: string;
};

export type ActiveListInfo = {
    shopping_list_id: string;
    name: string;
    status: ShoppingListStatus;
};

export type StockItemMembership = {
    stock_item_id: string;
    unticked_list_ids: string[];
    on_quick_add_target: boolean;
};

export type Membership = {
    quick_add_target_list_id: string | null;
    items: StockItemMembership[];
    active_lists?: ActiveListInfo[];
};

// Cart-button colour state derived from membership. The "target" is the
// inferred quick-add destination (only set when exactly one DRAFT exists).
export type CartState = 'none' | 'on_target' | 'on_other' | 'on_multiple';

export function cartStateFor(
    stockItemId: string | null,
    membership: Membership | null,
): CartState {
    if (!stockItemId || !membership) return 'none';
    const entry = membership.items.find((i) => i.stock_item_id === stockItemId);
    if (!entry || entry.unticked_list_ids.length === 0) return 'none';
    if (entry.unticked_list_ids.length > 1) return 'on_multiple';
    return entry.on_quick_add_target ? 'on_target' : 'on_other';
}

// Selected offer for a line OR the cheapest available offer as a fallback.
// Used to compute totals.
export function chosenOfferFor(line: ShoppingListLine): LineProductOffer | null {
    if (line.selected_product_id) {
        const selected = line.offers.find((o) => o.product_id === line.selected_product_id);
        if (selected) return selected;
    }
    // offers come back sorted cheapest-first from the API.
    return line.offers[0] ?? null;
}

// What this line is expected to cost. The ladder that picks the unit price
// (actual → what you last paid → offer → nothing) is resolved server-side and
// arrives as `estimated_unit_price`; this is only the quantity multiply, which
// is display math the client is allowed to own (R-003 Type C).
//
// It used to re-implement the ladder here as actual→offer. That was a second
// copy of a domain rule and it hard-required product data — a user with no
// products got zeroes even when Dora knew exactly what they last paid.
export function priceOfLine(line: ShoppingListLine): number {
    if (line.estimated_unit_price == null) return 0;
    return line.estimated_unit_price * (line.quantity ?? 1);
}

