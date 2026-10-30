<template>
    <!--
        Phase 1 of the three-phase stocktake — **Review** (D-3 / D-4).
        A desk screen: these items are worked out from logged evidence
        (purchases, cooks), so you don't need to be standing in the pantry to
        agree with them.

        **The critical constraint from D-3: this must NOT be a "Confirm all (12)"
        button.** Users tap that reflexively by session three, at which point it
        *is* the auto-check that was explicitly rejected, with a human-shaped fig
        leaf — and every risk that rejection was protecting against comes back.

        So the screen is built to be *read*: real item names and the two levels
        — believed and recorded — one row each. Owner, 2026-09-12: the reason
        line was dropped. On this screen you are agreeing or disagreeing at a
        glance, twelve times in a row; the cadence story behind each guess is a
        paragraph nobody reads here. It still lives on the walk card and the
        stock-item page, where you're looking at one item. Everything is
        pre-ticked, so agreeing is still one tap. The value being delivered is
        not "confirm in bulk" — it's that **disagreeing is cheap**: untick a row
        and it joins the items you check yourself.

        Copy note (owner, 2026-09-01): nothing user-facing says "walk". The
        internal phase is still called that — it names the posture, and the
        server sends a `walk` array — but on screen this is all just stocktake.
    -->
    <div class="stocktake-review">
        <div class="stocktake-review__head">
            <div class="text-h6">Dora's fairly sure about these</div>
            <div class="text-caption dora-text-muted-7 q-mt-xs">
                Worked out from your shopping and cooking.
                Untick anything you'd rather check yourself.
            </div>
        </div>

        <q-list separator class="stocktake-review__list">
            <q-item
                v-for="item in items"
                :key="item.stock_item_id"
                clickable
                @click="toggle(item.stock_item_id)"
            >
                <q-item-section side top>
                    <!-- DR-15 / D-010: the tick is the gesture this phase is
                         made of, repeated once per item. `dora-press`
                         (motion.scss) answers each one in 120ms. -->
                    <q-checkbox
                        class="dora-press"
                        :aria-label="item.name"
                        :model-value="isTicked(item.stock_item_id)"
                        @update:model-value="toggle(item.stock_item_id)"
                        @click.stop
                    />
                </q-item-section>
                <q-item-section>
                    <!-- No location here (owner, 2026-09-01). This screen is
                         read at a desk — you aren't going to go and find
                         anything — so the name is the whole identity. The walk
                         card, where you *do* go and look, shows the full
                         breadcrumb. -->
                    <q-item-label class="stocktake-review__name">
                        {{ item.name }}
                    </q-item-label>
                    <!-- Owner, 2026-09-01: the whole line used to be amber, so
                         the two levels — the thing you actually scan for —
                         didn't stand out from the sentence carrying them. The
                         words are neutral ink now and the levels are tinted
                         pills in their own D-001 colour, so a column of these
                         can be glanced down instead of read. -->
                    <q-item-label caption class="stocktake-review__believed">
                        <span>Dora thinks</span>
                        <span :class="tintClassForSequence(sequenceForBand(item.belief_band))">
                            {{ bandWord(item.belief_band) }}
                        </span>
                        <!-- Owner 2026-10-15: "Dora thinks stocked · but is
                             currently stocked" read as a contradiction. The
                             recorded level only earns a mention when it says
                             something different. -->
                        <template v-if="item.stock_level_name && !agrees(item)">
                            <span>· but is currently</span>
                            <span :class="tintClassForSequence(levelSequence(item.stock_level_id))">
                                {{ recordedWord(item) }}
                            </span>
                        </template>
                    </q-item-label>
                </q-item-section>
            </q-item>
        </q-list>

        <div class="stocktake-review__actions">
            <!-- The label counts what will actually be written, and says
                 "look at" for the rest, so the trade is visible before the tap
                 rather than discovered after it. -->
            <BaseButton
                variant="primary"
                class="full-width"
                :icon="ICONS.check"
                :label="confirmLabel"
                :loading="busy"
                @click="confirm"
            />
        </div>
    </div>
</template>

