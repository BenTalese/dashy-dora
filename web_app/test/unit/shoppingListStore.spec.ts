// Store-layer coverage — shoppingListStore, the shared cache behind every
// cart affordance (AddToListButton reads `membership` from here) and the
// list rail. What matters behaviourally:
//   * the quick-add-target derivation (server-inferred id → local summary),
//   * refresh error handling (all-or-nothing assignment, flags reset),
//   * the R-016 lazy-hydration contract (dedupe concurrent callers, don't
//     refetch once hydrated, DO retry after a failed hydration).
//
// Mocking sits at the API-service module boundary (same pattern as
// addToListButton.spec.ts); the store logic runs for real on a fresh Pinia
// per test. Runs in plain node — no DOM.
import { createPinia, setActivePinia } from 'pinia';
import type { Membership, ShoppingListSummary } from 'src/models/shoppingList';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useShoppingListStore } from 'src/stores/shoppingListStore';

const m = vi.hoisted(() => ({
    getAllAsync: vi.fn(),
    getMembershipAsync: vi.fn(),
}));

vi.mock('src/services/api/shoppingListApiService', () => ({
    default: class {
        getAllAsync = m.getAllAsync;
        getMembershipAsync = m.getMembershipAsync;
    },
}));

function summary(id: string, name: string): ShoppingListSummary {
    return {
        shopping_list_id: id,
        name: null,
        display_name: name,
        status: 'draft',
        created_at: '2026-07-01T00:00:00Z',
        completed_at: null,
        planned_shop_date: null,
        effective_date: '2026-07-01',
        is_next_up: false,
        line_count: 0,
        ticked_count: 0,
    };
}

function membership(targetId: string | null): Membership {
    return {
        quick_add_target_list_id: targetId,
        items: [],
        active_lists: [],
    };
}

/** A promise the test resolves by hand, to observe in-flight state. */
function deferred<T>() {
    let resolve!: (v: T) => void;
    let reject!: (e: unknown) => void;
    const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
    return { promise, resolve, reject };
}

beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    m.getAllAsync.mockResolvedValue([]);
    m.getMembershipAsync.mockResolvedValue(membership(null));
});

describe('shoppingListStore — quick-add-target derivation', () => {
    it('is null-safe before any membership has loaded', () => {
        const store = useShoppingListStore();

        expect(store.quickAddTargetListId).toBeNull();
        expect(store.quickAddTargetSummary).toBeNull();
    });

    it('resolves the server-inferred target id to its local summary', async () => {
        m.getAllAsync.mockResolvedValue([summary('L1', 'Groceries'), summary('L2', 'Bulk run')]);
        m.getMembershipAsync.mockResolvedValue(membership('L2'));
        const store = useShoppingListStore();

        await store.refreshAsync();

        expect(store.quickAddTargetListId).toBe('L2');
        expect(store.quickAddTargetSummary?.display_name).toBe('Bulk run');
    });

    it('returns a null summary (not a crash) when the target id has no matching summary', async () => {
        // Stale-cache shape: membership names a list the summaries payload
        // doesn't contain (e.g. deleted between the two responses).
        m.getAllAsync.mockResolvedValue([summary('L1', 'Groceries')]);
        m.getMembershipAsync.mockResolvedValue(membership('L-gone'));
        const store = useShoppingListStore();

        await store.refreshAsync();

        expect(store.quickAddTargetListId).toBe('L-gone');
        expect(store.quickAddTargetSummary).toBeNull();
    });
});

describe('shoppingListStore — refreshAsync', () => {
    it('populates summaries + membership and resets the loading flag', async () => {
        m.getAllAsync.mockResolvedValue([summary('L1', 'Groceries')]);
        m.getMembershipAsync.mockResolvedValue(membership('L1'));
        const store = useShoppingListStore();

        const inFlight = store.refreshAsync();
        expect(store.loading).toBe(true);
        await inFlight;

        expect(store.summaries).toHaveLength(1);
        expect(store.membership?.quick_add_target_list_id).toBe('L1');
        expect(store.loading).toBe(false);
        expect(store.loadError).toBeNull();
    });

    it('on failure: keeps prior data all-or-nothing, sets loadError, resets loading', async () => {
        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
        const store = useShoppingListStore();
        m.getAllAsync.mockResolvedValue([summary('L1', 'Groceries')]);
        await store.refreshAsync();

        // Second refresh: membership fails while summaries would succeed —
        // Promise.all means NEITHER half is applied (no torn state).
        m.getAllAsync.mockResolvedValue([summary('L2', 'Torn write')]);
        m.getMembershipAsync.mockRejectedValue(new Error('boom'));
        await store.refreshAsync();

        expect(store.summaries[0]?.shopping_list_id).toBe('L1');
        expect(store.loadError).toBe('boom');
        expect(store.loading).toBe(false);
        expect(consoleSpy).toHaveBeenCalled();
        consoleSpy.mockRestore();
    });

    it('stringifies non-Error rejections into loadError', async () => {
        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
        m.getAllAsync.mockRejectedValue('plain string failure');
        const store = useShoppingListStore();

        await store.refreshAsync();

        expect(store.loadError).toBe('plain string failure');
        consoleSpy.mockRestore();
    });
});

