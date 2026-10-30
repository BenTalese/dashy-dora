<template>
    <div class="mp-shop">
        <!-- Owner feedback 2026-09-05 — *"rename 'this week's shopping' to
             'missing this week' and put that text in place of the 'what's
             needed (X)'… same size as the all ingredients text… put the
             shopping cart there to match the look."* So the card's own title
             row is gone: its words, its icon and its job all moved down onto
             the disclosure header, which is now the only heading here. The
             card had been announcing a section whose contents already
             announced themselves. -->
        <MealPlanRailDisclosure
            v-if="focusedPlan && needToBuy.length"
            :icon="ICONS.shopping_cart"
            label="Missing this week"
            :class="{ 'mp-shop--stale': ingredientsLoading }"
        >
            <!-- Owner feedback 2026-09-05 — the two level LINES became two
                 circles on the header row. They previously sat above the CTA
                 as "2 of 3 to buy" per level with a tooltip each; the owner
                 deleted the tooltips ("useless") and asked for the counts to
                 read as badges beside the chevron. The number is the week's
                 demand at that level — what's *missing* — which is what the
                 heading beside it now says. How much of it is still yours to
                 do is the CTA's job, one row below. -->
            <template #badges>
                <MealPlanRailCount
                    v-for="band in levelBadges"
                    :key="band.key"
                    :count="band.count"
                    :sequence="band.sequence"
                    :label="band.label"
                />
            </template>

            <!-- The CTA sits above the rows and outside the disclosure, so
                 collapsing them never hides the action they exist for (owner:
                 "collapsed by default… with the 'add x to list' always
                 visible", restated 2026-09-05 as "below the row that is icon,
                 text, circles, chevron, but above the low/out list"). -->
            <template #actions>
                <!-- Owner feedback 2026-08-27 — was "Generate shopping list for
                     this week", which swept the week server-side and dropped
                     you on a new list with no say in it. Now it opens the same
                     picker the recipe page opens (R-001). -->
                <BaseButton
                    class="full-width"
                    :icon="ICONS.add_shopping_cart"
                    :label="addToListLabel"
                    :loading="generating"
                    @click="emit('addToList')"
                />
            </template>

            <!-- Still lists everything the week needs, handled or not: the
                 rail is the "what does this week want" view, and hiding rows
                 the moment they land on a list would make it lie by omission.
                 Each row's cart button says which of the two it is. -->
            <MealPlanIngredientRow
                v-for="ing in needToBuy"
                :key="ing.stock_item_id"
                :ingredient="ing"
                @hover="emit('hoverIngredient', ing)"
                @clear-hover="emit('clearHover')"
            />
        </MealPlanRailDisclosure>

        <!-- Nothing to disclose — the three states that have no rows behind
             them keep the bordered card they always had, so the rail doesn't
             collapse to bare text when the week is handled. -->
        <q-card v-else flat bordered>
            <q-card-section class="mp-shop__note">
                <template v-if="!focusedPlan">
                    <span class="text-caption dora-text-muted">
                        No meals planned for this week yet.
                    </span>
                </template>
                <!-- Owner feedback 2026-09-03 — *"don't like how the 'x of x
                     still to buy' text flashes to Calculating."* Only a first
                     load with nothing to show yet says so; after that the
                     previous answer stays put, dimmed. -->
                <template v-else-if="showFirstLoad">
                    <span class="text-caption dora-text-muted">Calculating…</span>
                </template>
                <template v-else>
                    <q-icon :name="ICONS.shopping_cart" size="18px" class="text-positive" />
                    <span class="mp-shop__headline text-positive">
                        Fully stocked for this week
                    </span>
                </template>
            </q-card-section>
        </q-card>

        <!-- Owner feedback 2026-09-03 — *"full ingredient demand could be
             designed a bit better (the text of it is wrapped and seems to have
             no margin around the text)"*. Both were true, and both came from
             wearing Quasar's raw expansion header in a 300px rail: the header
             is a `q-item` whose label had no room beside a leading icon and a
             chevron, so "Full ingredient demand (24)" wrapped hard against the
             card edge. It now sits in the same bordered card language as its
             neighbour, the count moves out of the label into its own badge (so
             the label is short enough not to wrap), and the header keeps the
             card's own gutter. Owner 2026-09-05 asked for that header to sit
             thicker; it is now the shared `MealPlanRailDisclosure`, which is
             also what the card above it wears — same shape by construction
             rather than by two stylesheets agreeing.

             "Full ingredient demand" wrapped to two lines even after the count
             moved out of the label — measured live at the rail's 300px. Three
             words was one too many for the space between an avatar and a
             chevron, and the fix is fewer words: "All ingredients" is what the
             disclosure actually holds (this week's demand INCLUDING what you
             already have, as against "Missing this week" above it). -->
        <MealPlanRailDisclosure
            v-if="focusedPlan && ingredients.length"
            :icon="ICONS.receipt_long"
            label="All ingredients"
            class="q-mt-sm"
        >
            <template #badges>
                <MealPlanRailCount
                    :count="ingredients.length"
                    :label="`${ingredients.length} ingredients this week`"
                />
            </template>
            <!-- Same row component as the list above, so hover-to-highlight
                 works here too — it used to be an inert name-and-chip
                 list. -->
            <MealPlanIngredientRow
                v-for="ing in ingredients"
                :key="ing.stock_item_id"
                :ingredient="ing"
                @hover="emit('hoverIngredient', ing)"
                @clear-hover="emit('clearHover')"
            />
        </MealPlanRailDisclosure>

        <!-- Owner 2026-09-12 — *"are text ingredients shown in the missing and
             all ingredients lists? They should be — visually separate though,
             perhaps their own dropdown, only shown if there are some."*

             They weren't, anywhere on this surface. The server has reported
             them since 2026-08-27 (FU-505) and the add-to-list picker names
             them, but the rail silently left them out of both lists — so a week
             whose recipes were half paste-imported looked fully accounted for.

             Their own disclosure rather than rows in the two above it, because
             they are a different KIND of thing: the lists above are stock items
             with a level and a cart, and these have neither. Listing them there
             would mean rows that can't answer the question their neighbours
             answer. It renders only when there are some, which is the one place
             on this surface where a section may disappear — an empty one would
             be a permanent invitation to fix something that isn't wrong. -->
        <MealPlanRailDisclosure
            v-if="focusedPlan && unlinked.length"
            :icon="ICONS.link_off"
            label="Free-text ingredients"
            class="q-mt-sm"
        >
            <template #badges>
                <MealPlanRailCount
                    :count="unlinked.length"
                    :label="`${unlinked.length} ingredients not linked to your pantry`"
                />
            </template>
            <!-- Owner 2026-09-12 — the same row as the two lists above
                 (R-001): hovering highlights the meals it comes from, and the
                 caption names the amount the week needs. The level dot resolves
                 to "Not tracked", which is the honest reading — there is no
                 pantry item behind this row, which is the whole reason it is in
                 its own section. No cart: it can't become a list line.
                 The explanatory paragraph that sat here went with it; the
                 heading and the dot say it. -->
            <MealPlanIngredientRow
                v-for="row in freeTextRows"
                :key="row.key"
                :ingredient="row.ingredient"
                :note="row.recipeName"
                :show-cart="false"
                @hover="emit('hoverIngredient', row.ingredient)"
                @clear-hover="emit('clearHover')"
            />
        </MealPlanRailDisclosure>

        <!-- Owner 2026-09-12 — what the week's meals cost, moved off the status
             banner above the week (which the owner cut as "repeats info readily
             available elsewhere"). It is a **card, not a disclosure**: one
             figure has nothing to collapse. Money-gated install-wide — with
             money off the server sends no figure at all, so this isn't a hidden
             empty state, it simply doesn't exist (R-029 / R-058).

             The tooltip was three sentences; it is one. The coverage fraction
             stays, because a week costed from half its meals must not read as a
             cheap week. -->
        <q-card
            v-if="focusedPlan && moneyEnabled && estimatedCost !== null"
            flat bordered
            class="mp-shop__cost q-mt-sm"
        >
            <div class="mp-shop__cost-row">
                <q-icon :name="ICONS.payments" size="18px" />
                <span class="mp-shop__cost-label">Cost this week</span>
                <span class="mp-shop__cost-value">
                    {{ formatMoney(estimatedCost) }}
                    <span v-if="costCountedMeals < costTotalMeals" class="dora-text-muted">
                        ({{ costCountedMeals }}/{{ costTotalMeals }})
                    </span>
                </span>
                <BaseTooltip>
                    What this week's meals cost to make, at the planned
                    servings<template v-if="costCountedMeals < costTotalMeals">
 (from {{ costCountedMeals }} of {{ costTotalMeals }} meals;
                    the rest aren't priced)</template>.
                </BaseTooltip>
            </div>

            <!-- Owner 2026-09-13 — inside the card, under the week's figure.
                 It was a caption below it on 09-12, which read as a note about
                 the rail rather than as the other half of the same money
                 question.

                 It is the HOUSEHOLD's period budget — the same `/budget/status`
                 the shopping lists and the builder's cap read (R-003) — not a
                 per-week allowance. -->
            <!-- Owner 2026-10-15 — *"$220 of $220 even when there are planned
                 meals"*. It was the period's remaining budget, which only moves
                 when a list is finished, so planned meals never touched it. It
                 now measures this week's meals against what is left, in the
                 budget period the week falls in (the planner asks
                 `/budget/status?on=<week>`). -->
            <div
                v-if="budgetLine"
                class="mp-shop__budget"
                :class="{ 'mp-shop__budget--over': budgetLine.over }"
            >
                {{ budgetLine.text }}
            </div>
        </q-card>

    </div>
</template>

<script lang="ts" setup>
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { formatMoney } from 'src/composables/useMoney';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import MealPlanIngredientRow from 'src/components/MealPlanIngredientRow.vue';
    import MealPlanRailCount from 'src/components/MealPlanRailCount.vue';
    import MealPlanRailDisclosure from 'src/components/MealPlanRailDisclosure.vue';
    import { ICONS } from 'src/style/icons';
    import { LOW_STOCK_SEQUENCE, OUT_OF_STOCK_SEQUENCE } from 'src/helpers/stockStatus';
    import { useStockStatus } from 'src/composables/useStockStatus';
    import type { BudgetStatus } from 'src/services/api/budgetApiService';
    import type {
        MealPlan, MealPlanIngredient, UnlinkedIngredient,
    } from 'src/models/mealPlan';
    import { computed } from 'vue';

    const props = defineProps<{
        focusedPlan: MealPlan | null;
        ingredientsLoading: boolean;
        ingredients: MealPlanIngredient[];
        /** Everything the week needs that isn't in the pantry. */
        needToBuy: MealPlanIngredient[];
        /** …of those, the ones not yet on any open list. */
        outstanding: MealPlanIngredient[];
        /** FU-505 — ingredient rows with no linked stock item (paste-imported
         *  and never matched). Reported by the server so this surface can name
         *  them rather than quietly dropping them from both lists. */
        unlinked: UnlinkedIngredient[];
        /** Owner 2026-09-12 — the week's estimated cost, server-summed, with
         *  the coverage that keeps it honest. Null when money features are off
         *  or nothing could be priced. */
        estimatedCost: number | null;
        costCountedMeals: number;
        costTotalMeals: number;
        /** The household's period budget status (`/budget/status`), loaded once
         *  by the page. Null when money features are off or it couldn't be
         *  read — the cost card then simply stands alone. */
        budgetStatus: BudgetStatus | null;
        generating: boolean;
    }>();

    const emit = defineEmits<{
        (e: 'addToList'): void;
        (e: 'hoverIngredient', ing: MealPlanIngredient): void;
        (e: 'clearHover'): void;
    }>();

    /** The meals' cost against what is left of the budget period. Display
     *  arithmetic over two server figures (the week's cost and the period's
     *  remaining), nothing re-derived. */
    const budgetLine = computed<{ text: string; over: boolean } | null>(() => {
        const status = props.budgetStatus;
        const cost = props.estimatedCost;
        if (!status?.enabled || status.remaining === null || cost === null) return null;
        const period = status.period === 'monthly' ? 'month' : 'week';
        if (status.remaining < 0) {
            return {
                text: `Budget already ${formatMoney(Math.abs(status.remaining))} over this ${period}`,
                over: true,
            };
        }
        // Exactly spent is not "$0.00 over": nothing is left, and this week's
        // meals only tip it over if they cost something.
        if (status.remaining === 0) {
            return { text: `Budget fully spent this ${period}`, over: cost > 0 };
        }
        if (cost > status.remaining) {
            return {
                text: `${formatMoney(cost - status.remaining)} more than the ${formatMoney(status.remaining)} left this ${period}`,
                over: true,
            };
        }
        return {
            text: `${formatMoney(cost)} of the ${formatMoney(status.remaining)} left this ${period}`,
            over: false,
        };
    });

    // R-003 — the level split reads the app-wide stock composable, the same
    // authority the rows' own dots use, so a row's colour and the count above
    // it cannot disagree.
    const { isMissing, isLowStock } = useStockStatus();
    const { moneyEnabled } = useMoneyEnabled();

    /**
     * The free-text rows, shaped as the ingredient row the other two lists
     * draw. The adapter is explicit rather than a second row component: what
     * differs is the *data* (no stock item, so no level and no cart), not the
     * layout, and the owner asked for the layout to be the same.
     *
     * `stock_item_id` is deliberately the empty string — there is no stock item,
     * `useStockStatus` resolves it to no level, and the row renders "Not
     * tracked". Nothing downstream looks it up, because the cart is off.
     */
    const freeTextRows = computed(() => props.unlinked.map((row, index) => ({
        key: `${row.recipe_id}-${row.ingredient_name}-${index}`,
        recipeName: row.recipe_name,
        ingredient: {
            stock_item_id: '',
            stock_item_name: row.ingredient_name,
            total_quantity: row.quantity,
            unit: row.unit,
            used_in_recipe_ids: [row.recipe_id],
            is_optional: false,
        } as MealPlanIngredient,
    })));

    /** Only the very first calculation may say "Calculating…" — after that
     *  there is a previous answer worth keeping on screen. */
    const showFirstLoad = computed(
        () => props.ingredientsLoading && props.ingredients.length === 0,
    );

    type LevelBadge = {
        key: string;
        sequence: number;
        count: number;
        label: string;
    };

    function countAtLevel(
        rows: MealPlanIngredient[], atLevel: (id: string) => boolean,
    ): number {
        return rows.filter((row) => atLevel(row.stock_item_id)).length;
    }

    const levelBadges = computed<LevelBadge[]>(() => {
        const bands: {
            key: string; sequence: number; noun: string;
            atLevel: (id: string) => boolean;
        }[] = [
            {
                key: 'out',
                sequence: OUT_OF_STOCK_SEQUENCE,
                noun: 'out of stock',
                atLevel: isMissing,
            },
            {
                key: 'low',
                sequence: LOW_STOCK_SEQUENCE,
                noun: 'running low',
                atLevel: isLowStock,
            },
        ];
        return bands.flatMap((band) => {
            const total = countAtLevel(props.needToBuy, band.atLevel);
            if (total === 0) return [];
            const left = countAtLevel(props.outstanding, band.atLevel);
            // The badge counts the week's demand at that level; the CTA below
            // counts what's still yours to do. The accessible name carries
            // both, because the digit alone can't say which of the two it is.
            return [{
                key: band.key,
                sequence: band.sequence,
                count: total,
                label: left > 0
                    ? `${total} ${band.noun}, ${left} not on a list yet`
                    : `${total} ${band.noun}, all on a list`,
            }];
        });
    });

    // Names the button by what's actually left, the way the recipe page's
    // "Add N missing" button does.
    const addToListLabel = computed(() => (
        props.outstanding.length > 0
            ? `Add ${props.outstanding.length} to a list`
            : 'Add to a list'
    ));
</script>

<style scoped>
    /* One figure on one line — a card rather than a disclosure, because there
       is nothing under it to reveal. */
    .mp-shop__cost {
        padding: var(--space-2);
    }
    .mp-shop__cost-row {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        min-height: 32px;
    }
    .mp-shop__cost-label {
        flex: 1 1 auto;
        font-size: var(--font-size-md);
        font-weight: 500;
    }
    .mp-shop__cost-value {
        font-weight: 700;
        font-variant-numeric: tabular-nums;
    }
    /* The period's budget, under the week's own figure inside the same card:
       two facts about the same question, so one card — but two lines, because
       they cover different spans. */
    .mp-shop__budget {
        padding-top: var(--space-1);
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
        font-variant-numeric: tabular-nums;
    }
    .mp-shop__budget--over {
        color: var(--text-primary);
        font-weight: 600;
    }

    .mp-shop__note {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        padding: var(--space-2);
        min-height: 44px;
    }
    /* One line at body weight — the figure it replaced was `text-h5`, which
       made a sidebar count the loudest thing on the page. */
    .mp-shop__headline {
        font-size: var(--font-size-md);
        font-weight: 600;
    }
    /* Mid-recalculation the previous answer stays, very slightly dimmed — the
       one honest way to say "this is a moment out of date" without a flicker.
       It dims the whole card now that the counts live on its header. */
    .mp-shop--stale {
        opacity: 0.6;
        transition: opacity var(--motion-fast) var(--motion-ease);
    }
</style>
