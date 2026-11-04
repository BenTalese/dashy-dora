import { computed, ref } from 'vue';
import type { TriState } from 'src/components/chips/TriStateFilterChip.vue';
import type { Difficulty } from 'src/helpers/recipeVocabulary';
import { useListState } from 'src/composables/useListState';
import {
    choiceFilter, listFilter, numberFilter, stateFilter, toggleFilter, useFilterRegistry,
} from 'src/composables/useFilterRegistry';

/**
 * The cookbook's filter, search and sort state: one place for the refs that
 * `RecipesOverview` filters and sorts by and `CookbookFilterPanel` renders
 * controls for (FU-934 / finalisation 01-R37, split out of the page).
 *
 * Every ref is A8 nav-state (R-026): it lives in `useListState`, so it survives
 * navigation within the session and resets on a full reload. That module Map is
 * also what makes the page and the panel share one set of refs: both call this,
 * the first call builds the bags, the second gets the same ones back. The scope
 * keys and defaults are the ones the page used before the split, so a session
 * that already holds cookbook state keeps it.
 */

export type CookbookSortKey =
    | 'name'
    | 'last_made'
    | 'created_at'
    | 'meal_count'
    | 'total_time'
    | 'kcal'
    | 'cost'
    | 'rating'
    | 'ingredient_count'
    | 'difficulty';
export type CookbookSortDir = 'asc' | 'desc';

export function useCookbookFilters() {
    const cookbookState = useListState('cookbook-overview', () => ({
        searchText: ref(''),
        favouritesOnly: ref(false),
        cookableNowOnly: ref(false),
        inStockOnly: ref(false),
        // tri-state: 'off' = no constraint; 'include' = only planned
        // recipes (any future un-consumed MealPlanEntry); 'exclude' = only
        // un-planned recipes. Cycles via TriStateFilterChip.
        plannedFilterState: ref<TriState>('off'),
        // C-waste W4 — when on, restricts the list to recipes using ≥1
        // expiring-within-14-days in-stock ingredient AND force-sorts by
        // count desc.
        expiringOnly: ref(false),
        // `null` means "no bound". Cleared inputs land as NaN via
        // v-model.number; predicates guard on Number.isFinite.
        mealCountMin: ref<number | null>(null),
        // "Serves ≥" lower bound (owner feedback 2026-08-20).
        servesMin: ref<number | null>(null),
        // "Kcal ≤" filter (only renders when nutrition opt-in
        // is on). Recipes with no kcal value pass through.
        kcalMax: ref<number | null>(null),
        ratingMin: ref<number | null>(null),
        collectionFilter: ref<string | null>(null),
        // L235 — cuisine + category are distinct single-select id filters.
        cuisineFilter: ref<string | null>(null),
        categoryFilter: ref<string | null>(null),
        // time-of-day single-select. Null = no filter.
        timeOfDayFilter: ref<string | null>(null),
        // §1.7 — difficulty single-select. Null = no filter.
        difficultyFilter: ref<Difficulty | null>(null),
        // "# ingredients ≤" cap.
        ingredientsMax: ref<number | null>(null),
        // Set via the "Uses ingredients" picker OR via `?usesStockItem=` query.
        usesStockItemIds: ref<string[]>([]),
        // "Doesn't use" pair. Combine with AND.
        excludesStockItemIds: ref<string[]>([]),
    }));

    const cookbookSortState = useListState('cookbook-overview:sort', () => ({
        sortBy: ref<CookbookSortKey>('name'),
        // explicit asc/desc toggle. Default per axis: name = asc,
        // everything else = desc.
        sortDir: ref<CookbookSortDir>('asc'),
    }));

    // Dietary + tools filter state — tri-state include/exclude id arrays
    // (combine with AND). Persisted with the rest of the cookbook filters.
    const cookbookTriStates = useListState('cookbook-overview:tri', () => ({
        dietaryTagsInclude: ref<string[]>([]),
        dietaryTagsExclude: ref<string[]>([]),
        toolsInclude: ref<string[]>([]),
        toolsExclude: ref<string[]>([]),
    }));

    const s = cookbookState;
    const t = cookbookTriStates;
    // Every filter, declared once: the badge count, the "anything filtered?"
    // check and Clear all read this list. The search box sits in the header
    // with its own clear, and the sort axis is presentation, so neither is a
    // filter here.
    const filterRegistry = useFilterRegistry([
        toggleFilter(s.favouritesOnly),
        toggleFilter(s.cookableNowOnly),
        toggleFilter(s.inStockOnly),
        stateFilter(s.plannedFilterState, 'off'),
        toggleFilter(s.expiringOnly),
        numberFilter(s.mealCountMin),
        numberFilter(s.servesMin),
        numberFilter(s.kcalMax),
        numberFilter(s.ratingMin),
        choiceFilter(s.collectionFilter),
        choiceFilter(s.cuisineFilter),
        choiceFilter(s.categoryFilter),
        choiceFilter(s.timeOfDayFilter),
        choiceFilter(s.difficultyFilter),
        numberFilter(s.ingredientsMax),
        listFilter(s.usesStockItemIds),
        listFilter(s.excludesStockItemIds),
        listFilter(t.dietaryTagsInclude),
        listFilter(t.dietaryTagsExclude),
        listFilter(t.toolsInclude),
        listFilter(t.toolsExclude),
    ]);
    const activeFilterCount = filterRegistry.activeCount;
    const hasAnyFilter = computed(() => s.searchText.value !== '' || activeFilterCount.value > 0);

    /** Clear all: every filter plus the search text. Sort is left alone. */
    function clearFilters() {
        s.searchText.value = '';
        filterRegistry.clearAll();
    }

    return {
        ...cookbookState,
        ...cookbookSortState,
        ...cookbookTriStates,
        activeFilterCount,
        hasAnyFilter,
        clearFilters,
    };
}
