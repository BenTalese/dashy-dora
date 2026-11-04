<template>
    <!-- FU-609 — root on <q-page> for the layout height contract so the sticky
         PageCountsFooter pins to the viewport bottom even on a short list. No
         :style-fn here: this page document-scrolls (a growing card grid), it is
         NOT a fixed-height app-shell like StockOverview — <q-page>'s default
         min-height is exactly what's wanted. See ENGINEERING_STANDARDS R-036. -->
    <q-page class="q-pa-md">
        <!-- ── Toolbar ─────────────────────────────────────────────
             2026-08-17 feedback: standardised on the Stock Overview
             toolbar (`StockOverview.vue`) so the two list surfaces read
             as one control. Actions left in a fixed order (add · import ·
             photos · view), filter-toggle + search pushed right. On
             phones every action drops its label and rides its icon alone
             (tooltip carries the name), and `__find` wraps to a full-width
             second row so the search box has room — same two-row shape,
             same `compactToolbar` gate. Import was `ghost` (which reads
             white/transparent next to the filled actions); it's a
             secondary now, like Stock's own non-primary buttons. -->
        <div class="row items-center q-gutter-sm recipes-toolbar">
            <!-- Counts live in the sticky PageCountsFooter (A7). -->
            <BaseButton
                variant="primary"
                :icon="ICONS.add"
                :label="compactToolbar ? undefined : 'New recipe'"
                aria-label="New recipe"
                @click="onCreateClick"
            >
                <BaseTooltip v-if="compactToolbar">New recipe</BaseTooltip>
            </BaseButton>
            <BaseButton
                variant="secondary"
                :icon="ICONS.content_paste"
                :label="compactToolbar ? undefined : 'Import'"
                aria-label="Import a recipe"
                @click="onImportClick"
            >
                <BaseTooltip v-if="compactToolbar">Import a recipe</BaseTooltip>
            </BaseButton>
            <!-- 2026-08-17 feedback: card grid ⇄ one row per recipe (the
                 Stock Overview shape). The icon shows the shape the button
                 switches TO. Remembered per device via localStorage —
                 `useListViewMode`.
                 2026-08-18: this ALSO owns photos now. The toolbar used to
                 carry a separate "Hide photos" toggle beside it, which made
                 four states out of two real ones — "compact with photos" and
                 "cards without" were both just a smaller/emptier version of
                 the other mode. Cards show photos, compact doesn't — and
                 since 2026-08-29 this is the only photo control in the app:
                 the per-user `show_recipe_images` preference was cut once it
                 governed nothing but the recipe page's hero image. -->
            <BaseButton
                variant="secondary"
                :icon="viewMode === 'grid' ? ICONS.view_list : ICONS.view_module"
                :label="compactToolbar ? undefined : (viewMode === 'grid' ? 'Compact' : 'Cards')"
                :aria-label="viewMode === 'grid' ? 'Switch to compact rows, without photos' : 'Switch to cards, with photos'"
                @click="toggleViewMode"
            >
                <!-- The "· remembered next visit" suffix was dropped
                     2026-08-19 (owner): the setting IS remembered, but saying
                     so in a tooltip you read every time is noise. -->
                <BaseTooltip>
                    {{ viewMode === 'grid' ? 'Compact rows, no photos' : 'Card grid with photos' }}
                </BaseTooltip>
            </BaseButton>

            <q-space class="gt-xs" />
            <div class="row items-center q-gutter-sm no-wrap recipes-toolbar__find">
                <!-- Feedback 2026-06-18: filter toggle in the main toolbar so
                     the FilterBar doesn't carry its own row of chrome. -->
                <FilterToggleButton
                    v-model="filtersExpanded"
                    :active-count="activeFilterCount"
                    :compact="compactToolbar"
                    @clear="clearFilters"
                />
                <q-input
                    v-model="searchText"
                    class="col"
                    dense
                    outlined
                    debounce="200"
                    placeholder="Search"
                    clearable
                >
                    <template #prepend><q-icon :name="ICONS.search" /></template>
                </q-input>
            </div>
        </div>

        <!-- Import-from-URL on the overview's New-Recipe
             surface. FU-102: dialog chrome extracted to a shared component;
             this page wires the imported DTO to `createAsync` + nav.
             IMPL_PLAN_RECIPE_IMPORTER §Chunk 6 — the PWA share target
             (manifest.json `share_target.action: /cookbook`) drops
             `?share_text=…&share_url=…` onto this route; on mount we
             read them, auto-open the dialog, and pre-fill the fields
             so the user only has to hit Import. -->
        <RecipeImportDialog
            v-model="importOpen"
            :prefill-content="sharePrefillContent"
            :prefill-source-url="sharePrefillSourceUrl"
            @imported="onRecipeImported"
        />

        <!-- ── Filter panel ─ FilterBar (A4), its controls in
             CookbookFilterPanel (FU-934). The state is `useCookbookFilters`,
             shared with this page; the open flag stays here because the
             toolbar FilterToggleButton drives the same panel. -->
        <CookbookFilterPanel v-model="filtersExpanded" />
        <!-- disclaimer surfaced when any dietary filter is on.
             Pulled from the backend so the wording stays consistent
             between the SPA and Dora. -->
        <div
            v-if="(dietaryTagsInclude.length > 0 || dietaryTagsExclude.length > 0) && tagCatalogue?.disclaimer"
            class="text-caption dora-text-muted q-mb-md"
        >
            <q-icon :name="ICONS.info" size="14px" class="q-mr-xs" />
            {{ tagCatalogue.disclaimer }}
        </div>

        <!-- ── Grid grouped by collection ─────────────────────────── -->
        <!-- Owner feedback 2026-08-20: "filter area needs a little gap between
             itself and page content, just like stock overview has". FilterBar
             only pads itself 4px; on StockOverview the separation comes from
             the bulk-action bar's own `q-py-xs` wrapper sitting between the
             panel and the list. This page has no bulk bar, so the list started
             flush against the filter panel. Own the gap here rather than
             adding bottom margin to FilterBar — that would move every other
             surface that uses it, and StockOverview's spacing is already
             right. -->
        <div class="recipes-content">
        <FadeTransition mode="out-in">
        <div v-if="loading && recipes.length === 0" key="rec-loading" class="text-center q-py-xl">
            <AppSpinner size="48px" />
        </div>
        <div v-else key="rec-content">
            <div
                v-if="filteredRecipes.length === 0"
                class="text-center dora-text-muted q-py-xl"
            >
                <q-icon :name="ICONS.menu_book" size="60px" class="q-mb-sm" />
                <!-- An empty cookbook is not a filter miss: say what to do next. -->
                <div v-if="recipes.length === 0 && !hasAnyFilter">No recipes yet. Add one, or import a recipe from a link or a photo.</div>
                <div v-else>No recipes match the current filters.</div>
                <BaseButton
                    v-if="hasAnyFilter"
                    variant="ghost"
                    label="Clear filters"
                    class="q-mt-sm"
                    @click="clearFilters"
                />
            </div>

            <!-- One flat list, in the order the sort axis put them.
                 Recipes used to be boxed into collapsible collection
                 folders; in a large cookbook that buried search results
                 under a folder you had to notice and open, which is the
                 opposite of what a search is for. The collection is now a
                 fact on each card's meta line, and the toolbar's Collection
                 filter is how you narrow to one.
                 Two shapes, one data path: the compact branch is the same
                 recipes, the same handlers and the same derived figures
                 (`useRecipeDisplay`) — only the component differs. -->
            <div v-if="viewMode === 'grid'" class="row q-col-gutter-md">
                <div
                    v-for="recipe in sortedRecipes"
                    :key="recipe.recipe_id"
                    class="col-12 col-sm-6 col-md-4"
                >
                    <RecipeCard
                        :recipe="recipeWithExpiringCount(recipe)"
                        :show-expiring-badge="expiringOnly"
                        @open="onOpenRecipe"
                        @cook="onCookClick"
                        @toggle-favourite="onToggleFavourite"
                        @add-missing="onAddMissing"
                        @add-all-to-list="onAddAllToList"
                    />
                </div>
            </div>
            <div v-else>
                <RecipeRow
                    v-for="recipe in sortedRecipes"
                    :key="recipe.recipe_id"
                    :recipe="recipeWithExpiringCount(recipe)"
                    :show-expiring-badge="expiringOnly"
                    @open="onOpenRecipe"
                    @cook="onCookClick"
                    @toggle-favourite="onToggleFavourite"
                    @add-missing="onAddMissing"
                    @add-all-to-list="onAddAllToList"
                />
            </div>
        </div>
        </FadeTransition>
        </div>

        <PageCountsFooter v-if="recipes.length > 0" :counts="footerCounts" />

        <!-- ── Edit dialog ────────────────────────────────────────── -->
        <RecipeEditDialog
            v-model="editDialogOpen"
            :recipe="editingRecipe"
            @created="onRecipeCreated"
            @updated="onRecipeUpdated"
        />

        <!-- Cook-mode guard. Owner feedback 2026-08-19: starting cook mode
             from here skipped the "you're missing ingredients" confirm that
             the recipe page shows. Same component, same predicate — the only
             difference is that nothing here can be dirty, because the cookbook
             doesn't edit recipes. -->
        <CookModeGuardDialog
            v-model="cookGuardOpen"
            :recipe="cookGuardRecipe"
            @start="startCookMode"
        />

        <!-- ── Per-ingredient picker (Chunk B §1.4) ─────────────────────
             Owner feedback 2026-08-27 — the recipe-only picker was replaced by
             the shared `AddToListDialog` that meal plans also render, so the
             two surfaces run one flow (R-001). -->
        <AddToListDialog
            ref="pickerRef"
            v-model="pickerOpen"
            :title="pickerRecipe ? `Add ingredients from ${pickerRecipe.name}` : 'Add ingredients to a list'"
            :rows="pickerRows"
            :unlinked="pickerUnlinked"
            :default-new-list-name="pickerRecipe ? `Shopping: ${pickerRecipe.name}` : 'Shopping list'"
            :initial-checked-ids="pickerInitialCheckedIds"
            @confirm="onPickerConfirm"
        />

    </q-page>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    import AppSpinner from 'src/components/AppSpinner.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import FilterToggleButton from 'src/components/FilterToggleButton.vue';
    import CookbookFilterPanel from 'src/components/recipes/CookbookFilterPanel.vue';
    import PageCountsFooter from 'src/components/PageCountsFooter.vue';
    import FadeTransition from 'src/components/transitions/FadeTransition.vue';
    import { storeToRefs } from 'pinia';
    import { useQuasar } from 'quasar';
    import RecipeCard from 'src/components/RecipeCard.vue';
    import RecipeRow from 'src/components/recipes/RecipeRow.vue';
    import RecipeEditDialog from 'components/RecipeEditDialog.vue';
    import AddToListDialog from 'src/components/shoppingList/AddToListDialog.vue';
    import CookModeGuardDialog from 'src/components/recipes/CookModeGuardDialog.vue';
    import { compareByCostPerServing } from 'src/helpers/recipeCostSort';
    import { useBatchEnabled } from 'src/composables/useBatchEnabled';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { useFilterPanelExpanded } from 'src/composables/useFilterPanelExpanded';
    import { useCookbookFilters } from 'src/composables/useCookbookFilters';
    import { useListViewMode } from 'src/composables/useListViewMode';
    import { useShoppingListActions } from 'src/composables/useShoppingListActions';
    import type { Recipe, RecipeTagCatalogue } from 'src/models/recipe';
    import type { AddToListConfirm } from 'src/components/shoppingList/addToListTypes';
    import { lineChoicesFromRecipe, rowsFromRecipe, unlinkedFromRecipe } from 'src/helpers/addToListRows';
    import RecipeApiService, { type ImportedRecipe } from 'src/services/api/recipeApiService';
    import RecipeImportDialog from 'src/components/recipes/RecipeImportDialog.vue';
    import { useMealSlotStore } from 'src/stores/mealSlotStore';
    import { useRecipeStore } from 'src/stores/recipeStore';
    import { useRecipeVocabStore } from 'src/stores/recipeVocabStore';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { needsCookGuard } from 'src/helpers/cookModeGuard';
    import {
        DIFFICULTY_RANK,
        type Difficulty,
    } from 'src/helpers/recipeVocabulary';
    import { computed, onMounted, ref, watch } from 'vue';
    import { useRoute, useRouter } from 'vue-router';
    import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useNutritionMode } from 'src/composables/useNutritionMode';
    import { useNutritionRating } from 'src/composables/useNutritionRating';
    import { newClientId } from 'src/helpers/clientId';
    import { totalMinutes } from 'src/helpers/recipeTime';

    const $q = useQuasar();
    const router = useRouter();
    const route = useRoute();
    const recipeStore = useRecipeStore();
    const stockItemStore = useStockItemStore();
    const shoppingListStore = useShoppingListStore();
    // meal-plan store dependency dropped: `is_planned` is
    // server-derived now, and the page never read the cache otherwise.
    // Saves one round-trip on cookbook overview load.
    const recipeVocabStore = useRecipeVocabStore();
    const mealSlotStore = useMealSlotStore();
    const recipeApi = new RecipeApiService();
    const { addStockItemsToList } = useShoppingListActions();

    const { recipes } = storeToRefs(recipeStore);
    // C-cross Chunk 5 — image-display opt-in for recipe surfaces.
    // Phones drop every toolbar label down to its icon — same gate and same
    // reason as Stock Overview (the row was eating a quarter of the screen).
    const compactToolbar = computed(() => $q.screen.lt.sm);
    // Card grid ⇄ compact rows, remembered across visits (localStorage).
    const viewMode = useListViewMode('cookbook-overview');
    function toggleViewMode() {
        viewMode.value = viewMode.value === 'grid' ? 'compact' : 'grid';
    }
    // FU-637 — the kcal axis works in both modes now. Which figure a recipe
    // carries (typed in simple, rolled-up in complex) is the server's call —
    // the list DTO ships the answer, so nothing is re-derived here (R-003).
    // `kcal_is_reliable` rides along on the DTO and is read by the card and
    // row for their "partial" styling; the filter and sort axes here stopped
    // consulting it on 2026-08-28 (see the filter note below).
    const { nutritionEnabled: kcalAxisAvailable } = useNutritionMode();
    // Install-wide cook-style. "fresh" installs have no cooked-ahead portions,
    // so every meals-prepared affordance (chip, minimum-count input, sort axis)
    // is hidden rather than left to always match nothing.
    const { batchEnabled } = useBatchEnabled();
    const { moneyEnabled } = useMoneyEnabled();
    const kcalOf = (recipe: Recipe) => ({ value: recipe.kcal_per_serving ?? null });
    // Front-of-pack rating axis (owner ask 2026-08-27). Gated on the install's
    // chosen scheme *and* complex nutrition — see `useNutritionRating`. The
    // rating rides the rollup that already runs for the whole page, so having
    // it on the list costs no extra query.
    //
    // The page deliberately holds no per-scheme knowledge: `rankOf` puts both
    // schemes on one higher-is-better scale for sorting, and the threshold
    // options and label come from the composable (CookbookFilterPanel reads
    // them). Adding a third scheme should not mean editing this file.
    const { ratingAvailable, rankOf, meetsThreshold } = useNutritionRating();

    const loading = ref(false);

    // ── Filter state ────────────────────────────────────────────────
    // A8 §3 nav-state — filters/search/sort survive navigation within the
    // session and reset on full reload (`useCookbookFilters`, shared with
    // CookbookFilterPanel, which renders the controls). Non-persisted state
    // (fetch-in-flight, fetched-data caches) stays as its own refs below.
    const {
        searchText, favouritesOnly, cookableNowOnly, inStockOnly,
        plannedFilterState, expiringOnly, mealCountMin, servesMin, kcalMax,
        ratingMin,
        collectionFilter, cuisineFilter, categoryFilter, timeOfDayFilter,
        difficultyFilter, ingredientsMax, usesStockItemIds, excludesStockItemIds,
        sortBy, sortDir,
        dietaryTagsInclude, dietaryTagsExclude, toolsInclude, toolsExclude,
        activeFilterCount, hasAnyFilter, clearFilters,
    } = useCookbookFilters();
    const EXPIRING_FILTER_HORIZON_DAYS = 14;
    /** Per-recipe at-risk facts from the filter fetch: how many ingredients
     *  are at risk, and when the soonest of them goes off. Both are server-
     *  derived; the client only orders and colours by them. */
    type ExpiringFacts = { count: number; soonest: string | null };
    const expiringByRecipeId = ref<Map<string, ExpiringFacts>>(new Map());
    const expiringFetchInFlight = ref(false);
    /** True once the expiring set has actually arrived — an empty map is a
     *  real answer ("nothing uses an expiring item"), not "still loading". */
    const expiringLoaded = ref(false);

    // Cookbook filter + sort state is persisted, so an install that *had* batch
    // cook-style on can come back with a meals-prepared sort or filter still
    // stored after an admin switches to "fresh". Left alone that shows an empty
    // Sort-by select and an active-but-invisible filter silently hiding recipes,
    // so neutralise the state rather than only hiding the controls. Immediate:
    // `batchEnabled` resolves from /api/health after mount, so a stale stored
    // value would otherwise survive until the flag next changed.
    watch(batchEnabled, (enabled) => {
        if (enabled) return;
        if (sortBy.value === 'meal_count') sortBy.value = 'name';
        inStockOnly.value = false;
        mealCountMin.value = null;
    }, { immediate: true });

    // Disclaimer text still comes from the recipe tag catalogue endpoint.
    const tagCatalogue = ref<RecipeTagCatalogue | null>(null);

    // Cookability is server-owned (§3.2): recipes carry `cookable` /
    // `missing_count` and each ingredient carries `is_missing`. The client
    // reads those fields rather than re-deriving from stock data.



    // `is_planned` is now server-owned (RecipeDto field,
    // derived from MealPlanEntry rows in the same query that fills
    // `committed_meals`). The client predicate reads it directly; the
    // old client-side walk of `mealPlanStore.mealPlans[].entries[]`
    // with timezone-juggling on `scheduled_for` is retired.

    // hint computeds removed (the input labels carry the meaning;
    // the hint-under-input text was just inflating the filter row).

    // A7 — sticky footer counts over the FILTERED view.
    const footerCounts = computed(() => [
        { label: 'Shown', value: filteredRecipes.value.length },
        {
            label: 'Cookable now',
            value: filteredRecipes.value.filter((r) => r.cookable).length,
            tone: 'positive' as const,
        },
        {
            label: 'Favourites',
            value: filteredRecipes.value.filter((r) => r.is_favourite).length,
            tone: 'info' as const,
        },
    ]);

    // ── Filtering + sorting + grouping ──────────────────────────────
    // Blank inputs collapse to `null`/NaN; every numeric predicate guards
    // on Number.isFinite so a half-typed/just-cleared field reverts to
    // "no filter" rather than wiping the list (L234).
    const filteredRecipes = computed(() =>
        recipes.value.filter((r) => {
            if (favouritesOnly.value && !r.is_favourite) return false;
            if (cookableNowOnly.value && !r.cookable) return false;
            if (inStockOnly.value && r.available_meals <= 0) return false;
            // tri-state: include keeps only planned; exclude keeps
            // only un-planned; off is no constraint.
            if (plannedFilterState.value === 'include' && !r.is_planned) return false;
            if (plannedFilterState.value === 'exclude' && r.is_planned) return false;

            // C-waste W4 — narrow to recipes the server flagged as
            // using ≥1 expiring-within-horizon ingredient. The map is
            // populated by a separate API call on the filter's true
            // edge; while it's loading we don't narrow (the user sees
            // the unrestricted list rather than an empty flash).
            if (
                expiringOnly.value
                && expiringLoaded.value
                && !expiringByRecipeId.value.has(r.recipe_id)
            ) {
                return false;
            }

            if (
                mealCountMin.value !== null
                && Number.isFinite(mealCountMin.value)
                && r.available_meals < mealCountMin.value
            ) {
                return false;
            }
            // "Serves ≥" lower bound. A recipe with no servings recorded
            // fails a set bound rather than passing through — the user asked
            // for something that feeds N, and "unknown" isn't an answer.
            if (
                servesMin.value !== null
                && Number.isFinite(servesMin.value)
                && (r.servings ?? 0) < servesMin.value
            ) {
                return false;
            }
            // "Kcal ≤" filter. Judges the figure the card displayed, whether
            // or not the rollup behind it cleared the coverage bar (owner
            // decision 2026-08-28 — see `meetsThreshold` for the full note).
            // A recipe with *no* figure still passes: nothing to judge.
            if (
                kcalAxisAvailable.value
                && kcalMax.value !== null
                && Number.isFinite(kcalMax.value)
            ) {
                const { value } = kcalOf(r);
                if (value !== null && value > kcalMax.value) return false;
            }
            // "Health stars ≥" / "Nutri-Score at least" filter. Same rule as
            // Kcal, and the composable owns it because the two schemes rank on
            // different scales.
            if (ratingAvailable.value && !meetsThreshold(r, ratingMin.value)) {
                return false;
            }

            // '__none__' is a real value meaning "uncategorised".
            if (collectionFilter.value !== null) {
                if (
                    collectionFilter.value === '__none__'
                        ? r.recipe_collection_id !== null
                        : r.recipe_collection_id !== collectionFilter.value
                ) {
                    return false;
                }
            }
            // L235 — cuisine + category are independent single-select id filters.
            if (cuisineFilter.value !== null && r.cuisine_id !== cuisineFilter.value) {
                return false;
            }
            if (categoryFilter.value !== null && r.category_id !== categoryFilter.value) {
                return false;
            }
            // time-of-day single-select. Null = no filter; a
            // recipe with null time_of_day fails any non-null filter
            // (matches the user intent of "show me breakfast recipes",
            // not "show me everything tagged breakfast OR unset").
            if (timeOfDayFilter.value !== null && r.time_of_day !== timeOfDayFilter.value) {
                return false;
            }
            // §1.7 — difficulty single-select. Null = no filter; a recipe
            // with null difficulty fails any non-null filter (same
            // intent rule as time_of_day above).
            if (difficultyFilter.value !== null && r.difficulty !== difficultyFilter.value) {
                return false;
            }
            // "# ingredients ≤" cap. Blank/NaN reverts to no
            // filter (matches L234 blank-input rule).
            if (
                ingredientsMax.value !== null
                && Number.isFinite(ingredientsMax.value)
                && r.ingredients.length > ingredientsMax.value
            ) {
                return false;
            }
            if (usesStockItemIds.value.length > 0) {
                const wanted = new Set(usesStockItemIds.value);
                if (!r.ingredients.some((i) => i.stock_item_id !== null && wanted.has(i.stock_item_id))) return false;
            }
            if (searchText.value) {
                const q = searchText.value.toLowerCase();
                if (!r.name.toLowerCase().includes(q)) return false;
            }
            // Tri-state dietary filter — must have all of include, none of exclude.
            if (dietaryTagsInclude.value.length > 0) {
                const has = new Set(r.dietary_tag_ids ?? []);
                if (!dietaryTagsInclude.value.every((t) => has.has(t))) return false;
            }
            if (dietaryTagsExclude.value.length > 0) {
                const has = new Set(r.dietary_tag_ids ?? []);
                if (dietaryTagsExclude.value.some((t) => has.has(t))) return false;
            }
            if (toolsInclude.value.length > 0) {
                const has = new Set(r.tool_ids ?? []);
                if (!toolsInclude.value.every((t) => has.has(t))) return false;
            }
            if (toolsExclude.value.length > 0) {
                const has = new Set(r.tool_ids ?? []);
                if (toolsExclude.value.some((t) => has.has(t))) return false;
            }
            // "Doesn't use" stock-item picker (the +/- partner to
            // "Uses ingredients"). Recipe is excluded if any picked id is in
            // its ingredient set. Replaces the old free-text path.
            if (excludesStockItemIds.value.length > 0) {
                const ingIds = new Set(r.ingredients.map((i) => i.stock_item_id));
                if (excludesStockItemIds.value.some((id) => ingIds.has(id))) return false;
            }
            return true;
        }),
    );

    // explicit asc/desc direction. Null sentinels (last_made,
    // total_time) always sink to the bottom regardless of direction —
    // the user doesn't want a wall of "—" at the top when toggling to
    // newest-first. Name is the universal tiebreaker.
    const sortedRecipes = computed<Recipe[]>(() => {
        const arr = [...filteredRecipes.value];
        // C-waste W4 — while the expiring filter is on, override the
        // user's sort with "most-expiring-ingredients first" so the
        // top of the list is the highest-impact rescue. The user's
        // sort axis + direction are preserved in state for when they
        // toggle the filter off.
        if (expiringOnly.value) {
            const facts = expiringByRecipeId.value;
            return arr.sort((a, b) => {
                const af = facts.get(a.recipe_id);
                const bf = facts.get(b.recipe_id);
                // URGENCY first (owner feedback 2026-08-18): the soonest
                // expiry wins, so 2 ingredients going off today outrank 4
                // going off next week — the filter exists to save the food
                // that's closest to being binned, not the biggest pile.
                // ISO dates compare correctly as strings; a recipe with no
                // date sinks below every recipe that has one.
                const ad = af?.soonest ?? null;
                const bd = bf?.soonest ?? null;
                if (ad !== bd) {
                    if (ad === null) return 1;
                    if (bd === null) return -1;
                    return ad.localeCompare(bd);
                }
                // Same urgency → the bigger rescue first.
                const ac = af?.count ?? 0;
                const bc = bf?.count ?? 0;
                if (ac !== bc) return bc - ac;
                return a.name.localeCompare(b.name);
            });
        }
        const dirSign = sortDir.value === 'desc' ? -1 : 1;
        const cmp = (a: Recipe, b: Recipe): number => {
            switch (sortBy.value) {
                case 'last_made': {
                    const av = a.last_made_on;
                    const bv = b.last_made_on;
                    if (av === null && bv === null) return a.name.localeCompare(b.name);
                    if (av === null) return 1;
                    if (bv === null) return -1;
                    return av.localeCompare(bv) * dirSign;
                }
                case 'created_at': {
                    // never null on rows from the API (DTO field
                    // is always populated post-backfill); ISO-8601 strings
                    // sort lexicographically. Tie-break alphabetical.
                    const c = a.created_at.localeCompare(b.created_at);
                    return c !== 0 ? c * dirSign : a.name.localeCompare(b.name);
                }
                case 'meal_count': {
                    const d = (a.available_meals - b.available_meals) * dirSign;
                    return d !== 0 ? d : a.name.localeCompare(b.name);
                }
                case 'total_time': {
                    const av = totalMinutes(a.prep_time_minutes, a.cook_time_minutes);
                    const bv = totalMinutes(b.prep_time_minutes, b.cook_time_minutes);
                    if (av === null && bv === null) return a.name.localeCompare(b.name);
                    if (av === null) return 1;
                    if (bv === null) return -1;
                    if (av === bv) return a.name.localeCompare(b.name);
                    return (av - bv) * dirSign;
                }
                case 'kcal': {
                    // Sorts on the displayed figure, thin or not — the same
                    // rule the filter follows since 2026-08-28. Sinking a
                    // half-known recipe here while the card shows its number
                    // is the contradiction the owner hit on the filter.
                    // Only "no figure at all" sinks.
                    const av = kcalOf(a).value;
                    const bv = kcalOf(b).value;
                    if (av === null && bv === null) return a.name.localeCompare(b.name);
                    if (av === null) return 1;
                    if (bv === null) return -1;
                    if (av === bv) return a.name.localeCompare(b.name);
                    return (av - bv) * dirSign;
                }
                case 'cost':
                    // Shared with the meal planner's rail since 2026-09-05 —
                    // the tie-break and the nulls-sink rule live in
                    // `recipeCostSort` so the two lists can't rank the same
                    // cookbook differently (R-001).
                    return compareByCostPerServing(a, b, dirSign);
                case 'rating': {
                    // Same rule as the kcal axis: rank on what was shown.
                    // Only an unrated recipe sinks.
                    const av = rankOf(a);
                    const bv = rankOf(b);
                    if (av === null && bv === null) return a.name.localeCompare(b.name);
                    if (av === null) return 1;
                    if (bv === null) return -1;
                    if (av === bv) return a.name.localeCompare(b.name);
                    return (av - bv) * dirSign;
                }
                case 'ingredient_count': {
                    // neither side is null (ingredients[] is
                    // always at least []), so no sentinel-sink handling.
                    const av = a.ingredients.length;
                    const bv = b.ingredients.length;
                    if (av === bv) return a.name.localeCompare(b.name);
                    return (av - bv) * dirSign;
                }
                case 'difficulty': {
                    // §1.7 — ordinal rank (Easy < Medium < Hard); recipes
                    // with no value sink regardless of direction.
                    const av = a.difficulty as Difficulty | null;
                    const bv = b.difficulty as Difficulty | null;
                    const ar = av && av in DIFFICULTY_RANK ? DIFFICULTY_RANK[av] : null;
                    const br = bv && bv in DIFFICULTY_RANK ? DIFFICULTY_RANK[bv] : null;
                    if (ar === null && br === null) return a.name.localeCompare(b.name);
                    if (ar === null) return 1;
                    if (br === null) return -1;
                    if (ar === br) return a.name.localeCompare(b.name);
                    return (ar - br) * dirSign;
                }
                case 'name':
                default:
                    return a.name.localeCompare(b.name) * dirSign;
            }
        };
        return arr.sort(cmp);
    });

    // NOTE: the collection-bucketing + collapsed-folder state that used to
    // live here is gone. Recipes render as one flat sorted list; the
    // collection travels on each card's meta line (`useRecipeDisplay`) and
    // the panel's Collection dropdown is how you narrow to one.

    // 2026-08-20 owner call — the panel opens iff something is filtered, and
    // that state is not remembered across visits. Adopted here from Stock
    // overview, which is where the owner met the behaviour and preferred it.
    const filtersExpanded = useFilterPanelExpanded(
        'cookbook-overview',
        () => activeFilterCount.value > 0,
    );

    // if the user had Kcal as their sort axis and then the
    // nutrition mode leaves simple (off, or complex where the figure is
    // derived per-recipe instead), snap back to Name so the picker doesn't
    // show an orphaned value.
    watch(kcalAxisAvailable, (on) => {
        if (!on && sortBy.value === 'kcal') sortBy.value = 'name';
    });

    // Same guard for the cost axis. Cookbook sort state is persisted, so an
    // install that had money on can come back with a cost sort stored after an
    // admin turns it off — which would show an empty Sort-by select and order
    // the page by a field the server no longer sends. `immediate` because
    // `moneyEnabled` resolves from /api/health after mount, so a stale stored
    // value would otherwise survive until the flag next changed.
    watch(moneyEnabled, (on) => {
        if (!on && sortBy.value === 'cost') sortBy.value = 'name';
    }, { immediate: true });

    // C-waste W4 — merge the server-fetched expiring count back onto
    // recipes from the store before passing them to the card. The
    // store's copies don't carry the count (the default fetch doesn't
    // ask for it); the filter-on fetch does. Identity-stable in the
    // off case so Vue's reactivity skips unnecessary card re-renders.
    function recipeWithExpiringCount(recipe: Recipe): Recipe {
        if (!expiringOnly.value) return recipe;
        const facts = expiringByRecipeId.value.get(recipe.recipe_id);
        const count = facts?.count ?? 0;
        const soonest = facts?.soonest ?? null;
        if (
            count === (recipe.expiring_ingredient_count ?? 0)
            && soonest === (recipe.expiring_soonest_date ?? null)
        ) return recipe;
        return {
            ...recipe,
            expiring_ingredient_count: count,
            expiring_soonest_date: soonest,
        };
    }

    // Fetch the expiring set whenever the filter is flipped on; clear
    // it when flipped off so a stale map doesn't leak into a future
    // session. R-003 — the predicate (which items expire within N days,
    // which recipes use them) lives entirely on the server.
    //
    // `immediate` because the two halves of this filter have different
    // lifetimes: `expiringOnly` is A8 session state and survives navigation
    // (`useListState`), while `expiringByRecipeId` is a plain ref that dies
    // with the component. Open a recipe and come back and the chip restored as
    // on with an empty map behind it — the predicate below then narrowed
    // nothing, so the filter read as active and did nothing (owner 2026-09-09).
    // Re-running on mount re-pairs the two.
    watch(expiringOnly, async (on) => {
        if (!on) {
            expiringByRecipeId.value = new Map();
            expiringLoaded.value = false;
            return;
        }
        expiringFetchInFlight.value = true;
        try {
            const items = await recipeApi.getAllPagesAsync({
                expiring_within_days: EXPIRING_FILTER_HORIZON_DAYS,
            });
            const next = new Map<string, ExpiringFacts>();
            for (const r of items) {
                next.set(r.recipe_id, {
                    count: r.expiring_ingredient_count ?? 0,
                    soonest: r.expiring_soonest_date ?? null,
                });
            }
            expiringByRecipeId.value = next;
            expiringLoaded.value = true;
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not load expiring-ingredient recipes.',
                caption: toastCaption(err),
            });
            expiringOnly.value = false;
        } finally {
            expiringFetchInFlight.value = false;
        }
    }, { immediate: true });

    // ── Recipe actions ──────────────────────────────────────────────
    const editDialogOpen = ref(false);
    const editingRecipe = ref<Recipe | null>(null);

    function onCreateClick() {
        editingRecipe.value = null;
        editDialogOpen.value = true;
    }

    // overview-side URL importer. Mirrors the detail-page
    // flow (which overwrites the current recipe); here we *create* a new
    // recipe from the import preview and route into its detail page so the
    // user can finish the cleanup.
    //
    // IMPL_PLAN_RECIPE_IMPORTER §Chunk 4/5 — every ingredient rides
    // through create now: matched ones as linked (stock_item_id set),
    // unmatched ones as unlinked (raw_text set, stock_item_id null).
    // The Chunk-6 bulk-linker page is where the user resolves the
    // unlinked ones at their leisure. Toast surfaces the count so the
    // user knows.
    const importOpen = ref(false);
    // IMPL_PLAN_RECIPE_IMPORTER §Chunk 6 — PWA share-target landing.
    // The manifest points `share_target.action: /cookbook` and maps
    // the OS share sheet's title/text/url into ?share_title / ?share_text
    // / ?share_url. On mount we lift them into the dialog's prefill
    // props and pop it. Cleared after read so a refresh doesn't
    // re-open the dialog forever.
    const sharePrefillContent = ref('');
    const sharePrefillSourceUrl = ref('');

    function onImportClick() {
        sharePrefillContent.value = '';
        sharePrefillSourceUrl.value = '';
        importOpen.value = true;
    }

    async function onRecipeImported(imported: ImportedRecipe) {
        try {
            const unmatchedCount = imported.ingredients.filter(
                (i) => !i.stock_item_id,
            ).length;

            // Map every ingredient through — Chunk 4 made both branches
            // legal at the create endpoint. Client_ids are fresh for
            // structured-step linkage.
            const ingredientPayload = imported.ingredients.map((i) => ({
                stock_item_id: i.stock_item_id,
                raw_text: i.raw_text ?? null,
                quantity: i.quantity,
                unit: i.unit,
                notes: i.notes,
                client_id: newClientId(),
            }));
            const stepsPayload = imported.steps.map((s) => ({
                client_id: s.client_id,
                parent_client_id: s.parent_client_id,
                sequence: s.sequence,
                text: s.text,
                hint: s.hint,
                ingredient_client_ids: [],
                tool_ids: [],
            }));

            const created = await recipeApi.createAsync({
                name: imported.name,
                category_id: imported.category_id,
                cook_time_minutes: imported.cook_time_minutes,
                cuisine_id: imported.cuisine_id,
                difficulty: imported.difficulty,
                instructions: imported.instructions,
                prep_time_minutes: imported.prep_time_minutes,
                recipe_collection_id: null,
                servings: imported.servings,
                time_of_day: null,
                source: imported.source_url,
                ingredients: ingredientPayload,
                steps: stepsPayload,
            });
            const newId = created.recipe_id;
            // Refresh the overview's cache so the new recipe shows up.
            await recipeStore.getRecipesAsync();

            importOpen.value = false;
            if (imported.is_degraded) {
                $q.notify({
                    type: 'warning',
                    timeout: 6000,
                    message: 'Couldn’t auto-structure that page',
                    caption:
                        'Created a new recipe with the page text in Instructions. ' +
                        'Review and clean it up.',
                });
            } else {
                const matchedCount = imported.ingredients.length - unmatchedCount;
                $q.notify({
                    type: 'positive',
                    timeout: 5000,
                    message: `Imported "${imported.name}".`,
                    caption: unmatchedCount === 0
                        ? `${matchedCount} ingredient${matchedCount === 1 ? '' : 's'} matched.`
                        : `${matchedCount} matched · ${unmatchedCount} unlinked.`,
                });
            }
            if (newId) void router.push(`/cookbook/${newId}`);
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not create the imported recipe.',
                caption: err instanceof Error ? err.message : String(err),
            });
        }
    }

    function onOpenRecipe(recipeId: string) {
        void router.push(`/cookbook/${recipeId}`);
    }

    // Cook-mode entry, guarded the same way `RecipeDetailPage` guards it —
    // the shared predicate lives in `helpers/cookModeGuard` so the two
    // surfaces can't answer "should we ask first?" differently (R-003).
    // `dirty` is never passed: the cookbook has no editable form.
    const cookGuardOpen = ref(false);
    const cookGuardRecipe = ref<Recipe | null>(null);

    function onCookClick(recipeId: string) {
        const r = recipes.value.find((x) => x.recipe_id === recipeId) ?? null;
        if (needsCookGuard(r)) {
            cookGuardRecipe.value = r;
            cookGuardOpen.value = true;
            return;
        }
        startCookMode(recipeId);
    }

    /** Navigate in. Called directly on a clean entry, or by the guard's
     *  "Start anyway", which has no recipe id of its own to hand back. */
    function startCookMode(recipeId?: string) {
        const id = recipeId ?? cookGuardRecipe.value?.recipe_id;
        if (!id) return;
        cookGuardOpen.value = false;
        void router.push(`/cookbook/${id}/cook`);
    }

    function onToggleFavourite(recipeId: string) {
        const r = recipes.value.find((x) => x.recipe_id === recipeId);
        if (r) void recipeStore.toggleFavouriteAsync(r);
    }

    // ── Per-ingredient picker (Chunk B §1.4) ─────────────────────────
    // Cookbook card emits `add-missing` (not cookable) or `add-all-to-list`
    // (cookable). Both open the same picker; the only difference is the
    // initial check state (default = missing/low checked, sufficient/well
    // unchecked; `add-missing` passes the explicit subset as initial-checked
    // so the user lands on exactly what they need to buy).
    const pickerRef = ref<{ setBusy: (v: boolean) => void; newListName: string } | null>(null);
    const pickerOpen = ref(false);
    const pickerRecipe = ref<Recipe | null>(null);
    const pickerInitialCheckedIds = ref<string[] | undefined>(undefined);
    const pickerRows = computed(() => rowsFromRecipe(pickerRecipe.value));
    const pickerUnlinked = computed(() => unlinkedFromRecipe(pickerRecipe.value));

    // `requireActiveList` retired 2026-08-27 — the shared dialog offers
    // "+ New list", so "you have no lists" is no longer a dead end that
    // bounces you to another page mid-task.

    function onAddMissing(recipeId: string, stockItemIds: string[]) {
        const recipe = recipes.value.find((r) => r.recipe_id === recipeId);
        if (!recipe) return;
        if (recipe.ingredients.length === 0) {
            $q.notify({
                type: 'info',
                message: `Nothing to add for "${recipe.name}".`,
            });
            return;
        }
        pickerRecipe.value = recipe;
        pickerInitialCheckedIds.value = stockItemIds;
        pickerOpen.value = true;
    }

    function onAddAllToList(recipeId: string) {
        const recipe = recipes.value.find((r) => r.recipe_id === recipeId);
        if (!recipe) return;
        if (recipe.ingredients.length === 0) {
            $q.notify({
                type: 'info',
                message: `Nothing to add for "${recipe.name}".`,
            });
            return;
        }
        pickerRecipe.value = recipe;
        pickerInitialCheckedIds.value = undefined;
        pickerOpen.value = true;
    }

    async function onPickerConfirm(payload: AddToListConfirm) {
        pickerRef.value?.setBusy(true);
        try {
            await addStockItemsToList(
                payload.targetListId,
                payload.stockItemIds,
                pickerRef.value?.newListName ?? 'Shopping list',
                lineChoicesFromRecipe(pickerRecipe.value),
            );
            pickerOpen.value = false;
            pickerRecipe.value = null;
            pickerInitialCheckedIds.value = undefined;
        } finally {
            pickerRef.value?.setBusy(false);
        }
    }

    // the modal is a stub-creator. On create,
    // close and navigate straight to the detail page so the user can
    // flesh the recipe out (ingredients, steps, image, times, tags)
    // without hunting the list. On update (rename/reclassify from
    // the overview), just refresh the grid.
    async function onRecipeCreated(recipeId: string) {
        editDialogOpen.value = false;
        await router.push(`/cookbook/${recipeId}`);
    }

    async function onRecipeUpdated() {
        editDialogOpen.value = false;
        await recipeStore.getRecipesAsync();
    }

    // ── Query-param deep links ──────────────────────────────────────
    // The stock item detail screen links here with `?usesStockItem=…`, the
    // dashboard with `?cookable=true` ("Cookable tonight → See more") and
    // `?expiring=true` ("Use it up → See more"). A deep link replaces the
    // session-saved filters rather than stacking on them (an intersection
    // usually lands on zero rows), and the query is replaced away once
    // applied so Back/refresh doesn't re-apply it.
    const DEEP_LINK_FILTER_KEYS = ['usesStockItem', 'cookable', 'expiring'] as const;
    function isTruthyFlag(value: unknown): boolean {
        return value === 'true' || value === '1';
    }
    function applyQuery() {
        const q = route.query;
        if (!DEEP_LINK_FILTER_KEYS.some((key) => q[key] !== undefined)) return;
        clearFilters();
        const id = q.usesStockItem;
        if (typeof id === 'string' && id) {
            usesStockItemIds.value = [id];
        }
        if (isTruthyFlag(q.cookable)) {
            cookableNowOnly.value = true;
        }
        // Setting the ref is enough — its own `watch` runs the fetch.
        if (isTruthyFlag(q.expiring)) {
            expiringOnly.value = true;
        }
        const next = { ...q };
        DEEP_LINK_FILTER_KEYS.forEach((key) => delete next[key]);
        void router.replace({ path: route.path, query: next });
    }
    watch(
        () => DEEP_LINK_FILTER_KEYS.map((key) => route.query[key]),
        applyQuery,
    );

    onMounted(async () => {
        loading.value = true;
        try {
            await Promise.all([
                recipeStore.ensureLoadedAsync(),
                recipeStore.ensureCollectionsLoadedAsync(),
                stockItemStore.ensureLoadedAsync(),
                shoppingListStore.ensureLoadedAsync(),
                // `is_planned` is now server-derived (RecipeDto
                // field), so this page no longer needs to fetch meal plans
                // for the "Planned" filter. The store hydration is left to
                // other surfaces that genuinely need it.
                // vocabularies for the cuisine/category/dietary
                // filters (sourced from the editable settings tables).
                recipeVocabStore.ensureLoadedAsync(),
                // household meal-slot vocabulary for the time-of-day filter.
                mealSlotStore.ensureLoadedAsync(),
                // Disclaimer text for the dietary filter. Errors non-fatal.
                recipeApi.getTagCatalogueAsync()
                    .then((c) => { tagCatalogue.value = c; })
                    .catch(() => { tagCatalogue.value = null; }),
            ]);
        } finally {
            loading.value = false;
        }
        applyQuery();
        // IMPL_PLAN_RECIPE_IMPORTER §Chunk 6 — PWA share target landed
        // us here with the OS-share payload in the query string. Lift
        // the text / URL into the dialog's prefill, pop it, and strip
        // the params so a subsequent refresh doesn't re-open.
        const shareText = (route.query.share_text ?? '').toString();
        const shareTitle = (route.query.share_title ?? '').toString();
        const shareUrl = (route.query.share_url ?? '').toString();
        if (shareText || shareUrl) {
            sharePrefillContent.value = shareText || shareTitle;
            sharePrefillSourceUrl.value = shareUrl;
            importOpen.value = true;
            const cleaned = { ...route.query };
            delete cleaned.share_text;
            delete cleaned.share_title;
            delete cleaned.share_url;
            void router.replace({ path: route.path, query: cleaned });
        }
    });
</script>

<style scoped>
    /* ── Toolbar (2026-08-17 feedback) ────────────────────────────────
       Lifted wholesale from `StockOverview.vue` so both list surfaces
       behave identically: desktop = one row (actions left, filter-toggle
       + search right); phones = icon-only actions with `__find` wrapping
       to a full-width second line. `flex-basis: 100%` forces that wrap;
       `q-space.gt-xs` is hidden there so nothing pushes against it. */
    .recipes-toolbar {
        margin-bottom: var(--space-4);
    }
    .recipes-toolbar__find {
        flex: 1 1 auto;
        min-width: 280px;
    }
    @media (max-width: 599px) {
        .recipes-toolbar__find {
            flex-basis: 100%;
            min-width: 0;
        }
    }

    /* Separation between the filter panel and the list — see the
       template note above the wrapper. Matches the gap StockOverview gets
       incidentally from its bulk-bar wrapper. */
    .recipes-content {
        margin-top: var(--space-3);
    }
</style>
