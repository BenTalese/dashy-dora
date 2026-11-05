<template>
    <!-- ═══ Status strip — replaces seven sidebar cards ══════════
         Severity lives in a 3px edge stripe rather than a washed cell
         (D-013): it stays legible on both grounds and doesn't shout.
         Cells that have nothing to say don't render. -->
    <div v-if="recipe" class="rn__status">
        <div
            class="rn__cell rn__cell--split"
            :class="missingIngredients.length > 0 ? 'rn__cell--bad' : (cookableNow ? 'rn__cell--ok' : '')"
        >
            <div class="rn__cellbody">
                <span class="rn__cellk">Right now</span>
                <span class="rn__cellv">{{ cookableHeadline }}</span>
                <!-- One line, and only one. The swap count and the
                     already-on-a-list state both used to be spelled out
                     here as well, and both are visible per-row a few
                     centimetres below — on the chip and on the cart
                     button's own state (owner, 2026-08-31: *"it may be
                     enough to just say the main line"*). The count the
                     button still needs is in the button's label, where
                     it's about what pressing it will do. -->
            </div>
            <!-- The cell's action, at the cell's edge — a real button on
                 the right rather than a text link buried under the copy
                 it belongs to. It disappears (rather than going inert)
                 once everything missing is already on a list. -->
            <BaseButton
                v-if="missingIngredients.length > 0 && missingNotOnListCount > 0"
                variant="secondary"
                :icon="ICONS.add_shopping_cart"
                :label="compact ? undefined : addMissingLabel"
                :aria-label="`${addMissingLabel}: the ingredients you're missing`"
                @click="onAddMissingToList"
            >
                <BaseTooltip v-if="compact">{{ addMissingLabel }}</BaseTooltip>
            </BaseButton>
        </div>

        <div v-if="atRiskCount > 0" class="rn__cell rn__cell--warn">
            <span class="rn__cellk">Worth cooking</span>
            <span class="rn__cellv">{{ atRiskHeadline }}</span>
            <span class="rn__cellsub">Uses it up</span>
        </div>

        <div v-if="moneyEnabled && showCostCell" class="rn__cell">
            <span class="rn__cellk">Estimated cost</span>
            <span class="rn__cellv">
                {{ recipe.estimated_cost !== null ? formatMoney(recipe.estimated_cost) : 'Not enough price info' }}
            </span>
            <span class="rn__cellsub">
                {{ recipe.estimated_cost_priced_count }} of
                {{ recipe.estimated_cost_total_count }} priced
            </span>
            <!-- Feedback 2026-08-24 — the breakdown was a section on
                 the page reached by a text link; it's a question with
                 an answer, so it's a button and a modal. -->
            <BaseButton
                variant="subtle"
                dense
                class="rn__cellbtn"
                :icon="ICONS.receipt_long"
                label="Details"
                @click="costDialogOpen = true"
            />
        </div>

        <div class="rn__cell">
            <span class="rn__cellk">Last cooked</span>
            <span class="rn__cellv">
                {{ recipe.last_made_on ? formatDate(recipe.last_made_on) : 'Never' }}
            </span>
            <!-- The meal pool merged in here rather than owning a card
                 of its own. Batch-cooking households only. -->
            <span v-if="batchEnabled" class="rn__pool">
                <MealStepper
                    :available="recipe.available_meals"
                    :busy="adjusting"
                    size="sm"
                    @adjust="onAdjustMeals"
                />
                <!-- Owner feedback 2026-09-01 — "N free of M" alone is
                     a riddle: add one to the pool and it can still read
                     "0 free of 1", because the meal plan already
                     claimed it. The line now says *why* whenever
                     something is spoken for, so the number moving (or
                     not) is explainable without opening the planner. -->
                <span v-if="poolLabel" class="rn__cellsub">
                    {{ poolLabel }}
                    <BaseTooltip v-if="poolTooltip">{{ poolTooltip }}</BaseTooltip>
                </span>
            </span>
        </div>

        <RecipeCostDialog
            v-model="costDialogOpen"
            :lines="recipe.estimated_cost_lines ?? []"
            :total="recipe.estimated_cost"
            :priced-count="recipe.estimated_cost_priced_count"
            :total-count="recipe.estimated_cost_total_count"
            :per-serving="recipe.estimated_cost_per_serving"
        />

        <!-- Owner feedback 2026-08-27 — shared with meal plans (R-001); the
             recipe-only picker component is gone. -->
        <AddToListDialog
            ref="pickerRef"
            v-model="pickerOpen"
            title="Add ingredients to a list"
            :rows="pickerRows"
            :unlinked="pickerUnlinked"
            :default-new-list-name="`Shopping: ${recipe.name}`"
            :initial-checked-ids="pickerInitialCheckedIds"
            @confirm="onPickerConfirm"
        />
    </div>
</template>

