/**
 * Owner feedback 2026-08-27 — `helpers/addToListRows` is the seam that lets
 * recipes and meal plans share one add-to-list dialog. It is the right place
 * for tests because it holds the *rules* (required-wins, band ordering,
 * "what requires this") in plain functions, with no component or store around
 * them, and those rules are what would silently drift if the two surfaces ever
 * grew their own mappers again.
 */
import { describe, expect, it, vi } from 'vitest';

// `formatQuantity` reads the household locale from `useMoney`, whose policy
// probe would pull axios/Quasar into this node run; stub it so the defaults
// (en-AU) stand.
vi.mock('src/services/api/healthApiService', () => ({
    default: class {
        getInfoAsync() {
            return new Promise(() => undefined);
        }
    },
    invalidateHealthInfo: () => undefined,
}));

import {
    rowsFromMealPlanIngredients, rowsFromRecipe, unlinkedFromMealPlan,
    unlinkedFromRecipe,
} from 'src/helpers/addToListRows';
import type { MealPlanIngredient } from 'src/models/mealPlan';
import type { Recipe } from 'src/models/recipe';

function ingredient(over: Record<string, unknown> = {}) {
    return {
        recipe_ingredient_id: `ri-${Math.random()}`,
        stock_item_id: 'si-1',
        stock_item_name: 'Flour',
        stock_level_id: null,
        stock_location_id: null,
        stock_location_name: null,
        quantity: 100,
        unit: 'g',
        notes: null,
        is_missing: false,
        is_low_stock: false,
        section_id: null,
        is_optional: false,
        raw_text: null,
        expiry_date: null,
        ...over,
    };
}

function recipe(ingredients: ReturnType<typeof ingredient>[], name = 'Pancakes') {
    return { recipe_id: 'r-1', name, ingredients } as unknown as Recipe;
}

function planIngredient(over: Partial<MealPlanIngredient> = {}): MealPlanIngredient {
    return {
        stock_item_id: 'si-1',
        stock_item_name: 'Flour',
        total_quantity: 100,
        unit: 'g',
        used_in_recipe_ids: [],
        is_optional: false,
        ...over,
    };
}

// ── recipe rows ────────────────────────────────────────────────────────────

describe('rowsFromRecipe', () => {
    it('drops unlinked ingredients from the tickable rows', () => {
        const rows = rowsFromRecipe(recipe([
            ingredient(),
            ingredient({ stock_item_id: null, raw_text: '1 cup of something' }),
        ]));

        expect(rows).toHaveLength(1);
        expect(rows[0]!.name).toBe('Flour');
    });

    it('reports those unlinked ingredients separately, named by their recipe', () => {
        const unlinked = unlinkedFromRecipe(recipe([
            ingredient({ stock_item_id: null, raw_text: '1 cup of something' }),
        ]));

        expect(unlinked).toEqual([
            { sourceName: 'Pancakes', ingredientName: '1 cup of something' },
        ]);
    });

    it('names an unlinked row with no raw text rather than leaving it blank', () => {
        const unlinked = unlinkedFromRecipe(recipe([
            ingredient({ stock_item_id: null, raw_text: '  ' }),
        ]));

        expect(unlinked[0]!.ingredientName).toBe('(unnamed ingredient)');
    });

    it('lets a required row beat an optional one for the same stock item', () => {
        // §1.9 — we'd rather over-stock than under-stock, so the item has to
        // land in the ticked-by-default section.
        const rows = rowsFromRecipe(recipe([
            ingredient({ is_optional: true }),
            ingredient({ is_optional: false }),
        ]));

        expect(rows).toHaveLength(1);
        expect(rows[0]!.isOptional).toBe(false);
    });

    it('keeps a stock item missing if any of its rows says so', () => {
        const rows = rowsFromRecipe(recipe([
            ingredient({ is_missing: false }),
            ingredient({ is_missing: true }),
        ]));

        expect(rows[0]!.isMissing).toBe(true);
    });

    it('orders missing, then low, then the rest — alphabetical within a band', () => {
        const rows = rowsFromRecipe(recipe([
            ingredient({ stock_item_id: 'a', stock_item_name: 'Zucchini' }),
            ingredient({ stock_item_id: 'b', stock_item_name: 'Butter', is_low_stock: true }),
            ingredient({ stock_item_id: 'c', stock_item_name: 'Yeast', is_missing: true }),
            ingredient({ stock_item_id: 'd', stock_item_name: 'Apples' }),
        ]));

        expect(rows.map((r) => r.name)).toEqual(['Yeast', 'Butter', 'Apples', 'Zucchini']);
    });

    it('leaves `sources` empty — you opened this from the recipe', () => {
        const rows = rowsFromRecipe(recipe([ingredient()]));

        expect(rows[0]!.sources).toEqual([]);
    });

    it('formats the quantity through the shared unit-spacing rule', () => {
        const rows = rowsFromRecipe(recipe([ingredient({ quantity: 100, unit: 'g' })]));

        expect(rows[0]!.quantityLabel).toBe('100g');
    });

    it('has no quantity label when the ingredient carries neither figure', () => {
        const rows = rowsFromRecipe(recipe([ingredient({ quantity: null, unit: null })]));

        expect(rows[0]!.quantityLabel).toBeNull();
    });

    it('is empty for a null recipe rather than throwing', () => {
        expect(rowsFromRecipe(null)).toEqual([]);
        expect(unlinkedFromRecipe(null)).toEqual([]);
    });
});

