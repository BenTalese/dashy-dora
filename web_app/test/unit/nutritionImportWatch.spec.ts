// FU-771 — the dataset-import poll outlives the admin page that started it.
// Contracts pinned: it only polls while a dataset source is busy, it fires the
// flags + recipe-list sync exactly once when the import goes idle, and it gives
// up after repeated failed reads instead of polling forever.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { NutritionSourcesResponse } from 'src/services/api/nutritionApiService';

const m = vi.hoisted(() => ({
    getSourcesAsync: vi.fn(),
    sync: vi.fn(),
}));

vi.mock('src/services/api/nutritionApiService', () => ({
    default: class {
        getSourcesAsync = m.getSourcesAsync;
    },
}));
vi.mock('src/composables/useNutritionSettingsSync', () => ({
    useNutritionSettingsSync: () => ({ syncAfterNutritionChange: m.sync }),
}));

import {
    resetNutritionImportWatch,
    useNutritionImportWatch,
} from 'src/composables/useNutritionImportWatch';

function res(phase: 'idle' | 'downloading'): NutritionSourcesResponse {
    return {
        mode: 'complex',
        any_available: true,
        sources: [
            { id: 'ausnut', label: 'AUSNUT', kind: 'dataset', available: true, food_count: 1, phase },
        ],
    };
}

describe('useNutritionImportWatch', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        m.getSourcesAsync.mockReset();
        m.sync.mockReset();
    });
    afterEach(() => {
        resetNutritionImportWatch();
        vi.useRealTimers();
    });

    it('does not poll when nothing is busy', async () => {
        useNutritionImportWatch().watchIfBusy(res('idle'));
        await vi.advanceTimersByTimeAsync(10_000);
        expect(m.getSourcesAsync).not.toHaveBeenCalled();
        expect(m.sync).not.toHaveBeenCalled();
    });

    it('syncs once when the import goes idle, then stops', async () => {
        m.getSourcesAsync
            .mockResolvedValueOnce(res('downloading'))
            .mockResolvedValue(res('idle'));
        const watch = useNutritionImportWatch();
        watch.watchIfBusy(res('downloading'));
        watch.watchIfBusy(res('downloading')); // second caller must not double the poll
        await vi.advanceTimersByTimeAsync(2500);
        expect(m.sync).not.toHaveBeenCalled();
        await vi.advanceTimersByTimeAsync(2500);
        expect(m.sync).toHaveBeenCalledTimes(1);
        expect(watch.latest.value?.sources[0]?.phase).toBe('idle');
        await vi.advanceTimersByTimeAsync(10_000);
        expect(m.getSourcesAsync).toHaveBeenCalledTimes(2);
    });

    it('gives up after repeated failed reads', async () => {
        m.getSourcesAsync.mockRejectedValue(new Error('down'));
        useNutritionImportWatch().watchIfBusy(res('downloading'));
        await vi.advanceTimersByTimeAsync(60_000);
        expect(m.getSourcesAsync).toHaveBeenCalledTimes(5);
        expect(m.sync).not.toHaveBeenCalled();
    });
});