<script lang="ts" setup>
    /**
     * The recipe page's status strip: can I cook it right now (and the
     * add-missing-to-a-list action), what needs using up, what it costs, and
     * when it was last cooked with the batch meal pool. Split out of
     * `RecipeDetailPage` (FU-934). Every number is the server's, read off the
     * loaded recipe (R-003); this block only phrases them.
     */
    import { computed, ref } from 'vue';
    import { useQuasar } from 'quasar';
    import { storeToRefs } from 'pinia';

    import BaseButton from 'src/components/BaseButton.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import MealStepper from 'src/components/recipes/MealStepper.vue';
    import RecipeCostDialog from 'src/components/recipes/RecipeCostDialog.vue';
    import AddToListDialog from 'src/components/shoppingList/AddToListDialog.vue';
    import type { AddToListConfirm } from 'src/components/shoppingList/addToListTypes';

    import { ICONS } from 'src/style/icons';
    import { lineChoicesFromRecipe, rowsFromRecipe, unlinkedFromRecipe } from 'src/helpers/addToListRows';
    import { formatDate } from 'src/composables/useDateFormat';
    import { formatMoney } from 'src/composables/useMoney';
    import { isAlreadyNotified, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useBatchEnabled } from 'src/composables/useBatchEnabled';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { useShoppingListActions } from 'src/composables/useShoppingListActions';
    import { useRecipeDetail } from 'src/composables/useRecipeDetail';
    import { useRecipeStore } from 'src/stores/recipeStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { cartStateFor, type Membership } from 'src/models/shoppingList';

    const $q = useQuasar();
    const recipeStore = useRecipeStore();
    const stockItemStore = useStockItemStore();
    const { recipe, compact, missingIngredients, expiringItems, loadRecipe } = useRecipeDetail();
    const { moneyEnabled } = useMoneyEnabled();
    const { batchEnabled } = useBatchEnabled();
    const { addStockItemsToList } = useShoppingListActions();

    // Shopping-list membership, read from the same place every cart button
    // reads it (R-003) so the page and the buttons can't disagree about
    // whether something is already on a list.
    const { membership: listMembership } = storeToRefs(useShoppingListStore());
    const membership = computed<Membership | null>(
        () => (listMembership.value as Membership | null) ?? null,
    );

    const adjusting = ref(false);
    const costDialogOpen = ref(false);

    // ── Right now ───────────────────────────────────────────────────────
    const cookableNow = computed<boolean | null>(() => recipe.value?.cookable ?? false);
    const unlinkedCount = computed(() => recipe.value?.unlinked_ingredient_count ?? 0);
    const cookableHeadline = computed(() => {
        if (unlinkedCount.value > 0 && missingIngredients.value.length === 0) {
            return `${unlinkedCount.value} ingredient${unlinkedCount.value === 1 ? '' : 's'} to link`;
        }
        if (missingIngredients.value.length === 0) return 'Everything in stock';
        return `${missingIngredients.value.length} ingredient${missingIngredients.value.length === 1 ? '' : 's'} missing`;
    });
    // Owner feedback 2026-08-29 — no "You can cook this now" sub-line: the
    // cell's own headline ("Everything in stock") plus its green edge already
    // say it, and it was the one caption that had to repeat itself.

    // ── What's already on a shopping list ───────────────────────────────
    // Server-owned membership, not a client guess: the same map the cart
    // buttons read. Missing rows split into "still to buy" and "already
    // handled" so the status strip stops offering to add both.
    const missingOnListCount = computed(() =>
        missingIngredients.value.filter(
            (i) => cartStateFor(i.stock_item_id, membership.value) !== 'none',
        ).length);
    const missingNotOnListCount = computed(
        () => missingIngredients.value.length - missingOnListCount.value);

    // Names the button by what it will actually do. When some of the missing
    // rows are already handled the count has to be explicit ("Add 2 to a list"),
    // because "add them" would otherwise read as all of them.
    const addMissingLabel = computed(() => {
        const left = missingNotOnListCount.value;
        if (left === missingIngredients.value.length) {
            return left === 1 ? 'Add it to a list' : 'Add them to a list';
        }
        return `Add ${left} to a list`;
    });

    // ── Worth cooking ───────────────────────────────────────────────────
    const atRiskCount = computed(() => expiringItems.value.size);
    const atRiskHeadline = computed(() => {
        const names = [...expiringItems.value.keys()]
            .map((id) => stockItemStore.byId.get(id)?.name)
            .filter(Boolean);
        if (names.length === 1) return `${names[0]} needs using`;
        return `${atRiskCount.value} ingredients need using`;
    });

    // ── Estimated cost ──────────────────────────────────────────────────
    const showCostCell = computed(() => {
        const r = recipe.value;
        if (!r) return false;
        return r.estimated_cost !== null
            || (r.estimated_cost_lines ?? []).some((l) => l.reason !== 'no_link');
    });

    // ── Last cooked + the meal pool ─────────────────────────────────────
    /* The cooked-meals pool, in words.
     *
     * Owner feedback 2026-09-01: *"when there's a shortfall add text to
     * explain this to the user so there's no confusion when they add 1 to the
     * pool and it still says '0 free of 1'"*.
     *
     * "Free" is `unallocated_meals` — what's in the pool minus what future
     * meal-plan entries have already claimed — so the two numbers move
     * independently and the old phrasing never said what ate the difference.
     *
     * Owner 2026-09-03 trimmed it further: *"no need to restate what the
     * counter shows … in a case where there's nothing planned we don't
     * care"*. The stepper beside this line already shows the pool count, so
     * "2 in the pool" was the number read out loud, and it was the state the
     * line appeared in most often. The line now exists only when the meal
     * plan has a claim on this recipe — which is the only thing the stepper
     * can't tell you:
     *   nothing planned → no line at all;
     *   partly claimed  → name the claim, so 0-free-with-1-in-the-pool has a
     *     visible cause;
     *   short           → the plan wants more than exists; say how many more,
     *     which is the number you'd cook.
     * Display phrasing only — every number here is server-derived (R-003). */
    const poolLabel = computed(() => {
        const r = recipe.value;
        if (!r || r.committed_meals === 0) return '';
        const shortfall = r.committed_meals - r.available_meals;
        if (shortfall > 0) return `Your meal plan needs ${shortfall} more`;
        return `${r.unallocated_meals} free · ${r.committed_meals} planned`;
    });

    const poolTooltip = computed(() => {
        const r = recipe.value;
        if (!r || r.committed_meals === 0) return null;
        const meals = `${r.committed_meals} meal${r.committed_meals === 1 ? '' : 's'}`;
        return `${meals} of this recipe ${r.committed_meals === 1 ? 'is' : 'are'} already on your meal plan, so ${r.committed_meals === 1 ? "it isn't" : "they aren't"} counted as free. Cooking more covers those first.`;
    });

    async function onAdjustMeals(delta: number) {
        if (!recipe.value) return;
        adjusting.value = true;
        try {
            await recipeStore.adjustMealsAsync(recipe.value.recipe_id, delta);
            await loadRecipe();
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({ type: 'negative', message: 'Could not update meals.', caption: toastCaption(err) });
            }
        } finally {
            adjusting.value = false;
        }
    }

    // ── Add missing to a list ───────────────────────────────────────────
    // Reuses the shared picker (and its list-target step) rather than a
    // second, thinner add path — same flow the old page runs (R-001).
    const pickerOpen = ref(false);
    const pickerRef = ref<{ setBusy: (v: boolean) => void; newListName: string } | null>(null);
    const pickerInitialCheckedIds = ref<string[] | undefined>(undefined);
    const pickerRows = computed(() => rowsFromRecipe(recipe.value));
    const pickerUnlinked = computed(() => unlinkedFromRecipe(recipe.value));

    function onAddMissingToList() {
        if (missingIngredients.value.length === 0) return;
        // The "no active shopping list" bounce is gone (2026-08-27) — the
        // shared dialog offers "+ New list", so the first list gets made
        // here rather than on a page you were sent to.
        pickerInitialCheckedIds.value = missingIngredients.value.map((i) => i.stock_item_id);
        pickerOpen.value = true;
    }

    async function onPickerConfirm(payload: AddToListConfirm) {
        pickerRef.value?.setBusy(true);
        try {
            await addStockItemsToList(
                payload.targetListId,
                payload.stockItemIds,
                pickerRef.value?.newListName ?? 'Shopping list',
                lineChoicesFromRecipe(recipe.value),
            );
            pickerOpen.value = false;
            pickerInitialCheckedIds.value = undefined;
        } finally {
            pickerRef.value?.setBusy(false);
        }
    }
