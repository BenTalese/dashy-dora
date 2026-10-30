import { acceptHMRUpdate, defineStore } from 'pinia';
import { invalidateBuyVerdict } from 'src/composables/useBuyVerdict';
import { nameCollator } from 'src/composables/useMoney';
import { usePantryBeliefs } from 'src/composables/usePantryBeliefs';
import { usePlannedDemand } from 'src/composables/usePlannedDemand';
import { isLowStockSequence, isOutOfStockSequence, needsRestockSequence } from 'src/helpers/stockStatus';
import { Notify } from 'quasar';
import type { StockItem } from 'src/models/stockItem';
import type {
    CreateStockItemCommand,
    UpdateStockItemCommand,
    UpdateStockItemResponse
} from 'src/services/api/stockItemApiService';
import StockItemApiService from 'src/services/api/stockItemApiService';
import { useRecipeStore } from 'src/stores/recipeStore';
import { useShoppingListStore } from 'src/stores/shoppingListStore';
import { useStockLevelStore } from 'src/stores/stockLevelStore';
import type { Ref } from 'vue';
import { computed, readonly, ref } from 'vue';

const stockItemApiService = new StockItemApiService();

/** How long a burst of level writes settles before loaded overlays refetch. */
const OVERLAY_REFRESH_DELAY_MS = 300;

