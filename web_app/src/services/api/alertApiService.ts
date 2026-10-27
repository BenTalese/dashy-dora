import {
    DEFAULT_SNOOZE_DAYS,
    type AlertAction,
    type AlertPrefs,
    type Alerts,
    type Upcoming,
    type UpdateAlertPrefCommand,
} from 'src/models/alert';
import AxiosHttpClient from './axiosHttpClient';

export default class AlertApiService {
    private httpClient = new AxiosHttpClient();

    getAlertsAsync = async (): Promise<Alerts> =>
        await this.httpClient.get<Alerts>('/alerts');

    applyActionAsync = async (alertId: string, action: AlertAction): Promise<void> =>
        await this.httpClient.post<void, { action: AlertAction }>(
            `/alerts/${alertId}/action`,
            { action },
        );

    // ── Per-user interaction state (C-9.1) ─────────────────────────────
    // alertId is the scoped key; it carries ':' but no '/', so it's a single
    // path segment server-side (matching the existing action endpoint).
    dismissAllAsync = async (): Promise<void> =>
        await this.httpClient.post<void, undefined>('/alerts/dismiss-all', undefined);

    snoozeAsync = async (alertId: string, days = DEFAULT_SNOOZE_DAYS): Promise<void> =>
        await this.httpClient.post<void, { days: number }>(
            `/alerts/${alertId}/snooze`,
            { days },
        );

    dismissAsync = async (alertId: string): Promise<void> =>
        await this.httpClient.post<void, undefined>(`/alerts/${alertId}/dismiss`, undefined);

    clearSuppressionAsync = async (alertId: string): Promise<void> =>
        await this.httpClient.delete<void>(`/alerts/${alertId}/suppression`);

    // ── Per-user preferences (C-9.2) ───────────────────────────────────
    // Enable/disable a kind. The server applies these to GET /alerts, so the
    // badge/list already reflect them (R-003); Settings → Notifications reads
    // and writes them.
    getPrefsAsync = async (): Promise<AlertPrefs> =>
        await this.httpClient.get<AlertPrefs>('/alerts/prefs');

    updatePrefAsync = async (command: UpdateAlertPrefCommand): Promise<AlertPrefs> =>
        await this.httpClient.patch<AlertPrefs, UpdateAlertPrefCommand>('/alerts/prefs', command);

    // ── Upcoming "this fortnight" timeline (C-9.6) — server-aggregated dated
    // events (expiries / planned shopping / meal-plan days) over the next N days.
    getUpcomingAsync = async (days = 14): Promise<Upcoming> =>
        await this.httpClient.get<Upcoming>(`/alerts/upcoming?days=${days}`);

    // ── Web Push (C-9.8) ───────────────────────────────────────────────
    // VAPID public key (404 when the install isn't configured — the
    // composable treats that as "channel disabled" and renders the
    // toggle accordingly, matching the SMTP-gated alerts-email card).
    getPushPublicKeyAsync = async (): Promise<{ public_key: string }> =>
        await this.httpClient.get<{ public_key: string }>('/alerts/push/vapid-public-key');

    subscribePushAsync = async (
        body: { endpoint: string; keys: { p256dh: string; auth: string }; user_agent: string | null },
    ): Promise<void> =>
        await this.httpClient.post<void, typeof body>('/alerts/push/subscribe', body);

    unsubscribePushAsync = async (endpoint: string): Promise<void> =>
        await this.httpClient.post<void, { endpoint: string }>(
            '/alerts/push/unsubscribe',
            { endpoint },
        );
}
