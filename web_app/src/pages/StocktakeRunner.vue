<template>
    <!-- FU-609 / R-036 — app-shell root: <q-page :style-fn> so the full-bleed
         runner fills the viewport below the header without a hardcoded offset. -->
    <q-page class="runner-shell" :style-fn="appShellStyleFn">
        <!-- ── Top progress strip ──────────────────────────────────────
             Close X on the left, progress bar with count in the middle,
             (?) help on the right. No separate landing page any more —
             empty-queue is a state of this same view. -->
        <div class="runner-topbar">
            <BaseButton
                variant="icon"
                :icon="ICONS.close"
                :to="'/stock'"
                aria-label="Close stocktake"
            />
            <!-- The bar tracks the WALK only. Review and Sweep are single
                 screens with their own "how many" in their own copy, and a
                 progress bar that jumped backwards on entering a new phase
                 would read as a bug. They get a phase name instead. -->
            <q-linear-progress
                v-if="phase === 'walk' && hasQueue"
                :value="progress"
                rounded
                size="6px"
                color="primary"
                class="col q-mx-md"
            />
            <!-- Owner, 2026-09-01: the tiny "Reviewing" / "Tidying up" caption
                 that sat here was removed. Review and Sweep each open with their
                 own full-size heading saying the same thing, so this was a
                 second, smaller, worse label for the screen you're already
                 looking at. -->
            <div v-else class="col" />
            <div v-if="phase === 'walk' && hasQueue" class="text-caption dora-text-muted q-mr-sm">
                {{ reviewedCount }} / {{ session.length }}
            </div>
            <!-- Owner feedback 2026-08-27: *"Info button should take you to
                 help and guides, not open a modal."* The explainer this used to
                 open now lives in Help → Guides → Stocktake; the `?q=` seeds
                 that page's filter so the deep-link lands on the one entry
                 rather than the whole library. The title in the query string
                 must match the guide entry's `title` in `HelpPage.vue`. -->
            <BaseButton
                variant="icon"
                :icon="ICONS.help_outline"
                aria-label="How stocktake works"
                :to="{ path: '/help', query: { q: 'How stocktake works' } }"
            />
        </div>

        <!-- ── Loading ─────────────────────────────────────────────── -->
        <div v-if="loading" class="runner-card-wrap">
            <q-spinner color="warning" size="42px" />
        </div>

        <!-- ── Switched off install-wide (2026-08-20) ──────────────────
             Nothing links here when the flag is off, so this is the stale
             bookmark / typed-URL case. It gets its own state rather than
             falling through to "you're all caught up", which would be a
             comforting lie about a feature that isn't running. -->
        <div v-else-if="!stocktakeEnabled" class="runner-card-wrap">
            <q-card class="runner-card" flat>
                <q-card-section class="text-center q-pt-lg">
                    <q-icon :name="ICONS.fact_check" size="64px" class="dora-text-muted-7" />
                    <div class="text-h5 q-mt-sm">Stocktake is turned off.</div>
                    <div class="text-caption dora-text-muted-7 q-mt-xs">
                        An admin can turn it back on in Settings → System →
                        Stocktake.
                    </div>
                </q-card-section>
                <q-card-actions align="center" class="q-pb-lg">
                    <BaseButton label="Back to Stock" :to="'/stock'" />
                </q-card-actions>
            </q-card>
        </div>

        <!-- ── Nothing to do at all ────────────────────────────────── -->
        <div v-else-if="nothingToDo" class="runner-card-wrap">
            <q-card class="runner-card" flat>
                <q-card-section class="text-center q-pt-lg">
                    <q-icon :name="ICONS.check_circle" color="positive" size="64px" />
                    <div class="text-h5 q-mt-sm">You're all caught up.</div>
                    <div class="text-caption dora-text-muted-7 q-mt-xs">
                        Nothing needs a check right now. Dora will surface
                        items again when they're due.
                    </div>
                </q-card-section>
                <q-card-actions align="center" class="q-pb-lg">
                    <BaseButton label="Back to Stock" :to="'/stock'" />
                </q-card-actions>
            </q-card>
        </div>

        <!-- ── Phase 1: Review (D-3) ───────────────────────────────────
             A desk screen, so it comes before the walk: agreeing with
             evidence-derived guesses doesn't need you in the pantry, and
             clearing them first means you walk in with a shorter list.
             Absent entirely when there's nothing confident to review —
             the normal case on a young install, and always for a user
             with inference switched off. -->
        <StocktakeReviewPhase
            v-else-if="phase === 'review'"
            :items="reviewItems"
            :busy="busy"
            @confirm="onReviewConfirm"
        />

        <!-- ── Phase 3: Sweep (D-4) ────────────────────────────────── -->
        <StocktakeSweepPhase
            v-else-if="phase === 'sweep'"
            :items="sweepItems"
            :busy="busy"
            @keep="onSweepKeep"
            @mute="onSweepMute"
            @remove="onSweepDelete"
            @finish="onSweepFinish"
        />

        <!-- ── Phase 2: Walk — the current item card ───────────────── -->
        <div v-else-if="current" class="runner-card-wrap">
            <q-card class="runner-card" flat>
                <q-card-section class="text-center">
                    <div class="text-h5">{{ current.name }}</div>
                    <!-- Full breadcrumb (owner, 2026-09-01). This is the one
                         screen where you get up and go and find the thing, so
                         the leaf name on its own ("Top shelf") is exactly the
                         wrong half of the answer. -->
                    <div class="text-caption dora-text-muted-7 q-mt-xs">
                        {{ currentLocation }}
                    </div>
                    <div class="text-caption dora-text-muted q-mt-xs">
                        Checked every {{ bandLabel(current.cadence_band) }}
                        · {{ current.overdue_days }} day{{ current.overdue_days === 1 ? '' : 's' }} overdue
                        <InfoTip label="What the cadence line means">
                            How often stocktake mode wants you to re-check this
                            item (Weekly / Fortnightly / Monthly) and how far
                            past the last check date you are. Cadence is set
                            globally in Settings or per-item on the detail page.
                        </InfoTip>
                    </div>

                    <!-- Chunk 5 / D-1: the queue is ordered least-certain
                         first, and D-1 explicitly rules out a toggle or a sort
                         selector to explain that. So the *item* explains it:
                         when belief is why this row came up when it did, it
                         says so, in belief's own words (server-owned copy, so
                         it's the same sentence the level picker shows).
                         `confident` rows get nothing — they're at the bottom
                         of the walk and "Dora already knows this" is not a
                         reason to look harder.

                         Owner, 2026-09-12: the block used to open with "Dora's
                         not sure about this one" on every card — which is the
                         premise of the whole runner, not news about this item —
                         and then the reason said the band again. It now leads
                         with the same "Dora thinks <band>" the overview chip
                         uses, and the reason underneath just tells the story. -->
                    <div
                        v-if="current.check_rank === 'uncertain' && current.belief_reason"
                        class="runner-belief q-mt-sm"
                    >
                        <div class="runner-belief__head">
                            <q-icon :name="ICONS.dora_voice" size="14px" />
                            <span>Dora thinks {{ beliefWord(current.belief_band) }}</span>
                        </div>
                        {{ current.belief_reason }}
                    </div>
                </q-card-section>

                <!-- Primary row: two big buttons, side by side.
                     Still correct: positive.
                     Change level: coloured to the current level so the
                     button doubles as the level readout. Small "(change)"
                     underneath makes the action explicit. -->
                <q-card-section class="runner-primary-row">
                    <BaseButton
                        variant="positive"
                        size="lg"
                        class="col runner-primary"
                        :icon="ICONS.check"
                        label="Still correct"
                        :loading="busy"
                        @click="onStillCorrect"
                    />
                    <!-- carve-out — raw q-btn: labeled dynamic-color button with custom stacked children, not an icon-variant fit -->
                    <q-btn
                        unelevated
                        no-caps
                        size="lg"
                        :color="currentLevelColour ?? undefined"
                        :class="[
                            'col runner-primary runner-change-level',
                            { 'runner-change-level--neutral': !currentLevelColour },
                        ]"
                        :loading="busy"
                        @click="changeOpen = true"
                    >
                        <div class="runner-change-level__stack">
                            <div class="runner-change-level__level">
                                {{ current.stock_level_name ?? '–' }}
                            </div>
                            <div class="runner-change-level__hint">(change)</div>
                        </div>
                    </q-btn>
                </q-card-section>

                <!-- Secondary row: three smaller buttons.
                     Skip = session-only, no API.
                     Push = 3-day snooze, no last_checked bump.
                     Mute = per-item off, with confirmation. -->
                <q-card-section class="runner-secondary-row">
                    <BaseButton
                        variant="ghost"
                        class="col"
                        :icon="ICONS.skip_next"
                        label="Skip"
                        :disable="busy"
                        @click="onSkip"
                    />
                    <BaseButton
                        variant="ghost"
                        class="col"
                        :icon="ICONS.snooze"
                        label="Push 3 days"
                        :loading="busy"
                        @click="onPush"
                    >
                        <BaseTooltip>
                            Delays this item's next stocktake prompt by 3 days
                            without recording a check. Use when you'll be able to
                            look properly soon.
                        </BaseTooltip>
                    </BaseButton>
                    <BaseButton
                        variant="danger-ghost"
                        class="col"
                        :icon="ICONS.mute"
                        label="Mute"
                        :disable="busy"
                        @click="onMute"
                    />
                </q-card-section>
            </q-card>
        </div>

        <!-- ── Session-complete card ────────────────────────────────
             Five-counter summary + optional batch add-to-list for
             items marked Low or Out during the session (SK-7). -->
        <div v-else class="runner-card-wrap">
            <q-card class="runner-card" flat>
                <q-card-section class="text-center">
                    <q-icon :name="ICONS.check_circle" color="positive" size="64px" />
                    <div class="text-h5 q-mt-sm">Stocktake complete</div>
                    <div class="runner-summary">
                        <div class="runner-summary__row">
                            <span class="runner-summary__count">{{ summary.checked }}</span>
                            <span class="dora-text-muted-7">checked</span>
                        </div>
                        <div class="runner-summary__row">
                            <span class="runner-summary__count">{{ summary.changed }}</span>
                            <span class="dora-text-muted-7">changed</span>
                        </div>
                        <div class="runner-summary__row">
                            <span class="runner-summary__count">{{ summary.skipped }}</span>
                            <span class="dora-text-muted-7">skipped</span>
                        </div>
                        <div class="runner-summary__row">
                            <span class="runner-summary__count">{{ summary.pushed }}</span>
                            <span class="dora-text-muted-7">pushed</span>
                        </div>
                        <div class="runner-summary__row">
                            <span class="runner-summary__count">{{ summary.muted }}</span>
                            <span class="dora-text-muted-7">muted</span>
                        </div>
                    </div>
                </q-card-section>

                <!-- SK-7: if anything went Low or Out this session, offer to
                     add them all to a shopping list in one action. Any active
                     list is a valid target. -->
                <!-- SK-7. Owner, 2026-09-01: this used to be a blind "add all
                     N" button over a radio dialog of lists — you couldn't see
                     what was about to go on, or drop one of them. It now opens
                     the same `AddToListDialog` recipes and meal plans use, so
                     there is one add-to-a-list flow in the app (R-001/R-003)
                     and it can't drift on this surface. -->
                <q-card-section v-if="restockNeeded.length > 0" class="runner-restock-prompt">
                    <div class="text-subtitle2 q-mb-sm text-center">
                        {{ restockNeeded.length }} item{{ restockNeeded.length === 1 ? '' : 's' }}
                        went Low or Out.
                    </div>
                    <BaseButton
                        variant="primary"
                        class="full-width"
                        :icon="ICONS.add_shopping_cart"
                        label="Add to a list…"
                        :disable="restockDone"
                        @click="restockPickerOpen = true"
                    />
                    <div v-if="restockDone" class="text-caption dora-text-muted-7 text-center q-mt-sm">
                        Added.
                    </div>
                </q-card-section>

                <q-card-actions align="center" class="q-pb-md">
                    <BaseButton label="Done" :to="'/stock'" />
                </q-card-actions>
            </q-card>
        </div>

        <!-- ── Level picker dialog ─────────────────────────────────
             SK-8: each option renders the level's colour dot so the
             picker matches the Stock Overview visual language. -->
        <BaseDialog v-model="changeOpen" title="Set level" closable card-style="min-width: 280px">
            <q-card-section>
                <q-list>
                    <q-item
                        v-for="level in stockLevels"
                        :key="level.stock_level_id"
                        clickable
                        v-close-popup
                        @click="onPickLevel(level.stock_level_id, level.sequence)"
                    >
                        <q-item-section avatar>
                            <StockLevelDot :sequence="level.sequence" size="14px" />
                        </q-item-section>
                        <q-item-section>{{ level.name }}</q-item-section>
                    </q-item>
                </q-list>
            </q-card-section>
        </BaseDialog>

        <!-- SK-7's picker — the shared component, so what you see here is
             what recipes and meal plans show. -->
        <AddToListDialog
            ref="restockPickerRef"
            v-model="restockPickerOpen"
            title="Add what ran low to a list"
            :rows="restockRows"
            default-new-list-name="Stocktake restock"
            @confirm="onRestockConfirm"
        />
    </q-page>
