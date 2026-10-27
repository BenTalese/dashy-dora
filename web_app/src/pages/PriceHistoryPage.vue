<template>
    <!-- FU-609 / R-036 — root on <q-page> for the layout height contract
         (document-scroll page; no :style-fn). -->
    <q-page class="q-pa-md row q-col-gutter-md">
        <!-- ── Left rail: picker + selected chips ─────────────────── -->
        <div class="col-12 col-md-3">
            <q-card flat bordered>
                <q-card-section>
                    <div class="text-subtitle1">Pick products</div>
                    <div class="text-caption dora-text-muted">
                        Compare up to 5 products' price history side by side.
                    </div>
                </q-card-section>
                <q-card-section class="q-pt-none">
                    <SearchInput
                        v-model="filter"
                        placeholder="Search saved products"
                        icon-size="16px"
                    />
                </q-card-section>
                <q-card-section class="q-pt-none">
                    <div class="text-caption dora-text-muted-7 q-mb-xs">Selected</div>
                    <div v-if="selectedIds.length === 0" class="text-caption dora-text-muted-5">
                        Pick from the list below.
                    </div>
                    <div v-else>
                        <q-chip
                            v-for="(p, i) in selectedProducts"
                            :key="p.product_id"
                            removable
                            dense
                            :color="seriesColour(i)"
                            text-color="white"
                            @remove="toggleSelect(p.product_id)"
                        >
                            {{ p.name }}
                        </q-chip>
                    </div>
                </q-card-section>
                <q-separator />
                <q-card-section class="q-pt-none" style="max-height: 360px; overflow: auto">
                    <q-list dense>
                        <q-item
                            v-for="p in filteredCandidates"
                            :key="p.product_id"
                            clickable
                            :active="selectedIds.includes(p.product_id)"
                            active-class="active-product-row"
                            @click="toggleSelect(p.product_id)"
                        >
                            <q-item-section avatar>
                                <q-checkbox
                                    :model-value="selectedIds.includes(p.product_id)"
                                    :disable="
                                        !selectedIds.includes(p.product_id)
                                        && selectedIds.length >= 5
                                    "
                                    @update:model-value="toggleSelect(p.product_id)"
                                    @click.stop
                                />
                            </q-item-section>
                            <q-item-section>
                                <q-item-label>{{ p.name }}</q-item-label>
                                <q-item-label v-if="p.store_name" caption>
                                    <StoreLogo :name="p.store_name" :height="16" :width="24" inline />{{ p.store_name }}
                                </q-item-label>
                            </q-item-section>
                        </q-item>
                        <q-item v-if="filteredCandidates.length === 0">
                            <q-item-section class="dora-text-muted text-caption">
                                No products match.
                            </q-item-section>
                        </q-item>
                    </q-list>
                </q-card-section>
            </q-card>
        </div>

        <!-- ── Chart + range + comparison strip ──────────────────── -->
        <div class="col-12 col-md-9">
            <!-- Was a bare `row` with an h5, the range control and a
                 full-label button, which had no answer for a narrow viewport:
                 the three competed on one line and the title lost. PageToolbar
                 is the shared answer to exactly that (its actions cluster
                 wraps below the title, and the title cell can shrink) — the
                 same component the recipe detail page uses. On phones the
                 alerts button drops its label, matching the list pages. -->
            <PageToolbar title="Price history">
                <template #actions>
                    <BaseSegmented
                        v-model="range"
                        :options="rangeOptions"
                        dense
                    />
                    <BaseButton
                        variant="ghost"
                        :icon="ICONS.notifications"
                        :label="compactToolbar ? undefined : 'Manage alerts'"
                        aria-label="Manage alerts"
                        @click="alertsOpen = true"
                    >
                        <BaseTooltip v-if="compactToolbar">Manage alerts</BaseTooltip>
                    </BaseButton>
                </template>
            </PageToolbar>

            <q-card ref="chartCardRef" flat bordered>
                <q-card-section class="q-pa-sm">
                    <!-- FU-833 — the chart takes neutral series now; the
                         product payload is mapped by `productSeriesToChart`,
                         which also owns the "no offers ⇒ show your own prices"
                         fallback this page relies on. -->
                    <PriceHistoryChart
                        :series="chartSeries"
                        :width="chartWidth"
                        :height="320"
                        legend
                        empty-line="Pick one or more products on the left to see their price history."
                    />
                </q-card-section>
            </q-card>

            <!-- Per-product comparison strip -->
            <div class="row q-col-gutter-sm q-mt-sm">
                <div
                    v-for="(s, i) in series"
                    :key="s.product_id"
                    class="col-12 col-sm-6 col-md-4"
                >
                    <q-card flat bordered>
                        <q-card-section>
                            <div class="row items-center q-gutter-sm">
                                <span
                                    class="series-swatch"
                                    :style="{ background: seriesColour(i) }"
                                />
                                <div class="col">
                                    <div class="text-subtitle2">{{ s.name }}</div>
                                    <div class="text-caption dora-text-muted-7">
                                        {{ s.store }}
                                    </div>
                                </div>
                            </div>
                        </q-card-section>
                        <q-card-section v-if="s.current" class="q-pt-none">
                            <div class="text-h6">
                                {{ s.current.unit_price != null ? formatMoney(s.current.unit_price) : '–' }}
                                <!-- PH-5/PH-6 — was a `size="sm"` chip reading
                                     "-12%", which is both the smallest and the
                                     only differently-worded spelling of the
                                     badge in the app. Now the shared chip, at
                                     the default size. -->
                                <DiscountChip class="q-ml-xs" :pct="s.current.deal_pct" />
                            </div>
                            <div v-if="s.all_time_low" class="text-caption dora-text-muted-7">
                                All-time low:
                                <strong>{{ formatMoney(s.all_time_low.unit_price) }}</strong>
                                <span v-if="aboveLowPct(s) !== null">
                                    · currently {{ aboveLowPct(s) }}% above
                                    <InfoTip label="What above the all-time low means">
                                        How far today's shelf price is above the
                                        lowest advertised price Dora has seen
                                        for this product.
                                    </InfoTip>
                                </span>
                            </div>
                            <!-- the user's own usual
                                 price for this product + above-usual signal. A
                                 caption (not on the chart axis) so the per-unit
                                 baseline never clashes with the raw offer scale. -->
                            <div
                                v-if="s.your_prices?.baseline != null"
                                class="text-caption dora-text-muted-7 q-mt-xs"
                            >
                                Your usual:
                                <strong>
                                    {{ formatMoney(s.your_prices.baseline)
                                    }}{{ s.your_prices.baseline_unit ? `/${s.your_prices.baseline_unit}` : '' }}
                                </strong>
                                <InfoTip label="What your usual price means">
                                    "Usually" is the median of prices you've
                                    logged for this item. "Above usual" means
                                    today's shelf price is meaningfully higher
                                    than that median.
                                </InfoTip>
                                <q-chip
                                    v-if="s.your_prices.above_baseline"
                                    dense
                                    size="sm"
                                    color="warning"
                                    text-color="dark"
                                    class="q-ml-xs"
                                    :icon="ICONS.trending_up"
                                >
                                    above usual
                                </q-chip>
                            </div>
                        </q-card-section>
                        <q-card-section v-else class="text-caption dora-text-muted-5">
                            No data yet.
                        </q-card-section>
                        <q-separator />
                        <!-- One watch editor for the whole app (10-R40): the
                             card opens the same dialog My products uses. -->
                        <q-card-section class="q-pt-sm">
                            <BaseButton
                                variant="primary"
                                class="full-width"
                                :icon="ICONS.notifications_active"
                                :label="watchByProduct.has(s.product_id) ? 'Change watch' : 'Watch this price'"
                                :disable="!productById.get(s.product_id)"
                                @click="openWatch(s.product_id)"
                            />
                        </q-card-section>
                    </q-card>
                </div>
            </div>
        </div>

        <!-- ── Alerts modal ──────────────────────────────────────── -->
        <BaseDialog v-model="alertsOpen" title="Price alerts" closable card-style="min-width: 420px">
                <q-card-section v-if="alerts.length === 0" class="dora-text-secondary">
                    No active alerts yet.
                </q-card-section>
                <q-list v-else separator>
                    <q-item v-for="a in alerts" :key="a.price_alert_id">
                        <q-item-section>
                            <q-item-label>{{ a.product_name }}</q-item-label>
                            <q-item-label caption>
                                <StoreLogo :name="a.store_name" :height="16" :width="24" inline />{{ a.store_name }} ·
                                notify below
                                <strong>{{ formatMoney(a.threshold_unit_price) }}</strong>
                            </q-item-label>
                        </q-item-section>
                        <q-item-section side>
                            <div class="row no-wrap q-gutter-xs">
                                <BaseButton
                                    v-if="productById.get(a.product_id)"
                                    variant="ghost"
                                    dense
                                    :icon="ICONS.edit"
                                    label="Change"
                                    @click="openWatch(a.product_id)"
                                />
                                <BaseButton
                                    variant="danger-ghost"
                                    dense
                                    :icon="ICONS.delete"
                                    label="Remove"
                                    @click="onDeleteAlert(a.price_alert_id)"
                                />
                            </div>
                        </q-item-section>
                    </q-item>
                </q-list>
        </BaseDialog>

        <ProductPriceWatchDialog
            v-model="watchOpen"
            :product="watchTarget"
            :watch="watchTarget ? (watchByProduct.get(watchTarget.product_id) ?? null) : null"
            @saved="refreshAlerts"
        />
    </q-page>
