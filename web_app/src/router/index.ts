import { defineRouter } from '#q-app/wrappers';
import { Notify } from 'quasar';
import { useAuthStore } from 'src/stores/authStore';
import { hasBackendBaseUrl } from 'src/services/api/backendUrl';
import { isNativePlatform } from 'src/helpers/platform';
import { createMemoryHistory, createRouter, createWebHashHistory, createWebHistory } from 'vue-router';

import routes from './routes';

import { PUBLIC_ROUTES } from './publicRoutes';
// Routes we allow incomplete-onboarding users to visit without the redirect.
// /welcome is the wizard itself; the error pages are safety hatches so a crash
// mid-wizard doesn't lock the user out. (The escape from the wizard is now
// "Skip onboarding", which completes onboarding into the app — the old in-wizard
// Sign-out button was removed 2026-08-10, FU-616.)
const ONBOARDING_BYPASS = new Set<string>([
    '/welcome',
    '/errors/not-found',
    '/errors/server',
]);

export default defineRouter(function (/* { store, ssrContext } */) {
    const createHistory = process.env.SERVER
        ? createMemoryHistory
        : process.env.VUE_ROUTER_MODE === 'history'
          ? createWebHistory
          : createWebHashHistory;

    const ROUTER = createRouter({
        // A8 §3 nav-state policy: scroll position persists on browser
        // back/forward within a session (Vue Router populates
        // savedPosition only for those navs), resets on fresh forward
        // nav and on full reload (the history stack is gone). Filters /
        // search / sort follow the same rule via useListState.
        scrollBehavior: (_to, _from, savedPosition) =>
            savedPosition ?? { left: 0, top: 0 },
        routes,

        // Leave this as is and make changes in quasar.conf.js instead!
        // quasar.conf.js -> build -> vueRouterMode
        // quasar.conf.js -> build -> publicPath
        history: createHistory(process.env.VUE_ROUTER_BASE)
    });

    // Navigation errors (lazy-loaded chunk failed to fetch, etc) route the
    // user to /errors/server with a retry rather than leaving them on a
    // half-loaded screen. The raw error message (e.g. "The requested module
    // '.../onboardingContent.ts' does not provide…") is dev-facing and MUST
    // NOT surface to the user — it's logged to the console for debugging
    // instead, and the error page renders without a spurious "ref".
    ROUTER.onError((err) => {
        console.error('Vue Router Error: ' + err.message);
        Notify.create({
            type: 'negative',
            position: 'top',
            message: "Couldn't load that page. Pointing you somewhere safer.",
            timeout: 3500,
        });
        // Avoid an infinite loop if /errors/server itself fails to load.
        if (typeof window !== 'undefined' && window.location.pathname.endsWith('/errors/server')) {
            return;
        }
        try {
            void ROUTER.push({ path: '/errors/server' });
        } catch {
            if (typeof window !== 'undefined') {
                window.location.assign('/');
            }
        }
    });

    // Global auth guard. Bootstraps the session on first navigation, then
    // either lets the request through, redirects to /login (when a protected
    // route needs a session), or redirects to / (when an already-logged-in
    // user lands on /login).
    ROUTER.beforeEach(async (to) => {
        // native app first-run gate. On Capacitor the app is served
        // from https://localhost with no backend behind it; block every
        // route (including /login) until the user has picked an instance.
        if (isNativePlatform() && !hasBackendBaseUrl()) {
            if (to.path !== '/setup/backend') return { path: '/setup/backend' };
            return true;
        }
        if (to.path === '/setup/backend' && !isNativePlatform()) {
            return { path: '/settings/about' };
        }

        const authStore = useAuthStore();
        if (!authStore.isBootstrapped) {
            await authStore.bootstrapAsync();
        }

        // fresh-install gate. While no admin exists, every route
        // funnels to /setup; conversely, an installed system never serves
        // /setup (the operator who saved a /setup tab from earlier doesn't
        // get a second-admin foothold). These checks sit ahead of the
        // login redirect so an unauthed visit on a fresh box lands on the
        // setup wizard, not a useless login page.
        if (authStore.bootstrapRequired) {
            if (to.path !== '/setup') return { path: '/setup' };
            return true;
        }
        if (to.path === '/setup') {
            return { path: authStore.isAuthenticated() ? '/' : '/login' };
        }

        const isPublic = PUBLIC_ROUTES.has(to.path);
        if (!isPublic && !authStore.isAuthenticated()) {
            return { path: '/login', query: { redirect: to.fullPath } };
        }
        if (to.path === '/login' && authStore.isAuthenticated()) {
            return { path: '/' };
        }

        // First-run onboarding (F1): authed users whose wizard isn't
        // finished get bounced to /welcome unless they're heading to a
        // bypass route. If we don't yet know the state (boot before the
        // backend grew the column, for instance), we let them through —
        // never trap the user in an opaque redirect loop.
        if (
            authStore.isAuthenticated()
            && !ONBOARDING_BYPASS.has(to.path)
            && authStore.currentUser?.onboarding_completed_at === null
        ) {
            return { path: '/welcome' };
        }
        // Conversely, an already-completed user landing on /welcome (e.g.
        // a stale tab) is bounced back to the dashboard.
        if (
            to.path === '/welcome'
            && authStore.isAuthenticated()
            && authStore.currentUser?.onboarding_completed_at !== null
        ) {
            return { path: '/' };
        }

        // Block non-admins from the global/admin settings tree. They get
        // bounced to the Account landing page (the post-rebuild settings
        // landing per IMPL_PLAN_SETTINGS_REBUILD §2.3) so they don't end up
        // on a blank screen if they navigated by URL.
        if (to.path.startsWith('/settings/admin') && !authStore.currentUser?.is_admin) {
            return { path: '/settings/account' };
        }
        return true;
    });

    // Browser tab title — picks the nearest matched-route's meta.title so
    // nested settings pages get their leaf title (e.g. "Preferences"), not
    // the parent ("Settings"). Falls back to the app name if a route has
    // no title set.
    const APP_NAME = 'Dashy Dora';
    ROUTER.afterEach((to) => {
        if (typeof document === 'undefined') return;
        const titled = [...to.matched].reverse().find((r) => r.meta?.title);
        const leaf = titled?.meta.title;
        document.title = leaf ? `${leaf} | ${APP_NAME}` : APP_NAME;
    });

    return ROUTER;
});
