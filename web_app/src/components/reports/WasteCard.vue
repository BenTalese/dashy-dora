<template>
    <DashboardCard :icon="ICONS.wasted" title="Waste">
        <CardLoadError
            v-if="wasteFailed"
            line="I couldn't load your wastage."
            @retry="emit('retry')"
        />
        <!-- B10 — shaped like the content below it: a figure, the fixed
             five-up reason grid, three rows. Never the empty state, which
             is what this rendered for the whole flight of the request. -->
        <div v-else-if="wasteLoading" class="wr-skeleton">
            <AppSkeleton type="line" width="40%" height="1.6em" />
            <div class="wr-reasons">
                <AppSkeleton
                    v-for="n in 5"
                    :key="n"
                    type="rect"
                    height="64px"
                    radius="var(--radius-md)"
                />
            </div>
            <AppSkeleton
                v-for="n in 3"
                :key="`row-${n}`"
                type="rect"
                height="44px"
                radius="var(--radius-md)"
            />
        </div>
        <template v-else-if="waste">
            <div class="wr-summary">
                <span class="wr-summary__figure">{{ waste.total_events }}</span>
                <span class="wr-summary__caption">
                    item{{ waste.total_events === 1 ? '' : 's' }} thrown out
                    in the last {{ waste.window_days }} day{{ waste.window_days === 1 ? '' : 's' }}
                </span>
            </div>

            <!-- A fixed 5-up grid where zero-count tiles still render, dimmed,
                 so the shape is stable. Each tile is also a filter on the
                 list below (owner, 2026-09-27); tapping the active one
                 clears it. A zero tile has nothing to filter to. -->
            <div class="wr-reasons" role="group" aria-label="Filter by reason">
                <button
                    v-for="tile in reasonTiles"
                    :key="tile.reason"
                    type="button"
                    class="wr-reason"
                    :class="{
                        'wr-reason--zero': tile.count === 0,
                        'wr-reason--active': selectedReason === tile.reason,
                    }"
                    :disabled="tile.count === 0"
                    :aria-pressed="selectedReason === tile.reason"
                    @click="toggleReason(tile.reason)"
                >
                    <q-icon :name="tile.icon" size="20px" class="wr-reason__icon" />
                    <span class="wr-reason__count">{{ tile.count }}</span>
                    <span class="wr-reason__label">{{ tile.label }}</span>
                </button>
            </div>

            <ul v-if="wastedShown.length > 0" class="wr-list">
                <li
                    v-for="row in wastedShown"
                    :key="row.stock_item_id ?? row.stock_item_name"
                >
                    <component
                        :is="row.stock_item_id ? 'a' : 'span'"
                        class="wr-list__name"
                        :href="row.stock_item_id ? `#/stock/${row.stock_item_id}` : undefined"
                    >{{ row.stock_item_name }}</component>
                    <span class="wr-list__count">×{{ row.event_count }}</span>
                </li>
            </ul>
            <!-- §3.4 — `most_wasted` returns up to 25 rows and the list had
                 no cap, so at ~37px a row this card could reach ~1200px and
                 drag its grid partner to the same height (D-011). Capped,
                 with the remainder counted rather than silently dropped. -->
            <div v-if="hiddenWastedCount > 0" class="wr-more">
                + {{ hiddenWastedCount }} more, not shown
            </div>
            <CardEmpty v-if="waste.most_wasted.length === 0" :icon="ICONS.wasted">
                Nothing wasted in this range.
            </CardEmpty>
        </template>

    </DashboardCard>
</template>

