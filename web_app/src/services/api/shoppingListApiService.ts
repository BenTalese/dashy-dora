import type {
    Membership,
    ShoppingListDetail,
    ShoppingListStatus,
    ShoppingListSummary
} from 'src/models/shoppingList';
import AxiosHttpClient from './axiosHttpClient';

export type CreateShoppingListCommand = {
    name?: string;
    /** P6-01 Chunk 7 — ISO date (YYYY-MM-DD). Optional. */
    planned_shop_date?: string | null;
};

export type UpdateShoppingListCommand = {
    /** UX-v2 — explicit `null` clears the custom name (the list then
     *  self-labels from its dates); omitting leaves it alone. */
    name?: string | null;
    /** FU-227 chunk 5 (E3) — a list becomes `done` only via POST /finish
     *  (which snapshots prices + restocks). PATCH can move it between
     *  draft/shopping; the server 400s on `status: 'done'` here. */
    status?: Exclude<ShoppingListStatus, 'done'>;
    /** P6-01 Chunk 7 — explicit `null` clears; omitting leaves it alone. */
    planned_shop_date?: string | null;
};

export type AddLineCommand = {
    /** C-7 Chunk 3 — a line may anchor on a stock item, a product, or
     *  both. At least one MUST be set; server returns 400 otherwise. */
    stock_item_id?: string | null;
    product_id?: string | null;
    quantity?: number | null;
    selected_product_id?: string | null;
    preferred_buy_id?: string | null;
};

export type UpdateLineCommand = {
    quantity?: number | null;
    is_ticked?: boolean;
    selected_product_id?: string | null;
    clear_selected_product?: boolean;
    sequence?: number;
    /** P2-02 — what the shopper actually paid per unit. Use
     *  `clear_actual_unit_price` to wipe a prior override (passing `null`
     *  here is treated as "leave alone" by the backend). */
    actual_unit_price?: number | null;
    clear_actual_unit_price?: boolean;
    /** P2-02 — store the shopper actually bought from. */
    purchased_store_id?: string | null;
    clear_purchased_store?: boolean;
    /** Where the user plans to buy it, set from the plan face. Never feeds a
     *  price observation — it isn't a purchase record. */
    planned_store_id?: string | null;
    clear_planned_store?: boolean;
    /** FU-215 — optional PreferredBuy hint on the line. */
    preferred_buy_id?: string | null;
    clear_preferred_buy?: boolean;
    /** FU-448 — "Add back" from the Deferred-to-fit-budget section.
     *  Only ever sent as `false`. Server clears the frozen reason chip
     *  in lock-step. */
    deferred_by_budget?: boolean;
};

/** FU-448 — POST /shopping-lists/<id>/trim-to-budget request/response. */
export type TrimToBudgetCommand = {
    /** `"preview"` computes cuts without mutation; `"apply"` sets
     *  `deferred_by_budget=true` on the chosen lines and returns the
     *  same shape with `applied: true`. */
    mode: 'preview' | 'apply';
    /** Override the target headroom. Omit to use the user's
     *  period-remaining budget for the shop's expected period. */
    budget_target?: number | null;
    /** Line IDs the user has explicitly kept from the preview. */
    exclude_line_ids?: string[];
};

export type TrimmedLine = {
    line_id: string;
    tier: number;
    reason_chip: string;
    saved: number;
};

export type TrimToBudgetResult = {
    projected_total: number;
    /** `null` when the user has no budget set (feature self-gates off). */
    budget_target: number | null;
    overshoot: number;
    trimmed: TrimmedLine[];
    /** `>0` when the safe-cut tiers exhausted before hitting the target. */
    still_over: number;
    applied: boolean;
};

export type FinishResult = {
    items_restocked: number;
};

export type QuickAddCandidate = {
    shopping_list_id: string;
    name: string;
};

/** Discriminated outcome of the quick-add endpoint. The target list is
 *  inferred from DRAFT count — the server replies with `ambiguous` when 2+
 *  drafts exist, expecting the client to pick (and remember the choice in
 *  sessionStorage).
 */
export type QuickAddResult =
    | {
          result: 'added';
          shopping_list_id: string;
          line_id: string | null;
          already_on_list: boolean;
      }
    | { result: 'no_draft' }
    | { result: 'ambiguous'; candidates: QuickAddCandidate[] };

export type AutoGenerateSources = {
    low_stock?: boolean;
    out_of_stock?: boolean;
    essentials_only_for_low?: boolean;
    /** Every essential item, whatever its stock level. */
    essentials?: boolean;
    frequently_added?: boolean;
    frequently_added_limit?: number;
    /** ISO date (YYYY-MM-DD) marking the start of the meal-plan week. */
    meal_plan_week?: string | null;
    recipes?: string[];
};