describe('shoppingListStore — ensureLoadedAsync (R-016 lazy hydration)', () => {
    it('dedupes concurrent callers into a single fetch', async () => {
        const gate = deferred<ShoppingListSummary[]>();
        m.getAllAsync.mockReturnValue(gate.promise);
        const store = useShoppingListStore();

        const first = store.ensureLoadedAsync();
        const second = store.ensureLoadedAsync();
        gate.resolve([summary('L1', 'Groceries')]);
        await Promise.all([first, second]);

        expect(m.getAllAsync).toHaveBeenCalledTimes(1);
        expect(m.getMembershipAsync).toHaveBeenCalledTimes(1);
    });

    it('is a no-op once hydrated', async () => {
        const store = useShoppingListStore();
        await store.ensureLoadedAsync();
        await store.ensureLoadedAsync();

        expect(m.getAllAsync).toHaveBeenCalledTimes(1);
    });

    it('retries after a failed hydration instead of caching the failure', async () => {
        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
        m.getAllAsync.mockRejectedValueOnce(new Error('offline'));
        const store = useShoppingListStore();

        // refreshAsync absorbs the error, so this resolves — but hydrated
        // must stay false so the next mount actually fetches.
        await expect(store.ensureLoadedAsync()).resolves.toBeUndefined();
        m.getAllAsync.mockResolvedValue([summary('L1', 'Groceries')]);
        await store.ensureLoadedAsync();

        expect(m.getAllAsync).toHaveBeenCalledTimes(2);
        expect(store.summaries).toHaveLength(1);
        consoleSpy.mockRestore();
    });

    it('explicit refreshAsync still refetches after hydration (post-mutation path)', async () => {
        const store = useShoppingListStore();
        await store.ensureLoadedAsync();

        await store.refreshAsync();

        expect(m.getAllAsync).toHaveBeenCalledTimes(2);
    });

    it('joins a refresh already in flight instead of returning before it lands', async () => {
        const list = deferred<ShoppingListSummary[]>();
        m.getAllAsync.mockReturnValueOnce(list.promise);
        const store = useShoppingListStore();

        const refresh = store.refreshAsync();
        const ensure = store.ensureLoadedAsync();
        list.resolve([summary('L1', 'Groceries')]);
        await ensure;

        expect(store.summaries).toHaveLength(1);
        expect(m.getAllAsync).toHaveBeenCalledTimes(1);
        await refresh;
    });
});

describe('shoppingListStore — overlapping refreshes', () => {
    it('applies only the latest request, and an earlier caller waits for it', async () => {
        const older = deferred<ShoppingListSummary[]>();
        m.getAllAsync.mockReturnValueOnce(older.promise);
        m.getAllAsync.mockResolvedValueOnce([summary('L2', 'Newer')]);
        const store = useShoppingListStore();

        const first = store.refreshAsync();
        await store.refreshAsync();
        older.resolve([summary('L1', 'Older')]);
        await first;

        expect(store.summaries.map((s) => s.shopping_list_id)).toEqual(['L2']);
        expect(store.loading).toBe(false);
    });

    it('exposes the server-flagged next-up list', async () => {
        m.getAllAsync.mockResolvedValue([summary('L1', 'A'), { ...summary('L2', 'B'), is_next_up: true }]);
        const store = useShoppingListStore();
        expect(store.nextUpSummary).toBeNull();

        await store.refreshAsync();

        expect(store.nextUpSummary?.shopping_list_id).toBe('L2');
    });
});
