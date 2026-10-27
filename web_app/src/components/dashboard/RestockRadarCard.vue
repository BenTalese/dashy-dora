<template>
    <DashboardCard :icon="ICONS.replay" title="Restock radar">
        <CardLoadError
            v-if="failed"
            line="I couldn't work out what needs restocking."
            @retry="emit('retry')"
        />

        <template v-else-if="rows.length > 0">
            <div class="dora-radar__head">Recently low or out</div>
            <ul class="dora-cook-list">
                <li v-for="row in rows" :key="row.stock_item_id" class="dora-radar__row">
                    <!-- Owner 2026-09-08 — *"use consistent level indicator at
                         the start of the row instead of out/etc text"*. This is
                         the app's own dot (`StockLevelDot`, R-001), the same one
                         the stock item header, the level picker and the stock
                         filter render, so "out" looks identical here and there.
                         D-013: a bare coloured dot is not a decodable signal, so
                         it carries the level's own name as a tooltip — which is
                         also what the words it replaced were for. -->
                    <StockLevelDot :sequence="row.level_sequence" size="12px">
                        <BaseTooltip>{{ row.level_name }}</BaseTooltip>
                    </StockLevelDot>
                    <router-link class="dora-cook-name" :to="`/stock/${row.stock_item_id}`">
                        {{ row.name }}
                    </router-link>
                    <!-- The chip that carried across from the retired "Before
                         you shop" card. It is the difference between "you're out
                         of this" and "you're out of this *and something you
                         planned needs it*", which is the whole reason that card
                         existed. -->
                    <q-badge
                        v-if="row.is_planned"
                        color="warning"
                        label="Planned"
                        class="dora-radar__chip"
                    >
                        <BaseTooltip>A meal you've planned needs this</BaseTooltip>
                    </q-badge>
                    <span class="dora-cook-meta">{{ whenLabel(row) }}</span>
                    <!-- The owner asked for "the same shopping cart button
                         from the stock overview rows" — this is literally
                         that component, in its `row` variant. It owns the
                         already-on-a-list toggle, the multi-list popover and
                         the toast, so the card emits nothing (R-011). -->
                    <AddToListButton variant="row" :stock-item-id="row.stock_item_id" />
                </li>
            </ul>
        </template>

        <!-- Honest about the window it actually looked at. The old copy said
             "Everything's stocked", which after the 09-08 staleness cutoff would
             be a lie: an item you ran out of in March is still out, it just
             isn't *recent*. The stock page, filtered by level, is where
             "everything you're out of" lives. -->
        <div v-else class="dora-empty dora-empty-ok">
            <q-icon :name="ICONS.check_circle" size="20px" class="q-mr-sm" />
            Nothing's gone low or out in the last {{ windowDays }} days.
        </div>
    </DashboardCard>
</template>

