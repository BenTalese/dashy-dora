import { useQuasar } from 'quasar';
import WasteApiService, { type WasteReason } from 'src/services/api/wasteApiService';
import { isAlreadyNotified, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
import { useStockItemStore } from 'src/stores/stockItemStore';

export type LogWasteTarget = {
    stockItemId: string;
    itemName: string;
    /** The item's expiry before the log, so Undo can put it back. */
    originalExpiry: string | null;
};

/**
 * C-waste single-item log: post the reason-only event, clear the item's
 * expiry, and offer a 5s Undo that reverts both
 * (PROPOSAL_WASTE_MINIMISATION §5).
 *
 * Lifted out of `StockItemRow` when the bell's expired alerts gained a
 * "Log waste" button (owner 2026-10-17), so both surfaces log the same way
 * (R-001). `onChanged` runs after the log and after an Undo, for callers
 * whose view is derived from the expiry (the bell refreshes its alerts).
 *
 * Callers pass a snapshot taken when the user picked the item, not live
 * props: the row may re-render with stale data while the request is in
 * flight, and the Undo closure must remember the original expiry on its own.
 */
export function useLogWaste(onChanged?: () => void | Promise<void>) {
    const $q = useQuasar();
    const wasteApi = new WasteApiService();
    const stockItemStore = useStockItemStore();

    async function logWasteAsync(target: LogWasteTarget, reason: WasteReason): Promise<void> {
        const { stockItemId, itemName, originalExpiry } = target;
        try {
            const { event_id } = await wasteApi.logEventAsync({
                stock_item_id: stockItemId,
                reason,
            });
            if (originalExpiry) {
                await stockItemStore.updateStockItemAsync({
                    stock_item_id: stockItemId,
                    expiry_date: null,
                });
            }
            await onChanged?.();
            $q.notify({
                type: 'info',
                message: `Logged "${itemName}" as wasted.`,
                timeout: 5000,
                actions: [
                    {
                        // No `color` — an info toast is a light elevated
                        // surface now, so a white Undo would be invisible on
                        // it. Quasar's default for notification actions is
                        // `var(--q-primary)`, which follows the theme.
                        label: 'Undo',
                        handler: () => {
                            void (async () => {
                                try {
                                    await wasteApi.deleteEventAsync(event_id);
                                    if (originalExpiry) {
                                        await stockItemStore.updateStockItemAsync({
                                            stock_item_id: stockItemId,
                                            expiry_date: originalExpiry,
                                        });
                                    }
                                    await onChanged?.();
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
                    },
                ],
            });
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not log as wasted.',
                    caption: toastCaption(err),
                });
            }
        }
    }

    return { logWasteAsync };
}
