import { computed, ref } from 'vue';
import HealthApiService, { invalidateHealthInfo } from 'src/services/api/healthApiService';
import type { BudgetPeriod } from 'src/models/auth';

// Install-wide household grocery budget, read from /api/health `budget_policy`.
// Moved off the per-user record (the budget tracks spend across every *shared*
// shopping list, so it's one value per household, not per person — same class
// of move as FU-615's cooking config). Value-driven: `amount` null ⇒ no budget
// set (the feature is off).
//
// Module-level state so the health probe runs once per session and every caller
// shares the same reactive answer — mirrors `useCookingPolicy`. The Settings →
// Money page calls `refreshBudgetPolicy()` after a save so the dashboard budget
// card + any other reader pick up the change without a full reload.

const amount = ref<number | null>(null);
const period = ref<BudgetPeriod>('weekly');
const loaded = ref(false);
let inflight: Promise<void> | null = null;

function load(): Promise<void> {
    if (!inflight) {
        inflight = new HealthApiService()
            .getInfoAsync()
            .then((info) => {
                const server = info.budget_policy;
                if (!server) return;
                const raw = server.amount;
                amount.value =
                    typeof raw === 'number' && Number.isFinite(raw) && raw > 0
                        ? raw
                        : null;
                period.value = server.period === 'monthly' ? 'monthly' : 'weekly';
            })
            .catch(() => {
                // Health probe failure ⇒ keep the conservative defaults (no
                // budget, weekly). Nothing breaks.
            })
            .finally(() => {
                loaded.value = true;
            });
    }
    return inflight;
}

/** Force-reload the household budget from the server. The Money settings page
 *  calls this after saving so every budget reader stays coherent. */
export function refreshBudgetPolicy(): Promise<void> {
    loaded.value = false;
    inflight = null;
    invalidateHealthInfo();
    return load();
}

export function useBudgetSettings() {
    void load();
    return {
        budgetAmount: computed(() => amount.value),
        budgetPeriod: computed(() => period.value),
        budgetPolicyLoaded: computed(() => loaded.value),
        refreshBudgetPolicy,
    };
}
