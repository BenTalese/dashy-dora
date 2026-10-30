<template>
    <!--
        FU-227 chunk 6 (C5b) — "Full history" bottom-sheet. Opens from the
        YourPrices widget; embeds the shared PriceHistoryChart scoped to one
        stock item's unioned series (observations ∪ linked-product offers,
        both normalised per-unit server-side). Offers render as subordinate
        "context" (offersAsContext) under the user's own observation line, with
        the baseline reference line drawn in (D2 + F-3).

        R-001 — reuses BaseDialog (position="bottom") as the bottom-sheet
        primitive, the same one QuickAddSheet uses; no hand-rolled q-dialog.
    -->
    <BaseDialog
        :model-value="modelValue"
        :title="`Price history: ${itemName}`"
        closable
        position="bottom"
        card-style="width: 760px; max-width: 96vw"
        @update:model-value="(v) => emit('update:modelValue', v)"
        @cancel="emit('update:modelValue', false)"
    >
        <q-card-section ref="bodyRef">
            <div v-if="loading" class="row justify-center q-pa-lg">
                <AppSpinner size="28px" />
            </div>

            <template v-else-if="hasPoints">
                <!-- The "above usual" chip stays here: it is a verdict about
                     the item, not a key to the chart. The legend itself moved
                     *into* `PriceHistoryChart` (FU-833) — it named the two
                     series and the baseline, which are the chart's own facts,
                     and two other consumers needed the same thing. -->
                <div class="row items-center q-mb-sm">
                    <q-space />
                    <q-chip
                        v-if="history?.above_baseline"
                        dense
                        class="dora-chip--tint-warning"
                        :icon="ICONS.trending_up"
                    >
                        above usual
                    </q-chip>
                </div>

                <PriceHistoryChart
                    :series="chartSeries"
                    :width="chartWidth"
                    :height="300"
                    legend
                    context-label="Store offers"
                    :aria-label="`Price history for ${itemName || history?.name || 'this item'}: your logged prices against store offers.`"
                />
            </template>

            <div v-else class="dora-text-muted text-body2 q-pa-md text-center">
                No price history yet.
            </div>
        </q-card-section>
    </BaseDialog>
</template>

<script lang="ts" setup>
    import { createFrameResizeObserver, type FrameResizeObserver } from 'src/composables/frameResizeObserver';
    import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
    import AppSpinner from 'src/components/AppSpinner.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import PriceHistoryChart from 'src/components/PriceHistoryChart.vue';
    import { stockItemHistoryToChart } from 'src/composables/usePriceChartSeries';
    import { ICONS } from 'src/style/icons';
    import StockItemApiService from 'src/services/api/stockItemApiService';
    import type { StockItemPriceHistory } from 'src/services/api/priceHistoryApiService';

    const props = withDefaults(
        defineProps<{
            modelValue: boolean;
            stockItemId: string;
            itemName?: string;
        }>(),
        { itemName: '' },
    );

    const emit = defineEmits<{
        (e: 'update:modelValue', value: boolean): void;
    }>();

    const stockItemApi = new StockItemApiService();
    const history = ref<StockItemPriceHistory | null>(null);
    const loading = ref(false);

    const hasPoints = computed(() => (history.value?.points.length ?? 0) > 0);

    /** The chart's series. `stockItemHistoryToChart` splits the server's tagged
     *  union — your observations lead, offers become the subordinate dashed
     *  line, the baseline rides along — so this component no longer rebuilds a
     *  product-shaped DTO it never had (FU-833). */
    const chartSeries = computed(() => stockItemHistoryToChart(history.value));

    // ── Responsive chart width (mirrors PriceHistoryPage) ───────────────────
    const bodyRef = ref<{ $el?: HTMLElement } | null>(null);
    const chartWidth = ref(720);
    let resizeObserver: FrameResizeObserver | null = null;

    function measure(): void {
        const el = bodyRef.value?.$el;
        if (!el) return;
        const next = Math.max(280, Math.floor(el.clientWidth) - 32);
        if (next !== chartWidth.value) chartWidth.value = next;
    }

    // R-101 — each open (and each close) bumps this, so a slow response for
    // the item the sheet was showing before can't paint into the one open now.
    let loadSeq = 0;

    async function load(): Promise<void> {
        const req = ++loadSeq;
        loading.value = true;
        try {
            const result = await stockItemApi.getPriceHistoryAsync(props.stockItemId);
            if (req !== loadSeq) return;
            history.value = result;
        } catch {
            if (req !== loadSeq) return;
            history.value = null;
        } finally {
            if (req === loadSeq) loading.value = false;
        }
        await nextTick();
        measure();
        const el = bodyRef.value?.$el;
        if (el && typeof ResizeObserver !== 'undefined' && !resizeObserver) {
            resizeObserver = createFrameResizeObserver(measure);
            resizeObserver.observe(el);
        }
    }

    // Lazy-fetch each time the sheet opens (prices may have changed since the
    // last open; the detail page reloads its own data after a log too).
    watch(
        () => props.modelValue,
        (open) => {
            if (open && props.stockItemId) void load();
            if (!open) {
                loadSeq += 1;
                resizeObserver?.disconnect();
                resizeObserver = null;
            }
        },
    );

    onBeforeUnmount(() => {
        resizeObserver?.disconnect();
        resizeObserver = null;
    });
</script>
