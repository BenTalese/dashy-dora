import { ref } from 'vue';
import { useQuasar } from 'quasar';
import type { Alert, AlertAction } from 'src/models/alert';
import AlertApiService from 'src/services/api/alertApiService';
import { useAlertStore } from 'src/stores/alertStore';
import { useStockItemStore } from 'src/stores/stockItemStore';
import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';

const api = new AlertApiService();

/**
 * The one place the "user taps an inline alert action" mutation lives: the
 * applyAction API call + refresh + success/error toast + per-row busy state.
 * Every alert surface composes this (the bell is the only one since the alerts
 * page went, 2026-10-15) so
 * the toast + error handling can't drift apart again (FU-521 / R-003) — the bug
 * that motivated it was the dashboard silently swallowing both toasts while the
 * bell + hub toasted "Done.".
 *
 * `refresh` defaults to the shared alert store; a surface with extra derived
 * state (the dashboard also reloads its summary/score) passes its own.
 *
 * Call from a component `setup`. Bind `busyAlertId` for per-row spinners.
 */
export function useAlertActions() {
    const $q = useQuasar();
    const alertStore = useAlertStore();
    const stockItemStore = useStockItemStore();

    const busyAlertId = ref<string | null>(null);

    async function applyAction(
        alert: Alert,
        action: AlertAction,
        opts?: { refresh?: () => Promise<void> },
    ): Promise<boolean> {
        busyAlertId.value = alert.alert_id;
        try {
            await api.applyActionAsync(alert.alert_id, action);
            await (opts?.refresh ? opts.refresh() : alertStore.refreshAsync());
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not apply.',
                caption: toastCaption(err),
            });
            busyAlertId.value = null;
            return false;
        }
        // Every alert action writes the item's expiry server-side. Refreshed
        // outside the try: the action already succeeded, so a failed refresh
        // (404 after a delete, a network blip) must not report it as failed.
        // The store skips the GET when the row isn't loaded.
        if (alert.stock_item_id) {
            await stockItemStore.refreshStockItemAsync(alert.stock_item_id).catch(() => undefined);
        }
        busyAlertId.value = null;
        $q.notify({ type: 'positive', message: 'Done.' });
        return true;
    }

    return { busyAlertId, applyAction };
}
