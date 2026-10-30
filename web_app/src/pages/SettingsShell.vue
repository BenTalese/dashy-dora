<template>
    <!-- FU-609 / R-036 — app-shell root: <q-page :style-fn> gives the desktop
         dual-scroll shell its height from the *live* layout offset instead of a
         hardcoded `calc(100dvh - 64px)` (which rotted when chrome changed, e.g.
         the OfflineBanner). On mobile the shell falls back to window-scroll — the
         media query overrides the inline height (see styles). -->
    <q-page class="settings-shell" :style-fn="appShellStyleFn">
        <header class="settings-shell__header">
            <!-- FU-346: for admins, the h1 becomes a two-mode segmented
                 toggle. "Settings" holds the personal groups (Account,
                 Preferences, Kitchen setup, About); "Admin" holds the
                 admin sections. The
                 sidebar underneath is filtered to only the active mode's
                 groups — Admin is a peer mode, not a buried third group.
                 Non-admins see the plain h1. Sign-out is the header's
                 right-hand peer of the toggle/title. -->
            <div v-if="isAdmin" class="settings-shell__mode-toggle" role="tablist" aria-label="Settings section">
                <button
                    type="button"
                    role="tab"
                    class="settings-shell__mode-btn"
                    :class="{ 'is-active': mode === 'settings' }"
                    :aria-selected="mode === 'settings'"
                    @click="switchMode('settings')"
                >
                    Settings
                </button>
                <button
                    type="button"
                    role="tab"
                    class="settings-shell__mode-btn"
                    :class="{ 'is-active': mode === 'admin' }"
                    :aria-selected="mode === 'admin'"
                    @click="switchMode('admin')"
                >
                    <q-icon :name="ICONS.shield" size="18px" class="q-mr-xs" />
                    Admin
                </button>
            </div>
            <h1 v-else class="settings-shell__title">Settings</h1>

            <div class="settings-shell__header-actions">
                <!-- Mobile packs this row tight (esp. the admin Settings/Admin
                     toggle), squishing sign-out and letting the page scroll
                     sideways. The app's main top bar already carries a donate
                     button, so this one is a duplicate on <md — hide it, and
                     drop sign-out to icon-only, to free the row (owner call). -->
                <DonateButton v-if="!$q.screen.lt.md" variant="settings" />
                <BaseButton
                    variant="danger-ghost"
                    :icon="ICONS.logout"
                    :label="$q.screen.lt.md ? undefined : 'Sign out'"
                    :loading="signingOut"
                    aria-label="Sign out"
                    @click="onSignOut"
                >
                    <BaseTooltip v-if="$q.screen.lt.md">Sign out</BaseTooltip>
                </BaseButton>
            </div>
        </header>

        <!-- Mobile (<md): top tab strip (§6.3). Shown via CSS below. -->
        <SettingsMobileNav class="settings-shell__mnav" :groups="navGroups" />

        <div class="settings-shell__body">
            <aside class="settings-shell__nav">
                <SettingsNavGroup
                    v-for="group in navGroups"
                    :key="group.label"
                    :label="group.label"
                    :items="group.items"
                    :icon="group.icon"
                    :headerless="group.headerless"
                />
            </aside>

            <main ref="mainEl" class="settings-shell__main">
                <router-view />
            </main>
        </div>
    </q-page>
</template>