export const useStockItemStore = defineStore('stockItem', () => {
    const stockItems: Ref<StockItem[]> = ref([]);
    // Locale-aware collation from the locale authority (finalisation 20-R7).
    const collator = { compare: (a: string, b: string) => nameCollator().compare(a, b) };

    /** When a level-change PATCH transitions a stock item to Low/Out and
     *  the install-wide auto-add mode says fire (FU-511: `off` never,
     *  `essential_only` iff `is_essential`, `all` always), the server drops
     *  it onto the unambiguous draft list and returns
     *  `{ auto_added: { line_id, shopping_list_id } }`. Fire a positive
     *  toast naming the list + the item, and refresh the shopping-list
     *  store so the new line renders everywhere it's watched. Silent
     *  no-op for the 204 no-trigger case. */
    async function handleAutoAddedResponse(
        stockItemId: string,
        result: UpdateStockItemResponse,
    ): Promise<void> {
        if (
            !result || typeof result !== 'object'
            || !('auto_added' in result) || !result.auto_added
        ) {
            return;
        }
        const shoppingListStore = useShoppingListStore();
        await shoppingListStore.refreshAsync();
        const item = stockItems.value.find((si) => si.stock_item_id === stockItemId);
        const itemName = item?.name ?? 'that item';
        const listSummary = shoppingListStore.summaries.find(
            (s) => s.shopping_list_id === result.auto_added!.shopping_list_id,
        );
        const listName = listSummary?.display_name ?? 'your list';
        Notify.create({
            type: 'positive',
            message: `Added ${itemName} to ${listName}.`,
            caption: 'Auto-added because it went low.',
            timeout: 3000,
        });
    }

    /** Every recipe DTO carries pantry-derived facts — cookability, the
     *  missing/expiring counts, the Zero-Input hint, and in complex nutrition
     *  mode the rollup behind the kcal figure and the front-of-pack rating.
     *  A stock write can move any of them, so the recipe list is marked stale
     *  here rather than each recipe surface guessing which writes matter
     *  (R-003). Called from every mutation below, not just the nutrition
     *  link: a level change moves `cookable`, a delete moves `missing_count`.
     *
     *  This only sets a flag — the refetch happens on the next
     *  `ensureLoadedAsync`, so a stocktake run doesn't fire one request per
     *  item. Store lookup is inside the function (not module scope) because
     *  Pinia stores can only be resolved once the active pinia exists. */
    function invalidateDerivedRecipeFacts(): void {
        useRecipeStore().invalidateRecipes();
    }

    /** A level change moves three per-item overlays: the buy verdict (its
     *  need axis), the pantry belief ("override wins") and the planned-demand
     *  grade (Out outranks Low). They are marked stale here, on the one level
     *  write path (R-074), so every caller (the row, the detail page, the
     *  verdict card, the stocktake runner) leaves the same surfaces fresh.
     *  Overlays a surface has already loaded refetch once after a burst of
     *  writes settles, so a stocktake run doesn't fire a request per item. */
    let overlayRefresh: ReturnType<typeof setTimeout> | null = null;
    function invalidateLevelOverlays(stockItemId: string): void {
        invalidateBuyVerdict(stockItemId);
        const beliefs = usePantryBeliefs();
        const demand = usePlannedDemand();
        const reloadBeliefs = beliefs.loaded.value;
        const reloadDemand = demand.loaded.value;
        beliefs.invalidate();
        demand.invalidate();
        if (overlayRefresh) clearTimeout(overlayRefresh);
        overlayRefresh = setTimeout(() => {
            overlayRefresh = null;
            if (reloadBeliefs) void beliefs.loadAsync(true);
            if (reloadDemand) void demand.loadAsync(true);
        }, OVERLAY_REFRESH_DELAY_MS);
    }

    let hydrated = false;
    let inflight: Promise<void> | null = null;

    /** Item by id, for per-row lookups (a page renders one per row). */
    const byId = computed(() => new Map(stockItems.value.map((si) => [si.stock_item_id, si])));

    /** C-1 Stock Overview Chunk 1 — page until exhausted so a pantry of
     *  >50 items doesn't silently get truncated to the first page
     *  (FU-035). Callers that only need a quick prefix (autocomplete-
     *  style) should hit `getAllAsync` on the service directly. */
    const getStockItemsAsync = (): Promise<void> =>
        stockItemApiService.getAllPagesAsync().then((items) => {
            stockItems.value = [...items].sort((si1, si2) =>
                collator.compare(si1.name, si2.name)
            );
            hydrated = true;
        });

    /** R-016 — lazy hydration. Use this in `onMounted` / `beforeRouteEnter`
     *  when you need the collection populated but don't care about a forced
     *  refresh. Call `getStockItemsAsync` directly for an explicit refetch
     *  (post-mutation, pull-to-refresh). */
    const ensureLoadedAsync = (): Promise<void> => {
        if (hydrated) return Promise.resolve();
        inflight ??= getStockItemsAsync().finally(() => { inflight = null; });
        return inflight;
    };

    const createStockItemAsync = async (
        stockItemToCreate: CreateStockItemCommand,
    ): Promise<StockItem> => {
        const created = await stockItemApiService.createAsync(stockItemToCreate);
        // The API returns the full DTO body when available.
        const entity =
            'stock_item_id' in created
                ? (created as unknown as StockItem)
                : await stockItemApiService.getAsync(created.id as string);
        stockItems.value.push(entity);
        stockItems.value.sort((a, b) => collator.compare(a.name, b.name));
        invalidateDerivedRecipeFacts();
        return entity;
    };

    /** Optimistic stock-level swap, reverted in place if the API rejects.
     *  Offline is read-only (2026-08-23): a network failure rejects like any
     *  other, the previous level is restored, and the error is rethrown so the
     *  caller (or the global handler) tells the user. */
    async function updateStockLevelAsync(stockItemToUpdate: UpdateStockItemCommand) {
        const { stock_item_id } = stockItemToUpdate;
        const findIndex = () => stockItems.value.findIndex((si) => si.stock_item_id === stock_item_id);
        const cached = stockItems.value[findIndex()];
        if (!cached) {
            // Not hydrated here (the stocktake runner writes before `/stock`
            // has been visited): still the one write path — persist, keep the
            // recipe facts honest and surface the auto-add — just nothing to
            // move optimistically.
            const result = await stockItemApiService.updateAsync(stockItemToUpdate);
            invalidateDerivedRecipeFacts();
            invalidateLevelOverlays(stock_item_id);
            await handleAutoAddedResponse(stock_item_id, result);
            return;
        }

        const original = {
            stock_level_id: cached.stock_level_id,
            stock_level_sequence: cached.stock_level_sequence,
            is_out_of_stock: cached.is_out_of_stock,
            is_low_stock: cached.is_low_stock,
            needs_restock: cached.needs_restock,
        };
        const nextLevelId = stockItemToUpdate.stock_level_id!;
        cached.stock_level_id = nextLevelId;
        // Rows read the derived status fields first, so move them with the id
        // or the swatch shows the old level until the refetch lands.
        const nextLevel = useStockLevelStore().levelById.get(nextLevelId);
        if (nextLevel) {
            cached.stock_level_sequence = nextLevel.sequence;
            cached.is_out_of_stock = isOutOfStockSequence(nextLevel);
            cached.is_low_stock = isLowStockSequence(nextLevel);
            cached.needs_restock = needsRestockSequence(nextLevel);
        }

        let result: UpdateStockItemResponse;
        try {
            result = await stockItemApiService.updateAsync(stockItemToUpdate);
        } catch (err) {
            // Revert here rather than via the global rollback registry: most
            // callers catch the rejection themselves, so a registry-only undo
            // would never run. Re-look-up by id — the array may have changed
            // during the await.
            const current = stockItems.value[findIndex()];
            if (current) Object.assign(current, original);
            throw err;
        }
        // Refetch the canonical row so any server-derived fields
        // (timestamps, normalised values, the attention flag) are picked up.
        const refreshed = await stockItemApiService.getAsync(stock_item_id);
        const index = findIndex();
        if (index >= 0) stockItems.value[index] = refreshed;
        invalidateDerivedRecipeFacts();
        invalidateLevelOverlays(stock_item_id);
        // level transition may have triggered the auto-add hook.
        await handleAutoAddedResponse(stock_item_id, result);
    }

    /** General-purpose update for the detail page (name/notes/location/etc).
     *  Rejects on a network failure like any other error — callers own the
     *  toast and any UI they optimistically moved. */
    const updateStockItemAsync = async (cmd: UpdateStockItemCommand) => {
        const { stock_item_id } = cmd;
        const result = await stockItemApiService.updateAsync(cmd);
        const refreshed = await stockItemApiService.getAsync(stock_item_id);
        const idx = stockItems.value.findIndex((si) => si.stock_item_id === stock_item_id);
        if (idx >= 0) {
            stockItems.value[idx] = refreshed;
            stockItems.value.sort((a, b) => collator.compare(a.name, b.name));
        }
        invalidateDerivedRecipeFacts();
        // `saveField`-style level changes on the detail page also
        // go through this path (they carry `stock_level_id`), so the
        // auto-add hook can fire here too.
        await handleAutoAddedResponse(stock_item_id, result);
    };

    /** Push the expiry "+N days" (server rule) and refresh the row. Returns
     *  the new ISO expiry date. */
    const pushExpiryAsync = async (stockItemId: string, days: number): Promise<string> => {
        const { expiry_date } = await stockItemApiService.pushExpiryAsync(stockItemId, days);
        const refreshed = await stockItemApiService.getAsync(stockItemId);
        const idx = stockItems.value.findIndex((si) => si.stock_item_id === stockItemId);
        if (idx >= 0) stockItems.value[idx] = refreshed;
        invalidateDerivedRecipeFacts();
        return expiry_date;
    };

    const deleteStockItemAsync = async (stockItemID: string) => {
        await stockItemApiService.deleteAsync(stockItemID);
        stockItems.value = stockItems.value.filter((si) => si.stock_item_id !== stockItemID);
        invalidateDerivedRecipeFacts();
    };

    return {
        byId,
        stockItems: readonly(stockItems),
        getStockItemsAsync,
        ensureLoadedAsync,
        createStockItemAsync,
        updateStockLevelAsync,
        invalidateLevelOverlays,
        updateStockItemAsync,
        pushExpiryAsync,
        deleteStockItemAsync,
    };
});

if (import.meta.hot) {
    import.meta.hot.accept(acceptHMRUpdate(useStockItemStore, import.meta.hot));
}
