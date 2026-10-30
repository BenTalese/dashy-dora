<template>
    <!--
        The Health Star Rating, drawn (owner ask 2026-08-27).

        One component for both surfaces — the recipe page's nutrition panel and
        the cookbook row's chip — because the two are the same claim at two
        sizes, and a second implementation would be the place the half-star
        rounding quietly diverges.

        Five stars, each one of three states: full, half, empty. Not a
        `q-rating`: that is an *input* (hover states, keyboard, a value the
        user sets), and this is a fact about the recipe.
    -->
    <span class="rhs" :class="`rhs--${size}`" role="img" :aria-label="ariaLabel">
        <q-icon
            v-for="star in STAR_POSITIONS"
            :key="star"
            :name="iconFor(star)"
            class="rhs__star"
            :class="{ 'rhs__star--empty': stars < star - 0.5 }"
        />
        <span v-if="showValue" class="rhs__value">{{ formatNumber(stars, { digits: 1, minDigits: 1 }) }}</span>
    </span>
</template>

<script lang="ts" setup>
    import { computed } from 'vue';
    import { formatNumber } from 'src/composables/useMoney';
    import { ICONS } from 'src/style/icons';

    const props = withDefaults(defineProps<{
        /** 0.5–5.0 in half steps, as the server computed it. */
        stars: number;
        size?: 'sm' | 'md';
        showValue?: boolean;
        /** Appended to the accessible name — "estimated" on a rating whose
         *  coverage is thin, so a screen reader hears the same caveat the
         *  sighted reader gets from the line underneath. */
        qualifier?: string;
    }>(), {
        size: 'md',
        showValue: true,
        qualifier: '',
    });

    const STAR_POSITIONS = [1, 2, 3, 4, 5] as const;

    /** A star is full at or above its own position, half within the 0.5 below
     *  it, empty otherwise. Comparing against `position - 0.5` rather than
     *  rounding keeps 3.5 rendering as three-and-a-half rather than four. */
    function iconFor(position: number): string {
        if (props.stars >= position) return ICONS.star;
        if (props.stars >= position - 0.5) return ICONS.star_half;
        return ICONS.star_outline;
    }

    const ariaLabel = computed(() => {
        const suffix = props.qualifier ? ` (${props.qualifier})` : '';
        return `Health Star Rating ${formatNumber(props.stars, { digits: 1, minDigits: 1 })} out of 5${suffix}`;
    });
</script>

<style scoped lang="scss">
    .rhs {
        display: inline-flex;
        align-items: center;
        gap: 1px;
        /* The rating is a *positive* signal, so it carries the brand's own
           ink rather than a semantic colour: this is not a warning, and
           painting a 1.5-star recipe red would be the app editorialising
           about someone's dinner (D-013). */
        color: var(--brand-primary);
        white-space: nowrap;
    }
    .rhs__star--empty { color: var(--border-strong); }
    .rhs__value {
        margin-left: var(--space-1, 4px);
        font-weight: 700;
        font-variant-numeric: tabular-nums;
        color: var(--text-secondary);
    }

    .rhs--md .rhs__star { font-size: 20px; }
    .rhs--md .rhs__value { font-size: 0.875rem; }
    .rhs--sm .rhs__star { font-size: 14px; }
    .rhs--sm .rhs__value { font-size: 0.75rem; }
</style>
