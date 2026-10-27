<template>
    <div class="mobile-focus">
        <!-- Week nav -->
        <div class="mobile-focus__weeknav">
            <BaseButton variant="icon" :icon="ICONS.arrow_back" @click="goPrevWeek">
                <BaseTooltip>Previous week</BaseTooltip>
            </BaseButton>
            <!-- Owner 2026-09-13 — the same heading voice the desktop toolbar
                 and the month grid use, and the same second line: where you are
                 on the left, how full the week is on the right. The phone had a
                 plain bold label and neither figure. -->
            <div class="mobile-focus__weeknav-block">
                <div class="mobile-focus__weeknav-label">{{ weekRangeLabel }}</div>
                <div class="mobile-focus__weeknav-meta text-caption dora-text-muted">
                    <span>{{ weekRelativeLabel }}</span>
                    <span v-if="plannedCount > 0">{{ plannedCount }} planned</span>
                </div>
            </div>
            <BaseButton variant="icon" :icon="ICONS.arrow_forward" @click="goNextWeek">
                <BaseTooltip>Next week</BaseTooltip>
            </BaseButton>
            <!-- Owner feedback 2026-09-03 — *"mobile view is missing some
                 functionality… no save as template, no browse/apply template,
                 no clear week."* It was: the phone carried two of the desktop
                 toolbar's six week actions as bare icon buttons, and the other
                 four had no entry point at all below 1024px. This is the SAME
                 overflow menu the desktop toolbar carries — same order, same
                 disabled rules — so there is one list of week actions rather
                 than a phone-sized subset of one (R-001 / D-023).

                 Duplicate and print give up their promoted icon buttons to it:
                 two of six promoted for no reason is what made the gap easy to
                 miss in the first place. `planner.printFocusedWeek` still does
                 the work (it opens the print-view route in a new tab, and the
                 browser's "Save as PDF" is the export). -->
            <BaseButton
                variant="icon"
                :icon="ICONS.more_vert"
                class="q-ml-sm"
                aria-label="More week actions"
            >
                <q-menu anchor="bottom right" self="top right">
                    <q-list style="min-width: 220px">
                        <q-item
                            v-close-popup clickable
                            :disable="plannedCount === 0"
                            @click="emit('duplicateWeek')"
                        >
                            <q-item-section avatar>
                                <q-icon :name="ICONS.content_copy" />
                            </q-item-section>
                            <q-item-section>Duplicate to next week</q-item-section>
                        </q-item>
                        <q-item
                            v-close-popup clickable
                            :disable="plannedCount === 0"
                            @click="emit('print')"
                        >
                            <q-item-section avatar>
                                <q-icon :name="ICONS.print" />
                            </q-item-section>
                            <q-item-section>Print this week</q-item-section>
                        </q-item>

                        <q-separator />

                        <q-item
                            v-close-popup clickable
                            :disable="!canSaveCurrentWeek"
                            @click="emit('saveTemplate')"
                        >
                            <q-item-section avatar>
                                <q-icon :name="ICONS.save" />
                            </q-item-section>
                            <q-item-section>Save week as template…</q-item-section>
                        </q-item>
                        <!-- Owner 2026-10-15: Apply template is the primary
                             button below, so the menu carries the one template
                             action the phone had no way to reach, the same
                             entry the desktop menu has. -->
                        <q-item v-close-popup clickable to="/meal-plans/templates">
                            <q-item-section avatar>
                                <q-icon :name="ICONS.settings" />
                            </q-item-section>
                            <q-item-section>Manage templates…</q-item-section>
                        </q-item>

                        <q-separator />

                        <q-item
                            v-close-popup clickable
                            :disable="plannedCount === 0"
                            class="text-negative"
                            @click="emit('clearWeek')"
                        >
                            <q-item-section avatar>
                                <q-icon :name="ICONS.delete_outline" color="negative" />
                            </q-item-section>
                            <q-item-section>Clear week</q-item-section>
                        </q-item>
                    </q-list>
                </q-menu>
                <BaseTooltip>More week actions</BaseTooltip>
            </BaseButton>
        </div>

        <!-- FU-596 — flagship "Build my week" entry point. Dora's audience is
            mobile, so the auto-planner must be reachable here, not just on the
            desktop toolbar.

            Owner 2026-09-13 — "Apply template" joins it, side by side and equal
            width. They are the two ways to fill an empty week in one move, so
            they read as a pair here exactly as they now do in the desktop
            toolbar; applying was a menu item on the phone and a promoted button
            on the desktop, which is the kind of difference nobody decided. -->
        <div class="mobile-focus__weekactions q-mt-sm">
            <BaseButton
                variant="primary"
                :icon="ICONS.dora_voice"
                label="Build my week"
                @click="emit('openBuilder')"
            />
            <BaseButton
                variant="secondary"
                :icon="ICONS.event_repeat"
                label="Apply template"
                @click="emit('openTemplates')"
            />
        </div>

        <!-- Owner 2026-09-13 — the over-budget banner had no phone home at all;
             it rendered inside the desktop week scroller only. The page fills
             this slot with the same component, so there is one warning, placed
             at the top of the week's content at both breakpoints. -->
        <slot name="alert" />

        <!-- Day strip — 7 day buttons across the top. Today is highlighted;
            the focused day carries the primary accent. -->
        <div class="mobile-focus__day-strip" role="tablist">
            <button
                v-for="day in weekDays"
                :key="day.iso"
                type="button"
                role="tab"
                :aria-selected="day.iso === focusedDayIso"
                :aria-label="dayChipLabel(day)"
                class="mobile-focus__day-chip"
                :class="{
                    'mobile-focus__day-chip--today': day.iso === currentDayIso,
                    'mobile-focus__day-chip--focused': day.iso === focusedDayIso,
                    'mobile-focus__day-chip--past': isPastDay(day.iso),
                    'mobile-focus__day-chip--has-meals': entriesFor(day.iso).length > 0,
                }"
                @click="focusedDayIso = day.iso"
            >
                <span class="mobile-focus__day-chip-label">{{ day.label.charAt(0) }}</span>
                <span class="mobile-focus__day-chip-num">{{ dayOfMonth(day.iso) }}</span>
                <!-- Owner feedback 2026-09-01 — "I expect the mobile view day
                     picker to act the same as the full calendar in that it
                     shows the same pip info at the bottom. Currently they feel
                     diverged." They were: this drew ONE dot meaning "something
                     is planned", while the desktop calendar drew a pip per meal
                     coded planned / short / cooked. Same component now, at the
                     small size (`MealPlanDayPips.vue`). D-013 — the pips are
                     not the only signal; the chip's `aria-label` names the
                     day's state in words. -->
                <MealPlanDayPips
                    class="mobile-focus__day-chip-pips"
                    size="sm"
                    v-bind="pipsFor(day.iso)"
                />
            </button>
        </div>

        <!-- Focused-day header -->
        <div class="mobile-focus__day-header">
            <div>
                <div class="text-h6 q-mb-none">{{ focusedDayLongLabel }}</div>
                <!-- Owner 2026-09-12 — the day's cost rollup is gone here too:
                     every meal carries its own price chip now, so the day's
                     spend reads off the column and the coverage fraction is
                     visible as the chips that aren't there. -->
                <div class="text-caption dora-text-muted">{{ focusedDayHumanCount }}</div>
            </div>
            <q-badge
                v-if="focusedDayIso === currentDayIso"
                color="primary"
                class="q-ml-sm mobile-focus__today"
                label="TODAY"
            />
        </div>

        <!-- Focused-day entries, grouped by meal slot. Owner feedback
             2026-09-05, two halves of one problem: *"no way to show all slots
             for a day on mobile"* and *"a chip on the meal row is not very
             obvious or easy to read for groupings of meals (based on slot)"* —
             plus *"mobile does not respect the order of the meal slots, it just
             appends."*

             All three came from the same shape: the phone rendered ONE flat
             list of the day's entries in the order the server returned them,
             with each card's slot printed as a small tag. So a slot with
             nothing in it did not exist here (the desktop week card renders
             every slot as a row), the day's meals read in save order rather
             than breakfast→dinner, and the only thing carrying the slot was a
             0.68rem uppercase chip.

             A heading per slot answers all three at once, and it is the same
             model the desktop day card uses (R-001 in spirit — the phone stops
             being a different arrangement of the same day). The order is
             `slotNames`, which is the household's own vocabulary order; the
             card's slot tag is gone, because the heading above it says it. -->
        <div class="mobile-focus__entries">
            <section
                v-for="group in slotGroups"
                :key="group.slot"
                class="mobile-focus__slot"
            >
                <h3 class="mobile-focus__slot-head">
                    <span class="mobile-focus__slot-name">{{ group.slot }}</span>
                    <span v-if="group.entries.length" class="mobile-focus__slot-count">
                        {{ group.entries.length }}
                    </span>
                </h3>
                <MealPlanRichCard
                    v-for="{ key, entry } in group.entries"
                    :key="key"
                    :entry="entry"
                    :shortfall="entry.needs_cooking"
                    :highlight="false"
                    @view="emit('entryView', entry.recipe_id)"
                    @cook="emit('entryCook', entry)"
                    @remove="emit('entryRemove', entry)"
                    @adjust="(d: number) => emit('entryAdjust', entry, d)"
                    @link="emit('entryLink', entry)"
                    @unlink="emit('entryUnlink', entry)"
                    @lighter="emit('entryLighter', entry)"
                    @fresh="emit('entryFresh', entry)"
                />
                <!-- The add lands straight in this slot. The "Which slot?"
                     bottom sheet the old single button opened is gone with it:
                     asking which slot is only necessary when the slots aren't
                     on screen, and now they always are. -->
                <button
                    v-if="!isPastDay(focusedDayIso) && group.addable"
                    type="button"
                    class="mobile-focus__add"
                    :aria-label="`Add a meal to ${group.slot}`"
                    @click="emit('addToSlot', focusedDayIso, group.slot)"
                >
                    <q-icon :name="ICONS.add" size="16px" class="q-mr-xs" />
                    <span>Add</span>
                </button>
            </section>
            <div
                v-if="isPastDay(focusedDayIso) && !entriesFor(focusedDayIso).length"
                class="dora-text-muted text-center q-py-md text-caption"
            >
                Past day, read-only.
            </div>
        </div>

        <!-- The week's consequences — the status strip and "This week's
             shopping" with its per-ingredient breakdown — used to live here as
             a collapsible card whose own header restated what was inside it.
             Owner feedback 2026-09-03, twice over: *"the expandable card in
             mobile view at the bottom is a bit odd. Don't like how it
             duplicates information so much. Just make it a normal card with
             the expanded contents shown"* and *"can't see the ingredient
             breakdown properly on the shopping list"*. Both are answered by
             giving the phone the SAME two components the desktop right rail
             renders, plainly and un-collapsed, rather than a second
             implementation behind a disclosure (R-001). The page owns that —
             it owns the planner's data — so see `MealPlansOverview.vue`'s
             mobile branch. -->

    </div>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import { formatDate as formatLocaleDate } from 'src/composables/useDateFormat';
    import MealPlanDayPips from 'src/components/MealPlanDayPips.vue';
    import MealPlanRichCard from 'src/components/MealPlanRichCard.vue';
    import { ICONS } from 'src/style/icons';
    import { useBatchEnabled } from 'src/composables/useBatchEnabled';
    import type { MealPlanEntry } from 'src/models/mealPlan';
    import type { WeekDay } from 'src/composables/useMealPlanner';
    import { dayPips } from 'src/helpers/mealPlanDayPips';
    import { keyedEntries } from 'src/helpers/mealPlanEntryKey';
    import { localTodayIso } from 'src/helpers/weekDates';
    import { computed, ref, watch } from 'vue';

    const { batchEnabled } = useBatchEnabled();

    const props = defineProps<{
        weekDays: WeekDay[];
        slotNames: readonly string[];
        entriesFor: (dayIso: string) => MealPlanEntry[];
        isPastDay: (dayIso: string) => boolean;
        currentDayIso: string;
        weekRangeLabel: string;
        /** "This week" / "in 2 weeks" — the same server-anchored label the
         *  desktop toolbar shows beside the range. */
        weekRelativeLabel: string;
        plannedCount: number;
        /** Gates "Save week as template…" on the same fact the desktop
         *  toolbar's copy of that item gates on (R-003 — one predicate, owned
         *  by the page). */
        canSaveCurrentWeek: boolean;
    }>();

    const emit = defineEmits<{
        (e: 'entryView', recipeId: string): void;
        (e: 'entryCook', entry: MealPlanEntry): void;
        (e: 'entryRemove', entry: MealPlanEntry): void;
        (e: 'entryAdjust', entry: MealPlanEntry, delta: number): void;
        (e: 'entryLink', entry: MealPlanEntry): void;
        (e: 'entryUnlink', entry: MealPlanEntry): void;
        (e: 'entryLighter', entry: MealPlanEntry): void;
        (e: 'entryFresh', entry: MealPlanEntry): void;
        (e: 'addToSlot', dayIso: string, slot: string): void;
        (e: 'goPrevWeek'): void;
        (e: 'goNextWeek'): void;
        (e: 'print'): void;
        (e: 'duplicateWeek'): void;
        (e: 'saveTemplate'): void;
        (e: 'openTemplates'): void;
        (e: 'clearWeek'): void;
        (e: 'openBuilder'): void;
    }>();

    /** Same coding as the desktop month grid, from the same helper: each
     *  entry's own server-owned `consumed_at` + `needs_cooking` (R-003). */
    function pipsFor(dayIso: string) {
        return dayPips(props.entriesFor(dayIso), batchEnabled.value);
    }

    /** The pips' text alternative. A chip reading "M 15" with three coloured
     *  dots says nothing to a screen reader otherwise. */
    function dayChipLabel(day: WeekDay): string {
        const entries = props.entriesFor(day.iso);
        if (!entries.length) return `${day.label} ${dayOfMonth(day.iso)}: no meals planned`;
        const short = entries.filter((e) => !e.consumed_at && e.needs_cooking).length;
        const meals = `${entries.length} meal${entries.length === 1 ? '' : 's'}`;
        return short
            ? `${day.label} ${dayOfMonth(day.iso)}: ${meals}, ${short} short`
            : `${day.label} ${dayOfMonth(day.iso)}: ${meals}`;
    }

    // Focused day — defaults to today when today is inside the focused week,
    // else the first day of the week.
    const focusedDayIso = ref<string>(initialFocusedDay());
    function initialFocusedDay(): string {
        const today = props.currentDayIso ?? localTodayIso();
        const inWeek = props.weekDays.some((d) => d.iso === today);
        return inWeek ? today : props.weekDays[0]?.iso ?? today;
    }

    // When the week changes, reset to today-in-week (or the first day) so the
    // user lands on a sensible default rather than the same weekday they were
    // on previously.
    watch(
        () => props.weekDays.map((d) => d.iso).join(','),
        () => {
            focusedDayIso.value = initialFocusedDay();
        },
    );

    const focusedDayLongLabel = computed(() => {
        const day = props.weekDays.find((d) => d.iso === focusedDayIso.value);
        if (!day) return '';
        // Owner 2026-09-13 — the weekday only. The week's range is two rows
        // above and the day strip under it carries the numbers, so "Sunday 13
        // September" was the third statement of the same date — the duplication
        // that took the dates off the desktop day headers on 09-12.
        return formatLocaleDate(day.iso, { weekday: 'long' });
    });
    const focusedDayHumanCount = computed(() => {
        const n = props.entriesFor(focusedDayIso.value).length;
        if (n === 0) return 'No meals planned';
        return `${n} meal${n === 1 ? '' : 's'} planned`;
    });

    // Read the day straight off the ISO string: `new Date(iso)` parses a
    // date-only string as UTC midnight, so west of Greenwich the chip showed
    // yesterday's number (R-021; `weekDates.ts` documents the trap —
    // finalisation 02-R34).
    function dayOfMonth(iso: string): number {
        return Number(iso.slice(8, 10));
    }

    // `onListCount` / `weekStatusCaption` / `addToListLabel` lived here to feed
    // the collapsible consequences card. All three went with it on 2026-09-03;
    // what survived of that summary was the week-status banner, and the owner
    // deleted that too on 2026-09-12 as a restatement of the cards and the
    // rail. `MealPlanShoppingSummary` owns what's left.

    /**
     * The focused day as one section per meal slot.
     *
     * Every household slot appears, in the household's own order, whether or
     * not the day has anything in it — that is the "show all slots" half of the
     * owner's report, and it is also what makes the order deterministic
     * (`entriesFor` returns the server's order, which is save order).
     *
     * A slot the vocabulary no longer holds still shows if the day has entries
     * in it: deleting a slot deliberately doesn't cascade (see
     * `update_meal_plan.py`), so those meals are real and hiding them would
     * lose them. They can't be *added* to, though — the picker only offers live
     * slots — so those sections carry no Add.
     */
    const slotGroups = computed(() => {
        const entries = props.entriesFor(focusedDayIso.value);
        const known = new Set(props.slotNames);
        const legacy = [...new Set(
            entries.map((e) => e.slot).filter((slot) => !known.has(slot)),
        )];
        const past = props.isPastDay(focusedDayIso.value);
        return [
            ...props.slotNames.map((slot) => ({ slot, addable: true })),
            ...legacy.map((slot) => ({ slot, addable: false })),
        ]
            .map((group) => ({
                ...group,
                entries: keyedEntries(entries.filter((e) => e.slot === group.slot)),
            }))
            // A past day is read-only, so an empty slot on one is a heading
            // over nothing you can do anything about.
            .filter((group) => !past || group.entries.length > 0);
    });

    function goPrevWeek() {
        emit('goPrevWeek');
    }
    function goNextWeek() {
        emit('goNextWeek');
    }
