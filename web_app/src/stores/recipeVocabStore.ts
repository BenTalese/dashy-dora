import { acceptHMRUpdate, defineStore } from 'pinia';
import type { Category, Cuisine, DietaryTag, Tool } from 'src/models/recipeVocab';
import CategoryApiService from 'src/services/api/categoryApiService';
import CuisineApiService from 'src/services/api/cuisineApiService';
import DietaryTagApiService from 'src/services/api/dietaryTagApiService';
import ToolApiService from 'src/services/api/toolApiService';
import type { Ref } from 'vue';
import { computed, ref } from 'vue';

// shared cache of the three recipe vocabularies, consumed by
// the cookbook overview filters and the recipe edit surfaces. The settings
// pages talk to the api services directly (CRUD); this store is read-mostly.

const cuisineApi = new CuisineApiService();
const categoryApi = new CategoryApiService();
const dietaryTagApi = new DietaryTagApiService();
const toolApi = new ToolApiService();

export const useRecipeVocabStore = defineStore('recipeVocab', () => {
    const cuisines: Ref<Cuisine[]> = ref([]);
    const categories: Ref<Category[]> = ref([]);
    const dietaryTags: Ref<DietaryTag[]> = ref([]);
    const tools: Ref<Tool[]> = ref([]);

    const getCuisinesAsync = async () => {
        cuisines.value = await cuisineApi.getAllAsync();
    };
    const getCategoriesAsync = async () => {
        categories.value = await categoryApi.getAllAsync();
    };
    const getDietaryTagsAsync = async () => {
        dietaryTags.value = await dietaryTagApi.getAllAsync();
    };
    const getToolsAsync = async () => {
        tools.value = await toolApi.getAllAsync();
    };

    // Picker options, one mapping for every surface (finalisation 01-R14).
    const cuisineOptions = computed(() => cuisines.value.map((c) => ({ label: c.name, value: c.cuisine_id })));
    const categoryOptions = computed(() => categories.value.map((c) => ({ label: c.name, value: c.category_id })));
    const dietaryTagOptions = computed(() =>
        dietaryTags.value.map((t) => ({ label: t.name, value: t.dietary_tag_id, category: t.category })));
    const toolOptions = computed(() => tools.value.map((t) => ({ label: t.name, value: t.tool_id })));

    let hydrated = false;
    let inflight: Promise<void> | null = null;

    const getAllAsync = async () => {
        await Promise.all([
            getCuisinesAsync(),
            getCategoriesAsync(),
            getDietaryTagsAsync(),
            getToolsAsync(),
        ]);
        hydrated = true;
    };

    /** R-016 — lazy hydration. The vocab tables are reference data; settings
     *  CRUD bypasses the store and talks to the api services directly, so
     *  callers reading the cached vocab can short-circuit on second visits. */
    const ensureLoadedAsync = (): Promise<void> => {
        if (hydrated) return Promise.resolve();
        inflight ??= getAllAsync().finally(() => { inflight = null; });
        return inflight;
    };

    return {
        cuisines,
        categories,
        dietaryTags,
        tools,
        cuisineOptions,
        categoryOptions,
        dietaryTagOptions,
        toolOptions,
        getCuisinesAsync,
        getCategoriesAsync,
        getDietaryTagsAsync,
        getToolsAsync,
        getAllAsync,
        ensureLoadedAsync,
    };
});

if (import.meta.hot) {
    import.meta.hot.accept(acceptHMRUpdate(useRecipeVocabStore, import.meta.hot));
}
