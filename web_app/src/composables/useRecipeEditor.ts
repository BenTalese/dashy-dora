// The recipe edit model — form shape, hydrate-from-server, and
// build-the-PATCH — extracted on 2026-08-20 from the recipe page the redesign
// replaced, so the redesigned page renders a *different page* over the *same*
// rules rather than a second copy of them (R-001 / R-003).
//
// Everything here was lifted verbatim from that page; the comments explaining
// each rule came with it, because the rules are the valuable part:
//   • client_id reuse — an existing `recipe_ingredient_id` / `section_id` /
//     `step_id` doubles as the client id, so unchanged rows round-trip and the
//     cross-references between steps, ingredients and sections stay valid.
//   • true PATCH semantics — only scalars that actually changed are sent, so
//     re-saving an untouched name can't trip the name-uniqueness check.
//     Arrays are always sent (replace semantics).
//   • non-destructive mode switching — `steps[]` is only replaced while the
//     user is *in* structured mode, and `step_images[]` only when they were
//     touched, so flipping modes never destroys the other mode's content.
//
// The duplicate inline copy this file used to warn about went with the old
// page on 2026-08-26 (FU-688). `RecipeDetailPage.vue` is now the only consumer,
// and this is the only copy of these rules.

import { reactive } from 'vue';
import { recipeStepImageUrl } from 'src/services/api/recipeApiService';
import type { EditableStepImage } from 'src/components/recipes/recipeStepImageEditorTypes';
import type { EditableStep as EditableRecipeStep } from 'src/components/recipes/recipeStepEditorTypes';
import type { Recipe, RecipeStepsMode } from 'src/models/recipe';
import type {
    CreateRecipeIngredientCommand,
    RecipeStepCommand,
    UpdateRecipeCommand,
} from 'src/services/api/recipeApiService';

export type IngredientForm = CreateRecipeIngredientCommand;

/** The editable subset of one ingredient row — everything
 *  `RecipeIngredientRowEditor` can change. `client_id` is the row's identity
 *  and is deliberately absent: an edit never re-identifies a row, because the
 *  id is what lets an unchanged row round-trip and keeps a structured step's
 *  `ingredient_client_ids` pointing at the right thing. */
export type IngredientPatch = {
    stock_item_id: string | null;
    raw_text: string | null;
    quantity: number | null;
    unit: string | null;
    notes: string | null;
    section_client_id: string | null;
    is_optional: boolean;
    label: string | null;
    preferred_buy_id: string | null;
    selected_product_id: string | null;
};

export type SectionForm = {
    client_id: string;
    sequence: number;
    name: string;
};

export type RecipeForm = {
    name: string;
    category_id: string | null;
    cook_time_minutes: number | null;
    cuisine_id: string | null;
    difficulty: string | null;
    instructions: string | null;
    notes: string | null;
    prep_time_minutes: number | null;
    recipe_collection_id: string | null;
    servings: number | null;
    source: string | null;
    time_of_day: string | null;
    ingredients: IngredientForm[];
    dietary_tag_ids: string[];
    tool_ids: string[];
    /** null = no change (existing image, shown via the endpoint). A data URL
     *  sets a new image; explicit null + `imageDirty` clears it. */
    image: string | null;
    steps: EditableRecipeStep[];
    /** `structured` sends `steps[]`; `freeform` sends an empty `steps[]` so the
     *  server clears structure; `image` sends `step_images[]`. */
    steps_mode: RecipeStepsMode;
    step_images: EditableStepImage[];
    kcal: number | null;
    /** Named ingredient/step groups. Empty list = flat recipe. */
    sections: SectionForm[];
};

/** `v-model.number` leaves an empty field as `''` and a non-numeric clear as
 *  `NaN`. The server expects `int | None`, so coerce at the wire boundary. */
export function toIntOrNull(value: unknown): number | null {
    if (value === null || value === undefined || value === '') return null;
    const n = typeof value === 'number' ? value : Number(value);
    if (!Number.isFinite(n)) return null;
    return Math.trunc(n);
}

export function emptyRecipeForm(): RecipeForm {
    return {
        name: '',
        category_id: null,
        cook_time_minutes: null,
        cuisine_id: null,
        difficulty: null,
        instructions: null,
        notes: null,
        prep_time_minutes: null,
        recipe_collection_id: null,
        servings: null,
        source: null,
        time_of_day: null,
        ingredients: [],
        dietary_tag_ids: [],
        tool_ids: [],
        image: null,
        steps: [],
        // Owner call 2026-08-27: free text is what a new recipe should start
        // as. Typing a method out is the thing everyone does; structuring it
        // step-by-step, with per-step ingredient and tool links, is the thing
        // you graduate to on a recipe you cook often. This matches the
        // server's own default for `POST /recipes` — a form that opened on
        // `structured` was the only place the two disagreed.
        steps_mode: 'freeform',
        step_images: [],
        kcal: null,
        sections: [],
    };
}

