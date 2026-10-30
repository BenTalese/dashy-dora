<template>
    <DashboardCard :icon="ICONS.price_check" title="Price changes">
        <CardLoadError
            v-if="failed"
            line="I couldn't load your price changes."
            @retry="emit('retry')"
        />
        <!-- B10 — headline plus two ranked lists, in outline. Without it the
             card rendered its B9 empty state ("log what you paid for a couple
             of items…") to a household that had done exactly that, for the
             whole flight of the request. -->
        <div v-else-if="loading" class="pm-skeleton">
            <AppSkeleton type="line" width="60%" height="1.2em" />
            <div class="pm-columns">
                <div class="pm-skeleton__col">
                    <AppSkeleton
                        v-for="n in 3"
                        :key="n"
                        type="rect"
                        height="44px"
                        radius="var(--radius-md)"
                    />
                </div>
                <div class="pm-skeleton__col">
                    <AppSkeleton
                        v-for="n in 3"
                        :key="n"
                        type="rect"
                        height="44px"
                        radius="var(--radius-md)"
                    />
                </div>
            </div>
        </div>
        <template v-else-if="hasRows">
            <p class="pm-headline">{{ headline }}</p>

            <div class="pm-columns" :class="{ 'pm-columns--single': !bothDirections }">
                <section v-if="dearer.length > 0">
                    <h4 class="pm-heading">Dearer</h4>
                    <ul class="pm-list">
                        <li v-for="row in dearer" :key="row.stock_item_id">
                            <button
                                type="button"
                                class="pm-row"
                                :class="{ 'pm-row--open': selectedId === row.stock_item_id }"
                                :aria-expanded="selectedId === row.stock_item_id"
                                @click="toggle(row.stock_item_id)"
                            >
                                <span class="pm-row__name">{{ row.name }}</span>
                                <span class="pm-row__figures">
                                    <!-- §4.5.3 / A1 — no red/green. Paying more
                                         for oats is not an error state, and
                                         semantic colour is reserved for the
                                         budget card, which has a threshold to
                                         breach. The arrow carries direction. -->
                                    <q-icon :name="ICONS.trending_up" size="16px" />
                                    {{ signed(row.delta_pct) }}
                                </span>
                                <span class="pm-row__detail">{{ priceLine(row) }}</span>
                            </button>
                        </li>
                    </ul>
                </section>

                <section v-if="cheaper.length > 0">
                    <h4 class="pm-heading">Cheaper</h4>
                    <ul class="pm-list">
                        <li v-for="row in cheaper" :key="row.stock_item_id">
                            <button
                                type="button"
                                class="pm-row"
                                :class="{ 'pm-row--open': selectedId === row.stock_item_id }"
                                :aria-expanded="selectedId === row.stock_item_id"
                                @click="toggle(row.stock_item_id)"
                            >
                                <span class="pm-row__name">{{ row.name }}</span>
                                <span class="pm-row__figures">
                                    <q-icon :name="ICONS.trending_down" size="16px" />
                                    {{ signed(row.delta_pct) }}
                                </span>
                                <span class="pm-row__detail">{{ priceLine(row) }}</span>
                            </button>
                        </li>
                    </ul>
                </section>
            </div>

            <!-- The trend half of the job (FU-703 D2: triage *and* trend). The
                 list says which items moved; the chart says how they got there,
                 with the item's usual price drawn in and any linked store offers
                 behind it as context. -->
            <div v-if="selectedId" ref="chartHostRef" class="pm-chart">
                <div v-if="chartLoading" class="pm-chart__loading">
                    <AppSpinner size="28px" />
                </div>
                <PriceHistoryChart
                    v-else
                    :series="chartSeries"
                    :width="chartWidth"
                    :height="220"
                    legend
                    context-label="Store offers"
                    empty-line="No priced history for this one yet."
                />
                <a class="pm-chart__link" :href="`#/stock/${selectedId}`">
                    Open {{ selectedName }}
                </a>
            </div>

        </template>

        <!-- B9 — an empty state that names the one action that fills it, and
             does not send you to a feature you may not have. Logging a shelf
             price and finishing a priced list both feed this; products don't
             come into it. -->
        <CardEmpty v-else :icon="ICONS.price_check">
            {{ emptyLine }}
        </CardEmpty>
    </DashboardCard>
</template>

<script lang="ts" setup>
    /**
     * "Which of my own items got more expensive?" — Reports chunk 4.
     *
     * `REPORTS_PAGE_REVIEW.md` §5 called this **the largest missing widget** on
     * the page: Price trends charts *products*, a push-your-own-data niche most
     * installs never populate, while every household that logs a shelf price or
     * finishes a priced list accumulates `StockItemPriceObservation` rows — and
     * those had **no trend surface anywhere in the app**. FU-703's decision D3
     * puts the trend job here, and D2 says the job is both halves: *triage*
     * (what moved) and *trend* (how). So the card is a ranked list that opens
     * into a chart.
     *
     * Money-gated, **not** products-gated, deliberately: this is precisely the
     * price report that has to survive an install with an empty catalogue.
     *
     * Everything numeric is server-derived — per-unit prices, the deltas, the
     * ranking and the coverage counts (R-003/R-041). This file formats.
     */
    import { createFrameResizeObserver, type FrameResizeObserver } from 'src/composables/frameResizeObserver';
    import { computed, onBeforeUnmount, ref, watch } from 'vue';
    import { ICONS } from 'src/style/icons';
    import { rangeWindowWords } from 'src/helpers/reportRangeWords';
    import AppSkeleton from 'src/components/AppSkeleton.vue';
    import AppSpinner from 'src/components/AppSpinner.vue';
    import CardEmpty from 'src/components/CardEmpty.vue';
    import CardLoadError from 'src/components/dashboard/CardLoadError.vue';
    import DashboardCard from 'src/components/dashboard/DashboardCard.vue';
    import PriceHistoryChart from 'src/components/PriceHistoryChart.vue';
    import { stockItemHistoryToChart } from 'src/composables/usePriceChartSeries';
    import { formatMoney, formatPercent, formatUnitPrice } from 'src/composables/useMoney';
    import StockItemApiService from 'src/services/api/stockItemApiService';
    import type { StockItemPriceHistory } from 'src/services/api/priceHistoryApiService';
    import type {
        ItemPriceMoverRow,
        ItemPriceMoversResponse,
        ReportRange,
    } from 'src/services/api/reportsApiService';

    const props = withDefaults(defineProps<{
        range: ReportRange;
        movers: ItemPriceMoversResponse | null;
        failed?: boolean;
        loading?: boolean;
    }>(), { failed: false, loading: false });

    const emit = defineEmits<{ (e: 'retry'): void }>();

    const stockItemApi = new StockItemApiService();


    const rows = computed(() => props.movers?.rows ?? []);
    const hasRows = computed(() => rows.value.length > 0);
    const dearer = computed(() => rows.value.filter((r) => r.delta > 0));
    const cheaper = computed(() => rows.value.filter((r) => r.delta < 0));
    /** Two columns only when there is something in both. A single list in a
     *  half-width column strands the other half — the within-card version of
     *  D-011's dead air, and visible the moment the card went full width. */
    const bothDirections = computed(
        () => dearer.value.length > 0 && cheaper.value.length > 0,
    );

    const headline = computed(() => {
        const moved = props.movers?.items_with_movement ?? 0;
        return `${moved} of your items changed price `
            + `${rangeWindowWords(props.range, 'since you started logging prices')}.`;
    });

    const emptyLine = computed(() => {
        const single = props.movers?.items_with_one_observation ?? 0;
        if (single > 0) {
            // The honest version of "nothing here": there IS data, it just
            // can't answer this question yet. Saying "log a price" when you
            // already logged one reads as if the app lost it.
            return `${single} of your items ${single === 1 ? 'has' : 'have'} a `
                + 'logged price, but none has two in this range yet.';
        }
        return 'Log what you paid for a couple of items to see what\'s drifting.';
    });

    function signed(pct: number): string {
        return formatPercent(pct, { signed: true });
    }
    function priceLine(row: ItemPriceMoverRow): string {
        return `${formatMoney(row.first_price)} → ${formatUnitPrice(row.last_price, row.unit)}`;
    }

    // ── Drill-in chart ──────────────────────────────────────────────────
    const selectedId = ref<string | null>(null);
    const selectedName = computed(
        () => rows.value.find((r) => r.stock_item_id === selectedId.value)?.name ?? 'item',
    );
    const history = ref<StockItemPriceHistory | null>(null);
    const chartLoading = ref(false);
    const chartSeries = computed(() => stockItemHistoryToChart(history.value));

    // Request token: only the newest drill-in may write the chart (a slower
    // earlier row's history used to land over the newer one).
    let historySeq = 0;
    function closeChart(): void {
        historySeq++;
        selectedId.value = null;
        history.value = null;
        chartLoading.value = false;
    }

    async function toggle(id: string): Promise<void> {
        if (selectedId.value === id) {
            closeChart();
            return;
        }
        const req = ++historySeq;
        selectedId.value = id;
        history.value = null;
        chartLoading.value = true;
        try {
            const result = await stockItemApi.getPriceHistoryAsync(id);
            if (req === historySeq && selectedId.value === id) history.value = result;
        } catch (err) {
            // The row itself is still true — only the chart is missing — so this
            // does not put the whole card in its error state. The chart's own
            // empty line says there is nothing to draw.
            console.warn('item price history failed to load', err);
        } finally {
            if (req === historySeq) chartLoading.value = false;
        }
    }

    // Changing the range re-answers the question, so a chart opened against the
    // old answer must not linger under the new one.
    watch(() => props.range, closeChart);

    // The SVG chart is sized in px, so the card measures its own content box —
    // the same pattern `/price-history`, the bottom sheet and Price trends use.
    const chartHostRef = ref<HTMLElement | null>(null);
    const chartWidth = ref(560);
    let observer: FrameResizeObserver | null = null;

    function measure(): void {
        const el = chartHostRef.value;
        if (!el) return;
        const next = Math.max(260, Math.floor(el.clientWidth));
        if (next !== chartWidth.value) chartWidth.value = next;
    }
    watch(chartHostRef, (el) => {
        observer?.disconnect();
        observer = null;
        if (!el || typeof ResizeObserver === 'undefined') return;
        measure();
        observer = createFrameResizeObserver(measure);
        observer.observe(el);
    });
    onBeforeUnmount(() => {
        observer?.disconnect();
        observer = null;
    });
</script>

<style scoped lang="scss">
    .pm-skeleton {
        display: flex;
        flex-direction: column;
        gap: var(--space-3);
    }
    .pm-skeleton__col {
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
    }
    .pm-headline {
        margin: 0;
        font-size: var(--font-size-md);
        line-height: 1.4;
    }
    .pm-columns {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: var(--space-4);
        margin-top: var(--space-4);
    }
    .pm-columns--single { grid-template-columns: 1fr; }
    @media (max-width: 599px) {
        .pm-columns { grid-template-columns: 1fr; }
    }
    .pm-heading {
        margin: 0 0 var(--space-2);
        font-size: var(--font-size-sm);
        font-weight: 600;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .pm-list {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: var(--space-1);
    }
    /* A real `<button>`, not a div with a click: the row opens a chart, so it
       is an operable control and has to be focusable and keyboard-operable
       (A6). The page's old report rows were `<a>` with no `href` — focusable
       by nothing, announced as nothing (§4.9). */
    .pm-row {
        width: 100%;
        min-height: 44px;           /* D-004 tap target */
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 0 var(--space-3);
        align-items: center;
        padding: var(--space-2) var(--space-3);
        background: var(--surface-sunken);
        border: 1px solid transparent;
        border-radius: var(--radius-md);
        color: var(--text-primary);
        font: inherit;
        text-align: left;
        cursor: pointer;
    }
    .pm-row:hover { background: var(--overlay-hover); }
    .pm-row:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    .pm-row--open { border-color: var(--border-strong); }
    .pm-row__name {
        font-weight: 500;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .pm-row__figures {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        font-variant-numeric: tabular-nums;
    }
    .pm-row__detail {
        grid-column: 1 / -1;
        color: var(--text-secondary);
        font-size: var(--font-size-sm);
        font-variant-numeric: tabular-nums;
    }
    .pm-chart {
        margin-top: var(--space-4);
        overflow-x: auto;
    }
    .pm-chart__loading {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: var(--space-6);
    }
    .pm-chart__link {
        display: inline-block;
        margin-top: var(--space-2);
        color: var(--brand-primary);
        font-size: var(--font-size-sm);
    }
    /* A6 — the row buttons already carry a ring; this link did not. */
    .pm-chart__link:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
        border-radius: var(--radius-sm);
    }
</style>
