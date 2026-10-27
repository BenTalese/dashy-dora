import { acceptHMRUpdate, defineStore } from 'pinia';
import { nameCollator } from 'src/composables/useMoney';
import type { Recipe, RecipeCollection } from 'src/models/recipe';
import type { CreateRecipeCommand, UpdateRecipeCommand } from 'src/services/api/recipeApiService';
import RecipeApiService from 'src/services/api/recipeApiService';
import type {
    CreateRecipeCollectionCommand,
    UpdateRecipeCollectionCommand
} from 'src/services/api/recipeCollectionApiService';
import RecipeCollectionApiService from 'src/services/api/recipeCollectionApiService';
import type { Ref } from 'vue';
import { computed, readonly, ref } from 'vue';

const recipeApiService = new RecipeApiService();
const recipeCollectionApiService = new RecipeCollectionApiService();

export const useRecipeStore = defineStore('recipe', () => {
    const recipes: Ref<Recipe[]> = ref([]);
    const recipeCollections: Ref<RecipeCollection[]> = ref([]);

    // Locale-aware collation from the locale authority (finalisation 20-R7).

    const collator = { compare: (a: string, b: string) => nameCollator().compare(a, b) };

    // Reactive so consumers can distinguish "still hydrating" from
    // "hydrated and the id genuinely doesn't resolve" (FU-109 deep-link chip).
    const recipesHydrated = ref(false);
    let recipesInflight: Promise<void> | null = null;
    // Separate from `recipesHydrated` deliberately: the collection is still
    // populated and still renderable, it just no longer matches the server.
    // Flipping `recipesHydrated` back to false instead would make every
    // consumer that distinguishes "hydrating" from "hydrated but absent"
    // (FU-109's deep-link chip) report a missing recipe mid-refetch.
    const recipesStale = ref(false);
    let collectionsHydrated = false;
    let collectionsInflight: Promise<void> | null = null;

    /** Pages until exhausted — the cookbook does its filtering, searching
     *  and sorting over this collection, so a single 50-row page made
     *  every recipe past the first page invisible on the overview. */
    const getRecipesAsync = () =>
        recipeApiService.getAllPagesAsync().then((items) => {
            recipes.value = [...items].sort((a, b) => collator.compare(a.name, b.name));
            recipesHydrated.value = true;
            recipesStale.value = false;
        });

    const getRecipeCollectionsAsync = () =>
        recipeCollectionApiService.getAllAsync().then((page) => {
            recipeCollections.value = [...page.items].sort((a, b) => collator.compare(a.name, b.name));
            collectionsHydrated = true;
        });

    /** R-016 — lazy hydration for the recipes list. Call this in `onMounted`
     *  when you need the collection populated but don't care about a forced
     *  refresh. Call `getRecipesAsync` directly for an explicit refetch
     *  (post-mutation, pull-to-refresh). */
    const ensureLoadedAsync = (): Promise<void> => {
        if (recipesHydrated.value && !recipesStale.value) return Promise.resolve();
        recipesInflight ??= getRecipesAsync().finally(() => { recipesInflight = null; });
        return recipesInflight;
    };

    /** Mark the collection as no longer matching the server, so the next
     *  `ensureLoadedAsync` refetches instead of returning the cached list.
     *
     *  A recipe DTO is not just the recipe: it carries a whole layer of facts
     *  derived from the pantry — `cookable`, `missing_count`,
     *  `expiring_ingredient_count`, the Zero-Input hint, and in complex
     *  nutrition mode the entire rollup behind `kcal_per_serving` and the
     *  front-of-pack rating. Every one of those moves when a stock item does,
     *  and none of them is visible in a diff of the recipe itself. Before
     *  this, `ensureLoadedAsync` was a permanent cache for the session: link a
     *  food to a stock item, walk to the cookbook, and the cards rendered the
     *  payload fetched before the edit — no rating, no kcal, and the
     *  thresholds filtering on figures that were no longer true. */
    const invalidateRecipes = (): void => { recipesStale.value = true; };

    /** R-016 — lazy hydration for the collections list (independent fetch). */
    const ensureCollectionsLoadedAsync = (): Promise<void> => {
        if (collectionsHydrated) return Promise.resolve();
        collectionsInflight ??= getRecipeCollectionsAsync().finally(() => { collectionsInflight = null; });
        return collectionsInflight;
    };

    const createRecipeAsync = async (command: CreateRecipeCommand): Promise<Recipe> => {
        const entity = await recipeApiService.createAsync(command);
        recipes.value.push(entity);
        recipes.value.sort((a, b) => collator.compare(a.name, b.name));
        // callers (RecipeEditDialog) navigate to the new detail
        // page after create, so we hand back the entity we just resolved.
        return entity;
    };

    const updateRecipeAsync = async (command: UpdateRecipeCommand) => {
        await recipeApiService.updateAsync(command);
        const updated = await recipeApiService.getAsync(command.recipe_id);
        const idx = recipes.value.findIndex((r) => r.recipe_id === command.recipe_id);
        if (idx >= 0) {
            recipes.value[idx] = updated;
        } else {
            recipes.value.push(updated);
        }
    };

    const deleteRecipeAsync = async (recipeId: string) => {
        await recipeApiService.deleteAsync(recipeId);
        recipes.value = recipes.value.filter((r) => r.recipe_id !== recipeId);
    };

    const toggleFavouriteAsync = async (recipe: Recipe) =>
        updateRecipeAsync({ recipe_id: recipe.recipe_id, is_favourite: !recipe.is_favourite });

    const cookAsync = async (recipeId: string, mealsCooked: number) => {
        await recipeApiService.cookAsync(recipeId, mealsCooked);
        const updated = await recipeApiService.getAsync(recipeId);
        const idx = recipes.value.findIndex((r) => r.recipe_id === recipeId);
        if (idx >= 0) recipes.value[idx] = updated;
    };

    const adjustMealsAsync = async (recipeId: string, delta: number) => {
        const { available_meals } = await recipeApiService.adjustMealsAsync(recipeId, delta);
        const idx = recipes.value.findIndex((r) => r.recipe_id === recipeId);
        if (idx >= 0) {
            recipes.value[idx] = { ...recipes.value[idx]!, available_meals };
        }
    };

    const createRecipeCollectionAsync = async (command: CreateRecipeCollectionCommand) => {
        await recipeCollectionApiService.createAsync(command);
        await getRecipeCollectionsAsync();
    };

    const updateRecipeCollectionAsync = async (command: UpdateRecipeCollectionCommand) => {
        await recipeCollectionApiService.updateAsync(command);
        await getRecipeCollectionsAsync();
    };

    const deleteRecipeCollectionAsync = async (recipeCollectionId: string) => {
        await recipeCollectionApiService.deleteAsync(recipeCollectionId);
        recipeCollections.value = recipeCollections.value.filter(
            (c) => c.recipe_collection_id !== recipeCollectionId
        );
    };

    const collectionOptions = computed(() =>
        recipeCollections.value.map((c) => ({ label: c.name, value: c.recipe_collection_id })));

    return {
        // Exposed as a plain ref (not readonly): consumers pass recipes into
        // display components and filter helpers typed as mutable Recipe[].
        recipes,
        recipesHydrated: readonly(recipesHydrated),
        recipeCollections: readonly(recipeCollections),
        collectionOptions,
        getRecipesAsync,
        getRecipeCollectionsAsync,
        ensureLoadedAsync,
        ensureCollectionsLoadedAsync,
        invalidateRecipes,
        createRecipeAsync,
        updateRecipeAsync,
        deleteRecipeAsync,
        toggleFavouriteAsync,
        cookAsync,
        adjustMealsAsync,
        createRecipeCollectionAsync,
        updateRecipeCollectionAsync,
        deleteRecipeCollectionAsync
    };
});

if (import.meta.hot) {
    import.meta.hot.accept(acceptHMRUpdate(useRecipeStore, import.meta.hot));
}
