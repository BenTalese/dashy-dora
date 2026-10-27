<template>
    <DashboardCard :icon="ICONS.restaurant_menu" title="Kitchen memory">
        <CardLoadError
            v-if="cooksFailed && boughtFailed"
            line="I couldn't load your kitchen memory."
            @retry="retryBoth"
        />
        <template v-else>
            <CardLoadError
                v-if="cooksFailed"
                line="I couldn't load your cook history."
                @retry="emit('retry-cooks')"
            />
            <!-- B10 — the headline, the note and the column track, in outline.
                 This card was the worst offender: with no loading state it
                 rendered "Nothing cooked in this range yet." to a household
                 with ten cooks, for as long as the request took. -->
            <div v-else-if="cooksLoading" class="km-skeleton">
                <AppSkeleton type="line" width="70%" height="1.2em" />
                <AppSkeleton type="line" width="45%" />
                <AppSkeleton type="rect" height="72px" radius="var(--radius-sm)" />
                <div class="km-lists">
                    <div class="km-skeleton__col">
                        <AppSkeleton
                            v-for="n in 3"
                            :key="n"
                            type="rect"
                            height="44px"
                            radius="var(--radius-md)"
                        />
                    </div>
                    <div class="km-skeleton__col">
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
            <template v-else>
                <!-- The sellable number, at a sellable size. It used to be the
                     SMALLEST text on the card — "14 cooks · 31 meals-worth" in an
                     11.5px note, below the legibility floor (§3.8, D-003). -->
                <p class="km-headline">{{ headline }}</p>
                <p v-if="repertoireLine" class="km-note">{{ repertoireLine }}</p>

                <!-- Columns, not a smoothed area line. `cook_count` per bucket is
                     0, 1 or 2 for a normal household, and a smoothed curve through
                     integers implies 1.4 cooks happened on Tuesday (§3.8.1,
                     §4.10.5). No chart library involved. -->
                <!-- A6 / §4.9 — a chart needs a text alternative, and this one
                     had none: `role="presentation"` with the per-bucket figures
                     reachable only through a hover tooltip, which is neither
                     keyboard- nor screen-reader-reachable. `role="img"` plus a
                     generated label is the same treatment `PriceHistoryChart`
                     got in chunk 4; the columns themselves stay decorative
                     because the label already carries what they say. -->
                <ul
                    v-if="columns.length > 0"
                    class="km-columns"
                    role="img"
                    :aria-label="timelineLabel"
                >
                    <li v-for="col in columns" :key="col.date" class="km-column">
                        <span
                            class="km-column__bar"
                            :style="{ height: `${col.heightPct}%` }"
                        >
                            <BaseTooltip>
                                {{ col.date }}: {{ col.cookCount }}
                                cook{{ col.cookCount === 1 ? '' : 's' }}
                            </BaseTooltip>
                        </span>
                    </li>
                </ul>
            </template>

            <div
                v-if="!cooksFailed && !cooksLoading && (mealsCooked?.top_recipes.length ?? 0) > 0"
                class="km-lists"
            >
                <section>
                    <h4 class="km-heading">Cooked most</h4>
                    <ul class="km-list">
                        <li
                            v-for="row in mealsCooked!.top_recipes.slice(0, 5)"
                            :key="row.recipe_id ?? row.recipe_name"
                        >
                            <component
                                :is="row.recipe_id ? 'a' : 'span'"
                                class="km-list__name"
                                :href="row.recipe_id ? `#/cookbook/${row.recipe_id}` : undefined"
                            >{{ row.recipe_name }}</component>
                            <span class="km-list__count">×{{ row.cook_count }}</span>
                        </li>
                    </ul>
                </section>
                <section>
                    <h4 class="km-heading">Bought most</h4>
                    <CardLoadError
                        v-if="boughtFailed"
                        line="I couldn't load what you buy most."
                        @retry="emit('retry-bought')"
                    />
                    <div v-else-if="boughtLoading" class="km-skeleton__col">
                        <AppSkeleton
                            v-for="n in 3"
                            :key="n"
                            type="rect"
                            height="44px"
                            radius="var(--radius-md)"
                        />
                    </div>
                    <ul v-else-if="(mostBought?.rows.length ?? 0) > 0" class="km-list">
                        <li v-for="row in mostBought!.rows.slice(0, 5)" :key="row.stock_item_id">
                            <a class="km-list__name" :href="`#/stock/${row.stock_item_id}`">
                                {{ row.name }}
                            </a>
                            <span class="km-list__count">×{{ row.appearances }}</span>
                        </li>
                    </ul>
                    <CardEmpty v-else :icon="ICONS.shopping_cart">
                        No archived lists in this range yet.
                    </CardEmpty>
                </section>
            </div>

            <CardEmpty
                v-else-if="!cooksFailed && !cooksLoading"
                :icon="ICONS.restaurant_menu"
            >
                No cooks logged in this range yet. Finish a recipe in cook mode to
                start building your memory.
            </CardEmpty>
        </template>
    </DashboardCard>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    /**
     * "What do we actually eat?" — cooks, repertoire, and what you keep buying.
     *
     * `REPORTS_PAGE_REVIEW.md` §5 merges meals-cooked with a repertoire count;
     * §3.8 is the argument for the repertoire specifically — *"nothing else in
     * the app can answer that, and it drives people back into the cookbook"*.
     *
     * **Most-bought lands here rather than in Spend**, which the §5 preview left
     * open. Two reasons: it is the same question in the other tense (what you
     * buy is what you eat), and — the deciding one — it is **count-based and
     * therefore ungated**. Folding it into the money card would delete it from a
     * money-off install, leaving that household two cards instead of the four
     * working reports the nav entry is justified by (FU-816).
     */
    import { computed } from 'vue';
    import { ICONS } from 'src/style/icons';
    import { rangeWindowWords } from 'src/helpers/reportRangeWords';
    import AppSkeleton from 'src/components/AppSkeleton.vue';
    import CardEmpty from 'src/components/CardEmpty.vue';
    import CardLoadError from 'src/components/dashboard/CardLoadError.vue';
    import DashboardCard from 'src/components/dashboard/DashboardCard.vue';
    import type {
        MealsCookedResponse,
        MostBoughtResponse,
        ReportRange,
    } from 'src/services/api/reportsApiService';

    const props = withDefaults(defineProps<{
        range: ReportRange;
        mealsCooked: MealsCookedResponse | null;
        mostBought: MostBoughtResponse | null;
        cooksFailed?: boolean;
        boughtFailed?: boolean;
        cooksLoading?: boolean;
        boughtLoading?: boolean;
    }>(), {
        cooksFailed: false,
        boughtFailed: false,
        cooksLoading: false,
        boughtLoading: false,
    });

    const emit = defineEmits<{
        (e: 'retry-cooks'): void;
        (e: 'retry-bought'): void;
    }>();

    function retryBoth() {
        emit('retry-cooks');
        emit('retry-bought');
    }


    const headline = computed(() => {
        const m = props.mealsCooked;
        if (!m || m.cook_count === 0) return 'Nothing cooked in this range yet.';
        const parts = [
            `You cooked ${m.cook_count} time${m.cook_count === 1 ? '' : 's'} `
            + `${rangeWindowWords(props.range)}: ${m.meals_total} meals`,
        ];
        if (m.distinct_recipes > 0) {
            parts.push(
                `, ${m.distinct_recipes} different `
                + `recipe${m.distinct_recipes === 1 ? '' : 's'}`,
            );
        }
        parts.push('.');
        return parts.join('');
    });

    /** The untouched tail. Deliberately not range-scoped — the server measures it
     *  over the last 365 days, so a 30-day view doesn't announce that you've
     *  abandoned almost everything you own. */
    const repertoireLine = computed(() => {
        const m = props.mealsCooked;
        if (!m || m.total_recipes <= 0 || m.uncooked_recipes <= 0) return null;
        return `${m.uncooked_recipes} of your ${m.total_recipes} saved `
            + `recipe${m.total_recipes === 1 ? '' : 's'} `
            + `${m.uncooked_recipes === 1 ? 'hasn\'t' : 'haven\'t'} been cooked in a year.`;
    });

    /** The column track's text alternative. Summarises rather than enumerating:
     *  a 30-day range is 31 buckets, and reading "0 cooks" twenty-two times is
     *  not an alternative to a chart, it is a punishment. */
    const timelineLabel = computed(() => {
        const timeline = props.mealsCooked?.timeline ?? [];
        if (timeline.length === 0) return 'Cooking activity over the range.';
        const active = timeline.filter((p) => p.cook_count > 0);
        const peak = Math.max(...timeline.map((p) => p.cook_count));
        return `Cooking activity across ${timeline.length} periods: `
            + `${active.length} with at least one cook, `
            + `busiest had ${peak} cook${peak === 1 ? '' : 's'}.`;
    });

    const columns = computed(() => {
        const timeline = props.mealsCooked?.timeline ?? [];
        const peak = Math.max(1, ...timeline.map((p) => p.cook_count));
        return timeline.map((p) => ({
            date: p.date,
            cookCount: p.cook_count,
            // A floor so a bucket with one cook is visibly a column rather than
            // a hairline, without misreporting its share of the peak.
            heightPct: p.cook_count === 0 ? 0 : Math.max(8, (p.cook_count / peak) * 100),
        }));
    });