<script setup lang="ts">
    import { computed, ref, watch } from 'vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import { ICONS } from 'src/style/icons';
    import { tintClassForSequence } from 'src/helpers/stockLevelLogic';
    import { bandForSequence, sequenceForBand } from 'src/helpers/beliefBand';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import type { StocktakeSessionItem } from 'src/services/api/stocktakeApiService';

    const props = defineProps<{
        items: StocktakeSessionItem[];
        busy?: boolean;
    }>();

    const emit = defineEmits<{
        /**
         * `checked` get a bulk check written for them; `unchecked` flow into the
         * walk phase. The page owns both actions — it holds the API service and
         * the walk queue, and keeping the calls in one place is what stops this
         * component growing a second opinion about what a check means.
         */
        (e: 'confirm', payload: {
            checked: string[];
            unchecked: StocktakeSessionItem[];
        }): void;
    }>();

    // Pre-ticked, per D-3. Re-seeded if the item list is ever replaced under us
    // (a refetch) so a stale id set can't survive into a new session.
    const ticked = ref<Set<string>>(new Set());
    watch(
        () => props.items,
        (items) => { ticked.value = new Set(items.map((i) => i.stock_item_id)); },
        { immediate: true, deep: false },
    );

    function isTicked(id: string): boolean {
        return ticked.value.has(id);
    }
    function toggle(id: string): void {
        // Reassigned rather than mutated: a Set mutation isn't reactive.
        const next = new Set(ticked.value);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        ticked.value = next;
    }

    const tickedCount = computed(() => ticked.value.size);

    // The pill carries the tone, so the words inside it are just the level —
    // "it's low" inside an amber pill is the same sentence said twice.
    function bandWord(band: string | null): string {
        if (!band) return 'Unchanged';
        return band.charAt(0).toUpperCase() + band.slice(1);
    }

    // Belief speaks in bands; colour is keyed to level *sequence*. The
    // translation lives in `helpers/beliefBand`.
    // The row carries the level's id, not its sequence, so the catalogue
    // resolves it. Renaming a level must not change its colour (FU-050).
    const stockLevelStore = useStockLevelStore();
    function levelSequence(levelId: string | null): number | null {
        if (!levelId) return null;
        return stockLevelStore.levelById.get(levelId ?? '')?.sequence ?? null;
    }

    // Owner, 2026-09-12: the two pills on a row are read as a pair, so they
    // have to speak the same language — "Dora thinks Low · but is currently
    // Low Stock" reads as two different claims. The recorded level is said in
    // belief's words wherever the catalogue maps onto a band; a household's
    // extra levels (anything off the three canonical sequences) keep their own
    // name, because there's no band word to say instead.
    function recordedWord(item: StocktakeSessionItem): string {
        const band = bandForSequence(levelSequence(item.stock_level_id));
        return band ? bandWord(band) : (item.stock_level_name ?? '');
    }

    /** True when the recorded level falls in the same band Dora believes. */
    function agrees(item: StocktakeSessionItem): boolean {
        return bandForSequence(levelSequence(item.stock_level_id)) === item.belief_band;
    }

    const confirmLabel = computed(() => {
        if (tickedCount.value === 0) return 'Check them all myself';
        const noun = tickedCount.value === 1 ? 'item' : 'items';
        return `That's right for ${tickedCount.value} ${noun}`;
    });

    function confirm(): void {
        emit('confirm', {
            checked: [...ticked.value],
            unchecked: props.items.filter((i) => !ticked.value.has(i.stock_item_id)),
        });
    }
</script>

<style scoped lang="scss">
    /* Scrolls inside the runner's dark shell; the list is the only thing that
       moves, so the heading and the action stay put on a long list. */
    .stocktake-review {
        display: flex;
        flex-direction: column;
        max-height: 100%;
        width: 100%;
        max-width: 520px;
        margin: 0 auto;
        padding: 16px;
        gap: var(--space-3);
    }
    /* Owner, 2026-09-01: the runner shell follows the theme now, so the
       heading takes page ink rather than the always-white inverse it used
       when the shell was hard-coded dark. */
    .stocktake-review__head {
        text-align: center;
        color: var(--text-primary);
    }
    .stocktake-review__list {
        flex: 1 1 auto;
        overflow-y: auto;
        background: var(--surface-component);
        color: var(--text-primary);
        border-radius: 12px;
    }
    .stocktake-review__name {
        font-weight: 600;
    }
    /* Neutral ink; the tinted pills inside carry the level colour. Wraps as a
       flex row so a long level name pushes the next pill onto its own line
       rather than stretching the row. */
    .stocktake-review__believed {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--space-1);
        color: var(--text-secondary);
    }
    .stocktake-review__actions {
        flex: 0 0 auto;
    }
</style>
