<template>
    <DashboardCard :icon="ICONS.calendar_month" title="What's coming">
        <div class="dora-cal-legend q-mb-sm">
            <span class="dora-cal-leg"><span class="dora-cal-dot dot-meal" /> meals</span>
            <span class="dora-cal-leg"><span class="dora-cal-dot dot-expiry" /> expiry</span>
            <span class="dora-cal-leg"><span class="dora-cal-dot dot-shopping" /> shopping</span>
        </div>

        <CardLoadError
            v-if="failed"
            line="I couldn't load what's coming up."
            @retry="emit('retry')"
        />
        <template v-else-if="cells.length > 0">
            <div class="dora-cal-grid" role="grid">
                <button
                    v-for="cell in cells"
                    :key="cell.iso"
                    type="button"
                    class="dora-cal-cell"
                    :class="{
                        'is-today': cell.isToday,
                        'is-selected': cell.iso === selected,
                        'has-events': cell.hasMeal || cell.hasExpiry || cell.hasShopping,
                    }"
                    :aria-pressed="cell.iso === selected"
                    :aria-label="cell.label"
                    @click="emit('select', cell.iso)"
                >
                    <!-- The weekday label came across from the retired week
                         strip. Losing it in the merge would have left a bare
                         number grid, and D-012 explicitly wants calendar cells
                         labelled rather than reduced to dots. -->
                    <span class="dora-cal-dow">{{ cell.dow }}</span>
                    <span class="dora-cal-num">{{ cell.dayNum }}</span>
                    <span class="dora-cal-dots">
                        <span v-if="cell.hasMeal" class="dora-cal-dot dot-meal" />
                        <span v-if="cell.hasExpiry" class="dora-cal-dot dot-expiry" />
                        <span v-if="cell.hasShopping" class="dora-cal-dot dot-shopping" />
                    </span>
                </button>
            </div>
            <!-- Owner 2026-09-08 — *"The text all looks too similar in the area
                 shown when tapping on a day."* It was four type roles at two
                 sizes and two weights, so the day, the category and the thing
                 itself all read as one block of prose. Three changes, each
                 giving one role a channel of its own: the day becomes the
                 panel's title (a step up the scale, accent ink, its own rule);
                 every category label carries the SAME dot the grid above uses,
                 so "Expiring" is keyed to the red pip you just tapped; and each
                 entry becomes an obvious tappable row with the qualifier (slot /
                 level) demoted to a chip rather than more sentence. -->
            <div v-if="selected" class="dora-cal-detail">
                <div class="dora-cal-detail-date">
                    {{ formatRelativeDay(selected) }}
                </div>
                <div v-if="!hasEntries" class="dora-cal-hint">Nothing on.</div>
                <template v-else-if="selectedDay">
                    <div v-if="selectedDay.meals.length > 0" class="dora-cal-group">
                        <div class="dora-cal-group-label">
                            <span class="dora-cal-dot dot-meal" />Meals
                        </div>
                        <router-link
                            v-for="(m, i) in selectedDay.meals"
                            :key="`${m.recipe_id}-${m.slot}-${i}`"
                            class="dora-cal-item"
                            :to="`/cookbook/${m.recipe_id}`"
                        >
                            <span class="dora-cal-item__name">{{ m.recipe_name }}</span>
                            <span class="dora-cal-slot">{{ m.slot }}</span>
                        </router-link>
                    </div>
                    <div v-if="selectedDay.expiries.length > 0" class="dora-cal-group">
                        <div class="dora-cal-group-label">
                            <span class="dora-cal-dot dot-expiry" />Expiring
                        </div>
                        <router-link
                            v-for="e in selectedDay.expiries"
                            :key="e.stock_item_id"
                            class="dora-cal-item"
                            :to="`/stock/${e.stock_item_id}`"
                        >
                            <span class="dora-cal-item__name">{{ e.name }}</span>
                        </router-link>
                    </div>
                    <div v-if="selectedDay.shopping.length > 0" class="dora-cal-group">
                        <div class="dora-cal-group-label">
                            <span class="dora-cal-dot dot-shopping" />Shopping
                        </div>
                        <router-link
                            v-for="s in selectedDay.shopping"
                            :key="s.list_id"
                            class="dora-cal-item"
                            :to="`/shopping-lists/${s.list_id}`"
                        >
                            <span class="dora-cal-item__name">{{ s.name }}</span>
                        </router-link>
                    </div>
                </template>
            </div>
        </template>
        <div v-else class="dora-empty">
            Nothing scheduled in the next fortnight.
            <router-link class="dora-empty-cta" to="/meal-plans">Plan a week →</router-link>
        </div>
    </DashboardCard>
</template>

