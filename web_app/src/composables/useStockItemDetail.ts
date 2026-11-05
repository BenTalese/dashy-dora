/**
 * The stock-item page's shared state (FU-934 / finalisation 06-R32).
 *
 * `StockItemDetailPage.vue` was one ~2,800-line file. It is now a page (header,
 * tab strip, the Recipes and Lists panels, delete) plus five tab blocks —
 * `StockItemOverviewTab`, `StockItemProductsTab`, `StockItemSubstitutesTab`,
 * `StockItemScanningTab`, `StockItemHistoryTab` — and the state those blocks
 * *share* lives here rather than being prop-drilled: the loaded detail, the
 * busy flag and the save / reload pair every mutation runs through, the
 * name / notes draft and its unsaved-changes guard, the open tab, the QR label
 * and the product sparklines (both fetched by the page, read by a tab), and
 * the store-sync watcher that keeps a peek in step with row edits.
 *
 * The page calls `provideStockItemDetail()` once in its setup; each tab calls
 * `useStockItemDetail()` (R-011: composables + provide/inject, not a global
 * store — this is one page's view state, and the Stock Overview peek mounts a
 * second page instance that wants its own). What only one tab reads stays in
 * that tab. Same shape as `useRecipeDetail` / `useShoppingListDetail`.
 *
 * The page's id is NOT stable for its lifetime: the peek swaps `idOverride` on
 * a mounted instance, so everything here keys off the `stockItemId` computed
 * and drops the previous item's state on a swap.
 *
 * No business logic of its own: every derived fact (verdict, belief, prices,
 * per-unit cost, history caps) is the server's (R-003), read rather than
 * recomputed.
 */
import { computed, inject, onMounted, onScopeDispose, provide, reactive, ref, watch, type InjectionKey } from 'vue';
import { useQuasar } from 'quasar';
import { useRoute } from 'vue-router';

import { useBuyVerdict } from 'src/composables/useBuyVerdict';
import { useFeatureFlags } from 'src/composables/useFeatureFlags';
import { usePantryBeliefs } from 'src/composables/usePantryBeliefs';
import { usePlannedDemand } from 'src/composables/usePlannedDemand';
import { describeQrFailure, fetchQrImageUrlAsync, openQrSheetAsync } from 'src/composables/useQrLabels';
import { useScanningEnabled } from 'src/composables/useScanningEnabled';
import { useUnsavedChangesGuard } from 'src/composables/useUnsavedChangesGuard';
import type { LinkedProduct, StockItemDetail } from 'src/models/stockItemDetail';
import PriceHistoryApiService from 'src/services/api/priceHistoryApiService';
import StockItemApiService from 'src/services/api/stockItemApiService';
import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
import { useLocationStore } from 'src/stores/locationStore';
import { useRecipeStore } from 'src/stores/recipeStore';
import { useShoppingListStore } from 'src/stores/shoppingListStore';
import { useStockGroupStore } from 'src/stores/stockGroupStore';
import { useStockItemStore } from 'src/stores/stockItemStore';
import { useStockLevelStore } from 'src/stores/stockLevelStore';
import { useStoresStore } from 'src/stores/storesStore';

/** The partial PATCH the inline-edit rows send — one field per row. */
export type StockItemFieldPatch = {
    name?: string;
    notes?: string | null;
    stock_location_id?: string | null;
    stock_group_id?: string | null;
    is_essential?: boolean;
    stocktake_alerts_are_enabled?: boolean;
    expiry_date?: string | null;
    usual_store_id?: string | null;
    clear_usual_store?: boolean;
    // Explicit clear flags — see `update_stock_item.py` for why the
    // relationship-only null assignment doesn't dirty the FK column.
    clear_stock_location?: boolean;
    clear_stock_group?: boolean;
    // Nutrition complex-mode link, same clear-vs-unset shape as the store.
    nutrition_food_id?: string;
    clear_nutrition_food?: boolean;
    // "Never suggest a food for this one." A plain bool, not a clear flag —
    // unlike the FK there's no difference between false and absent.
    nutrition_ignored?: boolean;
};

