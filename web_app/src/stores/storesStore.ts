import { acceptHMRUpdate, defineStore } from 'pinia';
import { nameCollator } from 'src/composables/useMoney';
import type { Store } from 'src/models/store';
import StoresApiService, {
    type CreateStoreCommand,
    type UpdateStoreCommand,
} from 'src/services/api/storesApiService';
import { readonly, ref } from 'vue';

const storesApiService = new StoresApiService();

/** FU-189 — Pinia store for the user-curated Stores list. Naming notes:
 *  the Pinia *store id* is `'stores'` and the composable is `useStoresStore`,
 *  using the existing repo convention (e.g. `useStockItemStore`); the
 *  *entity* is `Store`, distinct from the Pinia concept. */
export const useStoresStore = defineStore('stores', () => {
    const stores = ref<Store[]>([]);
    let hydrated = false;
    let inflight: Promise<void> | null = null;

    // Locale-aware collation from the locale authority (finalisation 20-R7).

    const collator = { compare: (a: string, b: string) => nameCollator().compare(a, b) };

    const listAsync = (): Promise<void> =>
        storesApiService.listAllAsync().then((items) => {
            stores.value = [...items].sort((a, b) =>
                collator.compare(a.name, b.name),
            );
            hydrated = true;
        });

    /** R-016 — lazy hydration. */
    const ensureLoadedAsync = (): Promise<void> => {
        if (hydrated) return Promise.resolve();
        inflight ??= listAsync().finally(() => { inflight = null; });
        return inflight;
    };

    const createAsync = async (cmd: CreateStoreCommand): Promise<void> => {
        await storesApiService.createAsync(cmd);
        await listAsync();
    };

    const updateAsync = async (cmd: UpdateStoreCommand): Promise<void> => {
        await storesApiService.updateAsync(cmd);
        await listAsync();
    };

    const deleteAsync = async (
        storeId: string,
    ): Promise<{ items_affected: number; lines_affected: number }> => {
        const result = await storesApiService.deleteAsync(storeId);
        await listAsync();
        return result;
    };

    return {
        stores: readonly(stores),
        listAsync,
        ensureLoadedAsync,
        createAsync,
        updateAsync,
        deleteAsync,
    };
});

if (import.meta.hot) {
    import.meta.hot.accept(acceptHMRUpdate(useStoresStore, import.meta.hot));
}
