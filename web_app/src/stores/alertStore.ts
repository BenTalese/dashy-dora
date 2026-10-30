import { acceptHMRUpdate, defineStore } from 'pinia';
import { DEFAULT_SNOOZE_DAYS, type Alert, type Alerts } from 'src/models/alert';
import AlertApiService from 'src/services/api/alertApiService';
import { computed, readonly, ref } from 'vue';

const api = new AlertApiService();

// Server now owns "what counts" (C-9.1): alert conditions are derived live
// and the user's snooze/dismiss decisions are persisted in
// AlertInteraction, so the badge, list, snoozed set, and (later) channels
// all read one server-derived truth. The store is a thin cache behind the
// header bell — no client-side recompute of counts or snooze (R-003).
const EMPTY: Alerts = {
    items: [],
    snoozed: [],
    high_count: 0,
    medium_count: 0,
    low_count: 0,
    actionable_count: 0,
    snoozed_count: 0,
};

export const useAlertStore = defineStore('alert', () => {
    const data = ref<Alerts>({ ...EMPTY });
    const loading = ref(false);
    const loadError = ref<string | null>(null);

    const alerts = computed<Alerts>(() => data.value);
    // The badge counts the actionable tier (high+medium) — server-derived.
    const badgeCount = computed(() => data.value.actionable_count);
    const totalCount = computed(() => data.value.items.length);
    const snoozedCount = computed(() => data.value.snoozed_count);
    const snoozedAlerts = computed<Alert[]>(() => data.value.snoozed);

    // Only the most recent request may write: concurrent refreshes would
    // otherwise apply whichever response happens to arrive last.
    let latestRequestId = 0;
    const refreshAsync = async () => {
        const requestId = ++latestRequestId;
        loading.value = true;
        loadError.value = null;
        try {
            const result = await api.getAlertsAsync();
            if (requestId === latestRequestId) data.value = result;
        } catch (err) {
            if (requestId === latestRequestId) loadError.value = String(err);
        } finally {
            if (requestId === latestRequestId) loading.value = false;
        }
    };

    // All mutations go server-side, then refresh so every surface agrees.
    const snoozeAlert = async (alertId: string, days = DEFAULT_SNOOZE_DAYS) => {
        await api.snoozeAsync(alertId, days);
        await refreshAsync();
    };
    const unsnoozeAlert = async (alertId: string) => {
        await api.clearSuppressionAsync(alertId);
        await refreshAsync();
    };
    const dismissAlert = async (alertId: string) => {
        await api.dismissAsync(alertId);
        await refreshAsync();
    };
    // No read state (owner 2026-10-15): dismiss is the one way to put an
    // alert away, and "Dismiss all" replaces "Mark all read".
    const dismissAllAsync = async () => {
        await api.dismissAllAsync();
        await refreshAsync();
    };

    /** ISO snooze cutoff for a snoozed alert, or null. Read from the server's
     *  snoozed set rather than tracked locally. */
    const snoozedUntil = (alertId: string): string | null =>
        data.value.snoozed.find((a) => a.alert_id === alertId)?.snoozed_until ?? null;

    return {
        alerts,
        loading: readonly(loading),
        loadError: readonly(loadError),
        badgeCount,
        totalCount,
        snoozedCount,
        snoozedAlerts,
        refreshAsync,
        snoozeAlert,
        unsnoozeAlert,
        dismissAlert,
        dismissAllAsync,
        snoozedUntil,
    };
});

if (import.meta.hot) {
    import.meta.hot.accept(acceptHMRUpdate(useAlertStore, import.meta.hot));
}
