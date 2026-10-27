import type { StockItem } from 'src/models/stockItem';
import type {
    LinkedProduct,
    PreferredBuy,
    PriceEntryPrefill,
    StockItemDetail,
    Substitute,
} from 'src/models/stockItemDetail';
import type { PantryBeliefsResponse } from 'src/models/pantryBelief';
import type { PlannedDemandResponse } from 'src/models/plannedDemand';
import type { StockItemPriceHistory } from './priceHistoryApiService';
import type { CreatedResponse } from './axiosHttpClient';
import AxiosHttpClient from './axiosHttpClient';
import { createQueryString, fetchAllPages, FilterOperator, type Page } from './queryStringBuilder';

/** FU-034 — wire-level body for substitute notes + optional ratio. All
 *  fields are optional; sending nothing clears the metadata. Direction
 *  (`*_in` = THIS item, `*_out` = the substitute) is from the perspective
 *  of the caller; the server flips into canonical storage. */
export interface SubstituteMetadataInput {
    notes?: string | null;
    ratio_quantity_in?: number | null;
    ratio_unit_in?: string | null;
    ratio_quantity_out?: number | null;
    ratio_unit_out?: string | null;
}

/** One row of `/stock-items/recently-priced` — a stock item you have logged a
 *  price for, with when you last did. Ordering is the server's. */
export type RecentlyPricedItem = {
    stock_item_id: string;
    name: string;
    last_priced_at: string;
};

export default class StockItemApiService {
    private httpClient: AxiosHttpClient;

    constructor() {
        this.httpClient = new AxiosHttpClient();
    }

    createAsync = async (stockItemToCreate: CreateStockItemCommand): Promise<CreatedResponse> =>
        await this.httpClient.post<CreatedResponse>('/stock-items', stockItemToCreate);

    deleteAsync = async (stockItemID: string): Promise<void> =>
        await this.httpClient.delete(`/stock-items/${stockItemID}`);

    getAsync = async (stockItemID: string): Promise<StockItem> => {
        const qs = createQueryString([
            { field: 'stock_item_id', operator: FilterOperator.EQUAL, value: stockItemID }
        ]);
        const page = await this.httpClient.get<Page<StockItem>>(`/stock-items${qs}`);
        return page.items[0]!;
    };

    /** Fetch a specific page of stock items. Callers that want every item
     *  use `getAllPagesAsync` below — `getAllAsync` keeps the original
     *  single-page shape for callers that only need page 1 (e.g. quick
     *  lookups that don't paginate). */
    getAllAsync = async (
        pagination?: { page: number; limit: number },
    ): Promise<Page<StockItem>> => {
        const qs = pagination
            ? createQueryString(undefined, undefined, pagination)
            : '';
        return await this.httpClient.get<Page<StockItem>>(`/stock-items${qs}`);
    };

    /** Every stock item, paged (FU-035): the overview filters client-side. */
    getAllPagesAsync = async (): Promise<StockItem[]> =>
        await fetchAllPages((page, limit) => this.getAllAsync({ page, limit }));

    getDetailAsync = async (stockItemID: string): Promise<StockItemDetail> =>
        await this.httpClient.get<StockItemDetail>(`/stock-items/${stockItemID}/detail`);

    // One slice of the detail each, for surfaces that need only that slice
    // (a full detail read runs every feed).
    getSubstitutesAsync = async (stockItemID: string): Promise<Substitute[]> =>
        (await this.httpClient.get<{ items: Substitute[] }>(`/stock-items/${stockItemID}/substitutes`)).items;

    getPriceEntryPrefillAsync = async (stockItemID: string): Promise<PriceEntryPrefill | null> =>
        (await this.httpClient.get<{ prefill: PriceEntryPrefill | null }>(
            `/stock-items/${stockItemID}/price-entry-prefill`,
        )).prefill;

    getBuyChoicesAsync = async (
        stockItemID: string,
    ): Promise<{ preferred_buys: PreferredBuy[]; products: LinkedProduct[] }> =>
        await this.httpClient.get<{ preferred_buys: PreferredBuy[]; products: LinkedProduct[] }>(
            `/stock-items/${stockItemID}/buy-choices`,
        );

    /** P8-07 — inferred pantry beliefs for every stock item (keyed by id).
     *  `enabled: false` when the user has inference switched off. */
    getPantryBeliefsAsync = async (): Promise<PantryBeliefsResponse> =>
        await this.httpClient.get<PantryBeliefsResponse>('/stock-items/beliefs');

    /** Planned demand — what the upcoming plan needs, keyed by stock item id.
     *  Sibling to the beliefs call and deliberately the same shape; the two
     *  answer different questions (what's on the shelf vs what the plan will
     *  want), so they are separate endpoints rather than one fatter one.
     *  `enabled: false` when the meal planner is switched off install-wide. */
    getPlannedDemandAsync = async (): Promise<PlannedDemandResponse> =>
        await this.httpClient.get<PlannedDemandResponse>('/stock-items/planned-demand');

