import { computed } from 'vue';
import StockItemApiService from 'src/services/api/stockItemApiService';
import { createOverlayCache } from 'src/composables/createOverlayCache';

// The Zero-Input Pantry beliefs. Additive: the belief is an overlay beside the
// recorded level, never a replacement. Gated server-side on the per-user
// `inferred_pantry_enabled` pref — when off, the endpoint answers
// `enabled: false` and no chip renders.

const stockItemApi = new StockItemApiService();

const cache = createOverlayCache({
    fetch: () => stockItemApi.getPantryBeliefsAsync(),
    entries: (r) => r.beliefs,
    enabled: (r) => r.enabled,
});

export function usePantryBeliefs() {
    return {
        enabled: computed(() => cache.isEnabled()),
        loaded: cache.loaded,
        loadAsync: cache.loadAsync,
        beliefFor: cache.entryFor,
        invalidate: cache.invalidate,
    };
}