<script lang="ts" setup>
    /**
     * "What's coming" — the dashboard's one forward-looking calendar.
     *
     * FU-818 merged two cards into this: the 7-day meal-pip strip ("The week
     * ahead") and the 14-day dot grid ("This fortnight"). They rendered the same
     * days from **two different endpoints** — the strip from
     * `/dashboard/summary`'s `upcoming_entries`, the grid from
     * `/alerts/upcoming` — so the overlapping week could disagree with itself on
     * one screen with no way to tell which was right (R-003). One source now,
     * D-012's reading is that a pip strip and a dot grid are the same widget at
     * two zoom levels, so they were never two cards' worth of information. The
     * 7/14 toggle that merge shipped is gone too (owner, 2026-09-08) — see the
     * note above `CalendarCell`.
     *
     * Two things improved in the merge: the week view gained the **expiry and
     * shopping** dots it never had, and the old "Next up" callout went — it
     * restated the hero line verbatim.
     *
     * Extracted from `DashboardPage.vue` (FU-829). The page owns the fetch and
     * builds `cells` (it needs the household's local-date logic and the shared
     * `parseLocalIso`), so this component renders and emits.
     */
    import { computed } from 'vue';
    import { ICONS } from 'src/style/icons';
    import { formatRelativeDay } from 'src/composables/useDateFormat';
    import DashboardCard from 'src/components/dashboard/DashboardCard.vue';
    import CardLoadError from 'src/components/dashboard/CardLoadError.vue';
    import type { UpcomingDay } from 'src/models/alert';

    /* `CalendarSpan` and the 7/14 toggle are gone (owner, 2026-09-08 — *"Just
       show 14 days always, remove the toggle option"*). FU-818 shipped the
       toggle when it merged the 7-day strip and the 14-day grid into this card,
       on the reasoning that a week is the planning unit. But both spans always
       came from the same already-fetched 14 days, so the control cost a header
       widget and a piece of persisted-looking state (it wasn't persisted — it
       reset on every navigation) to hide half of a payload the card had already
       paid for. Two rows of seven is also the shape a fortnight *is*. */

    export type CalendarCell = {
        iso: string;
        dayNum: number;
        dow: string;
        /** Accessible name — the cell's visible text is an abbreviation. */
        label: string;
        isToday: boolean;
        hasExpiry: boolean;
        hasShopping: boolean;
        hasMeal: boolean;
    };

    const props = withDefaults(
        defineProps<{
            /** All fourteen, built by the page. */
            cells: CalendarCell[];
            /** Always a day once the cells exist: today until you tap another. */
            selected: string | null;
            /** Null when nothing is scheduled on `selected`. */
            selectedDay: UpcomingDay | null;
            failed?: boolean;
        }>(),
        { failed: false },
    );

    const hasEntries = computed(() => {
        const d = props.selectedDay;
        return !!d && (d.meals.length + d.expiries.length + d.shopping.length) > 0;
    });

    const emit = defineEmits<{
        (e: 'select', iso: string): void;
        (e: 'retry'): void;
    }>();
</script>

