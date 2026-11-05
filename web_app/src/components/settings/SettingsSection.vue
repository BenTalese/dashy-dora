<template>
    <section class="settings-section">
        <header
            v-if="$slots.title || $slots.description || $slots.actions"
            class="settings-section__header"
            :class="{ 'settings-section__header--inline': !$slots.description }"
        >
            <div class="settings-section__heading">
                <div v-if="$slots.title" class="settings-section__title-row">
                    <h2 class="settings-section__title">
                        <slot name="title" />
                    </h2>
                    <HelpHint v-if="help" :topic="help" />
                </div>
                <p v-if="$slots.description" class="settings-section__description">
                    <slot name="description" />
                </p>
            </div>
            <div v-if="$slots.actions" class="settings-section__actions">
                <slot name="actions" />
            </div>
        </header>
        <div class="settings-section__body">
            <slot />
        </div>
    </section>
</template>

<script setup lang="ts">
    // IMPL_PLAN_SETTINGS_REBUILD §2.5 — left-info / right-control wrapper.
    // The parent page renders a 1px divider between sections so spacing
    // stays consistent. `help` names the Help guide the (?) beside the title
    // opens (FU-951).
    import HelpHint from 'src/components/help/HelpHint.vue';

    defineProps<{ help?: string }>();
</script>

<style scoped lang="scss">
    .settings-section {
        display: flex;
        flex-direction: column;
        gap: 16px;
        padding: 4px 0 24px;
    }
    .settings-section__header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 16px;
    }
    /* Same fix as SettingsRow's: a title-plus-toggle header top-aligns a ~40px
       control against a ~21px heading. With no description there is only one
       line to align to, so centre. Kept off the description case on purpose —
       there a control should stay level with the heading, not float to the
       middle of a four-line paragraph (Admin → Data pages). */
    .settings-section__header--inline {
        align-items: center;
    }
    .settings-section__heading {
        display: flex;
        flex-direction: column;
        gap: 4px;
        min-width: 0;
    }
    .settings-section__title-row {
        display: flex;
        align-items: center;
        gap: var(--space-1);
    }
    .settings-section__title {
        margin: 0;
        font-size: 1rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        color: var(--text-primary);
        line-height: 1.3;
    }
    .settings-section__description {
        margin: 0;
        max-width: 60ch;
        color: var(--text-secondary);
        font-size: 0.875rem;
        line-height: 1.4;
    }
    .settings-section__actions {
        flex: 0 0 auto;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .settings-section__body {
        display: flex;
        flex-direction: column;
        gap: 14px;
    }
</style>
