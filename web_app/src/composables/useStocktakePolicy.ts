import { computed, ref } from 'vue';
import HealthApiService, { invalidateHealthInfo } from 'src/services/api/healthApiService';

// Install-wide stocktake defaults, read from /api/health (2026-08-28).
// `newItemsOptIn` is the position the create-stock-item dialog's Stocktake
// toggle starts in — the server applies the same value when the field is
// omitted, so the switch shows what will actually happen rather than a
// client-side guess (R-003: the default is the server's fact).
//
// Module-level state so the health probe runs once per session and every
// caller shares the same reactive answer — mirrors useReconcilePolicy /
// useCookingPolicy. The admin Stocktake settings page calls
// `refreshStocktakePolicy()` after a save so the dialog picks up the new
// default without a full reload.

const newItemsOptIn = ref<boolean>(true); // default matches the server
const loaded = ref(false);
let inflight: Promise<void> | null = null;

function load(): Promise<void> {
    if (!inflight) {
        inflight = new HealthApiService()
            .getInfoAsync()
            .then((info) => {
                const server = info.stocktake_policy;
                if (!server) return;
                newItemsOptIn.value = !!server.new_items_opt_in;
            })
            .catch(() => {
                // Health probe failure ⇒ keep the default (opted in).
            })
            .finally(() => {
                loaded.value = true;
            });
    }
    return inflight;
}

/** Force-reload from the server. The admin Stocktake settings page calls this
 *  after saving so a changed default reaches the create dialog immediately. */
export function refreshStocktakePolicy(): Promise<void> {
    loaded.value = false;
    inflight = null;
    invalidateHealthInfo();
    return load();
}

export function useStocktakePolicy() {
    void load();
    return {
        newItemsOptIn: computed(() => newItemsOptIn.value),
        stocktakePolicyLoaded: computed(() => loaded.value),
        refreshStocktakePolicy,
    };
}
