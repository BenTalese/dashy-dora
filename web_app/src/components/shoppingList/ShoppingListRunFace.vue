<template>
    <div class="sl-run">
        <!-- Ordering stays available mid-shop — it is the single most useful
             control in a store (walk by aisle, or by the shop you're standing
             in) — but the control itself moved to the overview card at the top
             of the page. This face was rendering its own copy of the plan
             face's bar, identical but for the mode list, which is two places to
             change one view preference. This face still *reads* the mode; it no
             longer offers a second way to set it. -->
        <div
            v-for="section in runSections"
            :key="section.key"
            class="sl-section"
        >
            <!-- The same section header the plan face uses — uppercase title
                 and a count pill, rather than a muted `text-subtitle2` floating
                 above a bordered box. The progress reads `2/5` in the pill's
                 place because mid-shop the count that matters is how far
                 through the aisle you are. -->
            <div v-if="section.label && !section.cleared" class="sl-section__head">
                <q-icon :name="sectionIconFor(effectiveMode)" size="16px" />
                <span class="sl-section__title">{{ section.label }}</span>
                <span class="sl-section__count">
                    {{ section.picked }}/{{ section.total }}
                </span>
            </div>
            <!-- One soft slab, not `q-list bordered separator` inside an
                 already-bordered page (v4 chunk 5). The rows own their own
                 dividers, inset to the content column. -->
            <div v-if="section.remaining.length > 0" class="sl-list">
                <ShoppingListRunRow
                    v-for="line in section.remaining"
                    :key="line.line_id"
                    :line="line"
                    :picked="false"
                    :nested="isNestedChild(line)"
                    :caption="captionFor(line)"
                    @toggle="emit('tick', line)"
                    @capture-price="emit('capture-price', line)"
                />
            </div>

            <!-- A cleared section collapses to one line rather than
                 disappearing: vanishing sections make the list feel like it is
                 losing your work, and the count is the reassurance that it
                 isn't. -->
            <div
                v-else-if="section.label"
                class="sl-run-cleared row items-center q-gutter-xs"
            >
                <q-icon :name="ICONS.check_circle" color="positive" size="18px" />
                <span class="text-body2">
                    {{ section.label }}: all {{ section.total }} picked
                </span>
            </div>
        </div>

        <!-- Picked items land here rather than leaving the page. Rows used to
             be filtered out of their section and shown nowhere else, so a
             mis-tap removed an item with no way to see what had gone. Collapsed
             by default — it is a record, not the job — and it borrows the
             expansion shape the deferred-by-budget section already uses. -->
        <!-- Owner 2026-10-15: "Collected", with the count in the same circle the
             rest of the app uses for a count beside a chevron. -->
        <q-expansion-item
            v-if="pickedLines.length > 0"
            class="q-mt-md sl-panel sl-panel--sunken"
        >
            <template #header>
                <q-item-section avatar>
                    <q-icon :name="ICONS.check_circle" />
                </q-item-section>
                <q-item-section>
                    <q-item-label>Collected</q-item-label>
                    <q-item-label v-if="moneyEnabled" caption>
                        {{ formatMoney(pickedTotal) }} in the trolley
                    </q-item-label>
                </q-item-section>
                <q-item-section side>
                    <CountBadge
                        :count="pickedLines.length"
                        :label="`${pickedLines.length} collected`"
                    />
                </q-item-section>
            </template>
            <ShoppingListRunRow
                v-for="line in pickedLines"
                :key="line.line_id"
                :line="line"
                :picked="true"
                :nested="false"
                caption=""
                @toggle="emit('untick', line)"
                @capture-price="emit('capture-price', line)"
            />
        </q-expansion-item>

        <!-- Everything picked. The finish CTA lives in the sticky footer, so
             this is reassurance, not a second call to action. -->
        <div v-if="allPicked" class="text-center q-py-xl dora-text-muted">
            <q-icon :name="ICONS.check_circle" color="positive" size="48px" />
            <div class="text-h6 q-mt-sm">That's everything.</div>
            <div class="text-body2 q-mt-xs">
                Finish &amp; restock when you're through the till.
            </div>
        </div>

        <!-- Nothing to shop at all. Reachable when every line on the list was
             set aside by "Trim to fit" — rare, but the alternative is a blank
             page mid-shop with no explanation. -->
        <div v-else-if="lines.length === 0" class="text-center q-py-xl dora-text-muted">
            <q-icon :name="ICONS.shopping_cart" size="48px" />
            <div class="text-h6 q-mt-sm">Nothing on this list.</div>
            <div class="text-body2 q-mt-xs">
                Add something with <strong>Add item</strong>, or finish up.
            </div>
        </div>
    </div>
