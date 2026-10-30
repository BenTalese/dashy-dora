export type MealPlanEntry = {
    meal_plan_entry_id: string;
    recipe_id: string;
    recipe_name: string;
    scheduled_for: string;
    servings: number;
    slot: string;
    consumed_at: string | null;
    // IMPL_PLAN_MEAL_PLANS_REBUILD §6.5 / Q6 — display fields for the rich
    // meal card (Direction B). Server-derived so the client doesn't
    // cross-join the recipes store (R-003).
    cook_time_minutes: number | null;
    category_name: string | null;
    cuisine_name: string | null;
    has_image: boolean;
    // PROPOSAL_MEAL_PLANS_PART_2 — cook-batch view. `cook_batch_id` groups the
    // linked meals (one cook, several days); the rest are server-derived across
    // the batch. Null/false for a standalone meal.
    cook_batch_id: string | null;
    is_cook_day: boolean;
    cook_batch_total_servings: number | null;
    cook_batch_size: number | null;
    // FU-637 — what one serving of this meal costs, calorie-wise, in the
    // install's current nutrition mode. Server-owned (same figure the cookbook
    // card shows). Null when nutrition is off or the recipe has no figure.
    kcal_per_serving: number | null;
    kcal_is_reliable: boolean;
    /** FU-653 — Dora's belief about this planned meal: `'at_risk'` (an
     *  ingredient she thinks has run out since you planned it) or
     *  `'maybe_cookable'`. Additive only — the week's shortfall and "need to
     *  buy" figures ignore it. Null on cooked entries, and unless the user
     *  opted the meal-planner surface in. */
    inference_hint: 'at_risk' | 'maybe_cookable' | null;
    inference_stock_item_names: string[];
    /** Owner feedback 2026-09-03 — *"if I have 3 meals of fried rice planned
     *  and 2 in the pool, I'd expect the LAST of the 3 to highlight orange.
     *  Currently they all light up."* The per-entry verdict from the server's
     *  pool allocation (soonest-first, and batch-aware: a leftover day is
     *  covered by its own cook). Replaces the client's old "is this entry's
     *  RECIPE in the shortfall set?" test, which lit every entry of a short
     *  recipe. Always false when the household's cook-style is "fresh". */
    needs_cooking: boolean;
    /** A leftovers day of a batch whose cook is still owed: not something to
     *  cook today, but no portion is waiting yet either. Never true on a cook
     *  day. Server-owned off the same pool allocation as `needs_cooking`. */
    cook_batch_pending: boolean;
    /** Owner feedback 2026-09-04 — *"I batch cook and freeze lunches for the
     *  week, but dinner with the parents on Saturday is fresh."* This meal is
     *  cooked on its day and stands outside the cooked-portion pool: it is
     *  never allocated a portion from it and never adds to what has to be
     *  batch-cooked. A third state alongside `needs_cooking`, never both —
     *  "the pool is short one of these" is a question a fresh meal never asks.
     *  Mirrors the stored flag, so it stays honest in a "fresh" household;
     *  only the UI is conditional on cook-style. */
    cook_fresh: boolean;
    /** Owner 2026-09-05 — what this planned meal costs at the servings it is
     *  planned for (the recipe's per-serving estimate x `servings`), not the
     *  recipe's own total. Server-owned off the same pricing ladder the
     *  cookbook and the week builder use. Null when money features are off,
     *  when the recipe couldn't be priced, or when it records no servings. */
    estimated_cost: number | null;
    /** Owner 2026-09-12 — how many of the recipe's linked ingredients are
     *  missing right now. Server-owned, from the app's one cookability rule.
     *  Cards flag it only when this meal is actually cooked from ingredients
     *  (see `mealPlanEntryStatus`) — a leftovers day never asks the question. */
    missing_count: number;
    /** Owner 2026-09-12 — what ONE COOK of this entry's linked batch costs
     *  (the sum of the batch's own per-entry figures, so it can't drift from
     *  the week total). The cook day's price chip prints this; its leftover
     *  days print nothing, because the money is spent once. Null for a
     *  standalone meal, with money off, or when the batch couldn't be priced. */
    cook_batch_estimated_cost: number | null;
};

/** Owner 2026-09-05 — one day's planned cost, with the coverage that keeps it
 *  honest: a day that could only price two of its three meals says so rather
 *  than quoting a confident total (R-041). Null cost means nothing on the day
 *  could be priced — never 0, which would read as a free day. */
export type MealPlanDayCost = {
    scheduled_for: string;
    estimated_cost: number | null;
    counted_meals: number;
    total_meals: number;
};

/** FU-637 — one day's planned calories: "a serving of each meal planned that
 *  day". Not an intake figure — a meal plan schedules pots of food, not plates
 *  for named people. Coverage travels with it: meals whose figure isn't
 *  reliable are left out of the sum and counted in the shortfall. */
export type MealPlanDayNutrition = {
    scheduled_for: string;
    kcal_per_serving: number | null;
    counted_meals: number;
    total_meals: number;
};