<script lang="ts" setup>
    /**
     * What you threw out, by reason and by item.
     *
     * The "ran out before you restocked" half went on 2026-09-27 (owner: it
     * looked useless), and with it the run-outs endpoint. "Mark all essential"
     * went earlier (§3.5): an unconfirmed bulk mutation with no undo. Rows link
     * to the item instead.
     */
    import { computed, ref, watch } from 'vue';
    import { ICONS } from 'src/style/icons';
    import { WASTE_REASON_TILES } from 'src/helpers/wasteReasons';
    import AppSkeleton from 'src/components/AppSkeleton.vue';
    import CardEmpty from 'src/components/CardEmpty.vue';
    import CardLoadError from 'src/components/dashboard/CardLoadError.vue';
    import DashboardCard from 'src/components/dashboard/DashboardCard.vue';
    import type { WasteInsights, WasteReason } from 'src/services/api/wasteApiService';

    const props = withDefaults(defineProps<{
        waste: WasteInsights | null;
        wasteFailed?: boolean;
        wasteLoading?: boolean;
    }>(), {
        wasteFailed: false,
        wasteLoading: false,
    });

    const emit = defineEmits<{
        (e: 'retry'): void;
    }>();

    /** View state only: which reason the list is narrowed to. The rows for
     *  each reason are ranked server-side (`most_wasted_by_reason`). */
    const selectedReason = ref<WasteReason | null>(null);
    function toggleReason(reason: WasteReason) {
        selectedReason.value = selectedReason.value === reason ? null : reason;
    }
    // A new range can leave the picked reason at zero; drop it rather than
    // show an empty list under a disabled tile.
    watch(() => props.waste, (w) => {
        if (selectedReason.value && (w?.by_reason[selectedReason.value] ?? 0) === 0) {
            selectedReason.value = null;
        }
    });

    // One reason vocabulary (R-003): this card used to declare its own tiles
    // and name one reason differently from the Mark-as-wasted modal
    // ("Overbought" vs "Bought too much") — finalisation 12-R6.
    const reasonTiles = computed(() =>
        WASTE_REASON_TILES.map((t) => ({
            ...t,
            count: props.waste?.by_reason[t.reason] ?? 0,
        })),
    );

    /** Capped so the card can't drag its grid partner to its height
     *  (§3.4 / D-011). */
    const VISIBLE_ROWS = 6;
    const wastedRows = computed(() => {
        if (!props.waste) return [];
        return selectedReason.value
            ? props.waste.most_wasted_by_reason[selectedReason.value] ?? []
            : props.waste.most_wasted;
    });
    const wastedShown = computed(() => wastedRows.value.slice(0, VISIBLE_ROWS));
    const hiddenWastedCount = computed(
        () => Math.max(0, wastedRows.value.length - VISIBLE_ROWS),
    );
</script>

<style scoped lang="scss">
    .wr-skeleton {
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
    }
    .wr-summary {
        display: flex;
        align-items: baseline;
        gap: var(--space-2);
        margin-bottom: var(--space-3);
    }
    .wr-summary__figure {
        font-size: var(--font-size-3xl);
        font-weight: 700;
        font-variant-numeric: tabular-nums;
    }
    .wr-summary__caption {
        color: var(--text-secondary);
        font-size: var(--font-size-sm);
    }
    .wr-reasons {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: var(--space-2);
        margin-bottom: var(--space-3);
    }
    @media (max-width: 599px) {
        .wr-reasons { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    }
    .wr-reason {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: var(--space-1);
        padding: var(--space-2) var(--space-1);
        background: var(--surface-sunken);
        border-radius: var(--radius-md);
        text-align: center;
        border: 1px solid transparent;
        font: inherit;
        color: inherit;
        cursor: pointer;
        min-height: 44px;
    }
    .wr-reason:hover:not(:disabled) { border-color: var(--border-strong); }
    .wr-reason:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    .wr-reason:disabled { cursor: default; }
    .wr-reason--zero { opacity: 0.55; }
    .wr-reason--active {
        border-color: var(--brand-primary);
        background: var(--surface-component);
    }
    .wr-reason__icon { color: var(--text-secondary); }
    .wr-reason__count {
        font-size: var(--font-size-lg);
        font-weight: 700;
        font-variant-numeric: tabular-nums;
    }
    .wr-reason__label {
        /* D-003 floor. The old tile ran this at 11.5px on a ~95px square, so a
           two-word label ("Didn't like") wrapped inside its own tile. */
        font-size: var(--font-size-xs);
        color: var(--text-secondary);
        line-height: 1.15;
    }
    .wr-list {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: var(--space-1);
    }
    .wr-list li {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: var(--space-3);
        padding: var(--space-2) var(--space-3);
        /* D-004 — every row here is a link to the item, so it is a tap target
           and gets the 44px floor. Measured at 375px it came out 38px on the
           padding alone (the old page's rows were ~37px for the same reason);
           the raw value is the rule's own constant, not an off-scale guess. */
        min-height: 44px;
        background: var(--surface-sunken);
        border-radius: var(--radius-md);
    }
    /* A real <a href> rather than a click handler on a bare element: keyboard
       focusable, middle-clickable, and visible to a screen reader's link list
       (§4.9, A6, R-011). */
    .wr-list__name {
        color: var(--text-primary);
        font-weight: 500;
        text-decoration: none;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    a.wr-list__name:hover { text-decoration: underline; }
    /* A6 — "focus is always visible… this is not optional". Measured on the
       running page: a focused row link computed `outline-style: none`, so
       keyboard users had no indicator at all on any row of this card. The ring
       is the app's own idiom (`--focus-ring`, 2px, offset 2). */
    .wr-list__name:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
        border-radius: var(--radius-sm);
    }
    .wr-list__count {
        color: var(--text-secondary);
        font-size: var(--font-size-sm);
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
    }
    .wr-more {
        margin-top: var(--space-2);
        color: var(--text-secondary);
        font-size: var(--font-size-sm);
    }
</style>
