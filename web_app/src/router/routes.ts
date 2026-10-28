import 'vue-router';
import type { RouteRecordRaw } from 'vue-router';

declare module 'vue-router' {
    interface RouteMeta {
        // Set on every navigable route; router afterEach writes
        // `${title} · Dashy Dora` to document.title so browser tabs are
        // useful when several are open. Dynamic detail pages can override
        // at runtime by setting document.title in onMounted.
        title?: string;
    }
}

const routes: RouteRecordRaw[] = [
    // Login lives outside MainLayout so the drawer/header don't render while
    // the user is signed out.
    {
        path: '/login',
        component: () => import('pages/LoginPage.vue'),
        meta: { title: 'Sign In' }
    },
    // fresh-install first-admin setup. Lives outside MainLayout
    // for the same reason as /login. The router guard sends visitors here
    // when bootstrapRequired is true, and bounces them away once an admin
    // exists.
    {
        path: '/setup',
        component: () => import('pages/SetupAdminPage.vue'),
        meta: { title: 'Set Up Dashy Dora' },
    },
    // native app first-run instance picker. Only reachable when
    // Capacitor.isNativePlatform() is true and no backend URL is stored
    // yet; the router guard bounces web visitors to /settings/about.
    {
        path: '/setup/backend',
        component: () => import('pages/setup/BackendSetupPage.vue'),
        meta: { title: 'Choose Your Instance' },
    },
    // ── A1 out-of-band auth flows. Each one lives outside MainLayout so
    // signed-out users (or someone clicking a verify link in a fresh
    // browser) doesn't see the nav chrome.
    {
        path: '/verify-email',
        component: () => import('pages/VerifyEmailPage.vue'),
        meta: { title: 'Verify Email' },
    },
    {
        path: '/forgot-password',
        component: () => import('pages/ForgotPasswordPage.vue'),
        meta: { title: 'Forgot Password' },
    },
    {
        path: '/reset-password',
        component: () => import('pages/ResetPasswordPage.vue'),
        meta: { title: 'Reset Password' },
    },
    // First-run wizard. Uses its own minimal layout so the nav drawer /
    // dashboard chrome don't peek through while the user is still being
    // set up. Router guard forces incomplete users here.
    {
        path: '/welcome',
        component: () => import('layouts/WelcomeLayout.vue'),
        children: [
            {
                path: '',
                component: () => import('pages/onboarding/WelcomeWizard.vue'),
                meta: { title: 'Welcome' }
            },
        ],
    },
    {
        path: '/',
        component: () => import('layouts/MainLayout.vue'),
        children: [
            // Dashboard is the landing page; stock overview moves to /stock.
            { path: '', component: () => import('pages/DashboardPage.vue'), meta: { title: 'Dashboard' } },
            { path: 'stock', component: () => import('pages/StockOverview.vue'), meta: { title: 'Stock' } },
            // PROPOSAL_STOCKTAKE_MODE §5.1 — no landing page. Tapping
            // Stocktake drops straight into the focused runner; empty-
            // queue state is handled inside the runner itself. The
            // legacy `/stocktake/run` sub-route is redirected below for
            // any bookmark / deep link that predates this change.
            { path: 'stocktake', component: () => import('pages/StocktakeRunner.vue'), meta: { title: 'Stocktake' } },
            { path: 'stocktake/run', redirect: '/stocktake' },
            { path: 'stock/:id', component: () => import('pages/StockItemDetailPage.vue'), meta: { title: 'Stock Item' } },
            // Phase D / FU-186 — the in-app `/product-search` route is gone.
            // The Product Search nav entry now opens `AppSetting.product_search_url`
            // in a new tab when product data is present. No route remains here.
            { path: 'price-history', component: () => import('pages/PriceHistoryPage.vue'), meta: { title: 'Price History' } },
            { path: 'my-products', component: () => import('pages/MyProductsPage.vue'), meta: { title: 'My Products' } },
            { path: 'help', component: () => import('pages/HelpPage.vue'), meta: { title: 'Help' } },
            { path: 'help/whats-new', component: () => import('pages/HelpChangelogPage.vue'), meta: { title: "What's new" } },
            { path: 'help/about', component: () => import('pages/HelpAboutPage.vue'), meta: { title: 'About' } },
            // The alerts page was removed 2026-10-15 (owner): the bell panel
            // is the whole surface and the per-kind toggles live in Settings →
            // Notifications. Old links open the bell instead.
            { path: 'alerts', redirect: { path: '/', query: { alerts: 'open' } } },
            { path: 'help/:group', component: () => import('pages/HelpTopicPage.vue'), meta: { title: 'Help' } },
            // A8 + 2026-06-12 migration — recipe routes all live under
            // `/cookbook` (the cookbook is the page; a recipe is an
            // item in it). Legacy `/recipes*` redirects were retired
            // 2026-06-12 — pre-release, no live bookmarks to preserve,
            // no external links written yet. A user that types
            // `/recipes/<id>` now hits the 404 page (which is fine).
            { path: 'cookbook', component: () => import('pages/RecipesOverview.vue'), meta: { title: 'Cookbook' } },
            // The redesigned page (2026-08-20) is now the only one. It ran in
            // parallel at `cookbook/:id/new` while the two were compared; the
            // owner picked it on 2026-08-26 and the original was deleted with
            // that route (FU-688).
            { path: 'cookbook/:id', component: () => import('pages/RecipeDetailPage.vue'), meta: { title: 'Recipe' } },
            { path: 'cookbook/:id/cook', component: () => import('pages/RecipeCookMode.vue'), meta: { title: 'Cook Mode' } },
            { path: 'meal-plans', component: () => import('pages/MealPlansOverview.vue'), meta: { title: 'Meal Plans' } },
            // FU-304 closed 2026-07-07 — Direction A won the A/B experiment;
            // `/meal-plans/board` (Direction B) is retired. Redirect any
            // deep-links / bookmarks back to the surviving planner surface.
            { path: 'meal-plans/board', redirect: '/meal-plans' },
            // FU-308 (2026-07-07) — page repurposed to Rotating template
            // sets only; per-template CRUD moved to the planner's drawer.
            // Route path kept for existing deep-links / bookmarks.
            { path: 'meal-plans/templates', component: () => import('pages/MealPlanTemplatesPage.vue'), meta: { title: 'Rotating Template Sets' } },
            // FU-317 Chunk 5 — reconcile page (single-runner-style, one
            // entry at a time, five verbs). Empty state is handled by the
            // runner itself; no separate landing.
            { path: 'meal-plans/reconcile', component: () => import('pages/MealReconcilePage.vue'), meta: { title: 'Reconcile Past Meals' } },
            {
                path: 'shopping-lists',
                component: () => import('pages/ShoppingListsOverview.vue'),
                meta: { title: 'Shopping Lists' },
                // the detail page is the canonical surface
                // (with a list-selector in its header). The landing's job is
                // to pick a target list and route there. We do it as a
                // **route-level `beforeEnter`** rather than an in-component
                // `router.replace` in `onMounted`: a route guard resolves the
                // final destination before any component mounts, so the user
                // never sees the landing page flash then re-navigate. (This
                // also historically dodged a transition wedge from the
                // MainLayout router-view's <FadeTransition mode="out-in">;
                // out-in was removed after it began blanking pages under the
                // <q-page> roots, but the beforeEnter remains the cleaner
                // pattern regardless.)
                beforeEnter: async () => {
                    const { useShoppingListStore } = await import('src/stores/shoppingListStore');
                    const store = useShoppingListStore();
                    if (store.summaries.length === 0 && !store.loading) {
                        try {
                            await store.refreshAsync();
                        } catch {
                            // Fall through — Overview will render the
                            // empty / error state.
                        }
                    }
                    // UX-v2 §3.3 — the "next up" pick is a server-owned rule
                    // (live shop > first date-wise after the last completed >
                    // earliest pending > most recently completed). The guard
                    // just follows the flag; no date logic lives here.
                    const next = store.summaries.find((s) => s.is_next_up);
                    if (next) return `/shopping-lists/${next.shopping_list_id}`;
                    // No lists at all — render the empty state.
                    return;
                },
            },
            { path: 'shopping-lists/templates', component: () => import('pages/ShoppingListTemplates.vue'), meta: { title: 'Shopping List Templates' } },
            // UX-v2: detail is the single shopping surface for every status
            // (S4: plural title; the old /shop route + page were merged in).
            { path: 'shopping-lists/:id', component: () => import('pages/ShoppingListDetail.vue'), meta: { title: 'Shopping Lists' } },
            // PWA-shortcut landing page that redirects to whichever
            // list is live / next up. Lightweight stub; see
            // pages/ShopNowRedirect.vue.
            { path: 'shop-now', component: () => import('pages/ShopNowRedirect.vue'), meta: { title: 'Shop Now' } },
            { path: 'reports', component: () => import('pages/ReportsPage.vue'), meta: { title: 'Reports' } },
            // C-waste W6 — the standalone /waste page is gone. Capture
            // moved to a row action on the stock-item expiry dropdown;
            // expiry rescue surfaces via Needs-your-attention on the
            // dashboard. Bookmarks 404 by design (no redirect — pre-
            // release, per PROPOSAL_WASTE_MINIMISATION §2 D10).
            // In-layout error pages (F3). These keep the header/drawer
            // around so the user can navigate away without a full reload.
            // The bare-URL catch-all at the bottom of this file still
            // renders the fullscreen ErrorNotFound page for typo'd routes.
            {
                path: 'errors/not-found',
                component: () => import('pages/errors/ErrorPageNotFound.vue'),
                meta: { title: 'Not Found' }
            },
            {
                path: 'errors/server',
                component: () => import('pages/errors/ErrorServer.vue'),
                meta: { title: 'Server Error' }
            },
            // the `/data` shell + its DataManagement.vue host are
            // retired. Backup + Import now live under Settings → Admin →
            // Data (see the settings route tree below). Every child path
            // that used to hang off `/data` is preserved as a redirect so
            // stale bookmarks, prior emails, and the retired PWA shortcut
            // still land somewhere useful; the parent `/data` redirect
            // catches direct visits to the shell URL itself.
            {
                path: 'data',
                redirect: '/settings/admin/data/backup'
            },
            {
                path: 'data/backup',
                redirect: '/settings/admin/data/backup'
            },
            {
                path: 'data/import',
                redirect: '/settings/admin/data/import'
            },
            {
                path: 'data/barcodes',
                redirect: '/settings/kitchen-setup/qr-labels'
            },
            {
                // The redirect points at Backup so a stale bookmark lands
                // on the closest sibling rather than 404. Print now lives
                // in-context on each printable surface.
                path: 'data/export',
                redirect: '/settings/admin/data/backup'
            },
            // Settings shell hosts sub-routes via its own <router-view>.
            // Three top-level groups (IMPL_PLAN_SETTINGS_REBUILD §2.1):
            //   Account — identity + per-user preferences
            //   Kitchen setup — user-curated reference data (stock taxonomy,
            //     stores, recipe taxonomies)
            //   Admin · global — install-wide concerns (gated by the router
            //     guard in `router/index.ts`)
            // Phase 1 = routing structure only; Phase 2 splits the monoliths
            // (Preferences, RecipeVocab, System) into focused pages.
            {
                path: 'settings',
                component: () => import('pages/SettingsShell.vue'),
                redirect: '/settings/account',
                meta: { title: 'Settings' },
                children: [
                    // Account group ────────────────────────────────────────
                    {
                        path: 'account',
                        component: () => import('pages/settings/AccountSettings.vue'),
                        meta: { title: 'Account' }
                    },
                    {
                        // Phase 2: Appearance-only after the split below.
                        path: 'preferences',
                        component: () => import('pages/settings/PreferencesSettings.vue'),
                        meta: { title: 'Appearance' }
                    },
                    {
                        path: 'notifications',
                        component: () => import('pages/settings/NotificationsSettings.vue'),
                        meta: { title: 'Notifications' }
                    },
                    {
                        path: 'budget',
                        component: () => import('pages/settings/BudgetSettings.vue'),
                        meta: { title: 'Budget' }
                    },
                    {
                        path: 'voice',
                        component: () => import('pages/settings/VoiceSettings.vue'),
                        meta: { title: 'Voice' }
                    },
                    {
                        // `/settings/nutrition` retired 2026-08-14 — nutrition
                        // is install-wide, configured at
                        // /settings/admin/system/nutrition. Redirect so old
                        // links and bookmarks land somewhere sensible rather
                        // than 404ing.
                        path: 'nutrition',
                        redirect: '/settings/admin/system/nutrition'
                    },
                    {
                        // per-user Assistant config (provider + URL/model/API
                        // key) + per-user AI-mode opt-in. There is no
                        // install-wide master switch — AI mode is per-user only.
                        path: 'assistant',
                        component: () => import('pages/settings/AssistantSettings.vue'),
                        meta: { title: 'Assistant' }
                    },
                    {
                        path: 'about',
                        component: () => import('pages/settings/AboutSettings.vue'),
                        meta: { title: 'About' }
                    },
                    // Kitchen setup group ──────────────────────────────────
                    {
                        path: 'kitchen-setup/stock-locations',
                        component: () => import('pages/settings/StockLocationsSettings.vue'),
                        meta: { title: 'Stock Locations' }
                    },
                    {
                        path: 'kitchen-setup/stock-groups',
                        component: () => import('pages/settings/StockGroupsSettings.vue'),
                        meta: { title: 'Stock Groups' }
                    },
                    // Stores moved out of Admin per §2.1 — it's user-curated
                    // retail data, not install governance.
                    {
                        path: 'kitchen-setup/stores',
                        component: () => import('pages/settings/StoresSettings.vue'),
                        meta: { title: 'Stores' }
                    },
                    // Phase 2: Recipe vocab splits 1 → 5 focused pages. The
                    // first four share TaxonomyManagerPage; dietary tags keeps
                    // its bespoke editor (grouping field).
                    {
                        path: 'kitchen-setup/recipe-cuisines',
                        component: () => import('pages/settings/RecipeCuisinesSettings.vue'),
                        meta: { title: 'Cuisines' }
                    },
                    {
                        path: 'kitchen-setup/recipe-categories',
                        component: () => import('pages/settings/RecipeCategoriesSettings.vue'),
                        meta: { title: 'Categories' }
                    },
                    {
                        path: 'kitchen-setup/recipe-tools',
                        component: () => import('pages/settings/RecipeToolsSettings.vue'),
                        meta: { title: 'Tools' }
                    },
                    {
                        path: 'kitchen-setup/recipe-meal-slots',
                        component: () => import('pages/settings/RecipeMealSlotsSettings.vue'),
                        meta: { title: 'Meal Slots' }
                    },
                    {
                        path: 'kitchen-setup/recipe-dietary-tags',
                        component: () => import('pages/settings/RecipeDietaryTagsSettings.vue'),
                        meta: { title: 'Dietary Tags' }
                    },
                    // QR labels (Print sheet). Relocated from
                    // `/data/barcodes`; the old page's Scan tab was retired
                    // (duplicative with Stock Overview's scan button). Still
                    // gated by the install-wide `scanning_enabled` flag; the
                    // sidebar hides the entry when off, the page itself shows
                    // an "ask an admin to enable it" banner if reached by URL.
                    {
                        path: 'kitchen-setup/qr-labels',
                        component: () => import('pages/settings/QrLabels.vue'),
                        meta: { title: 'QR Labels' }
                    },
                    // IMPL_PLAN_RECIPE_IMPORTER §Chunk 6 — bulk-linker for
                    // paste-imported ingredients that landed unlinked. Moved
                    // out of Admin → Data: it's user-curated recipe data any
                    // recipe author cleans up, and its endpoints carry no
                    // admin guard.
                    {
                        path: 'kitchen-setup/unlinked-ingredients',
                        component: () => import('pages/settings/UnlinkedIngredientsSettings.vue'),
                        meta: { title: 'Unlinked Ingredients' }
                    },
                    // Complex-mode nutrition matching — the same bulk-resolve
                    // shape as unlinked ingredients above, for stock items with
                    // no food link. Sits under kitchen-setup for the same
                    // reason: user-curated pantry data, no admin guard on its
                    // endpoints. The nav entry is hidden unless the install
                    // runs complex nutrition; the page itself degrades to an
                    // empty list, since the API answers empty in other modes.
                    {
                        path: 'kitchen-setup/nutrition-matching',
                        component: () => import('pages/settings/NutritionMatchingSettings.vue'),
                        meta: { title: 'Nutrition Matching' }
                    },
                    // Backwards-compat redirects for moved/split routes.
                    // Bookmarks, email deep-links and HelpPage entries that
                    // shipped under the old paths keep working. Drop these
                    // only when there's no surface still referencing them.
                    {
                        path: 'stock-locations',
                        redirect: '/settings/kitchen-setup/stock-locations'
                    },
                    {
                        path: 'stock-groups',
                        redirect: '/settings/kitchen-setup/stock-groups'
                    },
                    {
                        // Old single recipe-vocab page → first of the five.
                        path: 'recipe-vocab',
                        redirect: '/settings/kitchen-setup/recipe-cuisines'
                    },
                    {
                        path: 'kitchen-setup/recipe-vocab',
                        redirect: '/settings/kitchen-setup/recipe-cuisines'
                    },
                    {
                        path: 'admin/stores',
                        redirect: '/settings/kitchen-setup/stores'
                    },
                    // Admin · global group ─────────────────────────────────
                    {
                        path: 'admin/users',
                        component: () => import('pages/settings/UsersAdminSettings.vue'),
                        meta: { title: 'Users' }
                    },
                    // Region: household timezone + currency + display locale
                    // combined onto one page (owner call 2026-08-12 — the three
                    // are one "where are we" concern). Replaced the old split
                    // timezone/locale pages (pre-release, no redirects kept).
                    {
                        path: 'admin/system/region',
                        component: () => import('pages/settings/AdminSystemRegionSettings.vue'),
                        meta: { title: 'Region & Locale' }
                    },
                    {
                        path: 'admin/system/alerts',
                        component: () => import('pages/settings/AdminSystemAlertsSettings.vue'),
                        meta: { title: 'Alert Thresholds' }
                    },
                    // (The install-wide AI master toggle + its admin page were
                    // removed 2026-08-12 — AI mode is per-user only. No
                    // redirect kept: pre-release, no bookmarks to preserve.)
                    // The Features page was dissolved 2026-09-03 (owner) — a
                    // pile of unrelated install switches, each of which now
                    // sits on the surface it governs: money here, scanning on
                    // Stock, ingestion + product search under Data & access,
                    // the weekly deals mail on Email. `meal_planning_enabled`
                    // went entirely (it gated nothing). Redirect lands on Money,
                    // the flag with the widest reach of the four.
                    {
                        path: 'admin/system/features',
                        redirect: '/settings/admin/system/money'
                    },
                    {
                        path: 'admin/system/money',
                        component: () => import('pages/settings/AdminSystemMoneySettings.vue'),
                        meta: { title: 'Money' }
                    },
                    {
                        path: 'admin/system/ingestion',
                        component: () => import('pages/settings/AdminSystemIngestionSettings.vue'),
                        meta: { title: 'Product data ingestion' }
                    },
                    {
                        // Nutrition is install-wide (2026-08-14) — mode +
                        // complex-mode source config live here, not on a
                        // per-user page.
                        path: 'admin/system/nutrition',
                        component: () => import('pages/settings/AdminSystemNutritionSettings.vue'),
                        meta: { title: 'Nutrition' }
                    },
                    // four focused System pages carrying the
                    // operational config that used to live in DORA_* env vars.
                    {
                        path: 'admin/system/email',
                        component: () => import('pages/settings/AdminSystemEmailSettings.vue'),
                        meta: { title: 'Email' }
                    },
                    {
                        path: 'admin/system/push',
                        component: () => import('pages/settings/AdminSystemPushSettings.vue'),
                        meta: { title: 'Push Notifications' }
                    },
                    {
                        path: 'admin/system/voice',
                        component: () => import('pages/settings/AdminSystemVoiceSettings.vue'),
                        meta: { title: 'Voice' }
                    },
                    // Hosting retired 2026-09-03 (owner) — a two-setting page
                    // whose two settings had nothing to do with each other. The
                    // public URL is what Dora writes into emails, so it moved to
                    // Email; audit retention moved onto the Audit log it prunes.
                    {
                        path: 'admin/system/hosting',
                        redirect: '/settings/admin/system/email'
                    },
                    // PROPOSAL_STOCKTAKE_MODE §8 — new focused page for the
                    // two global stocktake dials (default cadence + Auto
                    // self-tuning). The old "Default stocktake reminder"
                    // section on the Alerts page is superseded by this.
                    {
                        path: 'admin/system/stocktake',
                        component: () => import('pages/settings/AdminSystemStocktakeSettings.vue'),
                        meta: { title: 'Stocktake' }
                    },
                    // FU-511 — install-wide auto-add mode
                    // (off / essential-only / all). Collapsed here from the
                    // retired per-item `StockItem.auto_add_when_low` toggle.
                    {
                        path: 'admin/system/stock',
                        component: () => import('pages/settings/AdminSystemStockSettings.vue'),
                        meta: { title: 'Stock' }
                    },
                    // FU-317 Chunk 6 — install-wide meal-plan reconcile
                    // posture (auto-drain vs hold-for-confirm).
                    {
                        path: 'admin/system/meal-reconcile',
                        component: () => import('pages/settings/AdminSystemMealReconcileSettings.vue'),
                        meta: { title: 'Meal Reconciliation' }
                    },
                    // FU-615 — install-wide household cooking config
                    // (headcount + cook-style), moved off the per-user record.
                    {
                        path: 'admin/system/cooking',
                        component: () => import('pages/settings/AdminSystemCookingSettings.vue'),
                        meta: { title: 'Cooking' }
                    },
                    // 2026-08-23 owner feedback — image-encode knobs lifted out
                    // of Backup & Restore onto their own page.
                    {
                        path: 'admin/system/images',
                        component: () => import('pages/settings/AdminSystemImageSettings.vue'),
                        meta: { title: 'Image quality' }
                    },
                    {
                        // Old single System page → first System page.
                        path: 'admin/system',
                        redirect: '/settings/admin/system/region'
                    },
                    {
                        path: 'admin/audit-log',
                        component: () => import('pages/settings/AuditLogSettings.vue'),
                        meta: { title: 'Audit Log' }
                    },
                    {
                        path: 'admin/api-access',
                        component: () => import('pages/settings/ApiAccessSettings.vue'),
                        meta: { title: 'API Access' }
                    },
                    // Data sub-group under Admin: relocated
                    // Backup/Restore + Import from the retired `/data`
                    // shell. Admin-only via the same isAdmin router
                    // guard that covers the rest of `admin/*`; the
                    // backend endpoints these pages call carry the
                    // shared @require_admin dep (FU-198 closure).
                    {
                        path: 'admin/data/backup',
                        component: () => import('pages/settings/AdminDataBackupRestore.vue'),
                        meta: { title: 'Backup & Restore' }
                    },
                    {
                        path: 'admin/data/import',
                        component: () => import('pages/settings/AdminDataImport.vue'),
                        meta: { title: 'Import' }
                    },
                    // Old admin path kept as a redirect — the page moved to
                    // Kitchen setup (see below) since it's user-curated recipe
                    // data, not install governance; its endpoints were never
                    // admin-guarded.
                    {
                        path: 'admin/data/unlinked-ingredients',
                        redirect: '/settings/kitchen-setup/unlinked-ingredients'
                    }
                ]
            }
        ]
    },

    // Always leave this as last one,
    // but you can also remove it
    {
        path: '/:catchAll(.*)*',
        component: () => import('pages/ErrorNotFound.vue'),
        meta: { title: 'Not Found' }
    }
];

export default routes;
