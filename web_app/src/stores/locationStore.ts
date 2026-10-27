import { acceptHMRUpdate, defineStore } from 'pinia';
import type { LocationNode } from 'src/models/location';
import LocationApiService, {
    type CreateLocationCommand,
    type UpdateLocationCommand
} from 'src/services/api/locationApiService';
import { computed, readonly, ref } from 'vue';

const api = new LocationApiService();

export const useLocationStore = defineStore('location', () => {
    // Tree of zones. Each LocationNode has nested `children` for areas/sections
    // and `items` for direct stock items.
    const tree = ref<LocationNode[]>([]);
    const loading = ref(false);
    const loadError = ref<string | null>(null);

    let hydrated = false;
    let inflight: Promise<void> | null = null;

    const refreshAsync = async () => {
        loading.value = true;
        loadError.value = null;
        try {
            tree.value = await api.getTreeAsync();
            hydrated = true;
        } catch (err) {
            loadError.value = String(err);
        } finally {
            loading.value = false;
        }
    };

    /** R-016 — lazy hydration. Use this in `onMounted` when you need the
     *  location tree populated but don't care about a forced refresh.
     *  Call `refreshAsync` directly for an explicit refetch (post-mutation,
     *  pull-to-refresh, explicit reload). */
    const ensureLoadedAsync = (): Promise<void> => {
        if (hydrated) return Promise.resolve();
        inflight ??= refreshAsync().finally(() => { inflight = null; });
        return inflight;
    };

    const createAsync = async (command: CreateLocationCommand) => {
        await api.createAsync(command);
        await refreshAsync();
    };

    const updateAsync = async (locationId: string, command: UpdateLocationCommand) => {
        await api.updateAsync(locationId, command);
        await refreshAsync();
    };

    const deleteAsync = async (locationId: string) => {
        await api.deleteAsync(locationId);
        await refreshAsync();
    };

    // Walks the tree to find a node by id. Returns null if not found.
    const findNode = (locationId: string): LocationNode | null => {
        const stack: LocationNode[] = [...tree.value];
        while (stack.length) {
            const node = stack.pop()!;
            if (node.location_id === locationId) return node;
            for (const child of node.children) stack.push(child);
        }
        return null;
    };

    // Parent and name per node, built once per tree load: `breadcrumb` runs
    // once per stock row, so it must not walk the whole tree each time.
    const lookups = computed(() => {
        const parent = new Map<string, string | null>();
        const name = new Map<string, string>();
        const stack: LocationNode[] = [...tree.value];
        while (stack.length) {
            const node = stack.pop()!;
            parent.set(node.location_id, node.parent_id);
            name.set(node.location_id, node.name);
            for (const child of node.children) stack.push(child);
        }
        return { parent, name };
    });

    // Returns the names from root → target so the UI can show
    // "Pantry > Middle shelf > Left side".
    const breadcrumb = (locationId: string): string[] => {
        const { parent, name } = lookups.value;
        const path: string[] = [];
        let cursor: string | null | undefined = locationId;
        let safety = 16;
        while (cursor && safety-- > 0) {
            const label = name.get(cursor);
            if (label === undefined) break;
            path.unshift(label);
            cursor = parent.get(cursor) ?? null;
        }
        return path;
    };

    return {
        // Plain ref (not readonly): consumers walk the tree through helpers
        // typed as mutable LocationNode.
        tree,
        loading: readonly(loading),
        loadError: readonly(loadError),
        refreshAsync,
        ensureLoadedAsync,
        createAsync,
        updateAsync,
        deleteAsync,
        findNode,
        breadcrumb
    };
});

if (import.meta.hot) {
    import.meta.hot.accept(acceptHMRUpdate(useLocationStore, import.meta.hot));
}
