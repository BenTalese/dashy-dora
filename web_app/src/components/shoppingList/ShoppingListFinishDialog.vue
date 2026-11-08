<template>
    <!-- Finish shopping. Two shapes: everything ticked is a confirmation of
         what you got; finishing with leftovers adds a decision about them
         (another list or the bin), made at the one moment you're thinking
         about it (2026-08-26). A finished list is a receipt, so the
         leftovers can't stay on it. -->
    <BaseDialog
        v-model="finishReviewOpen"
        title="Finish shopping"
        closable
        card-style="min-width: 320px; max-width: 480px"
    >
        <q-card-section>
            <div class="text-body2 dora-text-muted">
                {{
                    finishEntries.length === 0
                        ? 'Nothing is ticked.'
                        : untickedCount === 0
                            ? "Everything's ticked. You got:"
                            : 'You got:'
                }}
            </div>
        </q-card-section>
        <q-card-section v-if="finishEntries.length > 0" class="q-pt-none scroll" style="max-height: 34vh">
            <q-list separator dense>
                <q-item v-for="entry in finishEntries" :key="entry.line_id">
                    <q-item-section>
                        <q-item-label>{{ entry.name }}</q-item-label>
                    </q-item-section>
                    <q-item-section v-if="!entry.stock_item_id" side>
                        <span class="text-caption dora-text-muted">
                            Not stock-tracked
                        </span>
                    </q-item-section>
                </q-item>
            </q-list>
        </q-card-section>

        <q-card-section v-if="untickedCount > 0" class="q-pt-none">
            <q-banner class="dora-bg-warning-soft q-mb-sm" dense rounded>
                <template #avatar>
                    <q-icon :name="ICONS.warning" color="warning" />
                </template>
                <span class="text-body2">
                    <strong>
                        {{ untickedCount }} item{{ untickedCount === 1 ? '' : 's' }}
                    </strong>
                    {{ untickedCount === 1 ? "isn't" : "aren't" }} ticked<template
                        v-if="deferredUntickedCount > 0"
                    >, including {{ deferredUntickedCount }} set aside for the
                        budget</template>.
                    A finished list is a receipt, so
                    {{ untickedCount === 1 ? 'it' : 'they' }}
                    can't stay on it.
                </span>
            </q-banner>
            <q-option-group
                v-model="leftoverAction"
                :options="leftoverOptions"
                color="primary"
                dense
            />
            <!-- Only rendered for the "move to an existing list" branch,
                 and that branch only exists when there is somewhere to
                 move to. -->
            <BaseSelect
                v-if="leftoverAction === 'move-existing'"
                v-model="leftoverTargetListId"
                class="q-mt-sm"
                label="Move to"
                :options="otherActiveListOptions"
                emit-value
                map-options
            />
            <div
                v-if="leftoverAction === 'move-existing' || leftoverAction === 'move-new'"
                class="text-caption dora-text-muted q-mt-sm"
            >
                Anything already on that list is skipped.
            </div>
            <div
                v-else-if="leftoverAction === 'discard'"
                class="text-caption dora-text-muted q-mt-sm"
            >
                Removed from the list for good. Your pantry and purchase
                history aren't touched.
            </div>
        </q-card-section>

        <template #actions>
            <BaseButton
                variant="ghost"
                :label="untickedCount > 0 ? 'Go back' : 'Not yet'"
                v-close-popup
            />
            <BaseButton
                variant="positive"
                :icon="ICONS.check"
                :label="finishCtaLabel"
                :disable="finishBlocked"
                :loading="finishing"
                @click="confirmFinish"
            />
        </template>
    </BaseDialog>
</template>

