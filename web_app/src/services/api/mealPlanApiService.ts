import type {
    AutoBuildRequest, AutoBuildResponse, MealPlan, MealPlanIngredients,
    MealPlanSuggestions,
} from 'src/models/mealPlan';
import type { CreatedResponse } from './axiosHttpClient';
import AxiosHttpClient from './axiosHttpClient';
import { createQueryString, fetchAllPages, SortOrder, type Page } from './queryStringBuilder';

export type MealPlanEntryCommand = {
    /** The saved entry this row edits; it keeps its id across the save. Omit
     *  for a new entry. Only honoured on update (FU-878). */
    meal_plan_entry_id?: string;
    recipe_id: string;
    scheduled_for: string;
    servings: number;
    slot: string;
    /** PROPOSAL_MEAL_PLANS_PART_2 — transient grouping token; entries sharing a
     *  `cook_key` become one CookBatch (cook once, eat several days). Carry the
     *  saved entry's `cook_batch_id` here to keep a link across edits. */
    cook_key?: string;
    /** Owner 2026-09-04 — this meal is cooked on its day, outside the cooked
     *  pool. Mutually exclusive with `cook_key`; the server refuses the pair. */
    cook_fresh?: boolean;
};

export type CreateMealPlanCommand = {
    name?: string; // optional — the planner creates nameless week-plans.
    start_date: string;
    entries: Omit<MealPlanEntryCommand, 'meal_plan_entry_id'>[];
};

export type UpdateMealPlanCommand = {
    meal_plan_id: string;
    name?: string;
    start_date?: string;
    entries?: MealPlanEntryCommand[];
    /** Required when `entries` is an empty array. Without it the backend
     *  rejects the wipe so a UI bug can't accidentally nuke a plan. */
    confirm_clear_entries?: boolean;
    /** FU-967 — the plan's `revision` this edit was built from; the server
     *  answers 409 when the week has changed since. */
    expected_revision?: string;
};

export default class MealPlanApiService {
    private httpClient: AxiosHttpClient;

    constructor() {
        this.httpClient = new AxiosHttpClient();
    }

    createAsync = async (command: CreateMealPlanCommand): Promise<CreatedResponse> =>
        await this.httpClient.post<CreatedResponse>('/meal-plans', command);

    deleteAsync = async (mealPlanId: string): Promise<void> =>
        await this.httpClient.delete(`/meal-plans/${mealPlanId}`);

    /** One page, newest week first. Stated explicitly so paging order never
     *  depends on the server's default. */
    getAllAsync = async (
        pagination?: { page: number; limit: number },
    ): Promise<Page<MealPlan>> =>
        await this.httpClient.get<Page<MealPlan>>(
            `/meal-plans${createQueryString(undefined, { field: 'start_date', order: SortOrder.DESCENDING }, pagination)}`,
        );

    /** Every meal plan: the planner matches weeks against this list, so a
     *  plan past the first page would read as missing and be re-created. */
    getAllPagesAsync = async (): Promise<MealPlan[]> =>
        await fetchAllPages((page, limit) => this.getAllAsync({ page, limit }));

    updateAsync = async (command: UpdateMealPlanCommand): Promise<void> => {
        const { meal_plan_id, ...payload } = command;
        await this.httpClient.patch<void>(`/meal-plans/${meal_plan_id}`, payload);
    };

    getIngredientsAsync = async (mealPlanId: string): Promise<MealPlanIngredients> =>
        await this.httpClient.get<MealPlanIngredients>(`/meal-plans/${mealPlanId}/ingredients`);

    /** The household's current date (ISO) in the install's configured
     *  timezone — the planner trusts this over the browser clock (C-2.K). */
    getTodayAsync = async (): Promise<string> =>
        (await this.httpClient.get<{ today: string }>('/meal-plans/today')).today;

    /** Aggregated ingredient demand for an unsaved recipe selection (C-2.J,
     *  sequential builder). Same scaling math as the saved-plan endpoint. */
    previewIngredientsAsync = async (
        recipes: { recipe_id: string; servings: number }[],
    ): Promise<MealPlanIngredients> =>
        await this.httpClient.post<MealPlanIngredients, { recipes: { recipe_id: string; servings: number }[] }>(
            '/meal-plans/preview-ingredients', { recipes },
        );

