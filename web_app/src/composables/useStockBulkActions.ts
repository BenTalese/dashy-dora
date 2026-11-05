/**
 * The stock overview's bulk-select mode, lifted out of `StockOverview.vue`
 * (FU-934 / finalisation 05-R33): the selection, the seven actions on the bulk
 * bar (add to the quick-add list, add to a chosen list, remove from a list,
 * move location, restock, log waste, print QRs) and `pickActiveListId`, the
 * list picker two of them share.
 *
 * The page keeps the bar and the two dialogs in its template and reads
 * everything from here. Every action writes through a bulk endpoint, so each
 * one refreshes the store it bypassed (and invalidates the verdict / level
 * overlays) itself — FU-572.
 */
import { computed, ref } from 'vue';
import { useQuasar } from 'quasar';

// FU-572: the bulk paths write list membership and levels straight to the
// server, so they invalidate the verdict cache themselves — the per-item
// helpers that used to do it for them are no longer in the loop.
import { invalidateBuyVerdict } from 'src/composables/useBuyVerdict';
import { useConfirm } from 'src/composables/useConfirm';
import { useStockItemActions } from 'src/composables/useStockItemActions';
import type { StockItem } from 'src/models/stockItem';
import ShoppingListApiService from 'src/services/api/shoppingListApiService';
import StockItemApiService from 'src/services/api/stockItemApiService';
import WasteApiService, { type WasteReason } from 'src/services/api/wasteApiService';
import { isAlreadyNotified, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
import { useRecipeStore } from 'src/stores/recipeStore';
import { useShoppingListStore } from 'src/stores/shoppingListStore';
import { useStockItemStore } from 'src/stores/stockItemStore';
import { useStockLevelStore } from 'src/stores/stockLevelStore';

export interface StockBulkActionsDeps {
    /** The rows currently on screen — "Select visible" ticks these. */
    visibleItems: () => readonly StockItem[];
    /** Opens the QR label sheet for the given ids (the page's export helper). */
    openQrSheet: (ids: string[]) => void;
}

export function useStockBulkActions(deps: StockBulkActionsDeps) {
    const $q = useQuasar();
    const { choose } = useConfirm();
    const actions = useStockItemActions();
    const stockItemStore = useStockItemStore();
    const stockLevelStore = useStockLevelStore();
    const shoppingListStore = useShoppingListStore();
    const recipeStore = useRecipeStore();
    const stockItemApi = new StockItemApiService();
    const shoppingListApi = new ShoppingListApiService();
    const wasteApi = new WasteApiService();

    // ── Selection ────────────────────────────────────────────────────────
    const bulkMode = ref(false);
    const bulkSelection = ref<Set<string>>(new Set());
    const bulkBusy = ref(false);

    function toggleBulk(id: string) {
        const wasSelected = bulkSelection.value.has(id);
        if (wasSelected) bulkSelection.value.delete(id);
        else bulkSelection.value.add(id);
        bulkSelection.value = new Set(bulkSelection.value);
        // 2026-08-15 feedback: unticking the last item leaves bulk mode
        // running with an empty selection and every action disabled —
        // a dead-end bar the user then has to dismiss by hand. Treat
        // "deselected the last one" as backing out of the mode — and
        // 2026-08-20 feedback extended that to `deselectAll` below, which
        // reaches the same empty selection by a different route and so
        // shouldn't leave the user in a different state.
        if (wasSelected && bulkSelection.value.size === 0) bulkMode.value = false;
    }
    function selectVisible() {
        for (const item of deps.visibleItems()) {
            bulkSelection.value.add(item.stock_item_id);
        }
        bulkSelection.value = new Set(bulkSelection.value);
    }
    function cancelBulk() {
        bulkMode.value = false;
        bulkSelection.value = new Set();
    }
    function deselectAll() {
        // 2026-08-20 feedback: "for mobile we made it so deselecting the last
        // item would stop bulk select. I would expect the same for using the
        // deselect all button." Same end state either way — an empty selection
        // with the bar still up is a dead end whichever button emptied it.
        // (That makes this equivalent to Cancel; it stays because on a phone
        // the bulk bar is what's on screen, not the toolbar's Cancel.)
        cancelBulk();
    }

    // ── Add to the quick-add list (the `a` shortcut) ─────────────────────
    async function bulkAddToPrimary() {
        if (bulkSelection.value.size === 0) return;
        bulkBusy.value = true;
        try {
            const ids = [...bulkSelection.value];
            // The first item goes through `addToList` because resolving the
            // quick-add target is the interactive bit — it may find no draft,
            // or prompt when several exist. It returns the list it landed on,
            // which is exactly what the rest of the batch needs (that return
            // value is documented for this caller). Silent so the per-item
            // toast doesn't precede the summary.
            const listId = await actions.addToList(ids[0]!, null, { silent: true });
            if (!listId) return; // no draft, or the user cancelled the picker.

            const rest = ids.slice(1);
            let added = 1;
            let already = 0;
            if (rest.length > 0) {
                const result = await shoppingListApi.bulkAddLinesAsync(listId, rest);
                added += result.added;
                already += result.already_on_list;
            }
            await shoppingListStore.refreshAsync();
            ids.forEach((id) => invalidateBuyVerdict(id));
            $q.notify({
                type: 'positive',
                message: already > 0
                    ? `Added ${added} to your list, ${already} already on it.`
                    : `Added ${added} item${added === 1 ? '' : 's'} to your list.`,
            });
            cancelBulk();
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not add all items.',
                    caption: toastCaption(err),
                });
            }
        } finally {
            bulkBusy.value = false;
        }
    }

    // ── Restock ──────────────────────────────────────────────────────────
    async function bulkRestock() {
        if (bulkSelection.value.size === 0) return;
        // The one "most-stocked level" (`stockLevelStore.stockedLevel`, by
        // sequence), resolved once rather than per item.
        const top = stockLevelStore.stockedLevel;
        if (!top) {
            $q.notify({
                type: 'negative',
                message: 'No stock levels configured.',
            });
            return;
        }
        bulkBusy.value = true;
        try {
            const ids = [...bulkSelection.value];
            const { updated_count } = await stockItemApi.bulkSetLevelAsync(
                ids, top.stock_level_id,
            );
            // The bulk endpoint writes server-side, so the store's rows are
            // stale until refetched — one refresh for the batch.
            await stockItemStore.getStockItemsAsync();
            ids.forEach((id) => stockItemStore.invalidateLevelOverlays(id));
            // Bypasses `stockItemStore`'s own mutations, so the recipe list's
            // stock-derived facts (cookable, missing counts) have to be marked
            // stale here too — a batch restock changes what's cookable.
            recipeStore.invalidateRecipes();
            $q.notify({
                type: 'positive',
                message: `Marked ${updated_count} item${updated_count === 1 ? '' : 's'} restocked.`,
            });
            cancelBulk();
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not restock.',
                    caption: toastCaption(err),
                });
            }
        } finally {
            bulkBusy.value = false;
        }
    }

    // ── Bulk log waste ──────────────────────────────────────────────────
    // Reuses the single-item MarkAsWastedDialog (R-001). One reason
    // applies to the whole selection ("these all went off"). Each
    // selected item gets its own StockItemWasteEvent + its expiry
    // cleared (same shape as the single-item flow in StockItemRow).
    const bulkWasteOpen = ref(false);
    const bulkWasteItemName = computed(() => {
        const n = bulkSelection.value.size;
        return `${n} item${n === 1 ? '' : 's'}`;
    });
    const bulkWasteSubline = computed(() =>
        'One reason applies to every selected item.',
    );
    function openBulkWasteDialog() {
        if (bulkSelection.value.size === 0) return;
        bulkWasteOpen.value = true;
    }
    async function onBulkMarkAsWasted(reason: WasteReason) {
        if (bulkSelection.value.size === 0) return;
        const ids = [...bulkSelection.value];
        bulkBusy.value = true;
        // 2026-08-22 feedback: this used to be up to THREE sequential
        // requests per selected item (log, clear the expiry, re-read the
        // row) — the slowest thing on the bulk bar by a wide margin. One
        // call now does the lot, and the server echoes each item's previous
        // expiry back so Undo can still put it right.
        let succeeded: Array<{
            event_id: string;
            stock_item_id: string;
            original_expiry: string | null;
        }> = [];
        try {
            const result = await wasteApi.logEventsBulkAsync({
                stock_item_ids: ids,
                reason,
            });
            succeeded = result.events.map((e) => ({
                event_id: e.event_id,
                stock_item_id: e.stock_item_id,
                original_expiry: e.previous_expiry_date,
            }));
            // The expiry clears happened server-side, so the store's copies
            // are stale — one refresh for the whole batch.
            await stockItemStore.getStockItemsAsync();
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not log any as wasted.',
                    caption: toastCaption(err),
                });
            }
            return;
        } finally {
            bulkBusy.value = false;
        }
        const okCount = succeeded.length;
        const failCount = ids.length - okCount;
        if (okCount === 0) {
            $q.notify({
                type: 'negative',
                message: 'Could not log any as wasted.',
            });
            return;
        }
        const failSuffix = failCount > 0
            ? ` (${failCount} could not be logged)`
            : '';
        $q.notify({
            type: 'info',
            message: `Logged ${okCount} item${okCount === 1 ? '' : 's'} as wasted${failSuffix}.`,
            timeout: 6000,
            actions: [{
                label: 'Undo',
                color: 'white',
                handler: () => {
                    void (async () => {
                        try {
                            // Deletes and expiry restores in one call — the
                            // server only restores where a date was echoed,
                            // so items that never had an expiry don't gain one.
                            await wasteApi.deleteEventsBulkAsync({
                                events: succeeded.map((s) => ({
                                    event_id: s.event_id,
                                    restore_expiry_date: s.original_expiry,
                                })),
                            });
                            await stockItemStore.getStockItemsAsync();
                            $q.notify({
                                type: 'positive',
                                message: 'Undone.',
                            });
                        } catch (err) {
                            if (!isAlreadyNotified(err)) {
                                $q.notify({
                                    type: 'negative',
                                    message: 'Could not undo.',
                                    caption: toastCaption(err),
                                });
                            }
                        }
                    })();
                },
            }],
        });
        cancelBulk();
    }

    // ── Bulk add to / remove from a list ────────────────────────────────
    // Round-18: always prompt for the target list, then add every
    // selected item to it. The server's addLineAsync already de-dupes
    // ("already on list"); items already on a DIFFERENT list still get
    // added (multi-list membership is fine).
    async function pickActiveListId(title: string, source: 'all' | 'present-only'): Promise<string | null> {
        const m = shoppingListStore.membership;
        const all = (m?.active_lists ?? []).filter((l) => l.status !== 'done');
        let candidates = all;
        if (source === 'present-only') {
            const ids = new Set<string>();
            for (const sid of bulkSelection.value) {
                const entry = m?.items.find((i) => i.stock_item_id === sid);
                entry?.unticked_list_ids.forEach((lid) => ids.add(lid));
            }
            candidates = all.filter((l) => ids.has(l.shopping_list_id));
        }
        if (candidates.length === 0) {
            $q.notify({
                type: 'info',
                message: source === 'present-only'
                    ? 'None of the selected items are on a list.'
                    : 'No active lists. Create one first.',
            });
            return null;
        }
        return await choose({
            title: title,
            items: candidates.map((l) => ({ label: l.name, value: l.shopping_list_id })),
            initial: candidates[0]!.shopping_list_id,
        });
    }

    async function bulkAddToListPrompt() {
        if (bulkSelection.value.size === 0) return;
        const listId = await pickActiveListId('Add to which list?', 'all');
        if (!listId) return;
        bulkBusy.value = true;
        try {
            const ids = [...bulkSelection.value];
            const { added, already_on_list } =
                await shoppingListApi.bulkAddLinesAsync(listId, ids);
            await shoppingListStore.refreshAsync();
            ids.forEach((id) => invalidateBuyVerdict(id));
            $q.notify({
                type: 'positive',
                message: already_on_list > 0
                    ? `${added} added, ${already_on_list} already on list.`
                    : `${added} added.`,
            });
            cancelBulk();
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not add all items.',
                    caption: toastCaption(err),
                });
            }
        } finally {
            bulkBusy.value = false;
        }
    }

    async function bulkRemoveFromListPrompt() {
        if (bulkSelection.value.size === 0) return;
        const listId = await pickActiveListId('Remove from which list?', 'present-only');
        if (!listId) return;
        bulkBusy.value = true;
        try {
            // Was: fetch the list detail, work out which lines match the
            // selection, then DELETE each one. The bulk endpoint takes stock
            // item ids and is a no-op per item that isn't on the list, so
            // both the detail read and the loop are gone — `removed_count`
            // is the honest number.
            const ids = [...bulkSelection.value];
            const { removed_count } =
                await shoppingListApi.bulkRemoveByStockItemAsync(listId, ids);
            await shoppingListStore.refreshAsync();
            ids.forEach((id) => invalidateBuyVerdict(id));
            const listName = shoppingListStore.summaries.find(
                (s) => s.shopping_list_id === listId,
            )?.display_name ?? 'list';
            $q.notify({
                type: 'positive',
                message: `Removed ${removed_count} from "${listName}".`,
            });
            cancelBulk();
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not remove from list.',
                    caption: toastCaption(err),
                });
            }
        } finally {
            bulkBusy.value = false;
        }
    }

    // ── Bulk move location ───────────────────────────────────────────────
    const moveDialogOpen = ref(false);
    function openMoveDialog() {
        moveDialogOpen.value = true;
    }
    async function bulkMove(locationId: string | null) {
        if (bulkSelection.value.size === 0) return;
        bulkBusy.value = true;
        try {
            await stockItemApi.bulkMoveAsync([...bulkSelection.value], locationId);
            await stockItemStore.getStockItemsAsync();
            $q.notify({
                type: 'positive',
                message: 'Items moved.',
            });
            moveDialogOpen.value = false;
            cancelBulk();
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not move items.',
                    caption: toastCaption(err),
                });
            }
        } finally {
            bulkBusy.value = false;
        }
    }

    // ── Bulk-print QRs (post-N5 polish) ───────────────────────────────────
    // Fires the same QR-sheet endpoint Data → Barcodes & QR uses, scoped to
    // the current bulk selection so the user can stocktake-print without
    // round-tripping through that page.
    function bulkPrintQrs() {
        if (bulkSelection.value.size === 0) return;
        deps.openQrSheet(Array.from(bulkSelection.value));
    }

    return {
        bulkMode,
        bulkSelection,
        bulkBusy,
        toggleBulk,
        selectVisible,
        cancelBulk,
        deselectAll,
        bulkAddToPrimary,
        bulkRestock,
        bulkWasteOpen,
        bulkWasteItemName,
        bulkWasteSubline,
        openBulkWasteDialog,
        onBulkMarkAsWasted,
        pickActiveListId,
        bulkAddToListPrompt,
        bulkRemoveFromListPrompt,
        moveDialogOpen,
        openMoveDialog,
        bulkMove,
        bulkPrintQrs,
    };
}
