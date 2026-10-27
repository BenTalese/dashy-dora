// Shared recipe presentation model — the single authority for everything
// the cookbook derives from a Recipe *for display*: the meta line, the
// chip figures, the cook/cart button colour + wording, and the belief
// tooltip.
//
// Why it exists (R-003): the compact row view added 2026-08-17 renders
// the same recipe as `RecipeCard` in a different shape. Copying the card's
// dozen computeds into the row would mean every future wording or colour
// change had to be made twice, and the two views would silently disagree
// the first time one was missed. Both components now read from here and
// decide only *layout*.
//
// Domain facts (cookable, missing_count, kcal_is_reliable, inference_hint)
// are all server-owned and arrive on the DTO — nothing here re-derives
// them; this is presentation of data in hand.

import { computed, type ComputedRef } from 'vue';
import { storeToRefs } from 'pinia';
import type { Recipe } from 'src/models/recipe';
import { recipeImageUrl } from 'src/services/api/recipeApiService';
import { inferenceTooltip as hintTooltip } from 'src/helpers/inferenceHint';
import { totalMinutes } from 'src/helpers/recipeTime';
import { useRecipeVocabStore } from 'src/stores/recipeVocabStore';

export interface RecipeDisplay {
    /** Prep + cook, or null when neither is set. */
    totalTime: ComputedRef<number | null>;
    /** Ingredient-line count (display of a hydrated list, not a domain rule). */
    ingredientCount: ComputedRef<number>;
    /** Per-serving kcal + whether the figure is solid enough to judge on. */
    kcal: ComputedRef<{ value: number | null; judgeable: boolean }>;
    /** Owner 2026-09-05 — per-serving cost + whether it was worked out from
     *  the whole recipe. Deliberately the same shape as `kcal`: both are a
     *  server-computed per-serving figure that may rest on partial data, and
     *  the row/card render them with the same asterisk convention.
     *
     *  `value` is null when money is off (the server sends nothing), when
     *  nothing on the recipe could be priced, or when the recipe has no
     *  servings — the caller draws nothing in all three cases. */
    cost: ComputedRef<{ value: number | null; judgeable: boolean }>;
    /** Why the cost figure carries an asterisk. Only meaningful when
     *  `cost.judgeable` is false. */
    costTooltip: ComputedRef<string>;
    /** Why the kcal figure carries an asterisk. Only meaningful when
     *  `kcal.judgeable` is false. */
    kcalTooltip: ComputedRef<string>;
    /** "Weeknight dinners · Italian · Dinner · Evening" — collection first,
     *  case-insensitively de-duplicated (DR-4). */
    metaLine: ComputedRef<string>;
    /** Dietary-tag names resolved from the vocabulary store. */
    tagNames: ComputedRef<string[]>;
    /** Distinct stock-item ids the recipe is short of. */
    missingIds: ComputedRef<string[]>;
    /** Server's cookability verdict: true / false / null (unlinked). */
    cookable: ComputedRef<boolean | null>;
    cookButtonColor: ComputedRef<string>;
    cookButtonTooltip: ComputedRef<string>;
    addListTooltip: ComputedRef<string>;
    /** FU-653 — explains the belief chip, naming the items it's about. */
    inferenceTooltip: ComputedRef<string>;
    /** Fallback glyph + colour for a recipe with no photo. */
    initial: ComputedRef<string>;
    mediaStyle: ComputedRef<{ background: string }>;
    imageUrl: ComputedRef<string>;
}

