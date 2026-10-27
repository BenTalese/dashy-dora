<template>
    <q-card
        bordered
        class="day-card"
        :class="{ 'day-card--past': isPast, 'day-card--has-target': hasTargetedSlot }"
    >
        <!-- The header is a real <button> only when there is something to
             collapse, so a normal day card keeps a plain, non-interactive
             header rather than announcing itself as a control that does
             nothing (D-016 / A6). -->
        <component
            :is="collapsible ? 'button' : 'div'"
            :type="collapsible ? 'button' : undefined"
            class="dora-bg-sunken q-py-xs q-px-md row items-center day-card__head"
            :class="{ 'day-card__head--toggle': collapsible }"
            :aria-expanded="collapsible ? String(!collapsed) : undefined"
            :aria-label="collapsible
                ? `${collapsed ? 'Show' : 'Hide'} ${day.label} ${formatDate(day.iso)}`
                : undefined"
            @click="collapsible && (collapsed = !collapsed)"
        >
            <q-icon
                v-if="collapsible"
                :name="collapsed ? ICONS.chevron_right : ICONS.expand_more"
                size="18px"
                class="q-mr-xs dora-text-muted"
            />
            <!-- Owner 2026-09-12 — the day name wears the auto builder's day-
                 divider voice (uppercase, tracked, secondary ink), so the two
                 places the app separates days speak the same way. It is a
                 heading over a column of meals, not a row of content, and the
                 old bold body text read as the first of them. -->
            <!-- Owner 2026-09-12 — the date is gone: *"just show the day text,
                 we know which dates by looking at the top of the page."* The
                 toolbar names the week, and seven dates repeated under it were
                 the widest thing in a narrow column. Still in the header's
                 `aria-label` and in every tooltip that names a day, where there
                 is no week banner to have just read. -->
            <div class="day-card__name">{{ day.label }}</div>
            <!-- Owner 2026-09-12 — caps. It is a marker, not a word in a
                 sentence, and it sits beside a day name that is now uppercase
                 itself. -->
            <q-badge v-if="isToday" color="primary" class="q-ml-sm day-card__today" label="TODAY" />
            <!-- Collapsed, the header IS the card, so it has to say what the
                 day held — otherwise a folded past week reads as an empty one. -->
            <div v-if="collapsed" class="day-card__summary text-caption dora-text-muted">
                {{ collapsedSummary }}
            </div>
            <q-space />
            <!-- Owner 2026-09-13 — the per-day kcal cell is gone, following the
                 per-day cost rollup out on 09-12 and for the same reason: it is
                 a total you don't read, on a header you scan. Calories are
                 decided on the recipe and shown on the meal, and the phone's
                 day header never had this cell — so removing it also closes a
                 desktop/mobile gap rather than opening one (FU-637's figure
                 survives in the DTO and on the recipe surfaces). -->
        </component>
        <q-card-section v-if="!collapsed" class="q-pa-sm column q-gutter-xs">
            <!-- R-Phase 6 §4.6 — slot row is a real <button> so it's
                focusable, announced, and Enter/Space-activated. Past days
                render a plain region (no action). -->
            <component
                :is="isPast ? 'div' : 'button'"
                v-for="slot in visibleSlots"
                :key="slot"
                :type="isPast ? undefined : 'button'"
                :aria-label="isPast ? undefined : `Add a meal to ${day.label} ${formatDate(day.iso)} ${slot}`"
                class="slot-row"
                :class="{
                    'slot-row--target': isTargetedSlot(slot),
                    'slot-row--clickable': !isPast,
                }"
                @click="!isPast && emit('selectSlot', slot)"
            >
                <div class="slot-row__label">{{ slot }}</div>
                <div class="slot-row__entries">
                    <MealPlanEntryChip
                        v-for="{ key, entry } in keyedEntries(slotEntries(slot))"
                        :key="key"
                        :entry="entry"
                        :show-slot="false"
                        :shortfall="entry.needs_cooking"
                        :highlight="hoveredRecipeIds.has(entry.recipe_id)"
                        @click.stop
                        v-on="entryListeners(entry)"
                    />
                    <span
                        v-if="!slotEntries(slot).length && !isPast"
                        class="slot-row__hint"
                    >
                        {{ isTargetedSlot(slot) ? '← pick a recipe' : 'tap to add' }}
                    </span>
                </div>
            </component>

            <!-- Off-vocabulary historical slots land here (C-2.A). -->
            <div v-if="otherEntries.length" class="slot-row">
                <div class="slot-row__label">Other</div>
                <div class="slot-row__entries">
                    <MealPlanEntryChip
                        v-for="{ key, entry } in keyedEntries(otherEntries)"
                        :key="key"
                        :entry="entry"
                        :show-slot="true"
                        :shortfall="entry.needs_cooking"
                        :highlight="hoveredRecipeIds.has(entry.recipe_id)"
                        @click.stop
                        v-on="entryListeners(entry)"
                    />
                </div>
            </div>

            <!-- Calm per-day add affordance — replaces the 5× italic
                "tap to add" sprawl when showAllSlots is false. Empty-state
                pattern, distinct from R-029. -->
            <button
                v-if="!isPast && unusedSlots.length"
                type="button"
                class="add-meal-button"
                :class="{ 'add-meal-button--empty': !visibleSlots.length && !otherEntries.length }"
            >
                <q-icon :name="ICONS.add" size="14px" class="q-mr-xs" />
                <span>{{ addButtonLabel }}</span>
                <!-- Arming a slot from this menu is a focus HAND-OFF, not a
                     round trip: §4.6 requires focus to land in the rail's
                     search so the armed slot can be answered from the keyboard.
                     QMenu fights that twice on close, and both were measured in
                     the browser:
                       1. it returns focus to whatever opened it — hence
                          `no-refocus`; without it focus snapped back to this
                          button and stayed there 1500ms after arming;
                       2. its teardown blurs the active element, so emitting on
                          click focused the rail and then lost it to BODY a beat
                          later.
                     So the selection is emitted on `@hide`, once the menu is
                     fully gone and nothing further will touch focus. -->
                <q-menu
                    anchor="top right"
                    self="bottom right"
                    auto-close
                    no-refocus
                    @hide="flushPendingSlot"
                >
                    <q-list dense style="min-width: 140px">
                        <q-item
                            v-for="slot in unusedSlots"
                            :key="slot"
                            clickable
                            @click="pendingSlot = slot"
                        >
                            <q-item-section>{{ slot }}</q-item-section>
                        </q-item>
                    </q-list>
                </q-menu>
            </button>
        </q-card-section>
    </q-card>
