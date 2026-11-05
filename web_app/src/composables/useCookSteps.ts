import { stripLeadingOrdinal } from 'src/helpers/stepOrdinal';
/**
 * Cook mode's step model (FU-942, split out of `RecipeCookMode.vue`): the
 * flattener that turns a recipe's method into one linear sequence, the
 * current step's ingredient / tool highlights and the current step's timer
 * duration. The flattener and the text match are pure and exported so they
 * can be pinned by a spec (`test/unit/cookSteps.spec.ts`).
 */
import { computed, type Ref } from 'vue';

import { formatQuantity } from 'src/helpers/formatQuantity';
import { scaleQuantity } from 'src/helpers/scaleQuantity';
import type { Recipe, RecipeIngredient } from 'src/models/recipe';

// step model. Structured recipes (Chunk 4) carry a
// flat `recipe.steps[]` with optional parent_step_id for one level of
// sub-steps and per-step ingredient/tool references; we flatten that to
// a linear sequence (top, its subs, next top, …) for navigation.
// Unstructured recipes fall back to splitting `instructions` on newline.
export type CookStep = {
    text: string;
    hint: string | null;
    ingredientIds: string[]; // references RecipeIngredient.recipe_ingredient_id
    toolIds: string[];       // references Tool.tool_id
    isSubStep: boolean;
    // name of the section this step belongs to (the
    // sub-step inherits its parent's section so the header doesn't
    // flicker mid-group). Null when the step is unsectioned.
    sectionName: string | null;
    // Owner feedback 2026-09-01 — the timer the cook *declared* on this
    // step, in minutes. Only a structured step can carry one; free-text
    // and photo faces leave it null and fall back to the text sniff.
    timerMinutes: number | null;
};

/** The recipe fields the flattener reads. */
export type CookStepSource = Pick<Recipe, 'steps_mode' | 'steps' | 'sections' | 'instructions'>;

/** Owner feedback 2026-08-27 — *"how does cook mode pick which steps it
 *  will follow? I've got all 3 filled out and it's picking structured when
 *  I've got free text picked on the recipe view."*
 *
 *  It picked structured because it only ever branched on `'image'` and
 *  otherwise preferred `steps[]` whenever the array was non-empty. Mode
 *  switching is deliberately **non-destructive** (all three payloads coexist
 *  — see `useRecipeEditor`), so "structured steps exist" says nothing about
 *  which face the user chose. `steps_mode` is the single source of truth for
 *  that (R-003), and cook mode now reads it rather than re-deriving an
 *  answer from the payloads.
 *
 *  The one fallback that remains is honest rather than a guess: a recipe in
 *  `structured` mode with an empty `steps[]` has nothing to render, so we
 *  fall back to the free-text split instead of showing a single
 *  "No instructions provided." card over instructions that do exist. */
function usesStructuredSteps(recipe: CookStepSource | null): boolean {
    return recipe?.steps_mode === 'structured'
        && (recipe?.steps?.length ?? 0) > 0;
}

/** Flatten a recipe's method into the linear sequence cook mode steps
 *  through. Pure — the spec pins ordering, section inheritance and the
 *  free-text fallback. */
export function flattenCookSteps(recipe: CookStepSource | null): CookStep[] {
    const structured = recipe?.steps ?? [];
    const sectionById = new Map(
        (recipe?.sections ?? []).map((s) => [s.section_id, s]),
    );
    const sectionName = (id: string | null) =>
        id ? (sectionById.get(id)?.name ?? null) : null;
    // `usesStructuredSteps`, not `structured.length > 0` — the recipe's
    // chosen `steps_mode` decides, not which payloads happen to be filled in.
    if (usesStructuredSteps(recipe)) {
        const flat: CookStep[] = [];
        const tops = structured
            .filter((s) => s.parent_step_id === null)
            .sort((a, b) => a.sequence - b.sequence);
        for (const top of tops) {
            flat.push({
                text: top.text,
                hint: top.hint,
                ingredientIds: [...top.ingredient_ids],
                toolIds: [...top.tool_ids],
                isSubStep: false,
                sectionName: sectionName(top.section_id),
                timerMinutes: top.timer_minutes ?? null,
            });
            const subs = structured
                .filter((s) => s.parent_step_id === top.step_id)
                .sort((a, b) => a.sequence - b.sequence);
            for (const sub of subs) {
                flat.push({
                    text: sub.text,
                    hint: sub.hint,
                    ingredientIds: [...sub.ingredient_ids],
                    toolIds: [...sub.tool_ids],
                    isSubStep: true,
                    sectionName: sectionName(top.section_id),
                    timerMinutes: sub.timer_minutes ?? null,
                });
            }
        }
        return flat;
    }
    // Unstructured fallback — same shape, empty refs.
    const raw = recipe?.instructions;
    if (!raw) {
        return [{
            text: 'No instructions provided.',
            hint: null,
            ingredientIds: [],
            toolIds: [],
            isSubStep: false,
            sectionName: null,
            timerMinutes: null,
        }];
    }
    const parts = raw
        .split(/\r?\n+/)
        .map((s) => stripLeadingOrdinal(s.trim()))
        .filter((s) => s.length > 0);
    const lines = parts.length > 0 ? parts : [raw];
    return lines.map((t) => ({
        text: t,
        hint: null,
        ingredientIds: [],
        toolIds: [],
        isSubStep: false,
        sectionName: null,
        timerMinutes: null,
    }));
}

