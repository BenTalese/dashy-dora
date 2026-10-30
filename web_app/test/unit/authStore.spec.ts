// @vitest-environment jsdom
//
// Store-layer coverage — authStore, the single source of truth for "who is
// signed in" + the cold-boot probe every route guard waits on. The
// behavioural contracts worth pinning (all documented in the store):
//   * bootstrap is a shared in-flight promise — App.vue and the router guard
//     both await it, so a second caller must NOT kick off a duplicate probe,
//   * a fresh install (no admin yet) skips the /me probe and flags /setup,
//   * a failed boot probe parks on a promise and the splash's Retry resumes
//     the same loop (network vs generic message split),
//   * sign-out AND a silent 401 both clear the user and wipe per-page list
//     state (FU-355 shared-device hygiene) — logout even when the call fails,
//     and drop the per-user overlay caches (buy verdicts, pantry beliefs,
//     planned demand),
//   * updateMe only busts the avatar cache when an image field was sent.
//
// API service + useListState mocked at the module boundary; the real
// NormalisedApiError is kept so the network-vs-generic branch is exercised
// for real, and setUnauthorizedHandler is spied to capture the 401 handler
// the store registers on creation.
import { createPinia, setActivePinia } from 'pinia';
import type { AuthenticatedUser } from 'src/models/auth';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useAuthStore } from 'src/stores/authStore';
import { NormalisedApiError } from 'src/services/api/axiosHttpClient';
import { clearBackendBaseUrl, setBackendBaseUrl } from 'src/services/api/backendUrl';
import type * as AxiosHttpClientModule from 'src/services/api/axiosHttpClient';

const m = vi.hoisted(() => ({
    bootstrapRequiredAsync: vi.fn(),
    getMeAsync: vi.fn(),
    loginAsync: vi.fn(),
    registerAsync: vi.fn(),
    bootstrapAdminAsync: vi.fn(),
    updateMeAsync: vi.fn(),
    changePasswordAsync: vi.fn(),
    logoutAsync: vi.fn(),
    // Captures the handler the store hands to setUnauthorizedHandler, so a
    // 401 from the axios interceptor can be simulated without a real request.
    unauthorizedHandler: null as (() => void) | null,
}));

vi.mock('src/services/api/authApiService', () => ({
    default: class {
        bootstrapRequiredAsync = m.bootstrapRequiredAsync;
        getMeAsync = m.getMeAsync;
        loginAsync = m.loginAsync;
        registerAsync = m.registerAsync;
        bootstrapAdminAsync = m.bootstrapAdminAsync;
        updateMeAsync = m.updateMeAsync;
        changePasswordAsync = m.changePasswordAsync;
        logoutAsync = m.logoutAsync;
    },
}));

const listState = vi.hoisted(() => ({ clearAllListState: vi.fn() }));
vi.mock('src/composables/useListState', () => ({
    clearAllListState: listState.clearAllListState,
}));

const overlays = vi.hoisted(() => ({
    clearBuyVerdictCache: vi.fn(),
    clearBeliefs: vi.fn(),
    clearDemand: vi.fn(),
}));
vi.mock('src/composables/useBuyVerdict', () => ({
    clearBuyVerdictCache: overlays.clearBuyVerdictCache,
}));
vi.mock('src/composables/usePantryBeliefs', () => ({
    usePantryBeliefs: () => ({ clear: overlays.clearBeliefs }),
}));
vi.mock('src/composables/usePlannedDemand', () => ({
    usePlannedDemand: () => ({ clear: overlays.clearDemand }),
}));

// Keep the real NormalisedApiError (the store branches on `isNetworkError`),
// but spy setUnauthorizedHandler so the test can drive the captured handler.
vi.mock('src/services/api/axiosHttpClient', async () => {
    const actual = await vi.importActual<typeof AxiosHttpClientModule>(
        'src/services/api/axiosHttpClient',
    );
    return {
        ...actual,
        setUnauthorizedHandler: (handler: (() => void) | null) => {
            m.unauthorizedHandler = handler;
        },
    };
});

