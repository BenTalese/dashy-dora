<template>
    <!--
        FU-227 chunk 3 — the "Your prices" inline widget (C5 revised).
        Renders the baseline + above-usual signal + last-seen line +
        `Based on N prices` count + the two actions [Log a price] /
        [Full history].

        LC-2 — source-blind UI: never says "8 observations · 3 offers"; the
        count line reads "Based on N prices" so the user doesn't have to
        ask what counts in vs out. The products-on offers sidecar is a
        separate section, never folded into baseline math or count chrome.
        `your_prices == null` renders the empty state.
    -->
    <!-- Owner 2026-10-15: same place, better dressed. The actions moved up
         into the header, the usual price became the card's figure, and the
         recent prices the page lists sit inside the card (default slot)
         instead of as a second box under it. -->
    <q-card flat bordered class="dora-your-prices q-mb-md">
        <div class="dora-your-prices__head">
            <q-icon :name="ICONS.price_check" size="20px" class="dora-text-secondary" />
            <div class="dora-your-prices__title">Your prices</div>
            <BaseButton
                variant="icon"
                :icon="ICONS.history"
                aria-label="Full history"
                :disable="!stockItemId"
                @click="historyOpen = true"
            >
                <BaseTooltip>Full history</BaseTooltip>
            </BaseButton>
            <BaseButton
                variant="primary"
                dense
                :icon="ICONS.cash_plus"
                label="Log a price"
                @click="dialogOpen = true"
            />
        </div>

        <div class="dora-your-prices__body">
            <!-- Below MIN_SAMPLES / null baseline: a calm empty state (a
                 not-enough-data case, not an opt-out). -->
            <template v-if="!yourPrices || yourPrices.baseline == null">
                <div class="text-body2 dora-text-secondary">{{ emptyStateCopy }}</div>
            </template>

            <template v-else>
                <div class="dora-your-prices__figure">
                    <div class="dora-your-prices__label">Usually</div>
                    <div class="dora-your-prices__amount">
                        {{ formatMoney(yourPrices.baseline) }}<span
                            v-if="yourPrices.baseline_unit"
                            class="dora-your-prices__unit"
                        > / {{ yourPrices.baseline_unit }}</span>
                    </div>
                </div>
                <span
                    class="dora-your-prices__verdict"
                    :class="yourPrices.above_baseline ? 'is-above' : 'is-usual'"
                >
                    <q-icon
                        :name="yourPrices.above_baseline ? ICONS.trending_up : ICONS.check"
                        size="14px"
                    />
                    {{ yourPrices.above_baseline ? 'Paying more than usual' : 'About average' }}
                </span>
            </template>

            <div v-if="yourPrices?.current != null" class="dora-your-prices__meta">
                Last seen
                <strong>{{ formatMoney(yourPrices.current) }}</strong>
                <span v-if="yourPrices.baseline_unit"> / {{ yourPrices.baseline_unit }}</span>
                <span v-if="yourPrices.last_observed_at">
                    · {{ relativeTime(yourPrices.last_observed_at) }}
                </span>
                <span v-if="yourPrices.last_seen_store_name">
                    · {{ yourPrices.last_seen_store_name }}
                </span>
                <span v-if="yourPrices.baseline != null">
                    · based on {{ yourPrices.sample_count }}
                    {{ yourPrices.sample_count === 1 ? 'price' : 'prices' }}
                </span>
            </div>

            <!-- LC-2 offers sidecar: separate from the baseline math. Only when
                 a linked product has a current offer in the same dimension. -->
            <div
                v-if="yourPrices && yourPrices.offers_sidecar.length > 0"
                class="dora-your-prices__shelf"
            >
                <div class="dora-your-prices__label">Current shelf prices</div>
                <div class="text-body2">
                    <span
                        v-for="(o, i) in yourPrices.offers_sidecar"
                        :key="`${o.store_name}-${i}`"
                    >
                        <span v-if="i > 0"> · </span>
                        <!-- The space lives INSIDE the span: Vue's whitespace
                             condense drops a newline-only gap between elements,
                             which rendered "$1.37/ qt" beside the "$1.89 / qt"
                             the lines above use. -->
                        <strong>{{ formatMoney(o.price_per_unit) }}</strong><span
                            class="dora-text-muted"
                        > / {{ o.unit }}</span>
                        at {{ o.store_name }}
                    </span>
                </div>
            </div>
        </div>

        <slot />

        <BaseDialog
            v-model="dialogOpen"
            title="Log a price"
            closable
            @cancel="dialogOpen = false"
        >
            <q-card-section>
                <PriceEntry
                    mode="shelf"
                    :prefill="prefill"
                    :stores="stores"
                    :busy="busy"
                    @submit="onSubmit"
                    @cancel="dialogOpen = false"
                />
            </q-card-section>
        </BaseDialog>

        <!-- "Full history" bottom-sheet (C5b). Lazy-fetches
             its own unioned series when opened. -->
        <PriceHistoryBottomSheet
            v-if="stockItemId"
            v-model="historyOpen"
            :stock-item-id="stockItemId"
            :item-name="itemName ?? ''"
        />
    </q-card>
</template>