<script lang="ts" setup>
    /**
     * Finish shopping: the list becomes a receipt, and the unticked lines get
     * a decision. Ticking already restocked each item (UX v5 D1), so this
     * lists what you got rather than what is about to restock.
     *
     * The page opens it through `show()` from the overview card's Finish and
     * from the last tick; the last tick passes `onCancel`, which unticks that
     * line again if the dialog closes without finishing (UX v5 S3).
     */
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import BaseSelect from 'src/components/BaseSelect.vue';
    import { ICONS } from 'src/style/icons';
    import { invalidateBuyVerdict } from 'src/composables/useBuyVerdict';
    import { useShoppingListDetail } from 'src/composables/useShoppingListDetail';
    import { useRecipeStore } from 'src/stores/recipeStore';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { isAlreadyNotified, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useQuasar } from 'quasar';
    import { computed, ref, watch } from 'vue';

    /** Two-way so the overview card's Finish button can show the spinner too. */
    const finishing = defineModel<boolean>('finishing', { default: false });

    const $q = useQuasar();
    const store = useShoppingListStore();
    const stockItemStore = useStockItemStore();
    const recipeStore = useRecipeStore();
    const {
        api, listId, detail, refreshAll, refreshDetailQuietly,
    } = useShoppingListDetail();

    // ── Finish ──────────────────────────────────────────────────────
    const finishReviewOpen = ref(false);
    type FinishEntry = {
        line_id: string;
        stock_item_id: string | null;
        name: string;
    };
    const finishEntries = ref<FinishEntry[]>([]);

    /** What to do with lines that were never ticked. There is deliberately no
     *  "leave them here" option and no default selection: a finished list is a
     *  receipt, and a receipt doesn't record what you didn't buy. Leaving them
     *  stranded them on an archived list forever and kept them counted in the
     *  dashboard's "queued" card. The fourth way out is Cancel — go back and
     *  tick them off after all. */
    type LeftoverAction = 'discard' | 'move-existing' | 'move-new';
    const leftoverAction = ref<LeftoverAction | null>(null);
    const leftoverTargetListId = ref<string | null>(null);

    const otherActiveListOptions = computed(() =>
        otherActiveLists.value.map((s) => ({
            label: s.display_name,
            value: s.shopping_list_id,
        }))
    );

    const leftoverOptions = computed(() => {
        const options = [];
        // Only offered when there is somewhere to move to. An empty radio
        // that opens an empty select is worse than not offering the choice.
        if (otherActiveLists.value.length > 0) {
            options.push({ label: 'Move them to another list', value: 'move-existing' });
        }
        options.push({ label: 'Move them to a new list', value: 'move-new' });
        options.push({ label: 'Discard them', value: 'discard' });
        return options;
    });

    /** Two states where "finish" is ambiguous: nothing chosen for the
     *  leftovers yet, or move-to-an-existing-list picked with no target. */
    const finishBlocked = computed(() => {
        if (untickedCount.value === 0) return false;
        if (leftoverAction.value === null) return true;
        return leftoverAction.value === 'move-existing' && !leftoverTargetListId.value;
    });

    const finishCtaLabel = computed(() => {
        if (untickedCount.value === 0) return 'Finish';
        if (leftoverAction.value === 'discard') return 'Discard & finish';
        return 'Move & finish';
    });

    /** Run once each if the dialog closes without finishing. A list: two
     *  quick ticks can both land as "the last one" and both open the dialog,
     *  and closing it must untick both. */
    let cancels: (() => void)[] = [];
    let finished = false;

    function openFinishReview(options?: { onCancel?: () => void }) {
        if (!detail.value) return;
        if (finishReviewOpen.value) {
            // Already up: keep the decision the user is part-way through.
            if (options?.onCancel) cancels.push(options.onCancel);
            return;
        }
        cancels = options?.onCancel ? [options.onCancel] : [];
        finished = false;
        // Reset the leftover decision each time the dialog opens — it is a
        // choice about *this* finish, not a remembered preference, and it
        // starts unmade so the dialog can't be confirmed past it.
        leftoverAction.value = null;
        leftoverTargetListId.value =
            otherActiveLists.value[0]?.shopping_list_id ?? null;
        const seen = new Set<string>();
        finishEntries.value = detail.value.lines
            .filter((l) => l.is_ticked)
            .filter((l) => {
                // One row per stock item — duplicate anchors (nested
                // product lines) collapse into the parent's entry.
                if (!l.stock_item_id) return true;
                if (seen.has(l.stock_item_id)) return false;
                seen.add(l.stock_item_id);
                return true;
            })
            .map((l) => ({
                line_id: l.line_id,
                stock_item_id: l.stock_item_id,
                name: l.stock_item_name,
            }));
        finishReviewOpen.value = true;
    }

    /** Clears the unticked lines off this list per the dialog's choice, before
     *  the finish archives it. Returns how many moved and how many were
     *  discarded, so the toast can say which happened.
     *
     *  Order matters: this has to happen *first*. `finishAsync` archives the
     *  list, and the server refuses to move lines onto (or, once done,
     *  meaningfully off) an archived list. */
    async function disposeLeftoversBeforeFinish(): Promise<{
        moved: number;
        discarded: number;
    }> {
        const none = { moved: 0, discarded: 0 };
        if (untickedCount.value === 0 || leftoverAction.value === null) return none;

        if (leftoverAction.value === 'discard') {
            const result = await api.discardUntickedAsync(listId.value);
            return { moved: 0, discarded: result.removed_count };
        }

        let targetId = leftoverTargetListId.value;
        if (leftoverAction.value === 'move-new') {
            // Two calls rather than one, and deliberately not a per-item
            // loop: create the list, then move the whole leftover set into
            // it in a single request.
            const created = await api.createAsync({
                name: `Leftovers from ${detail.value?.display_name ?? 'last shop'}`,
            });
            targetId = created.shopping_list_id;
        }
        if (!targetId) return none;

        const result = await api.moveUntickedToAsync(listId.value, targetId);
        return { moved: result.moved_count, discarded: 0 };
    }

    async function confirmFinish() {
        if (finishBlocked.value) return;
        finishing.value = true;
        try {
            const { moved, discarded } = await disposeLeftoversBeforeFinish();
            const restockedIds = [...new Set(
                (detail.value?.lines ?? [])
                    .filter((l) => l.is_ticked && l.stock_item_id)
                    .map((l) => l.stock_item_id as string),
            )];
            const result = await api.finishAsync(listId.value);
            finished = true;
            finishReviewOpen.value = false;
            if (moved > 0) {
                $q.notify({
                    type: 'positive',
                    message: `${moved} unticked item${
                        moved === 1 ? '' : 's'
                    } moved for later.`,
                });
            }
            if (discarded > 0) {
                $q.notify({
                    type: 'positive',
                    message: `${discarded} unticked item${
                        discarded === 1 ? '' : 's'
                    } discarded.`,
                });
            }
            await Promise.all([
                refreshAll(),
                stockItemStore.getStockItemsAsync(),
            ]);
            // The finish restocks server-side (and harvests prices), bypassing
            // the store mutations that would otherwise mark these stale.
            restockedIds.forEach((id) => {
                stockItemStore.invalidateLevelOverlays(id);
                invalidateBuyVerdict(id);
            });
            recipeStore.invalidateRecipes();
            $q.notify({
                type: 'positive',
                message: `Shopping finished. ${result.items_restocked} item${
                    result.items_restocked === 1 ? '' : 's'
                } bought.`,
            });
        } catch (err) {
            // The leftovers may already have moved or gone before the finish
            // itself failed. Re-read so `untickedCount` reflects that and a
            // retry doesn't dispose of them a second time (e.g. a second
            // "Leftovers from …" list).
            await refreshDetailQuietly();
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not finish shopping.',
                    caption: toastCaption(err),
                });
            }
        } finally {
            finishing.value = false;
        }
    }

    // Every unticked line, set-aside-by-budget ones included: those are
    // leftovers that go wherever the rest go (owner, 2026-10-30, FU-958), and
    // the server's move/discard actions take them too, so the dialog's figure
    // is what is about to move. It names the set-aside share so the number
    // doesn't read as more than the run face showed.
    const untickedCount = computed(() =>
        (detail.value?.lines ?? []).filter((l) => !l.is_ticked).length
    );
    const deferredUntickedCount = computed(() =>
        (detail.value?.lines ?? []).filter((l) => !l.is_ticked && l.deferred_by_budget).length
    );
    // The list-level money (`remaining_price`, `total_price`, `savings_vs_shelf_price`),
    // the progress percentage and the status pill's label all moved into
    // `ShoppingListOverviewCard`, which is the only thing that rendered them.
    // They stay server-owned there (state-ownership Type B) — read off
    // `detail.totals`, never re-summed. What's left here are the two counts the
    // *finish* flow needs, which is a different question from what the header
    // shows.

    const otherActiveLists = computed(() =>
        store.summaries.filter(
            (s) => s.status !== 'done' && s.shopping_list_id !== listId.value
        )
    );

    watch(finishReviewOpen, (open) => {
        if (open || finished) return;
        const pending = cancels;
        cancels = [];
        pending.forEach((cancel) => cancel());
    });

    defineExpose({ show: openFinishReview });
</script>
