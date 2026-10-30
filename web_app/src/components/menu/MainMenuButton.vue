<template>
    <!-- `role="link"` overrides QItem's hard-coded `role="listitem"`: the strip
         is a row of links, not a list, and a listitem outside a list is an
         ARIA error (axe `aria-required-parent`) that also hides the link from
         a screen reader's links rotor. -->
    <q-item
        v-if="href"
        :href="href"
        target="_blank"
        rel="noopener"
        :class="{ 'is-expanded': isExpanded }"
        class="dora-mainMenuButton"
        role="link"
        no-caps
        tag="a"
    >
        <div class="dora-mainMenuButton-inner column items-center justify-center">
            <q-icon :name="icon" class="dora-mainMenuButton-icon" />
            <div class="dora-mainMenuButton-label">{{ label }}</div>
        </div>
    </q-item>
    <!-- Quasar's router active classes are blanked here for the same reason as
         SideMenuButton: `.q-item.q-router-link--active` sets
         `color: var(--q-primary)` at a higher specificity than
         `.dora-mainMenuButton-active`, so an active strip button rendered
         primary instead of accent. `isActive` is the single source of truth. -->
    <q-item
        v-else
        :to="link"
        :class="{ 'is-expanded': isExpanded, 'dora-mainMenuButton-active': isActive }"
        class="dora-mainMenuButton"
        active-class=""
        exact-active-class=""
        role="link"
        no-caps
    >
        <div class="dora-mainMenuButton-inner column items-center justify-center">
            <q-icon :name="icon" class="dora-mainMenuButton-icon" />
            <div class="dora-mainMenuButton-label">{{ label }}</div>
        </div>
    </q-item>
</template>

<script setup lang="ts">
    import type { MenuButtonProps } from './menuButtonProps';
    import { useMenuLinkActive } from './useMenuLinkActive';

    const props = defineProps<MenuButtonProps & { isExpanded: boolean }>();
    const isActive = useMenuLinkActive(() => props.link, () => props.activePrefixes);
</script>

<style scoped lang="scss">
    .dora-mainMenuButton {
        flex: 1 1 0;
        min-width: 0;
        padding: 0;
        min-height: 60px;
        border-radius: 10px;
        position: relative;
        overflow: hidden;
        background: transparent;
        // `color` matches the strip's slide indicator (0.42s + same easing)
        // so icon + label tint slides in sync with the accent bar
        // underneath rather than snapping ahead of it.
        transition:
            background-color 0.3s ease,
            color 0.42s cubic-bezier(0.65, 0, 0.2, 1);

        &::before {
            content: '';
            position: absolute;
            inset: 2px;
            border-radius: 10px;
            background: var(--overlay-hover-on-coloured);
            opacity: 0;
            transform: scale(0.85);
            transition: opacity 0.25s ease, transform 0.25s ease;
            pointer-events: none;
        }

        &:hover::before {
            opacity: 1;
            transform: scale(1);
        }

        &.dora-mainMenuButton-active::before {
            opacity: 0;
        }
    }

    .dora-mainMenuButton-inner {
        width: 100%;
        height: 100%;
        padding: 4px 6px;
        position: relative;
        z-index: 1;
    }

    .dora-mainMenuButton-icon {
        font-size: clamp(22px, 2.2vw, 32px);
        transition: transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1),
            margin 0.35s ease;
    }

    .is-expanded .dora-mainMenuButton-icon {
        transform: scale(0.78) translateY(-2px);
    }

    .dora-mainMenuButton:hover .dora-mainMenuButton-icon {
        transform: scale(0.78) translateY(-3px) rotate(-4deg);
    }

    .dora-mainMenuButton-label {
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.2px;
        line-height: 1;
        max-height: 0;
        opacity: 0;
        overflow: hidden;
        transform: translateY(8px);
        transition:
            opacity 0.3s ease,
            max-height 0.3s ease,
            transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
        text-align: center;
        white-space: nowrap;
    }

    .is-expanded .dora-mainMenuButton-label,
    .dora-mainMenuButton:hover .dora-mainMenuButton-label {
        font-size: clamp(0.85rem, 1vw, 1.05rem);
        max-height: 28px;
        opacity: 1;
        transform: translateY(0);
        margin-top: 3px;
    }

    .dora-mainMenuButton-active {
        color: var(--q-accent);
    }

    // Hover tint on inactive buttons — previews the active accent colour,
    // animated on the same timing as the active-route slide indicator
    // (see `transition` above). `:not(...)` excludes the active button so
    // there's no specificity flicker (CSS would otherwise let `:hover`
    // override the active rule).
    .dora-mainMenuButton:not(.dora-mainMenuButton-active):hover {
        color: var(--q-accent);
    }

    // Quasar's q-item ships a built-in hover/focus overlay
    // (`.q-focus-helper`) that was stacking on top of the custom
    // `::before` overlay above — inactive-hover rendered as two
    // concentric rounded rectangles ("double outline"), while active
    // (where `::before` is hidden) only showed the Quasar overlay. Hide
    // the Quasar helper so our `::before` is the single source of truth.
    .dora-mainMenuButton :deep(.q-focus-helper) {
        display: none;
    }
</style>
