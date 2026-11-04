<template>
    <!-- The cookbook's filter panel (FU-934 / finalisation 01-R37 — lifted out
         of `RecipesOverview.vue` as-is). It renders the controls only: the
         state is `useCookbookFilters` (shared with the page, which filters and
         sorts by it), and the expanded flag is the page's, because the page's
         toolbar `FilterToggleButton` drives the same panel. The root is
         FilterBar itself — no wrapper element (R-027). -->
    <FilterBar
        v-model="expanded"
        :toolbar="false"
        :active-count="activeFilterCount"
        @clear="clearFilters"
    >
        <template #filters>
        <!-- FU-108: filter controls ordered by usage frequency
             (quick chips → sort → common single-selects →
             ingredients → numeric bounds → occasional
             dietary/tools → set-and-forget collection).
             2026-08-17 feedback: split into the Stock Overview's two
             rows — toggle chips on top, input filters below — each
             scrolling sideways on phones rather than wrapping to four
             or five lines (an open panel was eating the viewport).
             Same rows, same overflow treatment, same class shape as
             `stock-quick-filters` / `stock-input-filters`. -->
        <FilterRow>
        <FilterChip v-model="favouritesOnly" :icon="ICONS.favorite" active-color="negative">
            Favourites
        </FilterChip>
        <!-- Icon matches the recipe row's Cook button (`chef_hat`) — the
             filter and the action it predicts should read as the same
             thing. The help affordance sits INSIDE the chip rather than
             floating beside it, so the chip is one target and the row
             doesn't gain a stray un-aligned glyph. -->
        <FilterChip v-model="cookableNowOnly" :icon="ICONS.chef_hat" active-color="positive">
            Cookable now
            <InfoTip label="What cookable now means">
                Recipes where every ingredient is currently in stock.
            </InfoTip>
        </FilterChip>
        <!-- "Meals prepared" (was "Have meals in pool"): portions you've
             already cooked ahead and can eat now. Only meaningful when the
             install runs batch cook-style — with `batchEnabled` off there
             is no cook-ahead surface at all, so the filter is hidden rather
             than shown always matching nothing (R-029). -->
        <FilterChip
            v-if="batchEnabled"
            v-model="inStockOnly"
            :icon="ICONS.meals_prepared"
            active-color="primary"
        >
            Meals prepared
        </FilterChip>
        <!-- tri-state: click 1 = Planned only, click 2 = Not
             planned only, click 3 = off. Single chip cycles through; the
             active filter count + Clear filters cover both modes. -->
        <TriStateFilterChip
            v-model="plannedFilterState"
            include-label="Planned"
            exclude-label="Not planned"
            :include-icon="ICONS.calendar_month"
            :exclude-icon="ICONS.calendar_month"
            include-color="info"
            exclude-color="warning"
        />
        <!-- C-waste W4 — surfaces recipes that use at least one
             in-stock ingredient expiring within 14 days. While on,
             the list is force-sorted by count desc and each card
             shows a "Uses N expiring" badge. -->
        <FilterChip v-model="expiringOnly" :icon="ICONS.wasteExpired" active-color="warning">
            Uses expiring ingredients
        </FilterChip>
        </FilterRow>

        <!-- ── Row 2: input filters ──────────────────────────────── -->
        <!-- `wide-wraps` — owner feedback 2026-08-28: "on desktop only,
             make it two rows of filters under the quick filters; mobile
             stays one row". The phone keeps the sideways scroll.
             `cookbook-field-row` (FU-773, owner 2026-11-04: force two
             lines) narrows the width track so it is two lines at 1280px;
             see the style block. -->
        <FilterRow variant="fields" wide-wraps class="cookbook-field-row">
        <!-- Order — owner feedback 2026-08-20: "Collection and dietary
             tags filters should be near the front." They were dead last
             and second-to-last, behind six facets and four numeric
             bounds. Now: sort · Collection · Dietary tags (the two he
             reaches for) · the recipe's own facets · numeric bounds ·
             Tools (genuinely occasional). The earlier FU-108 ordering was
             by *guessed* frequency; this is by reported use.

             2026-08-28: Kcal and the front-of-pack rating moved from the
             middle of the numeric bounds to the very end ("health star and
             kcal at the end"). They are the two facets that only exist on
             an install that opted into nutrition, and the only two that
             disappear entirely for everyone else — so a row that ends with
             them keeps the same shape whether or not they render. -->

        <!-- Axis + direction are one control (SortControl) — the direction
             toggle rides in the select's append slot rather than sitting
             beside it as a separately-sized button. -->
        <SortControl
            v-model:sort-by="sortBy"
            v-model:sort-dir="sortDir"
            :options="SORT_OPTIONS"
        />

        <BaseSelect
            emit-value
            map-options
            clearable
            v-model="collectionFilter"
            :options="collectionOptionsWithNone"
            label="Collection"
        >
            <template #prepend><q-icon :name="ICONS.collection" size="18px" /></template>
        </BaseSelect>
        <!-- L237 — one tri-state dietary filter (must-have / must-not /
             neutral) replacing the old two include/exclude selects.
             These were `DietaryTagFilter`, a wrapper whose only remaining
             job was defaulting the label; its own docblock said new uses
             should consume TriStateFilter directly, so with icons to plumb
             through as well it was collapsed rather than widened (R-001). -->
        <TriStateFilter
            label="Dietary tags"
            :icon="ICONS.eco"
            :options="dietaryTagOptions"
            v-model:include="dietaryTagsInclude"
            v-model:exclude="dietaryTagsExclude"
        />

        <!-- L235 — cuisine + category are distinct single-select filters,
             no longer lumped together as one "tags" multi-select.
             Icons match the matching Settings → Kitchen setup pages
             (cuisines = globe, categories = shape, meal slots = clock,
             tools = blender, dietary tags = leaf) so the same concept
             carries the same glyph wherever it appears. -->
        <BaseSelect
            emit-value
            map-options
            clearable
            v-model="cuisineFilter"
            :options="cuisineOptions"
            label="Cuisine"
        >
            <template #prepend><q-icon :name="ICONS.public" size="18px" /></template>
        </BaseSelect>
        <BaseSelect
            emit-value
            map-options
            clearable
            v-model="categoryFilter"
            :options="categoryOptions"
            label="Category"
        >
            <template #prepend><q-icon :name="ICONS.category" size="18px" /></template>
        </BaseSelect>
        <!-- time-of-day single-select. §1.12: vocabulary sourced from the
             household MealSlot table (DEFAULT_MEAL_SLOTS is only the
             pre-first-load fallback).
             Keeps the clock glyph — it matches Settings → Meal slots. The
             crossover the owner reported ran the other way: the *duration*
             chips on the cookbook card/row were also on a clock, and are
             now on `timer`. Clock = a time of day, timer = a length of
             time; one glyph each. -->
        <BaseSelect
            emit-value
            map-options
            clearable
            v-model="timeOfDayFilter"
            :options="TIME_OF_DAY_OPTIONS"
            label="Time of day"
        >
            <template #prepend><q-icon :name="ICONS.schedule" size="18px" /></template>
        </BaseSelect>
        <!-- §1.7 — difficulty single-select. Closed vocabulary
             (Easy / Medium / Hard). The card's difficulty chip was on
             `star_outline`, which reads as a *rating*; it now shares this
             speedometer (owner feedback 2026-08-20). -->
        <BaseSelect
            emit-value
            map-options
            clearable
            v-model="difficultyFilter"
            :options="DIFFICULTY_OPTIONS"
            label="Difficulty"
        >
            <template #prepend><q-icon :name="ICONS.difficulty" size="18px" /></template>
        </BaseSelect>
        <!-- Uses / Doesn't use ingredients consolidated
             into the shared TriStateFilter, with `searchable` for the
             large stock-item set and a per-row stock-level colour dot.
             Single button (+/-) replaces the two paired q-selects. -->
        <TriStateFilter
            label="Ingredients"
            :icon="ICONS.ingredients"
            searchable
            search-placeholder="Search ingredients…"
            :options="ingredientFilterOptions"
            :sort-options="ingredientSortOptions"
            default-sort="name"
            v-model:include="usesStockItemIds"
            v-model:exclude="excludesStockItemIds"
        />

        <!-- Numeric bounds. :hint removed; the under-input copy was just
             padding out the filter row's height and offsetting alignment
             without adding info. Every bound carries the same icon as its
             sort axis / the surface it counts, so the row scans as a set
             rather than a mix of iconned and bare fields. -->
        <!-- "Serves ≥" — owner feedback 2026-08-20 ("missing filter for #
             of serves"). A lower bound, not a range: the intent is "I'm
             cooking for five tonight", and a recipe that serves more than
             that just leaves leftovers. A recipe with no servings recorded
             fails a set bound — same intent rule as the facets above
             ("show me things that feed 5", not "…or that might"). -->
        <q-input
            v-model.number="servesMin"
            dense
            outlined
            type="number"
            min="0"
            label="Serves ≥"
            hide-bottom-space
        >
            <template #prepend><q-icon :name="ICONS.people" size="18px" /></template>
        </q-input>
        <q-input
            v-model.number="ingredientsMax"
            dense
            outlined
            type="number"
            min="0"
            label="Ingredient count ≤"
            hide-bottom-space
        >
            <template #prepend><q-icon :name="ICONS.ingredientCount" size="18px" /></template>
        </q-input>
        <q-input
            v-if="batchEnabled"
            v-model.number="mealCountMin"
            dense
            outlined
            type="number"
            min="0"
            label="Meals prepared ≥"
            hide-bottom-space
        >
            <template #prepend><q-icon :name="ICONS.meals_prepared" size="18px" /></template>
        </q-input>

        <!-- L310 — tools inclusion/exclusion filter (same tri-state control). -->
        <TriStateFilter
            label="Tools"
            :icon="ICONS.blender"
            :options="toolFilterOptions"
            v-model:include="toolsInclude"
            v-model:exclude="toolsExclude"
        />

        <!-- ── The nutrition axes, last (owner 2026-08-28) ────────── -->
        <!-- kcal upper-bound filter (gated). -->
        <q-input
            v-if="kcalAxisAvailable"
            v-model.number="kcalMax"
            dense
            outlined
            type="number"
            min="0"
            label="Kcal ≤"
            hide-bottom-space
        >
            <template #prepend><q-icon :name="ICONS.local_fire_department" size="18px" /></template>
        </q-input>
        <!-- Front-of-pack rating lower-bound filter (gated on the
             install's scheme + complex nutrition). A minimum rather than a
             maximum, unlike Kcal: nobody browses for the worst dinner.
             Label and options come from the composable because they differ
             per scheme — stars count up, Nutri-Score letters count
             down. -->
        <BaseSelect
            v-if="ratingAvailable"
            v-model="ratingMin"
            :label="thresholdLabel"
            :options="thresholdOptions"
            emit-value
            map-options
            clearable
        >
            <template #prepend><q-icon :name="ICONS.star" size="18px" /></template>
        </BaseSelect>
        <!-- Two filters used to live here and no longer do:
             • "Missing ingredients ≤" — removed 2026-08-20 (owner: "feels
               a bit useless?"). The zero case IS the "Cookable now" chip,
               nothing sorted by it, and every card/row already shows what
               the recipe is short of. Its `missingMax` state went with it.
             • "Free from ingredient(s)" free-text — its concern is covered
               by the "Doesn't use" side of the Ingredients picker above;
               the text-match was a source of false negatives. -->
        </FilterRow>
        </template>
    </FilterBar>
</template>

<script lang="ts" setup>
    import { computed } from 'vue';
    import { storeToRefs } from 'pinia';
    import { ICONS } from 'src/style/icons';
    import InfoTip from 'src/components/help/InfoTip.vue';
    import FilterBar from 'src/components/FilterBar.vue';
    import FilterChip from 'src/components/chips/FilterChip.vue';
    import TriStateFilterChip from 'src/components/chips/TriStateFilterChip.vue';
    import FilterRow from 'src/components/filters/FilterRow.vue';
    import TriStateFilter from 'src/components/filters/TriStateFilter.vue';
    import BaseSelect from 'src/components/BaseSelect.vue';
    import SortControl, { type SortAxisFor } from 'src/components/filters/SortControl.vue';
    import type {
        TriStateOption,
        TriStateSort,
    } from 'src/components/filters/triStateFilterTypes';
    import { useBatchEnabled } from 'src/composables/useBatchEnabled';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { useNutritionMode } from 'src/composables/useNutritionMode';
    import { useNutritionRating } from 'src/composables/useNutritionRating';
    import { useCookbookFilters, type CookbookSortKey } from 'src/composables/useCookbookFilters';
    import { useMealSlotStore } from 'src/stores/mealSlotStore';
    import { useRecipeStore } from 'src/stores/recipeStore';
    import { useRecipeVocabStore } from 'src/stores/recipeVocabStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { colourForSequence } from 'src/helpers/stockLevelLogic';
    import { DIFFICULTY_OPTIONS } from 'src/helpers/recipeVocabulary';

    /** Open/closed. Owned by the page (`useFilterPanelExpanded`), which also
     *  hands it to the toolbar's `FilterToggleButton`. */
    const expanded = defineModel<boolean>({ required: true });

    const {
        favouritesOnly, cookableNowOnly, inStockOnly,
        plannedFilterState, expiringOnly, mealCountMin, servesMin, kcalMax,
        ratingMin,
        collectionFilter, cuisineFilter, categoryFilter, timeOfDayFilter,
        difficultyFilter, ingredientsMax, usesStockItemIds, excludesStockItemIds,
        sortBy, sortDir,
        dietaryTagsInclude, dietaryTagsExclude, toolsInclude, toolsExclude,
        activeFilterCount, clearFilters,
    } = useCookbookFilters();

    const { collectionOptions } = storeToRefs(useRecipeStore());
    const { stockItems } = storeToRefs(useStockItemStore());
    const {
        cuisineOptions, categoryOptions, dietaryTagOptions, toolOptions,
    } = storeToRefs(useRecipeVocabStore());
    // §1.12: vocabulary sourced from the household MealSlot table
    // (DEFAULT_MEAL_SLOTS is only the pre-first-load fallback).
    const { slotNamesOrDefault: TIME_OF_DAY_OPTIONS } = storeToRefs(useMealSlotStore());

    // FU-637 — the kcal axis works in both modes (which figure a recipe
    // carries is the server's call). Install-wide cook-style gates every
    // meals-prepared affordance (chip, minimum-count input, sort axis): a
    // "fresh" install has no cooked-ahead portions, so they are hidden rather
    // than left to always match nothing (R-029).
    const { nutritionEnabled: kcalAxisAvailable } = useNutritionMode();
    const { batchEnabled } = useBatchEnabled();
    const { moneyEnabled } = useMoneyEnabled();
    // Front-of-pack rating axis (owner ask 2026-08-27), gated on the install's
    // scheme *and* complex nutrition. Label and threshold options come from
    // the composable because they differ per scheme; this panel holds no
    // per-scheme knowledge.
    const {
        ratingAvailable, ratingLabel, thresholdOptions, thresholdLabel,
    } = useNutritionRating();

    // Labels name the axis only — the direction lives on the attached toggle
    // (see SortControl), so no option here says "first" or carries an arrow.
    // Each axis states how its two directions read and which one it snaps to
    // when picked; that used to live in a separate `sortDirTooltip` switch and
    // a separate `watch(sortBy)`, three places to keep in step for one fact.
    const STATIC_SORT_OPTIONS: SortAxisFor<CookbookSortKey>[] = [
        {
            label: 'Name', value: 'name',
            ascLabel: 'A → Z', descLabel: 'Z → A', defaultDir: 'asc',
        },
        {
            label: 'Recently made', value: 'last_made',
            ascLabel: 'Oldest first', descLabel: 'Most recent first',
        },
        // Recently added is the fifth IMPL_PLAN_COOKBOOK Chunk 1
        // axis; landed once Recipe.created_at became available on the DTO.
        {
            label: 'Recently added', value: 'created_at',
            ascLabel: 'Oldest first', descLabel: 'Most recent first',
        },
        // "Prep + cook time" described the arithmetic rather than the thing
        // being sorted; owner feedback 2026-08-18.
        {
            label: 'Total time', value: 'total_time',
            ascLabel: 'Fastest first', descLabel: 'Slowest first', defaultDir: 'asc',
        },
        // Fewer ingredients first is the common "make this quick" intent.
        {
            label: 'Ingredient count', value: 'ingredient_count',
            ascLabel: 'Fewest first', descLabel: 'Most first', defaultDir: 'asc',
        },
        // §1.7 — difficulty ordinal (Easy < Medium < Hard; nulls sink).
        {
            label: 'Difficulty', value: 'difficulty',
            ascLabel: 'Easiest first', descLabel: 'Hardest first', defaultDir: 'asc',
        },
    ];

    // Conditional axes, each gated on the feature that gives it meaning:
    // "Meals prepared" on batch cook-style, Kcal on the nutrition opt-in, cost
    // on money, rating on the front-of-pack scheme. The page snaps a stored
    // sort off an axis that disappears (its watches on the same flags).
    const SORT_OPTIONS = computed<SortAxisFor<CookbookSortKey>[]>(() => {
        const options = [...STATIC_SORT_OPTIONS];
        if (batchEnabled.value) {
            options.push({
                label: 'Meals prepared', value: 'meal_count',
                ascLabel: 'Fewest first', descLabel: 'Most first',
            });
        }
        if (kcalAxisAvailable.value) {
            options.push({
                label: 'Kcal', value: 'kcal',
                ascLabel: 'Lowest first', descLabel: 'Highest first', defaultDir: 'asc',
            });
        }
        // Owner 2026-09-05 — "can't see or filter on estimated cost". Gated on
        // the money opt-in exactly as Kcal is on nutrition: with money off the
        // server sends no cost at all, so the axis would sort every recipe by
        // null.
        if (moneyEnabled.value) {
            options.push({
                label: 'Cost per serving', value: 'cost',
                ascLabel: 'Cheapest first', descLabel: 'Priciest first', defaultDir: 'asc',
            });
        }
        if (ratingAvailable.value) {
            options.push({
                label: ratingLabel.value, value: 'rating',
                ascLabel: 'Lowest first', descLabel: 'Highest first', defaultDir: 'desc',
            });
        }
        return options;
    });

    // ── Vocabulary options (cuisine / category / dietary / tools) ───────
    // The tools rail groups its chips under a "Tools" heading.
    const toolFilterOptions = computed(() =>
        toolOptions.value.map((o) => ({ ...o, category: 'Tools' })),
    );

    // Collection filter options, plus the "(Uncategorised)" sentinel.
    const collectionOptionsWithNone = computed(() => [
        ...collectionOptions.value,
        { label: '(Uncategorised)', value: '__none__' },
    ]);

    // ── Ingredient (stock-item) filter options ──────────────────────
    // used by the shared TriStateFilter (the +/-
    // partner replaces the old two paired q-selects). The component
    // owns the search input AND the sort selector (name / stock level)
    // — we hand it the full options list with a `dotColour` per row
    // and embed the stock-level sequence in `meta` so the level-sort
    // compare can read it without re-querying the store.
    const ingredientFilterOptions = computed<TriStateOption[]>(() =>
        stockItems.value.map((si) => ({
            value: si.stock_item_id,
            label: si.name,
            // sequence-keyed (R-003). `si.stock_level_sequence`
            // is null on untracked items → null dotColour, which the
            // TriStateFilter renders as a muted dot.
            dotColour: colourForSequence(si.stock_level_sequence ?? null),
            meta: { levelSequence: si.stock_level_sequence ?? null },
        })),
    );

    // Sort axes for the ingredient filter. Name is the default
    // (alphabetical is more browsable than level when scanning); "Stock
    // level" is the secondary axis.
    //
    // Level sort runs **stocked first** (owner feedback 2026-08-20: "doesn't
    // let you change sort direction — if we aren't doing that then level sort
    // should be stocked first, not out of stock first"). A direction toggle
    // was the other option and was rejected: this is a picker inside a
    // dropdown inside a filter panel, and a third control in there costs more
    // than the one direction it would add. Stocked-first is also the right
    // single direction — the dominant use of "Uses ingredients" is picking
    // something you actually have. Ascending sequence = in-stock first per
    // `stock_status.py`; untracked items (null sequence) sink to the bottom
    // rather than riding at the top, which is what a -1 sentinel would do
    // under ascending order.
    const ingredientSortOptions: TriStateSort[] = [
        {
            value: 'name',
            label: 'Name',
            compare: (a, b) => a.label.localeCompare(b.label),
        },
        {
            value: 'level',
            label: 'Stock level',
            compare: (a, b) => {
                const UNTRACKED = Number.MAX_SAFE_INTEGER;
                const aSeq = (a.meta?.levelSequence as number | null | undefined) ?? UNTRACKED;
                const bSeq = (b.meta?.levelSequence as number | null | undefined) ?? UNTRACKED;
                if (aSeq === bSeq) return a.label.localeCompare(b.label);
                return aSeq - bSeq;
            },
        },
    ];
</script>

<style scoped>
    /* The filter rows' scroll behaviour and control scale live in
       `components/filters/FilterRow.vue` (2026-08-19). Both list pages had
       grown a copy of the same ~40 lines, which is how they drifted to
       different control heights; the tri-state dropdown overrides that used
       to live on the page are gone now that TriStateFilter renders a real
       field (see `BaseFilterField`). The one per-control track opt-out left
       is the `filter-row__auto` class applied at the call site — the wider
       numeric track went on 2026-08-29 (owner: the numeric bounds "seem
       bigger than others for no reason"). */

    /* FU-773 (owner 2026-11-04: "force two lines"). Moved here from the page
       with the panel. Cookbook only — every other filter row keeps
       FilterRow's 210px track. At 1280px the row is
       ~1216px wide and 210px fields wrapped thirteen controls onto three lines
       (5 / 5 / 3). Here the track is fluid: six fields share whatever the
       sort control and the gaps leave on the first line, so that line always
       holds sort + 6 and the rest (up to seven more, the most this page shows)
       fit on the second. The track still overrides FilterRow's custom property
       rather than restating widths, so every control keeps one width (the
       2026-08-29 consistency ask). Clamped: never wider than the shared 210px,
       and never under 150px — below that the leading icon, clear button and
       chevron leave no room for a value, so a narrower window (1024px) wraps
       to a third line instead. Measured: 153px fields, 7 / 6 at 1280×900.
       The cost: three long placeholder labels ("Time of day", "Ingredient
       count ≤", "Meals prepared ≥") ellipsise at 1280 until they float.
       Desktop only — the same 600px floor `wide-wraps` uses; the phone's
       sideways-scrolling row keeps 210px. Two classes to beat FilterRow's own
       `.filter-row--fields` rule. */
    @media (min-width: 600px) {
        .filter-row--fields.cookbook-field-row {
            --filter-control-w: clamp(
                150px,
                calc((100% - var(--filter-control-w-sort) - 6 * var(--space-2)) / 6),
                210px
            );
        }
    }
</style>
