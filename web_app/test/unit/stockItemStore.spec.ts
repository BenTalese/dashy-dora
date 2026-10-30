// Store-layer coverage — stockItemStore, the richest client store: sorted
// collection cache, optimistic stock-level swap with in-place revert,
// canonical-row refetch, and the FU-511 auto-add toast that reaches across
// into the shopping-list store. (The offline-queue absorption this used to
// cover went with the queue — offline is read-only as of 2026-08-23.)
//
// Mock boundary: the API service class, the shopping-list
// store, and Quasar's Notify. The rollback registry is REAL so the tests can
// prove a level write leaves nothing in it for a later global-handler sweep.
import { createPinia, setActivePinia } from 'pinia';
import type { StockItem } from 'src/models/stockItem';
import {
    clearRollbacks,
    executeRollbacks,
} from 'src/services/errorHandling/rollbackRegistry';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useStockItemStore } from 'src/stores/stockItemStore';
import { useStockLevelStore } from 'src/stores/stockLevelStore';

const m = vi.hoisted(() => ({
    getAllPagesAsync: vi.fn(),
    getAsync: vi.fn(),
    createAsync: vi.fn(),
    updateAsync: vi.fn(),
    deleteAsync: vi.fn(),
    notify: vi.fn(),
    slRefreshAsync: vi.fn(),
    slSummaries: [] as Array<{ shopping_list_id: string; display_name: string }>,
    getLevelsAsync: vi.fn(),
}));

vi.mock('src/services/api/stockLevelApiService', () => ({
    default: class {
        getAllAsync = m.getLevelsAsync;
    },
}));

vi.mock('src/services/api/stockItemApiService', () => ({
    default: class {
        getAllPagesAsync = m.getAllPagesAsync;
        getAsync = m.getAsync;
        createAsync = m.createAsync;
        updateAsync = m.updateAsync;
        deleteAsync = m.deleteAsync;
    },
}));
vi.mock('quasar', () => ({
    Notify: { create: m.notify },
}));
vi.mock('src/stores/shoppingListStore', () => ({
    useShoppingListStore: () => ({
        refreshAsync: m.slRefreshAsync,
        summaries: m.slSummaries,
    }),
}));

function item(id: string, name: string, level = 'LVL-good'): StockItem {
    return {
        stock_item_id: id,
        name,
        stock_group_id: null,
        stock_level_id: level,
        stock_location_id: null,
    };
}

function deferred<T>() {
    let resolve!: (v: T) => void;
    let reject!: (e: unknown) => void;
    const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
    return { promise, resolve, reject };
}

const levelOf = (store: ReturnType<typeof useStockItemStore>, id: string) =>
    store.stockItems.find((si) => si.stock_item_id === id)?.stock_level_id;

beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    clearRollbacks(); // real module-global registry — isolate tests
    m.slSummaries.length = 0;
    m.getAllPagesAsync.mockResolvedValue([]);
    m.updateAsync.mockResolvedValue({});
    m.deleteAsync.mockResolvedValue(undefined);
    m.slRefreshAsync.mockResolvedValue(undefined);
    m.getLevelsAsync.mockResolvedValue({ items: [], total: 0, page: 1, limit: 50 });
});

async function seedStore(items: StockItem[]) {
    m.getAllPagesAsync.mockResolvedValueOnce(items);
    const store = useStockItemStore();
    await store.getStockItemsAsync();
    return store;
}

describe('stockItemStore — collection cache', () => {
    it('sorts the fetched collection case-insensitively by name', async () => {
        const store = await seedStore([
            item('SI-3', 'cherry'), item('SI-1', 'Apple'), item('SI-2', 'banana'),
        ]);

        expect(store.stockItems.map((si) => si.name)).toEqual(['Apple', 'banana', 'cherry']);
    });

    it('ensureLoadedAsync dedupes concurrent callers and no-ops once hydrated', async () => {
        const gate = deferred<StockItem[]>();
        m.getAllPagesAsync.mockReturnValue(gate.promise);
        const store = useStockItemStore();

        const both = Promise.all([store.ensureLoadedAsync(), store.ensureLoadedAsync()]);
        gate.resolve([item('SI-1', 'Apple')]);
        await both;
        await store.ensureLoadedAsync();

        expect(m.getAllPagesAsync).toHaveBeenCalledTimes(1);
    });

    it('ensureLoadedAsync retries after a failed hydration', async () => {
        m.getAllPagesAsync.mockRejectedValueOnce(new Error('offline'));
        const store = useStockItemStore();

        await expect(store.ensureLoadedAsync()).rejects.toThrow('offline');

        m.getAllPagesAsync.mockResolvedValueOnce([item('SI-1', 'Apple')]);
        await store.ensureLoadedAsync();
        expect(store.stockItems).toHaveLength(1);
    });

    it('deleteStockItemAsync removes only the deleted row', async () => {
        const store = await seedStore([item('SI-1', 'Apple'), item('SI-2', 'Banana')]);

        await store.deleteStockItemAsync('SI-1');

        expect(m.deleteAsync).toHaveBeenCalledWith('SI-1');
        expect(store.stockItems.map((si) => si.stock_item_id)).toEqual(['SI-2']);
    });
});

