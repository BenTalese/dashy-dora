import type { Recipe, RecipeStepsMode, RecipeTagCatalogue } from 'src/models/recipe';
import AxiosHttpClient, { resolveBaseURL } from './axiosHttpClient';
import { fetchAllPages, type Page } from './queryStringBuilder';

/** C-4 Chunk 5 — URL for a recipe's image (served as raw bytes). Pass a
 *  `version` (e.g. a counter bumped after upload) to bust the browser cache. */
export function recipeImageUrl(recipeId: string, version?: number | string): string {
    const base = resolveBaseURL();
    const suffix = version !== undefined ? `?v=${encodeURIComponent(String(version))}` : '';
    return `${base}/recipes/${recipeId}/image${suffix}`;
}

/** PROPOSAL_RECIPE_IMAGE_STEPS — URL for a single step image (raw bytes). */
export function recipeStepImageUrl(
    recipeId: string,
    imageId: string,
    version?: number | string,
): string {
    const base = resolveBaseURL();
    const suffix = version !== undefined ? `?v=${encodeURIComponent(String(version))}` : '';
    return `${base}/recipes/${recipeId}/step-images/${imageId}${suffix}`;
}

export type CreateRecipeIngredientCommand = {
    /** IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 — send `stock_item_id` when
     *  the ingredient is linked, `raw_text` when it's unlinked, or both
     *  (after a bulk-link operation). At least one is required
     *  server-side. Existing "quick-add" flows still send stock_item_id
     *  only; the paste importer (Chunk 5) sends raw_text only. */
    stock_item_id: string | null;
    raw_text?: string | null;
    quantity: number | null;
    unit: string | null;
    notes: string | null;
    /** C-4 Chunk 6 — optional client-side identifier so a structured step's
     *  `ingredient_client_ids` can reference this row before the server has
     *  assigned a real UUID. Any unique string works; the editor uses crypto
     *  randomUUID. Omit when no step references this ingredient. */
    client_id?: string;
    /** C-4 Chunk 10 — optional section grouping; references one of the
     *  sibling sections by `client_id` (or its real UUID when sections
     *  are not being replaced in this payload). Omit/null = unsectioned. */
    section_client_id?: string | null;
    /** Cookbook revision §1.9 — optional flag. Default false; omitted by
     *  legacy editors (the server defaults to false anyway). */
    is_optional?: boolean;
    /** Which one of the stock item this recipe means. A preferred buy or
     *  product must belong to `stock_item_id` (422 otherwise). */
    label?: string | null;
    preferred_buy_id?: string | null;
    selected_product_id?: string | null;
};

/** C-4 Chunk 10 — a named section on the create/update payload. */
export type RecipeSectionCommand = {
    client_id: string;
    sequence: number;
    name: string;
};

/** C-4 Chunk 6 — one structured step (or sub-step) on a create/update
 *  payload. `client_id` is required so steps can refer to one another
 *  (parent_client_id) and to ingredients (ingredient_client_ids) before
 *  the server has issued real ids. `ingredient_client_ids` accepts either
 *  the matching ingredient's `client_id` from the same payload, or — on
 *  update without an `ingredients` replace — the existing
 *  `recipe_ingredient_id`. The server resolves both forms. */
export type RecipeStepCommand = {
    client_id: string;
    parent_client_id: string | null;
    sequence: number;
    text: string;
    hint: string | null;
    ingredient_client_ids: string[];
    tool_ids: string[];
    /** C-4 Chunk 10 — optional section grouping for top-level steps. */
    section_client_id?: string | null;
    /** Owner feedback 2026-09-01 — a declared countdown for this step, in
     *  minutes. Null means none, and cook mode falls back to sniffing the
     *  step text for a duration. */
    timer_minutes?: number | null;
};