// Capacitor is mocked at its own boundary so the real platform helper and the
// real backend-URL store run; `native.on` flips the shell per test.
const native = vi.hoisted(() => ({ on: false }));
vi.mock('@capacitor/core', () => ({
    Capacitor: { isNativePlatform: () => native.on },
}));
vi.mock('@capacitor/preferences', () => ({
    Preferences: {
        get: vi.fn().mockResolvedValue({ value: null }),
        set: vi.fn().mockResolvedValue(undefined),
        remove: vi.fn().mockResolvedValue(undefined),
    },
}));

function user(overrides: Partial<AuthenticatedUser> = {}): AuthenticatedUser {
    return {
        user_id: 'U-1',
        username: 'ben',
        email: 'ben@example.com',
        is_admin: false,
        onboarding_completed_at: '2026-07-01T00:00:00Z',
        email_verified: true,
        // The rest are irrelevant to the store's behaviour; cast keeps the
        // fixture readable without spelling out ~30 preference fields.
        ...overrides,
    } as AuthenticatedUser;
}

function networkError(): NormalisedApiError {
    return new NormalisedApiError({
        status: 0,
        code: 'network_error',
        message: 'Network request failed',
        details: null,
        correlationId: '',
        isNetworkError: true,
        method: 'GET',
        url: '/auth/bootstrap-required',
    });
}

beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    m.unauthorizedHandler = null;
    m.bootstrapRequiredAsync.mockResolvedValue(false);
    m.getMeAsync.mockResolvedValue(user());
    for (const fn of [
        m.loginAsync, m.registerAsync, m.bootstrapAdminAsync,
        m.updateMeAsync,
    ]) fn.mockResolvedValue(user());
    for (const fn of [
        m.changePasswordAsync, m.logoutAsync,
    ]) fn.mockResolvedValue(undefined);
});

describe('authStore — bootstrap probe', () => {
    it('starts unauthenticated and un-bootstrapped', () => {
        const store = useAuthStore();

        expect(store.isAuthenticated()).toBe(false);
        expect(store.isBootstrapped).toBe(false);
        expect(store.bootstrapRequired).toBe(false);
        expect(store.bootstrapError).toBeNull();
    });

    it('an existing session loads the user via /me and marks bootstrapped', async () => {
        const me = user({ user_id: 'U-9', is_admin: true });
        m.getMeAsync.mockResolvedValue(me);
        const store = useAuthStore();

        await store.bootstrapAsync();

        expect(store.currentUser).toEqual(me);
        expect(store.isAuthenticated()).toBe(true);
        expect(store.isAdmin).toBe(true);
        expect(store.isBootstrapped).toBe(true);
        expect(store.bootstrapError).toBeNull();
    });

    it('a fresh install skips the /me probe and flags bootstrapRequired', async () => {
        m.bootstrapRequiredAsync.mockResolvedValue(true);
        const store = useAuthStore();

        await store.bootstrapAsync();

        expect(store.bootstrapRequired).toBe(true);
        expect(store.currentUser).toBeNull();
        expect(store.isBootstrapped).toBe(true);
        expect(m.getMeAsync).not.toHaveBeenCalled(); // the whole point — no 401 probe
    });

    it('shares one in-flight probe between concurrent callers (App.vue + router guard)', async () => {
        const store = useAuthStore();

        // Two awaiters race, exactly like the real boot.
        await Promise.all([store.bootstrapAsync(), store.bootstrapAsync()]);

        expect(m.bootstrapRequiredAsync).toHaveBeenCalledTimes(1);
        expect(m.getMeAsync).toHaveBeenCalledTimes(1);
    });

    it('short-circuits once bootstrapped — no second probe', async () => {
        const store = useAuthStore();
        await store.bootstrapAsync();
        vi.clearAllMocks();

        await store.bootstrapAsync();

        expect(m.bootstrapRequiredAsync).not.toHaveBeenCalled();
    });
});

