import { computed, ref } from 'vue';

import MealPlanApiService, {
    type ReconcileEntry,
    type ReconcileVerbCommand,
    type ReconcileVerbResult,
} from 'src/services/api/mealPlanApiService';
import { useRecipeStore } from 'src/stores/recipeStore';

/** FU-317 Chunk 5 — one composable powers three surfaces: the reconcile
 *  page (runner), the dashboard chip (count only), and the meal-plans
 *  header nudge (count only). Shared refs so a verb submitted on the
 *  page invalidates the chip's count in the same tick.
 *
 *  Server owns the queue (R-003). This composable is a thin cache +
 *  request layer; no derivation of overdue / count / order client-side.
 */

const api = new MealPlanApiService();

const entries = ref<ReconcileEntry[]>([]);
const total = ref(0);
const nextCursor = ref<string | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);
let fetchedAt = 0;
let inflight: Promise<void> | null = null;

const STALE_AFTER_MS = 60_000;

async function fetchInitial(): Promise<void> {
    if (inflight) return inflight;
    loading.value = true;
    error.value = null;
    const p = api
        .getReconcileQueueAsync({ limit: 30 })
        .then((page) => {
            entries.value = page.entries;
            total.value = page.total;
            nextCursor.value = page.next_cursor;
            fetchedAt = Date.now();
        })
        .catch((err: unknown) => {
            error.value = err instanceof Error ? err.message : String(err);
        })
        .finally(() => {
            loading.value = false;
            inflight = null;
        });
    inflight = p;
    return p;
}

async function fetchNextPage(): Promise<void> {
    if (!nextCursor.value) return;
    loading.value = true;
    try {
        const page = await api.getReconcileQueueAsync({
            cursor: nextCursor.value,
            limit: 30,
        });
        entries.value.push(...page.entries);
        // `total` is exact and doesn't change page-to-page.
        nextCursor.value = page.next_cursor;
    } catch (err: unknown) {
        error.value = err instanceof Error ? err.message : String(err);
    } finally {
        loading.value = false;
    }
}

async function submitVerb(
    entryId: string,
    command: ReconcileVerbCommand,
): Promise<ReconcileVerbResult> {
    const result = await api.submitReconcileVerbAsync(entryId, command);
    // A verb moves the recipe's meal pool; the server returns the new value.
    const recipeId = entries.value.find((e) => e.entry_id === entryId)?.recipe.id;
    const recipeStore = useRecipeStore();
    if (recipeId) recipeStore.setAvailableMeals(recipeId, result.new_pool);
    else recipeStore.invalidateRecipes();
    // Remove the entry from the local queue on any non-skip terminal
    // resolution. Skip writes a `resolved_deferred` receipt whose queue
    // filter still shows it, so keep it visible until the next explicit
    // refetch. If a subsequent invalidate() is called, the server truth
    // rehydrates the list.
    if (command.verb !== 'skip' && !result.idempotent) {
        const idx = entries.value.findIndex((e) => e.entry_id === entryId);
        if (idx >= 0) {
            entries.value.splice(idx, 1);
            total.value = Math.max(0, total.value - 1);
        }
    }
    return result;
}

/** Called by callers that changed something the queue depends on
 *  (e.g. deleting a meal plan while receipts are still hanging off it).
 *  Doesn't refetch — the next `useReconcileQueue()` load triggers it. */
function invalidateReconcileQueue(): void {
    fetchedAt = 0;
}

export function useReconcileQueue() {
    const stale = Date.now() - fetchedAt > STALE_AFTER_MS;
    if (stale && !inflight) {
        void fetchInitial();
    }
    return {
        entries: computed(() => entries.value),
        total: computed(() => total.value),
        hasMore: computed(() => nextCursor.value !== null),
        loading: computed(() => loading.value),
        error: computed(() => error.value),
        fetchNextPage,
        submitVerb,
        reload: fetchInitial,
    };
}

export { invalidateReconcileQueue };