export type CreateRecipeCommand = {
    name: string;
    // cuisine + category are FK vocabulary ids (single-select).
    category_id: string | null;
    cook_time_minutes: number | null;
    cuisine_id: string | null;
    difficulty: string | null;
    instructions: string | null;
    /** RD-29 — free-text personal notes about the recipe. */
    notes?: string | null;
    prep_time_minutes: number | null;
    recipe_collection_id: string | null;
    servings: number | null;
    /** C-4 Chunk 7 — origin URL for imported recipes. */
    source?: string | null;
    time_of_day: string | null;
    ingredients: CreateRecipeIngredientCommand[];
    /** C-4 Chunk 2 — dietary tag ids (FK to DietaryTag). */
    dietary_tag_ids?: string[];
    /** C-4 Chunk 5 — tool ids (FK to Tool). */
    tool_ids?: string[];
    /** C-4 Chunk 5 — image as a data-URL string, or null/omitted for none. */
    image?: string | null;
    /** C-4 Chunk 6 — structured steps. Empty/omitted = unstructured. */
    steps?: RecipeStepCommand[];
    /** C-4 Chunk 9 — simple nutrition kcal. */
    kcal?: number | null;
    /** C-4 Chunk 10 — named sections. Empty/omitted = flat recipe. */
    sections?: RecipeSectionCommand[];
    /** PROPOSAL_RECIPE_IMAGE_STEPS — which step payload cook mode and the
     *  detail page should render. Defaults server-side to 'freeform'. */
    steps_mode?: RecipeStepsMode;
    /** PROPOSAL_RECIPE_IMAGE_STEPS — ordered data-URL strings for image
     *  mode. Omit/empty when not using image mode. */
    step_images?: string[];
};

export type UpdateRecipeCommand = {
    recipe_id: string;
    name?: string;
    category_id?: string | null;
    cook_time_minutes?: number | null;
    cuisine_id?: string | null;
    difficulty?: string | null;
    instructions?: string | null;
    /** RD-29 — free-text personal notes. Explicit null clears. */
    notes?: string | null;
    is_favourite?: boolean;
    prep_time_minutes?: number | null;
    recipe_collection_id?: string | null;
    servings?: number | null;
    /** C-4 Chunk 7 — origin URL. Explicit null clears it. */
    source?: string | null;
    time_of_day?: string | null;
    ingredients?: CreateRecipeIngredientCommand[];
    /** C-4 Chunk 2/5 — when present, replaces the full tag/tool set. Empty
     *  array clears; omit to leave untouched. */
    dietary_tag_ids?: string[];
    tool_ids?: string[];
    /** C-4 Chunk 5 — data-URL string to set the image, null to clear, omit to
     *  leave untouched. */
    image?: string | null;
    /** C-4 Chunk 6 — structured steps. Present (even as []) = replace the
     *  full set; empty list clears all structure and the recipe falls back
     *  to plain `instructions`. Omit to leave existing steps untouched. */
    steps?: RecipeStepCommand[];
    /** C-4 Chunk 9 — simple nutrition kcal. Explicit null clears it. */
    kcal?: number | null;
    /** C-4 Chunk 10 — named sections. Present (even as []) = replace; an
     *  empty list clears all sections and rows fall back to the implicit
     *  "main" group via ON DELETE SET NULL. Omit to leave untouched. */
    sections?: RecipeSectionCommand[];
    /** PROPOSAL_RECIPE_IMAGE_STEPS — flip which step payload is active.
     *  Omit to leave untouched. */
    steps_mode?: RecipeStepsMode;
    /** PROPOSAL_RECIPE_IMAGE_STEPS — present (even as []) = replace the
     *  full step image set. Mode flip without this field is
     *  non-destructive (rows stay in place). */
    step_images?: string[];
};

/** P2-08 — query filters for the recipes endpoint. Mirrors the
 *  `tags_include / tags_exclude / ingredient_exclude` query params the
 *  backend accepts; each is an array that's URL-encoded as repeated
 *  params. */
export type RecipeFilterArgs = {
    tags_include?: string[];
    tags_exclude?: string[];
    ingredient_exclude?: string[];
    /** State-ownership §3.3 — query cookability server-side instead of
     *  fetching every recipe + the whole pantry to filter in the browser.
     *  `cookable` true/false matches the recipe's `cookable` field;
     *  `max_missing` keeps recipes with at most N missing ingredients. */
    cookable?: boolean;
    max_missing?: number;
    /** C-waste W4 — when set, narrow the list to recipes using ≥1
     *  in-stock ingredient expiring within the horizon, and populate
     *  `expiring_ingredient_count` on the returned recipes. */
    expiring_within_days?: number;
    /** Standard pagination. Omitted = the server's defaults (page 1,
     *  limit 50) — which silently truncates any cookbook past 50
     *  recipes, so list surfaces page with `getAllPagesAsync` instead. */
    page?: number;
    limit?: number;
};

