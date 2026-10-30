import { acceptHMRUpdate, defineStore } from 'pinia';
import type {
    MealPlan, MealPlanIngredients, MealPlanSuggestion,
} from 'src/models/mealPlan';
import MealPlanApiService, {
    type CreateMealPlanCommand,
    type UpdateMealPlanCommand,
} from 'src/services/api/mealPlanApiService';
import type { Ref } from 'vue';
import { ref } from 'vue';

const api = new MealPlanApiService();

export const useMealPlanStore = defineStore('mealPlan', () => {
    const mealPlans: Ref<MealPlan[]> = ref([]);
    // Household "today" (ISO) in the install's timezone — server-owned (C-2.K).
    const today: Ref<string | null> = ref(null);

    const getMealPlansAsync = async () => {
        mealPlans.value = await api.getAllPagesAsync();
    };

    const createMealPlanAsync = async (command: CreateMealPlanCommand) => {
        await api.createAsync(command);
        await getMealPlansAsync();
    };

    const updateMealPlanAsync = async (command: UpdateMealPlanCommand) => {
        await api.updateAsync(command);
        await getMealPlansAsync();
    };

    const deleteMealPlanAsync = async (id: string) => {
        await api.deleteAsync(id);
        mealPlans.value = mealPlans.value.filter((p) => p.meal_plan_id !== id);
    };

    const getIngredientsForPlanAsync = async (id: string): Promise<MealPlanIngredients> =>
        await api.getIngredientsAsync(id);

    /** BRIEF_MEAL_PLANNER_RAIL_AND_SHELL §4.4 — the rail's ranked suggestions
     *  for one week. Deliberately NOT cached in the store: the ranking is only
     *  valid for the week it was asked about (it excludes what's already
     *  planned there), so the caller owns the week-scoped cache and the store
     *  stays a pass-through. */
    const getWeekSuggestionsAsync = async (
        weekStart: string,
    ): Promise<MealPlanSuggestion[]> =>
        (await api.getWeekSuggestionsAsync(weekStart)).suggestions;

    const getTodayAsync = async () => {
        today.value = await api.getTodayAsync();
    };

    return {
        mealPlans,
        today,
        getMealPlansAsync,
        createMealPlanAsync,
        updateMealPlanAsync,
        deleteMealPlanAsync,
        getIngredientsForPlanAsync,
        getWeekSuggestionsAsync,
        getTodayAsync,
    };
});

if (import.meta.hot) {
    import.meta.hot.accept(acceptHMRUpdate(useMealPlanStore, import.meta.hot));
}