</template>

<script lang="ts" setup>
    import MealPlanEntryChip from 'components/MealPlanEntryChip.vue';
    // Content-identity keys, not `meal_plan_entry_id` — see the helper's note:
    // every save mints new entry ids, which remounted the chip mid-edit and
    // took its open menu with it.
    import { keyedEntries } from 'src/helpers/mealPlanEntryKey';
    import { ICONS } from 'src/style/icons';
    import type { MealPlanEntry } from 'src/models/mealPlan';
    import type { WeekDay } from 'src/composables/useMealPlanner';
    import { computed, ref, watch } from 'vue';

    const props = defineProps<{
        day: WeekDay;
        isPast: boolean;
        isToday: boolean;
        slotNames: readonly string[];
        slotEntries: (slot: string) => MealPlanEntry[];
        otherEntries: MealPlanEntry[];
        isTargetedSlot: (slot: string) => boolean;
        hoveredRecipeIds: Set<string>;
        formatDate: (iso: string) => string;
        showAllSlots: boolean;
        /**
         * Start folded (owner 2026-09-01: "past days should be collapsed by
         * default *if today is within the displayed week*, because we want to
         * see the whole past week in one go").
         *
         * The condition is the host's to compute — it is a fact about the WEEK
         * (does it contain today), not about this day — and it is deliberately
         * not just `isPast`: on a week you have navigated back to, every card
         * is a past card, and folding all seven would leave a screen of headers
         * saying nothing. Collapsing is only useful when past days are the
         * minority sharing the view with days you can still act on.
         */
        collapsedByDefault?: boolean;
    }>();

    /* User-owned once the user touches it; re-seeded whenever the host's
       default changes — which is what a week change looks like from in here,
       since `day.iso` and `collapsedByDefault` move together. Without the
       watch, paging from this week to last week would keep Monday folded
       because *this* Monday was in the past. */
    const collapsed = ref(props.collapsedByDefault ?? false);
    watch(
        () => [props.day.iso, props.collapsedByDefault] as const,
        () => { collapsed.value = props.collapsedByDefault ?? false; },
    );
    /** Only a card that starts folded offers the control: an upcoming day has
     *  nothing worth hiding and gains a stray chevron if it does. */
    const collapsible = computed(() => props.collapsedByDefault === true);

    const collapsedSummary = computed(() => {
        const all = [
            ...props.slotNames.flatMap((slot) => props.slotEntries(slot)),
            ...props.otherEntries,
        ];
        if (!all.length) return 'nothing planned';
        // Owner 2026-09-12 — a count, not the names. Folding is only offered
        // for days already gone (`collapsedByDefault`), and reading back what
        // you ate on Monday is not what the fold is for: it exists to get the
        // past out of the way. The names were the 2026-09-0x reading of the
        // same line, when the fold was thought of as a summary.
        return `${all.length} meal${all.length === 1 ? '' : 's'}`;
    });

    /* The slot picked from the add-meal menu, held until the menu has finished
       hiding. See the `@hide` comment in the template: emitting on click races
       QMenu's own focus teardown, which would undo the rail's focus hand-off. */
    const pendingSlot = ref<string | null>(null);
    function flushPendingSlot() {
        const slot = pendingSlot.value;
        pendingSlot.value = null;
        if (slot) emit('selectSlot', slot);
    }

    /* §4.6 — when one of this day's slots is armed, the whole card takes an
       accent border. Without it the only marker is a single slot row inside one
       of seven stacked cards, so finding your own target means scanning slot by
       slot. */
    const hasTargetedSlot = computed(
        () => props.slotNames.some((slot) => props.isTargetedSlot(slot)),
    );

    const emit = defineEmits<{
        (e: 'selectSlot', slot: string): void;
        (e: 'entryView', recipeId: string): void;
        (e: 'entryCook', entry: MealPlanEntry): void;
        (e: 'entryRemove', entry: MealPlanEntry): void;
        (e: 'entryAdjust', entry: MealPlanEntry, delta: number): void;
        (e: 'entryLink', entry: MealPlanEntry): void;
        (e: 'entryUnlink', entry: MealPlanEntry): void;
        (e: 'entryLighter', entry: MealPlanEntry): void;
        (e: 'entryFresh', entry: MealPlanEntry): void;
    }>();

    /** The chip's menu, re-raised with the entry it belongs to. */
    function entryListeners(entry: MealPlanEntry) {
        return {
            view: () => emit('entryView', entry.recipe_id),
            cook: () => emit('entryCook', entry),
            remove: () => emit('entryRemove', entry),
            adjust: (delta: number) => emit('entryAdjust', entry, delta),
            lighter: () => emit('entryLighter', entry),
            link: () => emit('entryLink', entry),
            unlink: () => emit('entryUnlink', entry),
            fresh: () => emit('entryFresh', entry),
        };
    }

    // Q2 — used slots default. When showAllSlots is on, every household slot
    // renders (legacy behaviour, "tap to add" hint per slot). When off, only
    // slots with entries render; an explicit "+ add a meal" button opens a
    // slot-picker menu for the unused ones.
    /* An armed slot is ALWAYS visible, even when empty and even with
       "show all slots" off. §4.6 requires the destination to be named at both
       ends — the rail banner and the slot itself — because at 1280px+ they are
       far apart and naming both is the reliable version of drawing a connector.
       Without this the week's only marker was the card's accent border, so
       arming "Breakfast" from the add-meal menu highlighted the day but never
       said which slot; the target row simply didn't exist to be highlighted
       (measured in the browser — the `← pick a recipe` hint rendered nowhere). */
    const visibleSlots = computed(() => {
        if (props.showAllSlots) return props.slotNames;
        return props.slotNames.filter(
            (s) => props.slotEntries(s).length > 0 || props.isTargetedSlot(s),
        );
    });
    const unusedSlots = computed(() => props.slotNames.filter((s) => !props.slotEntries(s).length));

    const addButtonLabel = computed(() => {
        if (!visibleSlots.value.length && !props.otherEntries.length) return `Plan ${props.day.label}`;
        return 'Add a meal';
    });
