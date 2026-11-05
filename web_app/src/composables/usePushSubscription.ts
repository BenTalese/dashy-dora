// Web-push subscription state for the Preferences toggle.
//
// Owns the four-state lifecycle a real Push toggle has to express:
//   - unsupported    browser lacks ServiceWorker / PushManager / Notification
//   - denied         the user (or a previous tab) blocked notifications
//   - unsubscribed   default; permission may be 'default' or 'granted'
//   - subscribed     a live PushSubscription is registered + saved server-side
//
// Layered with `useFeatureFlags().pushVapidConfigured`: if the backend has
// no VAPID keys, this composable still loads but `subscribe()` short-
// circuits with an explicit error message. NotificationsSettings (the
// R-029 carve-out screen that owns the per-user push opt-in) checks the
// flag and renders its toggle disabled before subscribe is ever called;
// this guard is belt-and-braces for that path.

import { computed, onMounted, ref } from 'vue';
import AlertApiService from 'src/services/api/alertApiService';

const PUSH_SW_URL = '/push-sw.js';

export type PushState =
    | 'loading'
    | 'unsupported'
    | 'denied'
    | 'unsubscribed'
    | 'subscribed';

function browserSupports(): boolean {
    return (
        typeof window !== 'undefined'
        && 'serviceWorker' in navigator
        && 'PushManager' in window
        && 'Notification' in window
    );
}

function urlBase64ToUint8Array(base64String: string): Uint8Array {
    // VAPID public keys arrive base64url-encoded; the WebCrypto subscribe
    // call wants a raw Uint8Array. Padding + URL-safe char replacement
    // matches the canonical pywebpush/web-push examples.
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(base64);
    const output = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) output[i] = raw.charCodeAt(i);
    return output;
}

/**
 * The service-worker registration push attaches to.
 *
 * A registration is keyed by **scope**, not script URL, and both `sw.js`
 * (Workbox, the PWA build) and `/push-sw.js` default to `/`. Registering
 * `/push-sw.js` while `sw.js` controlled the page therefore *replaced* it:
 * the offline cache worker was gone until the next full load re-registered
 * `sw.js` (which then evicted the push worker), and every swap fired
 * `controllerchange` → a false "A new version of Dora is ready" banner —
 * simply from opening Settings → Notifications (finalisation 17-R1).
 *
 * The PWA build now imports `push-sw.js`'s handlers into the Workbox worker
 * (`quasar.config.ts` → `importScripts`), so when a registration already
 * exists it is the one to use. Only when nothing is registered (SPA / dev
 * mode, which has no `sw.js`) is the push-only worker registered on its own.
 * `container` is injectable for tests.
 */
export async function resolvePushRegistration(
    container: ServiceWorkerContainer = navigator.serviceWorker,
): Promise<ServiceWorkerRegistration> {
    const existing = await container.getRegistration();
    if (existing) {
        await container.ready;
        return existing;
    }
    const registered = await container.register(PUSH_SW_URL);
    // `ready` resolves once the SW is activated and controlling.
    await container.ready;
    return registered;
}

/**
 * Sign-out teardown (FU-959): drop this browser's push subscription, here and
 * on the server, so the next person to sign in on a shared device doesn't keep
 * receiving the previous user's alerts. Best-effort and quiet; it must never
 * stop the sign-out. Only an existing registration is consulted, so it never
 * registers a worker just to find nothing there.
 */
export async function dropPushSubscriptionAsync(): Promise<void> {
    if (!browserSupports()) return;
    try {
        const reg = await navigator.serviceWorker.getRegistration();
        const sub = await reg?.pushManager.getSubscription();
        if (!sub) return;
        await new AlertApiService().unsubscribePushAsync(sub.endpoint).catch(() => undefined);
        await sub.unsubscribe();
    } catch {
        // The server prunes a dead endpoint on its next send.
    }
}

export function usePushSubscription() {
    const state = ref<PushState>('loading');
    const error = ref<string | null>(null);
    const api = new AlertApiService();

    let registration: ServiceWorkerRegistration | null = null;

    async function ensureRegistration(): Promise<ServiceWorkerRegistration | null> {
        if (registration) return registration;
        try {
            registration = await resolvePushRegistration();
            return registration;
        } catch (err) {
            error.value = (err as Error).message || 'Service worker failed to register.';
            return null;
        }
    }

    async function refresh() {
        if (!browserSupports()) {
            state.value = 'unsupported';
            return;
        }
        if (Notification.permission === 'denied') {
            state.value = 'denied';
            return;
        }
        const reg = await ensureRegistration();
        if (!reg) {
            state.value = 'unsupported';
            return;
        }
        const sub = await reg.pushManager.getSubscription();
        state.value = sub ? 'subscribed' : 'unsubscribed';
    }

    async function subscribe(): Promise<void> {
        error.value = null;
        if (!browserSupports()) {
            error.value = 'This browser does not support web push.';
            state.value = 'unsupported';
            return;
        }
        // Permission must be requested from a user gesture — `subscribe`
        // is called from a toggle click, so this is the right place.
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') {
            state.value = permission === 'denied' ? 'denied' : 'unsubscribed';
            error.value = permission === 'denied'
                ? 'Notifications were blocked. Re-enable them in your browser settings.'
                : 'Permission to send notifications was not granted.';
            return;
        }
        const reg = await ensureRegistration();
        if (!reg) return;

        // Fetch VAPID key + subscribe. A 404 here means the install
        // isn't configured for push — surface it explicitly rather
        // than letting the toggle silently fail.
        let publicKey: string;
        try {
            const resp = await api.getPushPublicKeyAsync();
            publicKey = resp.public_key;
        } catch (_err) {
            error.value = 'Push notifications are not configured on this install.';
            state.value = 'unsubscribed';
            return;
        }
        const subscription = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(publicKey),
        });
        const json = subscription.toJSON();
        await api.subscribePushAsync({
            endpoint: subscription.endpoint,
            keys: {
                p256dh: (json.keys && json.keys.p256dh) || '',
                auth: (json.keys && json.keys.auth) || '',
            },
            user_agent: navigator.userAgent.slice(0, 255),
        });
        state.value = 'subscribed';
    }

    async function unsubscribe(): Promise<void> {
        error.value = null;
        const reg = await ensureRegistration();
        if (!reg) return;
        const sub = await reg.pushManager.getSubscription();
        if (!sub) {
            state.value = 'unsubscribed';
            return;
        }
        // Tear down server-side first — if the browser-side unsubscribe
        // succeeds but the server call fails, we'd leak a row that no
        // device can receive on. The reverse leaks a dead row only
        // until the next push (the job prunes 404/410s).
        try {
            await api.unsubscribePushAsync(sub.endpoint);
        } catch (err) {
            error.value = (err as Error).message || 'Server-side unsubscribe failed.';
            return;
        }
        await sub.unsubscribe();
        state.value = 'unsubscribed';
    }

    const subscribed = computed(() => state.value === 'subscribed');
    const supported = computed(() => state.value !== 'unsupported');

    onMounted(() => { void refresh(); });

    return { state, error, subscribed, supported, refresh, subscribe, unsubscribe };
}
