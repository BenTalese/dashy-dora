// @vitest-environment jsdom
//
// Store-layer coverage — locationStore, the Locations tree cache. The two
// tree-walking helpers (`findNode`, `breadcrumb`) are real client logic —
// they power "Pantry > Middle shelf > Left side" everywhere a location is
// rendered — so they get the edge-case treatment (empty tree, unknown id,
// deep nesting, root-only). Plus the mutation→refetch contract and the
// R-016 lazy-hydration semantics shared with the other collection stores.
import { createPinia, setActivePinia } from 'pinia';
import type { LocationKind, LocationNode } from 'src/models/location';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useLocationStore } from 'src/stores/locationStore';
import { useStockFilters } from 'src/composables/useStockFilters';

const m = vi.hoisted(() => ({
    getTreeAsync: vi.fn(),
    createAsync: vi.fn(),
    updateAsync: vi.fn(),
    deleteAsync: vi.fn(),
}));

const stock = vi.hoisted(() => ({ refreshIfLoadedAsync: vi.fn() }));
vi.mock('src/stores/stockItemStore', () => ({
    useStockItemStore: () => ({ refreshIfLoadedAsync: stock.refreshIfLoadedAsync }),
}));

vi.mock('src/services/api/locationApiService', () => ({
    default: class {
        getTreeAsync = m.getTreeAsync;
        createAsync = m.createAsync;
        updateAsync = m.updateAsync;
        deleteAsync = m.deleteAsync;
    },
}));

function node(
    id: string,
    name: string,
    kind: LocationKind,
    parentId: string | null,
    children: LocationNode[] = [],
): LocationNode {
    return {
        location_id: id,
        name,
        kind,
        parent_id: parentId,
        sequence: 0,
        direct_item_count: 0,
        descendant_item_count: 0,
        items: [],
        children,
    };
}

/** Pantry > Middle shelf > Left side, plus a sibling zone. */
function fixtureTree(): LocationNode[] {
    return [
        node('Z1', 'Pantry', 'zone', null, [
            node('A1', 'Middle shelf', 'area', 'Z1', [
                node('S1', 'Left side', 'section', 'A1'),
                node('S2', 'Right side', 'section', 'A1'),
            ]),
        ]),
        node('Z2', 'Garage fridge', 'zone', null),
    ];
}

beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    m.getTreeAsync.mockResolvedValue(fixtureTree());
    m.createAsync.mockResolvedValue(undefined);
    m.updateAsync.mockResolvedValue(undefined);
    m.deleteAsync.mockResolvedValue(undefined);
    stock.refreshIfLoadedAsync.mockResolvedValue(undefined);
});

describe('locationStore — findNode', () => {
    it('finds a root zone and a deeply nested section', async () => {
        const store = useLocationStore();
        await store.refreshAsync();

        expect(store.findNode('Z2')?.name).toBe('Garage fridge');
        expect(store.findNode('S1')?.name).toBe('Left side');
    });

    it('returns null for an unknown id and on an empty tree', async () => {
        const store = useLocationStore();
        expect(store.findNode('Z1')).toBeNull(); // nothing loaded yet

        await store.refreshAsync();
        expect(store.findNode('nope')).toBeNull();
    });
});

describe('locationStore — breadcrumb', () => {
    it('walks root → target in display order', async () => {
        const store = useLocationStore();
        await store.refreshAsync();

        expect(store.breadcrumb('S1')).toEqual(['Pantry', 'Middle shelf', 'Left side']);
    });

    it('is a single segment for a root zone', async () => {
        const store = useLocationStore();
        await store.refreshAsync();

        expect(store.breadcrumb('Z2')).toEqual(['Garage fridge']);
    });

    it('returns [] for an unknown id rather than throwing', async () => {
        const store = useLocationStore();
        await store.refreshAsync();

        expect(store.breadcrumb('missing')).toEqual([]);
    });
});

describe('locationStore — refresh + error handling', () => {
    it('keeps the stale tree and resets flags when a refresh fails', async () => {
        const store = useLocationStore();
        await store.refreshAsync();

        m.getTreeAsync.mockRejectedValueOnce(new Error('offline'));
        await store.refreshAsync();

        expect(store.tree).toHaveLength(2); // stale-but-usable beats blank
        expect(store.loadError).toContain('offline');
        expect(store.loading).toBe(false);
    });

    it('mutations refetch the whole tree (server owns structure)', async () => {
        const store = useLocationStore();
        await store.refreshAsync();

        await store.createAsync({ name: 'Freezer', kind: 'zone', parent_id: null });
        await store.updateAsync('Z1', { name: 'Big pantry' });
        await store.deleteAsync('Z2');

        expect(m.createAsync).toHaveBeenCalledTimes(1);
        expect(m.updateAsync).toHaveBeenCalledWith('Z1', { name: 'Big pantry' });
        expect(m.deleteAsync).toHaveBeenCalledWith('Z2');
        expect(m.getTreeAsync).toHaveBeenCalledTimes(4); // seed + one per mutation
    });

    it('delete refetches stock and drops a stock filter naming the deleted subtree', async () => {
        const store = useLocationStore();
        await store.refreshAsync();
        const filters = useStockFilters({
            stockItems: () => [],
            stockLevels: () => [],
            locationTree: () => [],
            recipes: () => [],
            stockGroups: () => [],
            membership: () => null,
        }, { persistScope: 'location-delete-test' });
        filters.locationFilter.value = 'S1';

        await store.deleteAsync('Z2');
        expect(filters.locationFilter.value).toBe('S1'); // unrelated zone

        await store.deleteAsync('A1'); // S1's parent area
        expect(filters.locationFilter.value).toBeNull();
        expect(stock.refreshIfLoadedAsync).toHaveBeenCalledTimes(2);
    });

    it('a failed refresh after a successful delete does not reject', async () => {
        const store = useLocationStore();
        await store.refreshAsync();
        m.getTreeAsync.mockRejectedValueOnce(new Error('blip'));
        stock.refreshIfLoadedAsync.mockRejectedValueOnce(new Error('blip'));

        await expect(store.deleteAsync('Z2')).resolves.toBeUndefined();
        expect(m.deleteAsync).toHaveBeenCalledWith('Z2');
        expect(store.loadError).toContain('blip');
    });
});

describe('locationStore — ensureLoadedAsync (R-016)', () => {
    it('dedupes concurrent callers into one fetch and no-ops once hydrated', async () => {
        const store = useLocationStore();

        await Promise.all([store.ensureLoadedAsync(), store.ensureLoadedAsync()]);
        await store.ensureLoadedAsync();

        expect(m.getTreeAsync).toHaveBeenCalledTimes(1);
    });

    it('retries after a failed hydration instead of caching the failure', async () => {
        m.getTreeAsync.mockRejectedValueOnce(new Error('offline'));
        const store = useLocationStore();

        await store.ensureLoadedAsync(); // absorbed into loadError
        expect(store.tree).toHaveLength(0);

        await store.ensureLoadedAsync();
        expect(m.getTreeAsync).toHaveBeenCalledTimes(2);
        expect(store.tree).toHaveLength(2);
    });
});