describe('stockItemStore — createStockItemAsync', () => {
    it('inserts a full-DTO create response in sorted position without a refetch', async () => {
        const store = await seedStore([item('SI-1', 'Apple'), item('SI-3', 'Cherry')]);
        m.createAsync.mockResolvedValueOnce(item('SI-2', 'banana'));

        const created = await store.createStockItemAsync({
            name: 'banana', stock_level_id: 'LVL-good', stock_location_id: null,
        });

        expect(created.stock_item_id).toBe('SI-2');
        expect(store.stockItems.map((si) => si.name)).toEqual(['Apple', 'banana', 'Cherry']);
        expect(m.getAsync).not.toHaveBeenCalled();
    });

    it('falls back to a getAsync round-trip when the API returns a bare id', async () => {
        const store = await seedStore([]);
        m.createAsync.mockResolvedValueOnce({ id: 'SI-9' });
        m.getAsync.mockResolvedValueOnce(item('SI-9', 'Zucchini'));

        const created = await store.createStockItemAsync({
            name: 'Zucchini', stock_level_id: 'LVL-good', stock_location_id: null,
        });

        expect(m.getAsync).toHaveBeenCalledWith('SI-9');
        expect(created.name).toBe('Zucchini');
        expect(store.stockItems).toHaveLength(1);
    });
});