<script lang="ts" setup>
    import { appShellStyleFn } from 'src/helpers/appShell';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    import { storeToRefs } from 'pinia';
    import { useQuasar } from 'quasar';
    import { useAuthStore } from 'src/stores/authStore';
    import { useNutritionMatchingStore } from 'src/stores/nutritionMatchingStore';
    import { useUnlinkedIngredientsStore } from 'src/stores/unlinkedIngredientsStore';
    import BaseButton from 'src/components/BaseButton.vue';
    import DonateButton from 'src/components/donate/DonateButton.vue';
    import SettingsNavGroup, { type SettingsNavEntry } from 'src/components/settings/SettingsNavGroup.vue';
    import SettingsMobileNav, { type SettingsNavGroupDef } from 'src/components/settings/SettingsMobileNav.vue';
    import { useScanningEnabled } from 'src/composables/useScanningEnabled';
    import { useNutritionMode } from 'src/composables/useNutritionMode';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import { suppressUnsavedChangesGuard } from 'src/composables/useUnsavedChangesGuard';
    import { computed, nextTick, ref, watch } from 'vue';
    import { useRoute, useRouter } from 'vue-router';

    // IMPL_PLAN_SETTINGS_REBUILD §2.1 — top-level groups, Account first.
    // §6.5 (user pick): nested groupings render as an indented sub-list under a
    // non-clickable sub-header (Recipe taxonomies under Kitchen setup; System
    // under Admin). Captions dropped — label + icon only.
    // §6.3 (user pick): on <md the sidebar is replaced by SettingsMobileNav (a
    // top tab strip). Both navs read the SAME `navGroups` definition (R-003 —
    // one source for the IA), so they can't drift.

    // Owner call 2026-08-14 — "Account" used to be a catch-all holding your
    // identity, five unrelated preference pages, and About (which isn't
    // personal at all). Account is its own destination now, the preferences
    // sit under their own header, and About is a standalone entry of its own
    // at the foot of the list. Both standalone groups are `headerless` —
    // they're single destinations, not categories.
    const accountSections: SettingsNavEntry[] = [
        { path: '/settings/account', label: 'Account', icon: ICONS.person },
    ];

    const preferenceSections: SettingsNavEntry[] = [
        // Palette, not the generic `tune` slider it used to carry — this page is
        // theme/colour/text-size, and `tune` is the admin Features page's icon.
        { path: '/settings/preferences', label: 'Appearance', icon: ICONS.palette },
        { path: '/settings/notifications', label: 'Notifications', icon: ICONS.notifications },
        { path: '/settings/voice', label: 'Voice', icon: ICONS.record_voice_over },
        { path: '/settings/assistant', label: 'Assistant', icon: ICONS.smart_toy },
    ];

    const aboutSections: SettingsNavEntry[] = [
        { path: '/settings/about', label: 'About', icon: ICONS.info },
    ];

    // QR labels only surfaces when scanning is enabled (matches
    // the install-wide gate the page itself enforces). Hiding the nav
    // entry keeps the sidebar honest for installs that never opted in.
    const { scanningEnabled } = useScanningEnabled();
    // Gates the nutrition-matching entry — there's nothing to match against
    // until the install runs complex mode with food data installed.
    const { isComplex: nutritionIsComplex } = useNutritionMode();
    // Money is an install-wide "kitchen setup" concern now (household budget +
    // dollar surfaces), gated on the install money flag — not a personal
    // account section. Hidden entirely when the install has money off.
    const { money: moneyEnabled } = useFeatureFlags();

    // Attention badge on the Unlinked-ingredients nav entry. The store caches
    // the count (server owns the grouping, R-003); we refetch on mount so each
    // settings visit reflects the current backlog, and the page keeps it in
    // sync after every link.
    const unlinkedStore = useUnlinkedIngredientsStore();
    const { count: unlinkedCount } = storeToRefs(unlinkedStore);
    void unlinkedStore.refreshAsync().catch(() => { /* badge just stays 0 */ });

    // Same badge for the nutrition matcher (owner 2026-09-03 — *"count of
    // unmatched items same as unlinked ingredients would be good"*). Only
    // fetched when the entry is actually shown; see the nav entry below.
    const nutritionMatchingStore = useNutritionMatchingStore();
    const { count: nutritionUnmatchedCount } = storeToRefs(nutritionMatchingStore);
    // Only fetched when the nav entry actually exists — in off/simple nutrition
    // mode there is no matching page to badge. `immediate` so the badge is
    // right on first paint rather than one tick late.
    watch(nutritionIsComplex, (isComplex) => {
        if (!isComplex) return;
        void nutritionMatchingStore.ensureLoadedAsync()
            .catch(() => { /* badge just stays 0 */ });
    }, { immediate: true });

    const kitchenSetupSections = computed<SettingsNavEntry[]>(() => {
        const base: SettingsNavEntry[] = [
            { path: '/settings/kitchen-setup/stock-locations', label: 'Stock locations', icon: ICONS.place },
            { path: '/settings/kitchen-setup/stock-groups', label: 'Stock groups', icon: ICONS.tag_multiple },
            { path: '/settings/kitchen-setup/stores', label: 'Stores', icon: ICONS.store },
        ];
        if (moneyEnabled.value) {
            base.push({ path: '/settings/budget', label: 'Budget', icon: ICONS.savings });
        }
        if (scanningEnabled.value) {
            base.push({ path: '/settings/kitchen-setup/qr-labels', label: 'QR labels', icon: ICONS.qr_code });
        }
        // Recipe-ingredient bulk-linker — moved out of Admin → Data
        // (user-curated recipe data, no admin guard on its endpoints).
        base.push({
            path: '/settings/kitchen-setup/unlinked-ingredients',
            label: 'Unlinked ingredients',
            icon: ICONS.link,
            badge: unlinkedCount.value,
        });
        // Complex-mode only: in off/simple there are no food links to make, so
        // the entry is hidden rather than shown leading to an empty page
        // (R-029). It carries the same outstanding-work badge as Unlinked
        // ingredients above — the earlier note here argued a backlog the user
        // opted into shouldn't nag, and the owner reversed that on 2026-09-03:
        // the two pages are the same job, so they read the same way.
        if (nutritionIsComplex.value) {
            base.push({
                path: '/settings/kitchen-setup/nutrition-matching',
                label: 'Nutrition matching',
                icon: ICONS.monitor_heart,
                badge: nutritionUnmatchedCount.value,
            });
        }
        // Recipe taxonomies — flat leaves (no sub-group), each with a
        // distinct icon: globe for world cuisines, shape for categories,
        // blender for equipment/tools, clock for time-of-day meal slots,
        // leaf for dietary tags.
        base.push(
            { path: '/settings/kitchen-setup/recipe-cuisines', label: 'Cuisines', icon: ICONS.public },
            { path: '/settings/kitchen-setup/recipe-categories', label: 'Categories', icon: ICONS.category },
            { path: '/settings/kitchen-setup/recipe-tools', label: 'Tools', icon: ICONS.blender },
            { path: '/settings/kitchen-setup/recipe-meal-slots', label: 'Meal slots', icon: ICONS.schedule },
            { path: '/settings/kitchen-setup/recipe-dietary-tags', label: 'Dietary tags', icon: ICONS.eco },
        );
        return base;
    });

    // Owner call 2026-08-17 — Admin used to be ONE group ("Admin · global")
    // whose contents were mostly buried under a "System" sub-header, so the
    // sidebar read as a single undifferentiated pile with an arbitrary nested
    // level. It's now shaped exactly like the personal side: several
    // top-level groups, each a flat list of destinations, no sub-headers
    // anywhere.
    //
    // Owner call 2026-09-03 — three groups, not five, and no page whose only
    // job is to hold switches that belong somewhere else:
    //   * **Users leads Install.** It was a headerless group of one sitting
    //     above everything, which read as though it were a category.
    //   * **Messaging dissolved into Install.** Email/Push/Voice are things
    //     this install has configured, not a separate concern.
    //   * **Kitchen defaults → Kitchen features**, absorbing the Features
    //     page: each of its switches now sits on the surface it governs
    //     (money here, scanning on Stock, ingestion under Data & access,
    //     the weekly deals mail on Email).
    //   * **Hosting retired** — public URL to Email, audit retention to the
    //     Audit log — and **Image quality** joined Data & access.
    // Every URL that survives is untouched; the two retired pages redirect.
    const adminInstall: SettingsNavEntry[] = [
        { path: '/settings/admin/users', label: 'Users', icon: ICONS.group },
        { path: '/settings/admin/system/region', label: 'Region & locale', icon: ICONS.language },
        { path: '/settings/admin/system/email', label: 'Email', icon: ICONS.mark_email_read },
        { path: '/settings/admin/system/push', label: 'Push notifications', icon: ICONS.notifications_active },
        { path: '/settings/admin/system/voice', label: 'Voice', icon: ICONS.record_voice_over },
    ];

    const adminKitchenFeatures: SettingsNavEntry[] = [
        { path: '/settings/admin/system/stock', label: 'Stock', icon: ICONS.inventory_2 },
        { path: '/settings/admin/system/stocktake', label: 'Stocktake', icon: ICONS.fact_check },
        { path: '/settings/admin/system/cooking', label: 'Cooking', icon: ICONS.restaurant },
        { path: '/settings/admin/system/meal-reconcile', label: 'Meal reconciliation', icon: ICONS.event_note },
        { path: '/settings/admin/system/nutrition', label: 'Nutrition', icon: ICONS.monitor_heart },
        { path: '/settings/admin/system/money', label: 'Money', icon: ICONS.savings },
        { path: '/settings/admin/system/alerts', label: 'Expiring-soon window', icon: ICONS.notifications },
    ];

    // Backup & restore + Import were relocated here from the retired `/data`
    // shell; API access and the Audit log join them because all four are about
    // data leaving, entering, or being accounted for — as are product data
    // ingestion (data arriving from outside) and image quality (how uploaded
    // data is stored), both added 2026-09-03.
    const adminData: SettingsNavEntry[] = [
        { path: '/settings/admin/system/ingestion', label: 'Product data ingestion', icon: ICONS.cloud_upload },
        { path: '/settings/admin/data/backup', label: 'Backup & restore', icon: ICONS.cloud_download },
        { path: '/settings/admin/data/import', label: 'Import', icon: ICONS.file_upload },
        { path: '/settings/admin/system/images', label: 'Image quality', icon: ICONS.image },
        { path: '/settings/admin/api-access', label: 'API access', icon: ICONS.key },
        { path: '/settings/admin/audit-log', label: 'Audit log', icon: ICONS.history },
    ];

    const $q = useQuasar();
    const authStore = useAuthStore();
    const { isAdmin } = storeToRefs(authStore);

    // Independent-scroll shell: the sidebar and the main pane each own their
    // own overflow (see styles below), so the *window* never needs to scroll
    // while inside settings. That in turn means the router's global
    // `scrollBehavior: {top:0}` has nothing to yank when the user clicks a
    // nav item after scrolling deep into a section — no jarring jump. But
    // switching leaves should still land the user at the top of the new
    // section (typical settings expectation), so reset the main pane's
    // scrollTop on route path change. `nextTick` waits for the fade
    // transition's new component to mount before we scroll it.
    const mainEl = ref<HTMLElement | null>(null);
    const route = useRoute();
    watch(
        () => route.path,
        () => {
            void nextTick(() => {
                if (mainEl.value) mainEl.value.scrollTop = 0;
            });
        },
    );

    // FU-346: mode is derived from the URL, so refresh / back-button /
    // deep-link all preserve it without a separate stored flag. Any
    // /settings/admin/* path is Admin mode; everything else is Settings.
    const mode = computed<'settings' | 'admin'>(() =>
        route.path.startsWith('/settings/admin') ? 'admin' : 'settings',
    );

    const router = useRouter();

    const signingOut = ref(false);
    async function onSignOut() {
        signingOut.value = true;
        // Sign-out is an intentional exit; suppress the unsaved-changes
        // guard so a page whose draft-vs-user diff goes stale the moment
        // logout clears currentUser (e.g. AccountSettings) doesn't fire
        // a false-positive "discard unsaved changes?" prompt. Cancel on
        // that prompt would also strand the app on a settings page while
        // already logged-out.
        try {
            await suppressUnsavedChangesGuard(async () => {
                await authStore.logoutAsync();
                await router.push('/login');
            });
        } finally {
            signingOut.value = false;
        }
    }

    function switchMode(next: 'settings' | 'admin') {
        if (next === mode.value) return;
        // Land on the first item of the mode's sidebar so the destination
        // matches what the user is about to see. `/settings/admin/users`
        // is the first admin section; `/settings/account` is the first
        // personal one.
        void router.push(next === 'admin' ? '/settings/admin/users' : '/settings/account');
    }

    const navGroups = computed<SettingsNavGroupDef[]>(() => {
        if (isAdmin.value && mode.value === 'admin') {
            return [
                { label: 'Install', items: adminInstall, icon: ICONS.settings },
                { label: 'Kitchen features', items: adminKitchenFeatures, icon: ICONS.restaurant },
                { label: 'Data & access', items: adminData, icon: ICONS.storage },
            ];
        }
        // Owner 2026-09-01 reverted the 2026-08-29 move: About sits back at
        // the bottom of the sidebar. Pairing it with Account read as though
        // it were part of your personal settings, which it isn't — it's the
        // install's own "what is this / what version" page, and the end of
        // the list is where that belongs.
        return [
            { label: 'Account', items: accountSections, headerless: true },
            { label: 'Preferences', items: preferenceSections },
            { label: 'Kitchen setup', items: kitchenSetupSections.value },
            { label: 'About', items: aboutSections, headerless: true },
        ];
    });

