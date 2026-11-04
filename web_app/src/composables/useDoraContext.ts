/**
 * What the Basic-mode rule engine reads about the household: the current page,
 * the user, and getters over the stores (finalisation 11-R30, split out of
 * DoraChat.vue). Getters, not snapshots, so an answer reads the stores at the
 * moment it is asked.
 */
import { storeToRefs } from 'pinia';
import { useRoute } from 'vue-router';
import { ref } from 'vue';

import { localTodayIso } from 'src/helpers/weekDates';
import type { AuthenticatedUser } from 'src/models/auth';
import type { LocationNode } from 'src/models/location';
import AlertApiService from 'src/services/api/alertApiService';
import HealthApiService from 'src/services/api/healthApiService';
import HelpApiService from 'src/services/api/helpApiService';
import type { DoraContext } from 'src/services/doraIntents';
import { useLocationStore } from 'src/stores/locationStore';
import { useMealPlanStore } from 'src/stores/mealPlanStore';
import { useRecipeStore } from 'src/stores/recipeStore';
import { useRecipeVocabStore } from 'src/stores/recipeVocabStore';
import { useShoppingListStore } from 'src/stores/shoppingListStore';
import { useStockItemStore } from 'src/stores/stockItemStore';
import { useStockLevelStore } from 'src/stores/stockLevelStore';

export function useDoraContext(currentUser: () => AuthenticatedUser | null) {
    const route = useRoute();
    const helpApi = new HelpApiService();
    const alertApi = new AlertApiService();
    // The household's expiring-soon window for Basic mode (11-R34); `/health`
    // is probed once per session and shared.
    const expiringSoonWindowDays = ref<number | undefined>(undefined);
    void new HealthApiService().getInfoAsync()
        .then((info) => { expiringSoonWindowDays.value = info.alerts_policy?.expiring_soon_window_days; })
        .catch(() => undefined);

    const recipeVocabStore = useRecipeVocabStore();
    const mealStore = useMealPlanStore();
    const locationStore = useLocationStore();
    const shoppingListStore = useShoppingListStore();
    const { recipes } = storeToRefs(useRecipeStore());
    const { stockItems } = storeToRefs(useStockItemStore());
    const { stockLevels } = storeToRefs(useStockLevelStore());

    function context(): DoraContext {
        return {
            currentPath: route.path,
            username: currentUser()?.username,
            expiringSoonWindowDays: expiringSoonWindowDays.value,
            fetchFoodFact: async () => (await helpApi.getFoodFactAsync()).fact,
            fetchVersion: async () => {
                const v = await helpApi.getVersionAsync();
                return {
                    current: v.current_version,
                    latest: v.latest_version,
                    updateAvailable: v.update_available,
                    releaseUrl: v.release_url,
                };
            },
            fetchAttention: async () => {
                const a = await alertApi.getAlertsAsync();
                return {
                    high: a.high_count,
                    medium: a.medium_count,
                    low: a.low_count,
                    topMessages: a.items.slice(0, 3).map((alert) => alert.message),
                };
            },
            getStock: () => {
                const levels = stockLevels.value;
                const levelById = new Map(levels.map((l) => [l.stock_level_id, l]));
                // Zone name per item from the location tree (the display
                // policy every chip uses — `formatLocation(…, 'zone')`), so
                // Basic-mode "where is X" answers; it used to stamp null for
                // every item (finalisation 11-R4).
                const zoneByItem = new Map<string, string>();
                const walk = (nodes: LocationNode[], zone: string) => {
                    for (const node of nodes) {
                        const zoneName = zone || node.name;
                        for (const item of node.items) zoneByItem.set(item.stock_item_id, zoneName);
                        walk(node.children, zoneName);
                    }
                };
                walk(locationStore.tree, '');
                return stockItems.value.map((s) => {
                    const lvl = levelById.get(s.stock_level_id);
                    return {
                        id: s.stock_item_id,
                        name: s.name,
                        levelName: lvl?.name ?? null,
                        levelSequence: lvl?.sequence ?? null,
                        locationName: zoneByItem.get(s.stock_item_id) ?? null,
                        expiryDate: s.expiry_date ?? null,
                        isEssential: Boolean(s.is_essential),
                        isOpen: Boolean(s.is_open),
                    };
                });
            },
            getRecipes: () => {
                // resolve dietary tag ids → names once per call
                // so the chat handler can substring-match "vegetarian"
                // / "gluten free" against recipes without an N×M scan
                // of the vocab.
                const tagNameById = new Map(
                    (recipeVocabStore.dietaryTags ?? []).map(
                        (t) => [t.dietary_tag_id, t.name],
                    ),
                );
                return recipes.value.map((r) => ({
                    id: r.recipe_id,
                    name: r.name,
                    cuisine: r.cuisine_name,
                    category: r.category_name,
                    cookTimeMinutes: r.cook_time_minutes,
                    isFavourite: Boolean(r.is_favourite),
                    ingredientStockItemIds: r.ingredients
                        .map((i) => i.stock_item_id)
                        .filter((id): id is string => !!id),
                    dietaryTagNames: (r.dietary_tag_ids ?? [])
                        .map((id) => tagNameById.get(id))
                        .filter((n): n is string => !!n),
                    timeOfDay: r.time_of_day ?? null,
                }));
            },
            getShoppingLists: () => shoppingListStore.summaries.map((l) => ({
                id: l.shopping_list_id,
                name: l.display_name,
                itemCount: l.line_count,
                isQuickAddTarget: l.shopping_list_id === shoppingListStore.quickAddTargetListId,
            })),
            getMealPlan: () => {
                const plans = mealStore.mealPlans;
                if (!plans || plans.length === 0) return null;
                // Plans sorted ascending by start_date — pick the soonest one
                // that hasn't fully passed. Surface up to 5 next meal names.
                // Household today from the server (R-021), local date before
                // it loads — never the UTC date (finalisation 11-R33).
                const today = mealStore.today ?? localTodayIso();
                const live = plans.find((p) =>
                    p.entries.some((e) => e.scheduled_for >= today),
                ) ?? plans[plans.length - 1]!;
                const upcoming = [...live.entries]
                    .filter((e) => e.scheduled_for >= today)
                    .sort((a, b) => a.scheduled_for.localeCompare(b.scheduled_for))
                    .slice(0, 5)
                    .map((e) => `${e.scheduled_for}: ${e.recipe_name} (×${e.servings})`);
                const lastDate = live.entries.length
                    ? live.entries.map((e) => e.scheduled_for).sort().at(-1)!
                    : live.start_date;
                return {
                    startDate: live.start_date,
                    endDate: lastDate,
                    upcomingMealNames: upcoming,
                };
            },
        };
    }

    return { context };
}
