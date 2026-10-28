<template>
    <!-- One topic on the Help landing: the whole card is the link (B4). -->
    <router-link :to="`/help/${topic.slug}`" class="help-topic">
        <span class="help-topic__icon" aria-hidden="true">
            <q-icon :name="topic.icon" size="22px" />
        </span>
        <span class="help-topic__text">
            <span class="help-topic__title">{{ topic.title }}</span>
            <span class="help-topic__blurb">{{ topic.blurb }}</span>
        </span>
        <span class="help-topic__meta">
            <span class="help-topic__count">{{ topic.entries.length }}</span>
            <q-icon :name="ICONS.chevron_right" size="18px" class="help-topic__chevron" />
        </span>
    </router-link>
</template>

<script setup lang="ts">
    import type { HelpTopic } from 'src/help/helpContent';
    import { ICONS } from 'src/style/icons';

    defineProps<{ topic: HelpTopic }>();
</script>

<style scoped lang="scss">
    .help-topic {
        display: grid;
        grid-template-columns: auto 1fr auto;
        align-items: center;
        gap: var(--space-4);
        padding: var(--space-4);
        min-height: 88px;
        background: var(--surface-component);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        box-shadow: var(--elevation-card);
        color: var(--text-primary);
        text-decoration: none;
        transition:
            box-shadow var(--motion-fast) var(--motion-ease),
            transform var(--motion-fast) var(--motion-ease),
            border-color var(--motion-fast) var(--motion-ease);
    }
    .help-topic:hover {
        box-shadow: var(--elevation-card-hover);
        border-color: var(--border-strong);
        transform: translateY(-1px);
    }
    .help-topic:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    .help-topic__icon {
        display: grid;
        place-items: center;
        width: 44px;
        height: 44px;
        border-radius: var(--radius-full);
        background: var(--brand-primary-soft);
        color: var(--accent-mark);
        flex: 0 0 auto;
    }
    .help-topic__text {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
    }
    .help-topic__title {
        font-size: var(--font-size-md);
        font-weight: 700;
        line-height: 1.25;
    }
    .help-topic__blurb {
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
        line-height: 1.35;
    }
    .help-topic__meta {
        display: inline-flex;
        align-items: center;
        gap: var(--space-1);
        color: var(--text-muted);
    }
    .help-topic__count {
        font-size: var(--font-size-xs);
        font-weight: 600;
        min-width: 22px;
        height: 22px;
        padding: 0 var(--space-2);
        display: grid;
        place-items: center;
        border-radius: var(--radius-pill);
        background: var(--surface-sunken);
        color: var(--text-secondary);
    }
    .help-topic__chevron {
        transition: transform var(--motion-fast) var(--motion-ease);
    }
    .help-topic:hover .help-topic__chevron {
        transform: translateX(2px);
    }
    @media (prefers-reduced-motion: reduce) {
        .help-topic,
        .help-topic__chevron {
            transition: none;
        }
        .help-topic:hover {
            transform: none;
        }
    }
</style>