<script setup lang="ts">
    import { computed, ref } from 'vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import PriceEntry from 'src/components/dora/PriceEntry.vue';
    import PriceHistoryBottomSheet from 'src/components/dora/PriceHistoryBottomSheet.vue';
    import { ICONS } from 'src/style/icons';
    import { relativeTime } from 'src/helpers/relativeTime';
    import { formatMoney } from 'src/composables/useMoney';
    import type {
        PriceEntryPrefill,
        YourPrices,
    } from 'src/models/stockItemDetail';
    import type { Store } from 'src/models/store';

    const props = withDefaults(
        defineProps<{
            yourPrices?: YourPrices | null | undefined;
            prefill?: PriceEntryPrefill | null | undefined;
            stores?: ReadonlyArray<Store> | undefined;
            busy?: boolean | undefined;
            /** FU-227 chunk 6 — drives the "Full history" bottom-sheet. When
             *  absent the button is disabled (the sheet needs an item to fetch). */
            stockItemId?: string | undefined;
            itemName?: string | undefined;
        }>(),
        {
            yourPrices: null, prefill: null, stores: () => [], busy: false,
            stockItemId: undefined, itemName: '',
        },
    );

    const emit = defineEmits<{
        (e: 'submit', value: {
            total_price: number;
            total_measure: number;
            unit: string;
            store_id: string | null;
            pack_count: number | null;
        }, done: () => void): void;
    }>();

    const dialogOpen = ref(false);
    const historyOpen = ref(false);

    // The widget handles the user-facing copy variants; the dialog only
    // emits up to the parent (which knows how to call the API service).
    const emptyStateCopy = computed(() => {
        const count = props.yourPrices?.sample_count ?? 0;
        if (count === 0) return 'No prices logged yet.';
        return 'Not enough price data yet.';
    });

    function onSubmit(value: {
        total_price: number;
        total_measure: number;
        unit: string;
        store_id: string | null;
        pack_count: number | null;
    }) {
        // The parent calls `done` once the save resolves, so a failed save
        // leaves the dialog open with the typed values intact.
        emit('submit', value, () => { dialogOpen.value = false; });
    }
</script>

<style scoped>
    /* Owner 2026-10-17: "style the card for your prices a little better".
       Card anatomy per D-017 (a card is `--radius-lg` + `--space-4`): a header
       bar on the sunken surface with the title at the sub-header size, the
       figure block on one rhythm (`--space-3`), and the slotted recent-prices
       list as aligned rows whose amounts share a right-hand column (D-018). */
    .dora-your-prices {
        border-radius: var(--radius-lg);
        overflow: hidden;
    }
    .dora-your-prices__head {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        padding: var(--space-2) var(--space-2) var(--space-2) var(--space-4);
        background: var(--surface-sunken);
        border-bottom: 1px solid var(--divider);
    }
    .dora-your-prices__title {
        flex: 1;
        font-size: var(--font-size-lg);
        font-weight: 700;
        color: var(--text-primary);
    }
    .dora-your-prices__body {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--space-3) var(--space-4);
        padding: var(--space-4);
    }
    .dora-your-prices__figure {
        display: flex;
        flex-direction: column;
        gap: var(--space-1);
    }
    /* :deep so the page's slotted "Recent prices" label wears it too. */
    .dora-your-prices :deep(.dora-your-prices__label) {
        font-size: var(--font-size-xs);
        font-weight: 600;
        color: var(--text-secondary);
    }
    .dora-your-prices__amount {
        font-size: var(--font-size-2xl);
        font-weight: 700;
        line-height: 1.1;
        font-variant-numeric: tabular-nums;
    }
    .dora-your-prices__unit {
        font-size: var(--font-size-sm);
        font-weight: 500;
        color: var(--text-secondary);
    }
    .dora-your-prices__verdict {
        display: inline-flex;
        align-items: center;
        gap: var(--space-1);
        padding: var(--space-1) var(--space-3);
        border-radius: var(--radius-pill);
        font-size: var(--font-size-sm);
        font-weight: 600;
    }
    .dora-your-prices__verdict.is-above {
        background: var(--semantic-warning-soft);
        color: var(--text-primary);
    }
    .dora-your-prices__verdict.is-usual {
        background: var(--semantic-positive-soft);
        color: var(--text-primary);
    }
    .dora-your-prices__meta {
        flex: 1 1 100%;
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
        font-variant-numeric: tabular-nums;
    }
    .dora-your-prices__shelf {
        flex: 1 1 100%;
        display: flex;
        flex-direction: column;
        gap: var(--space-1);
        background: var(--surface-sunken);
        border-radius: var(--radius-md);
        padding: var(--space-2) var(--space-3);
    }
    /* Recent prices the page slots in: flush with the card, a hairline above,
       the same small label as the figure's, amounts in one right-hand column. */
    .dora-your-prices :deep(.dora-your-prices__recent) {
        border-top: 1px solid var(--divider);
    }
    .dora-your-prices :deep(.dora-your-prices__recent-label) {
        padding: var(--space-3) var(--space-4) var(--space-1);
    }
    .dora-your-prices :deep(.dora-your-prices__list .q-item) {
        padding-left: var(--space-4);
        padding-right: var(--space-2);
    }
    .dora-your-prices :deep(.dora-your-prices__price) {
        font-weight: 700;
        font-variant-numeric: tabular-nums;
        text-align: right;
        color: var(--text-primary);
    }
</style>