export function useRecipeDisplay(recipe: () => Recipe): RecipeDisplay {
    const { dietaryTags } = storeToRefs(useRecipeVocabStore());

    const totalTime = computed<number | null>(() => totalMinutes(recipe().prep_time_minutes, recipe().cook_time_minutes));

    const ingredientCount = computed(() => recipe().ingredients.length);

    // FU-637 — the server decides which figure this mode carries and whether
    // it's solid enough to judge on; the UI just renders the answer.
    const kcal = computed(() => ({
        value: recipe().kcal_per_serving ?? null,
        judgeable: recipe().kcal_is_reliable === true,
    }));

    // Owner 2026-09-03: "remove 'open it to see what's missing'". The chip is
    // *on* the recipe you would open, so the instruction was telling you to do
    // the thing you were already doing. Lives here rather than in the two
    // components that render it (R-003) — it was the same sentence twice.
    const kcalTooltip = computed(() => 'Worked out from only part of this recipe.');

    // Owner 2026-09-05 — cost on the cookbook. Everything here is a read of a
    // server-owned figure (R-003): the division by servings happens on the
    // server precisely so a recipe with no servings typed in comes back null
    // rather than being treated as serves-1 by whichever component divided.
    //
    // "Judgeable" is the same idea as kcal's: a recipe where only two of six
    // ingredients priced has a real number attached to it, but it is not a
    // number you can rank recipes by without being misled — the cheapest-
    // looking dish on the page is usually just the least-priced one. So the
    // figure still shows (it's the best we have) and wears an asterisk that
    // says what it's missing.
    const cost = computed(() => {
        const r = recipe();
        const total = r.estimated_cost_total_count;
        return {
            value: r.estimated_cost_per_serving ?? null,
            judgeable: total > 0 && r.estimated_cost_priced_count === total,
        };
    });

    const costTooltip = computed(() => {
        const r = recipe();
        return `Based on ${r.estimated_cost_priced_count} of `
            + `${r.estimated_cost_total_count} ingredients. The rest aren't priced yet.`;
    });

    const metaLine = computed(() => {
        // DR-4 (FU-578 #14): dedupe case-insensitively so a recipe whose
        // cuisine and category are the same word doesn't read "Dessert ·
        // Dessert".
        // The collection leads the line. It used to be the cookbook's
        // grouping *layout* (collapsible folders); those hid search results
        // below the fold in a large book, so the folders went and the
        // collection became a fact about the recipe like any other.
        const r = recipe();
        const seen = new Set<string>();
        return [r.recipe_collection_name, r.cuisine_name, r.category_name, r.time_of_day]
            .filter((p): p is string => Boolean(p))
            .filter((p) => {
                const key = p.toLowerCase();
                if (seen.has(key)) return false;
                seen.add(key);
                return true;
            })
            .join(' · ');
    });

    const tagNames = computed(() => {
        const byId = new Map(dietaryTags.value.map((t) => [t.dietary_tag_id, t.name]));
        return (recipe().dietary_tag_ids ?? [])
            .map((id) => byId.get(id))
            .filter((n): n is string => Boolean(n));
    });

    const missingIds = computed(() => [
        ...new Set(
            recipe().ingredients
                .filter((i) => i.is_missing && i.stock_item_id !== null)
                .map((i) => i.stock_item_id as string),
        ),
    ]);

    const cookable = computed(() => recipe().cookable);
    const unlinkedCount = computed(() => recipe().unlinked_ingredient_count ?? 0);

    // Tri-state cook-button colour (IMPL_PLAN_RECIPE_IMPORTER §Chunk 4):
    //   true  → primary ("ready to cook")
    //   false → warning ("missing some ingredients but you can try")
    //   null  → grey ("we don't know — link ingredients to check")
    const cookButtonColor = computed(() => {
        if (cookable.value === null) return 'grey';
        return cookable.value ? 'primary' : 'warning';
    });
    // Owner 2026-09-01: "Tooltip for the cook button should be 'Enter cook
    // mode' and 'Missing X ingredients'. That's it." The old copy explained
    // the cookability *model* ("Cook anyway — …", "Link 3 ingredients to
    // check cookability — this is a stock-item feature") in the one place
    // that can't afford an explanation. The unknown (`null`) case folds into
    // "Enter cook mode": the button does exactly that, and the grey colour
    // already says the verdict is unknown.
    const cookButtonTooltip = computed(() => {
        if (cookable.value === false) {
            const n = missingIds.value.length;
            return `Missing ${n} ingredient${n === 1 ? '' : 's'}`;
        }
        return 'Enter cook mode';
    });

    /** Distinct linked stock items the recipe reads as low (not missing —
     *  `is_low_stock` and `is_missing` are separate server verdicts). */
    const lowIds = computed(() => [
        ...new Set(
            recipe().ingredients
                .filter((i) => i.is_low_stock && !i.is_missing && i.stock_item_id !== null)
                .map((i) => i.stock_item_id as string),
        ),
    ]);

    // Owner 2026-09-01, three states: what the button will add, a warning
    // that stock is thin even though nothing is missing, and the
    // nothing-to-do case. The unlinked (`null`) case keeps its own wording:
    // there, the button genuinely can't work out what to add, and saying
    // "all in stock" would be a claim the app hasn't got.
    const addListTooltip = computed(() => {
        if (cookable.value === null) {
            return `${unlinkedCount.value} ingredient${unlinkedCount.value === 1 ? '' : 's'} need linking first`;
        }
        if (cookable.value === false) {
            return `Add ${missingIds.value.length} missing to a list`;
        }
        return lowIds.value.length > 0 ? 'Some ingredients are low' : 'All ingredients in stock';
    });

    const inferenceTooltip = computed(() =>
        hintTooltip(recipe().inference_hint, recipe().inference_stock_item_names, 'recipe'),
    );

    const initial = computed(() => (recipe().name.trim()[0] ?? '?').toUpperCase());
    const mediaStyle = computed(() => {
        let hash = 0;
        for (const ch of recipe().name) hash = (hash * 31 + ch.charCodeAt(0)) % 360;
        return { background: `hsl(${hash}, 45%, 42%)` };
    });
    const imageUrl = computed(() => recipeImageUrl(recipe().recipe_id));

    return {
        totalTime,
        ingredientCount,
        kcal,
        kcalTooltip,
        cost,
        costTooltip,
        metaLine,
        tagNames,
        missingIds,
        cookable,
        cookButtonColor,
        cookButtonTooltip,
        addListTooltip,
        inferenceTooltip,
        initial,
        mediaStyle,
        imageUrl,
    };
}
