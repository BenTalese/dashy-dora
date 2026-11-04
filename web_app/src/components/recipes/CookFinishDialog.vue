<template>
    <!-- Cook mode's finish flow (FU-942, split out of `RecipeCookMode.vue`).
         The page opens it through `show()` — which builds the rows from the
         recipe and this cook's swaps at that moment — and leaves cook mode on
         `finished`.

         Owner feedback 2026-09-01: *"The finished cooking
         modal looks genuinely terrible."*

         It was a `q-list` of rows each stacking four things vertically — a
         name, a coloured level chip, a three-way segmented control, and
         then a full-width "Override to a specific level" select beside a
         labelled cart button. Two controls said the same thing in
         different vocabularies (an *action* — down one / out / unchanged —
         and a *destination* level), and the chip was a third reading of
         the same fact.

         So the row is the destination and nothing else: the household's
         stock levels as one segmented control per ingredient, with the
         item's **current** level preselected. Leaving a row alone is
         therefore "unchanged" — which is what actually happens most cooks,
         and the old default of "down one" quietly wrote a level change to
         every ingredient of every recipe you finished. The dot goes with
         the chip and the select: the selected segment already *is* the
         level indicator, and a dot beside it would be the same fact twice
         (owner's call). Name, states and cart sit on one line.

         Owner feedback 2026-09-03: *"The level picker looks horrible,
         let's move to showing the stock level picker from the overview
         rows. Would look better and consistent."* The segmented control
         was a *second vocabulary* for a question the app already asks one
         way everywhere else — the coloured square + level menu on a stock
         row. It also scaled badly: a household with five levels put five
         labelled segments on every ingredient line. Same control now,
         extracted as `StockLevelPicker`. The level *name* the segments
         used to print comes back as the row's own caption, because a
         colour alone is not a legible answer in a list you read top to
         bottom. -->
    <BaseDialog v-model="open" title="Finished cooking?" closable card-style="min-width: 360px; max-width: 720px">
        <q-card-section v-if="finishRows.length === 0" class="dora-text-muted">
            This recipe has no ingredients to adjust.
        </q-card-section>
        <q-card-section v-else class="q-pt-none">
            <div class="text-body2 q-mb-sm">
                Update stock levels of the ingredients you used.
            </div>
            <div class="finish-list">
                <div
                    v-for="row in finishRows"
                    :key="row.targetStockItemId"
                    class="finish-row"
                >
                    <StockLevelPicker
                        :level-id="row.selectedLevelId"
                        :label="`Stock level for ${row.targetName}`"
                        @select="row.selectedLevelId = $event"
                    />
                    <div class="finish-row__name">
                        <div>{{ row.targetName }}</div>
                        <div class="finish-row__level text-caption">
                            {{ levelNameFor(row.selectedLevelId) }}
                        </div>
                    </div>
                    <!-- Owner feedback 2026-09-03: *"incorrect old shopping
                         cart button in use… it doesn't add to a list when
                         one actually does exist, and it tells me to set up
                         a primary list"*. It was a hand-rolled button
                         reading `quickAddTargetListId`, which is non-null
                         only when exactly ONE draft list exists — every
                         other case fell into a bail-out toast naming
                         "primary lists", a concept retired in C-7 Chunk 2.
                         The shared `AddToListButton` is the sanctioned
                         path: it resolves the target (prompting on 2+
                         drafts), shows on-list state, and toggles back
                         off. -->
                    <AddToListButton
                        variant="row"
                        :stock-item-id="row.targetStockItemId"
                    />
                </div>
            </div>
        </q-card-section>
        <!-- The meal count only exists in a batch-cooking household
             (FU-615 — `batch_features_enabled`). In a "fresh" household
             there is no pool to add to, so the field was asking a question
             with no consequence. Owner: *"fix the wording (I previously in
             some commit got it reworded from pool because I hated that
             wording)"* — so this says leftovers, and it is a stepper
             rather than a bare number field, which is the shape the rest
             of the app uses for a small count you nudge.

             Owner feedback 2026-09-03: *"could be styled consistently with
             how this sort of input is done in the meal planner"*. The
             meal-plan builder's servings control is the compact inline
             shape; this was a bordered 44px pill, which is the right
             weight for cook mode's header (wet hands, mid-cook) but not
             for a settled row inside a dialog. Both are now the shared
             `NumberStepper` and differ only by which shape they ask for. -->
        <q-card-section v-if="batchEnabled" class="q-pt-md">
            <div class="finish-meals">
                <div class="finish-meals__copy">
                    <div class="text-body2">Extra servings for later</div>
                    <div class="text-caption dora-text-muted">
                        Leave at 0 if you ate the lot.
                    </div>
                </div>
                <NumberStepper
                    v-model="finishMealsCooked"
                    :min="0"
                    decrement-label="One fewer serving"
                    increment-label="One more serving"
                >
                    <BaseTooltip>Servings kept for later</BaseTooltip>
                </NumberStepper>
            </div>
        </q-card-section>
        <template #actions>
            <BaseButton variant="ghost" label="Cancel" @click="open = false" />
            <BaseButton variant="primary" label="Done" :loading="finishing" @click="confirmFinish" />
        </template>
    </BaseDialog>
