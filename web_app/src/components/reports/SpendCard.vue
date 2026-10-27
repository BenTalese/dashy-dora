<template>
    <DashboardCard :icon="ICONS.donut_large" title="Spend">
        <template #action>
            <BaseSegmented
                v-model="axis"
                :options="AXIS_OPTIONS"
                dense
            />
        </template>

        <CardLoadError
            v-if="failed"
            line="I couldn't load your spend."
            @retry="emit('retry')"
        />

        <!-- B10 — a skeleton shaped like the content, never a blank pane and
             never the empty state. Before this, the card rendered "No completed
             shopping lists in this range" for the whole flight of the request,
             so a household with five stores of spend was told it had none until
             the response landed. Same failure-reads-as-absence the error states
             exist to prevent (D-007), just on the other async edge. -->
        <div v-else-if="loading" class="spend-skeleton">
            <AppSkeleton type="rect" height="8px" radius="var(--radius-sm)" />
            <div v-for="n in 5" :key="n" class="spend-skeleton__row">
                <AppSkeleton type="circle" width="10px" height="10px" />
                <AppSkeleton type="line" :width="`${45 - n * 4}%`" />
                <AppSkeleton type="line" width="56px" />
            </div>
        </div>

        <template v-else-if="axis === 'store'">
            <div v-if="storeSegments.length > 0">
                <ProportionBar :segments="storeSegments" />
                <ul class="spend-legend">
                    <li v-for="row in storeSpend!.rows" :key="row.store_id ?? '__none__'">
                        <span
                            class="spend-legend__dot"
                            :class="{ 'spend-legend__dot--unassigned': row.store_id === null }"
                            :style="{ background: row.store_id === null ? undefined : storeColour(row.store, row.brand_colour) }"
                        />
                        <span class="spend-legend__name">{{ row.store }}</span>
                        <span class="spend-legend__value">{{ formatMoney(row.spend) }}</span>
                        <span class="spend-legend__meta">
                            {{ row.list_count }} list{{ row.list_count === 1 ? '' : 's' }}
                        </span>
                    </li>
                </ul>
            </div>
            <CardEmpty v-else :icon="ICONS.storefront">
                No completed shopping lists in this range.
            </CardEmpty>
        </template>

        <template v-else-if="axis === 'group'">
            <div v-if="groupSegments.length > 0">
                <ProportionBar :segments="groupSegments" />
                <ul class="spend-legend">
                    <li v-for="row in spendByCategory!.rows" :key="row.category">
                        <span
                            class="spend-legend__dot"
                            :style="{ background: colourFor(row.category) }"
                        />
                        <span class="spend-legend__name">{{ row.category }}</span>
                        <span class="spend-legend__value">{{ formatMoney(row.spent) }}</span>
                        <span class="spend-legend__meta">{{ row.share_pct }}%</span>
                    </li>
                </ul>
            </div>
            <CardEmpty v-else :icon="ICONS.category">
                No spend recorded in this range yet. Finish a shopping list with
                prices to see where your money's going.
            </CardEmpty>
        </template>

        <template v-else>
            <CardEmpty v-if="range === 'all'" :icon="ICONS.compare_arrows">
                Pick a bounded range (30d–5y) to compare it against the
                same-length prior window.
            </CardEmpty>
            <div
                v-else-if="spendYoY && (spendYoY.current_total > 0 || spendYoY.previous_total > 0)"
            >
                <ul class="spend-legend spend-legend--compare">
                    <li v-for="row in spendYoY.rows.slice(0, 8)" :key="row.category">
                        <span class="spend-legend__name">{{ row.category }}</span>
                        <!-- A1/§4.5.3: no red/green here. Spending $31 more on
                             dairy is not an error — you may have hosted more
                             dinners. Semantic colour is reserved for the budget
                             card, which has a threshold to breach. The arrow
                             carries the direction. -->
                        <span class="spend-legend__value">
                            <q-icon
                                v-if="row.delta !== 0"
                                :name="row.delta > 0 ? ICONS.trending_up : ICONS.trending_down"
                                size="16px"
                            />
                            <template v-if="row.delta_pct === null">new</template>
                            <template v-else>
                                {{ row.delta_pct > 0 ? '+' : '' }}{{ row.delta_pct }}%
                            </template>
                        </span>
                        <span class="spend-legend__meta">
                            {{ formatMoney(row.current) }} vs {{ formatMoney(row.previous) }}
                        </span>
                    </li>
                </ul>
            </div>
            <CardEmpty v-else :icon="ICONS.compare_arrows">
                Not enough history yet to compare periods. Finish lists over time
                and this fills in.
            </CardEmpty>
        </template>

        <!-- Savings, as a support line rather than a card of its own (§5).
             Suppressed while the card is in its error state: found in the
             browser, where a 404 on spend-by-store left *"1 item had no price
             recorded, so it isn't counted here"* sitting under "I couldn't load
             your spend" — a coverage footnote about numbers that aren't on
             screen, which is the same failure-dressed-as-data the error state
             exists to prevent (D-007).
             R-071: the figure names its baseline. This one is still computed
             against the retailer's shelf price; FU-831 moves the retrospective
             figure to your own usual price and re-words it, which is exactly why
             the label can't be a bare "saved". -->
        <template v-if="!failed && !loading">
            <div v-if="savingsLine" class="spend-support">{{ savingsLine }}</div>
            <div v-if="coverageLine" class="spend-support">{{ coverageLine }}</div>
        </template>
    </DashboardCard>
</template>