export default class RecipeApiService {
    private httpClient: AxiosHttpClient;

    constructor() {
        this.httpClient = new AxiosHttpClient();
    }

    /** The 201 body is the full recipe DTO (`create_recipe.py`). */
    createAsync = async (recipeToCreate: CreateRecipeCommand): Promise<Recipe> =>
        await this.httpClient.post<Recipe>('/recipes', recipeToCreate);

    // copies the recipe into a sibling version (same
    // `version_group_id`). If the source had no group id yet, the server
    // allocates one and back-fills the source so both rows form the group.
    createNewVersionAsync = async (recipeId: string): Promise<Recipe> =>
        await this.httpClient.post<Recipe>(
            `/recipes/${recipeId}/new-version`,
            {},
        );

    deleteAsync = async (recipeId: string): Promise<void> =>
        await this.httpClient.delete(`/recipes/${recipeId}`);

    // hits the real detail endpoint so the response carries
    // `steps[]` + `version_siblings[]`. Filtering the list endpoint by id
    // (the old shape) only returned the list-shape DTO, which silently
    // dropped structured-step + version data for everything downstream.
    getAsync = async (recipeId: string): Promise<Recipe> =>
        await this.httpClient.get<Recipe>(`/recipes/${recipeId}`);

    getAllAsync = async (filters?: RecipeFilterArgs): Promise<Page<Recipe>> => {
        const qs = encodeFilterQueryString(filters);
        return await this.httpClient.get<Page<Recipe>>(`/recipes${qs}`);
    };

    /** Every recipe, paged (FU-035): the cookbook filters and searches
     *  client-side over whatever the store holds. */
    getAllPagesAsync = async (filters?: RecipeFilterArgs): Promise<Recipe[]> =>
        await fetchAllPages((page, limit) => this.getAllAsync({ ...filters, page, limit }));

    /** P2-08 — pulls the canonical tag catalogue + disclaimer. The
     *  SPA caches this for the session; the picker re-renders on
     *  change but the list itself is stable across requests. */
    getTagCatalogueAsync = async (): Promise<RecipeTagCatalogue> =>
        await this.httpClient.get<RecipeTagCatalogue>('/recipes/tags');

    updateAsync = async (recipeToUpdate: UpdateRecipeCommand): Promise<void> => {
        const { recipe_id, ...payload } = recipeToUpdate;
        await this.httpClient.patch<void>(`/recipes/${recipe_id}`, payload);
    };

    cookAsync = async (recipeId: string, mealsCooked: number): Promise<{ available_meals: number }> =>
        await this.httpClient.post<{ available_meals: number }, { meals_cooked: number }>(
            `/recipes/${recipeId}/cook`,
            { meals_cooked: mealsCooked },
        );

    adjustMealsAsync = async (recipeId: string, delta: number): Promise<{ available_meals: number }> =>
        await this.httpClient.post<{ available_meals: number }, { delta: number }>(
            `/recipes/${recipeId}/adjust-meals`,
            { delta },
        );

    /** IMPL_PLAN_RECIPE_IMPORTER §Chunk 5 — replaces `importFromUrlAsync`.
     *  Server no longer fetches URLs; the user pastes the recipe text
     *  and (optionally) types the source URL for provenance.
     *  ``source_url`` is metadata only — stamped on the response but
     *  never opened by the server. */
    importFromContentAsync = async (
        content: string,
        sourceUrl?: string,
    ): Promise<ImportedRecipe> =>
        await this.httpClient.post<ImportedRecipe, { content: string; source_url: string }>(
            '/recipes/import-from-content',
            { content, source_url: sourceUrl ?? '' },
        );

    /** IMPL_PLAN_RECIPE_IMPORTER §Chunk 6 — bulk-linker page reads.
     *  Returns every unlinked RecipeIngredient row grouped by
     *  normalised raw_text (server-owned normalisation — see
     *  `normalise_raw_text` in the backend), sorted by count desc /
     *  text asc. */
    getUnlinkedIngredientsAsync = async (): Promise<UnlinkedIngredients> =>
        await this.httpClient.get<UnlinkedIngredients>('/recipes/unlinked-ingredients');

