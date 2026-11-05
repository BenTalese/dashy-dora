/**
 * The stock overview's scan flow (N5 + FU-378 action-first mode), lifted out
 * of `StockOverview.vue` (FU-934 / finalisation 05-R33).
 *
 * `scanAction` is a *persistent* selection shown + switched inside the
 * overlay: the user always sees what a scan does and can change it without
 * leaving the camera. `open` is the legacy N5 jump-to-detail flow (closes on
 * decode); a `level` action stays open and sets that level on every scanned
 * item (covers the stocktake scan-to-check case — decision §7a #4). Opening
 * the Scan button resets to the `open` default (navigate-on-scan unless you
 * pick an action).
 *
 * The page keeps the overlay and its action menu in its template (bound with
 * `ref="scanOverlayRef"`) and owns the create dialog an unknown code opens —
 * it hands this composable `openCreateDialog` for that.
 */
import { computed, ref, useTemplateRef } from 'vue';
import { useQuasar } from 'quasar';
import { useRouter } from 'vue-router';

import type ScanOverlay from 'src/components/ScanOverlay.vue';
import type { CreateStockItemPrefill } from 'src/components/stock/createStockItemPrefill';
import {
    buildScanActionOptions,
    resolveScanLevelOutcome,
    type ScanAction,
} from 'src/helpers/scanActions';
import type { StockItem } from 'src/models/stockItem';
import type { StockLevel } from 'src/models/stockLevel';
import BarcodeApiService from 'src/services/api/barcodeApiService';
import { useStockItemStore } from 'src/stores/stockItemStore';
import { useStockLevelStore } from 'src/stores/stockLevelStore';
import { ICONS } from 'src/style/icons';
import { isAlreadyNotified } from 'src/services/errorHandling/apiErrorHandler';

export interface StockScanDeps {
    stockItems: () => readonly StockItem[];
    stockLevels: () => readonly StockLevel[];
    /** Opens the page's add-item dialog seeded from the scanned code. */
    openCreateDialog: (prefill: CreateStockItemPrefill) => void;
}

