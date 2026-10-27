import type {
    ApplyTemplateResult,
    MealPlanTemplateDetail,
    MealPlanTemplateSummary,
    RecurringApplyResult,
} from 'src/models/mealPlanTemplate';
import type { CreatedResponse } from './axiosHttpClient';
import AxiosHttpClient from './axiosHttpClient';

export type CreateMealPlanTemplateCommand = {
    name: string;
    description?: string;
    /** Snapshot this week's plan into a template. */
    source_meal_plan_id: string;
};

export type UpdateMealPlanTemplateCommand = {
    name?: string;
    description?: string;
};

export type ApplyTemplateCommand = {
    template_id: string;
    /** Monday (ISO) of the week to fork onto. */
    monday_of_week: string;
};

export type ApplyRecurringCommand = {
    /** Exactly one of these. */
    template_id?: string;
    template_set_id?: string;
    start_monday: string;
    end_monday: string;
};

export default class MealPlanTemplateApiService {
    private httpClient = new AxiosHttpClient();

    getAllAsync = async (): Promise<MealPlanTemplateSummary[]> =>
        await this.httpClient.get<MealPlanTemplateSummary[]>('/meal-plan-templates');

    getDetailAsync = async (id: string): Promise<MealPlanTemplateDetail> =>
        await this.httpClient.get<MealPlanTemplateDetail>(`/meal-plan-templates/${id}`);

    createFromPlanAsync = async (command: CreateMealPlanTemplateCommand): Promise<CreatedResponse> =>
        await this.httpClient.post<CreatedResponse>('/meal-plan-templates', command);

    updateAsync = async (id: string, command: UpdateMealPlanTemplateCommand): Promise<void> =>
        await this.httpClient.patch<void>(`/meal-plan-templates/${id}`, command);

    deleteAsync = async (id: string): Promise<void> =>
        await this.httpClient.delete(`/meal-plan-templates/${id}`);

    /** Fork a week from a template (skips past days server-side). */
    applyAsync = async (command: ApplyTemplateCommand): Promise<ApplyTemplateResult> =>
        await this.httpClient.post<ApplyTemplateResult>('/meal-plans/from-template', command);

    /** Recurring apply of a template OR a rotating set over a week range. */
    applyRecurringAsync = async (command: ApplyRecurringCommand): Promise<RecurringApplyResult> =>
        await this.httpClient.post<RecurringApplyResult>('/meal-plans/from-template/recurring', command);
}
