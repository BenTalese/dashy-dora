// Module-level network awareness (F3).
//
// Exposes reactive `online` (browser-level) and `apiReachable` (the dora_api
// /health probe). Used by:
//   - OfflineBanner: pin a red strip when either is false. Offline is
//     read-only (2026-08-23) — there is no write queue to drain any more.
//   - Free-form code: any caller that wants to short-circuit before doing
//     an expensive search or background fetch.
//
// State lives at module scope so every consumer shares the same singleton
// — we only want one health-poll loop running per tab.

import { Notify } from 'quasar';
import { OFFLINE_COPY } from 'src/helpers/offlineCopy';
import { computed, readonly, ref } from 'vue';
import { getBackendBaseUrl } from 'src/services/api/backendUrl';

// Reads the runtime backend URL (env-baked, capacitor Preferences, or the
// browser localStorage override — see `services/api/backendUrl.ts`) and
// appends /health. Uses `fetch` directly so the probe sidesteps the
// AxiosHttpClient interceptors / retry layer.
function resolveHealthUrl(): string {
    const base = getBackendBaseUrl();
    if (base && base.length > 0) return base + '/health';
    return '';
}

// Poll cadence: when believed reachable we tick once a minute — the UI
// reacts to errors in real time anyway, so the poll is only there for the
// "I quietly stopped working" case, and the app also probes the moment it
// becomes visible again (see the visibility handling below), which is what
// actually matters after a phone unlock. It used to be 30s, which was
// noticeable background chatter for very little signal. When unreachable we
// ramp from 5s up to 60s with exponential backoff so a long outage doesn't
// hammer — a fast first retry is the point there, so that ladder stands.
const STABLE_INTERVAL_MS = 60_000;
const PROBE_INITIAL_MS = 5_000;
const PROBE_MAX_MS = 60_000;
const PROBE_TIMEOUT_MS = 4_000;

const online = ref(typeof navigator === 'undefined' ? true : navigator.onLine);
const apiReachable = ref(true);
const reconnecting = ref(false);

let pollTimer: ReturnType<typeof setTimeout> | null = null;
let currentBackoffMs = PROBE_INITIAL_MS;
let booted = false;
// Guards against two probes racing — the poll timer firing while the
// user's Retry click is still in flight. Whichever started first owns
// `reconnecting`, and the second call joins the same promise rather
// than issuing a duplicate request.
let inFlight: Promise<boolean> | null = null;

// Eats AbortError so we can race against a timeout without surfacing
// scary-looking unhandled rejections in the console.
async function probeOnce(): Promise<boolean> {
    const url = resolveHealthUrl();
    // on native before the user has picked an instance, the URL
    // resolves to empty; skip the probe cleanly rather than firing a
    // relative fetch at the WebView origin.
    if (!url) return false;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);
    try {
        const res = await fetch(url, {
            method: 'GET',
            // The health endpoint is open and cookie-less — no need to
            // attach credentials. Keeps the request preflight-free in
            // CORS terms too.
            credentials: 'omit',
            cache: 'no-store',
            signal: controller.signal,
        });
        return res.ok;
    } catch {
        return false;
    } finally {
        clearTimeout(timeoutId);
    }
}

function isHidden(): boolean {
    return typeof document !== 'undefined' && document.visibilityState === 'hidden';
}

function scheduleNext(delayMs: number) {
    if (pollTimer) clearTimeout(pollTimer);
    // Nothing is looking at the result while the app is in the background,
    // and the browser throttles the timer to roughly once a minute anyway.
    // `onVisible` re-arms the loop the moment the user comes back, so
    // standing down here costs nothing and saves a phone waking its radio
    // for a health check no one will read.
    if (isHidden()) {
        pollTimer = null;
        return;
    }
    pollTimer = setTimeout(() => void runProbe(), delayMs);
}

/**
 * Run one probe and fold the result into the reactive state.
 *
 * `force` is what the Retry button passes. Without it we skip the fetch
 * whenever `navigator.onLine` is false — cheap, and right for the
 * background poll. It was **wrong for Retry** (2026-08-17 feedback: "not
 * sure the retry button actually works"): the button called straight into
 * here, hit that early return, and did nothing at all — no request, no
 * spinner, no toast. `navigator.onLine` only reports whether the device
 * has *a* network interface, so it sits on `false` through captive
 * portals and half-dropped mobile data, which is exactly when someone
 * reaches for Retry. Forcing the probe also lets a success **correct**
 * `online`, rather than leaving us pinned offline until the browser
 * deigns to fire its `online` event.
 */