</script>

<style scoped lang="scss">
    // `.rn__cellk` is shared with the versions drawer's facts.
    @use '../../css/recipeDetail';

    .rn__status {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1px;
        margin-top: var(--space-5);
        background: var(--border-default);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        overflow: hidden;
    }
    .rn__cell {
        background: var(--surface-component);
        padding: var(--space-3) var(--space-4);
        display: flex; flex-direction: column; gap: 2px;
        position: relative;
    }
    /* A cell that carries an action: copy on the left, the action on the
       right edge where it can be reached without reading past it. */
    .rn__cell--split {
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
        gap: var(--space-3);
    }
    .rn__cellbody { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    /* Severity as an edge stripe rather than a washed cell: it survives both
       themes and doesn't drown the text it's qualifying (D-002/D-013). */
    .rn__cell--bad::before,
    .rn__cell--warn::before,
    .rn__cell--ok::before {
        content: '';
        position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
    }
    .rn__cell--bad::before { background: var(--semantic-negative); }
    .rn__cell--warn::before { background: var(--semantic-warning); }
    .rn__cell--ok::before { background: var(--semantic-positive); }
    .rn__cellv { font-weight: 600; }
    .rn__cellsub { font-size: var(--font-size-sm); color: var(--text-muted); }
    .rn__pool { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
    .rn__cellbtn { align-self: flex-start; margin-top: var(--space-1); }
</style>