</template>

<script lang="ts" setup>
    import { createFrameResizeObserver, type FrameResizeObserver } from 'src/composables/frameResizeObserver';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import InfoTip from 'src/components/help/InfoTip.vue';
    import { ICONS } from 'src/style/icons';
    import SearchInput from 'src/components/SearchInput.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import StoreLogo from 'src/components/StoreLogo.vue';
    import BaseSegmented from 'src/components/BaseSegmented.vue';
    import ProductPriceWatchDialog from 'src/components/products/ProductPriceWatchDialog.vue';
    import PageToolbar from 'src/components/PageToolbar.vue';
    import DiscountChip from 'src/components/chips/DiscountChip.vue';
    import { formatMoney } from 'src/composables/useMoney';
    import { useQuasar } from 'quasar';
    import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
    import { useRoute } from 'vue-router';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import PriceHistoryChart from 'src/components/PriceHistoryChart.vue';
    import { seriesColour } from 'src/composables/useThemePalette';
    import { productSeriesToChart } from 'src/composables/usePriceChartSeries';
    import type { Product } from 'src/models/product';
    import PriceHistoryApiService, {
        type PriceAlert, type PriceHistorySeries, type PriceRange,
    } from 'src/services/api/priceHistoryApiService';
    import { useProductStore } from 'src/stores/productStore';
    import { storeToRefs } from 'pinia';

    const $q = useQuasar();
    const route = useRoute();
    const compactToolbar = computed(() => $q.screen.lt.sm);
    const historyApi = new PriceHistoryApiService();
    // One product store for the app (R-003): My products and this page read
    // the same list, hydrated lazily.
    const productStore = useProductStore();
    const { products: candidates } = storeToRefs(productStore);

    const selectedIds = ref<string[]>([]);
    const filter = ref('');
    const range = ref<PriceRange>('90d');
    const rangeOptions = [
        { label: '30d', value: '30d' },
        { label: '90d', value: '90d' },
        { label: '1y', value: '1y' },
        { label: 'All', value: 'all' },
    ];

    const series = ref<PriceHistorySeries[]>([]);
    /** What the chart draws. Offers lead on this page — it is the *product*
     *  price surface — so `offersAsContext` stays off and the adapter falls back
     *  to the user's own observations only for a product that has no offers at
     *  all (the H2 rule, unchanged; it just no longer lives inside the chart). */
    const chartSeries = computed(() => productSeriesToChart(series.value));
    const alerts = ref<PriceAlert[]>([]);
    const alertsOpen = ref(false);
    const watchByProduct = computed(() => new Map(alerts.value.map((a) => [a.product_id, a])));
    const productById = computed(() => new Map(candidates.value.map((p) => [p.product_id, p])));
    const watchOpen = ref(false);
    const watchTarget = ref<Product | null>(null);
    function openWatch(productId: string): void {
        const product = productById.value.get(productId);
        if (!product) return;
        watchTarget.value = product;
        watchOpen.value = true;
    }

    // chart width tracks the surrounding card so the graph extends to
    // the card edge at every viewport size. Was hard-coded to 720, which
    // left a gap on wide screens and overflowed on narrow ones.
    const chartCardRef = ref<{ $el?: HTMLElement } | null>(null);
    const chartWidth = ref(720);
    let chartResizeObserver: FrameResizeObserver | null = null;

    function measureChart(): void {
        const el = chartCardRef.value?.$el;
        if (!el) return;
        // Account for q-card-section padding (q-pa-sm ≈ 8px each side).
        const next = Math.max(280, Math.floor(el.clientWidth) - 16);
        if (next !== chartWidth.value) chartWidth.value = next;
    }

    const filteredCandidates = computed(() => {
        const needle = filter.value.trim().toLowerCase();
        const all = candidates.value;
        if (!needle) return all;
        return all.filter((p) =>
            p.name.toLowerCase().includes(needle)
            || (p.store_name ?? '').toLowerCase().includes(needle),
        );
    });

    const selectedProducts = computed(() =>
        selectedIds.value
            .map((id) => productById.value.get(id))
            .filter((p): p is Product => Boolean(p)),
    );

    function toggleSelect(productId: string) {
        const idx = selectedIds.value.indexOf(productId);
        if (idx >= 0) {
            // Reassign (not splice/push) so the `watch([selectedIds, …])`
            // below fires: it's a shallow ref watch, and an in-place mutation
            // leaves `.value` identity unchanged, so the series never
            // refetched on interactive picking (only the deep-link preselect,
            // which reassigns, worked). FU-605.
            selectedIds.value = selectedIds.value.filter((id) => id !== productId);
        } else {
            if (selectedIds.value.length >= 5) {
                $q.notify({
                    type: 'warning', 
                    message: 'Up to 5 products at a time.',
                });
                return;
            }
            selectedIds.value = [...selectedIds.value, productId];
        }
    }

    function aboveLowPct(s: PriceHistorySeries): number | null {
        if (!s.current?.unit_price || !s.all_time_low?.unit_price) return null;
        if (s.all_time_low.unit_price === 0) return null;
        const pct = ((s.current.unit_price - s.all_time_low.unit_price) / s.all_time_low.unit_price) * 100;
        return Math.max(0, Math.round(pct));
    }

    async function refreshSeries() {
        if (selectedIds.value.length === 0) { series.value = []; return; }
        try {
            const result = await historyApi.seriesAsync(selectedIds.value, range.value);
            series.value = result.series;
        } catch (err) {
            $q.notify({
                type: 'negative', 
                message: "Couldn't load price history.",
                caption: err instanceof Error ? err.message : String(err),
            });
        }
    }

    async function refreshAlerts() {
        try {
            const result = await historyApi.listAlertsAsync();
            alerts.value = result.items;
        } catch { /* alerts list is non-critical */ }
    }

    async function onDeleteAlert(alertId: string) {
        try {
            await historyApi.deleteAlertAsync(alertId);
            await refreshAlerts();
        } catch (err) {
            $q.notify({
                type: 'negative', 
                message: "Couldn't remove the alert.",
                caption: err instanceof Error ? err.message : String(err),
            });
        }
    }

    watch([selectedIds, range], () => { void refreshSeries(); });

    onMounted(async () => {
        await productStore.getProductsAsync();
        // Deep-link: ?product_id=<id> pre-selects; the watch above fetches.
        const preselect = (route.query.product_id as string | undefined) ?? null;
        if (preselect && productById.value.has(preselect)) {
            selectedIds.value = [preselect];
        }
        void refreshAlerts();
        // Wait one tick so the q-card has mounted before measuring.
        await Promise.resolve();
        measureChart();
        const el = chartCardRef.value?.$el;
        if (el && typeof ResizeObserver !== 'undefined') {
            chartResizeObserver = createFrameResizeObserver(measureChart);
            chartResizeObserver.observe(el);
        }
    });

    onBeforeUnmount(() => {
        chartResizeObserver?.disconnect();
        chartResizeObserver = null;
    });
</script>

<style scoped>
    .series-swatch {
        width: 12px; height: 12px; border-radius: 3px;
        display: inline-block;
    }
    .active-product-row {
        background: var(--brand-primary-soft);
    }
</style>
