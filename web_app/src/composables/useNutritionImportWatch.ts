import { computed, shallowRef } from 'vue';
import NutritionApiService, {
    type NutritionSourceStatus,
    type NutritionSourcesResponse,
} from 'src/services/api/nutritionApiService';
import { useNutritionSettingsSync } from 'src/composables/useNutritionSettingsSync';

/**
 * Watches a running nutrition dataset import to completion, independent of
 * whichever page started it (FU-771). The poll used to live in the admin
 * nutrition page and died with it on unmount, so an import that finished after
 * the admin navigated away never refreshed the flags or the recipe list.
 *
 * State is module-level on purpose: one poll per session, however many times
 * the page mounts. It runs only while a dataset source reports a busy phase and
 * stops on the first idle answer (firing the sync once), or after a run of
 * failed reads so a dead server isn't polled for the rest of the session.
 */

const POLL_MS = 2500;
const MAX_CONSECUTIVE_FAILURES = 5;

const nutritionApi = new NutritionApiService();
const latest = shallowRef<NutritionSourcesResponse | null>(null);
// One poll at a time: a timeout re-armed only after the previous read lands,
// so a slow server can't stack reads (and fire the sync twice), and a late
// answer can't overwrite a newer one. `generation` retires any read still in
// flight when the poll is stopped or reset (sign-out).
let pollTimer: ReturnType<typeof setTimeout> | null = null;
let polling = false;
let generation = 0;
let failures = 0;

export function isImportBusy(source: NutritionSourceStatus): boolean {
    return ['downloading', 'parsing', 'saving'].includes(source.phase ?? '');
}

function anyDatasetBusy(res: NutritionSourcesResponse): boolean {
    return res.sources.some((s) => s.kind === 'dataset' && isImportBusy(s));
}

function stopPolling(): void {
    polling = false;
    generation += 1;
    if (pollTimer !== null) {
        clearTimeout(pollTimer);
        pollTimer = null;
    }
}

function schedule(gen: number): void {
    pollTimer = setTimeout(() => {
        pollTimer = null;
        void tick(gen);
    }, POLL_MS);
}

async function tick(gen: number): Promise<void> {
    try {
        const res = await nutritionApi.getSourcesAsync();
        if (gen !== generation) return;
        failures = 0;
        latest.value = res;
        if (!anyDatasetBusy(res)) {
            stopPolling();
            // An import just finished: every recipe's rollup can move.
            await useNutritionSettingsSync().syncAfterNutritionChange();
            return;
        }
    } catch {
        if (gen !== generation) return;
        // Silent: the page that started this may be long gone, so there is
        // nobody to toast. Give up after a run of failures rather than poll a
        // dead server forever; the next page visit re-arms it if still busy.
        failures += 1;
        if (failures >= MAX_CONSECUTIVE_FAILURES) {
            stopPolling();
            return;
        }
    }
    schedule(gen);
}

/** Start watching if a dataset import is in flight. Safe to call repeatedly;
 *  only one poll ever runs. Pass the response you already hold so the page's
 *  own read seeds `latest` without a second request. */
function watchIfBusy(res: NutritionSourcesResponse): void {
    latest.value = res;
    if (polling || !anyDatasetBusy(res)) return;
    polling = true;
    failures = 0;
    schedule(generation);
}

export function useNutritionImportWatch() {
    return {
        /** The most recent sources answer, from the page or the poll. */
        latest: computed(() => latest.value),
        watchIfBusy,
    };
}

/** Drop the poll and the last answer. Sign-out calls it (a soft navigation,
 *  so module state would otherwise outlive the session and 401 on every
 *  tick); specs call it between tests. */
export function resetNutritionImportWatch(): void {
    stopPolling();
    latest.value = null;
    failures = 0;
}
