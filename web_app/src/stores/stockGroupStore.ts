import { acceptHMRUpdate, defineStore } from 'pinia';
import type { StockGroup } from 'src/models/stockGroup';
import StockGroupApiService from 'src/services/api/stockGroupApiService';
import type { Ref } from 'vue';
import { readonly, ref } from 'vue';

const api = new StockGroupApiService();

/** The household's stock groups, loaded once and shared (finalisation 05-R13;
 *  the overview, the create dialog, the item page and onboarding each fetched
 *  their own). Writes go through here so the cache is marked stale. */
export const useStockGroupStore = defineStore('stockGroup', () => {
    const stockGroups: Ref<StockGroup[]> = ref([]);
    let hydrated = false;
    let inflight: Promise<void> | null = null;

    const refreshAsync = (): Promise<void> =>
        api.getAllAsync().then((groups) => {
            stockGroups.value = groups;
            hydrated = true;
        });

    /** R-016 — lazy hydration; concurrent first loads share one request. */
    const ensureLoadedAsync = (): Promise<void> => {
        if (hydrated) return Promise.resolve();
        inflight ??= refreshAsync().finally(() => { inflight = null; });
        return inflight;
    };

    const createAsync = async (name: string) => {
        const created = await api.createAsync({ name });
        hydrated = false;
        return created;
    };

    const renameAsync = async (id: string, name: string) => {
        await api.updateAsync(id, { name });
        hydrated = false;
    };

    const deleteAsync = async (id: string) => {
        const result = await api.deleteAsync(id);
        hydrated = false;
        return result;
    };

    return {
        stockGroups: readonly(stockGroups),
        refreshAsync,
        ensureLoadedAsync,
        createAsync,
        renameAsync,
        deleteAsync,
    };
});

if (import.meta.hot) {
    import.meta.hot.accept(acceptHMRUpdate(useStockGroupStore, import.meta.hot));
}
