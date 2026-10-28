<template>
    <!-- One guide. Collapsed it is a title and one sentence; open it adds the
         few lines that matter (how, the setting, the caveat), a screenshot
         when there is one, and a way to the surface. -->
    <article
        :id="`guide-${entry.slug}`"
        class="help-entry"
        :class="{ 'help-entry--open': open }"
    >
        <button
            type="button"
            class="help-entry__head"
            :aria-expanded="open"
            :aria-controls="`guide-${entry.slug}-body`"
            @click="emit('toggle')"
        >
            <span class="help-entry__text">
                <span class="help-entry__title">{{ entry.title }}</span>
                <span class="help-entry__summary">{{ entry.summary }}</span>
            </span>
            <q-icon :name="ICONS.expand_more" size="20px" class="help-entry__chevron" />
        </button>

        <div v-show="open" :id="`guide-${entry.slug}-body`" class="help-entry__body">
            <dl v-if="entry.how || entry.setting || entry.note" class="help-entry__facts">
                <div v-if="entry.how" class="help-entry__fact">
                    <dt><q-icon :name="ICONS.east" size="16px" /><span>How</span></dt>
                    <dd>{{ entry.how }}</dd>
                </div>
                <div v-if="entry.setting" class="help-entry__fact">
                    <dt><q-icon :name="ICONS.tune" size="16px" /><span>Setting</span></dt>
                    <dd>
                        <router-link :to="entry.setting.path" class="help-entry__link">
                            {{ entry.setting.label }}
                        </router-link>
                    </dd>
                </div>
                <div v-if="entry.note" class="help-entry__fact">
                    <dt><q-icon :name="ICONS.info_outline" size="16px" /><span>Note</span></dt>
                    <dd>{{ entry.note }}</dd>
                </div>
            </dl>

            <HelpLegend v-if="entry.block === 'legend'" />
            <HelpFaces v-else-if="entry.block === 'faces'" />

            <HelpShot :name="entry.image" :alt="entry.imageAlt ?? entry.title" />

            <div v-if="entry.path" class="help-entry__actions">
                <BaseButton
                    variant="subtle"
                    :icon="ICONS.arrow_forward"
                    :label="openLabel"
                    :to="entry.path"
                />
            </div>
        </div>
    </article>
</template>

<script setup lang="ts">
    import { computed } from 'vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import HelpFaces from 'src/components/help/HelpFaces.vue';
    import HelpLegend from 'src/components/help/HelpLegend.vue';
    import HelpShot from 'src/components/help/HelpShot.vue';
    import type { HelpEntry } from 'src/help/helpContent';
    import { ICONS } from 'src/style/icons';

    const props = defineProps<{
        entry: HelpEntry;
        open: boolean;
    }>();
    const emit = defineEmits<{ (e: 'toggle'): void }>();

    const openLabel = computed(() => (props.entry.path?.startsWith('/settings') ? 'Open the setting' : 'Take me there'));
</script>

<style scoped lang="scss">
    .help-entry {
        background: var(--surface-component);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        box-shadow: var(--elevation-card);
        transition: border-color var(--motion-fast) var(--motion-ease);
    }
    .help-entry--open {
        border-color: var(--border-strong);
    }
    .help-entry__head {
        all: unset;
        box-sizing: border-box;
        display: grid;
        grid-template-columns: 1fr auto;
        align-items: start;
        gap: var(--space-3);
        width: 100%;
        min-height: 56px;
        padding: var(--space-4);
        border-radius: var(--radius-lg);
        cursor: pointer;
        color: var(--text-primary);
    }
    .help-entry__head:hover {
        background: var(--surface-sunken);
    }
    .help-entry__head:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    .help-entry--open .help-entry__head {
        border-bottom-left-radius: 0;
        border-bottom-right-radius: 0;
    }
    .help-entry__text {
        display: flex;
        flex-direction: column;
        gap: 4px;
        min-width: 0;
    }
    .help-entry__title {
        font-size: var(--font-size-md);
        font-weight: 700;
        line-height: 1.3;
    }
    .help-entry__summary {
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
        line-height: 1.45;
    }
    .help-entry__chevron {
        margin-top: 2px;
        color: var(--text-muted);
        transition: transform var(--motion-fast) var(--motion-ease);
    }
    .help-entry--open .help-entry__chevron {
        transform: rotate(180deg);
    }
    .help-entry__body {
        padding: 0 var(--space-4) var(--space-4);
    }
    .help-entry__facts {
        margin: 0;
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
        padding-top: var(--space-1);
    }
    .help-entry__fact {
        display: grid;
        grid-template-columns: 92px 1fr;
        gap: var(--space-3);
        align-items: start;
    }
    .help-entry__fact dt {
        display: inline-flex;
        align-items: center;
        gap: var(--space-1);
        font-size: var(--font-size-xs);
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: var(--text-muted);
        line-height: 1.6;
    }
    .help-entry__fact dd {
        margin: 0;
        font-size: var(--font-size-sm);
        line-height: 1.5;
        color: var(--text-primary);
    }
    .help-entry__link {
        color: var(--accent-ink);
        font-weight: 600;
        text-decoration: none;
    }
    .help-entry__link:hover {
        text-decoration: underline;
    }
    .help-entry__link:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
        border-radius: var(--radius-sm);
    }
    .help-entry__actions {
        margin-top: var(--space-3);
    }
    @media (max-width: 599px) {
        .help-entry__fact {
            grid-template-columns: 1fr;
            gap: 2px;
        }
    }
    @media (prefers-reduced-motion: reduce) {
        .help-entry,
        .help-entry__chevron {
            transition: none;
        }
    }
</style>
