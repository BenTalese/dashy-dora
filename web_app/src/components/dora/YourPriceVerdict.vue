<template>
    <!-- FU-707: one verdict, one wording, on every surface that shows your
         usual price. Paying more is a fact about the shelf, not something the
         user did, so it reads in a neutral tone (D-001); paying less gets a
         chip as loud as paying more; and a usual price built on few prices
         says so. The server decides all three (R-003). -->
    <span v-if="verdict" class="your-price-verdict" :class="`is-${verdict.key}`">
        <q-icon :name="verdict.icon" size="14px" />
        {{ verdict.label }}<template v-if="rough"> · a rough guide</template>
    </span>
</template>

<script setup lang="ts">
    import { computed } from 'vue';
    import { ICONS } from 'src/style/icons';

    const props = defineProps<{
        above: boolean;
        below: boolean;
        rough?: boolean;
    }>();

    const verdict = computed(() => {
        if (props.above) return { key: 'more', label: 'More than usual', icon: ICONS.trending_up };
        if (props.below) return { key: 'less', label: 'Less than usual', icon: ICONS.trending_down };
        return { key: 'usual', label: 'About usual', icon: ICONS.check };
    });
</script>

<style scoped>
    .your-price-verdict {
        display: inline-flex;
        align-items: center;
        gap: var(--space-1);
        padding: var(--space-1) var(--space-3);
        border-radius: var(--radius-pill);
        font-size: var(--font-size-sm);
        font-weight: 600;
        color: var(--text-primary);
        background: var(--surface-sunken);
    }
    .your-price-verdict.is-less {
        background: var(--semantic-positive-soft);
    }
    .your-price-verdict.is-more .q-icon {
        color: var(--severity-attention-ink);
    }
    .your-price-verdict.is-less .q-icon {
        color: color-mix(in srgb, var(--semantic-positive) 62%, var(--text-primary));
    }
</style>