// ── meal-plan rows ─────────────────────────────────────────────────────────

describe('rowsFromMealPlanIngredients', () => {
    const nameById = (id: string) => ({ r1: 'Chilli', r2: 'Nachos' }[id] ?? null);
    const nothingMissing = () => false;

    it('names every recipe that requires the item, alphabetically', () => {
        const rows = rowsFromMealPlanIngredients(
            [planIngredient({ used_in_recipe_ids: ['r2', 'r1'] })],
            nameById, nothingMissing, nothingMissing,
        );

        expect(rows[0]!.sources).toEqual(['Chilli', 'Nachos']);
    });

    it('skips a recipe it cannot name rather than printing a raw id', () => {
        const rows = rowsFromMealPlanIngredients(
            [planIngredient({ used_in_recipe_ids: ['r1', 'gone'] })],
            nameById, nothingMissing, nothingMissing,
        );

        expect(rows[0]!.sources).toEqual(['Chilli']);
    });

    it('takes the stock bands from the caller, not the payload', () => {
        // The aggregate carries no per-item stock verdict — unlike a recipe
        // ingredient, which gets one from the server.
        const rows = rowsFromMealPlanIngredients(
            [planIngredient()],
            nameById, () => true, () => false,
        );

        expect(rows[0]!.isMissing).toBe(true);
    });

    it('rounds the scaled aggregate to something writable on a list', () => {
        const rows = rowsFromMealPlanIngredients(
            [planIngredient({ total_quantity: 2.6666666666666665, unit: 'cloves' })],
            nameById, nothingMissing, nothingMissing,
        );

        expect(rows[0]!.quantityLabel).toBe('2.67 cloves');
    });

    it('carries the server\'s week-wide optional flag through untouched', () => {
        const rows = rowsFromMealPlanIngredients(
            [planIngredient({ is_optional: true })],
            nameById, nothingMissing, nothingMissing,
        );

        expect(rows[0]!.isOptional).toBe(true);
    });

    it('maps the unlinked report into the dialog\'s shape', () => {
        expect(unlinkedFromMealPlan([
            {
                recipe_name: 'Chilli', ingredient_name: 'a pinch of luck',
                recipe_id: 'r-1', quantity: null, unit: null,
            },
        ])).toEqual([
            { sourceName: 'Chilli', ingredientName: 'a pinch of luck' },
        ]);
    });
});
