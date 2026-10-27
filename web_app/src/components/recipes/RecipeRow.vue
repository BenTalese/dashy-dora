<template>
    <!--
        Compact cookbook row — one line per recipe, the Stock Overview
        shape (2026-08-17 feedback). Same data and the same actions as
        `RecipeCard`; only the layout differs, and every derived figure
        comes from the shared `useRecipeDisplay` so the two views can't
        drift (R-003).

        Left → right:
          Name              · · ·  [chips] [expiring?] [♥] [👨‍🍳] [🛒]
          ⏱ 25m · 🔢 8
        Chrome mirrors `StockItemRow`: bordered flat card, 8px radius,
        accent-tinted hover, no lift — and, from 2026-08-20, the same
        name type size and the same name-plus-second-line shape.
    -->
    <q-card
        bordered
        flat
        class="recipe-row cursor-pointer"
        @click="emit('open', recipe.recipe_id)"
    >
        <q-card-section class="row items-center no-wrap recipe-row__body">
            <!-- No thumbnail, by definition. Owner call 2026-08-18 merged the
                 separate "show/hide photos" toggle into the cards/compact
                 switch: compact IS the without-photos shape. (The
                 `show_recipe_images` preference that toggle wrote was cut
                 entirely on 2026-08-29.) -->

            <!-- The old meta line (collection · cuisine · category · …) was
                 removed 2026-08-19 — owner: "remove the second info line under
                 the recipe name in compact view, looks too cluttered". It is
                 back on 2026-08-20, but as two facts rather than five:
                 "in desktop view put time and ingredient count right or
                 underneath of recipe name". Underneath, because the chip
                 cluster's width varies with how many chips a given recipe has,
                 so anything in it never lands twice in the same place (the
                 same reasoning that moved the expiring chip to the right edge)
                 — whereas a second line under the name starts at a fixed x.
                 Desktop only: on a phone these were already suppressed for
                 width, and that hasn't changed.
                 Icons, owner 2026-08-28: `timer` for a duration stays — a bare
                 "25m" is ambiguous. The ingredient count *lost* its icon and
                 gained the word instead ("6 ingredients"): the counter glyph
                 read as clutter at 14px and still needed explaining, whereas
                 the word explains itself and costs about the same width.
                 kcal joined this line rather than the chip cluster — it's a
                 plain fact about the dish, same species as the other two, and
                 the cluster is for opinions. -->
            <div class="recipe-row__name-zone column items-start justify-center">
                <div class="recipe-row__name">{{ recipe.name }}</div>
                <div
                    v-if="!compact && metaFacts"
                    class="recipe-row__meta row items-center no-wrap"
                >
                    <span v-if="totalTime !== null" class="recipe-row__fact">
                        <q-icon :name="ICONS.timer" size="14px" />{{ totalTime }}m
                    </span>
                    <span v-if="ingredientCount > 0" class="recipe-row__fact">
                        {{ ingredientCount }}
                        {{ ingredientCount === 1 ? 'ingredient' : 'ingredients' }}
                    </span>
                    <span v-if="kcal.value !== null" class="recipe-row__fact">
                        <q-icon :name="ICONS.monitor_heart" size="14px" />
                        <!-- One node, so `.recipe-row__fact`'s flex gap
                             doesn't push the asterisk off its number. -->
                        <span>
                            {{ Math.round(kcal.value) }} kcal<span
                                v-if="!kcal.judgeable"
                                aria-hidden="true"
                            >*</span>
                        </span>
                        <BaseTooltip v-if="!kcal.judgeable">{{ kcalTooltip }}</BaseTooltip>
                    </span>
                    <!-- Owner 2026-09-05: cost joins the fact line for the
                         same reason kcal did — it's a plain fact about the
                         dish, not an opinion, so it belongs here rather than
                         in the chip cluster. Per-serving, because that's the
                         figure that compares across a list of recipes with
                         different yields. Money-gated: with the opt-in off
                         the server sends no figure at all, so this is the
                         render half of a gate the API already applied. -->
                    <span v-if="moneyEnabled && cost.value !== null" class="recipe-row__fact">
                        <q-icon :name="ICONS.savings" size="14px" />
                        <span>
                            {{ formatMoney(cost.value) }}<span
                                v-if="!cost.judgeable"
                                aria-hidden="true"
                            >*</span>
                        </span>
                        <BaseTooltip>
                            {{ cost.judgeable ? 'Estimated cost per serving.' : costTooltip }}
                        </BaseTooltip>
                    </span>
                </div>
            </div>

            <q-space />

            <!-- Owner 2026-08-19: "put the expiring ingredients chip with the
                 buttons on the right, otherwise in compact view it goes all
                 over the place (not consistently lined up)". It used to sit in
                 the left-hand `__chips` group, whose width varies with how
                 many of the other chips a given recipe has — so the one chip
                 that only appears sometimes never landed in the same place
                 twice. Anchored to the right edge it's always in one spot. -->
            <ExpiringChip
                v-if="showExpiringBadge && (recipe.expiring_ingredient_count ?? 0) > 0"
                :count="recipe.expiring_ingredient_count ?? 0"
                :soonest-date="recipe.expiring_soonest_date"
                compact
                class="recipe-row__expiring q-mr-xs"
            />

            <!-- Anchored beside the favourite button, matching `RecipeCard`
                 (owner 2026-08-28). Survives `compact`: on a phone the pill is
                 the most compressible way to say the most, and it's the one
                 figure a browse is scanning down the list for. -->
            <RecipeRatingChip :recipe="recipe" class="q-mr-xs" />
            <!-- Dora's belief. It used to lead the row in its own group on
                 the left, with a `q-space` after it — so on a row with no
                 rating and no expiring chip it sat marooned mid-row, and it
                 landed at a different x on every recipe. Owner 2026-09-01:
                 "looks really odd on its own in compact view … move it to be
                 left of the favourite button", and nothing in compact should
                 be evenly spaced. Anchored to the right cluster it is always
                 in one spot. Label suppressed here (glyph + tooltip only) —
                 the row has no width to spend on wording. -->
            <RecipeBeliefChip :recipe="recipe" :labelled="false" class="q-mr-xs" />
            <RecipeActions
                :recipe="recipe"
                @toggle-favourite="(id) => emit('toggle-favourite', id)"
                @cook="(id) => emit('cook', id)"
                @add-missing="(id, ids) => emit('add-missing', id, ids)"
                @add-all-to-list="(id) => emit('add-all-to-list', id)"
            />
        </q-card-section>
    </q-card>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    import ExpiringChip from 'src/components/recipes/ExpiringChip.vue';
    import RecipeBeliefChip from 'src/components/recipes/RecipeBeliefChip.vue';
    import RecipeRatingChip from 'src/components/recipes/RecipeRatingChip.vue';
    import RecipeActions from 'src/components/recipes/RecipeActions.vue';
    import { useQuasar } from 'quasar';
    import type { Recipe } from 'src/models/recipe';
    import { useRecipeDisplay } from 'src/composables/useRecipeDisplay';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { formatMoney } from 'src/composables/useMoney';
    import { computed } from 'vue';

    const props = withDefaults(
        defineProps<{
            recipe: Recipe;
            /** C-waste W4 — render the expiring count when the cookbook's
             *  "Uses expiring ingredients" filter is active. */
            showExpiringBadge?: boolean;
        }>(),
        { showExpiringBadge: false },
    );

    const emit = defineEmits<{
        (e: 'open', recipeId: string): void;
        (e: 'cook', recipeId: string): void;
        (e: 'toggle-favourite', recipeId: string): void;
        (e: 'add-missing', recipeId: string, stockItemIds: string[]): void;
        (e: 'add-all-to-list', recipeId: string): void;
    }>();

    const $q = useQuasar();
    const compact = computed(() => $q.screen.lt.sm);

    // `metaLine` deliberately not destructured — the compact row renders its
    // own two-or-three-fact second line rather than the card's prose one.
    const {
        totalTime, ingredientCount, kcal, kcalTooltip, cost, costTooltip,
    } = useRecipeDisplay(() => props.recipe);
    const { moneyEnabled } = useMoneyEnabled();

    /** Whether the line under the name has anything on it. Computed rather
     *  than spelled out in the `v-if` so the three facts can't drift out of
     *  sync with the three `v-if`s inside it. */
    const metaFacts = computed(
        () => totalTime.value !== null
            || ingredientCount.value > 0
            || kcal.value.value !== null
            || (moneyEnabled.value && cost.value.value !== null));

