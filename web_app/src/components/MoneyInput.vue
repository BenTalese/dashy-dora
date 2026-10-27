<template>
    <q-input
        :model-value="modelValue"
        dense
        outlined
        type="number"
        inputmode="decimal"
        step="0.01"
        min="0"
        :prefix="currencySymbol"
        :label="label"
        :disable="disable"
        v-bind="$attrs"
        @update:model-value="onInput"
        @blur="onBlur"
    />
</template>

<script setup lang="ts">
    /** A price field (feedback PH-4).
     *
     *  The app had five hand-rolled money inputs and no agreement between
     *  them: some put the currency symbol in the *label text*
     *  (`"Notify me below ($)"`), `PriceEntry` used `prefix`, and none of them
     *  normalised what the user typed. The owner's note was *"formatting of
     *  the number input doesn't seem right. Should format to a decimal, no?
     *  Let's do what is standard for a price input."*
     *
     *  So: the symbol is a **prefix**, not label text — it stays visible while
     *  typing, and it stops the label growing long enough to truncate in a
     *  narrow card (which is what PH-3 was reporting). And the value settles to
     *  two decimals on blur, so `3` becomes `3.00` and `2.999` becomes `3.00`
     *  rather than being sent as-is.
     *
     *  Rounding happens **on blur, not on every keystroke** — normalising as
     *  the user types fights them mid-entry (typing "3.5" would rewrite to
     *  "3.50" before they finish).
     *
     *  D-006 (one formatting authority): the symbol comes from `useMoney`, the
     *  install-wide money policy, never a hardcoded "$".
     *
     *  Not yet adopted by `ShoppingListPlanRow`, the dashboard budget or the
     *  Money settings, which still hand-roll their price fields.
     */
    import { useMoney } from 'src/composables/useMoney';

    defineOptions({ inheritAttrs: false });

    const props = withDefaults(
        defineProps<{
            modelValue: number | null;
            label?: string;
            disable?: boolean;
            /** Decimal places to settle on. Currencies without minor units
             *  (JPY) want 0 — the money policy knows, callers shouldn't guess. */
            decimals?: number;
        }>(),
        { label: '', disable: false, decimals: 2 },
    );

    const emit = defineEmits<{ (e: 'update:modelValue', value: number | null): void }>();

    const { currencySymbol } = useMoney();

    function onInput(raw: string | number | null): void {
        if (raw === null || raw === '') {
            emit('update:modelValue', null);
            return;
        }
        const parsed = typeof raw === 'number' ? raw : Number(raw);
        // A partially-typed value ("3.", "-") parses to NaN; leave the field
        // alone rather than clobbering it back to null mid-keystroke.
        if (Number.isNaN(parsed)) return;
        emit('update:modelValue', parsed);
    }

    function onBlur(): void {
        const value = props.modelValue;
        if (value == null || Number.isNaN(value)) return;
        const rounded = Number(value.toFixed(props.decimals));
        if (rounded !== value) emit('update:modelValue', rounded);
    }
</script>
