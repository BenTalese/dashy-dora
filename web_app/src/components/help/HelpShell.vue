<template>
    <!-- The Help area's page frame (2026-10-29 redesign): one measured column,
         a quiet crumb back to Help, and the heading. Every Help page sits in
         it so the four of them read as one place. -->
    <q-page class="help-shell">
        <div class="help-shell__column">
            <nav v-if="crumb" class="help-shell__crumb" aria-label="Breadcrumb">
                <router-link :to="crumb.to" class="help-shell__crumb-link">
                    <q-icon :name="ICONS.arrow_back" size="16px" />
                    <span>{{ crumb.label }}</span>
                </router-link>
            </nav>
            <slot />
        </div>
    </q-page>
</template>

<script setup lang="ts">
    import { ICONS } from 'src/style/icons';

    defineProps<{
        crumb?: { label: string; to: string };
    }>();
</script>

<style scoped lang="scss">
    .help-shell {
        padding: var(--space-6) var(--space-4) var(--space-12);
    }
    .help-shell__column {
        max-width: 920px;
        margin: 0 auto;
        display: flex;
        flex-direction: column;
        gap: var(--space-6);
    }
    .help-shell__crumb {
        margin-bottom: calc(-1 * var(--space-3));
    }
    .help-shell__crumb-link {
        display: inline-flex;
        align-items: center;
        gap: var(--space-1);
        min-height: 32px;
        padding: 0 var(--space-2) 0 var(--space-1);
        border-radius: var(--radius-md);
        color: var(--text-secondary);
        font-size: var(--font-size-sm);
        font-weight: 600;
        text-decoration: none;
        transition: color var(--motion-fast) var(--motion-ease), background var(--motion-fast) var(--motion-ease);
    }
    .help-shell__crumb-link:hover {
        color: var(--text-primary);
        background: var(--surface-sunken);
    }
    .help-shell__crumb-link:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    @media (max-width: 599px) {
        .help-shell {
            padding: var(--space-4) var(--space-4) var(--space-10);
        }
    }
</style>
