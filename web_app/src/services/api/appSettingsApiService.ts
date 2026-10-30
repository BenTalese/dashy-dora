import AxiosHttpClient from './axiosHttpClient';
import type { CadenceBand } from './stocktakeApiService';

/** FU-511 — install-wide auto-add mode. Kept as a shared enum so the
 *  Settings page and any surface that reads the setting stay in sync. */
export type AutoAddMode = 'off' | 'essential_only' | 'all';

export type AppSettings = {
    // AI mode is per-user only (no install-wide master switch) — the LLM
    // URL/model/provider/API key live on the User row (see
    // authStore.currentUser.llm_*).
    scanning_enabled: boolean;
    // SEC-3 — whether the login page offers "Create account". Off by default.
    registration_enabled: boolean;
    // buy-verdict oracle. Default on (pure-personal feature).
    // C-cross Chunk 1 — install-wide feature flags (proposal §2.6).
    money_enabled: boolean;
    // Nutrition, install-wide (2026-08-14). Replaced `nutrition_enabled` +
    // the per-user mode + the dead `nutrition_db_source` seam.
    nutrition_mode: 'off' | 'simple' | 'complex';
    nutrition_usda_api_key: string;
    nutrition_off_lookup_enabled: boolean;
    // Meal Plans C-2.K — household IANA timezone for the "today" boundary.
    timezone: string;
    // install-wide currency (ISO 4217) + display locale (BCP-47).
    // Every money render in the SPA routes through the shared formatter
    // (composables/useMoney.ts), which reads these values from /api/health.
    currency: string;
    locale: string;
    /** Owner ask 2026-08-27 — which units every dropdown in the app offers:
     *  'metric' | 'imperial' | 'us'. Also decides the shelf convention a
     *  per-unit price is quoted in, replacing the old `unit_pricing_locale`
     *  (which answered only the second question, on an axis that couldn't
     *  tell the UK from the US). Read by every session via /api/health;
     *  editable here by admins. */
    measurement_system: 'metric' | 'imperial' | 'us';
    /** Owner ask 2026-08-27 — which front-of-pack rating recipes carry:
     *  'none' (the default everywhere) | 'health_star' | 'nutri_score'.
     *  Both schemes work anywhere; Dora just doesn't pick a nutritional
     *  authority for a household without being asked. */
    nutrition_rating_scheme: string;
    // Alerts C-9.2 — household-wide alert thresholds (PROPOSAL_ALERTS §3.3).
    expiring_soon_window_days: number;
    // Phase D / FU-186 — admin-set URL the Product Search nav opens.
    // Empty string ⇒ unset; the nav entry is hidden until a URL is set.
    product_search_url: string;
    // PROPOSAL_STOCKTAKE_MODE §4 + §8 — global cadence band + Auto toggle.
    // These are the single user-visible cadence dial; the old
    // `default_days_until_stocktake_alert` field was retired in the
    // 2026-07-04 cleanup.
    stocktake_default_cadence_band: CadenceBand;
    stocktake_auto_tuning_enabled: boolean;
    // 2026-08-20 owner feedback — install-wide stocktake master switch, and
    // the opt-in default new items are born with. `stocktake_enabled` false
    // hides the whole surface (overview button, Needs-check filter, per-item
    // toggle) and empties the server-side overdue map; it rides
    // `/api/health features.stocktake` for non-admin clients.
    stocktake_enabled: boolean;
    stocktake_new_items_opt_in: boolean;
    /** FU-511 — install-wide auto-add mode. Replaces the retired per-item
     *  `StockItem.auto_add_when_low` toggle. Auto-add fires per the mode:
     *    'off'            — never.
     *    'essential_only' — only for items with `is_essential=true` (default).
     *    'all'            — always on a Stocked → Low/Out transition.
     *  Server owns the branching in `update_stock_item._try_auto_add`. */
    auto_add_mode: AutoAddMode;
    // FU-615 — household cooking config, install-wide (moved off User).
    // `household_headcount` null = not set (cook mode uses recipe servings);
    // `batch_features_enabled` = cook-style ("batch" reveals the cook pool).
    // Also mirrored on /api/health.cooking_policy so every client (not just
    // admins) reads them — cook mode + the meal-planner read there.
    household_headcount: number | null;
    batch_features_enabled: boolean;
    // FU-317 — install-wide meal-plan reconcile posture. True = today's
    // silent auto-drain (past-day entries are assumed cooked, pool drains
    // as the day rolls). False = the sweep writes `unresolved_manual`
    // receipts and leaves the pool + entries untouched, forcing every
    // past meal through the reconcile page. Owned by admin.
    auto_drain_past_meals: boolean;
    // operational config promoted from DORA_* env vars.
    // Bucket-C secrets (SMTP password, VAPID private key) live encrypted-at-
    // rest on the AppSetting row; the read DTO surfaces a `_configured` bool
    // instead of the ciphertext. Writes accept plaintext via the write DTO
    // (see below) and the handler encrypts on save.
    smtp_host: string;
    smtp_port: number;
    smtp_username: string;
    smtp_password_configured: boolean;
    smtp_from: string;
    smtp_use_tls: boolean;
    vapid_public_key: string;
    vapid_private_key_configured: boolean;
    vapid_subject: string;
    piper_bin: string;
    piper_bundled_voice_dir: string;
    email_enabled: boolean;
    audit_retention_days: number;
    public_url: string;
    // install-wide image-encode policy, applied at upload time by the shared
    // `processImageFile` helper. Owned by Settings → Install → Image quality;
    // also mirrored on /api/health so non-admin clients read the same numbers.
    // Backup library (Settings → Backup & restore).
    backup_retention_count: number;
    backup_storage_path: string;
    image_quality: number;
    image_max_dimension: number;
};

// the read DTO exposes `<field>_configured` bools; the
// write DTO accepts the plaintext value on `<field>` (server encrypts and
// returns only the bool). Empty string on a secret field is the explicit
// "clear the stored value" signal; omit the field to leave it unchanged.
export type UpdateAppSettingsCommand = Partial<Omit<AppSettings,
    'smtp_password_configured' | 'vapid_private_key_configured'>> & {
    smtp_password?: string;
    vapid_private_key?: string;
};

export default class AppSettingsApiService {
    private httpClient = new AxiosHttpClient();

    getAsync = async (): Promise<AppSettings> =>
        await this.httpClient.get<AppSettings>('/app-settings');

    updateAsync = async (command: UpdateAppSettingsCommand): Promise<AppSettings> =>
        await this.httpClient.patch<AppSettings, UpdateAppSettingsCommand>('/app-settings', command);
}
