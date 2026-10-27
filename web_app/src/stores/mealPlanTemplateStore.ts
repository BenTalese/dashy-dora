import { acceptHMRUpdate, defineStore } from 'pinia';
import type {
    ApplyTemplateResult,
    MealPlanTemplateSummary,
    RecurringApplyResult,
} from 'src/models/mealPlanTemplate';
import MealPlanTemplateApiService, {
    type ApplyRecurringCommand,
    type ApplyTemplateCommand,
    type CreateMealPlanTemplateCommand,
    type UpdateMealPlanTemplateCommand,
} from 'src/services/api/mealPlanTemplateApiService';
import type { Ref } from 'vue';
import { ref } from 'vue';

const api = new MealPlanTemplateApiService();

export const useMealPlanTemplateStore = defineStore('mealPlanTemplate', () => {
    const templates: Ref<MealPlanTemplateSummary[]> = ref([]);

    const getTemplatesAsync = async () => {
        templates.value = await api.getAllAsync();
    };

    const createFromPlanAsync = async (command: CreateMealPlanTemplateCommand) => {
        await api.createFromPlanAsync(command);
        await getTemplatesAsync();
    };

    const updateAsync = async (id: string, command: UpdateMealPlanTemplateCommand) => {
        await api.updateAsync(id, command);
        await getTemplatesAsync();
    };

    const deleteAsync = async (id: string) => {
        await api.deleteAsync(id);
        await getTemplatesAsync();
    };

    // Apply returns its result for the caller's toast; the planner refreshes
    // its own plan and ingredient state after.
    const applyAsync = async (command: ApplyTemplateCommand): Promise<ApplyTemplateResult> =>
        await api.applyAsync(command);

    const applyRecurringAsync = async (command: ApplyRecurringCommand): Promise<RecurringApplyResult> =>
        await api.applyRecurringAsync(command);

    return {
        templates,
        getTemplatesAsync,
        createFromPlanAsync,
        updateAsync,
        deleteAsync,
        applyAsync,
        applyRecurringAsync,
    };
});

if (import.meta.hot) {
    import.meta.hot.accept(acceptHMRUpdate(useMealPlanTemplateStore, import.meta.hot));
}
