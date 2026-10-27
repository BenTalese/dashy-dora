<template>
    <!-- The sticky strip under the header that the offline and update
         notices share (finalisation 17-R12 — they were the same component
         twice, differing only in tone). `tone` picks the fill; the text and
         the ghost actions come from the caller. -->
    <transition name="shell-banner">
        <div
            v-if="show"
            class="shell-banner"
            :class="`shell-banner--${tone}`"
            role="status"
            aria-live="polite"
        >
            <q-icon :name="icon" size="18px" class="q-mr-sm" />
            <span class="shell-banner__text"><slot /></span>
            <q-space />
            <slot name="actions" />
        </div>
    </transition>
</template>

<script lang="ts" setup>
    defineProps<{
        show: boolean;
        icon: string;
        /** `negative` = something is wrong (offline); `accent` = informational (update). */
        tone: 'negative' | 'accent';
    }>();
</script>

<style scoped>
    .shell-banner {
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 6px 16px;
        color: var(--text-on-primary);
        font-size: 0.85rem;
        font-weight: 500;
        line-height: 1.3;
        position: sticky;
        top: 0;
        z-index: 2500;
        box-shadow: var(--elevation-1);
    }
    .shell-banner--negative {
        background: var(--q-negative);
    }
    .shell-banner--accent {
        background: var(--q-accent);
    }
    .shell-banner__text {
        flex: 1;
        min-width: 0;
    }
    .shell-banner-enter-active,
    .shell-banner-leave-active {
        transition: opacity var(--motion-normal) var(--motion-ease),
            transform var(--motion-normal) var(--motion-ease);
    }
    .shell-banner-enter-from,
    .shell-banner-leave-to {
        opacity: 0;
        transform: translateY(-100%);
    }
</style>
