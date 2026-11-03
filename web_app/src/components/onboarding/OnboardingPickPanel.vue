<template>
    <section class="pick-panel">
        <header class="pick-panel__head">
            <span class="pick-panel__icon" aria-hidden="true">
                <q-icon :name="icon" size="22px" />
            </span>
            <div class="pick-panel__heading">
                <div class="pick-panel__title">{{ title }}</div>
                <div class="pick-panel__sub">{{ sub }}</div>
            </div>
            <span class="pick-panel__count">{{ pickedCount }} of {{ totalCount }}</span>
            <BaseButton
                v-if="toggleableKeys.length > 0"
                variant="subtle"
                :label="allPicked ? 'None' : 'All'"
                @click="setAll(!allPicked)"
            />
        </header>

        <div v-for="section in sections" :key="section.key" class="pick-panel__section">
            <div v-if="section.label" class="pick-panel__section-label">{{ section.label }}</div>
            <div class="pick-panel__chips">
                <template v-for="opt in section.options" :key="opt.key">
                    <span v-if="opt.removable" class="pick-chip pick-chip--on pick-chip--own">
                        <q-icon :name="ICONS.check_circle" size="18px" class="pick-chip__mark" />
                        <span class="pick-chip__text">
                            <span class="pick-chip__label">{{ opt.label }}</span>
                            <span v-if="opt.caption" class="pick-chip__caption">{{ opt.caption }}</span>
                        </span>
                        <button
                            type="button"
                            class="pick-chip__remove"
                            :aria-label="`Remove ${opt.label}`"
                            @click="emit('remove', opt.key)"
                        >
                            <q-icon :name="ICONS.close" size="16px" />
                        </button>
                    </span>
                    <button
                        v-else
                        type="button"
                        role="checkbox"
                        class="pick-chip"
                        :class="{ 'pick-chip--on': modelValue[opt.key] }"
                        :aria-checked="!!modelValue[opt.key]"
                        @click="toggle(opt.key)"
                    >
                        <q-icon
                            :name="modelValue[opt.key] ? ICONS.check_circle : ICONS.circle_outline"
                            size="18px"
                            class="pick-chip__mark"
                        />
                        <span class="pick-chip__text">
                            <span class="pick-chip__label">{{ opt.label }}</span>
                            <span v-if="opt.caption" class="pick-chip__caption">{{ opt.caption }}</span>
                        </span>
                    </button>
                </template>
            </div>
        </div>

        <form class="pick-panel__add" @submit.prevent="onAdd">
            <q-input
                dark
                v-model="draftName"
                outlined
                dense
                class="pick-panel__add-name"
                :placeholder="addPlaceholder"
                :aria-label="addPlaceholder"
            />
            <slot name="add-fields" />
            <BaseButton
                variant="secondary"
                type="submit"
                :icon="ICONS.add"
                label="Add"
                :disable="draftName.trim().length === 0"
            />
        </form>
    </section>
</template>

<script setup lang="ts">
    // One onboarding catalogue (locations, groups or items): Dora's defaults as
    // tickable chips, grouped into sections, plus an "add your own" row. The
    // parent owns every pick and every added entry, because the wizard drafts
    // everything and applies it on Finish; this only draws and reports.
    // Fields take `dark` because WelcomeLayout pins a dark canvas while Quasar
    // fields follow the document's theme, which can be light.
    import { ICONS } from 'src/style/icons';
    import BaseButton from 'src/components/BaseButton.vue';
    import { computed, ref } from 'vue';

    export interface PickOption {
        key: string;
        label: string;
        caption?: string;
        /** The user's own entry: always included, removed with its x. */
        removable?: boolean;
    }
    export interface PickSection {
        key: string;
        label?: string;
        options: PickOption[];
    }

    const props = defineProps<{
        title: string;
        sub: string;
        icon: string;
        sections: PickSection[];
        modelValue: Record<string, boolean>;
        addPlaceholder: string;
    }>();
    const emit = defineEmits<{
        (e: 'update:modelValue', value: Record<string, boolean>): void;
        (e: 'add', name: string): void;
        (e: 'remove', key: string): void;
    }>();

    const draftName = ref('');

    const allOptions = computed(() => props.sections.flatMap((s) => s.options));
    const toggleableKeys = computed(() =>
        allOptions.value.filter((o) => !o.removable).map((o) => o.key),
    );
    const totalCount = computed(() => allOptions.value.length);
    const pickedCount = computed(() =>
        allOptions.value.filter((o) => o.removable || props.modelValue[o.key]).length,
    );
    const allPicked = computed(() =>
        toggleableKeys.value.every((k) => props.modelValue[k]),
    );

    function toggle(key: string) {
        emit('update:modelValue', { ...props.modelValue, [key]: !props.modelValue[key] });
    }
    function setAll(on: boolean) {
        const next = { ...props.modelValue };
        for (const k of toggleableKeys.value) next[k] = on;
        emit('update:modelValue', next);
    }
    function onAdd() {
        const name = draftName.value.trim();
        if (!name) return;
        emit('add', name);
        draftName.value = '';
    }