</script>

<style scoped lang="scss">
    /* Desktop shell (>= md): fill the viewport under the app toolbar, then
       let the sidebar and the main pane each scroll independently. Keeps
       the sidebar always in view no matter how far the user scrolls, and
       (with the scrollTop reset above) means clicking a nav item after
       scrolling deep into a section doesn't jarringly jump the whole
       window — the router's window-scroll reset now has nothing to yank
       because the window itself isn't the scroller. */
    .settings-shell {
        /* FU-609 / R-036 — height comes from the <q-page :style-fn> (viewport −
           live layout offset), not a hardcoded `calc(100dvh - 64px)` that
           ignored the real chrome height. Desktop fills the viewport under the
           toolbar, then the sidebar + main pane each scroll independently. */
        max-width: 1280px;
        margin: 0 auto;
        padding: 28px 28px 0;
        display: flex;
        flex-direction: column;
        min-height: 0;
    }
    .settings-shell__header {
        margin-bottom: 20px;
        flex: 0 0 auto;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
    }
    .settings-shell__header-actions {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .settings-shell__title {
        margin: 0;
        font-size: 1.5rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        color: var(--text-primary);
        line-height: 1.2;
    }
    /* FU-346 — admin-only mode toggle sits where the h1 does. Segmented
       control: two pills inside a bordered pill container. Active pill
       takes the brand-primary background; inactive pill stays flat but
       shows a hover affordance so it clearly reads as clickable. */
    .settings-shell__mode-toggle {
        display: inline-flex;
        gap: 4px;
        padding: 4px;
        border-radius: 999px;
        background: var(--surface-sunken);
        border: 1px solid var(--border-default);
    }
    .settings-shell__mode-btn {
        display: inline-flex;
        align-items: center;
        padding: 8px 20px;
        border: none;
        border-radius: 999px;
        background: transparent;
        color: var(--text-primary);
        font: inherit;
        font-size: 1.15rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        line-height: 1.2;
        cursor: pointer;
        transition: background 0.15s ease, color 0.15s ease;
    }
    .settings-shell__mode-btn:hover:not(.is-active) {
        background: var(--overlay-hover);
    }
    .settings-shell__mode-btn:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    .settings-shell__mode-btn.is-active {
        background: var(--brand-primary);
        color: var(--text-inverse);
    }
    /* D-004 — the toggle's buttons run 32px tall at the phone font size; a
       finger gets the 44px floor. Keyed to the pointer, not the width (R-085). */
    @media (pointer: coarse) {
        .settings-shell__mode-btn {
            min-height: 44px;
        }
    }
    .settings-shell__body {
        flex: 1 1 auto;
        min-height: 0; /* required for children's overflow to compute */
        display: grid;
        grid-template-columns: 232px 1fr;
        gap: 40px;
        align-items: stretch;
    }
    .settings-shell__nav {
        display: flex;
        flex-direction: column;
        gap: 4px;
        overflow-y: auto;
        min-height: 0;
        /* Breathing room so the last nav item isn't flush to the viewport
           edge when the list overflows. */
        padding-bottom: 20px;
    }
    .settings-shell__main {
        min-width: 0;
        overflow-y: auto;
        min-height: 0;
        /* The main pane owns bottom padding so long forms don't jam into
           the viewport edge; the shell itself has padding: 0 on the bottom
           so the scrollbar runs the full height. */
        padding-bottom: 28px;
        /* Gap between the page content and the scrollbar (same fix as the
           Stock Overview list): the bar is painted at this scroller's outer
           edge, so a right pad holds the content clear of it instead of the
           bar overlapping the form. `scrollbar-gutter: stable` reserves the
           space so content width doesn't jump between short (no-scroll) and
           long (scroll) pages. */
        padding-right: var(--space-4);
        scrollbar-gutter: stable;
    }

    // §6.3 — the mobile tab strip is hidden on desktop; the sidebar shows.
    .settings-shell__mnav {
        display: none;
    }

    /* Mobile: fall back to a single-column, window-scrolled layout. The
       top-tab strip replaces the sidebar; there's no dual-scroll to
       preserve, and internal overflow on a mobile viewport just makes the
       page feel truncated. */
    @media (max-width: 1023px) {
        .settings-shell {
            /* !important overrides the inline height the <q-page :style-fn> sets
               (FU-609) so mobile reverts to a single window-scrolled column. */
            height: auto !important;
            padding: 20px;
            display: block;
        }
        /* Keep the header row within the viewport: let the flex children shrink
           (min-width:0) and trim the admin mode-toggle so [Settings|Admin] +
           icon-only sign-out fit even on a ~320px screen — no sideways scroll. */
        .settings-shell__header,
        .settings-shell__header-actions,
        .settings-shell__mode-toggle {
            min-width: 0;
        }
        .settings-shell__header { gap: 12px; }
        .settings-shell__mode-btn {
            font-size: 1rem;
            padding: 6px 14px;
        }
        .settings-shell__nav { display: none; }
        .settings-shell__mnav {
            display: flex;
            margin-bottom: 20px;
        }
        .settings-shell__body {
            display: block;
        }
        .settings-shell__main {
            overflow: visible;
            padding-bottom: 0;
        }
    }
</style>
