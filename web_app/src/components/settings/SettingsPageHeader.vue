<template>
    <header class="settings-page-header">
        <div class="settings-page-header__heading">
            <q-icon v-if="headingIcon" :name="headingIcon" size="22px" class="settings-page-header__icon" />
            <div class="settings-page-header__text">
                <div class="settings-page-header__title-row">
                    <h1 class="settings-page-header__title">{{ title }}</h1>
                    <HelpHint v-if="help" :topic="help" />
                </div>
                <p v-if="description || $slots.description" class="settings-page-header__description">
                    <slot name="description">{{ description }}</slot>
                </p>
            </div>
        </div>
        <div v-if="$slots.actions" class="settings-page-header__actions">
            <slot name="actions" />
        </div>
    </header>
</template>

<script setup lang="ts">
    // IMPL_PLAN_SETTINGS_REBUILD §2.5 — standardised page-header chrome:
    // title (h1 / 24px / weight 700) + description + optional eyebrow
    // icon (left of title) + optional right-aligned actions slot
    // (refresh / export / primary action).
    // `help` names the Help guide the (?) beside the title opens (FU-951).
    import HelpHint from 'src/components/help/HelpHint.vue';

    import { computed } from 'vue';
    import { useRoute } from 'vue-router';
    import { settingsPageIcon } from 'src/config/settingsPageIcons';

    const props = defineProps<{
        title: string;
        description?: string;
        /** Only for a heading that isn't a settings page's own; a page's icon
         *  comes from `settingsPageIcon` by its route, the same one the nav
         *  shows (FU-672). */
        icon?: string;
        help?: string;
    }>();
    const route = useRoute();
    const headingIcon = computed(() => props.icon ?? settingsPageIcon(route.path));
</script>

<style scoped lang="scss">
    .settings-page-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 20px;
    }
    .settings-page-header__heading {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        min-width: 0;
    }
    .settings-page-header__icon {
        /* An icon is a graphic (D-002's 3:1 tier), so it takes the brighter
           `--accent-mark` rather than the body-text `--accent-ink`. */
        color: var(--accent-mark);
        margin-top: 2px;
        flex: 0 0 auto;
    }
    .settings-page-header__text {
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    .settings-page-header__title-row {
        display: flex;
        align-items: center;
        gap: var(--space-1);
    }
    .settings-page-header__title {
        margin: 0;
        font-size: 1.5rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        color: var(--text-primary);
        line-height: 1.2;
    }
    .settings-page-header__description {
        margin: 0;
        color: var(--text-secondary);
        font-size: 0.9375rem;
        max-width: 60ch;
        line-height: 1.4;
    }
    .settings-page-header__actions {
        flex: 0 0 auto;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    /* On a phone the actions drop under the heading. Beside it they took the
       width and wrapped the title and description a word per line (owner
       2026-10-15, on the API access page). */
    @media (max-width: 599px) {
        .settings-page-header {
            flex-wrap: wrap;
        }
        .settings-page-header__heading {
            flex: 1 1 100%;
        }
        .settings-page-header__actions {
            margin-left: auto;
        }
    }
</style>