</template>

<script lang="ts" setup>
    /**
     * The run face — the list as it is used in a store.
     *
     * This is a different *composition* of the same list, not the plan face
     * with bigger checkboxes (that was the original defect: "shopping mode is a
     * costume"). Everything that exists to curate a list — drag handles,
     * delete, quantity steppers, buy-hint pickers, offer chips, provenance,
     * suggestions, the budget banner — is absent here, because none of it is a
     * thing you do while holding a trolley. What is left is one row, one
     * gesture, and an optional price.
     *
     * Picked rows leave the list, so it shrinks as the trip progresses — but
     * they are not gone: the *section* stays, collapsed to a one-line "all N
     * picked", and every picked row collects in one ungrouped, collapsed
     * "Picked" section at the bottom. A section that vanished outright read as
     * work being lost rather than done, and a row that vanished outright left a
     * mis-tap with nothing to undo from.
     */
    import { computed, toRef } from 'vue';
    import { ICONS } from 'src/style/icons';
    import ShoppingListRunRow from 'src/components/shoppingList/ShoppingListRunRow.vue';
    import CountBadge from 'src/components/CountBadge.vue';
    import { formatMoney } from 'src/composables/useMoney';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import {
        isNestedChild, sectionIconFor, sectionProgress, useLineSections,
        type SectionMode,
    } from 'src/composables/useLineSections';
    import type { ShoppingListLine } from 'src/models/shoppingList';

    const props = defineProps<{
        lines: ShoppingListLine[];
        mode: SectionMode;
        /** Server-owned `totals.picked_price` — what's in the trolley. Passed
         *  in rather than summed here: re-deriving it from the lines would put
         *  a second copy of the money ladder in the browser (R-003). */
        pickedTotal: number;
    }>();

    const emit = defineEmits<{
        /** Mark this line picked. The page owns the mutation and the undo. */
        tick: [line: ShoppingListLine];
        /** Put a picked line back on the list, from the Picked section. */
        untick: [line: ShoppingListLine];
        'capture-price': [line: ShoppingListLine];
    }>();

    const { moneyEnabled } = useMoneyEnabled();

    const allLines = toRef(props, 'lines');
    // Read-only: the overview card owns the control that sets the mode, so this
    // face only ever receives one.
    const modeRef = computed(() => props.mode);
    // Sectioning runs over *every* line, ticked included. The run face still
    // hides picked rows — but it does so per-section, so a section that has
    // emptied survives as its own "all 4 picked" line instead of silently
    // disappearing along with the evidence that you did that aisle.
    const { sections, effectiveMode } = useLineSections(allLines, modeRef);

    /** One pass per render: what's left to pick in each section, plus the
     *  progress the header and the collapsed line both read. Derived once
     *  because the template needs all three and `sectionProgress` walks every
     *  line to answer. */
    const runSections = computed(() =>
        sections.value.map((section) => ({
            ...section,
            remaining: section.lines.filter((l) => !l.is_ticked),
            ...sectionProgress(props.lines, section, effectiveMode.value),
        }))
    );

    const allPicked = computed(() =>
        props.lines.length > 0 && props.lines.every((l) => l.is_ticked)
    );

    /** Every picked line, ungrouped — the trolley doesn't have aisles. Order is
     *  the list's own, not pick order: the server doesn't record when a line was
     *  ticked, and inventing an order from render position would reshuffle on
     *  every refetch. */
    const pickedLines = computed(() => props.lines.filter((l) => l.is_ticked));



    /** What the shopper can act on, in aisle terms. Location is dropped when
     *  the sectioning already groups by it — repeating the heading on every
     *  row is noise at arm's length. */
    function captionFor(line: ShoppingListLine): string {
        const parts: string[] = [];
        const hint = line.preferred_buys?.find(
            (pb) => pb.preferred_buy_id === line.preferred_buy_id
        );
        if (hint) parts.push(hint.label);
        if (effectiveMode.value !== 'location' && line.stock_location_breadcrumb.length > 0) {
            parts.push(line.stock_location_breadcrumb[0]!);
        }
        if (effectiveMode.value !== 'store' && line.resolved_store_name) {
            parts.push(line.resolved_store_name);
        }
        return parts.join(' · ');
    }

</script>

<style scoped>
    /* The row's own layout, type scale and tap sizing moved to
       `ShoppingListRunRow.vue` and `src/css/shoppingList.scss` (chunk 5). What
       stays here is the one thing that isn't a row. */
    .sl-run-cleared {
        padding: var(--space-3) var(--space-4);
        border-radius: var(--radius-lg);
        background: var(--surface-sunken);
        color: var(--text-secondary);
    }
</style>