</template>

<script lang="ts" setup>
    import { appShellStyleFn } from 'src/helpers/appShell';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import InfoTip from 'src/components/help/InfoTip.vue';
    import { ICONS } from 'src/style/icons';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import StockLevelDot from 'src/components/stock/StockLevelDot.vue';
    import AddToListDialog from 'src/components/shoppingList/AddToListDialog.vue';
    import StocktakeReviewPhase from 'src/components/stocktake/StocktakeReviewPhase.vue';
    import StocktakeSweepPhase from 'src/components/stocktake/StocktakeSweepPhase.vue';
    import { useQuasar } from 'quasar';
    import { storeToRefs } from 'pinia';
    import { computed, onMounted, reactive, ref } from 'vue';
    import StocktakeApiService, {
        type CadenceBand,
        type StocktakeSessionItem,
        type StocktakeSweptItem,
    } from 'src/services/api/stocktakeApiService';
    import { useShoppingListActions } from 'src/composables/useShoppingListActions';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import type {
        AddToListConfirm, AddToListRow,
    } from 'src/components/shoppingList/addToListTypes';
    import { formatLocation } from 'src/helpers/locationDisplay';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { colourForSequence } from 'src/helpers/stockLevelLogic';
    import { needsRestockSequence } from 'src/helpers/stockStatus';
    import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import { useConfirm } from 'src/composables/useConfirm';

    const $q = useQuasar();

    const { confirm } = useConfirm();
    // 2026-08-20 — install-wide stocktake switch. Off ⇒ the runner shows its
    // own off-state above (the server already resolves an empty queue).
    const { stocktake: stocktakeEnabled } = useFeatureFlags();
    const api = new StocktakeApiService();
    // Level / mute / delete writes go through the store (R-074; finalisation
    // 05-R5): writing the API directly left `/stock` showing pre-stocktake
    // levels until a hard reload and skipped the auto-add toast.
    const stockItemStore = useStockItemStore();

    const stockLevelStore = useStockLevelStore();
    const { stockLevels } = storeToRefs(stockLevelStore);
    const shoppingListStore = useShoppingListStore();
    const { addStockItemsToList } = useShoppingListActions();

    const loading = ref(true);
    const session = ref<StocktakeSessionItem[]>([]);
    const index = ref(0);
    const busy = ref(false);
    const changeOpen = ref(false);
    // ── Three phases: shrink → work → tidy (Chunk 6 / D-4) ──────────────────
    // `done` is the existing summary card. Every phase can be empty and is then
    // skipped **silently** — an install younger than a few months has no
    // confident items at all (high confidence needs ~3 logged purchases), and a
    // user with inference off never has a Review phase by design. Announcing
    // "0 items to review" would be a screen whose only content is its own
    // absence.
    type Phase = 'review' | 'walk' | 'sweep' | 'done';
    const phase = ref<Phase>('walk');
    const reviewItems = ref<StocktakeSessionItem[]>([]);
    const sweepItems = ref<StocktakeSweptItem[]>([]);
    /** Set while the shared level picker is open on behalf of a Sweep row
     *  rather than the walk's current item. */
    const sweepKeepId = ref<string | null>(null);

    /** No review, no walk, no sweep — the "all caught up" card. Distinct from
     *  `done`, which is the summary of work actually performed. */
    const nothingToDo = computed(() =>
        reviewItems.value.length === 0
        && session.value.length === 0
        && sweepItems.value.length === 0,
    );

    /** The first phase with anything in it, in fixed order. */
    function firstNonEmptyPhase(): Phase {
        if (reviewItems.value.length > 0) return 'review';
        if (session.value.length > 0) return 'walk';
        if (sweepItems.value.length > 0) return 'sweep';
        return 'done';
    }

    /** Five-counter summary powering the completion screen. */
    const summary = reactive({
        checked: 0,
        changed: 0,
        skipped: 0,
        pushed: 0,
        muted: 0,
    });

    /**
     * Items the user set to Low or Out via Change-level during THIS
     * session. Drives the SK-7 batch add-to-list prompt on the
     * completion screen. A later Change-level on the same item
     * upgrades whatever it was to the latest choice (e.g. flip Low →
     * Stocked → drop; last write wins).
     */
    const restockNeeded = ref<Array<{ stock_item_id: string; name: string }>>([]);
    const restockDone = ref(false);
    const restockPickerOpen = ref(false);
    const restockPickerRef = ref<InstanceType<typeof AddToListDialog> | null>(null);

    /**
     * The session's Low/Out flips in the shared picker's row shape.
     *
     * Every row is `isMissing`, which is what makes them all start ticked —
     * they are here *because* the user just said they'd run down, so proposing
     * the whole set is the honest default. The dialog still unticks anything
     * already on a list and lets you drop the rest by hand.
     */
    const restockRows = computed<AddToListRow[]>(() =>
        restockNeeded.value.map((r) => ({
            stockItemId: r.stock_item_id,
            name: r.name,
            isMissing: true,
            isLowStock: false,
            isOptional: false,
            quantityLabel: null,
            sources: [],
        })),
    );

    const hasQueue = computed(() => session.value.length > 0 && index.value < session.value.length);
    const current = computed<StocktakeSessionItem | null>(() =>
        index.value < session.value.length ? session.value[index.value]! : null,
    );
    const reviewedCount = computed(() => index.value);
    const progress = computed(() =>
        session.value.length === 0 ? 0 : index.value / session.value.length,
    );

    /** Full breadcrumb for the walk card, leaf name as a fallback for any row
     *  that arrives without one. */
    const currentLocation = computed(() => {
        const c = current.value;
        if (!c) return 'No location';
        return formatLocation(c.stock_location_breadcrumb, 'full')
            || c.stock_location_name
            || 'No location';
    });

    const currentLevelColour = computed(() => {
        const c = current.value;
        if (!c) return null;
        const level = stockLevelStore.levelById.get(c.stock_level_id ?? '');
        return colourForSequence(level?.sequence);
    });

    // Belief's own words, matching the level picker's belief header on the
    // stock overview so the phrase a user learns in one place reads the same
    // in the other.
    function beliefWord(band: string | null): string {
        return band ?? 'something has changed';
    }

    function bandLabel(band: CadenceBand): string {
        // Weekly → "week", Fortnightly → "fortnight", Monthly → "month".
        // Matches how the copy reads inline ("Checked every week").
        switch (band) {
            case 'weekly': return 'week';
            case 'fortnightly': return 'fortnight';
            case 'monthly': return 'month';
        }
    }

    function advance() {
        index.value += 1;
        // Walk finished → tidy up, or straight to the summary. Doing this here
        // rather than in each of the five walk actions means a new action can't
        // forget to hand over.
        if (index.value >= session.value.length) {
            leaveWalk();
        }
    }

    function leaveWalk() {
        if (sweepItems.value.length > 0) {
            phase.value = 'sweep';
            return;
        }
        void finish();
    }

    /**
     * Enter the summary and stamp the Sweep watermark.
     *
     * The stamp happens **here and nowhere else** — not per phase, not on
     * abandon. Once the watermark passes a departure, that item is
     * indistinguishable from the long-dead ones forever, so a run the user
     * backed out of must not silently swallow a Sweep list they never saw.
     * A failed stamp is deliberately silent: the cost is seeing the same tidy-up
     * list next time, which is a great deal better than a red toast on the
     * "you're done" screen.
     */
    async function finish() {
        phase.value = 'done';
        try {
            await api.completeSessionAsync();
        } catch {
            // intentionally quiet — see above.
        }
    }

    async function onStillCorrect() {
        if (!current.value) return;
        busy.value = true;
        try {
            await api.checkOneAsync(current.value.stock_item_id);
            summary.checked += 1;
            advance();
        } catch (err) {
            $q.notify({
                type: 'negative',
                position: 'top',
                message: 'Could not confirm.',
                caption: toastCaption(err),
            });
        } finally { busy.value = false; }
    }

    async function onPickLevel(levelId: string, sequence: number) {
        // Two callers now: the walk card's "Change level", and the Sweep
        // phase's "I still keep this" (which is a level-set by design — see
        // `onSweepKeep`). `sweepKeepId` says which, and is cleared either way
        // so a later walk pick can't be misattributed.
        if (sweepKeepId.value) {
            const stockItemId = sweepKeepId.value;
            sweepKeepId.value = null;
            busy.value = true;
            try {
                await stockItemStore.updateStockLevelAsync({
                    stock_item_id: stockItemId,
                    stock_level_id: levelId,
                });
                summary.changed += 1;
                dropFromSweep(stockItemId);
            } catch (err) {
                $q.notify({
                    type: 'negative',
                    position: 'top',
                    message: 'Could not update.',
                    caption: toastCaption(err),
                });
            } finally { busy.value = false; }
            return;
        }
        if (!current.value) return;
        const stockItemId = current.value.stock_item_id;
        const itemName = current.value.name;
        busy.value = true;
        try {
            await stockItemStore.updateStockLevelAsync({
                stock_item_id: stockItemId,
                stock_level_id: levelId,
            });
            summary.changed += 1;
            // SK-7 tracking: this session's Low/Out flips feed the
            // batch add-to-list prompt on the completion screen.
            // Dedupe if the user Changes the same item twice.
            const isRestockable = needsRestockSequence(sequence);
            const existingIdx = restockNeeded.value.findIndex(
                (r) => r.stock_item_id === stockItemId,
            );
            if (isRestockable) {
                if (existingIdx === -1) {
                    restockNeeded.value.push({ stock_item_id: stockItemId, name: itemName });
                }
            } else if (existingIdx !== -1) {
                // User flipped it back to Stocked — take it out again.
                restockNeeded.value.splice(existingIdx, 1);
            }
            advance();
        } catch (err) {
            $q.notify({
                type: 'negative',
                position: 'top',
                message: 'Could not update.',
                caption: toastCaption(err),
            });
        } finally { busy.value = false; }
    }

    function onSkip() {
        if (!current.value) return;
        // Session-only: drop the item for THIS run and advance. No API,
        // so no clock change — it comes back next time the queue is built.
        // 2026-08-17 feedback: it used to be re-appended to the end of the
        // queue, which grew `session.length` on every skip — the progress
        // denominator crept up and the run could never be finished by
        // skipping. Skipping now resolves the item for the session.
        summary.skipped += 1;
        advance();
    }

    async function onPush() {
        if (!current.value) return;
        busy.value = true;
        try {
            await api.snoozeAsync(current.value.stock_item_id);
            summary.pushed += 1;
            advance();
        } catch (err) {
            $q.notify({
                type: 'negative',
                position: 'top',
                message: 'Could not push.',
                caption: toastCaption(err),
            });
        } finally { busy.value = false; }
    }

    /** Mute is nuclear (persistent, only un-mutable from item detail), so it
     *  always confirms first; the walk card and the sweep share the wording. */
    function confirmMute(name: string): Promise<boolean> {
        return confirm({
            title: `Mute ${name}?`,
            message:
                "Dora will stop asking about this item entirely. You can un-mute it later from the item's detail page.",
            okLabel: 'Mute',
            destructive: true,
        });
    }

    async function onMute() {
        if (!current.value) return;
        const stockItemId = current.value.stock_item_id;
        const itemName = current.value.name;
        if (!await confirmMute(itemName)) return;
        busy.value = true;
        try {
            await stockItemStore.updateStockItemAsync({
                stock_item_id: stockItemId,
                stocktake_alerts_are_enabled: false,
            });
            summary.muted += 1;
            advance();
        } catch (err) {
            $q.notify({
                type: 'negative',
                position: 'top',
                message: 'Could not mute.',
                caption: toastCaption(err),
            });
        } finally { busy.value = false; }
        }

    // ── Phase 1 — Review (D-3) ──────────────────────────────────────────────

    /**
     * Ticked rows get one bulk check; unticked rows join the walk.
     *
     * The unticked items are **prepended**, not appended: the user has just
     * said "I want to look at this one myself", and making them walk the whole
     * queue before getting to it would punish the disagreement this screen is
     * built to make cheap.
     */
    async function onReviewConfirm(payload: {
        checked: string[];
        unchecked: StocktakeSessionItem[];
    }) {
        busy.value = true;
        try {
            if (payload.checked.length > 0) {
                await api.bulkCheckAsync(payload.checked);
                summary.checked += payload.checked.length;
            }
            if (payload.unchecked.length > 0) {
                session.value = [...payload.unchecked, ...session.value];
            }
            reviewItems.value = [];
            phase.value = 'walk';
            // An empty walk means `advance()` will never fire, so hand over to
            // the next phase here instead.
            if (session.value.length === 0) leaveWalk();
        } catch (err) {
            $q.notify({
                type: 'negative',
                position: 'top',
                message: 'Could not save those checks.',
                caption: toastCaption(err),
            });
        } finally { busy.value = false; }
    }

    // ── Phase 3 — Sweep (D-4) ───────────────────────────────────────────────

    function dropFromSweep(stockItemId: string) {
        sweepItems.value = sweepItems.value.filter(
            (i) => i.stock_item_id !== stockItemId,
        );
        // Clearing the list is finishing the phase — there's nothing left to
        // leave be.
        if (sweepItems.value.length === 0) void finish();
    }

    /**
     * "I still keep this" → open the level picker.
     *
     * **Not a check.** The plan flagged this as a wiring risk and it was
     * confirmed at implementation: the engagement gate keys off in-stock /
     * ever-opened / level-adjusted-in-60d / on-a-list-in-60d, while
     * `POST /check` writes only `last_checked_at`. Wiring this button to a check
     * would have looked like it worked and left the item out of rotation.
     * Setting a level writes a `StockLevelChange` (and, for anything in stock,
     * satisfies the gate outright) — and it's the truthful action anyway, since
     * the reason Dora lost track is that nobody has said what's on the shelf.
     */
    function onSweepKeep(item: StocktakeSweptItem) {
        sweepKeepId.value = item.stock_item_id;
        changeOpen.value = true;
    }

    async function onSweepMute(item: StocktakeSweptItem) {
        if (!await confirmMute(item.name)) return;
        busy.value = true;
        try {
            await stockItemStore.updateStockItemAsync({
                stock_item_id: item.stock_item_id,
                stocktake_alerts_are_enabled: false,
            });
            summary.muted += 1;
            dropFromSweep(item.stock_item_id);
        } catch (err) {
            $q.notify({
                type: 'negative',
                position: 'top',
                message: 'Could not mute.',
                caption: toastCaption(err),
            });
        } finally { busy.value = false; }
        }

    async function onSweepDelete(item: StocktakeSweptItem) {
        // Deletion is the one irreversible action in the runner, and it's being
        // offered about an item the user may simply have forgotten they own —
        // so the confirm names it and says what goes with it.
        const ok = await confirm({
            title: `Delete ${item.name}?`,
            message:
                'This removes the item and its history for good. If you just want Dora to stop asking about it, mute it instead.',
            okLabel: 'Delete',
            destructive: true,
        });
        if (!ok) return;
        busy.value = true;
        try {
            await stockItemStore.deleteStockItemAsync(item.stock_item_id);
            dropFromSweep(item.stock_item_id);
        } catch (err) {
            $q.notify({
                type: 'negative',
                position: 'top',
                message: 'Could not delete.',
                caption: toastCaption(err),
            });
        } finally { busy.value = false; }
    }

    function onSweepFinish() {
        void finish();
    }

    /**
     * The picker reports which items and which list; `addStockItemsToList`
     * owns the "or create the list first" branch, so the no-active-lists
     * dead-end this surface used to hit ("No active lists. Create one first.")
     * is gone — "+ New list" is an option inside the dialog.
     */
    async function onRestockConfirm(payload: AddToListConfirm) {
        restockPickerRef.value?.setBusy(true);
        try {
            const listId = await addStockItemsToList(
                payload.targetListId,
                payload.stockItemIds,
                restockPickerRef.value?.newListName ?? 'Stocktake restock',
            );
            if (listId === null) return;
            restockDone.value = true;
            restockPickerOpen.value = false;
        } finally {
            restockPickerRef.value?.setBusy(false);
        }
    }

    onMounted(async () => {
        try {
            await stockLevelStore.ensureLoadedAsync();
            await shoppingListStore.refreshAsync();
            // Chunk 6 — one read for all three phases. Chunk 5's note still
            // holds: the walk arrives already ordered (least-certain first, or
            // most-overdue first when there's no evidence) and must NOT be
            // re-sorted here. The ranking rule is server-owned; a second
            // opinion on the client is exactly the two-engines problem Chunk 3
            // spent itself removing. `ranked_by` only picks help-dialog wording.
            const result = await api.sessionAsync();
            reviewItems.value = result.review;
            session.value = result.walk;
            sweepItems.value = result.sweep;
            phase.value = firstNonEmptyPhase();
        } finally {
            loading.value = false;
        }
    });
