import { computed } from 'vue';
import StockItemApiService from 'src/services/api/stockItemApiService';
import { createOverlayCache } from 'src/composables/createOverlayCache';

// The planned-demand overlay. Not a preference: unlike the belief, planned
// demand is a plain fact about the user's own plan, so nothing gates it
// (meal planning is core since 2026-09-03). Invalidate after a plan edit, a
// cook, or a level change (which can move the urgency grade).

const stockItemApi = new StockItemApiService();

const cache = createOverlayCache({
    fetch: () => stockItemApi.getPlannedDemandAsync(),
    entries: (r) => r.demand,
});

export function usePlannedDemand() {
    return {
        horizonDays: computed(() => cache.result.value?.horizon_days ?? 0),
        loaded: cache.loaded,
        loadAsync: cache.loadAsync,
        demandFor: cache.entryFor,
        invalidate: cache.invalidate,
    };
}
