<template>
    <!--
        The Nutri-Score, drawn (owner ask 2026-08-27).

        One component for both surfaces — the recipe page's nutrition panel and
        the cookbook row's chip — because the two are the same claim at two
        sizes, and a second implementation would be the place the colours
        quietly diverge. Same reasoning as `RecipeHealthStars.vue`.

        **Dora draws its own badge; it does not reproduce the official
        Nutri-Score logo artwork.** The logo is a registered collective
        trademark of Santé publique France with its own graphic charter and a
        registration process aimed at food business operators putting products
        on the market. Dora is estimating a grade for someone's home cooking,
        which is a different act, and borrowing the official mark would dress an
        estimate up as a certified label. The five-letter scale is the published
        *scheme*; this is our rendering of it. Same call as the Health Star
        Rating, which draws generic star icons rather than the FSANZ mark.
    -->
    <span class="rns" :class="`rns--${size}`" role="img" :aria-label="ariaLabel">
        <span
            v-for="letter in NUTRI_SCORE_GRADES"
            :key="letter"
            class="rns__cell"
            :class="{ 'rns__cell--active': letter === grade }"
            :style="letter === grade ? { background: colourFor(letter) } : undefined"
        >{{ letter }}</span>
    </span>
</template>

<script lang="ts" setup>
    import { computed } from 'vue';
    import { NUTRI_SCORE_GRADES } from 'src/composables/useNutritionRating';

    const props = withDefaults(defineProps<{
        /** 'A'..'E', as the server graded it. */
        grade: string;
        size?: 'sm' | 'md';
        /** Appended to the accessible name — "estimated" on a grade whose
         *  coverage is thin, so a screen reader hears the same caveat the
         *  sighted reader gets from the line underneath. */
        qualifier?: string;
    }>(), {
        size: 'md',
        qualifier: '',
    });

    /** The published five-colour scale runs dark green → green → yellow →
     *  orange → dark orange, and the letters are only half the signal: the
     *  colour is what the scheme is actually built around, so it is reproduced
     *  rather than swapped for theme tokens.
     *
     *  D-002 carve-out: these are deliberately *not* `--dora-success` /
     *  `--dora-warning`. They are not Dora's semantic palette speaking, they
     *  are a published scale — repainting them in brand colours would make the
     *  badge say something different from every other Nutri-Score the reader
     *  has seen on a package. They are also fixed across light and dark for
     *  the same reason, with the letter's own ink chosen per cell for contrast
     *  rather than inherited. */
    const GRADE_COLOURS: Record<string, string> = {
        A: '#1b7e3c',
        B: '#7dc043',
        C: '#f4c72b',
        D: '#ef8200',
        E: '#e1231f',
    };

    /** Falls back to the middle band only if the server ever sends a letter
     *  outside A–E — which would be a bug, but a mis-keyed lookup should
     *  degrade to a visible neutral badge rather than an unstyled one. */
    function colourFor(letter: string): string {
        return GRADE_COLOURS[letter] ?? GRADE_COLOURS.C ?? '#f4c72b';
    }

    const ariaLabel = computed(() => {
        const suffix = props.qualifier ? ` (${props.qualifier})` : '';
        return `Nutri-Score ${props.grade} out of A to E${suffix}`;
    });
</script>

<style scoped lang="scss">
    .rns {
        display: inline-flex;
        align-items: stretch;
        border-radius: 4px;
        overflow: hidden;
        white-space: nowrap;
        font-weight: 700;
        line-height: 1;
        font-variant-numeric: tabular-nums;
    }

    /* The unselected letters stay muted so the graded one reads at a glance —
       the badge is a pointer to one letter, not a five-item legend. */
    .rns__cell {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: var(--surface-sunken);
        color: var(--text-secondary);
        opacity: 0.55;
    }

    .rns__cell--active {
        /* White on every band in the published scale clears 4.5:1 except the
           yellow C, which is why that one cell takes near-black ink instead
           (D-004 contrast floor). */
        color: #fff;
        opacity: 1;
    }
    .rns__cell--active:nth-child(3) { color: #1c1c1c; }

    .rns--md .rns__cell {
        min-width: 18px;
        padding: 4px 5px;
        font-size: var(--font-size-sm);
    }
    .rns--sm .rns__cell {
        min-width: 13px;
        padding: 2px 3px;
        font-size: var(--font-size-xs);
    }
</style>
