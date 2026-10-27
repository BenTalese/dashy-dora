// runtime-configurable Dora API base URL.
//
// The SPA runs in three shapes:
//   - web (dev / prod PWA): baseURL follows the current origin (env-baked
//     `VITE_API_BASE_URL` if provided, else `${protocol}//${hostname}:5170/api`).
//   - Capacitor native (Android APK / iOS): the app is served from
//     `capacitor://localhost` (Android WebView remaps to `https://localhost`),
//     so it CANNOT infer a backend from `window.location`. The user picks
//     their instance URL on first launch — we persist it via
//     `@capacitor/preferences` and prepend it to every API request.
//
// Storage layout: a single Preferences key `dora.backendBaseUrl`. The web
// fallback also honours a `localStorage` copy so a browser user can override
// the env default from the same Settings screen without touching env files.
//
// The axios request interceptor calls `getBackendBaseUrl()` synchronously
// per request, so a runtime change (Settings → save) applies to the next
// request without any client rebuild.

import { Preferences } from '@capacitor/preferences';
import { isNativePlatform } from 'src/helpers/platform';

// One key, whichever store holds it (Capacitor Preferences natively,
// localStorage in a browser) — finalisation 17-R14.
const STORAGE_KEY = 'dora.backendBaseUrl';

let cache: string | null = null;
let loaded = false;

// `isNativePlatform` lives in `helpers/platform.ts` (finalisation 17-R20);
// re-exported for the callers that only ever reached it from here.
export { isNativePlatform } from 'src/helpers/platform';

function envDefault(): string {
    const env = import.meta.env.VITE_API_BASE_URL;
    if (env && env.length > 0) return env.replace(/\/+$/, '');
    if (isNativePlatform()) {
        // Capacitor serves the SPA from https://localhost (Android) or
        // capacitor://localhost (iOS) — neither is a real backend, so
        // there is no honest default. Force the runtime-override path.
        return '';
    }
    if (typeof window !== 'undefined' && window.location) {
        const { protocol, hostname } = window.location;
        return `${protocol}//${hostname}:5170/api`;
    }
    return '';
}

export function getBackendBaseUrl(): string {
    if (cache !== null) return cache;
    return envDefault();
}

export function hasBackendBaseUrl(): boolean {
    if (cache !== null && cache.length > 0) return true;
    // Browsers: the env / window fallback is always usable, so a user
    // never sees the setup gate. Native: only "yes" once the user has
    // saved a URL.
    if (!isNativePlatform()) {
        return envDefault().length > 0;
    }
    return false;
}

function normaliseUrl(raw: string): string {
    let url = raw.trim().replace(/\/+$/, '');
    if (!/^https?:\/\//i.test(url)) {
        url = 'https://' + url;
    }
    // The app always talks to /api/*; accept both "http://host" and
    // "http://host/api" from users and store the /api-prefixed form.
    if (!/\/api$/i.test(url)) {
        url = url + '/api';
    }
    return url;
}

export async function setBackendBaseUrl(raw: string): Promise<string> {
    const url = normaliseUrl(raw);
    cache = url;
    loaded = true;
    if (isNativePlatform()) {
        await Preferences.set({ key: STORAGE_KEY, value: url });
    } else {
        try {
            localStorage.setItem(STORAGE_KEY, url);
        } catch {
            // Storage disabled — the in-memory cache still holds for this session.
        }
    }
    return url;
}

export async function clearBackendBaseUrl(): Promise<void> {
    cache = null;
    loaded = true;
    if (isNativePlatform()) {
        await Preferences.remove({ key: STORAGE_KEY });
    } else {
        try {
            localStorage.removeItem(STORAGE_KEY);
        } catch {
            // Ignore.
        }
    }
}

export async function loadBackendBaseUrl(): Promise<string | null> {
    if (loaded) return cache;
    if (isNativePlatform()) {
        try {
            const { value } = await Preferences.get({ key: STORAGE_KEY });
            if (value && value.length > 0) cache = value;
        } catch {
            // Preferences not available (e.g. web fallback failure).
        }
    } else {
        try {
            const value = localStorage.getItem(STORAGE_KEY);
            if (value && value.length > 0) cache = value;
        } catch {
            // Ignore.
        }
    }
    loaded = true;
    return cache;
}

export function backendBaseUrlIsUserSet(): boolean {
    return cache !== null && cache.length > 0;
}