export function useStockScan(deps: StockScanDeps) {
    const $q = useQuasar();
    const router = useRouter();
    const stockItemStore = useStockItemStore();
    const stockLevelStore = useStockLevelStore();
    const barcodeApi = new BarcodeApiService();

    const overviewScanOpen = ref(false);
    // The page's `<ScanOverlay ref="scanOverlayRef">` — the level loop
    // reports each scan's outcome through its `pushResult`.
    const scanOverlayRef = useTemplateRef<InstanceType<typeof ScanOverlay>>('scanOverlayRef');
    const scanAction = ref<ScanAction>({ kind: 'open' });

    // The full action menu, rebuilt from the live level rows so a renamed
    // seed level shows its custom name (R-003 — no hardcoded level literals).
    const scanActionOptions = computed(() => buildScanActionOptions(deps.stockLevels()));

    // Current-action display: label, the optional level colour-dot sequence,
    // the leading icon, and a one-line caption of what each scan will do.
    const currentScanActionLabel = computed(() =>
        scanAction.value.kind === 'open'
            ? 'Open stock item'
            : `Set to ${scanAction.value.levelName}`,
    );
    const currentScanActionSequence = computed<number | null>(() => {
        if (scanAction.value.kind !== 'level') return null;
        const id = scanAction.value.levelId;
        return stockLevelStore.levelById.get(id ?? '')?.sequence ?? null;
    });
    const currentScanActionIcon = computed(() =>
        scanAction.value.kind === 'open' ? ICONS.open_in_new : undefined,
    );
    const scanActionCaption = computed(() =>
        scanAction.value.kind === 'open'
            ? 'Scan an item to open it.'
            : 'Each item you scan is set to this level.',
    );

    function isCurrentScanAction(action: ScanAction): boolean {
        const cur = scanAction.value;
        if (action.kind === 'open') return cur.kind === 'open';
        return cur.kind === 'level' && cur.levelId === action.levelId;
    }

    function selectScanAction(action: ScanAction) {
        scanAction.value = action;
    }

    function openScan() {
        // Reset to the navigate-on-scan default each time the button is
        // pressed; switching to a level action happens inside the overlay.
        scanAction.value = { kind: 'open' };
        overviewScanOpen.value = true;
    }

    // Look up a stock item's display name for the scan result banner.
    function stockItemName(id: string): string | undefined {
        return deps.stockItems().find((si) => si.stock_item_id === id)?.name;
    }

    // Apply the chosen level to a scanned item. Reuses the shared
    // updateStockLevelAsync mutation (R-003) so it behaves exactly like the
    // in-row level swap (optimistic + offline-queue + auto-add hook). Any
    // result other than a resolvable stock item is reported and skipped —
    // we don't derail the scan loop into the add-item flow.
    async function onScanLevelDecoded(value: string, action: Extract<ScanAction, { kind: 'level' }>) {
        const overlay = scanOverlayRef.value;
        try {
            const result = await barcodeApi.lookupAsync(value);
            const outcome = resolveScanLevelOutcome(result, action.levelName, stockItemName);
            if (!outcome.ok || !outcome.stockItemId) {
                overlay?.pushResult(outcome.message, 'bad');
                return;
            }
            await stockItemStore.updateStockLevelAsync({
                stock_item_id: outcome.stockItemId,
                stock_level_id: action.levelId,
            });
            overlay?.pushResult(outcome.message, 'good');
        } catch {
            overlay?.pushResult('Lookup failed. Try again.', 'bad');
        }
    }

    async function onOverviewScanDecoded(value: string) {
        // Route level actions to the loop-apply handler; everything else is
        // the legacy open/navigate flow below.
        if (scanAction.value.kind === 'level') {
            await onScanLevelDecoded(value, scanAction.value);
            return;
        }
        try {
            const result = await barcodeApi.lookupAsync(value);
            // both stock-item kinds route directly. `UNIQUE` on
            // StockItemProduct.product_id guarantees there's no multi-link
            // ambiguity to handle. **P8-02 invariant: already-mapped EANs
            // never trigger the OFF lookup or the add flow** — they jump
            // straight to the existing item so no duplicate is created.
            if (result.kind === 'stock_item' || result.kind === 'stock_item_via_product') {
                overviewScanOpen.value = false;
                void router.push(`/stock/${result.id}`);
                return;
            }
            // `product_no_link` — the Product exists (probably from ingestion)
            // but no stock item is linked. Skip OFF (the user's own Product
            // data wins over an open-data suggestion) and open the add-item
            // dialog with a barcode-only prefill; the dialog registers the
            // EAN against the new stock item on save. Deeper "link into an
            // existing item" flow is deferred (see FU-056 Phase-2 Products
            // UI).
            if (result.kind === 'product_no_link') {
                overviewScanOpen.value = false;
                deps.openCreateDialog({
                    barcode: value,
                    source: 'product_no_link',
                });
                return;
            }
            // `unknown` — the EAN is genuinely not in Dora. Ask Open Food
            // Facts. On a hit, seed the dialog with the OFF suggestion; on
            // a miss (or network failure — OFF returns `found: false` for
            // both), open the dialog with only the barcode so the user can
            // still one-tap add + register the EAN. The barcode registers
            // against the new stock item on submit either way.
            overviewScanOpen.value = false;
            let prefill: CreateStockItemPrefill = { barcode: value, source: 'unknown' };
            try {
                const off = await barcodeApi.offLookupAsync(value);
                if (off.found) {
                    prefill = {
                        barcode: value,
                        source: 'off',
                        name: off.name ?? undefined,
                        brand: off.brand ?? undefined,
                        imageUrl: off.image_url ?? undefined,
                        categories: off.categories ?? undefined,
                        quantity: off.quantity ?? undefined,
                    };
                }
            } catch {
                // OFF endpoint itself failed (server-side, distinct from a
                // "found: false" miss). Fall through to the barcode-only
                // prefill so the user isn't blocked — the add still works,
                // and the EAN still gets registered on submit.
            }
            deps.openCreateDialog(prefill);
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Lookup failed.',
                    caption: err instanceof Error ? err.message : String(err),
                });
            }
        }
    }

    return {
        overviewScanOpen,
        scanAction,
        scanActionOptions,
        currentScanActionLabel,
        currentScanActionSequence,
        currentScanActionIcon,
        scanActionCaption,
        isCurrentScanAction,
        selectScanAction,
        openScan,
        onOverviewScanDecoded,
    };
}