</script>

<style scoped>
    /* Chrome deliberately matches `StockItemRow` — the two compact lists
       should read as the same control in two places. */
    .recipe-row {
        margin-bottom: 8px;
        border-radius: 8px;
        overflow: hidden;
        transition:
            box-shadow var(--motion-fast) var(--motion-ease),
            background-color var(--motion-fast) var(--motion-ease),
            border-color var(--motion-fast) var(--motion-ease);
        border: 1px solid var(--border-default, color-mix(in srgb, var(--text-primary) 12%, transparent));
    }
    .recipe-row:hover {
        background: color-mix(in srgb, var(--q-accent) 4%, var(--surface-component));
        border-color: color-mix(in srgb, var(--q-accent) 38%, transparent);
        box-shadow: 0 1px 6px color-mix(in srgb, var(--text-primary) 8%, transparent);
    }
    .recipe-row__body {
        padding: 6px 12px;
        gap: 12px;
        min-height: 56px;
    }
    /* The name zone is the only part allowed to shrink, so a long recipe
       name truncates instead of pushing the action cluster off the row. */
    .recipe-row__name-zone {
        min-width: 0;
        flex: 1 1 auto;
    }
    /* Owner feedback 2026-08-20: "in compact view, recipe name should be
       same font style as stock item name". Values copied from
       `StockItemRow.vue`'s `.stock-row__name`; the only difference was the
       missing font-size, which left the recipe name a step smaller than the
       stock one on the same-shaped row.

       D-003 carve-out: `1.05rem` is a raw size, and the rule says use the
       `--font-size-*` ratios. It is deliberately raw here because the request
       was *parity with the stock row*, and that row is 1.05rem — a value with
       no token (md = 1, lg = 1.125). Tokenising one of the pair would break
       the parity this line exists to create, and tokenising both changes the
       Stock Overview type the owner signed off on last week. Logged as FU-693
       to move the pair together. */
    .recipe-row__name {
        font-weight: 600;
        font-size: 1.05rem;
        line-height: 1.25;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    /* Second line under the name. Plain text + inline icons rather than
       chips: chip chrome at this size is heavier than the facts warrant, and
       the old chip version is what read as cluttered. */
    /* A partial rating is drawn at reduced opacity rather than with a "(part)"
       suffix like the kcal chip: there is no room for the word, and the stars
       still have to read as stars. The tooltip carries the detail. */
    .recipe-row__meta {
        gap: 10px;
        margin-top: 2px;
        /* D-003: `--font-size-sm` (14), not the 12 caption floor — cook time
           and ingredient count are values you act on ("can I make this
           tonight?"), and the rule reserves 12 for non-actionable captions. */
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
    }
    .recipe-row__fact {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        white-space: nowrap;
    }
    /* Phones: tighter gap so the trailing cluster doesn't eat half the row.
       Owner 2026-09-05 raised the buttons to the D-004 floor on the *stock*
       row; this row carried a copy of the same 30px squeeze ("same squeeze
       StockItemRow applies", which is why it is here at all), so it moves with
       it — the two lists are deliberately the same control in two places and
       leaving one at 30px would just be the inconsistency the owner keeps
       reporting. Full reasoning in `StockItemRow`'s matching block and in
       `BaseButton`'s `pointer: coarse` rule. */
    @media (max-width: 599px) {
        .recipe-row__body {
            padding: 4px 8px;
            gap: 6px;
        }
        .recipe-row__body :deep(.dora-btn--icon) {
            min-width: 44px;
            min-height: 44px;
            width: 44px;
            height: 44px;
        }
        .recipe-row__body :deep(.dora-btn--icon .q-icon) {
            font-size: 19px;
        }
    }
</style>
