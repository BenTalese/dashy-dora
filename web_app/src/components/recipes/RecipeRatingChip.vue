<template>
    <!--
        The recipe's front-of-pack rating, whichever scheme this install picked
        (owner ask 2026-08-27; redesigned 2026-08-28).

        **Health stars are a score pill, not five inline stars.** The original
        rendered all five glyphs at 14px directly in the card's chip run, and
        the owner's note was "the star rating looks a bit meh" — correctly. At
        that size the signal is carried by *which* glyphs are filled, and on a
        low-rated recipe that means four-and-a-half grey outlines: 75px of
        width spent saying almost nothing, in a row where every neighbour is a
        chip. The pill says the same thing in one glyph and a number, and the
        full five-star render moves into the hover, where there's room for it
        plus the caveat.

        **Nutri-Score keeps its badge.** The A–E strip is already a compact
        pill and the colour is the signal, so there is nothing to compress —
        wrapping it in a second pill would only add chrome.

        This exists because `RecipeCard` and `RecipeRow` rendered the same
        block twice already, and adding a per-scheme branch would have made it
        the same block *four* times — the point at which a second copy stops
        being cheap and starts being where the two quietly diverge (R-001).
        The cookbook's two densities differ only by which host places it.
    -->
    <span v-if="stars" class="rating-chip rating-chip--score">
        <q-icon :name="ICONS.star" class="rating-chip__glyph" />
        <span class="rating-chip__value">{{ formatNumber(stars.stars, { digits: 1, minDigits: 1 }) }}</span>
        <!-- A rating built from part of the recipe is marked, not hidden nor
             dimmed. The old treatment was `opacity: .55` on the whole block,
             which reads as "disabled" rather than "approximate" and dies
             against a tinted background. An asterisk is the convention for
             exactly this claim, and it costs 4px. -->
        <span v-if="!judgeable" class="rating-chip__part" aria-hidden="true">*</span>
        <BaseTooltip class="rating-chip__tip">
            <RecipeHealthStars
                :stars="stars.stars"
                size="md"
                :show-value="false"
                :qualifier="qualifier"
            />
            <div class="rating-chip__tip-text">{{ tooltip }}</div>
        </BaseTooltip>
    </span>
    <span v-else-if="nutriScore" class="rating-chip">
        <RecipeNutriScore
            :grade="nutriScore.grade"
            size="sm"
            :qualifier="qualifier"
        />
        <span v-if="!judgeable" class="rating-chip__part" aria-hidden="true">*</span>
        <BaseTooltip>{{ tooltip }}</BaseTooltip>
    </span>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { computed, toRef } from 'vue';

    import RecipeHealthStars from 'src/components/recipes/RecipeHealthStars.vue';
    import RecipeNutriScore from 'src/components/recipes/RecipeNutriScore.vue';
    import { useNutritionRating } from 'src/composables/useNutritionRating';
    import { formatNumber } from 'src/composables/useMoney';
    import type { Recipe } from 'src/models/recipe';
    import { ICONS } from 'src/style/icons';

    const props = defineProps<{ recipe: Recipe }>();

    const { ratingAvailable, ratingOf } = useNutritionRating();
    const recipe = toRef(props, 'recipe');

    const rating = computed(() => ratingOf(recipe.value));
    // The server only ever sends the scheme the install chose, but the
    // availability gate is still read here so a flag flip clears the chip
    // without waiting for a refetch.
    const stars = computed(() => (ratingAvailable.value ? rating.value.stars : null));
    const nutriScore = computed(
        () => (ratingAvailable.value ? rating.value.nutriScore : null));
    const judgeable = computed(() => rating.value.judgeable);

    const qualifier = computed(() => (
        judgeable.value ? 'estimated' : 'estimated from part of the recipe'
    ));

    /** Named in full rather than as "the health rating": these are national
     *  programmes, and a reader who recognises one should see its actual
     *  name. */
    const tooltip = computed(() => {
        const thin = judgeable.value
            ? ''
            : ' (from only part of this recipe)';
        if (stars.value) {
            return `Health Star Rating ${formatNumber(stars.value.stars, { digits: 1, minDigits: 1 })} of 5${thin}`;
        }
        if (nutriScore.value) {
            return `Nutri-Score ${nutriScore.value.grade}, on a scale of A to E${thin}`;
        }
        return '';
    });
</script>

<style scoped lang="scss">
    .rating-chip { display: inline-flex; align-items: center; }

    /* Sized to sit beside the 36px icon buttons it now neighbours without
       stretching their row. `--brand-primary-soft` rather than a semantic
       tint: a nutrition rating is not a warning, and painting a 1.5-star
       dinner in warning orange would be the app editorialising about
       someone's food (D-013). */
    .rating-chip--score {
        gap: 3px;
        padding: 2px var(--space-2);
        border-radius: 999px;
        background: var(--brand-primary-soft);
        /* Not the brand ink: every dark theme defines `--brand-primary-soft`
           as a translucent wash of its own accent, so brand-on-brand loses
           contrast there. Primary text is legible on the tint in both modes
           (D-002). */
        color: var(--text-primary);
        white-space: nowrap;
    }
    /* 18px, up from 14 (owner, 2026-08-29: "can we make the star icons a bit
       bigger?"). It matches the 18px leading glyphs the cookbook's own filter
       fields carry, so the one star on a card is now the same size as the star
       on the rating filter that produced the card. The pill's height is set by
       its text, not the glyph, so this doesn't grow the chip run's row. */
    .rating-chip__glyph {
        font-size: 18px;
        color: var(--brand-primary);
    }
    .rating-chip__value {
        font-size: var(--font-size-sm);
        font-weight: 600;
        font-variant-numeric: tabular-nums;
    }
    .rating-chip__part {
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
        line-height: 1;
    }
    /* The hover is where the five-star render lives now, so it gets a column
       rather than the tooltip's default single line. */
    .rating-chip__tip {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--space-1);
    }
    .rating-chip__tip-text {
        font-size: var(--font-size-sm);
        text-align: center;
        max-width: 220px;
    }
</style>