    /** FU-315 — the server returns a 200 with `{ auto_added: { line_id,
     *  shopping_list_id } }` when a level transition to Low/Out fires the
     *  auto-add-when-low hook (`update_stock_item.py:255-263`). Non-trigger
     *  updates come back as 204 (undefined). Callers use this to toast
     *  "Added <item> to <list>" + refresh the shopping-list store. */
    /** "+N days" on the expiry: from the later of the household's today and
     *  the current expiry (the rule lives server-side, R-003 / R-021). */
    pushExpiryAsync = async (stockItemId: string, days: number): Promise<{ expiry_date: string }> =>
        await this.httpClient.post<{ expiry_date: string }, { days: number }>(
            `/stock-items/${stockItemId}/push-expiry`,
            { days },
        );

    updateAsync = async (
        stockItemToUpdate: UpdateStockItemCommand,
    ): Promise<UpdateStockItemResponse> => {
        const { stock_item_id, ...payload } = stockItemToUpdate;
        return await this.httpClient.patch<UpdateStockItemResponse>(
            `/stock-items/${stock_item_id}`,
            payload,
        );
    };

    linkProductAsync = async (stockItemID: string, productID: string): Promise<void> =>
        await this.httpClient.post<void>(`/stock-items/${stockItemID}/products`, {
            product_id: productID
        });

    unlinkProductAsync = async (stockItemID: string, productID: string): Promise<void> =>
        await this.httpClient.delete<void>(`/stock-items/${stockItemID}/products/${productID}`);

    moveAsync = async (
        stockItemID: string,
        destinationLocationId: string | null
    ): Promise<void> =>
        await this.httpClient.patch<void>(`/stock-items/${stockItemID}/move`, {
            destination_location_id: destinationLocationId
        });

    /** Bulk-bar counterparts to `moveAsync` / the level PATCH. One request
     *  for the whole selection instead of one per item — see
     *  `dora_api/features/stock_items/bulk_operations.py` for why the server
     *  still runs the same per-item rules underneath. */
    bulkMoveAsync = async (
        stockItemIds: string[],
        destinationLocationId: string | null,
    ): Promise<{ moved_count: number; missing_ids: string[] }> =>
        await this.httpClient.post<{ moved_count: number; missing_ids: string[] }>(
            '/stock-items/bulk-move',
            {
                stock_item_ids: stockItemIds,
                destination_location_id: destinationLocationId,
            },
        );

    bulkSetLevelAsync = async (
        stockItemIds: string[],
        stockLevelId: string,
    ): Promise<{ updated_count: number; failed_ids: string[] }> =>
        await this.httpClient.post<{ updated_count: number; failed_ids: string[] }>(
            '/stock-items/bulk-set-level',
            { stock_item_ids: stockItemIds, stock_level_id: stockLevelId },
        );

    addSubstituteAsync = async (
        stockItemID: string,
        substituteID: string,
        metadata?: SubstituteMetadataInput,
    ): Promise<void> =>
        await this.httpClient.post<void>(`/stock-items/${stockItemID}/substitutes`, {
            substitute_id: substituteID,
            ...(metadata ?? {}),
        });

    removeSubstituteAsync = async (stockItemID: string, substituteID: string): Promise<void> =>
        await this.httpClient.delete<void>(
            `/stock-items/${stockItemID}/substitutes/${substituteID}`
        );

    /** FU-034 — edit the notes / structured ratio on an existing substitute
     *  pair. Direction is from THIS stock item's perspective; the server
     *  flips it into canonical storage. Sending an empty body clears the
     *  metadata (notes → null, ratio fields → null). */
    updateSubstituteAsync = async (
        stockItemID: string,
        substituteID: string,
        metadata: SubstituteMetadataInput,
    ): Promise<void> =>
        await this.httpClient.patch<void>(
            `/stock-items/${stockItemID}/substitutes/${substituteID}`,
            metadata,
        );

    // preferred buys (free-text reminders on a stock item).
    addPreferredBuyAsync = async (stockItemID: string, label: string): Promise<void> =>
        await this.httpClient.post<void>(`/stock-items/${stockItemID}/preferred-buys`, { label });

    updatePreferredBuyAsync = async (
        stockItemID: string, preferredBuyID: string, label: string,
    ): Promise<void> =>
        await this.httpClient.patch<void>(
            `/stock-items/${stockItemID}/preferred-buys/${preferredBuyID}`, { label },
        );

    deletePreferredBuyAsync = async (stockItemID: string, preferredBuyID: string): Promise<void> =>
        await this.httpClient.delete<void>(
            `/stock-items/${stockItemID}/preferred-buys/${preferredBuyID}`,
        );