export type AutoGenerateCommand = {
    name?: string | null;
    sources: AutoGenerateSources;
    merge_into_list_id?: string | null;
};

export type AutoGenerateLine = {
    line_id: string;
    stock_item_id: string;
};

/** FU-505 — a recipe / meal-plan ingredient that couldn't be turned into
 *  a shopping-list line because it isn't linked to any StockItem. The SPA
 *  renders these as a "you'll need to add these manually" banner right
 *  after the auto-generate call resolves. */
export type AutoGenerateUnlinkedSkip = {
    recipe_name: string;
    ingredient_name: string;
};

export type AutoGenerateResult = {
    shopping_list_id: string | null;
    added_count: number;
    skipped_already_on_list: number;
    nothing_to_add: boolean;
    lines: AutoGenerateLine[];
    /** FU-505 — recipe ingredients auto-gen couldn't include. Empty when
     *  every ingredient was either linked or already stocked. */
    unlinked_skipped: AutoGenerateUnlinkedSkip[];
};

export type MoveUntickedResult = {
    moved_count: number;
    skipped_duplicates: number;
};

export type BackToDraftResult = {
    unticked_count: number;
};

export type ClearListResult = {
    removed_count: number;
};

/** Ranked ids only (most-added first) — the sheet holds the items themselves
 *  (finalisation 03-R14). */
export type FrequentlyAddedItem = {
    stock_item_id: string;
};

export default class ShoppingListApiService {
    private httpClient = new AxiosHttpClient();

    getAllAsync = async (): Promise<ShoppingListSummary[]> =>
        await this.httpClient.get<ShoppingListSummary[]>('/shopping-lists');

    getDetailAsync = async (id: string): Promise<ShoppingListDetail> =>
        await this.httpClient.get<ShoppingListDetail>(`/shopping-lists/${id}`);

    getMembershipAsync = async (): Promise<Membership> =>
        await this.httpClient.get<Membership>('/shopping-lists/membership');

    createAsync = async (command: CreateShoppingListCommand): Promise<{ shopping_list_id: string }> =>
        await this.httpClient.post<{ shopping_list_id: string }>('/shopping-lists', command);

    updateAsync = async (id: string, command: UpdateShoppingListCommand): Promise<void> =>
        await this.httpClient.patch<void, UpdateShoppingListCommand>(
            `/shopping-lists/${id}`,
            command,
        );

    deleteAsync = async (id: string): Promise<void> =>
        await this.httpClient.delete<void>(`/shopping-lists/${id}`);

    /** Finishing takes no options: every ticked line restocks to Stocked. */
    finishAsync = async (id: string): Promise<FinishResult> =>
        await this.httpClient.post<FinishResult, Record<string, never>>(
            `/shopping-lists/${id}/finish`,
            {},
        );

    // `copyAsync` went with copy-to-new-list: the picker's kebab and the Export
    // menu were its only callers, and **Save as template** is the same idea
    // under a name that says what it's for. Server endpoint still exists —
    // FU-766.

    addLineAsync = async (listId: string, command: AddLineCommand): Promise<{ line_id: string; already_on_list: boolean }> =>
        await this.httpClient.post<{ line_id: string; already_on_list: boolean }, AddLineCommand>(
            `/shopping-lists/${listId}/lines`,
            command,
        );

    /** Add a whole selection in one round-trip. De-duplication is the same
     *  `AddLineHandler` rule the single-line endpoint uses — the server loops
     *  it — so `already_on_list` counts what was skipped. */
    bulkAddLinesAsync = async (
        listId: string,
        stockItemIds: string[],
    ): Promise<{ added: number; already_on_list: number; failed_ids: string[] }> =>
        await this.httpClient.post<
            { added: number; already_on_list: number; failed_ids: string[] },
            { stock_item_ids: string[] }
        >(`/shopping-lists/${listId}/lines/bulk-add`, { stock_item_ids: stockItemIds });

    /** The inverse. Idempotent per item, so `removed_count` is how many were
     *  actually on the list — not how many ids were sent. */
    bulkRemoveByStockItemAsync = async (
        listId: string,
        stockItemIds: string[],
    ): Promise<{ removed_count: number }> =>
        await this.httpClient.post<
            { removed_count: number },
            { stock_item_ids: string[] }
        >(`/shopping-lists/${listId}/lines/bulk-remove-by-stock-item`, {
            stock_item_ids: stockItemIds,
        });

    updateLineAsync = async (listId: string, lineId: string, command: UpdateLineCommand): Promise<void> =>
        await this.httpClient.patch<void, UpdateLineCommand>(
            `/shopping-lists/${listId}/lines/${lineId}`,
            command,
        );

