// Owner feedback 2026-08-27 — maps each surface's own ingredient shape into
// the one row type `AddToListDialog` renders. Kept in a helper rather than in
// either page so the two surfaces can't quietly disagree about what counts as
// missing, optional, or unlinked (R-003).

import type {
    AddToListRow, AddToListUnlinked, LineChoicePick,
} from 'src/components/shoppingList/addToListTypes';
import { formatQuantity } from 'src/helpers/formatQuantity';
import { ingredientDisplayName } from 'src/helpers/recipeIngredientLabel';
import type { MealPlanIngredient, UnlinkedIngredient } from 'src/models/mealPlan';
import type { Recipe } from 'src/models/recipe';

function quantityLabel(quantity: number | null, unit: string | null): string | null {
    if (quantity === null && !unit) return null;
    // `formatQuantity` rounds to two places itself (R-079).
    const label = formatQuantity(quantity, unit);
    return label || null;
}

/**
 * A single recipe's ingredients. `sources` stays empty: you opened this from
 * the recipe, so naming it on every row is noise.
 *
 * When the same stock item appears on both a required and an optional row the
 * *required* commitment wins — we'd rather over-stock than under-stock
 * (cookbook revision §1.9). Dedupe keeps the first row's quantity rather than
 * summing, matching what the picker showed before this helper existed.
 */
export function rowsFromRecipe(recipe: Recipe | null): AddToListRow[] {
    if (!recipe) return [];
    const byId = new Map<string, AddToListRow>();
    for (const ing of recipe.ingredients ?? []) {
        if (ing.stock_item_id === null) continue;
        const existing = byId.get(ing.stock_item_id);
        if (existing) {
            existing.isOptional = existing.isOptional && ing.is_optional;
            existing.isMissing = existing.isMissing || ing.is_missing;
            existing.isLowStock = existing.isLowStock || ing.is_low_stock;
            continue;
        }
        byId.set(ing.stock_item_id, {
            stockItemId: ing.stock_item_id,
            name: ingredientDisplayName(ing),
            isMissing: ing.is_missing,
            isLowStock: ing.is_low_stock,
            isOptional: ing.is_optional,
            quantityLabel: quantityLabel(ing.quantity, ing.unit),
            sources: [],
        });
    }
    return sortRows(Array.from(byId.values()));
}

/** Each item's chosen preferred buy or product, so the shopping line it
 *  becomes starts with the same pick. The first row of an item that chose
 *  anything wins, matching the dedupe in `rowsFromRecipe`. */
export function lineChoicesFromRecipe(recipe: Recipe | null): Map<string, LineChoicePick> {
    const out = new Map<string, LineChoicePick>();
    for (const ing of recipe?.ingredients ?? []) {
        if (ing.stock_item_id === null || out.has(ing.stock_item_id)) continue;
        if (!ing.preferred_buy_id && !ing.selected_product_id) continue;
        out.set(ing.stock_item_id, {
            preferred_buy_id: ing.preferred_buy_id,
            selected_product_id: ing.selected_product_id,
        });
    }
    return out;
}

/** The recipe's own unlinked rows, in the dialog's shape. */
export function unlinkedFromRecipe(recipe: Recipe | null): AddToListUnlinked[] {
    if (!recipe) return [];
    return (recipe.ingredients ?? [])
        .filter((ing) => ing.stock_item_id === null)
        .map((ing) => ({
            sourceName: recipe.name,
            ingredientName: (ing.raw_text ?? '').trim() || '(unnamed ingredient)',
        }));
}

/**
 * A week's aggregated demand. `sources` names the meals that pulled each item
 * in — the aggregate is the one place where an item genuinely has several
 * origins, and "why is celery on here?" is the question it answers.
 *
 * `isMissing` / `isLowStock` come from the caller's stock predicate rather than
 * the payload: unlike a recipe ingredient, the aggregate carries no per-item
 * stock verdict.
 */
export function rowsFromMealPlanIngredients(
    ingredients: MealPlanIngredient[],
    recipeNameById: (recipeId: string) => string | null,
    needsBuying: (stockItemId: string) => boolean,
    isLowStock: (stockItemId: string) => boolean,
): AddToListRow[] {
    return sortRows(ingredients.map((ing) => ({
        stockItemId: ing.stock_item_id,
        name: ing.stock_item_name,
        isMissing: needsBuying(ing.stock_item_id),
        isLowStock: isLowStock(ing.stock_item_id),
        isOptional: ing.is_optional,
        quantityLabel: quantityLabel(ing.total_quantity, ing.unit),
        sources: ing.used_in_recipe_ids
            .map((id) => recipeNameById(id))
            .filter((n): n is string => n !== null)
            .sort((a, b) => a.localeCompare(b)),
    })));
}

export function unlinkedFromMealPlan(unlinked: UnlinkedIngredient[]): AddToListUnlinked[] {
    return unlinked.map((u) => ({
        sourceName: u.recipe_name,
        ingredientName: u.ingredient_name,
    }));
}

/** Missing first, then low, then the rest; alphabetical within each band —
 *  the order the recipe picker has always used. */
function sortRows(rows: AddToListRow[]): AddToListRow[] {
    const rank = (r: AddToListRow) => (r.isMissing ? 0 : r.isLowStock ? 1 : 2);
    return rows.sort((a, b) => {
        const diff = rank(a) - rank(b);
        if (diff !== 0) return diff;
        return a.name.localeCompare(b.name);
    });
}