// per-step highlight. Structured recipes use the step's
// own `ingredient_ids` / `tool_ids` lists; unstructured recipes fall
// back to matching ingredient names inside the step text (same logic
// as the pre-Chunk-5 auto-mark behaviour, repurposed for visual
// highlight rather than tick state).
export function stepIngredientIds(
    step: CookStep | null,
    ingredients: ReadonlyArray<Pick<RecipeIngredient, 'recipe_ingredient_id' | 'label' | 'stock_item_name' | 'raw_text'>>,
): Set<string> {
    if (!step) return new Set();
    if (step.ingredientIds.length > 0) {
        return new Set(step.ingredientIds);
    }
    // Unstructured fallback — text match.
    const text = step.text.toLowerCase();
    const matched = new Set<string>();
    for (const ing of ingredients) {
        // Chunk 4 — unlinked ingredients have no stock_item_name.
        // Fall back to raw_text for matching so paste-imported
        // recipes still get highlighted where possible.
        // A recipe that calls its cheese "cheddar" says "cheddar" in
        // its steps, so the chosen name is tried as well as the item's.
        const names = [ing.label, ing.stock_item_name ?? ing.raw_text];
        if (names.some((n) => n && text.includes(n.toLowerCase()))) {
            matched.add(ing.recipe_ingredient_id);
        }
    }
    return matched;
}

/** The old whole-app behaviour: read a duration out of the step's prose.
 *  Kept, because it is the only thing a free-text or photo method can
 *  offer — there is nowhere on a line of prose to record "this step is
 *  timed". Now a *fallback*, not the mechanism.
 */
export function sniffTimerMinutes(stepText: string): number | null {
    const text = stepText.toLowerCase();
    const minMatch = text.match(/(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|m\b)/);
    if (minMatch) return parseFloat(minMatch[1]!);
    const hourMatch = text.match(/(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h\b)/);
    if (hourMatch) return parseFloat(hourMatch[1]!) * 60;
    return null;
}

/** Format a recipe ingredient's quantity for display, rescaled to the
 *  current headcount and routed through `formatQuantity` for unit
 *  spacing. The two helpers are deliberately separate — `scaleQuantity`
 *  owns the rounding (DEC-4), `formatQuantity` owns the spacing (DEC-3).
 *  Returns an empty string when both quantity and unit are null. Shared by
 *  the ingredients panel and the spoken "Ingredients" answer, so both say
 *  the same amount. */
export function cookQuantityLabel(
    quantity: number | null | undefined,
    unit: string | null | undefined,
    baseServings: number | null,
    cookingFor: number,
): string {
    const scaled = scaleQuantity(quantity, baseServings, cookingFor, unit);
    return formatQuantity(scaled, unit);
}

export function useCookSteps(recipe: Ref<Recipe | null>, currentStepIndex: Ref<number>) {
    const cookSteps = computed<CookStep[]>(() => flattenCookSteps(recipe.value));

    // Linear step text (consumed by the speech / nav / timer code that
    // existed before structured steps landed).
    const steps = computed(() => cookSteps.value.map((s) => s.text));

    const currentStep = computed(() => steps.value[currentStepIndex.value] ?? '');
    const currentStepObject = computed<CookStep | null>(
        () => cookSteps.value[currentStepIndex.value] ?? null,
    );

    const highlightedIngredientIds = computed<Set<string>>(
        () => stepIngredientIds(currentStepObject.value, recipe.value?.ingredients ?? []),
    );

    const highlightedToolIds = computed<Set<string>>(() => {
        const step = currentStepObject.value;
        if (!step) return new Set();
        return new Set(step.toolIds);
    });

    const sniffedTimerMinutes = computed<number | null>(() => sniffTimerMinutes(currentStep.value));

    /** Owner feedback 2026-09-01: *"How does the timer function get added? Is
     *  it guessing? … for structured I feel a tickable box option should be
     *  added"*. A structured step can now declare `timer_minutes`, and a
     *  declared timer always wins over the sniff — including where the step's
     *  wording disagrees with it ("reduce by half, about 20 minutes" on a step
     *  the cook actually timed at 25).
     */
    const timerIsDeclared = computed(() => currentStepObject.value?.timerMinutes != null);

    const stepTimerMinutes = computed<number | null>(
        () => currentStepObject.value?.timerMinutes ?? sniffedTimerMinutes.value,
    );

    return {
        cookSteps,
        steps,
        currentStep,
        currentStepObject,
        highlightedIngredientIds,
        highlightedToolIds,
        timerIsDeclared,
        stepTimerMinutes,
    };
}
