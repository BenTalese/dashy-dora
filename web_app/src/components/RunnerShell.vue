<template>
    <!-- The full-bleed meal-reconcile shell (02-R28): app-shell height from
         the live layout (R-036), a close X, the page's own strip content, and
         a (?) that opens the matching Help guide (owner 2026-08-27: *"Info
         button should take you to help and guides, not open a modal"*). -->
    <q-page class="runner-shell" :style-fn="appShellStyleFn">
        <div class="runner-topbar">
            <BaseButton
                variant="icon"
                :icon="ICONS.close"
                color="white"
                :to="closeTo"
                :aria-label="closeLabel"
            />
            <slot name="topbar" />
            <BaseButton
                variant="icon"
                :icon="ICONS.help_outline"
                color="white"
                :aria-label="`Read the ${helpTopic} guide`"
                :to="{ path: '/help', query: { q: helpTopic } }"
            />
        </div>
        <slot />
    </q-page>
</template>

<script lang="ts" setup>
    import BaseButton from 'src/components/BaseButton.vue';
    import { appShellStyleFn } from 'src/helpers/appShell';
    import { ICONS } from 'src/style/icons';

    defineProps<{
        closeTo: string;
        closeLabel: string;
        /** A guide title in `HelpPage.vue`; the `?q=` filter lands on it. */
        helpTopic: string;
    }>();
</script>

<style scoped>
    .runner-shell {
        background: var(--surface-page);
        display: flex;
        flex-direction: column;
    }
    .runner-topbar {
        display: flex;
        align-items: center;
        padding: var(--space-2) var(--space-3);
        background: var(--brand-primary);
        color: var(--text-on-primary);
        min-height: 3rem;
    }
</style>
