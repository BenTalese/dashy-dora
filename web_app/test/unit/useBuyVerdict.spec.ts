// @vitest-environment jsdom
/**
 * P8-05 — useBuyVerdict, the per-item verdict fetcher with the coarse
 * module-level cache. Pins the client half of the DORA_VERIFY cache
 * bullets (one request per item per paint; a second consumer inside the
 * 5-minute stale window serves the cache) and the FU-572 invalidation
 * contract (invalidating a LIVE entry refetches immediately so mounted
 * badges repaint in place — a stamp-only reset left them stale until
 * remount).
 *
 * The module holds singleton state (the cache Map), so every test gets a
 * fresh copy via vi.resetModules() + a dynamic import. The API service
 * and the enabled-flag composable are mocked at the module boundary.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type * as ModuleUnderTest from 'src/composables/useBuyVerdict';
import { nextTick, ref, type Ref } from 'vue';

const h = vi.hoisted(() => ({ getAsync: vi.fn() }));
vi.mock('src/services/api/buyVerdictApiService', () => ({
    default: class {
        getAsync = h.getAsync;
    },
}));

let enabled: Ref<boolean>;
vi.mock('src/composables/useBuyVerdictEnabled', () => ({
    useBuyVerdictEnabled: () => ({
        buyVerdictEnabled: enabled,
        buyVerdictLoaded: ref(true),
        refreshBuyVerdict: () => Promise.resolve(),
    }),
}));

type Mod = typeof ModuleUnderTest;

function verdictNamed(label: string) {
    return {
        verdict: 'buy',
        confidence: 'high',
        reasons: [],
        one_tap_action: { kind: 'add_to_list', label },
        data_used: null,
    };
}

function deferred<T>() {
    let resolve!: (v: T) => void;
    let reject!: (e: unknown) => void;
    const promise = new Promise<T>((res, rej) => {
        resolve = res;
        reject = rej;
    });
    return { promise, resolve, reject };
}

const flush = () => new Promise((r) => setTimeout(r, 0));

async function freshModule(): Promise<Mod> {
    vi.resetModules();
    return import('src/composables/useBuyVerdict');
}

describe('useBuyVerdict cache', () => {
    beforeEach(() => {
        h.getAsync.mockReset();
        enabled = ref(true);
        vi.restoreAllMocks();
    });

    it('fetches once per item — concurrent consumers share the inflight request', async () => {
        const mod = await freshModule();
        const v = verdictNamed('first');
        h.getAsync.mockResolvedValue(v);

        const a = mod.useBuyVerdict('id1');
        const b = mod.useBuyVerdict('id1');
        await flush();

        expect(h.getAsync).toHaveBeenCalledTimes(1);
        expect(a.verdict.value).toEqual(v);
        expect(b.verdict.value).toEqual(v);
    });

    it('serves the cache inside the stale window — a later consumer makes no request', async () => {
        const mod = await freshModule();
        h.getAsync.mockResolvedValue(verdictNamed('first'));
        mod.useBuyVerdict('id1');
        await flush();
        expect(h.getAsync).toHaveBeenCalledTimes(1);

        const late = mod.useBuyVerdict('id1');
        await flush();
        expect(h.getAsync).toHaveBeenCalledTimes(1);
        expect(late.verdict.value).toEqual(verdictNamed('first'));
    });

    it('past the 5-minute window a new consumer triggers a background refresh but keeps the old value on screen', async () => {
        const mod = await freshModule();
        const t0 = Date.now();
        const nowSpy = vi.spyOn(Date, 'now').mockReturnValue(t0);
        h.getAsync.mockResolvedValue(verdictNamed('first'));
        const a = mod.useBuyVerdict('id1');
        await flush();
        expect(h.getAsync).toHaveBeenCalledTimes(1);

        nowSpy.mockReturnValue(t0 + 5 * 60_000 + 1);
        const d = deferred<ReturnType<typeof verdictNamed>>();
        h.getAsync.mockReturnValue(d.promise);
        const b = mod.useBuyVerdict('id1');
        expect(h.getAsync).toHaveBeenCalledTimes(2);
        // Stale-but-usable: the old verdict stays visible while the fetch runs.
        expect(b.verdict.value).toEqual(verdictNamed('first'));

        d.resolve(verdictNamed('second'));
        await flush();
        expect(a.verdict.value).toEqual(verdictNamed('second'));
        expect(b.verdict.value).toEqual(verdictNamed('second'));
    });

    it('invalidating a LIVE entry refetches immediately so mounted consumers repaint (FU-572)', async () => {
        const mod = await freshModule();
        h.getAsync.mockResolvedValue(verdictNamed('first'));
        const a = mod.useBuyVerdict('id1');
        await flush();

        h.getAsync.mockResolvedValue(verdictNamed('second'));
        mod.invalidateBuyVerdict('id1');
        expect(h.getAsync).toHaveBeenCalledTimes(2);
        await flush();
        expect(a.verdict.value).toEqual(verdictNamed('second'));
    });

    it('a failed fetch parks the verdict as null with the error captured; invalidating it stays lazy', async () => {
        const mod = await freshModule();
        h.getAsync.mockRejectedValue(new Error('server hiccup'));
        const a = mod.useBuyVerdict('id1');
        await flush();
        expect(a.verdict.value).toBeNull();
        expect(a.error.value).toBe('server hiccup');
        expect(a.loading.value).toBe(false);

        // No live value → invalidation must NOT fire an eager request
        // (nothing is on screen to repaint)…
        h.getAsync.mockResolvedValue(verdictNamed('recovered'));
        mod.invalidateBuyVerdict('id1');
        expect(h.getAsync).toHaveBeenCalledTimes(1);

        // …but the next consumer refetches and recovers.
        const b = mod.useBuyVerdict('id1');
        await flush();
        expect(h.getAsync).toHaveBeenCalledTimes(2);
        expect(b.verdict.value).toEqual(verdictNamed('recovered'));
    });

    it('never fetches while the install-wide flag is off; flipping it on fetches', async () => {
        const mod = await freshModule();
        enabled.value = false;
        h.getAsync.mockResolvedValue(verdictNamed('first'));
        const a = mod.useBuyVerdict('id1');
        await flush();
        expect(h.getAsync).not.toHaveBeenCalled();

        enabled.value = true;
        await nextTick();
        await flush();
        expect(h.getAsync).toHaveBeenCalledTimes(1);
        expect(a.verdict.value).toEqual(verdictNamed('first'));
    });

    it('hides an already-fetched verdict when the flag goes off', async () => {
        // The cache outlives a flag flip, so gating only `fetchIfNeeded` left
        // verdicts painted after an admin turned money off (or the user hid
        // the surface) until the consumer remounted. The read is gated too.
        const mod = await freshModule();
        h.getAsync.mockResolvedValue(verdictNamed('first'));
        const a = mod.useBuyVerdict('id1');
        await flush();
        expect(a.verdict.value).toEqual(verdictNamed('first'));

        enabled.value = false;
        await nextTick();
        expect(a.verdict.value).toBeNull();

        // …and comes straight back from cache, without a refetch.
        enabled.value = true;
        await nextTick();
        await flush();
        expect(a.verdict.value).toEqual(verdictNamed('first'));
        expect(h.getAsync).toHaveBeenCalledTimes(1);
    });

    it('clearBuyVerdictCache drops everything — the next consumer refetches', async () => {
        const mod = await freshModule();
        h.getAsync.mockResolvedValue(verdictNamed('first'));
        mod.useBuyVerdict('id1');
        await flush();
        expect(h.getAsync).toHaveBeenCalledTimes(1);

        mod.clearBuyVerdictCache();
        mod.useBuyVerdict('id1');
        await flush();
        expect(h.getAsync).toHaveBeenCalledTimes(2);
    });
});