</script>

<style scoped>
    .pick-panel {
        display: flex;
        flex-direction: column;
        gap: var(--space-3);
        padding: var(--space-4) var(--space-5);
        border-radius: var(--radius-lg);
        background: var(--surface-component);
        border: 1px solid var(--border-default);
    }
    .pick-panel__head {
        display: flex;
        align-items: center;
        gap: var(--space-3);
    }
    .pick-panel__icon {
        flex: 0 0 auto;
        width: 40px;
        height: 40px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--brand-primary-soft);
        color: var(--primary-ink);
    }
    .pick-panel__heading {
        flex: 1 1 auto;
        min-width: 0;
    }
    .pick-panel__title {
        font-size: 1rem;
        font-weight: 700;
        color: var(--text-primary);
    }
    .pick-panel__sub {
        font-size: 0.85rem;
        color: var(--text-muted);
    }
    .pick-panel__count {
        flex: 0 0 auto;
        font-size: 0.8rem;
        font-weight: 600;
        color: var(--text-secondary);
        white-space: nowrap;
    }
    .pick-panel__section {
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
    }
    .pick-panel__section-label {
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-muted);
    }
    .pick-panel__chips {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-2);
    }
    .pick-chip {
        appearance: none;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        min-height: 40px;
        padding: 4px 14px 4px 10px;
        border: 1.5px solid var(--border-default);
        border-radius: 999px;
        background: var(--surface-component);
        color: var(--text-secondary);
        font: inherit;
        text-align: left;
        cursor: pointer;
        transition: border-color var(--motion-fast) var(--motion-ease),
            background var(--motion-fast) var(--motion-ease),
            color var(--motion-fast) var(--motion-ease);
    }
    .pick-chip:hover {
        border-color: var(--border-strong);
    }
    .pick-chip:focus-visible,
    .pick-chip__remove:focus-visible {
        outline: 2px solid var(--accent-mark);
        outline-offset: 2px;
    }
    .pick-chip--on {
        border-color: var(--brand-primary);
        background: color-mix(in srgb, var(--brand-primary-soft) 45%, var(--surface-component));
        color: var(--text-primary);
    }
    .pick-chip--own {
        cursor: default;
        padding-right: 4px;
    }
    .pick-chip__mark {
        flex: 0 0 auto;
        color: var(--text-muted);
    }
    .pick-chip--on .pick-chip__mark {
        color: var(--primary-ink);
    }
    .pick-chip__text {
        display: flex;
        flex-direction: column;
        line-height: 1.2;
        min-width: 0;
    }
    .pick-chip__label {
        font-size: 0.9rem;
        font-weight: 600;
    }
    .pick-chip__caption {
        font-size: 0.72rem;
        color: var(--text-muted);
    }
    .pick-chip__remove {
        appearance: none;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        border: 0;
        border-radius: 50%;
        background: transparent;
        color: var(--text-secondary);
        cursor: pointer;
    }
    .pick-chip__remove:hover {
        background: var(--overlay-hover);
    }
    .pick-panel__add {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--space-2);
        padding-top: var(--space-3);
        border-top: 1px solid var(--divider);
    }
    .pick-panel__add-name {
        flex: 1 1 180px;
        min-width: 0;
    }
    @media (pointer: coarse) {
        .pick-chip {
            min-height: 44px;
        }
        .pick-chip__remove {
            width: 44px;
            height: 44px;
        }
    }
    @media (max-width: 599px) {
        .pick-panel {
            padding: var(--space-3) var(--space-4);
        }
    }
</style>