    deleteLineAsync = async (listId: string, lineId: string): Promise<void> =>
        await this.httpClient.delete<void>(`/shopping-lists/${listId}/lines/${lineId}`);

    // FU-573: returns whether a line was actually removed. The endpoint is an
    // idempotent no-op (success) when the item isn't on the list, so callers
    // fanning out over multiple lists count `removed` rather than every 2xx.
    removeByStockItemFromListAsync = async (
        listId: string,
        stockItemId: string,
    ): Promise<{ removed: boolean }> =>
        await this.httpClient.delete<{ removed: boolean }>(
            `/shopping-lists/${listId}/lines/by-stock-item/${stockItemId}`,
        );

    quickAddAsync = async (
        stockItemId: string,
        shoppingListId?: string,
    ): Promise<QuickAddResult> =>
        await this.httpClient.post<
            QuickAddResult,
            { stock_item_id: string; shopping_list_id?: string }
        >('/shopping-lists/quick-add/lines', {
            stock_item_id: stockItemId,
            ...(shoppingListId ? { shopping_list_id: shoppingListId } : {}),
        });

    autoGenerateAsync = async (
        command: AutoGenerateCommand,
    ): Promise<AutoGenerateResult> =>
        await this.httpClient.post<AutoGenerateResult, AutoGenerateCommand>(
            '/shopping-lists/auto-generate',
            command,
        );

    /** FU-448 — trim-to-budget optimiser. Preview or apply. */
    trimToBudgetAsync = async (
        listId: string,
        command: TrimToBudgetCommand,
    ): Promise<TrimToBudgetResult> =>
        await this.httpClient.post<TrimToBudgetResult, TrimToBudgetCommand>(
            `/shopping-lists/${listId}/trim-to-budget`,
            command,
        );

    moveUntickedToAsync = async (
        sourceId: string,
        targetId: string,
    ): Promise<MoveUntickedResult> =>
        await this.httpClient.post<MoveUntickedResult, Record<string, never>>(
            `/shopping-lists/${sourceId}/move-unticked-to/${targetId}`,
            {},
        );

    /** The finish dialog's "discard" disposition — deletes the unticked
     *  lines so they don't strand on the archived receipt. */
    discardUntickedAsync = async (
        listId: string,
    ): Promise<{ removed_count: number }> =>
        await this.httpClient.post<{ removed_count: number }, Record<string, never>>(
            `/shopping-lists/${listId}/discard-unticked`,
            {},
        );

    startShoppingAsync = async (id: string): Promise<void> =>
        await this.httpClient.post<void, Record<string, never>>(
            `/shopping-lists/${id}/start`,
            {},
        );

    /** The reverse of `startShoppingAsync` — an undo for pressing the wrong
     *  button, not the old "pause" endpoint. Unticks every line on the way, and
     *  reports how many, because a draft has no tick model to return them to.
     *  A finished list is refused server-side. */
    backToDraftAsync = async (id: string): Promise<BackToDraftResult> =>
        await this.httpClient.post<BackToDraftResult, Record<string, never>>(
            `/shopping-lists/${id}/back-to-draft`,
            {},
        );

    reorderLinesAsync = async (id: string, lineIdsInOrder: string[]): Promise<void> =>
        await this.httpClient.post<void, { line_ids: string[] }>(
            `/shopping-lists/${id}/lines/reorder`,
            { line_ids: lineIdsInOrder },
        );

    clearListAsync = async (id: string): Promise<ClearListResult> =>
        await this.httpClient.post<ClearListResult, Record<string, never>>(
            `/shopping-lists/${id}/clear`,
            {},
        );

    getFrequentlyAddedAsync = async (limit = 12): Promise<FrequentlyAddedItem[]> =>
        await this.httpClient.get<FrequentlyAddedItem[]>(
            `/shopping-lists/frequently-added?limit=${limit}`,
        );

    // receipt-photo record-keeping. The image is sent as a
    // `data:image/...;base64,...` string produced by `processImageFile`
    // (R-003 centralised pipeline) — DO NOT bypass that helper.
    addAttachmentAsync = async (
        listId: string,
        imageDataUrl: string,
    ): Promise<{ attachment_id: string }> =>
        await this.httpClient.post<
            { attachment_id: string },
            { image_data_url: string }
        >(`/shopping-lists/${listId}/attachments`, {
            image_data_url: imageDataUrl,
        });

    deleteAttachmentAsync = async (
        listId: string,
        attachmentId: string,
    ): Promise<void> =>
        await this.httpClient.delete<void>(
            `/shopping-lists/${listId}/attachments/${attachmentId}`,
        );
}
