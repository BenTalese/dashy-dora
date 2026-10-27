<template>
    <!-- Owner feedback 2026-09-01 — one row shape for BOTH of the right rail's
         ingredient lists ("This week's shopping" and "Full ingredient demand"),
         which had diverged: the first carried a quantity caption, a list-status
         caption and a cart button, the second carried neither and only the two
         shared a level chip. "Make the row styling the same between the two
         ingredient lists" is therefore a componentisation ask (R-001), not a
         CSS one — two call sites, one component.

         The stock level reads as a LEFT dot rather than a right-hand chip, the
         way every other stock surface in the app codes it (`AddToListRowItem`,
         `StockItemRow`, the stocktake runner). D-013 — a bare dot is not a
         decodable signal, so it carries the level name as a tooltip. -->
    <div
        class="mp-ing"
        @mouseenter="emit('hover')"
        @mouseleave="emit('clearHover')"
    >
        <StockLevelDot :sequence="levelSequence" size="12px" dot-class="mp-ing__dot">
            <BaseTooltip>{{ levelLabel }}</BaseTooltip>
        </StockLevelDot>

        <div class="mp-ing__body">
            <div class="mp-ing__name">{{ ingredient.stock_item_name }}</div>
            <!-- The caption is the QUANTITY and nothing else. It used to append
                 `listStatusLabel` — "not on a list" beside a cart button that
                 already says exactly that, on the same row (owner: "redundant,
                 we can see that from the icon on the same row"). -->
            <div v-if="quantityLabel || note" class="mp-ing__qty">
                {{ [quantityLabel, note].filter(Boolean).join(' · ') }}
            </div>
        </div>

        <!-- FU-803 asked the question this prop answers: the auto builder's
             review step renders this row for a week that has NOT been saved
             yet, where a per-ingredient cart button invites you to shop for a
             plan that may never exist — and the builder already ends on "Add to
             a shopping list" for the whole week. So the cart is opt-out, and
             the two rail lists (real, saved demand) keep it. -->
        <AddToListButton
            v-if="showCart"
            variant="row"
            :stock-item-id="ingredient.stock_item_id"
        />
    </div>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import AddToListButton from 'src/components/AddToListButton.vue';
    import StockLevelDot from 'src/components/stock/StockLevelDot.vue';
    import { formatQuantity } from 'src/helpers/formatQuantity';
    import { useStockStatus } from 'src/composables/useStockStatus';
    import type { MealPlanIngredient } from 'src/models/mealPlan';
    import { computed } from 'vue';

    const props = withDefaults(
        defineProps<{
            ingredient: MealPlanIngredient;
            /** Show the per-ingredient add-to-list button. Off for a preview
             *  of demand that isn't committed yet (see the template note). */
            showCart?: boolean;
            /** Owner 2026-09-12 — a second fact for the caption, after the
             *  quantity. The free-text list uses it to name the recipe a row
             *  came from, which is the only thing that identifies an ingredient
             *  with no pantry item behind it. */
            note?: string | undefined;
        }>(),
        { showCart: true, note: undefined },
    );

    const emit = defineEmits<{
        /** Hovering a needed ingredient highlights the day cells whose recipes
         *  use it (F30). Both lists raise it now — the full-demand list was
         *  inert, which is the "does not highlight like this week's shopping
         *  does" report. */
        (e: 'hover'): void;
        (e: 'clearHover'): void;
    }>();

    // R-003 — level resolution is the app-wide composable's job, so this row
    // codes stock level exactly the way every other stock surface does. The
    // planner's own `stockStatusColour`/`stockStatusLabel` props are gone from
    // the two lists with the chip they fed.
    const { levelSequenceForItem, stockStatusLabel } = useStockStatus();
    const levelSequence = computed(() => levelSequenceForItem(props.ingredient.stock_item_id));
    const levelLabel = computed(() => stockStatusLabel(props.ingredient.stock_item_id));

    const quantityLabel = computed(() => (
        props.ingredient.total_quantity === null
            ? ''
            : `needs ${formatQuantity(props.ingredient.total_quantity, props.ingredient.unit)}`
    ));
</script>

<style scoped>
    .mp-ing {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        min-height: 40px;
        padding: var(--space-1) var(--space-2);
        border-radius: var(--radius-sm);
        transition: background var(--motion-fast) var(--motion-ease);
    }
    .mp-ing:hover {
        background: var(--surface-sunken);
    }
    .mp-ing + .mp-ing {
        border-top: 1px solid var(--border-default);
    }
    /* `q-avatar` is `flex` and will happily shrink to nothing beside a long
       name; the dot is the row's status signal, so it is the one thing that
       must not. */
    .mp-ing__dot {
        flex: 0 0 auto;
    }
    .mp-ing__body {
        flex: 1 1 auto;
        min-width: 0;
    }
    .mp-ing__name {
        font-size: var(--font-size-sm);
        line-height: 1.3;
    }
    .mp-ing__qty {
        font-size: var(--font-size-xs);
        color: var(--text-secondary);
        font-variant-numeric: tabular-nums;
    }
</style>
