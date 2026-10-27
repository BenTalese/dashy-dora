<template>
    <!-- FU-392 — persistent demo notice. Only renders when the install is
         booted in demo / sellable-showcase mode (env DORA_DEMO_MODE). A
         floating pill rather than a full-width bar so it never reflows the
         app layout or collides with the mobile bottom nav; it sits above
         everything and is purely informational. -->
    <div v-if="demoMode" class="demo-banner" role="status">
        <q-icon :name="ICONS.visibility" size="18px" class="demo-banner__icon" />
        <span class="demo-banner__text">
            Demo mode. This sample data resets periodically.
        </span>
    </div>
</template>

<script setup lang="ts">
    import { useDemoMode } from 'src/composables/useDemoMode';
    import { ICONS } from 'src/style/icons';

    const { demoMode } = useDemoMode();
</script>

<style scoped>
    .demo-banner {
        position: fixed;
        left: 50%;
        bottom: calc(env(safe-area-inset-bottom, 0px) + 12px);
        transform: translateX(-50%);
        z-index: 4000;
        display: flex;
        align-items: center;
        gap: 8px;
        max-width: calc(100vw - 24px);
        padding: 8px 16px;
        border-radius: var(--radius-pill);
        background: var(--brand-accent);
        color: var(--text-on-accent);
        box-shadow: var(--elevation-2);
        font-size: 0.8125rem;
        font-weight: 600;
        pointer-events: none;
    }

    .demo-banner__icon {
        flex: 0 0 auto;
    }

    .demo-banner__text {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
</style>