    /** IMPL_PLAN_RECIPE_IMPORTER §Chunk 6 — atomically link every
     *  unlinked RecipeIngredient row whose normalised raw_text
     *  matches to `stockItemId`. One round-trip per group; cookability
     *  re-derives at the next `GET /recipes` (server-owned, R-003). */
    bulkLinkUnlinkedIngredientsAsync = async (
        rawText: string,
        stockItemId: string,
    ): Promise<{ linked_count: number }> =>
        await this.httpClient.post<{ linked_count: number }, { raw_text: string; stock_item_id: string }>(
            '/recipes/unlinked-ingredients/bulk-link',
            { raw_text: rawText, stock_item_id: stockItemId },
        );
}

/** IMPL_PLAN_RECIPE_IMPORTER §Chunk 6 — mirrors
 *  `UnlinkedIngredientGroupDto` / `UnlinkedIngredientsDto`. */
export type UnlinkedIngredientGroup = {
    raw_text: string;
    used_in_recipe_ids: string[];
    count: number;
};
export type UnlinkedIngredients = {
    unlinked: UnlinkedIngredientGroup[];
};

// Mirrors ImportedRecipeDto / ImportedIngredientDto from
// dora_api/features/recipes/imported_recipe_dtos.py.
export type ImportedIngredient = {
    raw_text: string;
    stock_item_id: string | null;
    stock_item_name: string | null;
    match_score: number;
    quantity: number | null;
    unit: string | null;
    notes: string | null;
};

function encodeFilterQueryString(filters?: RecipeFilterArgs): string {
    if (!filters) return '';
    const params = new URLSearchParams();
    for (const tag of filters.tags_include ?? []) {
        if (tag) params.append('tags_include', tag);
    }
    for (const tag of filters.tags_exclude ?? []) {
        if (tag) params.append('tags_exclude', tag);
    }
    for (const term of filters.ingredient_exclude ?? []) {
        if (term) params.append('ingredient_exclude', term);
    }
    if (filters.cookable !== undefined) {
        params.append('cookable', String(filters.cookable));
    }
    if (filters.max_missing !== undefined) {
        params.append('max_missing', String(filters.max_missing));
    }
    if (filters.expiring_within_days !== undefined) {
        params.append('expiring_within_days', String(filters.expiring_within_days));
    }
    if (filters.page !== undefined) {
        params.append('page', String(filters.page));
    }
    if (filters.limit !== undefined) {
        params.append('limit', String(filters.limit));
    }
    const out = params.toString();
    return out ? `?${out}` : '';
}

export type ImportedRecipe = {
    name: string;
    // importer resolves parsed names to existing vocab ids when
    // it can; the id is null (with the parsed name kept) when there's no match.
    cuisine_id: string | null;
    cuisine_name: string | null;
    category_id: string | null;
    category_name: string | null;
    difficulty: string | null;
    servings: number | null;
    prep_time_minutes: number | null;
    cook_time_minutes: number | null;
    /** IMPL_PLAN_RECIPE_IMPORTER §Chunk 2 — some sites publish only a
     *  total time. Populated only when the parser explicitly extracts
     *  one; never derived from prep + cook. */
    total_time_minutes: number | null;
    instructions: string | null;
    /** IMPL_PLAN_RECIPE_IMPORTER §Chunk 5 — echoes whatever URL the
     *  user typed in the "Where's this from?" field of the paste dialog.
     *  Metadata only; the server never fetched it. Empty string when
     *  the user didn't provide one. */
    source_url: string;
    ingredients: ImportedIngredient[];
    /** C-4 Chunk 6 — parsed structured steps ready to feed into the
     *  create endpoint's `steps[]`. Empty when the parser produced a
     *  freeform ``instructions`` blob only. */
    steps: ImportedStep[];
    /** IMPL_PLAN_RECIPE_IMPORTER §Chunk 5 — true when the parser fell
     *  back to its lowest-shape output (typically < 3 ingredients).
     *  SPA shows a "couldn't auto-structure — review and edit" banner. */
    is_degraded: boolean;
};

export type ImportedStep = {
    client_id: string;
    parent_client_id: string | null;
    sequence: number;
    text: string;
    hint: string | null;
};
