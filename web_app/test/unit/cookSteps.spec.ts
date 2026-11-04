// @vitest-environment jsdom
// Cook mode's step model (FU-942 / CHUNK_04 §D): the flattener is the
// surface's core and had never had a test.
import { describe, expect, it } from 'vitest';

import { flattenCookSteps, sniffTimerMinutes, stepIngredientIds, type CookStepSource } from 'src/composables/useCookSteps';
import type { RecipeStep } from 'src/models/recipe';

function step(over: Partial<RecipeStep> & Pick<RecipeStep, 'step_id' | 'sequence' | 'text'>): RecipeStep {
    return {
        parent_step_id: null,
        hint: null,
        ingredient_ids: [],
        tool_ids: [],
        section_id: null,
        timer_minutes: null,
        ...over,
    };
}

function recipe(over: Partial<CookStepSource>): CookStepSource {
    return { steps_mode: 'structured', steps: [], sections: [], instructions: null, ...over };
}

describe('flattenCookSteps', () => {
    it('orders tops by sequence, each followed by its own sub-steps', () => {
        const flat = flattenCookSteps(recipe({
            steps: [
                step({ step_id: 'b', sequence: 2, text: 'Second' }),
                step({ step_id: 'b1', sequence: 1, text: 'Second, sub', parent_step_id: 'b' }),
                step({ step_id: 'a2', sequence: 2, text: 'First, sub 2', parent_step_id: 'a' }),
                step({ step_id: 'a', sequence: 1, text: 'First', timer_minutes: 10 }),
                step({ step_id: 'a1', sequence: 1, text: 'First, sub 1', parent_step_id: 'a' }),
            ],
        }));
        expect(flat.map((s) => [s.text, s.isSubStep])).toEqual([
            ['First', false],
            ['First, sub 1', true],
            ['First, sub 2', true],
            ['Second', false],
            ['Second, sub', true],
        ]);
        expect(flat[0]!.timerMinutes).toBe(10);
    });

    it("gives a sub-step its parent's section", () => {
        const flat = flattenCookSteps(recipe({
            sections: [{ section_id: 's1', sequence: 1, name: 'Sauce' }],
            steps: [
                step({ step_id: 'a', sequence: 1, text: 'Top', section_id: 's1' }),
                step({ step_id: 'a1', sequence: 1, text: 'Sub', parent_step_id: 'a', section_id: null }),
            ],
        }));
        expect(flat.map((s) => s.sectionName)).toEqual(['Sauce', 'Sauce']);
    });

    it('falls back to the free text when structured mode has no steps', () => {
        const flat = flattenCookSteps(recipe({ steps: [], instructions: 'Boil water\nAdd pasta' }));
        expect(flat.map((s) => s.text)).toEqual(['Boil water', 'Add pasta']);
    });

    it('splits free text on line breaks and strips numbering', () => {
        const flat = flattenCookSteps(recipe({
            steps_mode: 'freeform',
            // Structured steps exist but the chosen face is free text: steps_mode decides.
            steps: [step({ step_id: 'x', sequence: 1, text: 'Ignored' })],
            instructions: '1. Chop onions\r\n\n2) Fry them\n   \n',
        }));
        expect(flat.map((s) => s.text)).toEqual(['Chop onions', 'Fry them']);
        expect(flat.every((s) => !s.isSubStep && s.sectionName === null && s.timerMinutes === null)).toBe(true);
    });

    it('shows one placeholder step when there is no method at all', () => {
        expect(flattenCookSteps(recipe({ steps_mode: 'freeform' })).map((s) => s.text))
            .toEqual(['No instructions provided.']);
        expect(flattenCookSteps(null)).toHaveLength(1);
    });
});

describe('stepIngredientIds', () => {
    const ingredients = [
        { recipe_ingredient_id: 'i1', label: 'cheddar', stock_item_name: 'Cheese', raw_text: null },
        { recipe_ingredient_id: 'i2', label: null, stock_item_name: null, raw_text: 'Pasta' },
        { recipe_ingredient_id: 'i3', label: null, stock_item_name: 'Salt', raw_text: null },
    ];

    it("uses a structured step's own links", () => {
        const [s] = flattenCookSteps(recipe({ steps: [step({ step_id: 'a', sequence: 1, text: 'Add salt', ingredient_ids: ['i1'] })] }));
        expect([...stepIngredientIds(s!, ingredients)]).toEqual(['i1']);
    });

    it('matches names in the text of an unlinked step', () => {
        const [s] = flattenCookSteps(recipe({ steps_mode: 'freeform', instructions: 'Grate the Cheddar over the pasta' }));
        expect([...stepIngredientIds(s!, ingredients)].sort()).toEqual(['i1', 'i2']);
    });
});

describe('sniffTimerMinutes', () => {
    it('reads minutes, then hours, from the wording', () => {
        expect(sniffTimerMinutes('Simmer for 20 minutes')).toBe(20);
        expect(sniffTimerMinutes('Bake 1.5 hours')).toBe(90);
        expect(sniffTimerMinutes('Season to taste')).toBeNull();
    });
});
