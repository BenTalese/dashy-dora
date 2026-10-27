<template>
    <!--
        FU-653 — Dora's belief about a recipe, as a remark.

        Extracted from `RecipeCard` + `RecipeRow` on 2026-09-01 (R-003):
        both rendered the same chip with the same props and the same
        tooltip, and the owner's "filled with neutral text" restyle would
        otherwise have had to be made twice. Callers decide only whether
        the label shows — the compact row suppresses it for width and
        leans on the tooltip.

        Neutral, not outline (owner 2026-09-01): the outline version was
        hard to read in both themes. See `.dora-chip--neutral` in
        `colours.scss` for the D-002/D-013 reasoning — the semantic colour
        survives on the icon only.
    -->
    <q-chip
        v-if="recipe.inference_hint"
        dense
        :icon="ICONS.dora_voice"
        class="dora-chip--neutral rbc"
        :class="[
            `dora-chip--${inferenceTone(recipe.inference_hint)}`,
            { 'rbc--glyph': !labelled },
        ]"
    >
        <span v-if="labelled">
            {{ recipe.inference_hint === 'at_risk' ? 'May be short' : 'May be cookable' }}
        </span>
        <BaseTooltip max-width="300px">{{ inferenceTooltip }}</BaseTooltip>
    </q-chip>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    import { inferenceTone } from 'src/helpers/inferenceHint';
    import type { Recipe } from 'src/models/recipe';
    import { useRecipeDisplay } from 'src/composables/useRecipeDisplay';

    const props = withDefaults(
        defineProps<{
            recipe: Recipe;
            /** Show the wording beside the glyph. Off in the compact row,
             *  where the tooltip carries it instead. */
            labelled?: boolean;
        }>(),
        { labelled: true },
    );

    const { inferenceTooltip } = useRecipeDisplay(() => props.recipe);
</script>

<style scoped lang="scss">
    /* Owner 2026-09-03: in the compact row the chip "looks a bit off … like
       the icon is being pushed left by a text area that is always empty".
       Right diagnosis, wrong culprit — the label is `v-if`'d away and renders
       nothing. What's left is Quasar's own icon geometry, which assumes a
       label follows: `.q-chip__icon--left` carries `margin-left: -0.3em` (to
       pull the glyph back into the chip's padding) plus `margin-right: 0.2em`
       (to space it off the words). With no words, that is 0.5em of asymmetry
       and the glyph sits hard against the left edge.
       Unlabelled, the glyph *is* the chip, so it gets even padding and no
       label margins. */
    .rbc--glyph {
        padding: 0 var(--space-1, 4px);

        :deep(.q-chip__icon) {
            margin-left: 0;
            margin-right: 0;
        }
    }
</style>