<style scoped lang="scss">
    /* Moved with the card (R-027); off the page-local `--c-*` aliases, which
       resolve to nothing from a component (R-060). */
    .dora-cal-legend {
        display: flex;
        gap: var(--space-3);
        /* Was 11.5px — under D-003's floor, on the card's own decoder ring
           (D-013). The legend must be the most legible thing here. */
        font-size: var(--font-size-xs);
        color: var(--text-secondary);
    }
    .dora-cal-leg {
        display: inline-flex;
        align-items: center;
        gap: var(--space-1);
    }
    .dora-cal-grid {
        display: grid;
        grid-template-columns: repeat(7, minmax(0, 1fr));
        gap: var(--space-2);
    }
    .dora-cal-cell {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--space-1);
        min-height: 56px;
        padding: var(--space-2) var(--space-1);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
        /* A1: nested rows are inset wells inside a card — `--surface-sunken`.
           `--surface-elevated` is for surfaces floating ABOVE a card. */
        background: var(--surface-sunken);
        color: var(--text-primary);
        cursor: pointer;
        transition: border-color var(--motion-fast) var(--motion-ease), background var(--motion-fast) var(--motion-ease), transform var(--motion-fast) var(--motion-ease);
    }
    .dora-cal-cell.has-events:hover {
        border-color: var(--border-strong);
        transform: translateY(-1px);
    }
    .dora-cal-cell.is-today {
        /* An accent-coloured hairline is `--accent-mark` (R-069). */
        border-color: var(--accent-mark);
        font-weight: 700;
    }
    .dora-cal-cell.is-selected {
        background: var(--brand-primary-soft);
        border-color: var(--brand-primary);
    }
    /* A6 — focus is always visible. These are real <button>s, so they were
       keyboard-reachable already; what they lacked was a ring. */
    .dora-cal-cell:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    /* Weekday label, inherited from the retired week strip (FU-818). D-012 wants
       calendar cells labelled rather than reduced to bare dots, and a 14-cell
       grid of numbers alone is genuinely hard to read. */
    .dora-cal-dow {
        font-size: var(--font-size-xs);
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--text-secondary);
        line-height: 1;
    }
    .dora-cal-cell.is-today .dora-cal-dow {
        color: var(--accent-ink);
        font-weight: 700;
    }
    .dora-cal-num {
        font-size: var(--font-size-md);
        line-height: 1;
    }
    .dora-cal-dots {
        display: flex;
        gap: var(--space-1);
        min-height: 6px;
    }
    .dora-cal-dot {
        width: 6px;
        height: 6px;
        border-radius: var(--radius-pill);
        flex-shrink: 0;
    }
    .dora-cal-dot.dot-meal {
        background: var(--semantic-positive);
    }
    .dora-cal-dot.dot-expiry {
        background: var(--semantic-negative);
    }
    /* Owner 2026-09-04 — *"meals and shopping are too similar in colour"*. He
       is right, and it was theme-dependent rather than an oversight: meals take
       `--semantic-positive` (a green), shopping took `--brand-primary`, and on
       the themes whose brand tone is itself green the two dots were nearly the
       same swatch. Three categories on one cell need three *categorical*
       colours, not two semantics and a brand.

       `--semantic-info` is the fix: a blue in every theme, defined right beside
       the positive and negative these sit with, so the trio stays separable
       under any palette. Not a `--chart-*` ramp entry — those are for series in
       a chart, and these three are a fixed legend (D-001). */
    .dora-cal-dot.dot-shopping {
        background: var(--semantic-info);
    }
    .dora-cal-hint {
        margin-top: var(--space-3);
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
    }
    .dora-cal-detail {
        margin-top: var(--space-4);
        padding: var(--space-3) var(--space-4);
        background: var(--surface-sunken);
        border-radius: var(--radius-md);
    }
    /* ── The tapped day's panel (owner 2026-09-08: "text all looks too
       similar") ────────────────────────────────────────────────────────────
       Before: the date was `md`/700, the category label `xs`/uppercase, the
       entry `sm`/primary and its slot `sm`/secondary — so the entry and its
       qualifier were the same size, and the date differed from an entry only by
       weight. Four roles, effectively two appearances. Each role now has one
       clear channel: SIZE for the title, a COLOURED DOT for the category, a
       ROW SHAPE for the entry, and a CHIP for the qualifier. */
    .dora-cal-detail-date {
        /* One step up the ladder, and the accent ink every other
           accent-coloured string on this page uses (R-069) — the date is this
           panel's heading, not a bold line of its body. */
        font-size: var(--font-size-lg);
        font-weight: 700;
        line-height: 1.2;
        color: var(--accent-ink);
        padding-bottom: var(--space-2);
        /* A6: an in-panel separator is `--divider`. */
        border-bottom: 1px solid var(--divider);
        margin-bottom: var(--space-2);
    }
    .dora-cal-group + .dora-cal-group {
        margin-top: var(--space-3);
    }
    /* Carries the grid's own legend dot, so the label is keyed to the pip the
       user just tapped rather than being another line of small caps. D-013: the
       dot never travels alone — it is always beside its word. */
    .dora-cal-group-label {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        font-size: var(--font-size-xs);
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--text-secondary);
        margin-bottom: var(--space-1);
    }
    /* An entry is a tappable row now, not a line of text whose only affordance
       was a hover underline that touch devices never see. D-004's 44px floor
       applies for the same reason it does on `.dora-use-recipe`: these are
       links, so nothing else supplies it. */
    .dora-cal-item {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        min-height: 44px;
        padding: var(--space-1) var(--space-2);
        border-radius: var(--radius-md);
        color: var(--text-primary);
        text-decoration: none;
        font-size: var(--font-size-md);
    }
    .dora-cal-item:hover {
        /* The panel already sits on `--surface-sunken`, so a row inside it
           lifts rather than sinking further. */
        background: var(--surface-component);
    }
    /* A6 — focus is always visible, and these had nothing. */
    .dora-cal-item:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    .dora-cal-item__name {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    /* The qualifier, as a chip: two steps below the name and on its own
       ground, so "Dinner" can no longer be mistaken for part of the dish. */
    .dora-cal-slot {
        margin-inline-start: auto;
        flex-shrink: 0;
        padding: 0 var(--space-2);
        border-radius: var(--radius-pill);
        background: var(--surface-component);
        border: 1px solid var(--border-default);
        color: var(--text-secondary);
        font-size: var(--font-size-xs);
        line-height: 1.8;
    }
    .dora-cal-item:hover .dora-cal-slot {
        background: var(--surface-sunken);
    }

    @media (prefers-reduced-motion: reduce) {
        .dora-cal-cell {
            transition: none !important;
        }
        .dora-cal-cell.has-events:hover {
            transform: none !important;
        }
    }
</style>
