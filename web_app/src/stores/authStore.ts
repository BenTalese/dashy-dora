import { acceptHMRUpdate, defineStore } from 'pinia';
import { PUBLIC_ROUTES, currentHashPath } from 'src/router/publicRoutes';
import type { AuthenticatedUser } from 'src/models/auth';
import type {
    BootstrapAdminCommand,
    ChangePasswordCommand,
    LoginCommand,
    RegisterCommand,
    UpdateMeCommand
} from 'src/services/api/authApiService';
import { clearApiResponseCache } from 'src/services/api/apiResponseCache';
import AuthApiService from 'src/services/api/authApiService';
import { hasBackendBaseUrl } from 'src/services/api/backendUrl';
import { isNativePlatform } from 'src/helpers/platform';
import { NormalisedApiError, setUnauthorizedHandler } from 'src/services/api/axiosHttpClient';
import { clearAllListState } from 'src/composables/useListState';
import { clearBuyVerdictCache } from 'src/composables/useBuyVerdict';
import { usePantryBeliefs } from 'src/composables/usePantryBeliefs';
import { usePlannedDemand } from 'src/composables/usePlannedDemand';
import { computed, readonly, ref } from 'vue';

const authApiService = new AuthApiService();

export const useAuthStore = defineStore('auth', () => {
    const currentUser = ref<AuthenticatedUser | null>(null);
    // Tracks the boot probe so route guards can wait for it instead of
    // redirecting to /login on the very first navigation.
    const isBootstrapped = ref(false);
    // Set when the boot probe fails to reach the backend. The splash screen
    // watches this and surfaces a retry button instead of hanging silently.
    const bootstrapError = ref<string | null>(null);
    // fresh-install flag. True when no user exists yet; the
    // router uses this to route to /setup instead of /login. Cleared once
    // setupAdminAsync() succeeds (so refresh-after-setup falls through to
    // the normal login-or-authed path).
    const bootstrapRequired = ref(false);

    // Resolver for the in-flight bootstrap waiter: when bootstrap fails we
    // park the loop on a promise, then the splash's Retry button resolves it
    // to make us attempt the probe again.
    let retryResolver: (() => void) | null = null;
    // App.vue front-loads bootstrap and the router guard also awaits it.
    // We share the same in-flight promise so the second caller doesn't kick
    // off a duplicate /auth/me request.
    let inflightBootstrap: Promise<void> | null = null;

    const isAuthenticated = () => currentUser.value !== null;
    const isAdmin = computed(() => currentUser.value?.is_admin === true);

    // Settings rebuild Phase 4 — per-user profile-picture version counter,
    // bumped whenever an `image`/`clear_image` field is sent on updateMeAsync
    // (mirrors stockItemStore's `imageVersionOf`). Any consumer painting
    // the picture with `imageVersionOf(id)` in its path refetches after an
    // upload / clear (`UserAvatar`).
    const imageVersions = ref<Record<string, number>>({});
    function imageVersionOf(userId: string): number {
        return imageVersions.value[userId] ?? 0;
    }
    function bumpImageVersion(userId: string): void {
        imageVersions.value = {
            ...imageVersions.value,
            [userId]: (imageVersions.value[userId] ?? 0) + 1,
        };
    }

    // A response that isn't a user object (e.g. an HTML page served by a
    // WebView or proxy at a non-API address) means "not signed in", never a
    // truthy currentUser.
    function asUser(payload: unknown): AuthenticatedUser | null {
        if (typeof payload !== 'object' || payload === null) return null;
        return typeof (payload as { user_id?: unknown }).user_id === 'string'
            ? payload as AuthenticatedUser
            : null;
    }

    const probeAsync = async () => {
        // Native with no saved address: there's no backend to ask (the base
        // URL would resolve against the WebView's own origin). Settle as
        // signed-out so the router can render the address picker.
        if (isNativePlatform() && !hasBackendBaseUrl()) {
            bootstrapRequired.value = false;
            currentUser.value = null;
            isBootstrapped.value = true;
            bootstrapError.value = null;
            return;
        }
        // check fresh-install state first. If no admin
        // exists yet, skip the /me probe (it'll 401) and let the
        // router send the user to /setup. The probe is cheap
        // (single COUNT) and explicitly public.
        bootstrapRequired.value = (await authApiService.bootstrapRequiredAsync()) === true;
        if (bootstrapRequired.value) {
            currentUser.value = null;
        } else {
            currentUser.value = asUser(await authApiService.getMeAsync());
        }
        isBootstrapped.value = true;
        bootstrapError.value = null;
    };

    const runBootstrap = async () => {
        while (!isBootstrapped.value) {
            try {
                await probeAsync();
            } catch (error) {
                bootstrapError.value =
                    error instanceof NormalisedApiError && error.isNetworkError
                        ? "Can't reach the server. Check your connection and try again."
                        : 'Something went wrong starting up. Try again in a moment.';
                await new Promise<void>((resolve) => {
                    retryResolver = resolve;
                });
            }
        }
    };

    const bootstrapAsync = (): Promise<void> => {
        if (isBootstrapped.value) return Promise.resolve();
        if (!inflightBootstrap) inflightBootstrap = runBootstrap();
        return inflightBootstrap;
    };

    /** Re-run the boot probe in place after the backend address changes, so
     *  the fresh-install / signed-in state reflects the new server. Leaves
     *  the router view mounted; errors propagate to the caller. */
    const rebootstrapAsync = async (): Promise<void> => {
        await probeAsync();
    };

    const retryBootstrap = () => {
        bootstrapError.value = null;
        const resolve = retryResolver;
        retryResolver = null;
        resolve?.();
    };

    /** Force a fresh /me probe (e.g. after the user restarts onboarding so
     *  `onboarding_completed_at` flips back to null and the guard kicks in). */
    const refreshAsync = async () => {
        currentUser.value = asUser(await authApiService.getMeAsync());
    };

    const loginAsync = async (command: LoginCommand) => {
        currentUser.value = await authApiService.loginAsync(command);
    };

    /** Resolves to whether a verification mail went out, so the page can say
     *  "check your inbox" (finalisation 15-R3). */
    const registerAsync = async (command: RegisterCommand): Promise<boolean> => {
        const result = await authApiService.registerAsync(command);
        const { verification_sent, ...user } = result;
        currentUser.value = user;
        return verification_sent === true;
    };

    /** FU-200 — create the first admin and auto-login. The server 410s
     *  once any user exists, so this should only be invoked from the
     *  /setup page (the router guards that). Clears `bootstrapRequired`
     *  on success so a refresh-after-setup lands on the normal authed
     *  routes. */
    const setupAdminAsync = async (command: BootstrapAdminCommand) => {
        currentUser.value = await authApiService.bootstrapAdminAsync(command);
        bootstrapRequired.value = false;
    };

    const updateMeAsync = async (command: UpdateMeCommand) => {
        const touchedImage = 'image' in command || 'clear_image' in command;
        currentUser.value = await authApiService.updateMeAsync(command);
        // Bust the avatar cache everywhere it's painted once the server
        // confirms the image change.
        if (touchedImage && currentUser.value) {
            bumpImageVersion(currentUser.value.user_id);
        }
    };

    const changePasswordAsync = async (command: ChangePasswordCommand) => {
        await authApiService.changePasswordAsync(command);
    };

    /** Sign-out is a soft router push, not a full reload, so every
     *  module-level cache would otherwise hand the next person on a shared
     *  device the previous session's state. */
    const dropSessionState = () => {
        currentUser.value = null;
        // Per-page filter / search / sort state cached by `useListState`.
        clearAllListState();
        // The service worker's `dora-api` cache holds this user's actual
        // content (pantry, lists, recipes) keyed by URL alone, with no idea
        // who it belonged to, and it outlives a sign-out.
        void clearApiResponseCache();
        // Per-user overlays: the beliefs are gated on a per-user pref, and
        // the verdicts and planned demand are this user's own facts.
        clearBuyVerdictCache();
        usePantryBeliefs().clear();
        usePlannedDemand().clear();
    };

    const logoutAsync = async () => {
        try {
            await authApiService.logoutAsync();
        } finally {
            dropSessionState();
        }
    };

    // Called by the axios interceptor when any non-auth-probe request returns
    // 401 — typically means the cookie expired or was cleared server-side.
    const handleSessionExpired = () => {
        // A silent 401 could also mean "someone else's session started" on
        // a shared device.
        dropSessionState();
        // Send them to sign in with a way back (finalisation 15-R5): clearing
        // the user alone left emptied cards on screen until the next
        // navigation. A hash assignment, because the store can't import the
        // router without a cycle; the router guard does the rest.
        const path = currentHashPath();
        if (typeof window !== 'undefined' && !PUBLIC_ROUTES.has(path)) {
            window.location.hash = `#/login?redirect=${encodeURIComponent(path)}`;
        }
    };
    setUnauthorizedHandler(handleSessionExpired);

    return {
        currentUser: readonly(currentUser),
        isBootstrapped: readonly(isBootstrapped),
        bootstrapError: readonly(bootstrapError),
        bootstrapRequired: readonly(bootstrapRequired),
        isAdmin,
        isAuthenticated,
        imageVersionOf,
        bumpImageVersion,
        bootstrapAsync,
        rebootstrapAsync,
        retryBootstrap,
        refreshAsync,
        loginAsync,
        registerAsync,
        setupAdminAsync,
        updateMeAsync,
        changePasswordAsync,
        logoutAsync
    };
});

if (import.meta.hot) {
    import.meta.hot.accept(acceptHMRUpdate(useAuthStore, import.meta.hot));
}