<script lang="ts" setup>
    import { relativeTime } from 'src/helpers/relativeTime';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    /**
     * Restock radar — what recently went low or out, most recent first.
     *
     * Reworked on the owner's ask, 2026-09-04. It used to render
     * `/reports/keeps-running-out`: how often an item was already out at the
     * moment somebody put it on a list. A sharp signal, and the reports review
     * rated it the best thing on either surface — but it ranks on a *lifetime*
     * count, so the card looked the same every week and the radar never swept.
     * It also says nothing at all until an install has months of list history.
     *
     * This is the present tense of the same idea, and it keeps the verb: every
     * row ends in the stock overview's own cart button. The lifetime ranking
     * still lives on the reports page, which is where a history belongs.
     *
     * **2026-09-08 — this card absorbed "Before you shop".** The owner's list
     * asked that card for a level indicator, a "recently low or out" heading
     * and recency ordering, and then concluded a few items later that the two
     * cards overlapped and *"I'm inclined to axe before you shop and chuck
     * 'planned' as a chip on the rows for restock radar"*. Later points win, so
     * all of it landed here:
     *
     *   · **one list, not two columns.** Out and Low were ordered by recency
     *     *within* a column, so the most recent change was not necessarily the
     *     top row — which is the only claim a radar makes. The band is the
     *     level dot at the head of the row now.
     *   · **`is_planned`** — a chip, straight off `gather_planned_demand`.
     *   · **a staleness cutoff**, server-side: *"don't show stuff that has been
     *     low/out for a long time"*.
     *
     * Everything above is server-decided (`/dashboard/restock-radar`); this file
     * picks words and shapes (R-003).
     */
    import { ICONS } from 'src/style/icons';
    import AddToListButton from 'src/components/AddToListButton.vue';
    import StockLevelDot from 'src/components/stock/StockLevelDot.vue';
    import DashboardCard from 'src/components/dashboard/DashboardCard.vue';
    import CardLoadError from 'src/components/dashboard/CardLoadError.vue';
    import type { RestockRow } from 'src/services/api/dashboardApiService';

    withDefaults(
        defineProps<{
            /** Already ordered by recency, capped and staleness-filtered by the
             *  server. This component does not sort. */
            rows: RestockRow[];
            /** How far back "recently" reaches — named in the empty copy rather
             *  than hardcoded, because the server owns the number. */
            windowDays: number;
            failed?: boolean;
        }>(),
        { failed: false },
    );

    const emit = defineEmits<{ (e: 'retry'): void }>();

    /**
     * How long it has been in this state. Coarse on purpose — "3 days ago" is
     * the actionable resolution, and with the server's 30-day cutoff in front of
     * it the long arms of this ladder now only fire near the edge of the window.
     *
     * Not `formatRelativeDay`: that names the *day* ("Tuesday"), and after a
     * fortnight a weekday name is useless. This answers "how long has this been
     * sitting there", which is the question the card is asking.
     */
    function whenLabel(row: RestockRow): string {
        return relativeTime(row.changed_at, { style: 'coarse' });
    }
</script>

<style scoped lang="scss">
    /* `.dora-cook-list`, `.dora-cook-name`, `.dora-cook-meta` and the empty
       states come from `css/dashboardCards.scss`. The row's own grid is this
       card's — and it is a grid rather than the shared `.dora-cook-row` because
       this row leads with a level dot and can carry a chip, which no other
       dashboard row does. */

    /* The two-column `.dora-radar` shell is gone with the two columns (owner,
       2026-09-08). What is left is one heading over one list, so the heading no
       longer needs per-column icon tinting — the level dot on each row carries
       the band, which is strictly better than a column header implying it. */
    .dora-radar__head {
        margin-bottom: var(--space-2);
        font-size: var(--font-size-xs);
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-secondary);
    }
    /* dot · name · chip · when · cart.
       **Flex-wrap, not a five-track grid.** The row now carries five things and
       a grid keeps them on one line at any width, which is what squeezed the
       Next-to-cook recipe name to zero at 375px (fixed there in the 09-05 batch
       with a `7ch` floor). Here the row is allowed to *wrap* instead: the name
       holds a `7ch` floor and everything past it drops to a second line when
       there isn't room. That is intrinsic — it responds to the CARD's width, not
       the viewport's, which is what R-078 requires of a card that can render
       half-width on a desktop and full-width on a phone. No container query,
       because nothing in this app declares a containment context and adding one
       to the shared `DashboardCard` shell would change every card including
       Reports'. */
    .dora-radar__row {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--space-2);
        padding: var(--space-1) var(--space-2);
        background: var(--surface-sunken);
        border-radius: var(--radius-md);
    }
    /* The one flexible item. `min-width` is what actually permits the shrink —
       a flex item's default `min-width: auto` refuses to go below its content. */
    .dora-radar__row .dora-cook-name {
        flex: 1 1 auto;
        min-width: 7ch;
    }
    /* Pins the cart button to the trailing edge of whichever line it lands on,
       so a wrapped row still reads as a row rather than a ragged pile. Selected
       positionally because `AddToListButton`'s row variant renders a
       `RowActionButton` with no class of its own to hook — and it is always the
       last thing in the row. An auto margin absorbs the free space *before*
       flex-grow gets it, which is deliberate: the name sizes to its content and
       the cart sits hard right, rather than the name stretching and the button
       floating in the middle of the row. */
    .dora-radar__row > *:last-child {
        margin-inline-start: auto;
    }
    /* D-014 — the chip says "Planned" in words; the warning tint is support,
       not the signal. */
    .dora-radar__chip {
        font-size: var(--font-size-xs);
    }
</style>