    /** FU-596 — "Build my week" auto-planner. Returns a proposed set of
     *  meals (server-selected + slot/day-placed); never persists. The SPA
     *  renders it as an editable preview and commits via the normal
     *  create/update path. */
    autoBuildAsync = async (command: AutoBuildRequest): Promise<AutoBuildResponse> =>
        await this.httpClient.post<AutoBuildResponse, AutoBuildRequest>(
            '/meal-plans/auto-build', command,
        );

    /** BRIEF_MEAL_PLANNER_RAIL_AND_SHELL §4.4 — the rail's "Dora suggests"
     *  ranking. Read-only and deterministic; returns recipe ids paired with the
     *  server's own frozen reason tokens (`uses_expiring`, `cookable_now`, …),
     *  never prose — the copy map lives on the client, the vocabulary does not
     *  (R-003). Recipes already planned in `weekStart`'s week are excluded. */
    getWeekSuggestionsAsync = async (
        weekStart: string, count?: number,
    ): Promise<MealPlanSuggestions> =>
        await this.httpClient.get<MealPlanSuggestions>(
            `/meal-plans/suggestions?week_start=${weekStart}`
            + (count === undefined ? '' : `&count=${count}`),
        );

    // ── FU-451 — budget-defense recipe swaps ──────────────────────────

    getSwapSuggestionsAsync = async (mealPlanId: string): Promise<SwapSuggestions> =>
        await this.httpClient.get<SwapSuggestions>(`/meal-plans/${mealPlanId}/swap-suggestions`);

    applySwapAsync = async (
        mealPlanId: string, command: ApplySwapCommand,
    ): Promise<ApplySwapResult> =>
        await this.httpClient.post<ApplySwapResult, ApplySwapCommand>(
            `/meal-plans/${mealPlanId}/apply-swap`, command,
        );

    /** FU-637 — lighter alternatives for one planned meal. On demand only. */
    getLighterAlternativesAsync = async (
        mealPlanId: string, entryId: string,
    ): Promise<LighterAlternatives> =>
        await this.httpClient.get<LighterAlternatives>(
            `/meal-plans/${mealPlanId}/lighter-alternatives?entry_id=${entryId}`,
        );

    undoSwapAsync = async (
        mealPlanId: string, swapLedgerId: string,
    ): Promise<UndoSwapResult> =>
        await this.httpClient.post<UndoSwapResult, { swap_ledger_id: string }>(
            `/meal-plans/${mealPlanId}/undo-swap`, { swap_ledger_id: swapLedgerId },
        );

    // ── FU-317 — meal-plan reconcile ──────────────────────────────────

    getReconcileQueueAsync = async (
        params: { cursor?: string; limit?: number } = {},
    ): Promise<ReconcileQueue> => {
        const query = new URLSearchParams();
        if (params.cursor) query.set('cursor', params.cursor);
        if (params.limit != null) query.set('limit', String(params.limit));
        const qs = query.toString();
        return await this.httpClient.get<ReconcileQueue>(
            `/meal-plans/reconcile-queue${qs ? `?${qs}` : ''}`,
        );
    };

    /** The read-only reconcile **log** (`include_resolved=true`): every
     *  past-day meal with a receipt, whatever its outcome, newest-first. This
     *  is what auto mode shows instead of the confirm-each runner. Same page
     *  shape as the queue. */
    getReconcileLogAsync = async (
        params: { cursor?: string; limit?: number } = {},
    ): Promise<ReconcileQueue> => {
        const query = new URLSearchParams({ include_resolved: 'true' });
        if (params.cursor) query.set('cursor', params.cursor);
        if (params.limit != null) query.set('limit', String(params.limit));
        return await this.httpClient.get<ReconcileQueue>(
            `/meal-plans/reconcile-queue?${query.toString()}`,
        );
    };

    submitReconcileVerbAsync = async (
        entryId: string, command: ReconcileVerbCommand,
    ): Promise<ReconcileVerbResult> =>
        await this.httpClient.post<ReconcileVerbResult, ReconcileVerbCommand>(
            `/meal-plans/reconcile/${entryId}`, command,
        );
}

