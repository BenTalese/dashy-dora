// Phase D / FU-186 — admin-set URL the Product Search nav opens.
//
// Lives in the small composable shape established by `useFeatureFlags`
// (ADR-002): one composable per concern, never a parallel store. Reads
// `/api/health` (`products_policy`) once per session, because members can't
// read the admin-only `/app-settings` (R-038); `refresh()` re-reads after the
// admin saves a change.

import { computed, ref } from 'vue';
import type { Router } from 'vue-router';
import HealthApiService, { invalidateHealthInfo } from 'src/services/api/healthApiService';

// Admin page that owns the Product Search URL row — the Product data
// ingestion page since 2026-09-03, where the URL now sits beside the ingestion
// switch it pairs with. Used as the fallback destination for the non-nav
// "Product Search" CTAs (find-&-link, dashboard "hunt for deals", Dora
// quick-actions) when no URL is configured yet, so those stay actionable for an
// admin instead of dead-ending on the retired `/product-search` route. The
// main-nav entry no longer uses this — it simply hides when no URL is set
// (see MainLayout).
export const PRODUCT_SEARCH_SETTINGS_PATH = '/settings/admin/system/ingestion';

const url = ref<string>('');
const loaded = ref(false);
let inflight: Promise<void> | null = null;

function load(): Promise<void> {
    if (!inflight) {
        inflight = new HealthApiService()
            .getInfoAsync()
            .then((info) => {
                url.value = info.products_policy?.search_url ?? '';
            })
            .catch(() => {
                // Unreachable — leave the URL empty; the nav entry stays hidden.
            })
            .finally(() => {
                loaded.value = true;
            });
    }
    return inflight;
}

export function useProductSearchUrl() {
    void load();
    const configured = computed(() => url.value.trim().length > 0);
    function refresh(): Promise<void> {
        loaded.value = false;
        inflight = null;
        invalidateHealthInfo();
        return load();
    }
    return {
        url,
        loaded,
        configured,
        refresh,
    };
}

// Single destination resolver for every in-app "Product Search" entry point
// (nav strip + the empty-state / find-&-link CTAs). FU-186 removed the in-app
// `/product-search` route: a configured URL opens the external companion in a
// new tab; when unset we route to the admin Products page so the setup path is
// discoverable rather than a 404 (owner call, FU-581). The old `q` /
// `stock_item_id` seeding is dropped — nothing consumes it any more.
export function openProductSearch(router: Router): void {
    const target = url.value.trim();
    if (target) {
        window.open(target, '_blank', 'noopener,noreferrer');
    } else {
        void router.push(PRODUCT_SEARCH_SETTINGS_PATH);
    }
}
