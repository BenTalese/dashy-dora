import { computed, ref } from 'vue';
import HealthApiService, { invalidateHealthInfo } from 'src/services/api/healthApiService';

// Install-wide meal-reconcile posture, read from /api/health (owner 2026-08-13).
// `autoDrain` picks the /meal-plans/reconcile surface:
//   * true  (auto)   — Dora silently drains past-day meals; the page shows a
//                      read-only LOG of what happened (no confirm-each runner,
//                      no dashboard chip, no overdue nudge).
//   * false (manual) — past meals stay pending; the page shows the RUNNER that
//                      walks each one for confirmation.
//
// Module-level state so the health probe runs once per session and every caller
// shares the same reactive answer — mirrors useCookingPolicy / useMoney. The
// admin Meal-reconcile settings page calls `refreshReconcilePolicy()` after a
// save so the surface flips without a full reload.

const autoDrain = ref<boolean>(true); // default matches the server sweep
const loaded = ref(false);
let inflight: Promise<void> | null = null;

function load(): Promise<void> {
    if (!inflight) {
        inflight = new HealthApiService()
            .getInfoAsync()
            .then((info) => {
                const server = info.reconcile_policy;
                if (!server) return;
                autoDrain.value = !!server.auto_drain;
            })
            .catch(() => {
                // Health probe failure ⇒ keep the conservative default (auto).
            })
            .finally(() => {
                loaded.value = true;
            });
    }
    return inflight;
}

/** Force-reload from the server. The admin Meal-reconcile settings page calls
 *  this after saving so the reconcile page picks the right surface without a
 *  full page reload. */
export function refreshReconcilePolicy(): Promise<void> {
    loaded.value = false;
    inflight = null;
    invalidateHealthInfo();
    return load();
}

export function useReconcilePolicy() {
    void load();
    return {
        autoDrain: computed(() => autoDrain.value),
        reconcilePolicyLoaded: computed(() => loaded.value),
        refreshReconcilePolicy,
    };
}