    // `reorderPreferredBuysAsync` removed — the SPA now
    // sorts alphabetically client-side and the backend dropped `position` +
    // the `/preferred-buys/reorder` endpoint.

    // folded shape ({total_price, total_measure, unit}).
    // Optional store_id (A2). Provenance FK is only set by /finish harvest
    // server-side (chunk 5), not by this manual endpoint. Money-gated at UI.
    addPriceObservationAsync = async (
        stockItemID: string,
        observation: {
            total_price: number;
            total_measure: number;
            unit: string;
            observed_at?: string;
            store_id?: string | null;
            pack_count?: number | null;
        },
    ): Promise<void> =>
        await this.httpClient.post<void>(
            `/stock-items/${stockItemID}/price-observations`, observation,
        );

    /** Stock items with the most recent price observation, newest first —
     *  the log-price picker's shortlist (owner, 2026-09-04). Server-ordered
     *  (`recently_priced.py`); the client never re-sorts. Best-effort at the
     *  call site: on failure the picker falls back to its level ordering. */
    getRecentlyPricedAsync = async (limit = 12): Promise<RecentlyPricedItem[]> =>
        await this.httpClient.get<RecentlyPricedItem[]>(
            `/stock-items/recently-priced?limit=${limit}`,
        );

    deletePriceObservationAsync = async (stockItemID: string, observationID: string): Promise<void> =>
        await this.httpClient.delete<void>(
            `/stock-items/${stockItemID}/price-observations/${observationID}`,
        );

    // unioned price-history series (observations ∪ linked
    // offers, normalised per-unit server-side) for the "Full history"
    // bottom-sheet. Money-gated at the UI surface that opens the sheet.
    getPriceHistoryAsync = async (stockItemID: string): Promise<StockItemPriceHistory> =>
        await this.httpClient.get<StockItemPriceHistory>(
            `/stock-items/${stockItemID}/price-history`,
        );
}

export type CreateStockItemCommand = {
    name: string;
    stock_level_id: string;
    stock_location_id: string | null;
    stock_group_id?: string | null;
    expiry_date?: string | null;
    is_essential?: boolean;
    is_open?: boolean;
    /** Per-item stocktake mute. Omit to take the install-wide
     *  `stocktake_new_items_opt_in` default (what callers that don't render
     *  the toggle — imports, scan flows — should do). */
    stocktake_alerts_are_enabled?: boolean;
    /** Usual store hint. No clear flag: a create has nothing to clear. */
    usual_store_id?: string | null;
};

/** Server-populated payload on a level-transition PATCH that fires the
 *  low-stock auto-add hook (FU-511: driven by `AppSetting.auto_add_mode`
 *  + `is_essential`). Undefined body means no trigger fired (server returned
 *  204). See `update_stock_item.py` `_try_auto_add`. */
export type UpdateStockItemResponse = {
    auto_added?: {
        line_id: string;
        shopping_list_id: string;
    };
} | undefined;

export type UpdateStockItemCommand = {
    stock_item_id: string;
    name?: string;
    notes?: string | null;
    stocktake_alerts_are_enabled?: boolean;
    stock_level_id?: string;
    stock_location_id?: string | null;
    stock_group_id?: string | null;
    expiry_date?: string | null;
    is_essential?: boolean;
    is_open?: boolean;
    opened_on?: string | null;
    /** FU-189 — usual store hint. UUID to bind; use `clear_usual_store` to clear. */
    usual_store_id?: string | null;
    clear_usual_store?: boolean;
    /** Explicit clear flags for nullable lazy-noload FKs — see
     *  `update_stock_item.py` for why the relationship-only null assignment
     *  doesn't actually persist. The SPA sends these from the picker's X. */
    clear_stock_location?: boolean;
    clear_stock_group?: boolean;
    /** Nutrition complex-mode — the catalogue food whose per-100g values
     *  describe this item. UUID to bind; `clear_nutrition_food` to unlink.
     *  Only ever sent from the picker's explicit confirm, or from accepting a
     *  suggestion — which is the same confirm, just with the search already
     *  done for you. */
    nutrition_food_id?: string;
    clear_nutrition_food?: boolean;
    /** "Never suggest a food for this one" (dish soap). Drops the item out of
     *  the matching queue for good. A plain bool rather than a clear flag —
     *  unlike the FK above, false and absent mean different things only here,
     *  so omitting it leaves the current value alone. */
    nutrition_ignored?: boolean;
    /** P8-07 / FU-449 — consumption context. When a level DROP is the result
     *  of cooking (or another depletion), the server records a
     *  ConsumptionEvent so run-out prediction + the belief blend cooking with
     *  purchases. `consumption_source` ∈ 'cook' | 'manual' | 'waste'. */
    consumption_source?: 'cook' | 'manual' | 'waste';
    consumption_recipe_id?: string;
};
