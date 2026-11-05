import { acceptHMRUpdate, defineStore } from 'pinia';
import RecipeApiService from 'src/services/api/recipeApiService';
import { readonly, ref } from 'vue';

const recipeApiService = new RecipeApiService();

/** Count of distinct unlinked recipe-ingredient groups — the rows shown on
 *  Settings → Kitchen setup → Unlinked ingredients. Drives the sidebar
 *  attention badge so the nav flags outstanding cleanup without opening the
 *  page. Server owns the grouping/normalisation (R-003); this store only
 *  caches the count for cross-surface display. */
export const useUnlinkedIngredientsStore = defineStore('unlinkedIngredients', () => {
    const count = ref(0);
    let hydrated = false;
    let inflight: Promise<void> | null = null;

    const refreshAsync = (): Promise<void> =>
        recipeApiService.getUnlinkedIngredientCountAsync().then((n) => {
            count.value = n;
            hydrated = true;
        });

    /** R-016 — lazy hydration. Fetches once, dedupes concurrent first loads.
     *  Call `refreshAsync` directly to force a refetch. */
    const ensureLoadedAsync = (): Promise<void> => {
        if (hydrated) return Promise.resolve();
        inflight ??= refreshAsync().finally(() => { inflight = null; });
        return inflight;
    };

    /** Sync the count from a list the caller already fetched. The unlinked
     *  page refetches the full group list after every link, so it feeds the
     *  new count here rather than triggering a second round-trip. */
    const setCount = (n: number): void => {
        count.value = n;
        hydrated = true;
    };

    return { count: readonly(count), refreshAsync, ensureLoadedAsync, setCount };
});

if (import.meta.hot) {
    import.meta.hot.accept(acceptHMRUpdate(useUnlinkedIngredientsStore, import.meta.hot));
}
