import { computed, ref } from 'vue';
import HealthApiService, { invalidateHealthInfo } from 'src/services/api/healthApiService';

// FU-615 — install-wide household cooking config, read from /api/health.
// Two values, both moved off the per-user record onto the AppSetting
// singleton (a household has one headcount + one cook-style):
//   * householdHeadcount — how many people the household cooks for. null =
//     not set, in which case cook mode falls back to each recipe's own
//     servings.
//   * batchEnabled — the cook-style. false ("fresh") keeps the meal-planner
//     pure scheduling; true ("batch") reveals the cook pool (per-recipe ± /
//     log-cook / "n free"), the shortfall warning, and the "to cook by" line.
//
// Module-level state so the health probe runs once per session and every
// caller shares the same reactive answer — mirrors `useImagePolicy` /
// `useMoney`. The admin Cooking settings page calls `refreshCookingPolicy()`
// after a save so the change takes effect without a full reload.

const householdHeadcount = ref<number | null>(null);
const batchEnabled = ref<boolean>(false);
const loaded = ref(false);
let inflight: Promise<void> | null = null;

function load(): Promise<void> {
    if (!inflight) {
        inflight = new HealthApiService()
            .getInfoAsync()
            .then((info) => {
                const server = info.cooking_policy;
                if (!server) return;
                const raw = server.household_headcount;
                householdHeadcount.value =
                    typeof raw === 'number' && Number.isFinite(raw) && raw > 0
                        ? Math.floor(raw)
                        : null;
                batchEnabled.value = !!server.batch_features_enabled;
            })
            .catch(() => {
                // Health probe failure ⇒ keep the conservative defaults
                // (no headcount, fresh cook-style). Nothing breaks.
            })
            .finally(() => {
                loaded.value = true;
            });
    }
    return inflight;
}

/** Force-reload the policy from the server. The admin Cooking settings page
 *  calls this after saving so cook mode + the meal-planner pick up the new
 *  values without a full page reload. */
export function refreshCookingPolicy(): Promise<void> {
    loaded.value = false;
    inflight = null;
    invalidateHealthInfo();
    return load();
}

export function useCookingPolicy() {
    void load();
    return {
        householdHeadcount: computed(() => householdHeadcount.value),
        batchEnabled: computed(() => batchEnabled.value),
        cookingPolicyLoaded: computed(() => loaded.value),
        refreshCookingPolicy,
    };
}
