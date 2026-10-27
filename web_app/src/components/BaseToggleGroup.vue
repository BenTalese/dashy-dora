<template>
    <div class="toggle-group">
        <div class="toggle-group__header">
            <div class="toggle-group__label">{{ label }}</div>
            <BaseButton
                variant="ghost"
                dense
                :label="allSelected ? 'Clear all' : 'Select all'"
                :disable="selectableValues.length === 0"
                @click="toggleAll"
            />
        </div>
        <div class="toggle-group__row">
            <button
                v-for="option in options"
                :key="option.value"
                type="button"
                class="toggle-card"
                :class="{ 'toggle-card--on': isSelected(option.value) }"
                :disabled="option.disable === true"
                :aria-pressed="isSelected(option.value)"
                @click="toggle(option.value)"
            >
                <span class="toggle-card__label">{{ option.label }}</span>
                <span v-if="option.caption" class="toggle-card__caption">{{ option.caption }}</span>
                <BaseTooltip v-if="option.tooltip">{{ option.tooltip }}</BaseTooltip>
            </button>
        </div>
    </div>
</template>

<script setup lang="ts">
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    /*
     * Multi-select counterpart to BaseSegmented (D-015 — one anatomy per job):
     * a labelled row of card-sized toggle buttons plus a select-all/clear-all
     * control. Use it where several independent choices apply at once and the
     * whole set should be visible without opening anything — the meal-plan
     * builder's day and slot pickers are the reference consumers.
     *
     * Selection is emitted in `options` order, not click order, so the value is
     * stable regardless of how the user got there.
     */
    import BaseButton from 'src/components/BaseButton.vue';
    import { computed } from 'vue';

    export type ToggleOption = {
        label: string;
        value: string;
        /** Secondary line under the label (e.g. the date behind a weekday). */
        caption?: string;
        /** Reason shown on hover — pair it with `disable` so the greyed-out
         *  state is explainable rather than just inert (D-016). */
        tooltip?: string;
        disable?: boolean;
    };

    const props = defineProps<{
        modelValue: string[];
        label: string;
        options: ToggleOption[];
    }>();
    const emit = defineEmits<{ (e: 'update:modelValue', value: string[]): void }>();

    const selected = computed(() => new Set(props.modelValue));
    const selectableValues = computed(
        () => props.options.filter((o) => o.disable !== true).map((o) => o.value),
    );
    // "Select all" only ever reaches the selectable options, so an all-past
    // week doesn't leave the button in a permanently unsatisfiable state.
    const allSelected = computed(
        () => selectableValues.value.length > 0
            && selectableValues.value.every((v) => selected.value.has(v)),
    );

    function isSelected(value: string): boolean {
        return selected.value.has(value);
    }

    function emitFrom(next: Set<string>) {
        emit('update:modelValue', props.options.map((o) => o.value).filter((v) => next.has(v)));
    }

    function toggle(value: string) {
        const next = new Set(selected.value);
        if (next.has(value)) next.delete(value);
        else next.add(value);
        emitFrom(next);
    }

    function toggleAll() {
        emitFrom(allSelected.value ? new Set() : new Set(selectableValues.value));
    }
</script>

<style scoped>
    .toggle-group__header {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        margin-bottom: var(--space-2);
    }
    .toggle-group__label {
        font-size: var(--font-size-sm);
        font-weight: 500;
        flex: 1 1 auto;
    }
    .toggle-group__row {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-2);
    }
    .toggle-card {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: var(--space-1);
        /* D-004 — 44px minimum effective tap target. */
        min-width: 44px;
        min-height: 44px;
        padding: var(--space-2) var(--space-3);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        background: var(--surface-component);
        color: var(--text-primary);
        cursor: pointer;
        transition: background-color var(--motion-fast) var(--motion-ease),
                    border-color var(--motion-fast) var(--motion-ease);
    }
    .toggle-card__label {
        font-size: var(--font-size-sm);
        font-weight: 600;
        line-height: 1.2;
    }
    .toggle-card__caption {
        font-size: var(--font-size-xs);
        color: var(--text-muted);
        line-height: 1.2;
    }
    /* D-016 — every state defined and distinct. */
    .toggle-card:hover:not(:disabled) {
        background: var(--overlay-hover);
    }
    .toggle-card:active:not(:disabled) {
        background: var(--overlay-active);
    }
    .toggle-card:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    .toggle-card--on,
    .toggle-card--on:hover:not(:disabled) {
        background: var(--brand-primary);
        border-color: var(--brand-primary);
        color: var(--text-on-primary);
    }
    .toggle-card--on .toggle-card__caption {
        color: var(--text-on-primary);
    }
    .toggle-card:disabled {
        opacity: 0.45;
        cursor: not-allowed;
    }
</style>
