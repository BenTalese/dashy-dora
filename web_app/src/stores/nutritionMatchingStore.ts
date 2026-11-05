import { acceptHMRUpdate, defineStore } from 'pinia';
import NutritionApiService from 'src/services/api/nutritionApiService';
import { readonly, ref } from 'vue';

const nutritionApiService = new NutritionApiService();

/** Count of stock items still waiting for a nutrition food link — the rows
 *  shown on Settings → Kitchen setup → Nutrition matching. Drives the sidebar
 *  attention badge, exactly as `unlinkedIngredientsStore` does for the recipe
 *  bulk-linker (owner 2026-09-03 asked for the two to match; the earlier note
 *  on the nav entry argued the opposite and is superseded). Server owns the
 *  matching and the counts (R-003); this store only caches the number for
 *  cross-surface display. */
export const useNutritionMatchingStore = defineStore('nutritionMatching', () => {
    const count = ref(0);
    let hydrated = false;
    let inflight: Promise<void> | null = null;

    // Set-aside items aren't outstanding work, so the server's count leaves
    // them out, as the list does.
    const refreshAsync = (): Promise<void> =>
        nutritionApiService.getUnmatchedItemCountAsync().then((n) => {
            count.value = n;
            hydrated = true;
        });

    /** R-016 — lazy hydration. Fetches once, dedupes concurrent first loads. */
    const ensureLoadedAsync = (): Promise<void> => {
        if (hydrated) return Promise.resolve();
        inflight ??= refreshAsync().finally(() => { inflight = null; });
        return inflight;
    };

    /** Sync from a list the caller already fetched — the matching page refetches
     *  after every action, so it feeds the new count here rather than firing a
     *  second round-trip. */
    const setCount = (n: number): void => {
        count.value = n;
        hydrated = true;
    };

    return { count: readonly(count), refreshAsync, ensureLoadedAsync, setCount };
});

if (import.meta.hot) {
    import.meta.hot.accept(acceptHMRUpdate(useNutritionMatchingStore, import.meta.hot));
}