</script>

<style scoped>
    .mobile-focus {
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
    }
    .mobile-focus__weeknav {
        display: flex;
        align-items: center;
        gap: 6px;
        justify-content: center;
    }
    .mobile-focus__weeknav-block {
        flex: 1 1 auto;
        min-width: 0;
        text-align: center;
    }
    /* `.planner-toolbar__range` / `.cal__month`'s voice. */
    .mobile-focus__weeknav-label {
        font-size: var(--font-size-md);
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }
    .mobile-focus__weeknav-meta {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: var(--space-2);
    }
    /* Equal halves, so neither week-filling action reads as the smaller
       option. They wrap rather than squeeze their labels below ~300px. */
    .mobile-focus__weekactions {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-2);
    }
    .mobile-focus__weekactions > * {
        flex: 1 1 10rem;
        min-width: 0;
    }
    .mobile-focus__day-strip {
        display: grid;
        grid-template-columns: repeat(7, minmax(0, 1fr));
        gap: var(--space-1);
    }
    .mobile-focus__day-chip {
        position: relative;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 1px;
        padding: 6px 4px;
        background: var(--surface-elevated);
        border: 1px solid var(--border-default);
        border-radius: 8px;
        color: var(--text-secondary);
        font-size: 0.7rem;
        cursor: pointer;
        transition: background var(--motion-fast) var(--motion-ease), border-color var(--motion-fast) var(--motion-ease);
        min-height: 44px;
    }
    .mobile-focus__day-chip:hover,
    .mobile-focus__day-chip:focus-visible {
        background: var(--surface-sunken);
        outline: none;
    }
    .mobile-focus__day-chip--past {
        opacity: 0.55;
    }
    .mobile-focus__day-chip--today {
        border-color: var(--brand-primary);
    }
    .mobile-focus__day-chip--focused {
        background: var(--brand-primary);
        color: var(--text-on-primary);
        border-color: var(--brand-primary);
    }
    /* On the focused chip the primary fill is the ground, so the status
       colours have to sit on it rather than under it. Only `planned` collides
       (it is the same green family); warning and muted stay legible. */
    .mobile-focus__day-chip--focused :deep(.mp-pips__pip--planned) {
        background: var(--text-on-primary);
    }
    .mobile-focus__day-chip--focused :deep(.mp-pips__more) {
        color: var(--text-on-primary);
    }
    .mobile-focus__day-chip-label {
        font-weight: 700;
    }
    .mobile-focus__day-chip-num {
        font-weight: 600;
        font-size: 0.85rem;
    }
    .mobile-focus__day-chip-pips {
        margin-top: 2px;
    }
    .mobile-focus__day-header {
        display: flex;
        align-items: center;
        padding: var(--space-1) 0;
    }
    .mobile-focus__today {
        letter-spacing: 0.06em;
        font-weight: 700;
    }
    .mobile-focus__entries {
        display: flex;
        flex-direction: column;
        gap: 14px;
    }
    .mobile-focus__slot {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }
    /* The heading is what the card's slot tag used to be, promoted: the owner
       couldn't read a 0.68rem uppercase chip as a grouping, and a grouping is
       what it was doing. Same eyebrow language as the rest of the app — small,
       secondary ink, letter-spaced — but on its own line where it can be
       scanned down the day. */
    .mobile-focus__slot-head {
        display: flex;
        align-items: center;
        gap: 6px;
        margin: 0;
        padding: 0 2px;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: var(--text-secondary);
    }
    .mobile-focus__slot-count {
        font-weight: 600;
        color: var(--text-muted);
        font-variant-numeric: tabular-nums;
    }
    .mobile-focus__add {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 10px 12px;
        font-size: 0.85rem;
        font-weight: 500;
        color: var(--text-secondary);
        background: transparent;
        border: 1px dashed var(--border-default);
        border-radius: var(--radius-pill);
        cursor: pointer;
        transition: background var(--motion-fast) var(--motion-ease), color var(--motion-fast) var(--motion-ease), border-color var(--motion-fast) var(--motion-ease);
        min-height: 44px;
    }
    .mobile-focus__add:hover,
    .mobile-focus__add:focus-visible {
        color: var(--brand-primary);
        border-color: var(--brand-primary);
        background: var(--surface-sunken);
    }
    .mobile-focus__add:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
</style>
