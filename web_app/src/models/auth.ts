// Named-theme catalogue lives in services/themeService.ts. `light` and
// `dark` stay in the type for legacy values that may still be in the
// database; themeService maps them onto `pesto` and `midnight-snack`
// at apply time. `avocado` is similarly legacy — was retired when
// `pesto` (a fresher green) took over as the brand default.
export type ThemePreference =
    | 'system'
    // Round-19: per-family system-mode keys so the picker can split mode
    // (System / Light / Dark) and family (Pesto / Lemon Tart / …)
    // independently — picking System + Cherry Cola now actually follows
    // the OS using Cherry Cola variants, not the old hardcoded pesto
    // fallback. The bare `system` legacy key still resolves to the
    // pesto family for back-compat.
    | 'system-pesto'
    | 'system-lemon-tart'
    | 'system-blueberry'
    | 'system-cherry-cola'
    | 'system-sourdough'
    | 'system-salt-pepper'
    | 'system-dragonfruit'
    | 'pesto'
    | 'pesto-dark'
    | 'lemon-tart'
    | 'lemon-tart-dark'
    | 'blueberry'
    | 'blueberry-dark'
    | 'cherry-cola'
    | 'cherry-cola-dark'
    | 'sourdough'
    | 'sourdough-dark'
    | 'salt-pepper'
    | 'salt-pepper-dark'
    | 'dragonfruit'
    | 'dragonfruit-dark'
    // Legacy — themeService maps these forward at apply time.
    | 'pesto-noir'      // → pesto-dark
    | 'midnight-snack'  // → lemon-tart-dark
    | 'avocado'         // → pesto
    | 'light'           // → pesto
    | 'dark';           // → pesto-dark
export type FontFamilyPreference =
    | 'default'
    | 'urbanist'
    | 'nunito'
    | 'inter'
    | 'lexend'
    | 'plus_jakarta_sans';
export type FontSizePreference = 'sm' | 'md' | 'lg' | 'xl';
export type BudgetPeriod = 'weekly' | 'monthly';
// Which engine speaks Dora's replies / cook-mode steps. `piper` is the
// neural voice (POST /api/tts); `browser` is the built-in Web Speech voice.
// useSpeechOutput falls back from piper → browser when Piper isn't available.
export type VoiceEngine = 'browser' | 'piper';

export type AuthenticatedUser = {
    user_id: string;
    username: string;
    email: string | null;
    is_admin: boolean;
    send_deals_on_day: number;
    deals_email_enabled: boolean;
    deals_email_compact: boolean;
    theme: ThemePreference;
    font_family: FontFamilyPreference;
    font_size: FontSizePreference;
    // ISO timestamp; null until the user finishes (or skips) the first-run
    // wizard. The router guard reads this to bounce incomplete users to
    // /welcome.
    onboarding_completed_at: string | null;
    // A1: false until the user clicks the verification link in the email
    // sent on registration. Drives the verify-banner on LoginPage and
    // the Settings → Account hint. First-user-is-admin auto-verifies.
    email_verified: boolean;
    // grocery budget moved to the install-wide household setting
    // (AppSetting) — read via /api/health `budget_policy`, not this user
    // record. Spend is shared across shopping lists, so the target is too.
    // voice opt-ins. Both default false; the SPA seeds its
    // per-page mic / volume toggles from these on boot.
    voice_input_enabled: boolean;
    voice_output_enabled: boolean;
    // Voice engine + chosen Piper voice id (from the server catalog,
    // GET /api/tts/voices). Drive useSpeechOutput; only matter when
    // voice_output_enabled is on. Default `piper` / `amy`.
    voice_engine: VoiceEngine;
    voice_id: string;
    // money-features opt-in removed — money is a single install-wide flag
    // (`money_enabled`); there is no per-user money layer. `useMoneyEnabled()`
    // reads only the install flag now.
    // FU-615 — `batch_features_enabled` moved to the install-wide AppSetting
    // (read via `useCookingPolicy()` / `useBatchEnabled()`, edited by an admin
    // in Settings → System → Cooking). No longer a per-user field.
    // Zero-Input Pantry opt-out. Default true (inferred stock
    // levels are the headline experience); false hides the belief overlay.
    inferred_pantry_enabled: boolean;
    /** D-12 — per-user since 2026-08-19; was an install-wide AppSetting
     *  surfaced as `features.buy_verdict` on /api/health. */
    buy_verdict_enabled: boolean;
    /** FU-653 — the same belief surfaced on the pages where stock items
     *  *appear*: a remark on a recipe, suggestions beside a shopping list, a
     *  flag on a planned meal. One opt-in each, all **default false**. None of
     *  them changes cookability, filtering, or what's on a list — they only
     *  add a remark, which is why they're separate from the stock toggle
     *  above. */
    inference_recipes_enabled: boolean;
    inference_shopping_enabled: boolean;
    inference_meal_plan_enabled: boolean;
    // `nutrition_mode` removed (2026-08-14) — nutrition is install-wide.
    // Read it with `useNutritionMode()`, which sources it from
    // /api/health `features.nutrition_mode`.
    // `show_recipe_images` removed (2026-08-29) — the per-user recipe-image
    // opt-in is cut. Photo density on the cookbook is the cards/compact view
    // switch; every other surface renders photos unconditionally.
    // FU-615 — `household_headcount` moved to the install-wide AppSetting
    // (read via `useCookingPolicy()`, edited in Settings → System → Cooking).
    // No longer a per-user field.
    // Settings rebuild Phase 4 — whether the user has a profile picture.
    // Bytes are fetched separately via `GET /users/<id>/image`; server-derived
    // so the SPA never keeps its own truth about whether a picture exists.
    has_image: boolean;
    // Dashboard rebuild Phase 2 — per-user dashboard layout JSON (card order +
    // hidden set), or null when the user hasn't customised. Parsed by the
    // dashboard to seed card order/visibility; persisted via PATCH /auth/me so
    // it survives a cache clear and follows the user across devices.
    dashboard_layout: string | null;
    // The Reports page's layout JSON, the same contract (FU-832).
    reports_layout: string | null;
    // per-user assistant config. `llm_enabled` is the AI-mode opt-in and
    // `llm_provider` the active provider (or null for Basic). Per-provider
    // details live in the `UserLlmProvider` table, read/edited via the
    // `/assistant/providers` endpoints (see AssistantApiService). `assistant_
    // ready` is the derived bit the SPA needs inline: the active provider has
    // a verified config, so AI mode can actually run.
    llm_enabled: boolean;
    llm_provider: 'ollama' | 'openai' | 'anthropic' | 'gemini' | null;
    assistant_ready: boolean;
    // FU-360.6 — whether the Dora helper bubble is mounted at all. Default
    // true; distinct from `llm_enabled` (that switches AI mode only).
    show_assistant: boolean;
    /** Owner call 2026-08-17 — one opt-in evening push (19:00 household time)
     *  summarising tomorrow's meals and any shopping day that's due. Off by
     *  default, and silent on days with nothing to say. */
    daily_brief_enabled: boolean;
    /** Owner 2026-10-15 — alerts whose condition began more than this many
     *  days ago are dropped from the bell. Null keeps them all. */
    alert_discard_after_days: number | null;
};
export type LlmProvider = NonNullable<AuthenticatedUser['llm_provider']>;
