import { storeToRefs } from 'pinia';
import { useQuasar } from 'quasar';
import { useListState } from 'src/composables/useListState';
import { formatDate as formatLocaleDate } from 'src/composables/useDateFormat';
import { useMealPlanExport } from 'src/composables/useMealPlanExport';
import { useReducedMotion } from 'src/composables/useReducedMotion';
import { useBatchEnabled } from 'src/composables/useBatchEnabled';
import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
import { usePlannedDemand } from 'src/composables/usePlannedDemand';
import { invalidateReconcileQueue } from 'src/composables/useReconcileQueue';
import { useStockStatus } from 'src/composables/useStockStatus';
import { isDateOnly, isoDate as toIso, localTodayIso, mondayOf, shiftDays } from 'src/helpers/weekDates';
import type {
    MealPlan, MealPlanEntry, MealPlanIngredient,
    MealPlanSuggestion, UnlinkedIngredient,
} from 'src/models/mealPlan';
import type { AddToListConfirm } from 'src/components/shoppingList/addToListTypes';
import { rowsFromMealPlanIngredients, unlinkedFromMealPlan } from 'src/helpers/addToListRows';
import { useShoppingListActions } from 'src/composables/useShoppingListActions';
import { cartStateFor, type Membership } from 'src/models/shoppingList';
import BudgetApiService, { type BudgetStatus } from 'src/services/api/budgetApiService';
import type { MealPlanEntryCommand } from 'src/services/api/mealPlanApiService';
import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
import { NormalisedApiError } from 'src/services/api/axiosHttpClient';
import { useMealPlanStore } from 'src/stores/mealPlanStore';
import { useMealPlanTemplateStore } from 'src/stores/mealPlanTemplateStore';
import { useMealPlanTemplateSetStore } from 'src/stores/mealPlanTemplateSetStore';
import { useMealSlotStore } from 'src/stores/mealSlotStore';
import { useRecipeStore } from 'src/stores/recipeStore';
import { useShoppingListStore } from 'src/stores/shoppingListStore';
import { useStockItemStore } from 'src/stores/stockItemStore';
import { useStockLevelStore } from 'src/stores/stockLevelStore';
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useConfirm } from 'src/composables/useConfirm';

/* The recipe trays (and their `RecipeTray` type) were retired on 2026-08-30
   with Unit 2 of BRIEF_MEAL_PLANNER_RAIL_AND_SHELL: the rail's four collapsible
   accordions became one flat list plus a row of filter chips, so there is no
   grouping left to build. Their replacement is `helpers/recipeRailFilters.ts`,
   which is a set of independent predicates rather than a claiming/capping
   grouper — see that file for why FU-578 #47's dedupe is superseded and not
   regressed. */

export type WeekDay = { label: string; iso: string };

/**
 * R-001 / R-003 — the meal planner page's shared core. Both Direction A (the
 * existing carousel) and the upcoming Direction B (week board) consume this so
 * mutation logic, week navigation, ingredient loading, list generation, and
 * template flows live in one place.
 */
