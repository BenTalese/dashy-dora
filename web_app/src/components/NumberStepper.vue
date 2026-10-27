<template>
    <!--
        − value + for a small count you nudge rather than type. Three call
        sites had hand-rolled the same three elements with different gaps,
        different value widths and different tap targets (the meal-plan
        builder's servings, cook mode's headcount, cook mode's leftovers);
        owner feedback 2026-09-03 asked for the last of those to match the
        first, which is the point at which it becomes one component (R-001).

        Two shapes, and they are contexts rather than taste:
          inline — one cell inside a dense row of other controls.
          pill   — a standalone labelled control, bordered so the label, the
                   buttons and the number read as a single object, with 44px
                   targets (D-004) because it is reached for one-handed.
    -->
    <div class="num-stepper" :class="`num-stepper--${variant}`">
        <q-icon v-if="icon" :name="icon" size="20px" class="dora-text-muted" />
        <span v-if="label" class="num-stepper__label">{{ label }}</span>
        <BaseButton
            variant="icon"
            :dense="variant === 'inline'"
            :icon="ICONS.remove"
            :disable="atMin"
            :aria-label="decrementLabel"
            @click="step(-1)"
        />
        <!-- Owner 2026-09-12 — *"give it an input box same as the recipe
             panel"*. The rail's cooked-count tile has been typeable since
             2026-09-03 for the same reason: a number you can see and can't
             change reads as broken, and typing 6 beats six taps. Opt-in, so the
             call sites that are genuinely nudge-only keep a plain readout. -->
        <input
            v-if="editable"
            class="num-stepper__value num-stepper__input"
            type="number"
            inputmode="numeric"
            :min="min"
            :max="max"
            :value="modelValue"
            :aria-label="label ?? 'Value'"
            @click.stop
            @focus="selectAll"
            @keydown.enter.prevent="commit"
            @keydown.esc.prevent="cancel"
            @blur="commit"
        >
        <span v-else class="num-stepper__value" aria-live="polite">{{ modelValue }}</span>
        <BaseButton
            variant="icon"
            :dense="variant === 'inline'"
            :icon="ICONS.add"
            :disable="atMax"
            :aria-label="incrementLabel"
            @click="step(1)"
        />
        <!-- tooltip / anything else the caller wants anchored to the control -->
        <slot />
    </div>
</template>

<script setup lang="ts">
    import { computed } from 'vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import { ICONS } from 'src/style/icons';

    const props = withDefaults(
        defineProps<{
            modelValue: number;
            min?: number;
            max?: number | undefined;
            /** Leading caption inside the control (`pill` shape). */
            label?: string | undefined;
            /** Leading glyph inside the control (`pill` shape). */
            icon?: string | undefined;
            variant?: 'inline' | 'pill';
            /** Screen-reader names for the two buttons. Defaulted off `label`
             *  so a caller that sets one gets sensible ones for free. */
            decrementLabel?: string | undefined;
            incrementLabel?: string | undefined;
            /** Render the value as a typeable tile rather than a readout
             *  (owner 2026-09-12). Enter/blur commits, Esc reverts. */
            editable?: boolean | undefined;
        }>(),
        { min: 0, variant: 'inline', editable: false },
    );

    const emit = defineEmits<{ (e: 'update:modelValue', value: number): void }>();

    /** Floors before stepping: the seed value can come from a stored setting
     *  this control doesn't get to assume is integral. */
    function step(delta: number) {
        const current = Number.isFinite(props.modelValue)
            ? Math.floor(props.modelValue)
            : props.min;
        let next = Math.max(props.min, current + delta);
        if (props.max !== undefined) next = Math.min(props.max, next);
        emit('update:modelValue', next);
    }

    function selectAll(event: FocusEvent) {
        (event.target as HTMLInputElement | null)?.select();
    }
    /** Commit a typed value, clamped to the same bounds `step` honours. A
     *  value this control can't use re-asserts the truth rather than leaving
     *  the field showing it. */
    function commit(event: Event) {
        const input = event.target as HTMLInputElement;
        const typed = Math.floor(Number(input.value));
        if (!Number.isFinite(typed)) {
            input.value = String(props.modelValue);
            return;
        }
        let next = Math.max(props.min, typed);
        if (props.max !== undefined) next = Math.min(props.max, next);
        input.value = String(next);
        if (next !== props.modelValue) emit('update:modelValue', next);
    }
    function cancel(event: Event) {
        const input = event.target as HTMLInputElement;
        input.value = String(props.modelValue);
        input.blur();
    }

    const atMin = computed(() => props.modelValue <= (props.min ?? 0));
    const atMax = computed(
        () => props.max !== undefined && props.modelValue >= props.max,
    );

    const decrementLabel = computed(
        () => props.decrementLabel ?? (props.label ? `Decrease ${props.label}` : 'One fewer'),
    );
    const incrementLabel = computed(
        () => props.incrementLabel ?? (props.label ? `Increase ${props.label}` : 'One more'),
    );
</script>

<style scoped lang="scss">
    .num-stepper {
        display: flex;
        align-items: center;
        white-space: nowrap;
    }
    .num-stepper__value {
        text-align: center;
        font-variant-numeric: tabular-nums;
        color: var(--text-primary);
    }
    /* The typeable tile — the same shape the recipe rail's cooked-count wears
       (`.mp-row__tile`), so the two numeric controls in the planner read as one
       idea. Native spinners off: they'd duplicate the ± buttons beside them. */
    .num-stepper__input {
        width: 44px;
        height: 32px;
        flex: none;
        padding: 0;
        border: 1px solid transparent;
        border-radius: var(--radius-md);
        background: var(--surface-sunken);
        font: inherit;
        font-weight: 700;
        cursor: text;
        appearance: textfield;
        -moz-appearance: textfield;
    }
    .num-stepper__input::-webkit-outer-spin-button,
    .num-stepper__input::-webkit-inner-spin-button {
        appearance: none;
        margin: 0;
    }
    .num-stepper__input:hover {
        border-color: var(--border-strong);
    }
    .num-stepper__input:focus-visible {
        outline: 2px solid var(--brand-primary);
        outline-offset: 2px;
    }
    @media (pointer: coarse) {
        .num-stepper__input {
            height: 44px;
        }
    }
    .num-stepper--inline {
        gap: var(--space-1);
    }
    .num-stepper--inline .num-stepper__value {
        min-width: 1.2rem;
    }
    .num-stepper--pill {
        gap: var(--space-2);
        flex: 0 0 auto;
        padding: var(--space-1) var(--space-3);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-pill);
        background: var(--surface-elevated);
    }
    .num-stepper--pill .num-stepper__label {
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
    }
    .num-stepper--pill .num-stepper__value {
        min-width: 1.75rem;
        font-size: var(--font-size-xl);
        font-weight: 600;
    }
    /* D-004 — reached for one-handed, so the targets clear 44px rather than
       sitting at BaseButton's 36px desktop-chrome default. */
    .num-stepper--pill :deep(.dora-btn--icon) {
        min-height: 44px;
        min-width: 44px;
    }
</style>
