import { acceptHMRUpdate, defineStore } from 'pinia';
import type { MealSlot } from 'src/models/mealSlot';
import MealSlotApiService, {
    type ReorderMealSlotsCommand,
} from 'src/services/api/mealSlotApiService';
import type { Ref } from 'vue';
import { computed, ref } from 'vue';
import { DEFAULT_MEAL_SLOTS } from 'src/helpers/recipeVocabulary';

// shared cache of the household-wide meal-slot vocabulary, consumed by the
// planner, the planner edit dialog and the recipe `time_of_day` pickers.
//
// **R-003 — every write goes through here, including the settings page's.**
// Until 2026-09-01 `RecipeMealSlotsSettings.vue` talked to the api service
// directly while this store kept a `hydrated` short-circuit, so a slot added,
// renamed or deleted in settings was invisible to every other surface until a
// full page reload. Two owner-reported bugs came out of that single seam:
// the planner's "which slot?" list not honouring settings until a refresh, and
// "could not update the plan" errors after editing slots — the planner armed a
// slot name that no longer existed, and the server's write-time vocabulary
// check (`slot_validation.py`) rejected it. A store that caches must own the
// invalidation; a caller that mutates behind the cache is the bug.
const mealSlotApi = new MealSlotApiService();

export const useMealSlotStore = defineStore('mealSlot', () => {
    const mealSlots: Ref<MealSlot[]> = ref([]);

    // Ordered slot names — the shape every read-site dropdown wants.
    const mealSlotNames = computed(() =>
        [...mealSlots.value]
            .sort((a, b) => a.sequence - b.sequence || a.name.localeCompare(b.name))
            .map((s) => s.name),
    );

    /** Slot names for a picker; the seeded defaults stand in until the
     *  household's own slots have loaded. */
    const slotNamesOrDefault = computed<string[]>(() =>
        (mealSlotNames.value.length > 0 ? mealSlotNames.value : [...DEFAULT_MEAL_SLOTS]));

    let hydrated = false;
    let inflight: Promise<void> | null = null;

    const getMealSlotsAsync = async () => {
        mealSlots.value = await mealSlotApi.getAllAsync();
        hydrated = true;
    };

    /** R-016 — lazy hydration. Meal slots are household reference data, so
     *  cached readers can short-circuit on second visits. Every mutation below
     *  re-fetches, so the cache can only ever be stale between a write landing
     *  and its refresh resolving. */
    const ensureLoadedAsync = (): Promise<void> => {
        if (hydrated) return Promise.resolve();
        inflight ??= getMealSlotsAsync().finally(() => { inflight = null; });
        return inflight;
    };

    const createAsync = async (name: string): Promise<void> => {
        await mealSlotApi.createAsync({ name });
        await getMealSlotsAsync();
    };

    const renameAsync = async (id: string, name: string): Promise<void> => {
        await mealSlotApi.updateAsync(id, { name });
        await getMealSlotsAsync();
    };

    /** Deleting a slot is NOT a cascade — meal-plan entries and recipe
     *  `time_of_day` values keep their label string and become off-vocab. The
     *  count of entries left holding the name is returned so the caller can
     *  say so. */
    const removeAsync = async (id: string): Promise<{ entries_affected: number }> => {
        const result = await mealSlotApi.deleteAsync(id);
        await getMealSlotsAsync();
        return result;
    };

    const reorderAsync = async (command: ReorderMealSlotsCommand): Promise<void> => {
        await mealSlotApi.reorderAsync(command);
        await getMealSlotsAsync();
    };

    return {
        mealSlots,
        mealSlotNames,
        slotNamesOrDefault,
        getMealSlotsAsync,
        ensureLoadedAsync,
        createAsync,
        renameAsync,
        removeAsync,
        reorderAsync,
    };
});

if (import.meta.hot) {
    import.meta.hot.accept(acceptHMRUpdate(useMealSlotStore, import.meta.hot));
}
