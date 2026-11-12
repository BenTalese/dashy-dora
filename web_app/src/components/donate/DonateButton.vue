<template>
    <!-- Toolbar: compact pink disc in the header's right-hand cluster. -->
    <a
        v-if="variant === 'header'"
        class="donate-btn donate-btn--header"
        :href="DONATION_URL"
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Support Dora"
    >
        <span class="donate-btn__disc donate-btn__disc--pulse">
            <q-icon :name="ICONS.favorite" size="20px" />
        </span>
        <BaseTooltip>Support Dora 💗</BaseTooltip>
    </a>

    <!-- Settings: labelled pink pill, sits beside Sign out. -->
    <a
        v-else-if="variant === 'settings'"
        class="donate-btn donate-btn--settings"
        :href="DONATION_URL"
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Support Dora"
    >
        <q-icon :name="ICONS.favorite" size="18px" />
        <span>Support Dora</span>
    </a>

    <!-- Auth shell: fixed, gently pulsing FAB in the bottom-left corner. -->
    <a
        v-else
        class="donate-btn donate-btn--floating"
        :href="DONATION_URL"
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Support Dora"
    >
        <q-icon :name="ICONS.favorite" size="26px" />
        <BaseTooltip anchor="center right" self="center left">Support Dora 💗</BaseTooltip>
    </a>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    import { DONATION_URL } from 'src/config/donationLinks';

    // One donation control, three placements, all linking straight to the
    // single DONATION_URL (R-003) in a new tab. Its own pink --donate token
    // (not a semantic role, not the sparingly-used --brand-accent) with white
    // glyph so contrast holds on any toolbar/theme colour; aria-label + tooltip per D-005; the pulse is
    // neutralised by the global prefers-reduced-motion kill-switch (motion.scss)
    // and an explicit override below.
    withDefaults(
        defineProps<{
            variant?: 'header' | 'settings' | 'floating';
        }>(),
        { variant: 'header' },
    );
</script>

<style scoped>
    .donate-btn {
        appearance: none;
        border: none;
        background: transparent;
        padding: 0;
        cursor: pointer;
        color: var(--donate-contrast);
        text-decoration: none;
    }

    /* ── Shared pink disc (header + the FAB reuse the same fill/glow) ── */
    .donate-btn__disc {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        border-radius: var(--radius-full);
        background: var(--donate);
        color: var(--donate-contrast);
        box-shadow: 0 2px 8px var(--donate-glow);
        transition: background var(--motion-fast) var(--motion-ease);
    }

    /* ── Header: 44px hit area (D-004) around a 32px disc. ── */
    .donate-btn--header {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 44px;
        height: 44px;
        border-radius: var(--radius-full);
    }
    .donate-btn--header:hover .donate-btn__disc {
        background: var(--donate-strong);
    }
    .donate-btn--header:focus-visible {
        outline: 2px solid var(--donate-contrast);
        outline-offset: -2px;
    }
    .donate-btn__disc--pulse {
        animation: donate-pulse 2.6s ease-in-out infinite;
    }

    /* ── Settings: pink pill next to Sign out. ── */
    .donate-btn--settings {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        min-height: 44px; /* D-004 tap-target floor */
        padding: 0 16px;
        border-radius: var(--radius-pill);
        background: var(--donate);
        color: var(--donate-contrast);
        font: inherit;
        font-weight: 700;
        box-shadow: 0 2px 10px var(--donate-glow);
        transition:
            background var(--motion-fast) var(--motion-ease),
            transform var(--motion-fast) var(--motion-ease);
    }
    .donate-btn--settings:hover {
        background: var(--donate-strong);
    }
    .donate-btn--settings:active {
        transform: scale(0.97);
    }
    .donate-btn--settings:focus-visible {
        outline: 2px solid var(--donate);
        outline-offset: 2px;
    }

    /* ── Auth shell: fixed bottom-left FAB. Bottom-right is the Dora bubble's
       turf and the bubble doesn't render pre-auth, so left stays clear of
       floating chrome (D-009). ── */
    .donate-btn--floating {
        position: fixed;
        left: 18px;
        bottom: 18px;
        z-index: 3000;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 56px;
        height: 56px;
        border-radius: var(--radius-full);
        background: var(--donate);
        color: var(--donate-contrast);
        box-shadow: 0 8px 24px var(--donate-glow);
        animation: donate-float-pulse 2.8s ease-in-out infinite;
        transition:
            background var(--motion-fast) var(--motion-ease),
            transform var(--motion-normal) var(--motion-ease-spring);
    }
    .donate-btn--floating:hover {
        background: var(--donate-strong);
        transform: scale(1.08);
    }
    .donate-btn--floating:focus-visible {
        outline: 2px solid var(--donate-contrast);
        outline-offset: 3px;
    }

    @keyframes donate-pulse {
        0%,
        100% {
            box-shadow: 0 2px 8px var(--donate-glow);
        }
        50% {
            box-shadow:
                0 2px 16px var(--donate-glow),
                0 0 0 6px color-mix(in srgb, var(--donate) 18%, transparent);
        }
    }
    @keyframes donate-float-pulse {
        0%,
        100% {
            transform: scale(1);
            box-shadow: 0 8px 24px var(--donate-glow);
        }
        50% {
            transform: scale(1.06);
            box-shadow:
                0 10px 30px var(--donate-glow),
                0 0 0 8px color-mix(in srgb, var(--donate) 16%, transparent);
        }
    }

    /* Belt-and-braces over the global motion kill-switch: freeze the
       attention pulses when reduced motion is requested. */
    @media (prefers-reduced-motion: reduce) {
        .donate-btn__disc--pulse,
        .donate-btn--floating {
            animation: none;
        }
    }
</style>