/** Mirrors RecipeSwapCandidate from dora_api swap_suggestions.py. */
export type RecipeSwapCandidate = {
    kind: 'recipe';
    entry_id: string;
    entry_scheduled_for: string;
    entry_slot: string;
    from_recipe_id: string;
    from_recipe_name: string;
    to_recipe_id: string;
    to_recipe_name: string;
    saved: number;
    reason_chip: 'cheaper_recipe_cookable' | 'cheaper_recipe_similar' | 'cheaper_recipe_household_fav';
    missing_ingredient_names: string[];
};

export type SwapSuggestions = {
    projected_over: boolean;
    cost_per_week: number;
    cost_per_week_priced_ratio: { priced: number; total: number; unpriced_recipe_ids: string[] };
    budget_amount: number | null;
    overshoot: number;
    projected_after_applying_all: number;
    candidates: RecipeSwapCandidate[];
};

export type ApplySwapCommand = {
    kind: 'recipe';
    entry_id: string;
    to_recipe_id: string;
    expected_from_recipe_id?: string;
    /** FU-637 — which axis suggested this. Omitted = 'budget' (the original
     *  caller). Decides which feature gate the server applies: a lighter swap
     *  is unrelated to money and must work with spend-tracking off. */
    reason?: 'budget' | 'lighter';
};

/** FU-637 — one lighter alternative for a planned meal. */
export type LighterAlternative = {
    to_recipe_id: string;
    to_recipe_name: string;
    kcal_per_serving: number;
    saved_kcal: number;
    reason_chip: string;
    missing_ingredient_names: string[];
};

export type LighterAlternatives = {
    entry_id: string;
    from_recipe_id: string;
    from_recipe_name: string;
    from_kcal_per_serving: number | null;
    candidates: LighterAlternative[];
};

export type ApplySwapResult = {
    swap_ledger_id: string;
    new_cost_per_week: number;
    new_projected_over: boolean;
};

export type UndoSwapResult = {
    new_cost_per_week: number;
    new_projected_over: boolean;
};

// ── FU-317 — meal-plan reconcile ────────────────────────────────────────

/** Verb vocabulary — must stay in sync with
 *  `dora_api/features/meal_plans/reconcile.py`'s `_ALLOWED_VERBS`. */
export type ReconcileVerb =
    | 'cooked'
    | 'cooked_adjusted'
    | 'cooked_later'
    | 'not_cooked'
    | 'skip';

/** Receipt state — mirror of
 *  `dora_api/domain/entities/meal_plan_reconcile_receipt.py`. */
export type ReconcileState =
    | 'unresolved_auto'
    | 'unresolved_manual'
    | 'resolved_confirmed'
    | 'resolved_adjusted'
    | 'resolved_not_cooked'
    | 'resolved_deferred';

export type ReconcileEntry = {
    entry_id: string;
    scheduled_for: string;   // ISO date
    slot: string;
    planned_servings: number;
    recipe: { id: string; name: string };
    receipt: {
        state: ReconcileState;
        original_servings: number;
        actual_servings: number | null;
        cooked_on: string | null;
        created_at: string;
    };
};

export type ReconcileQueue = {
    entries: ReconcileEntry[];
    next_cursor: string | null;
    total: number;
};

export type ReconcileVerbCommand = {
    verb: ReconcileVerb;
    /** Required when `verb === 'cooked_adjusted'`. */
    actual_servings?: number;
    /** Required when `verb === 'cooked_later'`. ISO date. */
    cooked_on?: string;
    /** Free-form user note; persisted on the receipt (surfaced in the
     *  history view Chunk 5 doesn't ship). */
    note?: string;
};

export type ReconcileVerbResult = {
    entry_id: string;
    new_pool: number;
    /** True when the verb didn't change anything (same latest-receipt
     *  state + fields as the incoming call). */
    idempotent: boolean;
    receipt: {
        state: ReconcileState;
        original_servings: number;
        actual_servings: number | null;
        cooked_on: string | null;
        created_at: string;
    };
};
