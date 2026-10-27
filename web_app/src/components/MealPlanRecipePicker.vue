<template>
    <q-card flat bordered class="meal-plan-recipe-picker">
        <q-card-section class="q-pb-xs">
            <!-- S3 — targeting. The destination is named at BOTH ends (here and
                 on the slot itself): at 1280px+ the rail and the targeted day
                 are far apart, and naming both ends is the reliable version of
                 drawing a connector between them.
                 `role="status"` makes it a live region, so arming a slot is
                 *announced*, not only drawn — the pulse is visual-only and this
                 is its screen-reader equivalent.

                 Owner feedback 2026-09-03 — this was a filled `q-banner`, and
                 two complaints landed on it at once: *"don't like the current
                 big box that appears at the top shifting the UI so much"* and
                 *"replace the box at the top with a simple Done button and '→
                 <meal slot> <date>' text inline with each other"* — plus a
                 preference for the styling the rows had been using: *"I do like
                 the bold green text on the recipe cards for it, better styling
                 than what's in the top box."* So: one line, the arrow-led
                 destination in accent-bold beside its button, and the ~44px the
                 banner used to insert above a scrolled list is now ~28px.

                 The button says **Done**, not Cancel (owner, same batch:
                 *"cancel makes you think you'll undo the meals you added to
                 that slot"*). It never undid anything — it disarms the slot —
                 and "Done" is what disarming means once you have added
                 something. -->
            <!-- Owner 2026-09-12, two changes.
                 (1) The line reads as a target, not as a stray sentence: a
                 tinted, bordered strip in the accent — *"style the destination
                 text better, maybe in a card or something"*.
                 (2) `showTarget` is false on the phone sheet, which names the
                 destination in its own title bar instead (*"could save some
                 vertical space on mobile by moving the destination text to the
                 heading of the dialog instead of 'Pick a recipe'"*). The Done
                 button goes with it there: the sheet closes on a pick, so
                 disarming inside it had nothing left to do — which is exactly
                 the *"Done button does nothing on mobile and also makes no
                 sense there"* report. Its close button is the way out. -->
            <div v-if="focusedTarget && showTarget" role="status" class="picker-target q-mb-sm">
                <span class="picker-target__label">
                    <q-icon :name="ICONS.arrow_forward" size="14px" />
                    {{ focusedTarget.slot }} · {{ formatDate(focusedTarget.dayIso) }}
                </span>
                <BaseButton variant="ghost" dense label="Done" @click="emit('cancelTarget')" />
            </div>

            <!-- L99 — "keep search filter separate to other filters". The search
                 box sits ABOVE the chips and narrows whatever the active chip
                 produced, rather than being one of them. -->
            <q-input
                ref="searchRef"
                :model-value="recipeSearch"
                dense
                outlined
                clearable
                :debounce="150"
                placeholder="Search recipes"
                @update:model-value="(v) => emit('update:recipeSearch', (v ?? '') as string)"
            >
                <template #prepend><q-icon :name="ICONS.search" /></template>
            </q-input>

            <MealPlanRailFilterChips
                class="q-mt-sm"
                :chips="chips"
                :selected="activeFilter"
                @update:selected="onFilterChange"
            >
                <!-- Owner 2026-09-05 — *"no way to filter recipes on estimated
                     cost."* This is a ranking rather than a filter,
                     deliberately: a cost *filter* needs bands, and a band
                     boundary ("under $3 a serving") is a domain constant this
                     client doesn't own and shouldn't invent. Cheapest-first
                     answers the same question out of figures the server
                     already ships, and it is the same ordering the cookbook's
                     Cost-per-serving sort produces (one comparator, R-001).

                     Two options, so `BaseSegmented` is the right primitive
                     (B2a sanctions it at 2-4). Money-gated install-wide: with
                     money off the server sends no cost at all, so the control
                     would sort every recipe by null. It sits in the chip row
                     since 2026-09-12 — see the slot's comment there. -->
                <template #trailing>
                    <BaseSegmented
                        v-if="moneyEnabled"
                        v-model="sortBy"
                        class="picker-sort"
                        dense
                        :options="sortOptions"
                        aria-label="Order recipes"
                    />
                </template>
            </MealPlanRailFilterChips>

            <!-- Owner feedback 2026-09-01 — "some useful filters feel like
                 they're missing from the left rail (time of day, difficulty)".
                 A SECOND axis rather than two more chips: the chip row is one
                 mutually-exclusive shortlist and these two are independent
                 dimensions that narrow whatever it produced, exactly as the
                 search box above does (L99). Both are always present and never
                 change shape (D-023); "Any time" / "Any level" is the unset
                 state, so there is no separate clear control to hunt for.

                 Time-of-day options are the household `MealSlot` vocabulary,
                 not a hardcoded list — the same source the week's slot rows
                 use, so deleting a slot in settings removes it here too.

                 Owner 2026-09-12: the difficulty field's empty state reads
                 "Any difficulty", not "Any level" — in an app whose other long
                 list is full of *stock* levels, "level" was the wrong word. -->
            <div class="picker-axes q-mt-sm">
                <BaseSelect
                    v-model="axisTimeOfDay"
                    class="picker-axes__field"
                    :options="slotOptions"
                    behavior="menu"
                    clearable
                    empty-text="Any time"
                    aria-label="Filter by time of day"
                />
                <BaseSelect
                    v-model="axisDifficulty"
                    class="picker-axes__field"
                    :options="DIFFICULTY_OPTIONS"
                    behavior="menu"
                    clearable
                    empty-text="Any difficulty"
                    aria-label="Filter by difficulty"
                />
            </div>

        </q-card-section>
        <q-separator />

        <div class="recipe-list">
            <!-- F21 — one flat filtered list, where the trays capped their
                 shortcuts at 10 and hid what didn't fit behind an accordion.
                 Above the threshold this virtualises: the item size and the CSS
                 row height MUST agree exactly or Quasar re-measures mid-scroll
                 (the trap `StockOverview` documents at its own switch). -->
            <q-virtual-scroll
                v-if="visibleRecipes.length > VIRTUAL_SCROLL_THRESHOLD"
                :items="visibleRecipes"
                :virtual-scroll-item-size="VIRTUAL_ROW_HEIGHT_PX"
                separator
            >
                <template #default="{ item }">
                    <div :key="item.recipe_id" class="recipe-list__slot">
                        <MealPlanRecipeRow
                            :recipe="item"
                            :mode="rowMode"
                            :target-slot="focusedTarget?.slot"
                            :reason-text="reasonFor(item.recipe_id)"
                            :cost-text="costTextFor(item)"
                            :batch-enabled="batchEnabled"
                            @pick="(id) => emit('recipePick', id)"
                            @pool-adjust="(id, delta) => emit('paletteMealAdjust', id, delta)"
                        />
                    </div>
                </template>
            </q-virtual-scroll>

            <template v-else>
                <div
                    v-for="recipe in visibleRecipes"
                    :key="recipe.recipe_id"
                    class="recipe-list__slot"
                >
                    <MealPlanRecipeRow
                        :recipe="recipe"
                        :mode="rowMode"
                        :target-slot="focusedTarget?.slot"
                        :reason-text="reasonFor(recipe.recipe_id)"
                        :cost-text="costTextFor(recipe)"
                        :batch-enabled="batchEnabled"
                        @pick="(id) => emit('recipePick', id)"
                        @pool-adjust="(id, delta) => emit('paletteMealAdjust', id, delta)"
                    />
                </div>
            </template>

            <div v-if="recipes.length === 0" class="dora-text-muted text-center q-py-md">
                No recipes yet. Create some in the Cookbook.
            </div>
            <div
                v-else-if="visibleRecipes.length === 0"
                class="dora-text-muted text-center q-py-md"
            >
                {{ emptyMessage }}
            </div>
        </div>

    </q-card>
</template>

<script lang="ts" setup>
    import { ICONS } from 'src/style/icons';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseSegmented from 'src/components/BaseSegmented.vue';
    import BaseSelect from 'src/components/BaseSelect.vue';
    import { compareByCostPerServing } from 'src/helpers/recipeCostSort';
    import { formatMoney } from 'src/composables/useMoney';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import MealPlanRailFilterChips from 'src/components/MealPlanRailFilterChips.vue';
    import MealPlanRecipeRow from 'src/components/MealPlanRecipeRow.vue';
    import { storeToRefs } from 'pinia';
    import type { Recipe } from 'src/models/recipe';
    import type { MealPlanSuggestion } from 'src/models/mealPlan';
    import { useBatchEnabled } from 'src/composables/useBatchEnabled';
    import { DIFFICULTY_OPTIONS } from 'src/helpers/recipeVocabulary';
    import {
        buildFilterChips, filterRecipes, matchesAxes,
        type RecipeAxisFilters, type RecipeFilterKey,
    } from 'src/helpers/recipeRailFilters';
    import { suggestionReasonText } from 'src/helpers/mealPlanSuggestionCopy';
    import { useMealSlotStore } from 'src/stores/mealSlotStore';
    import { computed, onMounted, ref, watch } from 'vue';

    const { batchEnabled } = useBatchEnabled();

    /** Above this many rows the list virtualises. Matches the threshold
     *  `StockOverview` uses, so the two long lists in the app behave the same. */
    const VIRTUAL_SCROLL_THRESHOLD = 50;
    /** Must equal the rendered row height (`.recipe-list__slot` min-height), or
     *  Quasar re-measures mid-scroll and the list judders. */
    const VIRTUAL_ROW_HEIGHT_PX = 64;

    const props = withDefaults(
        defineProps<{
            recipeSearch: string;
            recipes: Recipe[];
            focusedTarget: { dayIso: string; slot: string } | null;
            formatDate: (iso: string) => string;
            /** Server-ranked suggestions for the focused week (§4.4). Empty
             *  until loaded; the "Dora suggests" chip shows the plain list
             *  meanwhile rather than an empty rail. */
            suggestions?: MealPlanSuggestion[] | undefined;
            /** Whether to render the "→ slot · date" target line. False on the
             *  phone sheet, whose own title bar names the destination — an
             *  explicit prop, never a viewport sniff (R-019 / ADR-014): this
             *  card is hosted at three widths and only the host knows which
             *  chrome is around it. */
            showTarget?: boolean | undefined;
        }>(),
        {
            suggestions: () => [], showTarget: true,
        },
    );

    const emit = defineEmits<{
        (e: 'update:recipeSearch', value: string): void;
        (e: 'cancelTarget'): void;
        (e: 'recipePick', recipeId: string): void;
        (e: 'paletteMealAdjust', recipeId: string, delta: number): void;
        /** Raised when the user selects the "Dora suggests" chip, so the host
         *  can fetch the ranking lazily rather than on every page load. */
        (e: 'suggestionsRequested'): void;
    }>();

    // ── Filter chips + the two narrowing axes ──────────────────────────────
    const activeFilter = ref<RecipeFilterKey>('all');

    // `null` is "don't narrow on this axis". BaseSelect's `clearable` writes
    // `null` on clear, which is the same value, so no normalisation is needed.
    const axisTimeOfDay = ref<string | null>(null);
    const axisDifficulty = ref<string | null>(null);
    const axes = computed<RecipeAxisFilters>(() => ({
        timeOfDay: axisTimeOfDay.value,
        difficulty: axisDifficulty.value,
    }));

    // R-003 — the household slot vocabulary, from the one store that owns it.
    const { slotNamesOrDefault: slotOptions } = storeToRefs(useMealSlotStore());

    // Owner 2026-09-05 — the rail's ordering. `name` is the resting order every
    // chip but `regulars` already produced, so picking it changes nothing about
    // the list you knew; `cost` re-ranks it cheapest-first.
    const { moneyEnabled } = useMoneyEnabled();
    const sortBy = ref<'name' | 'cost'>('name');
    const sortOptions = [
        { label: 'A-Z', value: 'name' as const },
        { label: 'Cheapest', value: 'cost' as const },
    ];

    const chips = computed(() => buildFilterChips(props.recipes, axes.value));

    function onFilterChange(key: RecipeFilterKey) {
        activeFilter.value = key;
        if (key === 'suggests') emit('suggestionsRequested');
    }

    const reasonByRecipeId = computed(
        () => new Map(props.suggestions.map((s) => [s.recipe_id, s.reason_chip])),
    );

    /**
     * The rows on screen. Every chip but `suggests` is a predicate over the
     * cookbook; `suggests` instead takes the server's ranked id list and
     * preserves ITS order, because the ranking is the whole value — re-sorting
     * it by name would throw away what was computed.
     */
    const visibleRecipes = computed<Recipe[]>(() => {
        const ordered = orderByCost(rawVisibleRecipes.value);
        return ordered;
    });

    /**
     * Cheapest-first, when the user asked for it.
     *
     * Applied AFTER the chip has produced its list, including `suggests`:
     * Dora's ranking is the whole value of that chip, so re-ordering it is
     * something the user has to have asked for — which, having moved this
     * control, they have. `regulars`' most-planned-first order gives way for
     * the same reason.
     */
    function orderByCost(recipes: Recipe[]): Recipe[] {
        if (!moneyEnabled.value || sortBy.value !== 'cost') return recipes;
        return [...recipes].sort((a, b) => compareByCostPerServing(a, b));
    }

    const rawVisibleRecipes = computed<Recipe[]>(() => {
        if (activeFilter.value !== 'suggests') {
            return filterRecipes(
                props.recipes, activeFilter.value, props.recipeSearch, axes.value,
            );
        }
        if (!props.suggestions.length) {
            return filterRecipes(props.recipes, 'all', props.recipeSearch, axes.value);
        }
        const byId = new Map(props.recipes.map((r) => [r.recipe_id, r]));
        const query = props.recipeSearch.trim().toLowerCase();
        return props.suggestions
            .map((s) => byId.get(s.recipe_id))
            .filter((r): r is Recipe => !!r)
            .filter((r) => matchesAxes(r, axes.value))
            .filter((r) => !query || r.name.toLowerCase().includes(query));
    });

    const isSuggesting = computed(
        () => activeFilter.value === 'suggests' && props.suggestions.length > 0,
    );

    const rowMode = computed<'browsing' | 'targeting' | 'suggesting'>(() => {
        if (props.focusedTarget) return 'targeting';
        return isSuggesting.value ? 'suggesting' : 'browsing';
    });

    /** The per-serving figure, shown only while the list is ranked by it. An
     *  unpriced recipe says so rather than showing a blank where every other
     *  row has a number — it is at the bottom of a cheapest-first list, and
     *  "we don't know" is why. */
    function costTextFor(recipe: Recipe): string {
        if (!moneyEnabled.value || sortBy.value !== 'cost') return '';
        const value = recipe.estimated_cost_per_serving;
        return value === null || value === undefined
            ? 'No price yet'
            : `${formatMoney(value)} a serving`;
    }

    function reasonFor(recipeId: string): string {
        if (!isSuggesting.value) return '';
        const chip = reasonByRecipeId.value.get(recipeId);
        return chip ? suggestionReasonText(chip) : '';
    }

    const emptyMessage = computed(() => {
        if (props.recipeSearch.trim()) return 'No matches.';
        // Naming the axis matters more than naming the chip: the chip row is
        // on screen and visibly selected, whereas an "Any time" field that now
        // reads "Breakfast" is easy to forget you set.
        if (axisTimeOfDay.value || axisDifficulty.value) {
            return 'No recipes match those filters.';
        }
        if (activeFilter.value === 'suggests') return 'Nothing to suggest for this week.';
        return 'Nothing here yet.';
    });

    // ── Focus on arming (§4.6) ─────────────────────────────────────────────
    //
    // "Focus moves into the rail's search on auto-open. Not optional: the pulse
    // is visual-only, and moving focus is its keyboard equivalent."
    //
    // The picker focuses ITSELF rather than exposing a method for the page to
    // call. The page's version didn't work: it set `railOpen` and then reached
    // for the child through a template ref, but the child mounts as a result of
    // that very state change, so the ref was still null when the call was made
    // — and measured in the browser, focus never moved at 300ms OR at 1500ms.
    // Owning it here means `onMounted` runs when this component's own DOM
    // exists, which is exactly the guarantee that was missing.
    //
    // Two entry points, because the rail may be either closed or already open:
    // mounting with a target set (the rail just opened for it), and a target
    // arriving/changing while mounted (you re-armed a different slot).
    const searchRef = ref<{ focus: () => void } | null>(null);

    function focusSearch() {
        searchRef.value?.focus();
    }

    onMounted(() => {
        if (props.focusedTarget) focusSearch();
    });
    watch(() => props.focusedTarget, (target) => {
        if (target) focusSearch();
    });

    // The rail's "Log a cook…" button and the count dialog it opened were
    // deleted 2026-09-01 (owner: "log a cook on the left rail feels
    // unnecessary — remove the button to get back horizontal space and delete
    // the modal"). The row's `+` still logs one cooked meal through
    // `paletteMealAdjust`, and a real cook belongs to the recipe page.
</script>

<style scoped>
    /* The card fills whatever height its host gives it and hands the scroll to
       the recipe list, so the search box, the chips and the "adding to…" target
       banner stay pinned while the recipes move under them.
       Before Unit 1 this was `max-height: 65vh` — a viewport formula that knew
       nothing about the page chrome above it. Inside the planner's fixed-height
       shell the pane is already correctly sized, so measuring the viewport a
       second time would reintroduce exactly the overhang R-036 forbids. The
       three other hosts (mobile picker sheet, builder dialog) size this card
       themselves too. */
    .meal-plan-recipe-picker {
        display: flex;
        flex-direction: column;
        min-height: 0;
    }
    .recipe-list {
        flex: 1 1 auto;
        min-height: 0;
        overflow-y: auto;
        padding: var(--space-2);
        /* Reserve the gutter so row width doesn't jump as searching crosses the
           list from non-scrolling to scrolling. */
        scrollbar-gutter: stable;
    }
    /* Wraps each row so multi-select can put a checkbox beside it without the
       row component knowing anything about selection. The min-height must match
       `VIRTUAL_ROW_HEIGHT_PX`. */
    .recipe-list__slot {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        min-height: 64px;
    }
    .recipe-list__slot > :last-child {
        flex: 1 1 auto;
        min-width: 0;
    }

    /* Two dense fields on one line. They wrap to two lines below ~260px of
       usable width rather than scrolling sideways (D-011). */
    .picker-axes {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-1);
    }
    .picker-axes__field {
        flex: 1 1 120px;
        min-width: 0;
    }

    /* S3 — the durable signal that the rail is armed, and it has to survive
       `prefers-reduced-motion` flattening every animation to 0.01ms (§4.7).
       It carries that signal in accent-weighted TEXT now rather than a filled
       surface: the fill was a box whose arrival shoved the list down, and the
       row it replaced already reads as armed because the destination is named
       in the accent and nothing else in this card is. */
    .picker-target {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        min-height: 28px;
        padding: var(--space-1) var(--space-2);
        border: 1px solid color-mix(in srgb, var(--brand-primary) 35%, var(--border-default));
        border-radius: var(--radius-sm);
        background: color-mix(in srgb, var(--brand-primary) 6%, var(--surface-component));
    }
    .picker-target__label {
        flex: 1 1 auto;
        min-width: 0;
        display: flex;
        align-items: center;
        gap: var(--space-1);
        font-size: var(--font-size-sm);
        font-weight: 600;
        color: var(--accent-ink);
    }
</style>
