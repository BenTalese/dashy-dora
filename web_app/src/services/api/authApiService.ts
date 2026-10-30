import type {
    AuthenticatedUser,
    FontFamilyPreference,
    FontSizePreference,
    ThemePreference,
    VoiceEngine
} from 'src/models/auth';
import AxiosHttpClient, { NormalisedApiError } from './axiosHttpClient';

/** Settings rebuild Phase 4 — URL for a user's profile-picture bytes (served
 *  raw; 404 when unset). Pass a `version` (a counter bumped after upload /
 *  clear) to bust the browser cache. */
export type LoginCommand = { username: string; password: string };
export type RegisterResult = AuthenticatedUser & { verification_sent?: boolean };

export type RegisterCommand = {
    username: string;
    password: string;
    email: string | null;
};
/** FU-200 — first-admin bootstrap. Email is optional, as on /register
 *  (owner call 2026-08-17). It becomes mandatory only on an install that
 *  sets ADMIN_BOOTSTRAP_EMAIL, where the server matches it. */
export type BootstrapAdminCommand = {
    username: string;
    password: string;
    email: string | null;
};
export type UpdateMeCommand = {
    send_deals_on_day?: number;
    // Direct email edit (the verified change-email flow was retired as
    // overengineered). Empty string clears the address; omit to leave
    // it untouched.
    email?: string;
    username?: string;
    deals_email_enabled?: boolean;
    deals_email_compact?: boolean;
    theme?: ThemePreference;
    font_family?: FontFamilyPreference;
    font_size?: FontSizePreference;
    /** P2-13 — voice opt-in toggles. Saved per user. */
    voice_input_enabled?: boolean;
    voice_output_enabled?: boolean;
    /** Voice engine (`browser` | `piper`) + chosen Piper voice id. Server
     *  validates the voice id against its catalog (GET /api/tts/voices). */
    voice_engine?: VoiceEngine;
    voice_id?: string;
    /** P8-07 — Zero-Input Pantry opt-out. `false` hides the inferred-level
     *  belief overlay; default `true`. */
    inferred_pantry_enabled?: boolean;
    buy_verdict_enabled?: boolean;
    /** FU-653 — per-surface belief overlays (recipes / shopping lists / meal
     *  planner). Each defaults false. */
    inference_recipes_enabled?: boolean;
    inference_shopping_enabled?: boolean;
    inference_meal_plan_enabled?: boolean;
    /** Settings rebuild Phase 4 — profile picture. Data-URL string to set,
     *  `clear_image: true` to remove. Omitting both leaves it untouched. */
    image?: string | null;
    clear_image?: boolean;
    /** Dashboard rebuild Phase 2 — per-user dashboard layout JSON (card order +
     *  hidden set). A string sets it; `null` clears it back to the default
     *  layout. Omitting it leaves it untouched. */
    dashboard_layout?: string | null;
    /** Per-user assistant Mode. `llm_provider` selects the active provider
     *  (or null for Basic); `llm_enabled` is the AI opt-in. Per-provider
     *  details are edited via AssistantApiService (`/assistant/providers`),
     *  not here. Enabling AI requires the active provider to be verified. */
    llm_enabled?: boolean;
    llm_provider?: 'ollama' | 'openai' | 'anthropic' | 'gemini' | null;
    /** FU-360.6 — show/hide the Dora helper bubble for this account. */
    show_assistant?: boolean;
    /** Daily brief push opt-in. See AuthenticatedUser. */
    daily_brief_enabled?: boolean;
    /** Days after which alerts are discarded (7 / 14 / 30), or null for never. */
    alert_discard_after_days?: number | null;
};
export type ChangePasswordCommand = {
    current_password: string;
    new_password: string;
};

export default class AuthApiService {
    private httpClient: AxiosHttpClient;

    constructor() {
        this.httpClient = new AxiosHttpClient();
    }

    loginAsync = async (command: LoginCommand): Promise<AuthenticatedUser> =>
        await this.httpClient.post<AuthenticatedUser, LoginCommand>('/auth/login', command);

    /** The register body is the signed-in user plus `verification_sent`
     *  (an address was given and a verification mail went out — finalisation
     *  15-R3, R-057: the flag was emitted but never read). */
    registerAsync = async (command: RegisterCommand): Promise<RegisterResult> =>
        await this.httpClient.post<RegisterResult, RegisterCommand>('/auth/register', command);