</script>

<style scoped>
    /* Owner feedback 2026-09-03 — *"a bit more margin between the days would
       be good on the middle section of the meal planner page. A tad, not a
       lot."* Was Quasar's `q-mb-sm` (8px); `--space-3` is 12px, the next step
       on the spacing scale, and it lives here on the component rather than as
       a utility class at the call site so the gap travels with the card. */
    .day-card {
        margin-bottom: var(--space-3);
    }
    .day-card--past {
        opacity: 0.6;
    }
    /* Reset the native button so a collapsible header still paints as the same
       sunken strip as a plain one — the two sit side by side in one week. */
    .day-card__head {
        width: 100%;
        border: 0;
        font: inherit;
        color: inherit;
        text-align: left;
    }
    .day-card__name {
        font-size: var(--font-size-sm);
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-secondary);
    }
    .day-card__today {
        letter-spacing: 0.06em;
        font-weight: 700;
    }
    .day-card__head--toggle {
        cursor: pointer;
    }
    .day-card__head--toggle:focus-visible {
        outline: 2px solid var(--brand-primary);
        outline-offset: -2px;
    }
    .day-card__summary {
        margin-left: var(--space-2);
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    /* Reset native button affordances — slot rows are buttons for
        accessibility (R-Phase 6 §4.6) but render as plain rows. */
    .slot-row {
        display: flex;
        align-items: flex-start;
        gap: var(--space-2);
        padding: 4px 6px;
        border-radius: var(--radius-md);
        transition: background var(--motion-fast) var(--motion-ease), outline var(--motion-fast) var(--motion-ease);
        background: transparent;
        border: 0;
        text-align: left;
        font: inherit;
        color: inherit;
        width: 100%;
        min-height: 28px;
    }
    .slot-row--clickable {
        cursor: pointer;
    }
    .slot-row--clickable:hover,
    .slot-row--clickable:focus-visible {
        background: var(--surface-sunken);
        outline: none;
    }
    .slot-row--clickable:focus-visible {
        outline: 2px solid var(--brand-primary);
        outline-offset: 2px;
    }
    /* §4.6 — the armed slot is a FILLED accent surface with an inset accent
       bar. It used to be `outline: 2px dashed` over a sunken fill, which reads
       as an empty DROP ZONE — and with drag-and-drop retired (D1) a drop-zone
       idiom is not merely dated, it is actively misleading: there is nothing to
       drop any more. This says "this is the destination", not "drop here". */
    .slot-row--target {
        background: color-mix(in srgb, var(--brand-primary) 14%, var(--surface-component));
        box-shadow: inset 2px 0 0 0 var(--brand-primary);
    }
    .day-card--has-target {
        border-color: var(--brand-primary);
    }
    /* Owner 2026-09-12 — part of the middle pane's type bump; 0.78rem beside a
       1rem meal name read as a different app. */
    .slot-row__label {
        flex: 0 0 5.5rem;
        font-size: var(--font-size-sm);
        font-weight: 600;
        padding-top: 6px;
        color: var(--text-secondary);
    }
    .slot-row__entries {
        flex: 1 1 auto;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: var(--space-1);
    }
    .slot-row__hint {
        font-size: 0.72rem;
        color: var(--text-muted);
        font-style: italic;
    }
    .add-meal-button {
        display: inline-flex;
        align-items: center;
        align-self: flex-start;
        margin-top: var(--space-1);
        padding: 4px 10px;
        font-size: 0.78rem;
        font-weight: 500;
        color: var(--text-secondary);
        background: transparent;
        border: 1px dashed var(--border-default);
        border-radius: var(--radius-pill);
        cursor: pointer;
        transition: background var(--motion-fast) var(--motion-ease), color var(--motion-fast) var(--motion-ease), border-color var(--motion-fast) var(--motion-ease);
        min-height: 28px;
    }
    .add-meal-button:hover,
    .add-meal-button:focus-visible {
        color: var(--brand-primary);
        border-color: var(--brand-primary);
        background: var(--surface-sunken);
    }
    .add-meal-button:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    /* Empty-day variant — a calm full-width affordance, not a tiny chip. */
    .add-meal-button--empty {
        align-self: stretch;
        justify-content: center;
        padding: 10px 12px;
        font-size: 0.82rem;
        min-height: 36px;
    }
</style>