describe('stockItemStore — updateStockLevelAsync (optimistic + rollback)', () => {
    it('applies the new level optimistically before the API answers', async () => {
        const store = await seedStore([item('SI-1', 'Apple', 'LVL-good')]);
        const gate = deferred<Record<string, never>>();
        m.updateAsync.mockReturnValueOnce(gate.promise);
        m.getAsync.mockResolvedValueOnce(item('SI-1', 'Apple', 'LVL-low'));

        const inFlight = store.updateStockLevelAsync({
            stock_item_id: 'SI-1', stock_level_id: 'LVL-low',
        });

        expect(levelOf(store, 'SI-1')).toBe('LVL-low'); // before resolve
        gate.resolve({});
        await inFlight;
        expect(levelOf(store, 'SI-1')).toBe('LVL-low');
    });

    it('replaces the row with the canonical server copy after an online success', async () => {
        const store = await seedStore([item('SI-1', 'Apple', 'LVL-good')]);
        m.getAsync.mockResolvedValueOnce({
            ...item('SI-1', 'Apple', 'LVL-low'),
            stock_level_last_updated: '2026-07-11T00:00:00Z',
        });

        await store.updateStockLevelAsync({ stock_item_id: 'SI-1', stock_level_id: 'LVL-low' });

        expect(m.getAsync).toHaveBeenCalledWith('SI-1');
        expect(store.stockItems[0]?.stock_level_last_updated).toBe('2026-07-11T00:00:00Z');
        // Nothing is left in the global rollback registry to revert the
        // committed level on a later, unrelated error.
        executeRollbacks();
        expect(levelOf(store, 'SI-1')).toBe('LVL-low');
    });

    it('moves the derived status fields with the level, and restores them on failure', async () => {
        m.getLevelsAsync.mockResolvedValueOnce({
            items: [
                { stock_level_id: 'LVL-good', name: 'Good', sequence: 0 },
                { stock_level_id: 'LVL-out', name: 'Out', sequence: 2 },
            ],
            total: 2, page: 1, limit: 50,
        });
        await useStockLevelStore().getStockLevelsAsync();
        const store = await seedStore([{
            ...item('SI-1', 'Apple', 'LVL-good'),
            stock_level_sequence: 0, is_out_of_stock: false, is_low_stock: false, needs_restock: false,
        }]);
        const update = deferred<never>();
        m.updateAsync.mockReturnValueOnce(update.promise);

        const pending = store.updateStockLevelAsync({ stock_item_id: 'SI-1', stock_level_id: 'LVL-out' });
        expect(store.stockItems[0]).toMatchObject({
            stock_level_sequence: 2, is_out_of_stock: true, needs_restock: true,
        });

        update.reject(new Error('offline'));
        await expect(pending).rejects.toThrow('offline');
        expect(store.stockItems[0]).toMatchObject({
            stock_level_id: 'LVL-good', stock_level_sequence: 0, is_out_of_stock: false, needs_restock: false,
        });
    });

    it('on API rejection restores the original level itself and rethrows', async () => {
        const store = await seedStore([item('SI-1', 'Apple', 'LVL-good')]);
        m.updateAsync.mockRejectedValueOnce(new Error('422 validation'));

        // Callers like the stocktake runner catch the rejection themselves, so
        // the revert must not depend on the global error handler.
        await expect(
            store.updateStockLevelAsync({ stock_item_id: 'SI-1', stock_level_id: 'LVL-out' }),
        ).rejects.toThrow('422 validation');

        expect(levelOf(store, 'SI-1')).toBe('LVL-good');
    });

    it('restores the right row by id when the cache is re-sorted during the request', async () => {
        const store = await seedStore([item('SI-1', 'Banana', 'LVL-good')]);
        const update = deferred<never>();
        m.updateAsync.mockReturnValueOnce(update.promise);
        m.createAsync.mockResolvedValueOnce(item('SI-0', 'Apple', 'LVL-low'));

        const pending = store.updateStockLevelAsync({ stock_item_id: 'SI-1', stock_level_id: 'LVL-out' });
        await store.createStockItemAsync({ name: 'Apple' } as never); // sorts in at index 0
        update.reject(new Error('offline'));
        await expect(pending).rejects.toThrow('offline');

        expect(levelOf(store, 'SI-0')).toBe('LVL-low');
        expect(levelOf(store, 'SI-1')).toBe('LVL-good');
    });

    it('persists a level write for an id the cache has not loaded, without an optimistic move', async () => {
        // Finalisation 05-R5: the stocktake runner writes before `/stock` has
        // ever been visited. The store is still the one write path — persist
        // and surface the auto-add — there is just no cached row to move.
        const store = await seedStore([item('SI-1', 'Apple')]);

        await store.updateStockLevelAsync({ stock_item_id: 'SI-404', stock_level_id: 'LVL-low' });

        expect(m.updateAsync).toHaveBeenCalledTimes(1);
        expect(m.updateAsync).toHaveBeenCalledWith({ stock_item_id: 'SI-404', stock_level_id: 'LVL-low' });
        expect(store.stockItems.map((s) => s.stock_item_id)).toEqual(['SI-1']);
    });

    it('fires the FU-511 auto-add toast and refreshes the shopping-list store', async () => {
        const store = await seedStore([item('SI-1', 'Apple', 'LVL-good')]);
        m.slSummaries.push({ shopping_list_id: 'SL-1', display_name: 'Groceries' });
        m.updateAsync.mockResolvedValueOnce({
            auto_added: { line_id: 'LN-1', shopping_list_id: 'SL-1' },
        });
        m.getAsync.mockResolvedValueOnce(item('SI-1', 'Apple', 'LVL-low'));

        await store.updateStockLevelAsync({ stock_item_id: 'SI-1', stock_level_id: 'LVL-low' });

        expect(m.slRefreshAsync).toHaveBeenCalledTimes(1);
        expect(m.notify).toHaveBeenCalledWith(expect.objectContaining({
            type: 'positive',
            message: 'Added Apple to Groceries.',
        }));
    });

    it('stays silent (no toast, no cross-store refresh) on the 204 no-trigger path', async () => {
        const store = await seedStore([item('SI-1', 'Apple')]);
        m.getAsync.mockResolvedValueOnce(item('SI-1', 'Apple', 'LVL-low'));

        await store.updateStockLevelAsync({ stock_item_id: 'SI-1', stock_level_id: 'LVL-low' });

        expect(m.notify).not.toHaveBeenCalled();
        expect(m.slRefreshAsync).not.toHaveBeenCalled();
    });
});

describe('stockItemStore — updateStockItemAsync (general PATCH)', () => {
    it('refetches the canonical row and re-sorts when a rename changes order', async () => {
        const store = await seedStore([item('SI-1', 'Apple'), item('SI-2', 'Banana')]);
        m.getAsync.mockResolvedValueOnce(item('SI-1', 'Zucchini'));

        await store.updateStockItemAsync({ stock_item_id: 'SI-1', name: 'Zucchini' });

        expect(store.stockItems.map((si) => si.name)).toEqual(['Banana', 'Zucchini']);
    });

    // Offline is read-only (2026-08-23): a network failure rejects like any
    // other error, so there is no queued-path branch left to cover here. The
    // PATCH-classification test that fed the queue's labels went with it.
    it('passes the whole command through and does not leak the id into a second call', async () => {
        const store = await seedStore([item('SI-1', 'Apple')]);
        m.getAsync.mockResolvedValue(item('SI-1', 'Apple'));

        await store.updateStockItemAsync({ stock_item_id: 'SI-1', expiry_date: '2026-08-01' });

        expect(m.updateAsync).toHaveBeenCalledWith({
            stock_item_id: 'SI-1',
            expiry_date: '2026-08-01',
        });
        expect(m.getAsync).toHaveBeenCalledWith('SI-1');
    });
});