export type MealPlan = {
    meal_plan_id: string;
    // instances are nameless (UI shows "Week starting <date>").
    name: string | null;
    start_date: string;
    entries: MealPlanEntry[];
    /** FU-637 — per-day rollup over `entries`, summed server-side. Empty when
     *  nutrition is off. */
    day_nutrition: MealPlanDayNutrition[];
    /** Owner 2026-09-05 — the money rollups, summed server-side for the same
     *  reason. Empty / null when money features are off. `estimated_cost` is
     *  the whole plan's, which for the planner is the week's. */
    day_cost: MealPlanDayCost[];
    estimated_cost: number | null;
    cost_counted_meals: number;
    cost_total_meals: number;
    /** FU-967 — fingerprint of the week as the server holds it. Sent back as
     *  `expected_revision` on a save so a stale copy can't overwrite another
     *  device's edit. */
    revision: string;
};

export type MealPlanIngredient = {
    stock_item_id: string;
    stock_item_name: string;
    total_quantity: number | null;
    unit: string | null;
    used_in_recipe_ids: string[];
    /** Owner feedback 2026-08-27 — server-owned; true only when *every*
     *  contributing ingredient row across the week was optional. Drives the
     *  shared add-to-list picker's Optional section. */
    is_optional: boolean;
};

/** An ingredient row with no linked stock item, so it can't become a
 *  shopping-list line (FU-505). Reported so the picker can name what it
 *  couldn't take rather than dropping it silently. */
export type UnlinkedIngredient = {
    recipe_name: string;
    ingredient_name: string;
    /** Owner 2026-09-12 — the planner highlights the meals an ingredient is
     *  used in by recipe id, and the rail's rows show the amount the week
     *  needs. A free-text row now carries both, so it can be the same row as
     *  its linked neighbours. Quantity is scaled to the planned servings. */
    recipe_id: string;
    quantity: number | null;
    unit: string | null;
};

/** Envelope returned by both the saved-plan `/ingredients` endpoint and the
 *  builder's `/preview-ingredients`. Was a bare array until 2026-08-27 —
 *  `unlinked` has no per-item home. */
export type MealPlanIngredients = {
    items: MealPlanIngredient[];
    unlinked: UnlinkedIngredient[];
    /** Owner 2026-09-12 — the two bands counted separately (a low item may not
     *  need buying at all), plus what the shop and the meals are worth. All
     *  four are server-derived; the costs are `null` when money features are
     *  off install-wide (R-058) or when nothing in the set could be priced. */
    low_count: number;
    out_count: number;
    to_buy_cost: number | null;
    meals_cost: number | null;
};

// ── FU-596 — "Build my week" auto-planner ───────────────────────────────
// Mirrors dora_api/features/meal_plans/build_week.py. Selection + slot/day
// placement are server-owned (R-003); the client sends guidance and renders
// / edits / commits the returned proposal.

export type AutoBuildEmphasis = 'use_up_stock' | 'variety' | 'favourites' | 'surprise';

/** Reason chip frozen server-side per proposed meal. */
export type AutoBuildReason =
    | 'uses_expiring'
    | 'cookable_now'
    | 'favourite'
    | 'not_made_recently'
    | 'variety'
    | 'budget_friendly'
    | 'picked';

export type AutoBuildRequest = {
    /** The days the user toggled on (ISO). One meal per day × slot cell, so
     *  the toggles are the meal count — there is no separate knob. */
    days: string[];
    emphasis: AutoBuildEmphasis;
    /** Empty ⇒ every household slot; a subset ⇒ just those. */
    slot_names: string[];
    /** Build one day's line-up and duplicate it to the other selected days. */
    repeat_same_day: boolean;
    budget_cap: boolean;
    /** Servings every proposed meal is created at. The dialog seeds it from
     *  the household headcount (Settings -> Cooking); the review step still
     *  edits each row. */
    default_servings: number;
};

export type ProposedEntry = {
    recipe_id: string;
    recipe_name: string;
    scheduled_for: string;   // ISO date
    slot: string;
    servings: number;
    reason_chip: AutoBuildReason;
    cookable: boolean | null;
    missing_stock_item_names: string[];
    estimated_cost: number | null;
    // PROPOSAL_MEAL_PLANS_PART_2 §9 — grouping token for a proposed cook batch
    // (Batch households). Entries sharing it are one cook; null = standalone.
    cook_key: string | null;
};

/**
 * The server's frozen reason vocabulary (`build_week.py:88-94`, annotated
 * "frozen server-side, R-003"). The rail maps these tokens to copy; it must not
 * invent a token, and a new one must be added on the server first.
 */
export type SuggestionReasonChip =
    | 'uses_expiring'
    | 'cookable_now'
    | 'favourite'
    | 'not_made_recently'
    | 'variety'
    | 'budget_friendly'
    | 'picked';

export type MealPlanSuggestion = {
    recipe_id: string;
    reason_chip: SuggestionReasonChip;
};

export type MealPlanSuggestions = {
    suggestions: MealPlanSuggestion[];
};

export type AutoBuildResponse = {
    entries: ProposedEntry[];
    /** The requested days the server actually built into (past days dropped). */
    days_used: string[];
    slots_used: string[];
    cost_total: number | null;
    budget_amount: number | null;
    projected_over: boolean;
};
