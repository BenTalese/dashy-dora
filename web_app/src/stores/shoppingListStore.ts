import { acceptHMRUpdate, defineStore } from 'pinia';
import type {
    Membership,
    ShoppingListSummary
} from 'src/models/shoppingList';
import ShoppingListApiService from 'src/services/api/shoppingListApiService';
import { computed, readonly, ref } from 'vue';

const api = new ShoppingListApiService();

export const useShoppingListStore = defineStore('shoppingList', () => {
    const summaries = ref<ShoppingListSummary[]>([]);
    const membership = ref<Membership | null>(null);
    const loading = ref(false);
    const loadError = ref<string | null>(null);

    // Chunk 2: the quick-add target is inferred — the server returns it
    // id only when exactly one DRAFT exists; otherwise it's null and the caller
    // must prompt the user.
    const quickAddTargetListId = computed(
        () => membership.value?.quick_add_target_list_id ?? null
    );
    const quickAddTargetSummary = computed(() => {
        const id = quickAddTargetListId.value;
        if (!id) return null;
        return summaries.value.find((s) => s.shopping_list_id === id) ?? null;
    });

    // UX-v2 §3.3 — the "next up" pick is a server-owned rule; the client
    // just follows the flag.
    const nextUpSummary = computed(
        () => summaries.value.find((s) => s.is_next_up) ?? null
    );

    let hydrated = false;
    let latestRequestId = 0;
    let inflight: Promise<void> | null = null;

    // Only the most recent request may write: concurrent refreshes would
    // otherwise apply whichever response happens to arrive last.
    const fetchAsync = async (requestId: number): Promise<void> => {
        try {
            const [s, m] = await Promise.all([
                api.getAllAsync(),
                api.getMembershipAsync()
            ]);
            if (requestId !== latestRequestId) return;
            summaries.value = s;
            membership.value = m;
            hydrated = true;
        } catch (err) {
            if (requestId !== latestRequestId) return;
            // Surface to the console explicitly — the catch used to set
            // `loadError` silently and the UI rendered nothing useful,
            // which read as a "blank screen" bug.
            console.error('[shoppingListStore] refreshAsync failed', err);
            loadError.value = err instanceof Error ? err.message : String(err);
        } finally {
            if (requestId === latestRequestId) loading.value = false;
        }
    };

    /** Resolves once the latest in-flight request has been applied. */
    const settledAsync = async (): Promise<void> => {
        while (inflight) await inflight;
    };

    const refreshAsync = async (): Promise<void> => {
        loading.value = true;
        loadError.value = null;
        const request = fetchAsync(++latestRequestId).finally(() => {
            // Compare identity: a request that settled synchronously must not
            // clear a newer one, and must not be left behind to spin on.
            if (inflight === request) inflight = null;
        });
        inflight = request;
        await settledAsync();
    };

    /** R-016 — lazy hydration. Use this in `onMounted` (or a route guard)
     *  when you need summaries/membership populated but don't care about a
     *  forced refresh; it joins a load already in flight rather than
     *  starting another. Call `refreshAsync` directly for an explicit
     *  refetch (post-mutation, pull-to-refresh, explicit reload). */
    const ensureLoadedAsync = (): Promise<void> => {
        if (hydrated) return Promise.resolve();
        return inflight ? settledAsync() : refreshAsync();
    };

    return {
        summaries: readonly(summaries),
        membership: readonly(membership),
        loading: readonly(loading),
        loadError: readonly(loadError),
        quickAddTargetListId,
        quickAddTargetSummary,
        nextUpSummary,
        refreshAsync,
        ensureLoadedAsync
    };
});

if (import.meta.hot) {
    import.meta.hot.accept(acceptHMRUpdate(useShoppingListStore, import.meta.hot));
}