describe('authStore — boot failure + retry', () => {
    it('parks on a network error with a connection message, then Retry resumes the same loop', async () => {
        m.bootstrapRequiredAsync
            .mockRejectedValueOnce(networkError())
            .mockResolvedValueOnce(false);
        const me = user({ user_id: 'U-2' });
        m.getMeAsync.mockResolvedValue(me);
        const store = useAuthStore();

        const booted = store.bootstrapAsync();
        await vi.waitFor(() => expect(store.bootstrapError).not.toBeNull());

        expect(store.bootstrapError).toContain("reach the server");
        expect(store.isBootstrapped).toBe(false); // still parked, not given up

        store.retryBootstrap();
        await booted;

        expect(store.currentUser).toEqual(me);
        expect(store.isBootstrapped).toBe(true);
        expect(store.bootstrapError).toBeNull();
        expect(m.bootstrapRequiredAsync).toHaveBeenCalledTimes(2); // parked + retried
    });

    it('a non-network failure gets the generic startup message', async () => {
        m.bootstrapRequiredAsync
            .mockRejectedValueOnce(new Error('boom'))
            .mockResolvedValueOnce(false);
        const store = useAuthStore();

        const booted = store.bootstrapAsync();
        await vi.waitFor(() => expect(store.bootstrapError).not.toBeNull());

        expect(store.bootstrapError).toContain('Something went wrong');

        store.retryBootstrap();
        await booted;
        expect(store.isBootstrapped).toBe(true);
    });
});

describe('authStore — credential entry points', () => {
    it('login sets the current user', async () => {
        const me = user({ user_id: 'U-3' });
        m.loginAsync.mockResolvedValue(me);
        const store = useAuthStore();

        await store.loginAsync({ username: 'ben', password: 'pw' });

        expect(m.loginAsync).toHaveBeenCalledWith({ username: 'ben', password: 'pw' });
        expect(store.currentUser).toEqual(me);
        expect(store.isAuthenticated()).toBe(true);
    });

    it('register sets the current user', async () => {
        const me = user({ user_id: 'U-4' });
        m.registerAsync.mockResolvedValue(me);
        const store = useAuthStore();

        await store.registerAsync({ username: 'ben', password: 'pw', email: null });

        expect(store.currentUser).toEqual(me);
    });

    it('first-admin setup logs in and clears bootstrapRequired', async () => {
        m.bootstrapRequiredAsync.mockResolvedValue(true);
        const store = useAuthStore();
        await store.bootstrapAsync();
        expect(store.bootstrapRequired).toBe(true);

        const admin = user({ user_id: 'U-5', is_admin: true });
        m.bootstrapAdminAsync.mockResolvedValue(admin);
        await store.setupAdminAsync({ username: 'ben', password: 'pw', email: 'ben@x.io' });

        expect(store.currentUser).toEqual(admin);
        expect(store.bootstrapRequired).toBe(false); // refresh-after-setup lands authed
    });
});

describe('authStore — sign-out + session expiry (FU-355)', () => {
    it('logout clears the user and wipes per-page list state', async () => {
        const store = useAuthStore();
        await store.loginAsync({ username: 'ben', password: 'pw' });

        await store.logoutAsync();

        expect(store.currentUser).toBeNull();
        expect(store.isAuthenticated()).toBe(false);
        expect(listState.clearAllListState).toHaveBeenCalledTimes(1);
    });

    it('logout still clears local state even when the server call fails', async () => {
        const store = useAuthStore();
        await store.loginAsync({ username: 'ben', password: 'pw' });
        m.logoutAsync.mockRejectedValueOnce(new Error('offline'));

        await expect(store.logoutAsync()).rejects.toThrow('offline');

        expect(store.currentUser).toBeNull(); // finally-block ran
        expect(listState.clearAllListState).toHaveBeenCalledTimes(1);
    });

    it('a silent 401 (via the axios interceptor) clears the user and list state', async () => {
        const store = useAuthStore();
        await store.loginAsync({ username: 'ben', password: 'pw' });
        expect(store.isAuthenticated()).toBe(true);
        expect(m.unauthorizedHandler).toBeTypeOf('function');

        m.unauthorizedHandler?.();

        expect(store.currentUser).toBeNull();
        expect(listState.clearAllListState).toHaveBeenCalledTimes(1);
    });

    it('logout and a silent 401 both drop the per-user overlay caches', async () => {
        const store = useAuthStore();
        await store.loginAsync({ username: 'ben', password: 'pw' });

        await store.logoutAsync();
        expect(overlays.clearBuyVerdictCache).toHaveBeenCalledTimes(1);
        expect(overlays.clearBeliefs).toHaveBeenCalledTimes(1);
        expect(overlays.clearDemand).toHaveBeenCalledTimes(1);

        await store.loginAsync({ username: 'ben', password: 'pw' });
        m.unauthorizedHandler?.();
        expect(overlays.clearBuyVerdictCache).toHaveBeenCalledTimes(2);
        expect(overlays.clearBeliefs).toHaveBeenCalledTimes(2);
        expect(overlays.clearDemand).toHaveBeenCalledTimes(2);
    });
});