</template>

<script lang="ts" setup>
    import { useQuasar } from 'quasar';
    import { ref } from 'vue';

    import AddToListButton from 'src/components/AddToListButton.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import NumberStepper from 'src/components/NumberStepper.vue';
    import type { SessionSwap } from 'src/components/recipes/CookIngredientsPanel.vue';
    import StockLevelPicker from 'src/components/stock/StockLevelPicker.vue';
    import { useCookingPolicy } from 'src/composables/useCookingPolicy';
    import type { Recipe } from 'src/models/recipe';
    import RecipeApiService from 'src/services/api/recipeApiService';
    import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useRecipeStore } from 'src/stores/recipeStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import { ICONS } from 'src/style/icons';

    const props = defineProps<{
        recipe: Recipe | null;
        /** This cook's substitutions (keyed by the original stock item). */
        swaps: Map<string, SessionSwap>;
    }>();

    const emit = defineEmits<{
        /** The cook was recorded; the page leaves cook mode. */
        (e: 'finished'): void;
    }>();

    const open = defineModel<boolean>({ default: false });

    const $q = useQuasar();
    const recipeStore = useRecipeStore();
    const stockItemStore = useStockItemStore();
    const stockLevelStore = useStockLevelStore();
    const recipeApiService = new RecipeApiService();
    const { batchEnabled } = useCookingPolicy();

    // ── Finish flow ──────────────────────────────────────────────────────
    // Owner feedback 2026-09-01 — a row is now just "which level is this at
    // now?", with the item's current level preselected. The old shape carried
    // an *action* (`down_one` / `out` / `unchanged`) **and** a destination
    // override select **and** a colour chip: three vocabularies for one fact,
    // which is what made the modal read as packed. Selecting the level the
    // item is already on is the no-op, so "unchanged" needs no option of its
    // own — and it is the default, where the old flow defaulted to writing a
    // level drop onto every ingredient of every recipe you finished.
    type FinishRow = {
        // After session swaps: the stock item whose level we actually
        // touch on finish (the substitute, not the original recipe item).
        targetStockItemId: string;
        targetName: string;
        /** Where the item sits now — the write is skipped when the selection
         *  still matches this. `undefined` when the stock item hasn't loaded. */
        currentLevelId: string | undefined;
        selectedLevelId: string | undefined;
    };
    const finishing = ref(false);
    const finishMealsCooked = ref<number>(0);
    const finishRows = ref<FinishRow[]>([]);

    /** The selected level's name, printed under the ingredient name. The
     *  picker itself is a colour swatch, and a colour on its own is not an
     *  answer in a list you read row by row — the segments it replaced said
     *  the word, so the row has to. */
    function levelNameFor(levelId: string | undefined): string {
        if (!levelId) return 'No level set';
        return stockLevelStore.levelById.get(levelId)?.name ?? '';
    }

    function buildFinishRows(): FinishRow[] {
        // finish ranges over every ingredient on the recipe,
        // applying any session swaps. The user no longer ticks ingredients
        // mid-cook; cooking the recipe implies using all of them.
        //
        // IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 — unlinked ingredients
        // (stock_item_id === null) can't participate in the finish flow
        // (no stock item to decrement). They're skipped here; the cook
        // still succeeds for the linked ingredients.
        //
        // One row per stock item: the same item used twice, or a swap onto
        // an item the recipe already uses, would otherwise give two pickers
        // writing the same level (and a duplicate v-for key). First wins.
        const rows: FinishRow[] = [];
        const seen = new Set<string>();
        for (const ing of props.recipe?.ingredients ?? []) {
            if (ing.stock_item_id === null) continue;
            const swap = props.swaps.get(ing.stock_item_id);
            const targetId = swap?.substituteId ?? ing.stock_item_id;
            if (seen.has(targetId)) continue;
            seen.add(targetId);
            const item = stockItemStore.byId.get(targetId);
            const fallbackName = swap?.substituteName ?? ing.stock_item_name ?? ing.raw_text ?? '';
            rows.push({
                targetStockItemId: targetId,
                targetName: item?.name ?? fallbackName,
                currentLevelId: item?.stock_level_id,
                selectedLevelId: item?.stock_level_id,
            });
        }
        return rows;
    }

    /** Open the dialog on rows built from the recipe and swaps as they are
     *  now. Rebuilt on every call, so a second "finish" starts fresh. */
    function show() {
        finishRows.value = buildFinishRows();
        open.value = true;
    }

    async function confirmFinish() {
        finishing.value = true;
        try {
            // Fan out per-row level updates with fail-soft semantics: one
            // failed item doesn't take down the rest of the batch.
            // tag each finish-driven level change as a
            // `cook` consumption so the server persists a ConsumptionEvent
            // (the depletion leg of the loop). The server only records one
            // when the level actually drops, so an "unchanged"/manual-up row
            // that slips through carries no false consumption signal.
            const recipeId = props.recipe?.recipe_id;
            const updates = finishRows.value
                .map((row) => {
                    // A row still sitting on the level it arrived at is the
                    // "unchanged" case — no write, and so no ConsumptionEvent.
                    const target = row.selectedLevelId;
                    if (!target || target === row.currentLevelId) return null;
                    return {
                        stock_item_id: row.targetStockItemId,
                        stock_level_id: target,
                        consumption_source: 'cook' as const,
                        ...(recipeId ? { consumption_recipe_id: recipeId } : {}),
                    };
                })
                .filter((u): u is NonNullable<typeof u> => u !== null);
            const settled = await Promise.allSettled(
                updates.map((u) => stockItemStore.updateStockLevelAsync(u)),
            );
            const failed = settled.filter((r) => r.status === 'rejected').length;
            if (failed > 0) {
                // Fail-soft is right for the batch, silent is not: say which
                // part didn't land before the celebration (finalisation 04-R5).
                $q.notify({
                    type: 'negative',
                    message: `Couldn't update ${failed} stock level${failed === 1 ? '' : 's'}.`,
                    caption: 'Check them on the Stock page.',
                });
            }

            let mealsCooked = 0;
            const recipe = props.recipe;
            if (recipe) {
                mealsCooked = Math.max(0, Math.floor(finishMealsCooked.value || 0));
                // The POST alone, not `recipeStore.cookAsync`: that one also
                // refetches the recipe, and a failed refetch after a landed
                // POST would leave the dialog open for a retry that counts
                // the cook twice. Only the POST failing keeps it open; the
                // cookbook list is marked stale and refetches on next visit.
                let cooked: { available_meals: number };
                try {
                    cooked = await recipeApiService.cookAsync(recipe.recipe_id, mealsCooked);
                } catch (err) {
                    $q.notify({
                        type: 'negative',
                        message: "Couldn't record this cook.",
                        caption: toastCaption(err) || 'Try again in a moment.',
                    });
                    return;
                }
                recipeStore.setAvailableMeals(recipe.recipe_id, cooked.available_meals);
                recipeStore.invalidateRecipes();
            }

            // Celebration. Copy reads off `meals_cooked` per L337 / DEC-5.
            $q.notify({
                type: 'positive',
                timeout: 4000,
                // A fresh household never sets aside meals, so "all eaten" only
                // makes sense where saving some was an option.
                message: !batchEnabled.value
                    ? 'Enjoy your meal.'
                    : mealsCooked === 0
                        ? 'All eaten. Hope it was good.'
                        : `You saved ${mealsCooked} meal${mealsCooked === 1 ? '' : 's'}.`,
                icon: ICONS.check_circle,
            });
            open.value = false;
            emit('finished');
        } finally {
            finishing.value = false;
        }
    }

    defineExpose({ show });
</script>

<style scoped lang="scss">
    // Finish rows: [level swatch] name + level name ... [cart]. One line at
    // every width now — the segmented control that used to wrap under the name
    // on a phone is a 32px square, so the row no longer needs a wrap rule.
    .finish-list {
        max-height: 50vh;
        overflow-y: auto;
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
    }
    .finish-row {
        display: flex;
        align-items: center;
        gap: var(--space-3);
        // The level swatch wears a dashed uncertainty ring that bleeds 5px
        // past the button; the vertical padding keeps it off the divider.
        padding: var(--space-3);
        border-bottom: 1px solid var(--divider);
    }
    .finish-row:last-child {
        border-bottom: none;
    }
    .finish-row__name {
        flex: 1 1 auto;
        min-width: 0;
        font-weight: 500;
        overflow-wrap: anywhere;
    }
    .finish-row__level {
        font-weight: 400;
        color: var(--text-secondary);
    }
    .finish-meals {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--space-4);
        flex-wrap: wrap;
    }
</style>
