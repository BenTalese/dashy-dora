// C-cross Chunk 1 — install-wide feature flags.
//
// Reads `/api/health` once per session and exposes the `features.*`
// dictionary as reactive booleans. Every consumer reads through this
// composable — never a parallel store, never a direct AppSetting fetch
// (ADR-002 pattern: one composable per feature *family*, not per flag).
//
// `refresh()` re-probes; call it from the admin Features panel after a
// successful PATCH so the cached answer doesn't drift from the row.

import { computed, ref } from 'vue';
import HealthApiService, { invalidateHealthInfo } from 'src/services/api/healthApiService';

// Mostly booleans, but `nutrition_mode` publishes a three-state string
// (2026-08-14) — the install's nutrition depth is a mode, not a flag, and
// forcing it through a bool is what produced the old two-switch mess.
// `readFlag` coerces, so boolean call sites are unaffected.
type FeatureFlagMap = Record<string, boolean | string>;

const flagsRaw = ref<FeatureFlagMap>({});
const loaded = ref(false);
let inflight: Promise<void> | null = null;

function load(): Promise<void> {
    if (!inflight) {
        inflight = new HealthApiService()
            .getInfoAsync()
            .then((info) => {
                flagsRaw.value = { ...info.features };
            })
            .catch(() => {
                // Network failure → leave the previous map intact (likely
                // empty on first call); consumers will see every flag as
                // false until the next refresh succeeds. Intentionally a
                // no-op — we keep whatever flags we already had.
            })
            .finally(() => {
                loaded.value = true;
            });
    }
    return inflight;
}

function readFlag(name: string): boolean {
    return !!flagsRaw.value[name];
}

/** For the rare flag whose server-side default is ON. `readFlag` can't serve
 *  those: the map is empty until the probe resolves, so a default-on surface
 *  would blink out of existence on every page load and stay hidden if the
 *  probe ever failed. Absent key ⇒ true; present key ⇒ whatever it says. */
function readFlagDefaultOn(name: string): boolean {
    const raw = flagsRaw.value[name];
    return raw === undefined ? true : !!raw;
}

export function useFeatureFlags() {
    void load();
    function refresh(): Promise<void> {
        loaded.value = false;
        inflight = null;
        invalidateHealthInfo();
        return load();
    }
    return {
        flagsLoaded: loaded,
        // Named-flag computeds keep call sites concise + type-safe at the
        // read site without exposing the raw map shape. Add more as new
        // flags ship — keys here mirror the backend `_feature_flags()` map.
        auth: computed(() => readFlag('auth')),
        audit: computed(() => readFlag('audit')),
        scanning: computed(() => readFlag('scanning')),
        // 2026-08-20 — install-wide stocktake master switch. Unlike most
        // flags here this one defaults ON server-side, so a failed probe (or
        // the moment before the probe lands) leaves the surface visible
        // rather than blinking a feature the household uses in and out.
        stocktake: computed(() => readFlagDefaultOn('stocktake')),
        multiUser: computed(() => readFlag('multi_user')),
        email: computed(() => readFlag('email')),
        // No `assistant` flag — AI mode has no install-wide gate (per-user
        // opt-in only), so there's nothing for the server to publish.
        money: computed(() => readFlag('money')),
        nutrition: computed(() => readFlag('nutrition')),
        // True when the admin has set an SMTP username (Settings → Email).
        // Consumed by NotificationsSettings (the settings screen that owns
        // the per-user email opt-in — R-029 carve-out; the disabled toggle
        // legitimately renders there and only there). Any other surface
        // that references an email affordance should `v-if` on this flag,
        // not `:disable`.
        emailSmtpConfigured: computed(() => readFlag('email_smtp_configured')),
        // True iff DORA_SECRET_ENCRYPTION_KEY is set on the backend. Consumed
        // by EncryptionKeyBanner (per-user Assistant page + admin Email/Push
        // pages) to warn — and offer to generate a key — when secrets can't
        // be stored encrypted. Read by every user, not just admins.
        secretEncryptionConfigured: computed(() => readFlag('secret_encryption_configured')),
        // True when both VAPID keys are set (Settings → Push). Consumed by NotificationsSettings (same R-029 carve-out
        // as emailSmtpConfigured) and short-circuits `usePushSubscription`
        // before it tries to fetch the public key.
        pushVapidConfigured: computed(() => readFlag('push_vapid_configured')),
        // Onboarding C-5.3 — products feature (linked products, price history,
        // ingestion). Per-surface gating when off is FU-182.
        products: computed(() => readFlag('products')),
        // Nutrition depth, install-wide (2026-08-14). `nutrition` above stays
        // the plain "on at all" gate most surfaces want; this carries the
        // depth for the ones that differ between simple and complex.
        nutritionMode: computed<'off' | 'simple' | 'complex'>(() => {
            const raw = flagsRaw.value['nutrition_mode'];
            return raw === 'simple' || raw === 'complex' ? raw : 'off';
        }),
        // Complex is selected AND at least one source can actually answer
        // (a dataset is imported / a key is set / OFF is permitted). Derived
        // server-side from installed reality — see features/nutrition/sources.py.
        nutritionComplexUsable: computed(() => readFlag('nutrition_complex_usable')),
        // Owner ask 2026-08-27 — which front-of-pack rating recipes carry:
        // 'none' | 'health_star' | 'nutri_score'. 'none' everywhere by
        // default. Neither scheme is a universal fact about food, so Dora
        // doesn't pick a nutritional authority for a household at install
        // time; Settings → Region's "Match this device" offers the locally
        // recognised one, and the picker takes any of them anywhere.
        //
        // The scheme string, not a bool: the client renders a different badge
        // per scheme, and which-scheme is the server's answer (R-003).
        nutritionRatingScheme: computed(() => {
            const raw = flagsRaw.value['nutrition_rating_scheme'];
            return raw === 'health_star' || raw === 'nutri_score' ? raw : 'none';
        }),
        refresh,
    };
}
