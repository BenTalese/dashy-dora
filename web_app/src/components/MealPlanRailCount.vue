<template>
    <!-- Owner feedback 2026-09-05 — *"low and out to be circles with numbers
         left of the dropdown chevron, matching the all ingredients circle but
         with the low and out colours."* One badge, one shape: `sequence` null
         is the neutral count the "All ingredients" header carries, and a stock
         sequence tints it.

         Colour comes from `tintClassForSequence`, the same helper every other
         level pill in the app uses (R-003) — including its D-002 carve-out,
         which keeps the digits at `--text-primary` on a soft ground rather
         than at semantic ink that measured under 4.5:1 on the light themes.

         D-013 — a coloured circle is not a decodable signal on its own, so the
         badge carries an accessible name. It is deliberately NOT a tooltip:
         the tooltips these replaced were the ones the owner called useless. -->
    <span
        class="rail-count"
        :class="tintClassForSequence(sequence ?? null)"
        role="img"
        :aria-label="label"
    >{{ count }}</span>
</template>

<script lang="ts" setup>
    import { tintClassForSequence } from 'src/helpers/stockLevelLogic';

    defineProps<{
        count: number;
        /** Stock level sequence to tint by, or null/undefined for the plain
         *  neutral count. */
        sequence?: number | null;
        /** What the number means, in words. */
        label: string;
    }>();
</script>

<style scoped>
    /* Overrides the shared tint pill's left-aligned, text-width shape into a
       centred circle: these hold one or two digits beside a chevron, not a
       phrase. */
    .rail-count {
        justify-content: center;
        min-width: 24px;
        min-height: 24px;
        padding: 0 var(--space-1);
        font-size: var(--font-size-sm);
        font-variant-numeric: tabular-nums;
    }
</style>
