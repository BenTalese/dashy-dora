// Shape of GET /dashboard/summary — the single aggregated payload the
// dashboard renders from. (AboutSettings reads `/usage-stats` instead.)
//
// FU-826 trimmed seven fields that nothing in the app rendered: `products`
// and `meals` as whole sub-objects, `shopping_lists.total_items`, and
// `recipes.{favourites, cookable_count, needs_linking_count}`. They were
// shipped for the counter cards IMPL_PLAN_DASHBOARD_REBUILD Phase 1 deleted —
// the cards went, the payload behind them didn't. Two of them
// (`meals.*`) were dedicated aggregate queries running on every dashboard
// load. `shopping_lists.total_items` was additionally the subject of FU-767,
// a bug report about it over-counting; the honest fix for a field no surface
// renders is deletion, which retires that FU too.

export type StockItemSummary = {
    total: number;
    out_of_stock: number;
    low_stock: number;
};

// `ShoppingListSummary` / `RecipeSummary` were deleted in finalisation 08-R2
// (R-057): nothing rendered them after the 2026-09-04 hero cut, and
// AboutSettings reads `/usage-stats`.

export type UpcomingMealPlanEntry = {
    recipe_id: string;
    recipe_name: string;
    scheduled_for: string; // ISO date
    slot: string;
    servings: number;
    /** FU-298 — count of missing ingredients for this entry's recipe, derived
     *  server-side from the shared cookability map. `null` for empty recipes
     *  (no ingredients) OR for tri-state None recipes with unlinked
     *  ingredients (Chunk 4). `0` = ready to cook; > 0 = N missing. Use
     *  ``unlinked_ingredient_count`` to distinguish the two null cases. */
    missing_count: number | null;
    /** IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 — number of required
     *  ingredients on this entry's recipe that have no stock_item
     *  link. Non-zero ⇒ badge shows "N need linking" instead of the
     *  ambiguous "No ingredients". */
    unlinked_ingredient_count: number;
    /** Owner 2026-09-04 — the card used to know nothing about the cooked pool,
     *  so it offered "Cook" on meals already sitting in the freezer. These two
     *  are the same server-owned verdict the planner's chips read (R-003):
     *  `needs_cooking` = the pool is short one of these; `cook_fresh` = marked
     *  cooked-on-the-day, outside the pool. Never both. Both false ⇒ the pool
     *  already covers it — or the household cooks fresh, where there is no pool
     *  and neither word means anything (which is why the card reads
     *  `useBatchEnabled` before showing either). */
    needs_cooking: boolean;
    cook_fresh: boolean;
    /** Owner 2026-09-05 — what one cook of this meal's linked batch must yield,
     *  server-derived across the whole batch (not just the days inside the
     *  dashboard's week). `null` for a standalone meal. This is the figure the
     *  card prints and opens cook mode at, the same as the planner's chips —
     *  `useMealPlanner.cookRecipe` reads the identically-named field. */
    cook_batch_total_servings: number | null;
};

export type MealPlanSummary = {
    upcoming_entries: UpcomingMealPlanEntry[];
};

export type DashboardSummary = {
    stock_items: StockItemSummary;
    meal_plan: MealPlanSummary;
};