export function useMealPlanner() {
    const $q = useQuasar();
    const { confirm } = useConfirm();
    const router = useRouter();
    const route = useRoute();
    const planExport = useMealPlanExport();
    // The household cook-style. A "fresh" household has no cook pool, so it
    // has no cook batches either and every batch branch below is inert.
    const { batchEnabled } = useBatchEnabled();
    const { moneyEnabled } = useMoneyEnabled();
    const budgetApi = new BudgetApiService();

    const mealPlanStore = useMealPlanStore();
    const mealPlanTemplateStore = useMealPlanTemplateStore();
    const mealPlanTemplateSetStore = useMealPlanTemplateSetStore();
    const mealSlotStore = useMealSlotStore();
    const recipeStore = useRecipeStore();
    const stockItemStore = useStockItemStore();
    const stockLevelStore = useStockLevelStore();
    const shoppingListStore = useShoppingListStore();
    const { addStockItemsToList } = useShoppingListActions();

    const { mealPlans, today } = storeToRefs(mealPlanStore);
    const { slotNamesOrDefault } = storeToRefs(mealSlotStore);
    const { templates } = storeToRefs(mealPlanTemplateStore);
    const { sets } = storeToRefs(mealPlanTemplateSetStore);
    const { recipes } = storeToRefs(recipeStore);

    const ingredients = ref<MealPlanIngredient[]>([]);
    // FU-505's report, now that the picker (not the auto-generate endpoint)
    // does the adding — ingredients with no linked stock item can't become
    // lines, and the dialog names them rather than dropping them silently.
    const unlinkedIngredients = ref<UnlinkedIngredient[]>([]);
    /**
     * Owner 2026-09-12 — *"no indication of how much budget remains."* The
     * week's own cost has been on this page since 09-05; what it was missing is
     * the thing that makes a number mean something. Loaded once per page (not
     * per card — the summary renders at both breakpoints) and only when money
     * features are on, so an install without them makes no call.
     *
     * This is the household's period budget, the same figure the shopping
     * lists and the auto builder's cap work against (R-003 — one budget
     * engine, `/budget/status`), NOT a per-week allowance.
     */
    const budgetStatus = ref<BudgetStatus | null>(null);
    const ingredientsLoading = ref(false);
    const generating = ref(false);
    // FU-354 — the picker's search string survives navigate-away-and-back
    // within the session (A8 §3 nav-state policy). Full reload /
    // sign-out (via `clearAllListState` from FU-355) resets it to empty.
    // The composable's other refs (ingredients, generating, ...) reset
    // on remount — they're derived / lifecycle state, not user-picked
    // filters, so they don't want persistence.
    const { recipeSearch } = useListState('meal-plans-overview', () => ({
        recipeSearch: ref(''),
    }));
    // R-Phase 6 §9-I — initial-load flag. The page mounts ~10 parallel store
    // hydrations; until they finish we render skeleton screens so the user
    // sees the grid/list shape instantly (Doherty) instead of a popcorn of
    // cards arriving.
    const isInitialLoading = ref(true);

    // R-021 carve-out — server-owned `today` (household timezone) is the
    // authoritative boundary; `localTodayIso()` is a display-only pre-load
    // fallback that flips the moment `today.value` arrives from the store.
    const currentDayIso = computed(() => today.value ?? localTodayIso());
    function isPastDay(iso: string): boolean {
        return iso < currentDayIso.value;
    }
    // R-003 — the single predicate for "entries the client may resend on a
    // plan PATCH": forward-looking AND not yet consumed. Past + consumed
    // entries are immutable history the server preserves on its own (FU-595);
    // the client must NOT resend a past entry — doing so trips the server's
    // past-date guard and used to freeze the whole week. Every command builder
    // below (add / adjust servings / remove) filters through this.
    function isForwardEditable(entry: MealPlanEntry): boolean {
        return !entry.consumed_at && !isPastDay(toIso(entry.scheduled_for));
    }

    // ── Focused week (the carousel's source of truth) ──────────────────────
    const focusedMonday = ref<string>(mondayOf(localTodayIso()));
    const focusedPlan = computed<MealPlan | null>(
        () => mealPlans.value.find((p) => mondayOf(p.start_date) === focusedMonday.value) ?? null,
    );
    // Weekday names come from the household locale, like the dashboard strip.
    const weekDays = computed<WeekDay[]>(() =>
        Array.from({ length: 7 }, (_, i) => {
            const iso = shiftDays(focusedMonday.value, i);
            return { label: formatLocaleDate(iso, { weekday: 'short' }), iso };
        }),
    );
    const weekRangeLabel = computed(
        () => `${formatDate(focusedMonday.value)} – ${formatDate(shiftDays(focusedMonday.value, 6))}`,
    );
    // BRIEF_MEAL_PLANNER_RAIL_AND_SHELL §3.2 — the toolbar carries the range as
    // its only week label (D4: the page has no title, and F40 killed the
    // "Week of…" prefix), so the range needs a relative anchor or "13 Oct –
    // 19 Oct" never says *which* week you're looking at.
    //
    // Both sides parse as UTC midnight, so the difference is always an exact
    // multiple of seven days and no DST boundary can round this the wrong way.
    const weekRelativeLabel = computed(() => {
        const MS_PER_WEEK = 7 * 24 * 60 * 60 * 1000;
        const weeks = Math.round(
            (Date.parse(focusedMonday.value) - Date.parse(mondayOf(localTodayIso()))) / MS_PER_WEEK,
        );
        if (weeks === 0) return 'This week';
        if (weeks === 1) return 'Next week';
        if (weeks === -1) return 'Last week';
        return weeks > 0 ? `In ${weeks} weeks` : `${-weeks} weeks ago`;
    });

    // ── Slots (household vocabulary, C-2.A) ────────────────────────────────
    const slotNames = slotNamesOrDefault;
    const slotNameSet = computed(() => new Set(slotNames.value));

    function dayEntries(dayIso: string): MealPlanEntry[] {
        return (focusedPlan.value?.entries ?? []).filter((e) => toIso(e.scheduled_for) === dayIso);
    }
    function slotEntries(dayIso: string, slot: string): MealPlanEntry[] {
        return dayEntries(dayIso).filter((e) => e.slot === slot);
    }
    function otherSlotEntries(dayIso: string): MealPlanEntry[] {
        return dayEntries(dayIso).filter((e) => !slotNameSet.value.has(e.slot));
    }

    // ── "Dora suggests" (§4.4) ─────────────────────────────────────────────
    // Replaces the recipe trays, which the rail's filter chips retired on
    // 2026-08-30. Fetched **lazily** — only when the user actually selects the
    // chip — because it is a ranking over the whole cookbook and most visits to
    // the planner never ask for it.
    //
    // Cached per focused week: the ranking excludes recipes already planned in
    // that week, so it is only valid for the week it was asked about. Changing
    // week invalidates it rather than showing last week's answer.
    const suggestions = ref<MealPlanSuggestion[]>([]);
    const suggestionsLoading = ref(false);
    const suggestionsWeek = ref<string | null>(null);

    // The week whose ranking is in flight — the guard is per week, so a week
    // change mid-request starts the new week's fetch instead of being refused.
    let suggestionsInflightWeek: string | null = null;

    async function loadSuggestions() {
        const week = focusedMonday.value;
        if (suggestionsInflightWeek === week) return;
        if (suggestionsWeek.value === week && suggestions.value.length) return;
        suggestionsInflightWeek = week;
        suggestionsLoading.value = true;
        try {
            const ranked = await mealPlanStore.getWeekSuggestionsAsync(week);
            // The user moved on to another week — this answer is not theirs.
            if (focusedMonday.value !== week) return;
            suggestions.value = ranked;
            suggestionsWeek.value = week;
        } catch {
            // A failed ranking is not worth a toast: the chip falls back to the
            // plain list, which is a usable rail. Staying silent beats an error
            // for something the user did not explicitly ask to be told about.
            if (focusedMonday.value !== week) return;
            suggestions.value = [];
            suggestionsWeek.value = null;
        } finally {
            if (suggestionsInflightWeek === week) {
                suggestionsInflightWeek = null;
                suggestionsLoading.value = false;
            }
        }
    }

    // ── Tap-to-add: focus a slot, then pick a recipe ───────────────────────
    const focusedTarget = ref<{ dayIso: string; slot: string } | null>(null);
    function isTargeted(dayIso: string, slot: string): boolean {
        return focusedTarget.value?.dayIso === dayIso && focusedTarget.value?.slot === slot;
    }
    function selectSlot(dayIso: string, slot: string) {
        if (isPastDay(dayIso)) {
            $q.notify({ type: 'warning', message: 'Past days are read-only.' });
            return;
        }
        focusedTarget.value = isTargeted(dayIso, slot) ? null : { dayIso, slot };
    }
    async function pickRecipe(recipeId: string) {
        // No armed slot, no action — and no toast. It used to raise an info
        // toast reading "Tap a day's meal slot first, then a recipe", which
        // fired on the very first thing a new arrival does (owner 2026-09-01:
        // "I click a recipe straight away and get a blank blue info toast.
        // Nothing should happen if no meal slot is selected"). It was also
        // scolding the user for the app's own default: the rail opens showing
        // a browsable list with nothing armed, so clicking a row there is a
        // reasonable thing to try. The instruction it carried is already on
        // screen permanently — every unfilled slot row says "tap to add" — so
        // the toast added nothing but a modal-feeling interruption.
        if (!focusedTarget.value) return;
        await addEntry(focusedTarget.value.dayIso, focusedTarget.value.slot, recipeId);
    }
    function clearFocusedTarget() {
        focusedTarget.value = null;
    }

    // ── Drag-to-add: RETIRED 2026-08-29 (BRIEF_MEAL_PLANNER_RAIL_AND_SHELL D1)
    //
    // `dragAllowed` / `draggingRecipeId` / `onRecipePointerDown` / `onDragStart`
    // / `onDragEnd` / `onDropOnSlot` all lived here. Unit 1 gives the week pane
    // its own scroll container, and the planner's drag was native HTML5 with no
    // edge auto-scroll anywhere in the app — so a drag toward a day below the
    // fold would have silently stopped working rather than scrolling to it.
    // It was also mouse-only by construction (`pointerType === 'mouse'`) and
    // carried its payload on a module ref rather than `dataTransfer`, so a slot
    // accepted any drag and merely early-returned. F9 asked for drag *and* tap;
    // the owner revised that on 2026-08-29 — tap-to-target is the one way to
    // place a recipe. F47/F48 were answered by the servings stepper, not drag.
    //
    // Do not reinstate without building edge auto-scroll first; `useDragDropList`
    // is the reorderable-list editor and is a different job.

    // ── Entry mutations ────────────────────────────────────────────────────
    // PROPOSAL_MEAL_PLANS_PART_2 — map a saved entry to a write command, carrying
    // its `cook_batch_id` back as the transient `cook_key` so a cook batch (one
    // cook, several days) survives every edit. Standalone entries have no key.
    function toCommand(e: MealPlanEntry): MealPlanEntryCommand {
        return {
            meal_plan_entry_id: e.meal_plan_entry_id,
            recipe_id: e.recipe_id,
            scheduled_for: toIso(e.scheduled_for),
            servings: e.servings,
            slot: e.slot,
            ...(e.cook_batch_id ? { cook_key: e.cook_batch_id } : {}),
            ...(e.cook_fresh ? { cook_fresh: true } : {}),
        };
    }

    function planEntryCommands(plan: MealPlan): MealPlanEntryCommand[] {
        return plan.entries.filter(isForwardEditable).map(toCommand);
    }

    // R-003 — `/meal-plans/shortfall` is deliberately NOT refetched here any
    // more. Its recipe-level rows were the planner's only source of "what still
    // needs cooking", and that reading is now per-entry and rides on the plan
    // itself (`MealPlanEntry.needs_cooking`), which `updateMealPlanAsync`
    // reloads. Keeping the second fetch would leave two answers to one question
    // in the client, which is how the highlight and the "N to cook" figure came
    // to disagree in the first place. The endpoint stays — the assistant's
    // `meals_shortfall` tool reads it, and it answers a genuinely different
    // question (how many SERVINGS short each recipe is).
    async function refreshAfterMutation() {
        // Planned demand and the cook-reconcile queue both derive from the
        // plan's entries.
        usePlannedDemand().invalidate();
        invalidateReconcileQueue();
        await Promise.all([
            loadIngredients(),
            recipeStore.getRecipesAsync(),
        ]);
    }

    // FU-595(b) — every plan mutation funnels through here or `addEntry`'s
    // create branch, and both toast on failure rather than letting a rejected
    // request escape to the page ErrorBoundary (a stray 400 used to blank the
    // whole planner). Returns whether the write succeeded so callers can gate
    // their success toast.
    function notifyPlanError(err: unknown) {
        $q.notify({
            type: 'negative',
            message: 'Could not update the plan.',
            caption: toastCaption(err),
        });
    }

    /**
     * Drop the `cook_key` from any group left with fewer than two days.
     *
     * The server refuses a one-day "batch" — *"A cook batch must cover at least
     * two days"* (`cook_batch_grouping.validate_cook_groups`) — and it is right
     * to: a single day is just a meal. But every edit path builds its command
     * list by mapping the plan's entries through `toCommand`, which carries
     * each `cook_batch_id` along, so removing one day of a two-day cook (or
     * stepping its servings to zero) resent a lone member and the whole PATCH
     * came back 400 as *"Could not update the plan."* — owner, 2026-09-03:
     * *"error updating the plan when trying to drop a multi-day cook below 0
     * servings"* and *"cannot remove a multi-day cook from the plan either"*.
     *
     * One guard here rather than a fix in each caller (R-003): a batch that
     * loses its second day stops being a batch, whichever edit did it, and no
     * caller has to remember that rule.
     */
    function dissolveOrphanCookKeys(
        entries: MealPlanEntryCommand[],
    ): MealPlanEntryCommand[] {
        const size = new Map<string, number>();
        for (const cmd of entries) {
            if (cmd.cook_key) size.set(cmd.cook_key, (size.get(cmd.cook_key) ?? 0) + 1);
        }
        return entries.map((cmd) => {
            if (!cmd.cook_key || (size.get(cmd.cook_key) ?? 0) >= 2) return cmd;
            const { cook_key: _dropped, ...rest } = cmd;
            return rest;
        });
    }

    // FU-967 — every save names the revision of the copy it was built from.
    // If another device (or a tab left open since this morning) changed the
    // week in between, the server answers 409 instead of letting this copy
    // overwrite that edit. A queued edit is then re-applied once on top of the
    // reloaded week (see `queuePlanMutation`); anything else is told to retry.
    class PlanChangedElsewhere extends Error {}
    let replayingQueuedEdit = false;

    function notifyPlanChangedElsewhere() {
        $q.notify({
            type: 'warning',
            message: 'This week was changed on another device.',
            caption: "It's been reloaded. Try that again.",
        });
    }

    async function persistEntries(
        planId: string,
        entries: MealPlanEntryCommand[],
    ): Promise<boolean> {
        const revision = mealPlans.value.find((p) => p.meal_plan_id === planId)?.revision;
        // The planner's edits are explicit, so set the clear flag when an
        // action empties the future-entries list. The backend treats an
        // unflagged [] as a probable bug and refuses.
        try {
            await mealPlanStore.updateMealPlanAsync({
                meal_plan_id: planId,
                entries: dissolveOrphanCookKeys(entries),
                ...(entries.length === 0 ? { confirm_clear_entries: true } : {}),
                ...(revision ? { expected_revision: revision } : {}),
            });
            await refreshAfterMutation();
            return true;
        } catch (err) {
            if (err instanceof NormalisedApiError && err.status === 409) {
                try {
                    await mealPlanStore.getMealPlansAsync();
                    await refreshAfterMutation();
                } catch (reloadErr) {
                    notifyPlanError(reloadErr);
                    return false;
                }
                if (replayingQueuedEdit) throw new PlanChangedElsewhere();
                notifyPlanChangedElsewhere();
                return false;
            }
            notifyPlanError(err);
            return false;
        }
    }

    // Plan mutations rebuild the whole entry list from `focusedPlan`, so two
    // in flight at once both start from the same snapshot and the later write
    // drops the earlier one (rapid ± taps lost a serving). Run them one after
    // another, each building from the plan the previous one refreshed.
    //
    // Each step rebuilds from the current plan, which is also what makes a
    // FU-967 conflict cheap to recover from: reload the week, run the step
    // again, and the one edit lands on top of the other device's.
    let planMutationChain: Promise<unknown> = Promise.resolve();
    function queuePlanMutation(fn: () => Promise<void>): Promise<void> {
        const step = async () => {
            replayingQueuedEdit = true;
            try {
                try {
                    await fn();
                } catch (err) {
                    if (!(err instanceof PlanChangedElsewhere)) throw err;
                    try {
                        await fn();
                    } catch (again) {
                        if (!(again instanceof PlanChangedElsewhere)) throw again;
                        notifyPlanChangedElsewhere();
                    }
                }
            } finally {
                replayingQueuedEdit = false;
            }
        };
        const run = planMutationChain.then(step, step);
        planMutationChain = run.catch(() => undefined);
        return run;
    }

    function addEntry(dayIso: string, slot: string, recipeId: string): Promise<void> {
        const week = focusedMonday.value;
        return queuePlanMutation(() => addEntryNow(week, dayIso, slot, recipeId));
    }

    async function addEntryNow(week: string, dayIso: string, slot: string, recipeId: string) {
        // Queued steps run later: a week change in between means this tap
        // belongs to a week no longer on screen, not to the one now focused.
        if (focusedMonday.value !== week) return;
        if (isPastDay(dayIso)) return;
        // Bridge until C-2.E: the first add to an unplanned week implicitly
        // creates the plan (auto-named) carrying that entry.
        if (!focusedPlan.value) {
            try {
                await mealPlanStore.createMealPlanAsync({
                    start_date: focusedMonday.value,
                    entries: [{ recipe_id: recipeId, scheduled_for: dayIso, servings: 1, slot }],
                });
                await refreshAfterMutation();
            } catch (err) {
                notifyPlanError(err);
                return;
            }
            $q.notify({ type: 'positive', message: 'Added to plan.' });
            return;
        }
        const plan = focusedPlan.value;
        const cmds = planEntryCommands(plan);
        const existing = cmds.find(
            (c) => c.recipe_id === recipeId && c.scheduled_for === dayIso && c.slot === slot,
        );
        if (existing) {
            existing.servings += 1; // same recipe + day + slot increments, not duplicates
        } else {
            cmds.push({ recipe_id: recipeId, scheduled_for: dayIso, servings: 1, slot });
        }
        if (await persistEntries(plan.meal_plan_id, cmds)) {
            $q.notify({ type: 'positive', message: 'Added to plan.' });
        }
    }

    function adjustEntryServings(entry: MealPlanEntry, delta: number): Promise<void> {
        const week = focusedMonday.value;
        return queuePlanMutation(() => adjustEntryServingsNow(week, entry.meal_plan_entry_id, delta));
    }

    async function adjustEntryServingsNow(week: string, entryId: string, delta: number) {
        if (focusedMonday.value !== week) return;
        const plan = focusedPlan.value;
        // Read the entry from the plan as it is NOW (an earlier queued step may
        // have changed its servings), not from the caller's snapshot.
        const entry = plan?.entries.find((e) => e.meal_plan_entry_id === entryId);
        if (!plan || !entry) return;
        const next = entry.servings + delta;
        // Stepping the last serving away means "take this meal off the plan",
        // so it goes through the removal path rather than dropping the row
        // here. That matters for a cook batch: removal is the code that knows
        // a cook and its leftovers travel together, and that asks first
        // (owner 2026-09-03 — dropping a multi-day cook below 0 servings used
        // to return a bare "Could not update the plan").
        if (next < 1) {
            await removeEntry(entry);
            return;
        }
        const cmds = plan.entries
            .filter(isForwardEditable)
            .map((e) => ({
                ...toCommand(e),
                servings: e.meal_plan_entry_id === entry.meal_plan_entry_id ? next : e.servings,
            }));
        await persistEntries(plan.meal_plan_id, cmds);
    }

    /**
     * Take a meal off the plan.
     *
     * A cook batch is one cook eaten over several days, so removing its **cook
     * day** takes the leftover days with it — they were only ever that cook's
     * output, and leaving them behind would show meals that nothing produces.
     * Because that touches days the user may not be looking at, it asks first.
     * Removing a *leftover* day is local: the cook still happens, one day
     * shorter, and `dissolveOrphanCookKeys` turns a batch of one back into a
     * plain meal.
     */
    async function removeEntry(entry: MealPlanEntry) {
        const plan = focusedPlan.value;
        if (!plan) return;

        const batchIds = new Set<string>([entry.meal_plan_entry_id]);
        if (batchEnabled.value && entry.cook_batch_id && entry.is_cook_day) {
            const members = plan.entries.filter(
                (e) => e.cook_batch_id === entry.cook_batch_id && isForwardEditable(e),
            );
            const leftovers = members.filter(
                (e) => e.meal_plan_entry_id !== entry.meal_plan_entry_id,
            );
            if (leftovers.length > 0) {
                const ok = await confirm({
                    title: 'Remove this cook?',
                    message: `${entry.recipe_name} is cooked once for `
                        + `${members.length} days. Removing the cook removes `
                        + `${leftovers.length === 1 ? 'its leftover day' : `its ${leftovers.length} leftover days`} too.`,
                    okLabel: 'Remove all',
                    destructive: true,
                });
                if (!ok) return;
                leftovers.forEach((e) => batchIds.add(e.meal_plan_entry_id));
            }
        }

        const remaining = plan.entries
            .filter((e) => !batchIds.has(e.meal_plan_entry_id) && isForwardEditable(e))
            .map(toCommand);
        await persistEntries(plan.meal_plan_id, remaining);
    }

    // ── PROPOSAL_MEAL_PLANS_PART_2 — cook batches (one cook, several days) ─────

    /** ISO days already part of `entry`'s cook batch (empty if standalone). */
    function cookBatchDays(entry: MealPlanEntry): string[] {
        const plan = focusedPlan.value;
        if (!plan || !entry.cook_batch_id) return [];
        return plan.entries
            .filter((e) => e.cook_batch_id === entry.cook_batch_id)
            .map((e) => toIso(e.scheduled_for));
    }

    /**
     * Redefine `entry`'s cook to span exactly `selectedDayIsos` (same recipe +
     * slot). >=2 days links them as one cook; one day leaves a plain meal.
     * Reuses an existing same-recipe+slot entry on a day, else adds one.
     * Preserves every OTHER batch on the plan.
     *
     * **A day dropped out of the cook loses its meal.** Owner, 2026-09-03:
     * *"changing cook days leaves behind a copy of that meal — planned Mon +
     * Tue, change to Mon + Wed, and Tue still has a copy showing as not
     * linked."* It did: the old code un-keyed every member of the batch and
     * then re-keyed only the picked days, so a dropped day kept its entry and
     * turned into an unlinked duplicate of the same meal. Un-ticking Tuesday in
     * a dialog titled "Change cook days" means "don't eat this on Tuesday", not
     * "cook it separately on Tuesday".
     *
     * `mode` is what keeps the other reading available, because the owner asked
     * for it in the same breath: *"a copy SHOULD be left if the separate cook
     * days option is used."* `'separate'` (the menu's "Separate this cook")
     * keeps every day's meal and only breaks the link between them.
     */
    async function setCookDays(
        entry: MealPlanEntry,
        selectedDayIsos: string[],
        mode: 'redefine' | 'separate' = 'redefine',
    ) {
        const plan = focusedPlan.value;
        if (!plan) return;
        const selected = new Set(selectedDayIsos.filter((iso) => !isPastDay(iso)));
        const oldKey = entry.cook_batch_id ?? undefined;
        const newKey = selected.size >= 2
            ? (globalThis.crypto?.randomUUID?.() ?? `cook-${entry.meal_plan_entry_id}`)
            : undefined;

        // Days this cook covers today but the new selection doesn't. On a
        // redefine their meals go; on a separate they stay as standalone meals.
        const droppedEntryIds = new Set(
            mode === 'redefine' && oldKey
                ? plan.entries
                    .filter((e) => e.cook_batch_id === oldKey
                        && isForwardEditable(e)
                        && !selected.has(toIso(e.scheduled_for)))
                    .map((e) => e.meal_plan_entry_id)
                : [],
        );

        // Start from the current forward entries, dropping this batch's old links
        // (we're redefining it) while keeping every other batch intact.
        const cmds: MealPlanEntryCommand[] = plan.entries
            .filter(isForwardEditable)
            .filter((e) => !droppedEntryIds.has(e.meal_plan_entry_id))
            .map((e) => {
                const cmd = toCommand(e);
                if (oldKey && cmd.cook_key === oldKey) delete cmd.cook_key;
                return cmd;
            });

        for (const iso of selected) {
            let cmd = cmds.find(
                (c) => c.recipe_id === entry.recipe_id && c.slot === entry.slot && c.scheduled_for === iso,
            );
            if (!cmd) {
                cmd = { recipe_id: entry.recipe_id, scheduled_for: iso, servings: entry.servings, slot: entry.slot };
                cmds.push(cmd);
            }
            if (newKey) {
                cmd.cook_key = newKey;
                // A cook batch IS the pool, so a member of one can't also be a
                // fresh cook (the server refuses the pair). This is reachable
                // without going through the fresh toggle: picking a day that
                // already holds a fresh meal of the same recipe + slot reuses
                // that entry rather than adding a second one.
                delete cmd.cook_fresh;
            } else {
                delete cmd.cook_key;
            }
        }
        await persistEntries(plan.meal_plan_id, cmds);
    }

    /** "Separate this cook" — every day the batch covered keeps its meal, they
     *  just stop being one cook. The counterpart to a `redefine`, and the case
     *  the owner explicitly wanted a copy left behind for. */
    async function separateCook(entry: MealPlanEntry) {
        const plan = focusedPlan.value;
        if (!plan) return;
        const days = entry.cook_batch_id
            ? plan.entries
                .filter((e) => e.cook_batch_id === entry.cook_batch_id)
                .map((e) => toIso(e.scheduled_for))
            : [toIso(entry.scheduled_for)];
        await setCookDays(entry, days, 'separate');
    }

    /**
     * Flip one meal between "cooked fresh on the day" and "on the pool".
     *
     * Owner, 2026-09-04: *"I batch cook and freeze lunches for the week, but
     * dinner with the parents on Saturday is fresh."* A fresh meal is not
     * allocated a cooked portion and doesn't add to what has to be batch-cooked
     * — the whole rule is server-owned (`planned_meals.allocate_pool`), so this
     * only writes the flag and re-reads the plan.
     *
     * The mark is meaningless outside a batch household (every meal is fresh
     * there) and impossible inside a cook batch, so both are refused rather
     * than silently written — the menu hides the control in both cases, but
     * this is the one that has to hold.
     */
    async function toggleCookFresh(entry: MealPlanEntry) {
        const plan = focusedPlan.value;
        if (!plan || !batchEnabled.value || entry.cook_batch_id) return;
        const next = !entry.cook_fresh;
        const cmds = plan.entries
            .filter(isForwardEditable)
            .map((e) => {
                const cmd = toCommand(e);
                if (e.meal_plan_entry_id !== entry.meal_plan_entry_id) return cmd;
                if (next) cmd.cook_fresh = true; else delete cmd.cook_fresh;
                return cmd;
            });
        if (await persistEntries(plan.meal_plan_id, cmds)) {
            $q.notify({
                type: 'positive',
                message: next
                    ? `${entry.recipe_name} is cooked fresh on the day.`
                    : `${entry.recipe_name} is back on the cooked pool.`,
            });
        }
    }

    // ── Week navigation (carousel) ─────────────────────────────────────────
    const slideDir = ref<'up' | 'down'>('down');
    const prefersReducedMotion = useReducedMotion();
    const weekTransition = computed(() =>
        prefersReducedMotion.value ? '' : slideDir.value === 'down' ? 'wk-down' : 'wk-up',
    );
    function goPrevWeek() {
        focusedMonday.value = shiftDays(focusedMonday.value, -7);
    }
    function goNextWeek() {
        focusedMonday.value = shiftDays(focusedMonday.value, 7);
    }
    // Any focus change — arrows, ↑/↓ keys, swipe, or a calendar-widget click —
    // sets the slide direction, clears the pending add-target, and tracks the
    // focused week in the URL (F28 refresh-resume).
    watch(focusedMonday, (next, prev) => {
        slideDir.value = next >= prev ? 'down' : 'up';
        focusedTarget.value = null;
        // The ranking excludes what's already planned in the week it was asked
        // about, so it does not survive a week change — drop it rather than
        // show last week's answer under this week's heading.
        suggestions.value = [];
        suggestionsWeek.value = null;
        // Owner 2026-09-12 — the param is `week`, not `monday`. The VALUE is
        // always a Monday (that is what a focused week is here), so naming the
        // key after the value described the encoding rather than the thing:
        // `?week=2026-09-14` says what you are looking at. Renamed outright
        // rather than accepting both — nothing is released, and a compat alias
        // for a URL nobody has bookmarked is the kind of shim that outlives its
        // reason.
        void router.replace({ query: { ...route.query, week: next } });
        void loadBudgetStatus();
    });
    function onKeydown(e: KeyboardEvent) {
        const t = e.target as HTMLElement | null;
        if (!t) return;

        // §4.6 — Esc cancels the armed slot. Checked BEFORE the editable/
        // interactive guards below, deliberately: the rail's auto-open moves
        // focus into the search input, so by the time you want to back out of
        // targeting your focus is nearly always in a text field — and the guard
        // that stops Arrow keys stealing focus would have swallowed every Esc.
        // Cancelling is also the one binding that is unambiguous everywhere:
        // there is nothing else on this page for Esc to mean.
        if (e.key === 'Escape' && focusedTarget.value) {
            e.preventDefault();
            clearFocusedTarget();
            return;
        }

        // R-Phase 6 §9-J — global Arrow nav must NOT steal focus from
        // the active control. Skip when typing in any editable region
        // (INPUT/TEXTAREA/contentEditable) OR when an interactive element
        // has focus (button/link/select/details/summary) — arrowing off a
        // slot button used to jump the week.
        if (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable) return;
        if (t.closest('button, a, select, [role="button"], [role="menuitem"], [role="tab"], [contenteditable="true"]')) return;
        if (e.key === 'ArrowUp') { e.preventDefault(); goPrevWeek(); }
        else if (e.key === 'ArrowDown') { e.preventDefault(); goNextWeek(); }
    }
    let touchStartY = 0;
    function onTouchStart(e: TouchEvent) { touchStartY = e.changedTouches[0]?.clientY ?? 0; }
    function onTouchEnd(e: TouchEvent) {
        const dy = (e.changedTouches[0]?.clientY ?? 0) - touchStartY;
        if (Math.abs(dy) < 60) return;
        if (dy > 0) goPrevWeek(); else goNextWeek();
    }

    // ── Stock status (shared composable, R-003) ────────────────────────────
    const { needsBuying, isMissing, isLowStock } = useStockStatus();
    const needToBuy = computed(() =>
        ingredients.value.filter((ing) => needsBuying(ing.stock_item_id)),
    );

    // Owner feedback 2026-08-27 — "the shopping list area should account for
    // the state of 'already on a list'. On mobile I can see 8 planned, 3 to
    // buy, and it stays like that even after I add those 3 to a shopping
    // list." `needToBuy` answers "what don't I have", which is a stock
    // question and doesn't move when you go shopping-*planning*. What the
    // week card is actually asking is "what's left for me to do", so the
    // headline count is now the outstanding half and the handled half is
    // named beneath it — the same shape the recipe page uses for its missing
    // ingredients.
    const listMembership = computed<Membership | null>(
        () => (shoppingListStore.membership as Membership | null) ?? null,
    );
    function isOnAList(stockItemId: string): boolean {
        return cartStateFor(stockItemId, listMembership.value) !== 'none';
    }
    const needToBuyOutstanding = computed(
        () => needToBuy.value.filter((ing) => !isOnAList(ing.stock_item_id)),
    );

    // ── Hover-to-highlight (F30, C-2.H) ────────────────────────────────────
    //
    // `listStatusLabel` lived here (F31) and shipped "not on a list" / "on
    // Weekly shop" as a caption under every right-rail ingredient. Deleted
    // 2026-09-01: the row's own cart button already carries that state as an
    // icon on the same line, so the caption restated it in words (owner:
    // "redundant, we can see that from the icon on the same row"). The level
    // chip it sat beside went the same way — `MealPlanIngredientRow` codes
    // level as the app's standard left-hand dot via `useStockStatus`, so the
    // planner no longer re-exports that composable's labels either.

    // Hovering a needed ingredient highlights the day cells whose recipes use
    // it (desktop only — mouse events don't fire on touch).
    const hoveredRecipeIds = ref<Set<string>>(new Set());
    let budgetSeq = 0;
    async function loadBudgetStatus() {
        const req = ++budgetSeq;
        if (!moneyEnabled.value) { budgetStatus.value = null; return; }
        const week = focusedMonday.value;
        try {
            // The period containing the week on screen, not today's: a week
            // two weeks out is measured against its own (as yet unspent)
            // budget (owner 2026-10-15).
            const status = await budgetApi.getStatusAsync(week);
            // A newer load (e.g. the week changed) owns the card now.
            if (req !== budgetSeq) return;
            budgetStatus.value = status;
        } catch {
            // A budget we can't read is not worth interrupting the planner for;
            // the card simply shows the week's cost without it.
            if (req !== budgetSeq) return;
            budgetStatus.value = null;
        }
    }

    function hoverIngredient(ing: MealPlanIngredient) {
        hoveredRecipeIds.value = new Set(ing.used_in_recipe_ids);
    }
    function clearHover() {
        hoveredRecipeIds.value = new Set();
    }

    // ── Recipe pool quick-actions (± / log cook) ───────────────────────────
    async function adjustPaletteMeals(recipeId: string, delta: number) {
        try {
            await recipeStore.adjustMealsAsync(recipeId, delta);
            // The plans reload too: spending or topping up the pool changes
            // which planned meals still need cooking, and that verdict now
            // rides on the entries themselves (`needs_cooking`), not on a
            // separate recipe-level list.
            await Promise.all([
                recipeStore.getRecipesAsync(),
                mealPlanStore.getMealPlansAsync(),
            ]);
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not update meals.',
                caption: toastCaption(err),
            });
        }
    }
    // `logPaletteCook` lived here and backed the rail row's "Log a cook…"
    // dialog, deleted 2026-09-01 with the button (owner call). `cookAsync` is
    // still reachable from the recipe page, which is where a cook belongs; the
    // rail's `+` goes through `adjustPaletteMeals` above.

    function goToRecipe(recipeId: string) {
        void router.push(`/cookbook/${recipeId}`);
    }
    /**
     * Open cook mode for a planned meal, cooking for what the plan says.
     *
     * Owner, 2026-09-04: *"When clicking cook now from a meal slot, auto adjust
     * the servings based on what the meal plan says for that slot. Also account
     * for linked days. For example I see now 'Cook - serves 6', so I expect it
     * to be adjusted to 6 when I get to cook mode."*
     *
     * `cook_batch_total_servings` is the server's own figure for what one cook
     * of a linked batch must produce — the same number the chip prints — so the
     * page and cook mode can't disagree about it (R-003). Cook mode's headcount
     * is session-only and still freely adjustable there; this only changes what
     * it opens at.
     */
    function cookRecipe(entry: MealPlanEntry) {
        const serves = entry.cook_batch_total_servings ?? entry.servings;
        const query = serves > 0 ? `?for=${serves}` : '';
        void router.push(`/cookbook/${entry.recipe_id}/cook${query}`);
    }
    // FU-308 (2026-07-07) — `goToManageTemplates` retired. The Templates
    // drawer now houses per-template CRUD; the drawer itself owns the
    // "Manage rotating sets →" jump to `/meal-plans/templates`, so a
    // composable-level nav helper isn't needed.

    // ── Add to list (shared picker + flow, owner feedback 2026-08-27) ─────
    // Replaces the old one-shot "Generate shopping list for this week", which
    // asked the server to sweep the week and then dropped you on a brand-new
    // list — you never saw the items and couldn't veto any of them. This runs
    // the *same* `AddToListDialog` the recipe page runs, seeded with the
    // week's aggregated demand. The dialog's "+ New list" option is what keeps
    // the old button's one-tap "make me a list for this week" reachable, so
    // nothing was lost in the swap.
    const addToListOpen = ref(false);
    const addToListRows = computed(() => rowsFromMealPlanIngredients(
        ingredients.value, recipeNameById, isMissing, isLowStock,
    ));
    const addToListUnlinked = computed(() => unlinkedFromMealPlan(unlinkedIngredients.value));
    const addToListNewName = computed(() => {
        const plan = focusedPlan.value;
        return plan ? `Meals: week of ${formatDate(plan.start_date)}` : 'Shopping list';
    });

    const recipeNames = computed(() => new Map(recipes.value.map((r) => [r.recipe_id, r.name])));
    function recipeNameById(recipeId: string): string | null {
        return recipeNames.value.get(recipeId) ?? null;
    }

    function openAddToList() {
        addToListOpen.value = true;
    }

    /** Commits the picker's selection. `newListName` comes from the dialog so
     *  a user who renamed the proposed list gets the name they typed. */
    async function confirmAddToList(
        payload: AddToListConfirm, newListName: string,
    ): Promise<void> {
        generating.value = true;
        try {
            const listId = await addStockItemsToList(
                payload.targetListId, payload.stockItemIds, newListName,
            );
            addToListOpen.value = false;
            // Reload so the "already on a list" counts settle immediately —
            // this is exactly the staleness the owner reported.
            await loadIngredients();
            if (payload.targetListId === null && listId) {
                // Only a *brand-new* list navigates. Topping up an existing
                // one leaves you on the planner, where you were working.
                void router.push(`/shopping-lists/${listId}`);
            }
        } finally {
            generating.value = false;
        }
    }

    function formatDate(iso: string): string {
        return formatLocaleDate(iso);
    }
    // Request token: a slower earlier week's response (or one in flight when
    // the week was cleared) must not overwrite what is on screen now.
    let ingredientsSeq = 0;
    async function loadIngredients() {
        const req = ++ingredientsSeq;
        const id = focusedPlan.value?.meal_plan_id;
        if (!id) {
            ingredients.value = [];
            unlinkedIngredients.value = [];
            ingredientsLoading.value = false;
            return;
        }
        ingredientsLoading.value = true;
        try {
            const payload = await mealPlanStore.getIngredientsForPlanAsync(id);
            if (req !== ingredientsSeq) return;
            ingredients.value = payload.items;
            unlinkedIngredients.value = payload.unlinked;
        } catch (err) {
            if (req !== ingredientsSeq) return;
            // Fail soft: an empty shopping card plus a toast, rather than a
            // rejection escaping to the page ErrorBoundary — or a mutation's
            // "Could not update the plan" when only this follow-up read failed.
            ingredients.value = [];
            unlinkedIngredients.value = [];
            $q.notify({
                type: 'negative',
                message: "Couldn't load this week's ingredients.",
                caption: toastCaption(err),
            });
        } finally {
            if (req === ingredientsSeq) ingredientsLoading.value = false;
        }
    }

    async function confirmClearWeek() {
        const plan = focusedPlan.value;
        if (!plan) return;
        const ok = await confirm({
            title: 'Clear this week',
            message: `Remove all meals from the week of ${formatDate(plan.start_date)}?`,
            okLabel: 'Clear',
            destructive: true,
        });
        if (ok) await doClearWeek(plan.meal_plan_id);
    }
    async function doClearWeek(planId: string) {
        await mealPlanStore.deleteMealPlanAsync(planId);
        await loadIngredients();
    }

    // ── Templates (C-2.F) ──────────────────────────────────────────────────
    async function saveFocusedWeekAsTemplate(name: string, description: string): Promise<boolean> {
        if (!focusedPlan.value || !name.trim()) return false;
        try {
            await mealPlanTemplateStore.createFromPlanAsync({
                name: name.trim(),
                source_meal_plan_id: focusedPlan.value.meal_plan_id,
                ...(description.trim() ? { description: description.trim() } : {}),
            });
            $q.notify({ type: 'positive', message: 'Saved this week as a template.' });
            return true;
        } catch (err) {
            $q.notify({
                type: 'negative', 
                message: 'Could not save the template.',
                caption: toastCaption(err),
            });
            return false;
        }
    }

    /**
     * Warn before replacing the focused week's future meals (Decision 1 copy
     * from C-2). Returns true when the user has explicitly confirmed (or there
     * are no future entries to replace). The templates drawer (§9-E) and any
     * other apply-template entry point both gate on this.
     */
    async function warnBeforeReplaceWeek(): Promise<boolean> {
        const futureCount = (focusedPlan.value?.entries ?? []).filter(
            (e) => !e.consumed_at && !isPastDay(toIso(e.scheduled_for)),
        ).length;
        if (futureCount === 0) return true;
        return await confirm({
            title: 'Replace this week?',
            message: `This week has ${futureCount} planned meal${futureCount === 1 ? '' : 's'}. `
                + `Applying the template will replace ${futureCount === 1 ? 'it' : 'them'}.`,
            okLabel: 'Replace',
        });
    }

    async function applyTemplate(templateId: string) {
        try {
            const result = await mealPlanTemplateStore.applyAsync({
                template_id: templateId,
                monday_of_week: focusedMonday.value,
            });
            await refreshAfterMutation();
            if (result.added_count === 0) {
                $q.notify({ type: 'info', message: 'Nothing added. Those days are in the past.' });
                return;
            }
            let message = `Added ${result.added_count} meal${result.added_count === 1 ? '' : 's'}.`;
            if (result.skipped_past_count) {
                message += ` ${result.skipped_past_count} past day${result.skipped_past_count === 1 ? '' : 's'} skipped.`;
            }
            $q.notify({ type: 'positive', message });
        } catch (err) {
            $q.notify({
                type: 'negative', 
                message: 'Could not apply the template.',
                caption: toastCaption(err),
            });
        }
    }

    // ── Recurring apply (template or rotating set over a range) ────────────
    const recurringSourceOptions = computed(() => [
        ...templates.value.map((t) => ({ label: `Template · ${t.name}`, value: `t:${t.meal_plan_template_id}` })),
        ...sets.value.map((s) => ({ label: `Set · ${s.name}`, value: `s:${s.meal_plan_template_set_id}` })),
    ]);

    async function loadRecurringSources(): Promise<boolean> {
        await Promise.all([mealPlanTemplateStore.getTemplatesAsync(), mealPlanTemplateSetStore.getSetsAsync()]);
        if (recurringSourceOptions.value.length === 0) {
            $q.notify({ type: 'info', message: 'Save a template first.' });
            return false;
        }
        return true;
    }

    async function applyRecurring(args: {
        source: string;
        startMonday: string;
        endMonday: string;
    }): Promise<boolean> {
        const [kind, id] = [args.source.slice(0, 1), args.source.slice(2)];
        try {
            const result = await mealPlanTemplateStore.applyRecurringAsync({
                ...(kind === 't' ? { template_id: id } : { template_set_id: id }),
                start_monday: mondayOf(args.startMonday),
                end_monday: mondayOf(args.endMonday),
            });
            await refreshAfterMutation();
            let message = `Planned ${result.weeks_applied} week${result.weeks_applied === 1 ? '' : 's'} `
                + `(${result.total_added} meal${result.total_added === 1 ? '' : 's'}).`;
            if (result.total_skipped_past) message += ` ${result.total_skipped_past} past day(s) skipped.`;
            $q.notify({ type: 'positive', message });
            if (result.first_meal_plan_id) focusedMonday.value = mondayOf(args.startMonday);
            return true;
        } catch (err) {
            $q.notify({
                type: 'negative', 
                message: 'Could not apply the recurring plan.',
                caption: toastCaption(err),
            });
            return false;
        }
    }

    // ── "Build my week" auto-planner commit (FU-596) ───────────────────────
    // The builder dialog now hands us fully-placed entry commands — recipe +
    // day + slot + servings — authored server-side (or edited by the user in
    // the review step). This replaces the old recipe-ids-only signature whose
    // client-side slot spread defaulted everything to the vocab's first slot
    // (the FU-596 "everything in Breakfast" bug). Placement is no longer
    // computed here; we just persist what the review step committed.
    async function builderBuildPlan(newCmds: MealPlanEntryCommand[]) {
        const upcoming = newCmds.filter((c) => !isPastDay(c.scheduled_for));
        if (upcoming.length === 0) {
            $q.notify({
                type: 'warning', 
                message: 'No upcoming meals to add.',
            });
            throw new Error('no upcoming entries');
        }
        if (!focusedPlan.value) {
            try {
                await mealPlanStore.createMealPlanAsync({ start_date: focusedMonday.value, entries: upcoming });
                await refreshAfterMutation();
            } catch (err) {
                notifyPlanError(err);
                throw err; // let the builder stay on its Build step, not advance to Done
            }
        } else {
            const ok = await persistEntries(
                focusedPlan.value.meal_plan_id,
                [...planEntryCommands(focusedPlan.value), ...upcoming],
            );
            if (!ok) throw new Error('meal-plan build failed'); // toast already shown by persistEntries
        }
        // §9-B — build is decoupled from generate-list. The builder UI exposes
        // an explicit "Generate shopping list" button on its done step.
    }
    // ── Duplicate this week to the next one ────────────────────────────────
    // Owner call (2026-08-07): **replace** semantics — next week's forward
    // entries are overwritten, not merged, so "duplicate" produces a week that
    // actually matches the one you copied. Past + consumed entries are never
    // sent (FU-595's rule); the server preserves those on its own.
    // Built from `toCommand` so a duplicated week keeps `cook_key` and
    // `cook_fresh` — the hand-rolled mapping turned every cook batch into N
    // standalone meals and un-marked fresh meals, silently (finalisation
    // 02-R2). The entry id is dropped: these are *new* entries next week.
    function nextWeekCommands(): MealPlanEntryCommand[] {
        return (focusedPlan.value?.entries ?? [])
            .map((e) => {
                const { meal_plan_entry_id: _id, ...command } = toCommand(e);
                return { ...command, scheduled_for: shiftDays(command.scheduled_for, 7) };
            })
            .filter((c) => !isPastDay(c.scheduled_for));
    }

    async function confirmDuplicateToNextWeek() {
        if (!focusedPlan.value) return;
        const commands = nextWeekCommands();
        if (commands.length === 0) {
            $q.notify({
                type: 'info', 
                message: 'This week has no meals to duplicate.',
            });
            return;
        }
        const nextMonday = shiftDays(focusedMonday.value, 7);
        const existing = mealPlans.value.find((p) => mondayOf(p.start_date) === nextMonday);
        const replacing = (existing?.entries ?? []).filter(isForwardEditable).length;
        const plural = commands.length === 1 ? '' : 's';
        const ok = await confirm({
            title: 'Duplicate to next week',
            message: replacing > 0
                ? `Copy ${commands.length} meal${plural} to the week of ${formatDate(nextMonday)}. `
                    + `This replaces the ${replacing} meal${replacing === 1 ? '' : 's'} already planned there.`
                : `Copy ${commands.length} meal${plural} to the week of ${formatDate(nextMonday)}.`,
            okLabel: replacing > 0 ? 'Replace' : 'Copy',
        });
        if (ok) await doDuplicateToNextWeek(commands, nextMonday, existing?.meal_plan_id);
    }

    async function doDuplicateToNextWeek(
        commands: MealPlanEntryCommand[],
        nextMonday: string,
        existingPlanId: string | undefined,
    ) {
        if (existingPlanId) {
            if (!await persistEntries(existingPlanId, commands)) return;
        } else {
            try {
                await mealPlanStore.createMealPlanAsync({ start_date: nextMonday, entries: commands });
                await refreshAfterMutation();
            } catch (err) {
                notifyPlanError(err);
                return;
            }
        }
        $q.notify({
            type: 'positive', 
            message: `Copied ${commands.length} meal${commands.length === 1 ? '' : 's'} to next week.`,
        });
        // Land the user on what they just created rather than making them
        // navigate to check it worked.
        focusedMonday.value = nextMonday;
    }

    function printFocusedWeek() {
        if (focusedPlan.value) planExport.openPrintView(focusedPlan.value.meal_plan_id);
    }

    watch(() => focusedPlan.value?.meal_plan_id, loadIngredients);

    onMounted(async () => {
        window.addEventListener('keydown', onKeydown);
        try {
            await Promise.all([
                mealPlanStore.getMealPlansAsync(),
                mealPlanStore.getTodayAsync(),
                mealSlotStore.ensureLoadedAsync(),
                mealPlanTemplateStore.getTemplatesAsync(),
                mealPlanTemplateSetStore.getSetsAsync(),
                recipeStore.ensureLoadedAsync(),
                stockItemStore.ensureLoadedAsync(),
                stockLevelStore.ensureLoadedAsync(),
                shoppingListStore.ensureLoadedAsync(),
            ]);
            // Resume on the URL's week if present (F28), else the household's
            // current week (server tz, C-2.K).
            // `mondayOf` normalises whatever day the URL names, so a
            // hand-typed `?week=2026-09-17` still resumes on that week.
            // A mangled `?week=` that isn't a real date is ignored (it used to
            // throw a RangeError out of `isoDate`).
            const rawWeek = route.query.week;
            const urlWeek = typeof rawWeek === 'string' && isDateOnly(rawWeek)
                && Number.isFinite(Date.parse(rawWeek)) ? rawWeek : null;
            focusedMonday.value = mondayOf(urlWeek ?? today.value ?? localTodayIso());
            await Promise.all([loadIngredients(), loadBudgetStatus()]);
        } finally {
            isInitialLoading.value = false;
        }
    });
    onUnmounted(() => window.removeEventListener('keydown', onKeydown));

    return {
        // state
        recipes,
        recipeSearch,
        templates,
        sets,
        ingredients,
        ingredientsLoading,
        isInitialLoading,
        generating,
        focusedMonday,
        focusedPlan,
        weekDays,
        weekRangeLabel,
        weekRelativeLabel,
        suggestions,
        loadSuggestions,
        slotNames,
        currentDayIso,
        needToBuy,
        needToBuyOutstanding,
        unlinkedIngredients,
        budgetStatus,
        hoveredRecipeIds,
        focusedTarget,
        weekTransition,
        // lookups
        dayEntries,
        slotEntries,
        otherSlotEntries,
        isPastDay,
        isTargeted,
        formatDate,
        // mutations
        addEntry,
        adjustEntryServings,
        removeEntry,
        cookBatchDays,
        setCookDays,
        separateCook,
        confirmClearWeek,
        loadIngredients,
        addToListOpen,
        addToListRows,
        addToListUnlinked,
        addToListNewName,
        openAddToList,
        confirmAddToList,
        adjustPaletteMeals,
        saveFocusedWeekAsTemplate,
        warnBeforeReplaceWeek,
        applyTemplate,
        loadRecurringSources,
        applyRecurring,
        builderBuildPlan,
        confirmDuplicateToNextWeek,
        printFocusedWeek,
        // nav
        goPrevWeek,
        goNextWeek,
        goToRecipe,
        cookRecipe,
        toggleCookFresh,
        onTouchStart,
        onTouchEnd,
        // tap-to-target (drag retired — D1, see above)
        selectSlot,
        pickRecipe,
        clearFocusedTarget,
        // hover
        hoverIngredient,
        clearHover,
    };
}