</script>

<style scoped>
    /* Fullscreen focus mode.
       Owner, 2026-09-01: this used to pin itself to `--palette-neutral-900`
       under every theme — the reasoning was that the contrast *is* the
       "you're concentrating" affordance. In practice it read as a bug: you
       drive the app in a light theme and stocktake alone goes black, and the
       phase screens had to paint themselves `--text-inverse` to survive it.
       It follows the theme now, like every other full-page surface (R-002). */
    .runner-shell {
        /* FU-609 / R-036 — height comes from the <q-page :style-fn> (viewport −
           live layout offset); no hardcoded 100vh (which ignored the header). */
        background: var(--surface-page);
        color: var(--text-primary);
        display: flex; flex-direction: column;
    }
    .runner-topbar {
        display: flex; align-items: center; padding: 12px;
        background: var(--surface-page);
    }
    .runner-card-wrap {
        flex: 1; display: flex; align-items: center; justify-content: center;
        padding: var(--space-6);
    }
    .runner-card {
        max-width: 480px; width: 100%;
        background: var(--surface-component); color: var(--text-primary);
        border-radius: 12px;
    }

    /* Why-this-item-first line (Chunk 5 / D-1). Still warning-toned — that's
       the "Dora thinks" vocabulary the level picker and the dashed level box
       use — but owner feedback 2026-09-01 was that amber text on an amber wash
       is unreadable (it measured ~2.1:1, well under D-002's 4.5 floor). Same
       fix the B2 tint chips took: the tint and the hairline carry the tone, the
       glyph stays saturated, and the words are page ink. */
    .runner-belief {
        font-size: var(--font-size-xs);
        line-height: 1.35;
        color: var(--text-primary);
        text-align: left;
        background: var(--semantic-warning-soft);
        border: 1px solid var(--semantic-warning);
        border-radius: var(--radius-sm, 4px);
        padding: 6px 8px;
    }
    .runner-belief .q-icon {
        color: var(--semantic-warning);
    }
    /* The band, said once, above its reason. */
    .runner-belief__head {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        font-weight: 600;
    }

    /* Two big primary buttons side-by-side. gap comes from `q-gutter-*`
       being awkward across sections, so we use a flex row directly. */
    .runner-primary-row {
        display: flex;
        gap: var(--space-2);
    }
    .runner-primary {
        min-height: 72px;
    }

    /* Change-level button: two stacked lines (level name + "(change)")
       inside q-btn's default slot. */
    .runner-change-level__stack {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
        line-height: 1.15;
    }
    .runner-change-level__level {
        font-size: var(--font-size-md);
        font-weight: 600;
    }
    .runner-change-level__hint {
        font-size: var(--font-size-xs);
        opacity: 0.85;
    }
    /* Out-of-stock / unknown level → neutral state. Uses theme tokens
       (R-002) rather than a hardcoded grey literal so it tracks dark
       + light themes. */
    .runner-change-level--neutral {
        background: var(--surface-sunken);
        color: var(--text-primary);
    }
    .runner-change-level--neutral:hover {
        background: color-mix(in srgb, var(--surface-sunken), var(--text-primary) 8%);
    }

    /* Secondary row: three smaller ghost-style actions. */
    .runner-secondary-row {
        display: flex;
        gap: var(--space-2);
        padding-top: 0;
    }

    /* Completion summary — five short rows, count on left, label on right. */
    .runner-summary {
        display: flex;
        flex-direction: column;
        gap: var(--space-1);
        max-width: 200px;
        margin: var(--space-4) auto 0;
    }
    .runner-summary__row {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: var(--space-3);
    }
    .runner-summary__count {
        font-size: var(--font-size-md);
        font-weight: 600;
        min-width: 24px;
        text-align: right;
    }

    .runner-restock-prompt {
        /* R-060: `--c-line` was never declared where this page can see it, so
           this always painted the hard-coded fallback (FU-747). */
        border-top: 1px solid var(--divider);
    }

</style>