</script>

<style scoped lang="scss">
    .km-headline {
        margin: 0;
        font-size: calc(var(--font-size-md) * 1rem);
        line-height: 1.4;
    }
    .km-note {
        margin: var(--space-1) 0 0;
        color: var(--text-secondary);
        font-size: calc(var(--font-size-sm) * 1rem);
    }
    .km-columns {
        list-style: none;
        margin: var(--space-4) 0 0;
        padding: 0;
        display: flex;
        align-items: flex-end;
        /* A3 carve-out — this is chart geometry, not layout spacing. A 30-day
           range draws 31 columns across the card, so the gap is the hairline
           between bars; at `--space-1` (4px) the gaps would total more width
           than the data. Same reasoning as the token carve-outs inside an SVG
           viewBox: the number isn't spacing, it's part of the drawing. */
        gap: 2px;
        height: 72px;
    }
    .km-column {
        flex: 1 1 0;
        min-width: 2px;
        height: 100%;
        display: flex;
        align-items: flex-end;
    }
    .km-column__bar {
        display: block;
        width: 100%;
        min-height: 2px;
        background: var(--brand-primary);
        border-radius: var(--radius-sm) var(--radius-sm) 0 0;
    }
    .km-skeleton {
        display: flex;
        flex-direction: column;
        gap: var(--space-3);
    }
    .km-skeleton__col {
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
    }
    .km-lists {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: var(--space-4);
        margin-top: var(--space-4);
    }
    @media (max-width: 599px) {
        .km-lists { grid-template-columns: 1fr; }
    }
    .km-heading {
        margin: 0 0 var(--space-2);
        font-size: calc(var(--font-size-sm) * 1rem);
        font-weight: 600;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .km-list {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: var(--space-1);
    }
    .km-list li {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: var(--space-3);
        padding: var(--space-2) var(--space-3);
        /* D-004 tap-target floor — see the sibling note in
           `WasteCard`. Every row is a link. */
        min-height: 44px;
        background: var(--surface-sunken);
        border-radius: var(--radius-md);
    }
    .km-list__name {
        color: var(--text-primary);
        font-weight: 500;
        text-decoration: none;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    a.km-list__name:hover { text-decoration: underline; }
    /* A6 — see the sibling note in `WasteCard`. */
    .km-list__name:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
        border-radius: var(--radius-sm);
    }
    .km-list__count {
        color: var(--text-secondary);
        font-size: calc(var(--font-size-sm) * 1rem);
        font-variant-numeric: tabular-nums;
    }
</style>