/** Every tab the page knows; `?section=` deep links pick one of these. */
export const STOCK_ITEM_TAB_NAMES = ['overview', 'products', 'recipes', 'substitutes', 'scanning', 'lists', 'history'];

function createStockItemDetail(idSource: () => string) {
    const route = useRoute();
    const $q = useQuasar();

    const stockItemApi = new StockItemApiService();
    const stockItemStore = useStockItemStore();
    const stockLevelStore = useStockLevelStore();
    const stockGroupStore = useStockGroupStore();
    const storesStore = useStoresStore();
    const locationStore = useLocationStore();
    const recipeStore = useRecipeStore();
    const shoppingListStore = useShoppingListStore();
    // Shared caches; loaded on mount, read by the overview tab.
    const pantryBeliefs = usePantryBeliefs();
    const plannedDemandCache = usePlannedDemand();

    const stockItemId = computed(idSource);

    // buy-verdict oracle (row/line badges elsewhere; the full card renders on
    // the overview tab, per FU-437). Fetched on mount, cached for 5 min.
    // 2026-08-21 feedback ("the verdicts don't update when switching between
    // items in desktop view"): this used to pass `stockItemId.value` — a
    // snapshot taken at setup. The peek swaps `idOverride` on a mounted
    // instance, so the card kept rendering the first item's verdict. Pass the
    // ref itself and the composable's own watcher re-fetches per id. Lives
    // here rather than in the overview tab so it still fetches on page load,
    // whichever tab is open, and the Lists tab's add can invalidate it.
    const { verdict: buyVerdict, invalidate: buyVerdictInvalidate } =
        useBuyVerdict(stockItemId);

    const detail = ref<StockItemDetail | null>(null);
    const loading = ref(false);
    const loadError = ref<string | null>(null);
    const busy = ref(false);

    // ── Install-wide gates the tab strip and its guards read ─────────────
    // when `products` is off the Products tab + per-product surfaces
    // disappear entirely; FU-182 owns the app-wide sweep, this page just
    // consumes the flag.
    const { scanningEnabled } = useScanningEnabled();
    const { products: productsEnabled } = useFeatureFlags();

    // ── QR label (gated by the install-wide scanning flag) ───────────────
    // The QR PNG and the print sheet are fetched through the authenticated
    // http client and handed to the browser as blobs (see useQrLabels). The
    // previous `<img :src="apiUrl">` / `window.open(apiUrl)` pair relied on
    // the browser volunteering the session cookie on an unauthenticated
    // request, which is why the code rendered empty and "Print one" died.
    // Held here, not in the Scanning tab, so the fetched code survives a tab
    // switch (the tab panel unmounts) and the id-swap watcher can drop it.
    const qrSrc = ref<string | null>(null);
    const qrLoading = ref(false);
    const qrError = ref<string | null>(null);
    // The label is a blob object URL: release the old one whenever it's
    // replaced or dropped, and when the page goes (FU-952).
    function setQrSrc(next: string | null) {
        if (qrSrc.value) URL.revokeObjectURL(qrSrc.value);
        qrSrc.value = next;
    }
    onScopeDispose(() => setQrSrc(null));

    // Feedback 2026-08-24: the code renders inside the Scanning tab rather than
    // behind a header button + modal, so the fetch is keyed to that tab opening.
    // Still lazy — most visits to this page never open Scanning, and this is a
    // network round-trip per item.
    // Bumped on every fetch and on an id swap (peek panel), so a response for
    // the previous item can't land under the new one.
    let qrRequest = 0;
    async function ensureQrLoadedAsync() {
        if (qrSrc.value || qrLoading.value) return;
        const token = ++qrRequest;
        qrLoading.value = true;
        qrError.value = null;
        try {
            // size 512 looks crisp on retina; the box clamps to 256.
            const src = await fetchQrImageUrlAsync(stockItemId.value, 512);
            if (token === qrRequest) setQrSrc(src);
            else URL.revokeObjectURL(src);
        } catch (error) {
            // The reason, not just the fact. This used to be a bare sentence
            // with the error discarded, which is why the reported failure
            // (FU-648) survived two investigations unexplained — there was
            // nothing for the one person who could see it to report back.
            if (token === qrRequest) qrError.value = describeQrFailure(error);
        } finally {
            if (token === qrRequest) qrLoading.value = false;
        }
    }

    // "Print" opens a tab, so it must stay synchronous into
    // `openQrSheetAsync` — see the pop-up note there. Failures used to be
    // dropped on the floor by a bare `void`; they now land in the tab's own
    // error slot, next to the button that caused them.
    async function openSingleQrSheet() {
        qrError.value = null;
        try {
            await openQrSheetAsync({ ids: [stockItemId.value] });
        } catch (error) {
            qrError.value = describeQrFailure(error);
        }
    }

    // ── Tabs ─────────────────────────────────────────────────────────────
    const tab = ref<string>(
        typeof route.query.section === 'string' ? route.query.section : 'overview',
    );
    // Dora's "Find substitutes" pushes `?section=substitutes` onto this same
    // page, which reuses the component — follow the query after mount too.
    watch(
        () => route.query.section,
        (section) => {
            if (typeof section === 'string' && STOCK_ITEM_TAB_NAMES.includes(section)) tab.value = section;
        },
    );
    // if the URL pointed at ?section=products but products
    // is off (or the admin flips it off later), fall back to Overview so
    // we don't strand the user on an invisible tab.
    watch(
        [productsEnabled, tab],
        ([enabled, current]) => {
            if (!enabled && current === 'products') tab.value = 'overview';
        },
        { immediate: true },
    );
    // Same guard for the Scanning tab, which is gated on the scanning flag.
    watch(
        [scanningEnabled, tab],
        ([enabled, current]) => {
            if (!enabled && current === 'scanning') tab.value = 'overview';
        },
        { immediate: true },
    );
    // Opening Scanning is what fetches the QR label — see `ensureQrLoadedAsync`.
    watch(tab, (current) => {
        if (current === 'scanning') void ensureQrLoadedAsync();
    }, { immediate: true });

    // ── Inline-edit state (C-1b.1) ──────────────────────────────────────
    // Text rows (name/notes) live in `form` and save on blur if changed;
    // toggles/selects/dates save immediately on change (see the overview
    // tab's handlers). Each row IS its editor. The form lives here, not in
    // the overview tab, because every reload re-hydrates it.
    type BasicsForm = {
        name: string;
        notes: string;
        stock_location_id: string | null;
        stock_group_id: string | null;
        usual_store_id: string | null;
    };
    const emptyBasics = (): BasicsForm => ({
        name: '', notes: '', stock_location_id: null, stock_group_id: null,
        usual_store_id: null,
    });
    const form = reactive<BasicsForm>(emptyBasics());

    /** `keepDrafts` holds an unsaved name / notes edit across a reload of the
     *  same item (a toggle saved elsewhere on the page reloads the detail). */
    function hydrateForm(d: StockItemDetail, keepDrafts = false) {
        if (!keepDrafts) {
            form.name = d.name;
            form.notes = d.notes ?? '';
        }
        form.stock_location_id = d.stock_location_id;
        form.stock_group_id = d.stock_group_id;
        form.usual_store_id = d.usual_store_id;
    }
    // The unsaved-changes guard now only covers text rows — selects/toggles/
    // dates persist on change, so they can never be "dirty but not saved."
    const isDirty = computed(() => {
        if (!detail.value) return false;
        return (
            form.name.trim() !== detail.value.name ||
            (form.notes ?? '') !== (detail.value.notes ?? '')
        );
    });
    // R-020 — deferred-save surface, must wire the unsaved-changes guard.
    // `confirmLeave` covers the peek swapping items, which is no route change.
    const { confirmLeave } = useUnsavedChangesGuard(isDirty);

    // Overview view state that outlives the overview tab panel, which
    // unmounts on a tab switch: the nutrition disclosure (feedback 2026-08-16
    // — the full per-100g table is behind it so it can't bury the sections
    // under it), a half-typed preferred buy and an in-progress rename of one
    // (FU-981 (13)). Page-level before the split, so kept page-level.
    const nutritionExpanded = ref(false);
    const newBuyLabel = ref('');
    const editingBuyId = ref<string | null>(null);
    const editingBuyLabel = ref('');

    // ── Linked products' sparklines ──────────────────────────────────────
    // Fetched by every detail load (so they're ready whichever tab is open)
    // and read by the Products tab.
    const priceHistory = ref<Map<string, number[]>>(new Map());
    const priceSeriesApi = new PriceHistoryApiService();
    const PRICE_SERIES_BATCH = 5;

    /** Sparkline series for the linked products, from the batched
     *  `/price-history` read (it takes up to five products a call). */
    async function loadPriceHistories(products: LinkedProduct[]) {
        const ids = products.map((p) => p.product_id);
        const batches: string[][] = [];
        for (let i = 0; i < ids.length; i += PRICE_SERIES_BATCH) batches.push(ids.slice(i, i + PRICE_SERIES_BATCH));
        const map = new Map<string, number[]>();
        await Promise.all(batches.map(async (batch) => {
            try {
                const { series } = await priceSeriesApi.seriesAsync(batch, '90d');
                for (const s of series) {
                    map.set(s.product_id, s.points.map((pt) => pt.unit_price ?? 0).filter((n) => n > 0));
                }
            } catch {
                // Sparklines just render empty if history can't be loaded.
            }
        }));
        priceHistory.value = map;
    }

    // ── Load / save ──────────────────────────────────────────────────────
    function notifyErr(message: string, err: unknown) {
        $q.notify({ type: 'negative', message, caption: toastCaption(err) });
    }

    async function loadDetail() {
        const id = stockItemId.value;
        loading.value = true;
        loadError.value = null;
        try {
            const d = await stockItemApi.getDetailAsync(id);
            // The peek panel can swap ids mid-flight — drop a stale response.
            if (id !== stockItemId.value) return;
            const keepDrafts = detail.value?.stock_item_id === d.stock_item_id && isDirty.value;
            detail.value = d;
            hydrateForm(d, keepDrafts);
            void loadPriceHistories(d.products);
            // List membership (the "on lists" tab) comes from the shopping-list
            // store, loaded on mount and refreshed by the list actions themselves.
        } catch (err) {
            if (id !== stockItemId.value) return;
            loadError.value = 'Could not load this stock item.';
            console.warn('stock-item detail load failed', err);
        } finally {
            if (id === stockItemId.value) loading.value = false;
        }
    }

    // Each inline-edit row's editor calls this; the partial PATCH already
    // supports per-field updates so there's no Save button. Reloads detail to
    // pick up any server-derived state changes (e.g. auto-add hook firing
    // when level transitions).
    async function saveField(patch: StockItemFieldPatch) {
        if (!detail.value) return;
        busy.value = true;
        try {
            await stockItemStore.updateStockItemAsync({
                stock_item_id: detail.value.stock_item_id,
                ...patch,
            });
            await loadDetail();
        } catch (err) {
            notifyErr('Save failed.', err);
        } finally {
            busy.value = false;
        }
    }

    /** Runs a mutation with the page busy, then re-reads the detail. A throw
     *  propagates to the caller (after `busy` clears) and skips the reload. */
    async function withBusyReload(fn: () => Promise<void>) {
        busy.value = true;
        try {
            await fn();
            await loadDetail();
        } finally {
            busy.value = false;
        }
    }

    watch(stockItemId, (id) => {
        // Leaving the page empties the id; keep the old detail up through the
        // layout cross-fade rather than blanking it (R-037).
        if (!id) return;
        // The peek panel swaps ids in place — drop the previous item's detail
        // (so a failed load can't leave it on screen for saveField to patch)
        // and its cached QR, invalidating any in-flight QR fetch, then re-fetch
        // the label if it's the tab we're currently looking at.
        detail.value = null;
        qrRequest++;
        qrLoading.value = false;
        setQrSrc(null);
        qrError.value = null;
        if (tab.value === 'scanning') void ensureQrLoadedAsync();
        if (stockItemId.value) void loadDetail();
    });

    // when the row's expiry / open / flag / level toggles fire
    // while this page is open as a peek, the store's StockItem updates
    // but `detail.value` (loaded as a one-shot) goes stale. Sync the
    // handful of fields the row can mutate from the store version onto
    // detail.value so the peek reflects external edits without a
    // refresh. The store always re-fetches the canonical row after a
    // mutation (stockItemStore.updateStockItemAsync /
    // updateStockLevelAsync), so the assignments here are authoritative.
    // Self-triggered edits on the detail page also flow through the
    // store, but the value already matches by the time the watcher
    // fires — the assignment is a no-op, not a loop.
    const storeItem = computed(() => stockItemStore.byId.get(stockItemId.value) ?? null);
    watch(storeItem, (si) => {
        if (!si || !detail.value || detail.value.stock_item_id !== si.stock_item_id) return;
        if (si.expiry_date !== undefined && si.expiry_date !== detail.value.expiry_date) {
            detail.value.expiry_date = si.expiry_date;
        }
        if (si.is_open !== undefined && si.is_open !== detail.value.is_open) {
            detail.value.is_open = si.is_open;
        }
        if (si.opened_on !== undefined && si.opened_on !== detail.value.opened_on) {
            detail.value.opened_on = si.opened_on;
        }
        if (si.is_essential !== undefined && si.is_essential !== detail.value.is_essential) {
            detail.value.is_essential = si.is_essential;
        }
        if (si.stock_level_id && si.stock_level_id !== detail.value.stock_level_id) {
            detail.value.stock_level_id = si.stock_level_id;
            detail.value.stock_level_name = stockLevelStore.levelById.get(si.stock_level_id)?.name ?? null;
        }
    });

    onMounted(async () => {
        // Stock groups are page-local (only consumer); load alongside the
        // other dropdowns so the inline picker has options on first paint.
        void stockGroupStore.ensureLoadedAsync();
        // populate the usual-store picker. R-016 ensureLoaded.
        void storesStore.ensureLoadedAsync();
        await Promise.all([
            stockLevelStore.ensureLoadedAsync(),
            locationStore.ensureLoadedAsync(),
            stockItemStore.ensureLoadedAsync(),
            recipeStore.ensureLoadedAsync(),
            shoppingListStore.ensureLoadedAsync(),
            // load inferred beliefs (shared cache; idempotent when
            // the overview already loaded them).
            pantryBeliefs.loadAsync(),
            plannedDemandCache.loadAsync(),
        ]);
        await loadDetail();
    });

    return {
        stockItemApi,
        stockItemId,
        detail,
        loading,
        loadError,
        busy,
        buyVerdict,
        buyVerdictInvalidate,
        scanningEnabled,
        productsEnabled,
        tab,
        qrSrc,
        qrLoading,
        qrError,
        openSingleQrSheet,
        form,
        isDirty,
        confirmLeave,
        nutritionExpanded,
        newBuyLabel,
        editingBuyId,
        editingBuyLabel,
        priceHistory,
        notifyErr,
        loadDetail,
        saveField,
        withBusyReload,
    };
}

export type StockItemDetailContext = ReturnType<typeof createStockItemDetail>;

const STOCK_ITEM_DETAIL_KEY: InjectionKey<StockItemDetailContext> = Symbol('stockItemDetail');

/** Called once, in `StockItemDetailPage`'s setup, with the page's id
 *  (`idOverride` when it's the overview's peek, else the route param). */
export function provideStockItemDetail(idSource: () => string): StockItemDetailContext {
    const ctx = createStockItemDetail(idSource);
    provide(STOCK_ITEM_DETAIL_KEY, ctx);
    return ctx;
}

/** Called by the stock-item page's tabs. Throws outside the page: a tab
 *  mounted without its page has no item to show, and a silent `undefined`
 *  would surface as a template error somewhere less obvious. */
export function useStockItemDetail(): StockItemDetailContext {
    const ctx = inject(STOCK_ITEM_DETAIL_KEY, null);
    if (!ctx) throw new Error('useStockItemDetail() must be used inside StockItemDetailPage (provideStockItemDetail).');
    return ctx;
}
