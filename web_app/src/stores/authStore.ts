import { acceptHMRUpdate, defineStore } from 'pinia';
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
import { NormalisedApiError, setUnauthorizedHandler } from 'src/services/api/axiosHttpClient';
import { clearAllListState } from 'src/composables/useListState';
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

    const runBootstrap = async () => {
        while (!isBootstrapped.value) {
            try {
                // check fresh-install state first. If no admin
                // exists yet, skip the /me probe (it'll 401) and let the
                // router send the user to /setup. The probe is cheap
                // (single COUNT) and explicitly public.
                bootstrapRequired.value = await authApiService.bootstrapRequiredAsync();
                if (bootstrapRequired.value) {
                    currentUser.value = null;
                } else {
                    currentUser.value = await authApiService.getMeAsync();
                }
                isBootstrapped.value = true;
                bootstrapError.value = null;
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

    const retryBootstrap = () => {
        bootstrapError.value = null;
        const resolve = retryResolver;
        retryResolver = null;
        resolve?.();
    };

    /** Force a fresh /me probe (e.g. after the user restarts onboarding so
     *  `onboarding_completed_at` flips back to null and the guard kicks in). */
    const refreshAsync = async () => {
        currentUser.value = await authApiService.getMeAsync();
    };

    const loginAsync = async (command: LoginCommand) => {
        currentUser.value = await authApiService.loginAsync(command);
    };

    const registerAsync = async (command: RegisterCommand) => {
        currentUser.value = await authApiService.registerAsync(command);
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

    const logoutAsync = async () => {
        try {
            await authApiService.logoutAsync();
        } finally {
            currentUser.value = null;
            // FU-355 — clear any per-page filter / search / sort state that
            // `useListState` cached in its module-level Map. Sign-out is a
            // soft router push, not a full reload, so without this the next
            // user on a shared device would inherit the previous session's
            // list-page UI shape. The fallout is minor (per-page view
            // knobs, no sensitive data) but honest is better.
            clearAllListState();
            // The service worker's `dora-api` cache holds this user's actual
            // content (pantry, lists, recipes) keyed by URL alone, with no
            // idea who it belonged to. Now that offline is read-only, that
            // cache IS the offline story and it outlives a sign-out — so drop
            // it, or the next person on this device reads the last one's data.
            void clearApiResponseCache();
        }
    };

    // Called by the axios interceptor when any non-auth-probe request returns
    // 401 — typically means the cookie expired or was cleared server-side.
    const handleSessionExpired = () => {
        currentUser.value = null;
        // FU-355 — same reasoning as `logoutAsync`. A silent 401 could
        // also mean "someone else's session started" on a shared device;
        // don't hand them the previous user's filter shape.
        clearAllListState();
        void clearApiResponseCache();
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