async function runProbe(force = false): Promise<boolean> {
    if (inFlight) return inFlight;
    if (!online.value && !force) {
        // No point hitting the API while the browser says we're offline —
        // schedule a long-tail check so we recover if the browser misses
        // the 'online' event.
        scheduleNext(STABLE_INTERVAL_MS);
        return false;
    }
    reconnecting.value = !apiReachable.value;
    inFlight = probeOnce();
    let ok: boolean;
    try {
        ok = await inFlight;
    } finally {
        inFlight = null;
    }
    const wasReachable = apiReachable.value;
    apiReachable.value = ok;
    reconnecting.value = false;

    if (ok) {
        currentBackoffMs = PROBE_INITIAL_MS;
        // The probe reaching the server is proof of connectivity, whatever
        // `navigator.onLine` claims. Flip it back so the banner clears and
        // the queue drain (which watches `apiReachable`) can run.
        online.value = true;
        if (!wasReachable) {
            // Copy lives in `helpers/offlineCopy.ts` with the banner's (R-052:
            // offline is read-only, nothing promises a sync).
            Notify.create({
                type: 'positive',
                position: 'top',
                message: OFFLINE_COPY.backOnline,
                timeout: 3000,
            });
        }
        scheduleNext(STABLE_INTERVAL_MS);
    } else {
        if (wasReachable) {
            // Just transitioned reachable → unreachable.
            Notify.create({
                type: 'warning',
                position: 'top',
                message: OFFLINE_COPY.unreachable,
                timeout: 4000,
            });
        } else if (force) {
            // A Retry that failed. Say so — a button that reports nothing
            // is indistinguishable from a button that isn't wired up.
            Notify.create({
                type: 'warning',
                position: 'top',
                message: OFFLINE_COPY.stillDown,
                timeout: 2500,
            });
        }
        scheduleNext(currentBackoffMs);
        currentBackoffMs = Math.min(currentBackoffMs * 2, PROBE_MAX_MS);
    }
    return ok;
}

function onBrowserOnline() {
    if (online.value) return;
    online.value = true;
    Notify.create({
        type: 'info',
        position: 'top',
        message: OFFLINE_COPY.networkDetected,
        timeout: 2500,
    });
    currentBackoffMs = PROBE_INITIAL_MS;
    void runProbe();
}

/**
 * The app came back to the foreground (tab focused, phone unlocked, PWA or
 * Capacitor shell resumed — all of which fire `visibilitychange`).
 *
 * This is the fix for "coming back to the app takes ages to reconnect". While
 * backgrounded the poll is stood down, and even before that it was throttled;
 * either way the connection state we're holding is stale, and on mobile the
 * socket the app was using is usually dead. Nothing used to re-check until
 * the next scheduled tick, so the offline banner (or a page waiting on data)
 * could sit there long after the network was fine. Probe immediately instead,
 * with the backoff reset so we don't resume mid-ladder from an outage that
 * ended while the user was away.
 */
function onVisible() {
    if (isHidden()) return;
    currentBackoffMs = PROBE_INITIAL_MS;
    void runProbe(true);
}

function onBrowserOffline() {
    online.value = false;
    apiReachable.value = false;
    Notify.create({
        type: 'warning',
        position: 'top',
        message: OFFLINE_COPY.offline,
        timeout: 4000,
    });
}

// One-shot setup. Idempotent because every consumer calls it via
// useNetworkStatus().
function boot() {
    if (booted) return;
    booted = true;
    if (typeof window !== 'undefined') {
        window.addEventListener('online', onBrowserOnline);
        window.addEventListener('offline', onBrowserOffline);
    }
    if (typeof document !== 'undefined') {
        document.addEventListener('visibilitychange', onVisible);
    }
    // First probe runs immediately so the banner state settles fast.
    void runProbe();
}

export function useNetworkStatus() {
    boot();
    return {
        online: readonly(online),
        apiReachable: readonly(apiReachable),
        reconnecting: readonly(reconnecting),
        isFullyOnline: computed(() => online.value && apiReachable.value),
        /** Force an immediate probe (e.g. when the user clicks "Retry").
         *  Bypasses the `navigator.onLine` short-circuit — see runProbe. */
        retryNow: () => {
            currentBackoffMs = PROBE_INITIAL_MS;
            // `reconnecting` drives the button's spinner. runProbe sets it
            // too, but only after the `inFlight` guard; setting it here
            // means the click is acknowledged on the same frame.
            reconnecting.value = true;
            return runProbe(true);
        },
    };
}
