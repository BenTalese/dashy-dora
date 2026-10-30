<template>
    <!-- BRIEF_MEAL_PLANNER_RAIL_AND_SHELL §5 (Unit 3) — the calendar as a real
         month grid.

         **This revises F13, which the previous widget built faithfully**, and
         it overrules DESIGN_REMEDIATION_PLAN's DR-12 "labelled 14-day strip"
         directive. Both were confirmed by the owner as D7 on 2026-08-29 — do
         not "restore" either without a fresh decision.

         The diagnosis it fixes: the old component was a **week picker wearing a
         calendar costume**. Only the week ROW was clickable, yet the day squares
         carried the status colour, so a day invited a click that did something
         else. Its status was a 2px underline on a ~20px square (the aria-label
         carried more than the visual), and only each Monday showed a number, so
         six rows read as a barcode.

         Kept deliberately: `dayStatus` still derives from the server's own
         verdict rather than re-judging cookability (R-003), and
         `STATUS_LABEL` / the accessible labels are ported to day cells rather
         than rewritten — they were good work against 1.4.1. -->
    <q-card flat bordered class="cal">
        <q-card-section class="row items-center q-py-xs no-wrap">
            <BaseButton
                variant="icon" size="sm"
                :icon="ICONS.chevron_left"
                aria-label="Previous month"
                @click="pageMonth(-1)"
            >
                <BaseTooltip>Previous month</BaseTooltip>
            </BaseButton>
            <q-space />
            <div class="text-subtitle2 text-weight-bold cal__month">{{ monthBanner }}</div>
            <q-space />
            <BaseButton
                variant="icon" size="sm"
                :icon="ICONS.chevron_right"
                aria-label="Next month"
                @click="pageMonth(1)"
            >
                <BaseTooltip>Next month</BaseTooltip>
            </BaseButton>
        </q-card-section>
        <q-separator />

        <q-card-section class="q-pa-sm">
            <div class="cal__dows" aria-hidden="true">
                <span v-for="dow in DOW_LETTERS" :key="dow.key">{{ dow.letter }}</span>
            </div>

            <!-- Month paging slides horizontally, direction-aware, mirroring the
                 week carousel. Tokens only (D-010). -->
            <transition :name="monthTransition" mode="out-in" @after-enter="flushPendingFocus">
                <div
                    :key="viewMonthKey"
                    class="cal__grid"
                    role="grid"
                    :aria-label="`Meal plan calendar, ${monthBanner}`"
                    @keydown="onGridKeydown"
                >
                    <div
                        v-for="week in weeks"
                        :key="week.monday"
                        class="cal__week"
                        :class="{ 'cal__week--focused': week.monday === focusedMonday }"
                        role="row"
                    >
                        <button
                            v-for="cell in week.days"
                            :key="cell.iso"
                            type="button"
                            role="gridcell"
                            class="cal-day"
                            :class="{
                                'cal-day--outside': !cell.inMonth,
                                'cal-day--today': cell.isToday,
                            }"
                            :aria-label="dayTitle(cell)"
                            :aria-current="cell.isToday ? 'date' : undefined"
                            :aria-selected="week.monday === focusedMonday ? 'true' : 'false'"
                            :tabindex="cell.iso === rovingIso ? 0 : -1"
                            :data-cal-iso="cell.iso"
                            @click="selectDay(cell.iso)"
                            @focus="rovingIso = cell.iso"
                        >
                            <span class="cal-day__dd">{{ cell.dd }}</span>
                            <!-- Shared with the phone's day strip since
                                 2026-09-01 (see `MealPlanDayPips.vue`). B2 /
                                 D-013: a coloured pip is never the only signal
                                 — the tooltip below counts the day's meals
                                 (owner 2026-09-12: a summary, not a line per
                                 meal), and `aria-label` spells the day's status
                                 out in full. -->
                            <MealPlanDayPips :pips="cell.pips" />
                            <BaseTooltip v-if="cell.tooltip" anchor="top middle" self="bottom middle">
                                {{ cell.tooltip }}
                            </BaseTooltip>
                        </button>
                    </div>
                </div>
            </transition>
        </q-card-section>
    </q-card>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    import { formatDate as formatLocaleDate, formatMonthYear, weekdayLetters } from 'src/composables/useDateFormat';
    import BaseButton from 'src/components/BaseButton.vue';
    import MealPlanDayPips from 'src/components/MealPlanDayPips.vue';
    import { storeToRefs } from 'pinia';
    import { isoDate, localTodayIso, mondayOf, shiftDays } from 'src/helpers/weekDates';
    import { dayPips, type DayPip } from 'src/helpers/mealPlanDayPips';
    import type { MealPlanEntry } from 'src/models/mealPlan';
    import { useBatchEnabled } from 'src/composables/useBatchEnabled';
    import { useMealPlanStore } from 'src/stores/mealPlanStore';
    import { computed, nextTick, ref, watch } from 'vue';

    const focusedMonday = defineModel<string>('focusedMonday', { required: true });

    const emit = defineEmits<{
        /** §5 — clicking a day focuses its week AND asks the host to scroll the
         *  week pane to that day's card. The scroll is the host's job because
         *  only it owns the scroller; this component just names the day. That
         *  payoff is only possible because Unit 1 gave the week its own scroll
         *  container. */
        (e: 'daySelected', dayIso: string): void;
    }>();

    /** Six rows always, so the grid's height never changes between months — a
     *  calendar that grows a row in a fixed-height pane pushes the shopping
     *  summary around underneath it. */
    const GRID_WEEKS = 6;


    // D-006 — weekday initials come from the household locale (de-DE reads
    // "M D M D F S S"), not a hard-coded English row. Computed so a late-landing
    // locale policy re-renders them.
    const DOW_LETTERS = computed(() => weekdayLetters());

    const { batchEnabled } = useBatchEnabled();
    const mealPlanStore = useMealPlanStore();
    const { mealPlans, today } = storeToRefs(mealPlanStore);

    // Declared up here, not beside the month state below: `monthForWeek` reads
    // it during setup to seed `viewMonth`, so a later `const` would be in its
    // temporal dead zone.
    const todayIso = computed(() => today.value ?? localTodayIso());

    // Entries for every plan, keyed by day — the calendar spans many weeks, so
    // it reads across all plans (not just the focused one).
    const entriesByDay = computed(() => {
        const map = new Map<string, MealPlanEntry[]>();
        for (const plan of mealPlans.value) {
            for (const entry of plan.entries) {
                const key = isoDate(entry.scheduled_for);
                const list = map.get(key) ?? [];
                if (!map.has(key)) map.set(key, list);
                list.push(entry);
            }
        }
        return map;
    });

    type DayStatus = 'empty' | 'planned' | 'short' | 'consumed';
    function dayStatus(dayIso: string): DayStatus {
        const entries = entriesByDay.value.get(dayIso);
        if (!entries || entries.length === 0) return 'empty';
        // Status is derived from the server's PER-ENTRY cook verdict (R-003)
        // — the client never re-judges cookability here. It used to test the
        // entry's recipe against the shortfall set, which called a day short
        // whenever any meal of a short recipe fell on it, even one the pool
        // covered.
        if (entries.some((e) => !e.consumed_at && e.needs_cooking)) return 'short';
        if (entries.every((e) => e.consumed_at)) return 'consumed';
        return 'planned';
    }

    // The per-meal pip (`pipFor` / `MAX_PIPS`) moved to
    // `src/helpers/mealPlanDayPips.ts` on 2026-09-01 so the phone's day strip
    // could code a day the same way this grid does instead of drawing one
    // undifferentiated dot.

    // ── The visible month ──────────────────────────────────────────────────
    // Anchored on the 1st of a month. Follows the focused week when that week
    // leaves the visible month, so toolbar nav and the calendar stay two views
    // of one `focusedMonday` (F17).
    const viewMonth = ref(monthForWeek(focusedMonday.value));
    const monthSlide = ref<'cal-next' | 'cal-prev'>('cal-next');
    const monthTransition = computed(() => monthSlide.value);
    const viewMonthKey = computed(() => viewMonth.value);

    function firstOfMonth(iso: string): string {
        return `${iso.slice(0, 7)}-01`;
    }
    /**
     * Which month a week belongs to — NOT simply its Monday's month.
     *
     * Owner feedback 2026-09-03: *"why does the calendar start on the previous
     * month if today is in the next month? Monday is the 31st and today is the
     * 2nd… the only reason I can think of is that the week started in that
     * month."* That was exactly it. A week straddling a month boundary is
     * mostly in one of the two, and that is the month a reader means: Mon 31
     * Aug – Sun 6 Sep is a September week (six days of seven), so opening it on
     * AUGUST showed the user a month they had already left.
     *
     * Today wins outright when it is inside the week, because "the month I am
     * in" beats any counting argument. Otherwise the majority of the week's
     * seven days decides — never a tie, since seven is odd.
     */
    function monthForWeek(mondayIso: string): string {
        const days = Array.from({ length: 7 }, (_, i) => shiftDays(mondayIso, i));
        const todayInWeek = days.find((iso) => iso === todayIso.value);
        if (todayInWeek) return firstOfMonth(todayInWeek);
        const tally = new Map<string, number>();
        for (const iso of days) {
            const month = firstOfMonth(iso);
            tally.set(month, (tally.get(month) ?? 0) + 1);
        }
        return [...tally.entries()].reduce((a, b) => (b[1] > a[1] ? b : a))[0];
    }
    function addMonths(firstIso: string, delta: number): string {
        const [y, m] = firstIso.split('-').map(Number);
        const base = new Date(Date.UTC(y!, m! - 1 + delta, 1));
        return base.toISOString().slice(0, 10);
    }
    function pageMonth(delta: number) {
        monthSlide.value = delta > 0 ? 'cal-next' : 'cal-prev';
        viewMonth.value = addMonths(viewMonth.value, delta);
    }

    watch(focusedMonday, (next, prev) => {
        const wanted = monthForWeek(next);
        if (wanted === viewMonth.value) return;
        // Only re-anchor when the focused week genuinely leaves the month on
        // screen; direction keeps the slide honest.
        monthSlide.value = next >= (prev ?? next) ? 'cal-next' : 'cal-prev';
        viewMonth.value = wanted;
    });


    type CalCell = {
        iso: string;
        dd: string;
        inMonth: boolean;
        isToday: boolean;
        status: DayStatus;
        pips: DayPip[];
        tooltip: string;
    };

    const weeks = computed<{ monday: string; days: CalCell[] }[]>(() => {
        const gridStart = mondayOf(viewMonth.value);
        const month = viewMonth.value.slice(0, 7);
        const out: { monday: string; days: CalCell[] }[] = [];
        for (let w = 0; w < GRID_WEEKS; w++) {
            const monday = shiftDays(gridStart, w * 7);
            const days: CalCell[] = [];
            for (let i = 0; i < 7; i++) {
                const iso = shiftDays(monday, i);
                const entries = entriesByDay.value.get(iso) ?? [];
                days.push({
                    iso,
                    dd: String(Number(iso.slice(8, 10))),
                    inMonth: iso.slice(0, 7) === month,
                    isToday: iso === todayIso.value,
                    status: dayStatus(iso),
                    ...dayPips(entries, batchEnabled.value),
                    tooltip: dayTooltip(iso, entries),
                });
            }
            out.push({ monday, days });
        }
        return out;
    });

    // Formatted from the YYYY-MM-DD itself (parsed as local midnight by the
    // formatter). The old `new Date(Date.UTC(...))` was UTC midnight, which
    // west of Greenwich is the previous local day — October read "SEPTEMBER".
    const monthBanner = computed(() => formatMonthYear(viewMonth.value).toUpperCase());

    // ── Selection ──────────────────────────────────────────────────────────
    function selectDay(dayIso: string) {
        focusedMonday.value = mondayOf(dayIso);
        emit('daySelected', dayIso);
    }

    // ── Keyboard: roving tabindex over the grid (§5) ───────────────────────
    // The old six-button list had no grid navigation at all. Exactly one cell
    // is tabbable; arrows move focus within the month, PageUp/PageDown page it.
    const rovingIso = ref(todayIso.value);
    watch([viewMonth, todayIso], () => {
        const visible = weeks.value.flatMap((w) => w.days.map((d) => d.iso));
        if (!visible.includes(rovingIso.value)) {
            rovingIso.value = visible.includes(todayIso.value)
                ? todayIso.value
                : (visible.find((iso) => iso.slice(0, 7) === viewMonth.value.slice(0, 7)) ?? visible[0]!);
        }
    });

    /**
     * Arrowing across a month boundary re-renders the whole grid through a
     * `mode="out-in"` transition: the old month leaves *before* the new one
     * enters, so one `nextTick` later the destination cell does not exist yet.
     * Measured — ArrowDown from 27 Jul focused nothing at all, and because the
     * keydown handler lives on the grid, losing focus killed every subsequent
     * key. So when the cell isn't there we park it and let `@after-enter` place
     * the focus once the new month has actually arrived.
     */
    const pendingFocusIso = ref<string | null>(null);

    /** Is this day one of the 42 currently drawn? The grid starts on the Monday
     *  on/before the 1st and always runs six weeks, so it reaches into both
     *  neighbouring months. */
    function isRendered(iso: string): boolean {
        const start = mondayOf(viewMonth.value);
        return iso >= start && iso <= shiftDays(start, GRID_WEEKS * 7 - 1);
    }

    async function focusCell(iso: string) {
        rovingIso.value = iso;
        await nextTick();
        const el = document.querySelector<HTMLElement>(`[data-cal-iso="${iso}"]`);
        if (el) el.focus();
        else pendingFocusIso.value = iso;
    }

    function flushPendingFocus() {
        const iso = pendingFocusIso.value;
        pendingFocusIso.value = null;
        if (iso) document.querySelector<HTMLElement>(`[data-cal-iso="${iso}"]`)?.focus();
    }

    function onGridKeydown(e: KeyboardEvent) {
        const DELTAS: Record<string, number> = {
            ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7,
        };
        const delta = DELTAS[e.key];
        if (delta !== undefined) {
            e.preventDefault();
            // Stop the page's own ArrowUp/ArrowDown week paging from also
            // firing — inside the grid, arrows move the grid.
            e.stopPropagation();
            const next = shiftDays(rovingIso.value, delta);
            // Page the month only when the day is genuinely NOT on screen —
            // not merely when it belongs to another month. The grid always
            // renders six weeks from the Monday on/before the 1st, so it spills
            // into both neighbours: July's grid runs to 9 August. Comparing
            // months instead of the rendered range paged unnecessarily, and the
            // cost was invisible but total — `focusCell` found the cell in the
            // OUTGOING grid, focused it, and the transition then unmounted it,
            // leaving focus on <body>. With the grid's own keydown handler gone
            // with it, every subsequent arrow fell through to the page's week
            // paging instead (measured: arrowing twice silently moved the week).
            if (!isRendered(next)) {
                monthSlide.value = delta > 0 ? 'cal-next' : 'cal-prev';
                viewMonth.value = firstOfMonth(next);
            }
            void focusCell(next);
            return;
        }
        if (e.key === 'PageUp' || e.key === 'PageDown') {
            e.preventDefault();
            e.stopPropagation();
            pageMonth(e.key === 'PageDown' ? 1 : -1);
            void focusCell(addMonths(firstOfMonth(rovingIso.value), e.key === 'PageDown' ? 1 : -1));
        }
    }

    function formatDate(iso: string): string {
        return formatLocaleDate(iso);
    }

    // R-Phase 6 §4.6 — text alternatives for the colour-only status (1.4.1).
    // Ported from the week rows to day cells; the wording is unchanged.
    const STATUS_LABEL: Record<DayStatus, string> = {
        empty: 'no meals planned',
        planned: 'meals planned',
        short: 'cook shortfall',
        consumed: 'all cooked',
    };
    function dayTitle(cell: CalCell): string {
        return `${formatDate(cell.iso)}: ${STATUS_LABEL[cell.status]}`;
    }

    /** §5 — hover NAMES the meals rather than reporting a status word. This is
     *  the reason to make days interactive at all: the calendar becomes a read
     *  surface, not only a picker. */
    /**
     * One line about the day, not a transcript of it.
     *
     * Owner 2026-09-12: *"the calendar day tooltips are too dense with text
     * when many meals are planned — just put a summary."* A busy day printed a
     * line per meal, so the hover card grew taller than the week it floated
     * over and you had to *read* it to learn what the pips already showed. The
     * counts are what a month view is for; the day itself is one click away.
     */
    function dayTooltip(iso: string, entries: MealPlanEntry[]): string {
        if (!entries.length) return `${formatDate(iso)}: no meals planned`;
        const meals = `${entries.length} meal${entries.length === 1 ? '' : 's'}`;
        const parts = [meals];
        const toCook = entries.filter((e) => !e.consumed_at && e.needs_cooking).length;
        if (toCook > 0) parts.push(`${toCook} to cook`);
        const cooked = entries.filter((e) => e.consumed_at).length;
        if (cooked > 0) parts.push(`${cooked} cooked`);
        return `${formatDate(iso)}: ${parts.join(' · ')}`;
    }
