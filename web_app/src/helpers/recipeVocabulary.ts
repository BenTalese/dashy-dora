// Cookbook card revision (§1.7 + §1.12) — closed-set vocabularies for
// `Recipe.difficulty` and `Recipe.time_of_day`. The values are generated from
// `dora_api/domain/entities/recipe.py` (`generated/recipe_vocabulary.ts`,
// R-089); this module adds the client-side helpers around them.
//
// the meal-slot vocabulary is now the household-wide `MealSlot`
// table (mealSlotStore / `/api/meal-slots`). `DEFAULT_MEAL_SLOTS` here is
// kept only as the seeded default + a pre-first-load fallback for the slot
// dropdowns — the store is the live source of truth once loaded.

import { DEFAULT_MEAL_SLOTS, DIFFICULTY_VALUES, type Difficulty, type MealSlot } from 'src/generated/recipe_vocabulary';

export { DEFAULT_MEAL_SLOTS, DIFFICULTY_VALUES, type Difficulty, type MealSlot };

/** The difficulty picker's options (one copy for every surface). */
export const DIFFICULTY_OPTIONS: Difficulty[] = [...DIFFICULTY_VALUES];

export const DIFFICULTY_RANK: Record<Difficulty, number> = {
    Easy: 0,
    Medium: 1,
    Hard: 2,
};

