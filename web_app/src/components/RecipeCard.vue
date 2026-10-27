<template>
    <q-card
        bordered
        flat
        class="recipe-card cursor-pointer column no-wrap"
        @click="onCardClick"
    >
        <!-- Unconditional since 2026-08-29: a card IS the with-photos shape.
             The `showImage` prop existed only so a caller could pass the
             per-user `show_recipe_images` preference instead; that preference
             is cut, both callers were passing `true`, and the density choice
             on the cookbook is the cards/compact switch. -->
        <div class="recipe-card__media" :style="mediaStyle">
            <img
                v-if="recipe.has_image && !imgFailed"
                class="recipe-card__img"
                :src="imageUrl"
                alt=""
                @error="imgFailed = true"
            />
            <span v-else class="recipe-card__initial">{{ initial }}</span>
        </div>

        <q-card-section class="q-pb-xs">
            <div class="text-h6 ellipsis-2-lines">{{ recipe.name }}</div>
        </q-card-section>

        <q-card-section class="q-pt-none q-pb-xs">
            <div class="row q-gutter-xs items-center">
                <!-- Icon set matched to the filter row (owner feedback
                     2026-08-20). `timer` = a length of time; `schedule`
                     (clock) is reserved for a time OF day, i.e. the meal-slot
                     facet — the two were sharing a clock. -->
                <q-chip v-if="totalTime !== null" dense :icon="ICONS.timer">
                    {{ totalTime }}m
                </q-chip>
                <!-- `restaurant` (fork-and-knife) is the app-wide glyph for
                     "a meal" — dashboard, alerts, meal plans, help. Servings
                     is a count of people, and now says so; it also matches
                     the new "Serves ≥" filter. -->
                <q-chip v-if="recipe.servings" dense :icon="ICONS.people">
                    Serves {{ recipe.servings }}
                </q-chip>
                <!-- A count, so `ingredientCount` (carrot), the same glyph
                     as the "Ingredient count ≤" filter. `ingredients`
                     (food-variant) stays on the Ingredients *picker*, which is
                     about which items, not how many. -->
                <q-chip v-if="ingredientCount > 0" dense :icon="ICONS.ingredientCount">
                    {{ ingredientCount }}
                    {{ ingredientCount === 1 ? 'ingredient' : 'ingredients' }}
                </q-chip>
                <!-- Was `star_outline`, which reads as a rating. Difficulty
                     has its own glyph and the filter already used it. -->
                <q-chip v-if="recipe.difficulty" dense :icon="ICONS.difficulty">
                    {{ recipe.difficulty }}
                </q-chip>
                <!-- FU-637 — kcal per serving while you're choosing, which is
                     where it's actually useful. Sits directly after difficulty
                     (owner 2026-08-28): both are one-word judgements of the
                     dish rather than counts of its parts.
                     A thin complex-mode estimate still shows (hiding it would
                     be its own kind of lie) but is marked with an asterisk
                     rather than switched to an outline chip — the outline made
                     it the one chip in the run that looked like a different
                     species, which is what the owner reported. -->
                <q-chip
                    v-if="kcal.value !== null"
                    dense
                    :icon="ICONS.monitor_heart"
                >
                    {{ Math.round(kcal.value) }} kcal<span
                        v-if="!kcal.judgeable"
                        class="recipe-card__part"
                        aria-hidden="true"
                    >*</span>
                    <BaseTooltip v-if="!kcal.judgeable">{{ kcalTooltip }}</BaseTooltip>
                </q-chip>
                <!-- Owner 2026-09-05 — cost per serving, next to kcal because
                     they are the same species of fact: a per-serving figure
                     the server worked out, which may rest on partial data and
                     says so with the same asterisk. Per-serving rather than
                     per-recipe so two cards side by side are comparable when
                     one feeds two and the other feeds eight. -->
                <q-chip
                    v-if="moneyEnabled && cost.value !== null"
                    dense
                    :icon="ICONS.savings"
                >
                    {{ formatMoney(cost.value) }}<span
                        v-if="!cost.judgeable"
                        class="recipe-card__part"
                        aria-hidden="true"
                    >*</span>
                    <BaseTooltip>
                        {{ cost.judgeable ? 'Estimated cost per serving.' : costTooltip }}
                    </BaseTooltip>
                </q-chip>
                <!-- C-waste W4 — surfaced only when the cookbook's
                     "Uses expiring ingredients" filter is active (the
                     parent passes `showExpiringBadge`). Off-filter, the
                     count is meaningless noise; we hide it. -->
                <!-- FU-653 — Dora's belief, as a remark. Extracted to
                     `RecipeBeliefChip` on 2026-09-01 so the card and the
                     compact row can't drift (R-003); it was outline until
                     then, and is now the B2 neutral chip — the owner found
                     the outline hard to read in both themes. Server sends
                     the hint only when the user opted the recipes surface
                     in, and the chip renders nothing without it. -->
                <RecipeBeliefChip :recipe="recipe" />
                <ExpiringChip
                    v-if="showExpiringBadge && (recipe.expiring_ingredient_count ?? 0) > 0"
                    :count="recipe.expiring_ingredient_count ?? 0"
                    :soonest-date="recipe.expiring_soonest_date"
                />
            </div>
        </q-card-section>

        <q-card-section v-if="metaLine" class="q-pt-none q-pb-xs">
            <div class="text-caption dora-text-muted">{{ metaLine }}</div>
        </q-card-section>

        <q-card-section v-if="tagNames.length > 0" class="q-pt-none q-pb-xs">
            <div class="row q-gutter-xs">
                <!-- Neutral, not outline-primary (owner 2026-09-01: the
                     hollow chips read as hard to make out in both light and
                     dark). A dietary tag is a plain fact with no state to
                     encode, so it takes the B2 neutral chip unmodified. -->
                <q-chip
                    v-for="tag in tagNames"
                    :key="tag"
                    class="recipe-card-tag dora-chip--neutral"
                >
                    {{ tag }}
                </q-chip>
            </div>
        </q-card-section>

        <q-space />
        <q-separator />
        <q-card-actions class="row items-center no-wrap q-px-sm">
            <!-- The install's front-of-pack rating (owner ask 2026-08-27),
                 moved out of the chip run and next to the favourite button
                 2026-08-28. Two reasons: in the chip run it landed at a
                 different x on every card, because the chips before it vary
                 per recipe — so the one figure meant to be scannable *down* a
                 grid never lined up. Here it does, and it reads as the
                 card's verdict rather than one more fact about it. -->
            <RecipeRatingChip :recipe="recipe" class="q-mr-xs" />
            <RecipeActions
                :recipe="recipe"
                :show-filter-by-ingredients="showFilterByIngredients"
                spread
                @toggle-favourite="(id) => emit('toggle-favourite', id)"
                @filter-by-ingredients="(id) => emit('filter-by-ingredients', id)"
                @cook="(id) => emit('cook', id)"
                @add-missing="(id, ids) => emit('add-missing', id, ids)"
                @add-all-to-list="(id) => emit('add-all-to-list', id)"
            />
        </q-card-actions>
    </q-card>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import ExpiringChip from 'src/components/recipes/ExpiringChip.vue';
    import RecipeBeliefChip from 'src/components/recipes/RecipeBeliefChip.vue';
    import RecipeActions from 'src/components/recipes/RecipeActions.vue';
    import RecipeRatingChip from 'src/components/recipes/RecipeRatingChip.vue';
    import { ICONS } from 'src/style/icons';
    import type { Recipe } from 'src/models/recipe';
    import { useRecipeDisplay } from 'src/composables/useRecipeDisplay';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { formatMoney } from 'src/composables/useMoney';
    import { ref } from 'vue';

    const props = withDefaults(
        defineProps<{
            recipe: Recipe;
            /** C-waste W4 — when true, render the "Uses N expiring"
             *  chip if the recipe carries a positive count. Off by
             *  default; the cookbook flips it on while its filter is
             *  active so the badge stays scoped to that intent. */
            showExpiringBadge?: boolean;
            /** When true, render a "Filter stock to this recipe's
             *  ingredients" action in the card footer. Off by default;
             *  the stock-item detail page flips it on inside its
             *  "Recipes using this" tab so the user can jump from a
             *  recipe back to the rest of its pantry footprint. */
            showFilterByIngredients?: boolean;
        }>(),
        {
            showExpiringBadge: false,
            showFilterByIngredients: false,
        },
    );

    const emit = defineEmits<{
        (e: 'open', recipeId: string): void;
        (e: 'cook', recipeId: string): void;
        (e: 'toggle-favourite', recipeId: string): void;
        (e: 'add-missing', recipeId: string, stockItemIds: string[]): void;
        (e: 'add-all-to-list', recipeId: string): void;
        (e: 'filter-by-ingredients', recipeId: string): void;
    }>();

    const imgFailed = ref(false);

    // Everything derived from the recipe for display lives in one place,
    // shared with the compact `RecipeRow` (R-003) — the card decides only
    // how to lay it out.
    const {
        totalTime, ingredientCount, kcal, kcalTooltip, cost, costTooltip,
        metaLine, tagNames,
        initial, mediaStyle, imageUrl,
    } = useRecipeDisplay(() => props.recipe);
    const { moneyEnabled } = useMoneyEnabled();

    function onCardClick() {
        emit('open', props.recipe.recipe_id);
    }