</script>

<style scoped>
    .cal__month {
        letter-spacing: 0.06em;
    }

    .cal__dows,
    .cal__week {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 2px;
    }
    .cal__dows {
        margin-bottom: 4px;
        text-align: center;
        font-size: var(--font-size-xs);
        font-weight: 600;
        color: var(--text-secondary);
    }
    .cal__grid {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    /* The focused week is a tinted BAND across all seven cells, with the outer
       corners rounded, so a week reads as one selected object even though every
       cell inside it is independently clickable. */
    .cal__week--focused {
        background: color-mix(in srgb, var(--brand-primary) 12%, transparent);
        border-radius: var(--radius-sm);
        box-shadow: 0 0 0 1px color-mix(in srgb, var(--brand-primary) 35%, transparent);
    }

    /* Owner feedback 2026-09-03 — *"after putting enough meals on the planner
       the calendar days go askew; keep the day squares where they are"*. The
       square was `aspect-ratio` with no ceiling, so a day whose pip row grew
       (a second row of pips, or the old "+N" label) pushed its own cell taller
       and dragged the whole week row with it. The cell is now a fixed square
       that clips: the pips wrap inside it and stop when it is full. */
    .cal-day {
        position: relative;
        aspect-ratio: 1 / 1;
        min-height: 34px;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 2px;
        border: none;
        border-radius: 5px;
        background: var(--surface-sunken);
        color: var(--text-primary);
        cursor: pointer;
        font: inherit;
        transition: background var(--motion-fast) var(--motion-ease),
            transform var(--motion-fast) var(--motion-ease);
    }
    .cal-day:hover {
        background: color-mix(in srgb, var(--brand-primary) 16%, var(--surface-sunken));
        transform: translateY(-1px);
    }
    .cal-day:focus-visible {
        outline: 2px solid var(--brand-primary);
        outline-offset: 2px;
    }
    /* Out-of-month days are dimmed but still clickable — they belong to real
       weeks, and clicking one is a legitimate way to reach that week. */
    .cal-day--outside {
        opacity: 0.45;
    }

    .cal-day__dd {
        font-size: var(--font-size-xs);
        line-height: 1;
        /* Real dates in every cell now, so the column of numbers has to align —
           the old grid showed a number only on Mondays. */
        font-variant-numeric: tabular-nums;
    }
    /* Today is a FILLED disc, never a ring: a ring would collide with the focus
       ring the moment days became focusable, which they now are. */
    .cal-day--today .cal-day__dd {
        background: var(--brand-primary);
        color: var(--text-on-primary);
        border-radius: 999px;
        padding: 1px 5px;
        font-weight: 700;
    }


    /* Direction-aware month paging, mirroring the week carousel's transition
       and riding the same tokens (D-010 — no literal ms). */
    .cal-next-enter-active,
    .cal-next-leave-active,
    .cal-prev-enter-active,
    .cal-prev-leave-active {
        transition:
            transform var(--motion-normal) var(--motion-ease),
            opacity var(--motion-normal) var(--motion-ease);
    }
    .cal-next-enter-from { transform: translateX(16px); opacity: 0; }
    .cal-next-leave-to { transform: translateX(-16px); opacity: 0; }
    .cal-prev-enter-from { transform: translateX(-16px); opacity: 0; }
    .cal-prev-leave-to { transform: translateX(16px); opacity: 0; }
</style>
