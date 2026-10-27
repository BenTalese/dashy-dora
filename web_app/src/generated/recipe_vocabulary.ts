// THIS FILE IS GENERATED — DO NOT EDIT BY HAND.
// Source of truth: dora_api/domain/entities/recipe.py
// Regenerate via: python scripts/dump_recipe_vocabulary.py
//
// The recipe closed vocabularies the server validates (R-010), so the
// pickers and filters offer exactly what a write accepts.

export const DIFFICULTY_VALUES = ["Easy", "Medium", "Hard"] as const;
export type Difficulty = (typeof DIFFICULTY_VALUES)[number];

export const STEPS_MODES = ["structured", "freeform", "image"] as const;
export type RecipeStepsMode = (typeof STEPS_MODES)[number];

export const DEFAULT_MEAL_SLOTS = ["Breakfast", "Lunch", "Dinner", "Snack", "Dessert"] as const;
export type MealSlot = (typeof DEFAULT_MEAL_SLOTS)[number];
