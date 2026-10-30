import { readonly, ref, type Ref } from 'vue';

/**
 * A module-level cache for a per-stock-item overlay (the pantry belief, the
 * planned demand): one fetch shared by the overview's rows and the detail
 * page, invalidated by the store's level write path (finalisation 07-R6; the
 * two overlays were copies of one 58-line module). A failed load is non-fatal:
 * the overlay just doesn't render, and the recorded level is unaffected.
 */
export function createOverlayCache<R, T>(options: {
    fetch: () => Promise<R>;
    entries: (result: R) => Record<string, T> | undefined;
    /** Whether the overlay is on for this user; always on when omitted. */
    enabled?: (result: R) => boolean;
}) {
    const result = ref<R | null>(null) as Ref<R | null>;
    const loaded = ref(false);
    const loading = ref(false);

    // Bumped by `clear()`. A load started before sign-out can resolve after
    // it; the generation check drops that response instead of writing the
    // previous user's overlay back with `loaded = true`.
    let generation = 0;

    async function loadAsync(force = false): Promise<void> {
        if (loading.value) return;
        if (loaded.value && !force) return;
        const gen = generation;
        loading.value = true;
        try {
            const fetched = await options.fetch();
            if (gen !== generation) return;
            result.value = fetched;
            loaded.value = true;
        } catch {
            if (gen !== generation) return;
            result.value = null;
        } finally {
            // `clear()` already reset `loading`; a newer load may own it now.
            if (gen === generation) loading.value = false;
        }
    }

    function isEnabled(): boolean {
        if (result.value === null) return false;
        return options.enabled ? options.enabled(result.value) : true;
    }

    function entryFor(stockItemId: string): T | null {
        if (result.value === null || !isEnabled()) return null;
        return options.entries(result.value)?.[stockItemId] ?? null;
    }

    /** The next `loadAsync` refetches. */
    function invalidate(): void {
        loaded.value = false;
    }

    /** Drop the loaded result too — on sign-out it belongs to someone else. */
    function clear(): void {
        generation++;
        result.value = null;
        loaded.value = false;
        loading.value = false;
    }

    return {
        result: readonly(result), loaded: readonly(loaded),
        isEnabled, loadAsync, entryFor, invalidate, clear,
    };
}