    /** FU-200 — fresh-install probe. Returns `{ required: true }` when the
     *  DB has no users yet; the router uses this to route to /setup
     *  instead of /login. Never throws on a 401 (unauthenticated probes
     *  are explicitly allowed by the middleware). */
    bootstrapRequiredAsync = async (): Promise<boolean> => {
        const result = await this.httpClient.get<{ required: boolean }>(
            '/auth/bootstrap-required',
        );
        return result.required;
    };

    /** Is the server at the configured address actually Dora? Any host
     *  answers *something* with a 200 (a router admin page, a WebView's own
     *  index.html), so a status code alone proves nothing. The public
     *  `bootstrap-required` endpoint always answers `{ required: boolean }`;
     *  anything else is a different server. Network/HTTP errors propagate. */
    isDoraServerAsync = async (): Promise<boolean> => {
        const result = await this.httpClient.get<unknown>('/auth/bootstrap-required');
        return typeof result === 'object'
            && result !== null
            && typeof (result as { required?: unknown }).required === 'boolean';
    };

    /** Pre-auth capability probe. Currently exposes just
     *  `email_sender_configured` — false when the install has no live
     *  SMTP (dry-run only logs the outbound body, which a normal user
     *  can't read), so login-screen surfaces that would only work with
     *  real email (Forgot password?, Resend verification) should hide. */
    getCapabilitiesAsync = async (): Promise<{ emailSenderConfigured: boolean; demoMode: boolean }> => {
        const result = await this.httpClient.get<{ email_sender_configured: boolean; demo_mode?: boolean }>(
            '/auth/capabilities',
        );
        return {
            emailSenderConfigured: result.email_sender_configured,
            // FU-392 — demo / sellable-showcase mode. Optional-chained so an
            // older backend that predates the flag reads as "not a demo".
            demoMode: result.demo_mode ?? false,
        };
    };

    /** FU-200 — single-use first-admin creation. The server 410s once any
     *  user exists, so the SPA should only call this when
     *  bootstrapRequiredAsync() returned true. Success auto-logs the new
     *  admin in (session cookie set server-side). */
    bootstrapAdminAsync = async (
        command: BootstrapAdminCommand,
    ): Promise<AuthenticatedUser> =>
        await this.httpClient.post<AuthenticatedUser, BootstrapAdminCommand>(
            '/auth/bootstrap-admin', command,
        );

    logoutAsync = async (): Promise<void> =>
        await this.httpClient.post<void, Record<string, never>>('/auth/logout', {});

    updateMeAsync = async (command: UpdateMeCommand): Promise<AuthenticatedUser> =>
        await this.httpClient.patch<AuthenticatedUser, UpdateMeCommand>('/auth/me', command);

    changePasswordAsync = async (command: ChangePasswordCommand): Promise<void> =>
        await this.httpClient.post<void, ChangePasswordCommand>('/auth/me/password', command);

    // ── A1 out-of-band flows ───────────────────────────────────────
    verifyEmailAsync = async (token: string): Promise<void> =>
        await this.httpClient.post<void, { token: string }>('/auth/verify-email', { token });

    resendVerificationAsync = async (email: string): Promise<void> =>
        await this.httpClient.post<void, { email: string }>('/auth/resend-verification', { email });

    forgotPasswordAsync = async (email: string): Promise<void> =>
        await this.httpClient.post<void, { email: string }>('/auth/forgot-password', { email });

    resetPasswordAsync = async (token: string, newPassword: string): Promise<void> =>
        await this.httpClient.post<void, { token: string; new_password: string }>(
            '/auth/reset-password', { token, new_password: newPassword },
        );

    getMeAsync = async (): Promise<AuthenticatedUser | null> => {
        try {
            return await this.httpClient.get<AuthenticatedUser>('/auth/me');
        } catch (error) {
            // 401 means no session — caller treats null as "not logged in".
            // Network/server errors propagate so bootstrap can show a splash.
            if (error instanceof NormalisedApiError && error.status === 401) {
                return null;
            }
            throw error;
        }
    };
}
