import AxiosHttpClient from './axiosHttpClient';

/** Shape of GET /api/health from dora_api. Mobile + desktop clients
 *  use this to detect incompatible backend versions and to gate
 *  feature-specific UI on what the backend has enabled. Adding new
 *  fields is fine; removing fields is a breaking change for clients
 *  built against older shapes. */
export interface HealthInfo {
    ok: boolean;
    version: string;
    schema_version: string | null;
    profile: string;
    features: {
        auth: boolean;
        audit: boolean;
        scanning: boolean;
        multi_user: boolean;
        email: boolean;
        // True iff DORA_SECRET_ENCRYPTION_KEY is set on the backend.
        secret_encryption_configured: boolean;
        // Two string-valued "flags" ride in the same map (finalisation 13-R16):
        // the nutrition depth and the rating scheme the install shows.
        nutrition_mode?: string;
        nutrition_rating_scheme?: string;
        // Open shape — later additions like `reports`, `substitutes`
        // can land without breaking existing clients.
        [key: string]: boolean | string;
    };
    /** Alembic head the running DB is at (null when unreadable); compare
     *  against `schema_version` to spot an un-migrated DB. */
    schema_version_db?: string | null;
    // install-wide image compression knobs the client applies
    // at upload time. Optional in the type because older backends won't
    // emit it; callers default to 85 / 1920.
    image_policy?: {
        quality: number;         // 30–100
        max_dimension: number;   // longest edge in px
    };
    // install-wide currency (ISO 4217) + display locale (BCP-47)
    // for money rendering. Optional in the type because older backends
    // won't emit it; callers default to Dora's AU shipping values.
    locale_policy?: {
        currency: string;        // ISO 4217, e.g. 'AUD'
        locale: string;          // BCP-47, e.g. 'en-AU'
        // which units every dropdown in the app offers:
        // 'metric' | 'imperial' | 'us'. Rides with currency/locale because
        // it is the same kind of fact — an install-wide regional convention
        // every session needs on boot, not just admins. Optional in the type
        // because older backends won't emit it; callers default to metric.
        measurement_system?: string;
        // the household's IANA timezone (`AppSetting.timezone`), e.g.
        // 'Australia/Sydney'. Drives the client's display-only "today" and
        // datetime renders (R-021 / D-006). Optional in the type because older
        // backends won't emit it; callers fall back to the device clock.
        timezone?: string;
    };
    // FU-615 — install-wide household cooking config (moved off User).
    // Every client reads it here: cook mode seeds its serving scaler from
    // `household_headcount`, and the meal-planner reveals the cook pool when
    // `batch_features_enabled` is on. Optional in the type because older
    // backends won't emit it; callers default to no-headcount + fresh.
    cooking_policy?: {
        household_headcount: number | null;
        batch_features_enabled: boolean;
    };
    // install-wide household grocery budget (moved off User — spend is
    // summed across shared shopping lists, so the target is shared too).
    // Every client reads it here: the dashboard budget card + Settings →
    // Money page. Optional in the type because older backends won't emit it;
    // callers default to no budget / weekly. `amount` null ⇒ no budget set.
    budget_policy?: {
        amount: number | null;
        period: 'weekly' | 'monthly';
    };
    // install-wide meal-reconcile posture. Every client reads it to pick the
    // right /meal-plans/reconcile surface: auto ⇒ a read-only log of what Dora
    // did; manual ⇒ the confirm-each runner. Optional in the type because older
    // backends won't emit it; callers default to auto (matches the sweep).
    reconcile_policy?: {
        auto_drain: boolean;
    };
    // install-wide stocktake defaults. Every client reads it: the create
    // stock-item dialog seeds its Stocktake toggle from `new_items_opt_in`
    // so the switch shows the position the item will really be created in.
    // Optional in the type because older backends won't emit it; callers
    // default to opted-in (matches the server).
    stocktake_policy?: {
        new_items_opt_in: boolean;
    };
    // The household's expiring-soon window (days), as the alerts use it.
    alerts_policy?: {
        expiring_soon_window_days: number;
    };
    // Admin-set Product Search (companion) URL. Every user's nav and the
    // find-a-product buttons read it here; '' ⇒ not set up.
    products_policy?: {
        search_url: string;
    };
    // FU-370 — install's support / report-an-issue channel. Optional in the
    // type because older backends won't emit it; both strings empty ⇒ dormant
    // (no report affordance renders). `url` wins over `email` when both set.
    support?: {
        url: string;             // external "Report an issue" URL, or ''
        email: string;           // mailto: fallback address, or ''
    };
}

export default class HealthApiService {
    private httpClient = new AxiosHttpClient();

    /** Boot probe. Any 2xx from dora_api is "alive". */
    healthCheckAsync = async (): Promise<boolean> => {
        return await this.httpClient
            .get<HealthInfo | boolean>('/health')
            .then(() => true)
            .catch(() => false);
    };

    /** The health payload for compatibility + feature gating. Every policy
     *  composable reads it, so one probe is shared per session (13-R37);
     *  `invalidateHealthInfo()` makes the next read fetch again. */
    getInfoAsync = async (): Promise<HealthInfo> => {
        sharedInfo ??= this.httpClient.get<HealthInfo>('/health').catch((err: unknown) => {
            sharedInfo = null;
            throw err;
        });
        return await sharedInfo;
    };
}

let sharedInfo: Promise<HealthInfo> | null = null;

/** Drop the shared probe so the next `getInfoAsync()` refetches. The policy
 *  composables' `refresh…()` call this after an admin save. */
export function invalidateHealthInfo(): void {
    sharedInfo = null;
}