/** Overwrite `form` in place from a freshly-loaded recipe. */
export function hydrateRecipeForm(form: RecipeForm, source: Recipe): void {
    const ingredients = source.ingredients.map((i) => ({
        stock_item_id: i.stock_item_id,
        // Carry the free-text label through load so an unlinked ingredient
        // still shows what it was — without this the row renders nameless.
        raw_text: i.raw_text,
        quantity: i.quantity,
        unit: i.unit,
        notes: i.notes,
        client_id: i.recipe_ingredient_id,
        section_client_id: i.section_id,
        is_optional: i.is_optional ?? false,
        label: i.label,
        preferred_buy_id: i.preferred_buy_id,
        selected_product_id: i.selected_product_id,
    }));
    const sections: SectionForm[] = (source.sections ?? []).map((s) => ({
        client_id: s.section_id,
        sequence: s.sequence,
        name: s.name,
    }));
    const steps: EditableRecipeStep[] = (source.steps ?? []).map((s) => ({
        client_id: s.step_id,
        parent_client_id: s.parent_step_id,
        sequence: s.sequence,
        text: s.text,
        hint: s.hint,
        ingredient_client_ids: [...s.ingredient_ids],
        tool_ids: [...s.tool_ids],
        section_client_id: s.section_id,
        timer_minutes: s.timer_minutes ?? null,
    }));
    Object.assign(form, {
        name: source.name,
        category_id: source.category_id,
        cook_time_minutes: source.cook_time_minutes,
        cuisine_id: source.cuisine_id,
        difficulty: source.difficulty,
        instructions: source.instructions,
        notes: source.notes,
        prep_time_minutes: source.prep_time_minutes,
        recipe_collection_id: source.recipe_collection_id,
        servings: source.servings,
        source: source.source,
        time_of_day: source.time_of_day,
        ingredients,
        dietary_tag_ids: [...(source.dietary_tag_ids ?? [])],
        tool_ids: [...(source.tool_ids ?? [])],
        image: null,
        steps,
        // Trust the server's declared steps_mode rather than re-deriving it;
        // the fallback covers rows written before the column existed.
        steps_mode: source.steps_mode
            ?? (source.has_structured_steps ? 'structured' : 'freeform'),
        step_images: (source.step_images ?? []).map((img) => ({
            client_id: img.image_id,
            existing_image_id: img.image_id,
            preview_url: recipeStepImageUrl(source.recipe_id, img.image_id),
            data_url: '',
        })),
        kcal: source.kcal,
        sections,
    });
}

/** Build the PATCH body for `form` against the recipe it was hydrated from. */
export function buildUpdateCommand(
    form: RecipeForm,
    src: Recipe,
    dirty: { image: boolean; stepImages: boolean },
): UpdateRecipeCommand {
    const command: UpdateRecipeCommand = {
        recipe_id: src.recipe_id,
        ingredients: form.ingredients,
        dietary_tag_ids: form.dietary_tag_ids,
        tool_ids: form.tool_ids,
        // Sections always ride along with the ingredient replace so a renamed
        // section keeps its rows. Empty array = clear all; rows fall back to
        // the implicit main group via ON DELETE SET NULL on the server.
        sections: form.sections.map((s, i) => ({
            client_id: s.client_id,
            sequence: i,
            name: (s.name || '').trim() || 'Untitled section',
        })),
    };
    if (dirty.image) command.image = form.image;
    if (form.name !== src.name) command.name = form.name;
    if (form.category_id !== src.category_id) command.category_id = form.category_id;
    if (form.cuisine_id !== src.cuisine_id) command.cuisine_id = form.cuisine_id;
    if (form.cook_time_minutes !== src.cook_time_minutes) command.cook_time_minutes = toIntOrNull(form.cook_time_minutes);
    if (form.difficulty !== src.difficulty) command.difficulty = form.difficulty;
    if (form.instructions !== src.instructions) command.instructions = form.instructions;
    if (form.notes !== src.notes) command.notes = form.notes;
    if (form.steps_mode === 'structured') {
        const stepsToSend: RecipeStepCommand[] = form.steps.map((s) => ({
            client_id: s.client_id,
            parent_client_id: s.parent_client_id,
            sequence: s.sequence,
            text: s.text,
            hint: s.hint,
            ingredient_client_ids: [...s.ingredient_client_ids],
            tool_ids: [...s.tool_ids],
            // Sub-steps stay null (no picker on depth-1 rows); the server
            // flattens them by parent.
            section_client_id: s.parent_client_id === null ? s.section_client_id : null,
            timer_minutes: s.timer_minutes,
        }));
        command.steps = stepsToSend;
    }
    if (form.steps_mode !== src.steps_mode) command.steps_mode = form.steps_mode;
    if (dirty.stepImages) {
        // Full replace, in display order: a saved image rides along as its
        // image id (the server keeps it), a new upload as its data URL.
        command.step_images = form.step_images
            .map((img) => img.existing_image_id ?? img.data_url)
            .filter((s) => !!s);
    }
    if (form.prep_time_minutes !== src.prep_time_minutes) command.prep_time_minutes = toIntOrNull(form.prep_time_minutes);
    if (form.recipe_collection_id !== src.recipe_collection_id) command.recipe_collection_id = form.recipe_collection_id;
    if (form.servings !== src.servings) command.servings = toIntOrNull(form.servings);
    if (form.source !== src.source) command.source = form.source;
    if (form.time_of_day !== src.time_of_day) command.time_of_day = form.time_of_day;
    if (form.kcal !== src.kcal) command.kcal = toIntOrNull(form.kcal);
    return command;
}

/** A fresh reactive form. Sugar so pages don't import `reactive` + `emptyRecipeForm`. */
export function useRecipeForm() {
    return reactive<RecipeForm>(emptyRecipeForm());
}