</script>

<style scoped>
    .recipe-card {
        transition: box-shadow var(--motion-fast) var(--motion-ease),
            outline-color var(--motion-fast) var(--motion-ease),
            transform var(--motion-fast) var(--motion-ease);
        outline: 2px solid transparent;
        outline-offset: -2px;
        height: 100%;
        /* Owner feedback 2026-08-18 — "round the corners a tad more". The card
           was on Quasar's 4px generic radius (measured); --radius-lg is the
           token the media strip was already reaching for by hand. */
        border-radius: var(--radius-lg);
    }
    .recipe-card:hover {
        box-shadow: var(--elevation-card-hover);
        transform: translateY(-1px);
    }
    /* Marks a figure worked out from only part of the recipe. Matches the
       rating pill's asterisk so both caveats read as the same claim. */
    .recipe-card__part {
        margin-left: 2px;
        color: var(--text-secondary);
    }
    .recipe-card__media {
        position: relative;
        height: 110px;
        /* `inherit`, not a repeated literal: Quasar's own
           `.q-card > *:first-child` rule already forces the top corners to
           follow the card, which is why the hardcoded `10px 10px 0 0` that
           used to sit here measured as 4px in the browser — it never applied.
           Inheriting states the real relationship and can't drift from the
           card's radius (and drops a hardcoded value, R-002). */
        border-top-left-radius: var(--radius-lg);
        border-top-right-radius: var(--radius-lg);
        border-bottom-left-radius: 0;
        border-bottom-right-radius: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
    }
    .recipe-card__img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    .recipe-card__initial {
        font-size: 2.75rem;
        font-weight: 700;
        color: rgba(255, 255, 255, 0.92);
        user-select: none;
    }
    .ellipsis-2-lines {
        display: -webkit-box;
        -webkit-line-clamp: 2;
        line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }

    /* Mirrors `.recipe-row__hsr`: a partial rating dims rather than gaining a
       "(part)" suffix, because the stars still have to read as stars. */
</style>