<script lang="ts" setup>
    /**
     * "Where did my money go?" — one card, three axes.
     *
     * `REPORTS_PAGE_REVIEW.md` §5: spend-by-store, spend-by-category and
     * year-over-year were three cards built on the same query, the same range
     * and the same shape. The user's question is singular; store / group / vs
     * last period is a **control**, not three answers. Savings joins them as a
     * support line, because "what you kept" is a footnote to "what you spent",
     * not a peer of it (§3.7).
     *
     * The donuts are gone (§4.6): unreadable past three slices, fragile at
     * half-width, and a different language from the one the same household
     * already reads on its shopping list. Composition is a `ProportionBar`,
     * shared with that card.
     */
    import { computed, ref } from 'vue';
    import { ICONS } from 'src/style/icons';
    import AppSkeleton from 'src/components/AppSkeleton.vue';
    import BaseSegmented from 'src/components/BaseSegmented.vue';
    import CardEmpty from 'src/components/CardEmpty.vue';
    import CardLoadError from 'src/components/dashboard/CardLoadError.vue';
    import DashboardCard from 'src/components/dashboard/DashboardCard.vue';
    import ProportionBar from 'src/components/ProportionBar.vue';
    import { formatMoney } from 'src/composables/useMoney';
    import { storeColour } from 'src/style/storeSwatch';
    import type {
        ReportRange,
        SavingsCapturedResponse,
        SpendByCategoryResponse,
        SpendYoYResponse,
        StoreSpendResponse,
    } from 'src/services/api/reportsApiService';

    const props = withDefaults(defineProps<{
        range: ReportRange;
        storeSpend: StoreSpendResponse | null;
        spendByCategory: SpendByCategoryResponse | null;
        spendYoY: SpendYoYResponse | null;
        /** Null when products are off — savings only ever has data if you pick
         *  product offers, so the support line simply doesn't render (B9). */
        savings: SavingsCapturedResponse | null;
        /** Categorical colour for a bucket with no colour of its own. Passed in
         *  rather than re-implemented so the page keeps one hash (R-002). */
        colourFor: (key: string) => string;
        failed?: boolean;
        /** True while any of the three axes (or the savings support line) is in
         *  flight. One flag for the whole card because it is one question: a
         *  card that renders an axis toggle cannot say "two thirds of me have
         *  arrived". */
        loading?: boolean;
    }>(), { failed: false, loading: false });

    const emit = defineEmits<{ (e: 'retry'): void }>();

    type Axis = 'store' | 'group' | 'compare';
    const AXIS_OPTIONS: { label: string; value: Axis }[] = [
        { label: 'By store', value: 'store' },
        { label: 'By group', value: 'group' },
        { label: 'vs last period', value: 'compare' },
    ];
    const axis = ref<Axis>('store');

    const storeSegments = computed(() =>
        (props.storeSpend?.rows ?? []).map((row) => ({
            key: row.store_id ?? '__none__',
            label: `${row.store} · ${formatMoney(row.spend)}`,
            value: row.spend,
            colour: row.store_id === null
                ? undefined
                : storeColour(row.store, row.brand_colour),
            isUnassigned: row.store_id === null,
        })),
    );

    const groupSegments = computed(() =>
        (props.spendByCategory?.rows ?? []).map((row) => ({
            key: row.category,
            label: `${row.category} · ${formatMoney(row.spent)}`,
            value: row.spent,
            colour: props.colourFor(row.category),
        })),
    );

    const savingsLine = computed(() => {
        const savings = props.savings;
        if (!savings || savings.total_spent <= 0 || savings.total_savings <= 0) return null;
        return `${formatMoney(savings.total_savings)} of that was under shelf price.`;
    });

    /** R-041 — the total states what it was built from. */
    const coverageLine = computed(() => {
        const unpriced = props.storeSpend?.unpriced_lines ?? 0;
        if (axis.value !== 'store' || unpriced <= 0) return null;
        return `${unpriced} item${unpriced === 1 ? '' : 's'} had no price recorded, `
            + `so ${unpriced === 1 ? "it isn't" : "they aren't"} counted here.`;
    });
</script>

<style scoped lang="scss">
    .spend-legend {
        list-style: none;
        margin: var(--space-3) 0 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: var(--space-1);
    }
    .spend-legend li {
        display: grid;
        grid-template-columns: 12px minmax(0, 1fr) auto auto;
        gap: var(--space-2);
        align-items: center;
        padding: var(--space-1) 0;
        font-size: var(--font-size-sm);
    }
    /* The compare axis has no swatch — there is no bar above it to key to. */
    .spend-legend--compare li {
        grid-template-columns: minmax(0, 1fr) auto auto;
    }
    .spend-legend__dot {
        width: 10px;
        height: 10px;
        border-radius: var(--radius-pill);
    }
    /* Matches the bar's catch-all treatment: texture, not a hue (D-001). */
    .spend-legend__dot--unassigned {
        background-color: var(--border-strong);
        background-image: repeating-linear-gradient(
            135deg,
            transparent 0 2px,
            var(--surface-component) 2px 3px
        );
    }
    .spend-legend__name {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .spend-legend__value {
        font-weight: 600;
        font-variant-numeric: tabular-nums;
        display: inline-flex;
        align-items: center;
        gap: var(--space-1);
    }
    .spend-legend__meta {
        color: var(--text-secondary);
        font-size: var(--font-size-sm);
        font-variant-numeric: tabular-nums;
    }
    .spend-skeleton {
        display: flex;
        flex-direction: column;
        gap: var(--space-3);
    }
    .spend-skeleton__row {
        display: flex;
        align-items: center;
        gap: var(--space-2);
    }
    .spend-support {
        margin-top: var(--space-3);
        color: var(--text-secondary);
        font-size: var(--font-size-sm);
    }
</style>
