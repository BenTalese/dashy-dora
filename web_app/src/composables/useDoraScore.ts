import { ref, type Ref } from 'vue';
import DashboardApiService from 'src/services/api/dashboardApiService';
import type { DoraScore } from 'src/models/doraScore';

/** P8-08 — module-level cache for the dashboard's Dora Score card.
 *  There's only ever one score, so a shared singleton is the right shape
 *  (no per-key Map). The card mounts and reads the cached value; a mount
 *  after STALE_AFTER_MS refetches, and the page calls `refresh` when it
 *  reloads its cards. STALE_AFTER_MS matches useBuyVerdict. */

const api = new DashboardApiService();

const value = ref<DoraScore | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);
let fetchedAt = 0;
let inflight: Promise<void> | null = null;

const STALE_AFTER_MS = 5 * 60_000;

function refresh(): Promise<void> {
    if (inflight) return inflight;
    loading.value = true;
    error.value = null;
    const p = api.getDoraScoreAsync()
        .then((dto) => {
            value.value = dto;
            fetchedAt = Date.now();
        })
        .catch((err: unknown) => {
            // The card v-ifs itself away on error — a 500 shouldn't
            // block the rest of the dashboard from rendering.
            error.value = err instanceof Error ? err.message : String(err);
            value.value = null;
        })
        .finally(() => {
            loading.value = false;
            inflight = null;
        });
    inflight = p;
    return p;
}

export function useDoraScore(): {
    doraScore: Ref<DoraScore | null>;
    loading: Ref<boolean>;
    error: Ref<string | null>;
    refresh: () => Promise<void>;
} {
    const isStale = Date.now() - fetchedAt > STALE_AFTER_MS;
    if (!value.value && !inflight) {
        void refresh();
    } else if (isStale && !inflight) {
        void refresh();
    }
    return {
        doraScore: value,
        loading,
        error,
        refresh,
    };
}
