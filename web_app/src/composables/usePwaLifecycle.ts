/**
 * PWA lifecycle hooks the SPA listens to:
 *   - `beforeinstallprompt`  — defer the browser's native install
 *     prompt so we can surface it via our own "Install Dora" button.
 *   - `appinstalled`         — clear the deferred prompt + record state.
 *   - `controllerchange` on `navigator.serviceWorker` — a new service
 *     worker has taken control; flag `updateAvailable` so the app shell
 *     can offer a reload (UpdateBanner).
 *
 * Designed to be idempotent so multiple call sites (App.vue mounting,
 * Settings page surfacing the install button) share state via the
 * module-level refs without double-binding listeners.
 */
import { computed, ref } from 'vue';

// Augment the standard BeforeInstallPromptEvent (TS lib doesn't ship one).
interface BeforeInstallPromptEvent extends Event {
    prompt: () => Promise<void>;
    userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

const deferredPrompt = ref<BeforeInstallPromptEvent | null>(null);
const installed = ref(false);
let lifecycleInstalled = false;

// A newer frontend build is cached and one reload away from taking effect.
// Surfaced as a dismissible in-app banner (UpdateBanner) for every user, not
// a toast — the toast fired once and was easy to miss (owner feedback).
const updateAvailable = ref(false);
const updateDismissed = ref(false);

/** True once a genuinely new SW has replaced the one that was controlling
 *  the page at boot, and the user hasn't dismissed the prompt. */
export function updateAvailablePrompt() {
    return computed(() => updateAvailable.value && !updateDismissed.value);
}

/** Reload to activate the already-cached new build. */
export function applyUpdateReload(): void {
    if (typeof window !== 'undefined') window.location.reload();
}

/** Dismiss the update banner for this page load. */
export function dismissUpdate(): void {
    updateDismissed.value = true;
}

export { isIosSafari } from 'src/helpers/platform';

/**
 * Why the install button isn't offered, when it isn't.
 *
 * `beforeinstallprompt` only fires in a **secure context** — HTTPS, or
 * localhost. A self-hosted Dora reached over plain HTTP on the LAN
 * (`http://192.168.x.x:8080`, the shape a Docker install takes) therefore
 * never fires it, in any browser. The page used to answer that with
 * *"Install isn't available in this browser. Try Chrome…"*, which is wrong
 * twice over: it blames the browser, and it sends the user to a browser that
 * will do exactly the same thing (owner 2026-09-03 — *"always says
 * unavailable even in chrome"*).
 *
 * `'browser'` stays the honest answer for a secure context that still hasn't
 * fired the event — Firefox desktop, an already-dismissed prompt, or a
 * manifest/SW the browser judged ineligible.
 */
export function installUnavailableReason() {
    return computed<'insecure-context' | 'browser'>(() => {
        if (typeof window !== 'undefined' && window.isSecureContext === false) {
            return 'insecure-context';
        }
        return 'browser';
    });
}

export function installPromptAvailable() {
    return computed(() => deferredPrompt.value !== null);
}

export function isInstalled() {
    return computed(() => installed.value);
}

export async function showInstallPrompt(): Promise<'accepted' | 'dismissed' | 'unavailable'> {
    const event = deferredPrompt.value;
    if (!event) return 'unavailable';
    try {
        await event.prompt();
        const choice = await event.userChoice;
        deferredPrompt.value = null;
        return choice.outcome;
    } catch {
        return 'dismissed';
    }
}

/** Wire window + service-worker listeners exactly once. Call from a
 *  boot file or App.vue mounted hook. */
export function installPwaLifecycle(): void {
    if (lifecycleInstalled) return;
    if (typeof window === 'undefined') return;
    lifecycleInstalled = true;

    // Some browsers fire `appinstalled` for an install that happened in
    // a different tab. Best-effort flag — no behaviour depends on it
    // beyond hiding the "Install Dora" button.
    window.addEventListener('appinstalled', () => {
        installed.value = true;
        deferredPrompt.value = null;
    });

    window.addEventListener('beforeinstallprompt', (event) => {
        event.preventDefault();
        deferredPrompt.value = event as BeforeInstallPromptEvent;
    });

    // Treat `display-mode: standalone` as already installed so we don't
    // nag a user who launched from the home screen.
    try {
        if (window.matchMedia('(display-mode: standalone)').matches) {
            installed.value = true;
        }
    } catch {
        // Ancient browsers without matchMedia — ignored.
    }

    // Service-worker update flow: when a new SW activates and takes control
    // of this client, flag an update so the shell can offer a reload rather
    // than hard-reloading mid-interaction.
    //
    // False-positive guard: `controllerchange` also fires the FIRST time any
    // SW claims a client that booted uncontrolled — e.g. the Notifications
    // page registering the push SW on a fresh session (dev especially). That
    // initial claim is NOT a new version. We only treat it as an update when a
    // controller was already in place at boot, i.e. an existing SW was
    // genuinely replaced.
    if ('serviceWorker' in navigator) {
        const hadControllerAtBoot = !!navigator.serviceWorker.controller;
        navigator.serviceWorker.addEventListener('controllerchange', () => {
            if (!hadControllerAtBoot) return; // initial claim, not an upgrade
            updateAvailable.value = true;
        });
    }
}
