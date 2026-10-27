import { describe, expect, it, vi } from 'vitest';

import { createOverlayCache } from 'src/composables/createOverlayCache';

type Result = { enabled: boolean; map: Record<string, number> };

function cacheOver(fetch: () => Promise<Result>) {
    return createOverlayCache({ fetch, entries: (r: Result) => r.map, enabled: (r: Result) => r.enabled });
}

describe('createOverlayCache', () => {
    it('fetches once, then serves entries until invalidated', async () => {
        const fetch = vi.fn(async () => ({ enabled: true, map: { a: 1 } }));
        const cache = cacheOver(fetch);
        await cache.loadAsync();
        await cache.loadAsync();
        expect(fetch).toHaveBeenCalledTimes(1);
        expect(cache.entryFor('a')).toBe(1);
        expect(cache.entryFor('b')).toBeNull();
        cache.invalidate();
        await cache.loadAsync();
        expect(fetch).toHaveBeenCalledTimes(2);
    });

    it('serves nothing when the overlay is off for the user', async () => {
        const cache = cacheOver(async () => ({ enabled: false, map: { a: 1 } }));
        await cache.loadAsync();
        expect(cache.isEnabled()).toBe(false);
        expect(cache.entryFor('a')).toBeNull();
    });

    it('treats a failed load as no overlay', async () => {
        const cache = cacheOver(async () => { throw new Error('offline'); });
        await cache.loadAsync();
        expect(cache.entryFor('a')).toBeNull();
        expect(cache.loaded.value).toBe(false);
    });
});