describe('authStore — profile updates + avatar cache', () => {
    it('updateMe bumps the image version only when an image field is sent', async () => {
        const me = user({ user_id: 'U-6' });
        m.updateMeAsync.mockResolvedValue(me);
        const store = useAuthStore();

        await store.updateMeAsync({ username: 'renamed' });
        expect(store.imageVersionOf('U-6')).toBe(0); // no avatar touched

        await store.updateMeAsync({ image: 'data:image/png;base64,AAAA' });
        expect(store.imageVersionOf('U-6')).toBe(1); // cache busted

        await store.updateMeAsync({ clear_image: true });
        expect(store.imageVersionOf('U-6')).toBe(2); // clear also busts
    });

    it('bumpImageVersion increments per user id independently', () => {
        const store = useAuthStore();

        expect(store.imageVersionOf('X')).toBe(0);
        store.bumpImageVersion('X');
        store.bumpImageVersion('X');
        expect(store.imageVersionOf('X')).toBe(2);
        expect(store.imageVersionOf('Y')).toBe(0);
    });

    it('refresh re-probes /me and swaps the user in', async () => {
        const store = useAuthStore();
        await store.loginAsync({ username: 'ben', password: 'pw' });

        const refreshed = user({ user_id: 'U-1', onboarding_completed_at: null });
        m.getMeAsync.mockResolvedValue(refreshed);
        await store.refreshAsync();

        expect(store.currentUser).toEqual(refreshed);
    });

    it('changePassword calls through without mutating the user', async () => {
        const me = user({ user_id: 'U-7', email: 'old@x.io' });
        m.loginAsync.mockResolvedValue(me);
        const store = useAuthStore();
        await store.loginAsync({ username: 'ben', password: 'pw' });

        await store.changePasswordAsync({ current_password: 'a', new_password: 'b' });

        expect(m.changePasswordAsync).toHaveBeenCalledWith({ current_password: 'a', new_password: 'b' });
        // A password change must not touch the cached user identity.
        expect(store.currentUser?.email).toBe('old@x.io');
    });
});

describe('authStore — native shell with no backend address', () => {
    beforeEach(async () => {
        native.on = true;
        await clearBackendBaseUrl();
    });

    it('settles signed-out without probing, so the address picker can render', async () => {
        const store = useAuthStore();

        await store.bootstrapAsync();

        expect(store.isBootstrapped).toBe(true);
        expect(store.currentUser).toBeNull();
        expect(store.bootstrapRequired).toBe(false);
        expect(store.bootstrapError).toBeNull();
        expect(m.bootstrapRequiredAsync).not.toHaveBeenCalled();
        expect(m.getMeAsync).not.toHaveBeenCalled();
    });

    it('re-probes the new server once an address is saved', async () => {
        const store = useAuthStore();
        await store.bootstrapAsync();

        await setBackendBaseUrl('dora.example.com');
        const me = user({ user_id: 'U-5' });
        m.getMeAsync.mockResolvedValue(me);
        await store.rebootstrapAsync();

        expect(m.bootstrapRequiredAsync).toHaveBeenCalledTimes(1);
        expect(store.currentUser).toEqual(me);
    });
});

describe('authStore — non-JSON probe answers', () => {
    it('treats an HTML body from /auth/me as signed out', async () => {
        m.getMeAsync.mockResolvedValue('<!doctype html><html></html>');
        const store = useAuthStore();

        await store.bootstrapAsync();

        expect(store.isBootstrapped).toBe(true);
        expect(store.currentUser).toBeNull();
        expect(store.isAuthenticated()).toBe(false);
    });

    it('treats an HTML body on refresh as signed out', async () => {
        const store = useAuthStore();
        await store.loginAsync({ username: 'ben', password: 'pw' });

        m.getMeAsync.mockResolvedValue('<!doctype html><html></html>');
        await store.refreshAsync();

        expect(store.currentUser).toBeNull();
    });

    it('treats a non-boolean bootstrap-required answer as "not required"', async () => {
        m.bootstrapRequiredAsync.mockResolvedValue(undefined);
        const store = useAuthStore();

        await store.bootstrapAsync();

        expect(store.bootstrapRequired).toBe(false);
    });
});
