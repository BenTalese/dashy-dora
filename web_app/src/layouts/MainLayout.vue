<template>
    <q-layout view="hHh LpR lFf">
        <q-header
            class="dora-toolbar-surface"
            :reveal="$q.screen.lt.md"
        >
            <q-toolbar class="dora-titlebar">
                <HamburgerButton
                    :is-visible="$q.screen.lt.md"
                    :on-click="toggleLeftDrawer"
                />

                <!-- Desktop only. On mobile the mascot + wordmark ate the
                     width the page title needs (long titles were being
                     pushed out of the toolbar entirely); the Dashboard is
                     reachable from the drawer instead — see `linksList`. -->
                <ApplicationLogo v-if="$q.screen.gt.sm" />

                <PageTitle
                    v-if="$q.screen.lt.md && route.meta.title"
                    :label="String(route.meta.title)"
                />

                <MainMenuButtonStrip
                    :is-visible="$q.screen.gt.sm"
                    :menu-links="linksList"
                />

                <!-- Mobile fallback filler: shove the right-hand buttons
                     (alerts, profile) to the far edge on routes with no
                     title. When a title *is* present it flexes and does
                     the filling itself — a second growing element here
                     would halve the width the title can use.
                     Desktop already fills the middle with MainMenuButtonStrip. -->
                <q-space v-if="$q.screen.lt.md && !route.meta.title" />

                <!-- Right-hand cluster: mobile gets a trimmed-down gap
                     (`q-mr-xs`, 4px) rather than the desktop margins — the
                     buttons read as separate targets without costing the page
                     title the ~12px desktop spacing eats. -->
                <AlertsBell
                    v-if="currentUser"
                    :class="$q.screen.gt.sm ? 'q-mr-sm' : 'q-mr-xs'"
                />

                <!-- Support Dora — donation CTA. Dora is free & open-source;
                     this is the gentle, always-available "chip in" affordance
                     (own --donate pink, own DonateMenu). -->
                <DonateButton
                    v-if="currentUser"
                    variant="header"
                    class="q-mr-xs"
                />

                <!-- Help & guides — peer of the profile button.
                     Direct nav to `/help`; carries the same active-ring
                     affordance as the avatar so the header advertises
                     "you're somewhere reachable from here" when on a
                     /help/* route. -->
                <BaseButton
                    v-if="currentUser && $q.screen.gt.sm"
                    variant="icon"
                    aria-label="Help & guides"
                    to="/help"
                >
                    <span
                        class="dora-headerActiveRing"
                        :class="{ 'is-active': isHelpActive }"
                    >
                        <q-icon :name="ICONS.help_outline" size="24px" />
                    </span>
                    <BaseTooltip>Help &amp; guides</BaseTooltip>
                </BaseButton>

                <!-- Account / settings — direct nav, no dropdown.
                     Sign-out lives on the Account settings page; the
                     header dropdown was a duplicate path that mostly
                     hid the destination behind an extra click. -->
                <BaseButton
                    v-if="currentUser"
                    variant="icon"
                    aria-label="Account settings"
                    to="/settings/account"
                >
                    <!-- Settings rebuild Phase 4: profile picture when set,
                         else the original account-circle icon. Wrapping
                         span carries the box-shadow ring since q-avatar's
                         circular mask would clip its own shadow. -->
                    <span
                        class="dora-headerActiveRing"
                        :class="{ 'is-active': isAvatarActive }"
                    >
                        <UserAvatar
                            :user-id="currentUser.user_id"
                            :has-image="currentUser.has_image"
                            size="30px"
                            fallback="icon"
                            :fallback-icon="ICONS.account_circle"
                            :username="currentUser.username"
                        />
                    </span>
                    <BaseTooltip>{{ currentUser.username }}</BaseTooltip>
                </BaseButton>
            </q-toolbar>
        </q-header>

        <q-drawer
            v-if="$q.screen.lt.md"
            v-model="leftDrawerOpen"
            bordered
            side="left"
        >
            <q-list>
                <SideMenuButton
                    v-for="link in linksList"
                    :key="link.label"
                    v-bind="link"
                />
            </q-list>
        </q-drawer>

        <q-page-container>
            <!-- Pinned under the header when we can't reach the API (or the
                 browser says we're offline). Sticky so it stays visible
                 while the user keeps scrolling/working. -->
            <OfflineBanner />
            <!-- A newer frontend build is cached and one reload away.
                 Dismissible, shown to every user. -->
            <UpdateBanner />
            <!-- No mode="out-in" here. Once the page roots became <q-page>
                 (FU-609 / R-036), out-in started wedging the transition state
                 machine: the leaving page unmounts but the entering page never
                 mounts, so every client-side nav lands on a blank screen (a
                 full reload paints fine because no transition is in flight).
                 A plain cross-fade swaps reliably; the ~200ms overlap of two
                 q-pages is imperceptible. -->
            <router-view v-slot="{ Component }">
                <FadeTransition>
                    <component :is="Component" />
                </FadeTransition>
            </router-view>
        </q-page-container>

        <!-- Dora help assistant. Lives inside the authenticated layout so
             the login page stays clean; bubble + chat are always present
             across every authenticated route. -->
        <!-- FU-360.6 — a user can hide the helper entirely via Settings →
             Assistant. `show_assistant` defaults true; `!== false` keeps the
             bubble for older sessions whose user object predates the field. -->
        <DoraBubble v-if="currentUser && currentUser.show_assistant !== false" />

        <!-- Global quick-add sheet. Mounted once; any screen pops it via
             useQuickAdd().openQuickAdd(). -->
        <QuickAddSheet v-if="currentUser" />

        <!-- global log-price sheet. Mounted once; any screen pops
             it via useLogPrice().openLogPrice(). -->
        <LogPriceSheet v-if="currentUser" />

        <!-- Keyboard-shortcut cheatsheet (opened with "?"). -->
        <ShortcutsCheatsheet v-if="currentUser" />
    </q-layout>
</template>

<script setup lang="ts">
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import { ICONS } from 'src/style/icons';
    import { storeToRefs } from 'pinia';
    import { useQuasar } from 'quasar';
    import AlertsBell from 'src/components/AlertsBell.vue';
    import DonateButton from 'src/components/donate/DonateButton.vue';
    import UserAvatar from 'src/components/UserAvatar.vue';
    import DoraBubble from 'src/components/dora/DoraBubble.vue';
    import OfflineBanner from 'src/components/OfflineBanner.vue';
    import UpdateBanner from 'src/components/UpdateBanner.vue';
    import FadeTransition from 'src/components/transitions/FadeTransition.vue';
    import QuickAddSheet from 'src/components/QuickAddSheet.vue';
    import LogPriceSheet from 'src/components/LogPriceSheet.vue';
    import ShortcutsCheatsheet from 'src/components/ShortcutsCheatsheet.vue';
    import ApplicationLogo from 'src/components/menu/ApplicationLogo.vue';
    import HamburgerButton from 'src/components/menu/HamburgerButton.vue';
    import MainMenuButtonStrip from 'src/components/menu/MainMenuButtonStrip.vue';
    import PageTitle from 'src/components/menu/PageTitle.vue';
    import SideMenuButton from 'src/components/menu/SideMenuButton.vue';
    import type { MenuButtonProps } from 'src/components/menu/menuButtonProps';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import { useProductSearchUrl } from 'src/composables/useProductSearchUrl';
    import { useShortcut, useShortcutRegistry } from 'src/composables/useShortcut';
    import { useAuthStore } from 'src/stores/authStore';
    import { computed, ref } from 'vue';
    import { useRoute, useRouter } from 'vue-router';

    const $q = useQuasar();
    const route = useRoute();
    const router = useRouter();
    const authStore = useAuthStore();
    const { currentUser } = storeToRefs(authStore);

    // ── Global keyboard shortcuts (S5) ──────────────────────────────────
    const { openCheatsheet } = useShortcutRegistry();
    useShortcut([
        {
            keys: '?',
            scope: 'Global',
            description: 'Show keyboard shortcuts',
            handler: openCheatsheet,
        },
        {
            keys: '/',
            scope: 'Global',
            description: 'Focus search / go to Stock',
            handler: () => {
                // On Stock the page registers its own "/" to focus the filter;
                // it wins (newest). Elsewhere we route there (search autofocuses).
                if (router.currentRoute.value.path !== '/stock') void router.push('/stock');
            },
        },
        { keys: 'g s', scope: 'Global', description: 'Go to Stock', handler: () => void router.push('/stock') },
        { keys: 'g l', scope: 'Global', description: 'Go to Shopping Lists', handler: () => void router.push('/shopping-lists') },
        { keys: 'g r', scope: 'Global', description: 'Go to Cookbook', handler: () => void router.push('/cookbook') },
        { keys: 'g d', scope: 'Global', description: 'Go to Dashboard', handler: () => void router.push('/') },
        { keys: 'g h', scope: 'Global', description: 'Go to Help', handler: () => void router.push('/help') },
    ]);

    // Command palette retired 2026-06-12 — see worklog + FU-029.
    // `useShortcut` / `useShortcutRegistry` (keyboard shortcuts) stay;
    // they were always orthogonal to the palette.

    // Phase D / FU-186 — the "Product Search" entry:
    //   - hidden when products is off (no product data ⇒ no search surface)
    //   - hidden when no `product_search_url` is configured — the entry exists
    //     only to open that URL, and a nav item that dead-ends on an admin-only
    //     settings page is useless to a normal user (owner call: setting the
    //     URL, in Settings → Features, is what makes the button appear).
    //   - otherwise: external link (new tab) to the configured URL. The
    //     destination (a sibling companion / a static page / whatever the
    //     operator runs) is **never named** here.
    const features = useFeatureFlags();
    const productSearch = useProductSearchUrl();

    const productSearchEntry = computed<MenuButtonProps | null>(() => {
        if (!features.products.value) return null;
        const url = productSearch.url.value.trim();
        if (!url) return null;
        return {
            label: 'Product Search',
            icon: ICONS.search,
            link: '',
            href: url
        };
    });

    const linksList = computed<MenuButtonProps[]>(() => {
        const base: MenuButtonProps[] = [];
        // Mobile hides the brand mascot (the toolbar's only route to `/`),
        // so the drawer carries the Dashboard entry instead. Desktop keeps
        // the mascot as the home affordance and doesn't need the duplicate.
        if ($q.screen.lt.md) {
            base.push({ label: 'Dashboard', icon: ICONS.dashboard, link: '/' });
        }
        base.push({ label: 'Stock', icon: ICONS.inventory_2, link: '/stock' });
        if (productSearchEntry.value) {
            base.push(productSearchEntry.value);
        }
        // My Products is gated on the same data-presence flag
        // as the rest of the products overlay — hide it entirely when
        // no products exist. Previously this entry slipped through
        // (productSearchEntry above was gated but the push below wasn't),
        // so the nav still advertised the surface on a products-empty
        // install.
        if (features.products.value) {
            base.push({ label: 'My Products', icon: ICONS.shopping_bag, link: '/my-products' });
        }
        base.push(
            { label: 'Cookbook', icon: ICONS.menu_book, link: '/cookbook' },
            { label: 'Meal Plans', icon: ICONS.calendar_month, link: '/meal-plans' },
            { label: 'Shopping Lists', icon: ICONS.shopping_cart, link: '/shopping-lists' },
            { label: 'Reports', icon: ICONS.insights, link: '/reports' },
            // "Data" main-menu entry retired. The `/data` shell
            // itself is gone; Backup/Restore and Import now live under
            // Settings → Admin → Data (admin-only). A top-level slot for
            // an admin-only workflow was confusing for the 90% case, and
            // admins can still reach it in two clicks from the header
            // avatar (Settings → Admin · global → Data → Backup).
            // C-waste W6 — Waste nav slot removed; near-expiry items
            // surface via Needs-your-attention on the dashboard and
            // through Dora's `expiry_rescue` tool. No replacement slot
            // (PROPOSAL_WASTE_MINIMISATION §2 D11).
            // Settings used to live here too; it's already in the user
            // dropdown (header avatar). Duplicating it in the main menu was
            // confusing — removed.
        );
        // On mobile the header's Help icon is hidden (space); mirror it into
        // the drawer as a nav row so the guides stay reachable. Desktop
        // keeps the header icon and doesn't need a duplicate here.
        if ($q.screen.lt.md) {
            base.push({ label: 'Help & Guides', icon: ICONS.help_outline, link: '/help' });
        }
        return base;
    });

    // Two peer header buttons (Help + Account) each carry the active-ring
    // affordance that mirrors the main-menu strip's underline indicator.
    // Avatar lights up under `/settings/*`; Help lights up under `/help`
    // / `/help/*`. Same prefix-match style as `useMenuLinkActive`.
    function matchesPrefix(prefix: string): boolean {
        return route.path === prefix || route.path.startsWith(prefix + '/');
    }
    const isAvatarActive = computed(() => matchesPrefix('/settings'));
    const isHelpActive = computed(() => matchesPrefix('/help'));

    const leftDrawerOpen = ref(false);

    function toggleLeftDrawer() {
        leftDrawerOpen.value = !leftDrawerOpen.value;
    }

</script>

<style scoped lang="scss">
    /* Toolbar reads its own surface + text tokens (not brand-primary)
       so themes with a yellow primary (Lemon Tart) don't render
       yellow-on-yellow Dora text or invisible active-nav links. Each
       theme controls --surface-toolbar in themes.scss. */
    /* Owner feedback 2026-09-03: *"Just noticed lemon tart dark theme you
       can't see any colour for the menu bar. Is this intentional or a
       mistake?"* A mistake, in two parts — Lemon Tart Dark's own toolbar
       value is fixed in themes.scss, and the header had nothing separating
       it from the page in *any* theme whose bar sits close to its page
       colour. The hairline is drawn from `--text-on-toolbar` at 14% rather
       than from `--divider`, so it works out to a faint light line on a dark
       or saturated bar and a faint dark one on a light bar (Salt & Pepper) —
       one rule, no per-theme token. */
    .dora-toolbar-surface {
        background: var(--surface-toolbar);
        color: var(--text-on-toolbar);
        border-bottom: 1px solid color-mix(in srgb, var(--text-on-toolbar) 14%, transparent);
    }
    .dora-titlebar {
        height: 64px;
        gap: 8px;
        padding: 0 12px;
    }

    /* Mobile (Quasar lt.md): tighter bar so a long page title has room.
       Only the *visual* size comes down — glyph and avatar shrink, the
       36px button hit box is left alone so this doesn't push the header
       controls further under the D-004 touch-target floor. */
    @media (max-width: 1023px) {
        .dora-titlebar {
            height: 52px;
            gap: 2px;
            padding: 0 4px;
        }
        .dora-titlebar :deep(.dora-btn--icon) .q-icon {
            font-size: 22px;
        }
        .dora-titlebar :deep(.q-avatar) {
            font-size: 26px;
        }
    }

    /* Shared active-ring for header peer buttons (Help + Account).
       Each button's inner content (avatar or icon) is wrapped in a
       `.dora-headerActiveRing` span that takes an `is-active` class
       from the route. Box-shadow puts the ring outside the circular
       click target without shifting layout — the avatar's mask would
       have clipped its own shadow, hence the wrapping span (the icon
       button gets the same wrap for visual consistency).

       Two shadows: a 3px ring in the accent colour (matches the main-
       menu strip's slide indicator height) + a soft glow (same
       `color-mix` shape as the strip's box-shadow). Activation also
       fires a one-shot pulse that starts in the strip's "moving"
       colour (`--nav-slide-flash`) and settles into the resting
       accent — the header button doesn't translate position the way
       the strip indicator does, so the colour transition IS the
       motion. */
    .dora-headerActiveRing {
        display: inline-flex;
        border-radius: 50%;
        box-shadow:
            0 0 0 3px transparent,
            0 0 10px transparent;
        transition: box-shadow var(--motion-slow) var(--motion-ease);
    }
    .dora-headerActiveRing.is-active {
        box-shadow:
            0 0 0 3px var(--q-accent),
            0 0 10px color-mix(in srgb, var(--brand-accent) 55%, transparent);
        animation: dora-headerActiveRing-pulse 0.55s cubic-bezier(0.4, 0, 0.2, 1);
    }

    @keyframes dora-headerActiveRing-pulse {
        0% {
            box-shadow:
                0 0 0 5px var(--nav-slide-flash),
                0 0 18px color-mix(in srgb, var(--nav-slide-flash) 70%, transparent);
        }
        55% {
            box-shadow:
                0 0 0 4px color-mix(in srgb, var(--nav-slide-flash) 60%, var(--q-accent)),
                0 0 14px color-mix(in srgb, var(--nav-slide-flash) 35%, transparent);
        }
        100% {
            box-shadow:
                0 0 0 3px var(--q-accent),
                0 0 10px color-mix(in srgb, var(--brand-accent) 55%, transparent);
        }
    }

    /* Reduced-motion users: the pulse IS the motion, so suppress it
       entirely and let the static accent ring appear without the
       flash-coloured beat. Resting state still applies. */
    @media (prefers-reduced-motion: reduce) {
        .dora-headerActiveRing.is-active {
            animation: none;
        }
    }
</style>
