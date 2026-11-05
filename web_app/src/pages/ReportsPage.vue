<template>
    <!-- FU-609 / R-036 — root on <q-page> for the layout height contract
         (document-scroll page; no :style-fn). -->
    <q-page class="reports-page">
        <header class="reports-header">
            <div class="reports-title-block">
                <!-- §4.10.1 — the page opens with the answer, not the caveat.
                     The "estimates pulled from…" disclaimer that used to sit
                     here is now an info icon beside the range control. The
                     "Reports" <h1> was dropped (owner, 2026-09-04): the nav
                     already says where you are. -->
                <ReportsLede
                    v-if="moneyEnabled"
                    :range="range"
                    :store-spend="storeSpend"
                    :spendYoY="spendYoY"
                />
            </div>
            <!-- The dates sit on their own line under the picker, in one fixed
                 format on every range (owner, 2026-09-27). Beside it they made
                 the page scroll sideways on a phone, and on "All time", which
                 had no dates, the picker grew into the gap they left. -->
            <div class="reports-range">
                <div class="reports-range__row">
                    <BaseSegmented
                        aria-label="Date range"
                        v-model="range"
                        :options="RANGE_OPTIONS"
                        dense
                        @update:model-value="loadAll"
                    />
                    <q-icon :name="ICONS.info" size="18px" class="reports-caveat">
                        <BaseTooltip>
                            Built from your archived shopping lists and stock history.
                        </BaseTooltip>
                    </q-icon>
                </div>
                <span class="reports-window">{{ windowLabel }}</span>
            </div>
            <CardsMenu
                :cards="menuCards"
                :is-visible="isCardVisible"
                :can-move="canMove"
                mime="application/x-dora-report-card"
                @move="moveCard"
                @toggle="toggleCard"
                @drop="dropCardOn"
            />
        </header>

        <!-- Cards follow the user's layout (FU-832): which show and in what
             order, from `user.reports_layout`, with the feature gates read off
             `helpers/reportCards` rather than declared here. Spend and Price
             changes are full width by design (two lists side by side and a
             chart under them, D-011); the half-width pair widens when one of
             them is hidden. -->
        <div class="row q-col-gutter-lg reports-cards">
            <div
                v-if="cardRendered('spend')"
                :class="cardCol('spend')"
                :style="{ order: cardCssOrder('spend') }"
            >
                <SpendCard
                    :range="range"
                    :store-spend="storeSpend"
                    :spend-by-category="spendByCategory"
                    :spendYoY="spendYoY"
                    :savings="savings"
                    :colour-for="colourFor"
                    :failed="spendFailed"
                    :loading="spendLoading"
                    @retry="loadSpend"
                />
            </div>

            <div
                v-if="cardRendered('waste')"
                :class="cardCol('waste')"
                :style="{ order: cardCssOrder('waste') }"
            >
                <WasteCard
                    :waste="waste"
                    :waste-failed="slotFailed('waste')"
                    :waste-loading="loading.waste"
                    @retry="loadWaste"
                />
            </div>

            <div
                v-if="cardRendered('kitchen_memory')"
                :class="cardCol('kitchen_memory')"
                :style="{ order: cardCssOrder('kitchen_memory') }"
            >
                <KitchenMemoryCard
                    :range="range"
                    :meals-cooked="mealsCooked"
                    :most-bought="mostBought"
                    :cooks-failed="slotFailed('mealsCooked')"
                    :bought-failed="slotFailed('mostBought')"
                    :cooks-loading="loading.mealsCooked"
                    :bought-loading="loading.mostBought"
                    @retry-cooks="loadMealsCooked"
                    @retry-bought="loadMostBought"
                />
            </div>

            <!-- Chunk 4 / FU-703 D3 — the everyday-user price report, built
                 from your own logged prices. -->
            <div
                v-if="cardRendered('price_changes')"
                :class="cardCol('price_changes')"
                :style="{ order: cardCssOrder('price_changes') }"
            >
                <ItemPriceMoversCard
                    :range="range"
                    :movers="itemMovers"
                    :failed="slotFailed('itemMovers')"
                    :loading="loading.itemMovers"
                    @retry="loadItemMovers"
                />
            </div>

            <div v-if="visibleCardCount === 0" class="col-12 dora-text-muted">
                Every report is hidden. Turn them back on from Cards.
            </div>
        </div>
    </q-page>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    /**
     * `/reports` — four questions, one card each.
     *
     * ## What this page is now
     *
     * `REPORTS_PAGE_REVIEW.md` §5: eleven widgets answered four questions, and
     * three of them were the same query sliced three ways. The card set is now
     * question-led: where did my money go (Spend), what do I throw out (Waste),
     * what do we actually eat (Kitchen memory), what am I paying more for
     * (Price changes), plus a lede sentence that gives the answer first.
     *
     * **Cut 2026-09-27:** Price trends (the product chart; better read on My
     * Products and the stock item page) and the run-outs half of Waste.
     *
     * **Added in chunk 4:** Price changes, the report §5 called the largest
     * missing widget on the page — the everyday user's own
     * `StockItemPriceObservation` history had no trend surface anywhere in the
     * app, while Price trends charted a product catalogue most installs never
     * populate (FU-703 D3).
     *
     * **Cut in chunk 3:** stock value over time. Its formula was a 0–5 level
     * *ordinal* multiplied by a price, which is not a dollar figure at all, and
     * it systematically undercounted because every unpriced item contributed
     * zero (§3.3). The endpoint survives for the dashboard's opt-in
     * `pantry_value` card; only the card here is gone.
     *
     * ## What this file owns
     *
     * Data and gates, not presentation. Every card body lives in
     * `components/reports/` (R-001) and the shell is the shared `DashboardCard`,
     * so the ~60-line byte-identical fork of it that used to live here — and had
     * already drifted, losing the hover, the reduced-motion guard and the
     * router-link variant — is gone (FU-814 item 1).
     */
    import { computed, onMounted, ref, watch } from 'vue';
    import { storeToRefs } from 'pinia';
    import CardsMenu from 'src/components/cards/CardsMenu.vue';
    import { useCardLayout } from 'src/composables/useCardLayout';
    import { REPORT_CARD_DEFS, type ReportCardId } from 'src/helpers/reportCards';
    import { useAuthStore } from 'src/stores/authStore';
    import { ICONS } from 'src/style/icons';
    import BaseSegmented from 'src/components/BaseSegmented.vue';
    import ItemPriceMoversCard from 'src/components/reports/ItemPriceMoversCard.vue';
    import KitchenMemoryCard from 'src/components/reports/KitchenMemoryCard.vue';
    import ReportsLede from 'src/components/reports/ReportsLede.vue';
    import SpendCard from 'src/components/reports/SpendCard.vue';
    import WasteCard from 'src/components/reports/WasteCard.vue';
    import { categoricalColour, categoricalColours } from 'src/composables/useThemePalette';
    import { useSlotLoader } from 'src/composables/useSlotLoader';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { formatDate } from 'src/composables/useDateFormat';
    import ReportsApiService, {
        type StoreSpendResponse,
        type MostBoughtResponse,
        type ItemPriceMoversResponse,
        type RangeWindow,
        type ReportRange,
        type SavingsCapturedResponse,
        type MealsCookedResponse,
        type SpendByCategoryResponse,
        type SpendYoYResponse,
        type YoYReportRange,
    } from 'src/services/api/reportsApiService';
    import WasteApiService, { type WasteInsights } from 'src/services/api/wasteApiService';

    const reportsApi = new ReportsApiService();
    const wasteApi = new WasteApiService();

    const RANGE_OPTIONS: { label: string; value: ReportRange }[] = [
        { label: '30 days', value: '30d' },
        { label: '90 days', value: '90d' },
        { label: '1 year', value: '1y' },
        // multi-year windows unlock the culinary-memory questions ("what did we
        // cook in the last two years", "how has dairy trended over 5 years").
        { label: '2 years', value: '2y' },
        { label: '5 years', value: '5y' },
        { label: 'All time', value: 'all' },
    ];

    const range = ref<ReportRange>('30d');

    // ── Feature gates (FU-816) ───────────────────────────────────────────
    // This page imported no feature flag at all, so an install that had turned
    // money off still got spend by store, savings, spend by category,
    // year-over-year, price trends and two dollar-formatted chart axes. The
    // endpoints refuse with 403 now too (R-058); these gates stop us asking.
    //
    // The nav entry stays unconditional on purpose: Waste & run-outs and Kitchen
    // memory are both count-based and survive a money-off install, so hiding the
    // page would cost two working reports to gate two.
    const { moneyEnabled } = useMoneyEnabled();
    const { products: productsEnabled } = useFeatureFlags();

    // ── Card layout (FU-832) ─────────────────────────────────────────────
    const authStore = useAuthStore();
    const { currentUser } = storeToRefs(authStore);
    const {
        applyStored: applyLayoutFromUser, cardRendered, isCardVisible, toggleCard,
        visibleCardCount, cardCol, cardCssOrder, canMove, moveCard, dropCardOn, menuCards,
    } = useCardLayout({
        defs: REPORT_CARD_DEFS,
        stored: () => currentUser.value?.reports_layout ?? null,
        persist: (layout) => {
            void authStore.updateMeAsync({ reports_layout: JSON.stringify(layout) });
        },
        moneyEnabled: () => moneyEnabled.value,
        productsEnabled: () => productsEnabled.value,
    });
    watch(() => currentUser.value?.user_id, applyLayoutFromUser);

    const loading = ref({
        storeSpend: false,
        mostBought: false,
        savings: false,
        mealsCooked: false,
        spendByCategory: false,
        spendYoY: false,
        waste: false,
        itemMovers: false,
        // Page chrome rather than a card, but it goes through the same slot
        // machinery so a failure is recorded rather than swallowed — the label
        // simply doesn't render, which is the honest degradation.
        rangeWindow: false,
    });

    const storeSpend = ref<StoreSpendResponse | null>(null);
    const mostBought = ref<MostBoughtResponse | null>(null);
    const savings = ref<SavingsCapturedResponse | null>(null);
    const mealsCooked = ref<MealsCookedResponse | null>(null);
    const spendByCategory = ref<SpendByCategoryResponse | null>(null);
    // YoY only accepts bounded windows; on "All time" we skip the fetch and the
    // card's compare axis renders its own explanation.
    const spendYoY = ref<SpendYoYResponse | null>(null);
    // Waste is always reported over a day-count window; the API caps at 365, so
    // a 2y/5y/all pick still shows the last year. The card's caption uses the
    // effective window the server returned, so what you read is what's real.
    const waste = ref<WasteInsights | null>(null);
    // Chunk 4 — movement in the prices you logged yourself, per canonical unit.
    const itemMovers = ref<ItemPriceMoversResponse | null>(null);

    // ── Per-card failure (REPORTS_PAGE_REVIEW.md finding 8) ──────────────
    // Every loader used to let a failed fetch fall through to the card's EMPTY
    // state, so a 500 on the waste endpoint rendered "Nothing wasted in this
    // range — nicely played". Same fix, same component and same reasoning as the
    // dashboard's Chunk 4: failure is visible, per-card, and retryable where it
    // happened (`useSlotLoader`).
    type SlotId = keyof typeof loading.value;
    const { slotFailed, loadSlot } = useSlotLoader<SlotId>({
        label: 'reports card',
        loading: loading.value,
    });

    /** The Spend card draws three endpoints, so it fails as one thing: a card
     *  that renders an axis toggle can't tell the reader "two thirds of me are
     *  trustworthy". Any of the three failing puts the whole card in the error
     *  state, and Try again re-fetches all three. */
    /** One flag for the whole Spend card: it is one question with an axis
     *  control, so it cannot say "two thirds of me have arrived". */
    const spendLoading = computed(
        () => loading.value.storeSpend
            || loading.value.spendByCategory
            || loading.value.spendYoY
            || loading.value.savings,
    );

    const spendFailed = computed(
        () => slotFailed('storeSpend')
            || slotFailed('spendByCategory')
            || slotFailed('spendYoY'),
    );

    /** Categorical colour for a bucket with no colour of its own — a stock
     *  group, in practice. Deterministic so a group keeps its hue between
     *  renders.
     *
     *  This used to colour **stores** as well, hashing the store name into the
     *  chart ramp, so one store was its logo green on the shopping list and
     *  whatever the hash landed on here (FU-814). Stores go through
     *  `storeColour` in the card. Do not put a store back in here. */
    function colourFor(key: string): string {
        return groupColours.value.get(key) ?? categoricalColour(key);
    }
    /** FU-976 — assigned over the whole set of groups the chart shows, so two
     *  groups never share a bar colour (a bare per-key hash put "Pantry
     *  staples" and "Fruit & Veg" on the same hue). */
    const groupColours = computed(() =>
        categoricalColours((spendByCategory.value?.rows ?? []).map((r) => r.category)),
    );

    // ── Loaders ──────────────────────────────────────────────────────────
    // A gated-off card must not fetch: the endpoint would 403 (R-058) and the
    // card would render a load failure for a report the install deliberately
    // does not have.
    async function loadStoreSpend() {
        if (!cardRendered('spend')) { storeSpend.value = null; return; }
        const r = range.value;
        await loadSlot('storeSpend', async () => {
            const data = await reportsApi.getSpendByStoreAsync(r);
            if (r === range.value) storeSpend.value = data;
        });
    }
    async function loadSpendByCategory() {
        if (!cardRendered('spend')) { spendByCategory.value = null; return; }
        const r = range.value;
        await loadSlot('spendByCategory', async () => {
            const data = await reportsApi.getSpendByCategoryAsync(r);
            if (r === range.value) spendByCategory.value = data;
        });
    }
    async function loadSpendYoY() {
        if (!cardRendered('spend')) { spendYoY.value = null; return; }
        // YoY needs a bounded window to compare against the same-length prior
        // window. Blank it on "All time" so the card can explain itself.
        if (range.value === 'all') { spendYoY.value = null; return; }
        const r = range.value;
        await loadSlot('spendYoY', async () => {
            const data = await reportsApi.getSpendYearOverYearAsync(
                r as YoYReportRange,
            );
            if (r === range.value) spendYoY.value = data;
        });
    }
    async function loadSavings() {
        if (!cardRendered('spend')) { savings.value = null; return; }
        const r = range.value;
        await loadSlot('savings', async () => {
            const data = await reportsApi.getSavingsCapturedAsync(r);
            if (r === range.value) savings.value = data;
        });
    }
    /** The Spend card's retry — all three axes plus its savings support line. */
    async function loadSpend() {
        await Promise.all([
            loadStoreSpend(), loadSpendByCategory(), loadSpendYoY(), loadSavings(),
        ]);
    }

    async function loadMostBought() {
        if (!cardRendered('kitchen_memory')) return;
        const r = range.value;
        await loadSlot('mostBought', async () => {
            const data = await reportsApi.getMostBoughtAsync(r);
            if (r === range.value) mostBought.value = data;
        });
    }
    async function loadMealsCooked() {
        if (!cardRendered('kitchen_memory')) return;
        const r = range.value;
        await loadSlot('mealsCooked', async () => {
            const data = await reportsApi.getMealsCookedAsync(r, 10);
            if (r === range.value) mealsCooked.value = data;
        });
    }

    // FU-845 #2 — the resolved window, from the server. This also deleted a
    // client-side `RANGE_TO_DAYS` table that was a second copy of the server's
    // own range vocabulary, in a second language (R-003), kept only because the
    // waste endpoint takes a day count rather than a range token.
    const rangeWindow = ref<RangeWindow | null>(null);
    async function loadRangeWindow() {
        const r = range.value;
        await loadSlot('rangeWindow', async () => {
            const data = await reportsApi.getRangeWindowAsync(r);
            if (r === range.value) rangeWindow.value = data;
        });
    }
    /** The dates the range covers, always in full ("3 Aug 2026 – 2 Sep
     *  2026"), so the label is the same shape on every range and the header
     *  doesn't move when you switch. "All time" starts at the household's
     *  earliest record, from the server. A non-breaking space keeps the line
     *  from reflowing while the window loads. */
    const windowLabel = computed(() => {
        const w = rangeWindow.value;
        if (!w || !w.start) return '\u00a0';
        // Install locale via the formatting authority (D-006), not the
        // browser's (finalisation 12-R7 / 20-R6).
        const opts = { day: 'numeric', month: 'short', year: 'numeric' } as const;
        return `${formatDate(w.start, opts)} – ${formatDate(w.end, opts)}`;
    });

    async function loadWaste() {
        // `days` is null for "all time"; the waste report clamps to 365 itself
        // and reports the window it actually used, so a wide number is safe and
        // the card renders whatever came back.
        if (!cardRendered('waste')) return;
        const r = range.value;
        // The window must be THIS range's: if its load failed (or is from the
        // range just left), fetch it again rather than read another range's
        // day count.
        if (rangeWindow.value?.range !== r) await loadRangeWindow();
        await loadSlot('waste', async () => {
            const w = rangeWindow.value;
            if (w?.range !== r) {
                if (r !== range.value) return; // superseded — the new range loads its own
                throw new Error('No date window for this range');
            }
            const data = await wasteApi.getInsightsAsync(w.days ?? 3650);
            if (r === range.value) waste.value = data;
        });
    }

    async function loadItemMovers() {
        if (!cardRendered('price_changes')) { itemMovers.value = null; return; }
        const r = range.value;
        await loadSlot('itemMovers', async () => {
            const data = await reportsApi.getItemPriceMoversAsync(r, 8);
            if (r === range.value) itemMovers.value = data;
        });
    }

    // No page-level error banner: each card records its own failure, so the
    // reader can see exactly which parts of the page to trust. A banner over the
    // whole grid said "something here is wrong" without saying what, while the
    // failed card underneath still read as empty.
    // Each range switch is a new generation; a superseded one stops before
    // starting its card fetches (each loader also drops a response for a
    // range the reader has since left).
    let loadGeneration = 0;
    async function loadAll() {
        const gen = ++loadGeneration;
        // The window first: `loadWaste` needs its `days`, and it is the one
        // fetch the rest depend on rather than merely sit beside.
        await loadRangeWindow();
        if (gen !== loadGeneration) return;
        await Promise.all([
            loadStoreSpend(),
            loadSpendByCategory(),
            loadSpendYoY(),
            loadSavings(),
            loadMostBought(),
            loadMealsCooked(),
            loadWaste(),
            loadItemMovers(),
        ]);
    }

    // A card that starts rendering fetches then: the user turned it on from
    // Cards, or its gate opened. FU-586's failure mode is the second case: the
    // gates read the once-per-document `/api/health` probe, which may not have
    // resolved when the page mounted, so a gated loader early-returned and the
    // card showed its empty state as if the household had never shopped. On a
    // warm navigation the gate is already open at mount, `loadAll` fetches
    // normally, and these never fire.
    const CARD_LOADERS: Record<ReportCardId, () => Promise<unknown>> = {
        spend: () => Promise.all([loadStoreSpend(), loadSpendByCategory(), loadSpendYoY(), loadSavings()]),
        waste: loadWaste,
        kitchen_memory: () => Promise.all([loadMostBought(), loadMealsCooked()]),
        price_changes: loadItemMovers,
    };
    for (const def of REPORT_CARD_DEFS) {
        watch(() => cardRendered(def.id), (on) => {
            if (on) void CARD_LOADERS[def.id]();
        });
    }

    onMounted(() => {
        void loadAll();
    });
</script>

<style scoped lang="scss">
    .reports-page {
        padding: var(--space-6) var(--space-6) var(--space-12);
        background: var(--surface-page);
        color: var(--text-primary);
        min-height: 100%;
    }
    .reports-header {
        display: flex;
        align-items: flex-start;
        gap: var(--space-4);
        flex-wrap: wrap;
        margin-bottom: var(--space-6);
    }
    .reports-title-block { flex: 1; min-width: 280px; }
    .reports-range {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: var(--space-1);
        max-width: 100%;
    }
    .reports-range__row {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        max-width: 100%;
    }
    .reports-caveat { color: var(--text-secondary); }
    .reports-window {
        color: var(--text-secondary);
        font-size: var(--font-size-sm);
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
    }
    /* A8's vocabulary: phone <600, tablet 600–1023, desktop ≥1024. The shared
       half-width class goes two-up from 600px, which on a tablet put two 470px
       columns around 280px charts (§4.8), so Reports stays one column until
       desktop. */
    @media (max-width: 1023px) {
        .reports-cards > [class*='col-sm-6'] {
            width: 100%;
        }
    }
</style>
