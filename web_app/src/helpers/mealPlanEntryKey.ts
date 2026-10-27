import type { MealPlanEntry } from 'src/models/mealPlan';

/**
 * Stable `v-for` keys for a list of planned meals.
 *
 * **Why not `meal_plan_entry_id`.** `PATCH /meal-plans/{id}` keeps a forward
 * entry's id when the row names it (FU-878 match-and-update), but a row without
 * one, and anything the cook-batch rebuild re-mints, comes back as a new entry
 * with a new id. Keyed on that id, Vue would remount any card whose entry the
 * save re-created.
 *
 * That is invisible until something lives *inside* a card across an edit — and
 * one thing does: the entry menu's servings stepper. Owner report 2026-09-05:
 * *"tapping increase or decrease servings on mobile once hides the dropdown for
 * a meal slot. To increase by 3 you have to tap 6 times."* Each tap saved the
 * week, the card remounted, and the `q-menu` inside it went with it.
 *
 * The key is therefore the entry's *content identity* — the three fields that
 * say which meal this is, none of which a servings change touches. A day+slot
 * that genuinely holds the same recipe twice gets an occurrence suffix, so the
 * keys stay unique without pretending the two rows are one.
 *
 * The database id is still the identity for everything else (writes, batch
 * membership, reconcile). This is a rendering concern only.
 */
export type KeyedMealPlanEntry = { key: string; entry: MealPlanEntry };

export function keyedEntries(entries: MealPlanEntry[]): KeyedMealPlanEntry[] {
    const seen = new Map<string, number>();
    return entries.map((entry) => {
        const base = `${String(entry.scheduled_for)}|${entry.slot}|${entry.recipe_id}`;
        const occurrence = seen.get(base) ?? 0;
        seen.set(base, occurrence + 1);
        return { key: occurrence === 0 ? base : `${base}#${occurrence}`, entry };
    });
}
