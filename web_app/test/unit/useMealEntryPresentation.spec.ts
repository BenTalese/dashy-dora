// The two meal cards (desktop chip, phone card) draw one meal from this
// composable (02-R19b), so a drift between breakpoints shows up here.
import { describe, expect, it, vi } from 'vitest';
import { ref } from 'vue';

import type { MealPlanEntry } from 'src/models/mealPlan';

const batch = ref(true);
const money = ref(true);
vi.mock('src/composables/useBatchEnabled', () => ({ useBatchEnabled: () => ({ batchEnabled: batch }) }));
vi.mock('src/composables/useMoneyEnabled', () => ({ useMoneyEnabled: () => ({ moneyEnabled: money }) }));
vi.mock('src/composables/useMoney', () => ({ formatMoney: (n: number) => `$${n.toFixed(2)}` }));

const { useMealEntryPresentation } = await import('src/composables/useMealEntryPresentation');

function entry(over: Partial<MealPlanEntry> = {}): MealPlanEntry {
    return {
        meal_plan_entry_id: 'id-1', recipe_id: 'recipe-1', recipe_name: 'Ragu',
        scheduled_for: '2026-09-14', servings: 2, slot: 'Dinner', consumed_at: null,
        cook_time_minutes: null, category_name: null, cuisine_name: null, has_image: false,
        cook_batch_id: null, is_cook_day: false, cook_batch_total_servings: null,
        cook_batch_size: null, kcal_per_serving: null, kcal_is_reliable: false,
        inference_hint: null, inference_stock_item_names: [], needs_cooking: false,
        cook_batch_pending: false, cook_fresh: false, estimated_cost: null, missing_count: 0,
        cook_batch_estimated_cost: null,
        ...over,
    };
}

function present(e: MealPlanEntry, shortfall = false) {
    return useMealEntryPresentation(() => e, () => shortfall);
}

describe('useMealEntryPresentation', () => {
    it('names a batch cook day by what the cook produces', () => {
        const p = present(entry({ cook_batch_id: 'b', is_cook_day: true, cook_batch_total_servings: 6 }));
        expect(p.linked.value).toBe(true);
        expect(p.cookMarkerLabel.value).toBe('Cook day · 6 servings');
        expect(p.accessibleLabel.value).toBe('Ragu, Dinner, 2 servings, cook day of a batch');
    });

    it('prices a batch on its cook day only', () => {
        const cook = present(entry({ cook_batch_id: 'b', is_cook_day: true, cook_batch_estimated_cost: 12 }));
        const leftover = present(entry({ cook_batch_id: 'b', is_cook_day: false, cook_batch_estimated_cost: 12 }));
        expect(cook.priceLabel.value).toBe('$12.00');
        expect(leftover.priceLabel.value).toBe('');
        expect(leftover.cookMarkerLabel.value).toBe('Leftovers');
    });

    it('prices a standalone meal and hides money when it is off', () => {
        expect(present(entry({ estimated_cost: 4.5 })).priceLabel.value).toBe('$4.50');
        money.value = false;
        expect(present(entry({ estimated_cost: 4.5 })).priceLabel.value).toBe('');
        money.value = true;
    });

    it('says fresh, cooked and needs-cooking in words', () => {
        expect(present(entry({ cook_fresh: true })).accessibleLabel.value)
            .toBe('Ragu, Dinner, 2 servings, cooked fresh on the day');
        expect(present(entry({ consumed_at: '2026-09-14T10:00:00Z' })).accessibleLabel.value)
            .toBe('Ragu, Dinner, 2 servings, cooked');
        expect(present(entry(), true).accessibleLabel.value).toBe('Ragu, Dinner, 2 servings, needs cooking');
    });

    it('drops batch vocabulary for a fresh household', () => {
        batch.value = false;
        const p = present(entry({ cook_batch_id: 'b', cook_fresh: true }), true);
        expect(p.linked.value).toBe(false);
        expect(p.fresh.value).toBe(false);
        expect(p.accessibleLabel.value).toBe('Ragu, Dinner, 2 servings');
        batch.value = true;
    });

    it('explains Dora\'s hunch either way', () => {
        expect(present(entry({ inference_hint: 'at_risk', inference_stock_item_names: ['milk'] }))
            .inferenceTooltip.value).toBe('Dora thinks you may have run out of milk since you planned this.');
    });
});
