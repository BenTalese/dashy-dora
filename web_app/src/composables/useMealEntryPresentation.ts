/**
 * What a planned meal says about itself, shared by the desktop chip
 * (`MealPlanEntryChip`) and the phone card (`MealPlanRichCard`), which draw
 * the same meal at two sizes (finalisation 02-R19b, R-001).
 */
import { computed, toValue, type MaybeRefOrGetter } from 'vue';
import { inferenceTooltip as hintTooltip } from 'src/helpers/inferenceHint';
import { mealCardStatus } from 'src/helpers/mealPlanEntryStatus';
import { formatMoney } from 'src/composables/useMoney';
import { useBatchEnabled } from 'src/composables/useBatchEnabled';
import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
import type { MealPlanEntry } from 'src/models/mealPlan';

function plural(n: number, word: string): string {
    return `${n} ${word}${n === 1 ? '' : 's'}`;
}

export function useMealEntryPresentation(
    entrySource: MaybeRefOrGetter<MealPlanEntry>,
    shortfallSource: MaybeRefOrGetter<boolean>,
) {
    const { batchEnabled } = useBatchEnabled();
    const { moneyEnabled } = useMoneyEnabled();

    // FU-653 — Dora's belief about this meal, as a remark. Names the items and
    // says the plan is unchanged, so it reads as a heads-up rather than an error.
    const inferenceTooltip = computed(() => {
        const entry = toValue(entrySource);
        return hintTooltip(entry.inference_hint, entry.inference_stock_item_names, 'plan');
    });

    // PROPOSAL_MEAL_PLANS_PART_2 — a linked cook batch (one cook, several days),
    // and (owner 2026-09-04) a meal cooked on the day outside the pool. Both
    // only mean something to a Batch-cooking household.
    const linked = computed(() => batchEnabled.value && !!toValue(entrySource).cook_batch_id);
    const fresh = computed(() => batchEnabled.value && toValue(entrySource).cook_fresh);

    // Owner 2026-09-12 — "Cook day · 6 servings": the day's role first, then
    // what that one cook produces.
    const cookMarkerLabel = computed(() => {
        const entry = toValue(entrySource);
        if (!entry.is_cook_day) return 'Leftovers';
        return `Cook day · ${plural(entry.cook_batch_total_servings ?? entry.servings, 'serving')}`;
    });

    const status = computed(
        () => mealCardStatus(toValue(entrySource), batchEnabled.value, toValue(shortfallSource)),
    );

    /** The price chip's text, or '' for no chip. A batch's cook day prices the
     *  whole cook; its leftover days price nothing, because the money is spent
     *  once (owner 2026-09-12). Both figures are server-owned (R-003). */
    const priceLabel = computed(() => {
        if (!moneyEnabled.value) return '';
        const entry = toValue(entrySource);
        if (entry.cook_batch_id !== null) {
            if (!entry.is_cook_day) return '';
            return entry.cook_batch_estimated_cost === null ? '' : formatMoney(entry.cook_batch_estimated_cost);
        }
        return entry.estimated_cost === null ? '' : formatMoney(entry.estimated_cost);
    });

    // R-Phase 6 §4.6 — one label naming recipe, slot, servings and status, so a
    // screen reader hears the whole meal at once. Status is said, not coloured.
    const accessibleLabel = computed(() => {
        const entry = toValue(entrySource);
        let label = `${entry.recipe_name}, ${entry.slot}, ${plural(entry.servings, 'serving')}`;
        if (linked.value) {
            label += entry.is_cook_day ? ', cook day of a batch' : ', leftovers from a batch cook';
        } else if (fresh.value) {
            label += ', cooked fresh on the day';
        }
        if (entry.consumed_at) return `${label}, cooked`;
        if (toValue(shortfallSource) && batchEnabled.value) return `${label}, needs cooking`;
        return label;
    });

    return { inferenceTooltip, linked, fresh, cookMarkerLabel, status, priceLabel, accessibleLabel };
}
