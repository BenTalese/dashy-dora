// FU-520 workstream 1 — unit coverage for the DEC-4 quantity-scaling rule.
//
// Cook mode rescales every ingredient by `cookingFor / recipe.servings` and
// then rounds into kitchen-friendly buckets: countables snap to whole numbers
// (floored at 1), continuous units snap to ½ / ¼ / ¾ / ⅓ / ⅔ glyphs within a
// 0.04 tolerance, else one decimal place. These buckets are the contract —
// pin them so a tolerance tweak can't silently produce "1.333 cups" again.
//
// Pure functions only — no Vue, no network (see vitest.config.ts).
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

import { isCountableUnit, scaleQuantity } from 'src/helpers/scaleQuantity';

describe('isCountableUnit — discrete-object detection', () => {
    it('treats null / undefined / blank units as countable (bare counts like "2 eggs")', () => {
        expect(isCountableUnit(null)).toBe(true);
        expect(isCountableUnit(undefined)).toBe(true);
        expect(isCountableUnit('')).toBe(true);
        expect(isCountableUnit('   ')).toBe(true);
    });

    it('recognises the inclusion list in both singular and plural forms', () => {
        for (const unit of ['egg', 'eggs', 'clove', 'cloves', 'slice', 'slices', 'can', 'cans']) {
            expect(isCountableUnit(unit), unit).toBe(true);
        }
    });

    it('is case- and whitespace-insensitive', () => {
        expect(isCountableUnit(' Eggs ')).toBe(true);
        expect(isCountableUnit('CLOVES')).toBe(true);
    });

    it('treats mass / volume / unknown units as continuous', () => {
        for (const unit of ['g', 'ml', 'cups', 'tbsp', 'handful']) {
            expect(isCountableUnit(unit), unit).toBe(false);
        }
    });
});

describe('scaleQuantity — countable units round to whole numbers', () => {
    it('scales up and rounds to the nearest whole', () => {
        // 2 eggs for 4 servings, cooking for 6 → 3 eggs.
        expect(scaleQuantity(2, 4, 6, 'eggs')).toBe(3);
    });

    it('rounds half-way cases to the nearest whole', () => {
        // 1 egg for 4 servings, cooking for 6 → 1.5 → rounds to 2.
        expect(scaleQuantity(1, 4, 6, 'eggs')).toBe(2);
    });

    it('never scales a countable below 1 (you cannot cook with 0 eggs)', () => {
        // 1 egg for 6 servings, cooking for 1 → 0.17 → floored at 1.
        expect(scaleQuantity(1, 6, 1, 'eggs')).toBe(1);
    });

    it('treats a bare count (no unit) as countable', () => {
        expect(scaleQuantity(2, 2, 3, null)).toBe(3);
    });

    it('leaves an unscaled count as written (QA2-35: ½ onion stayed 1)', () => {
        expect(scaleQuantity(0.5, 4, 4, null)).toBe(0.5);
    });
});

describe('scaleQuantity — continuous units snap to kitchen fractions', () => {
    it('snaps to ½ / ¼ / ¾ / ⅓ / ⅔ within tolerance', () => {
        expect(scaleQuantity(1, 2, 1, 'cups')).toBe('½');
        expect(scaleQuantity(1, 4, 1, 'cups')).toBe('¼');
        expect(scaleQuantity(3, 4, 1, 'cups')).toBe('¾');
        expect(scaleQuantity(1, 3, 1, 'cups')).toBe('⅓');
        expect(scaleQuantity(2, 3, 1, 'cups')).toBe('⅔');
    });

    it('prefixes a whole part when the value exceeds 1', () => {
        // 1 cup for 3 servings, cooking for 4 → 1.333… → "1⅓".
        expect(scaleQuantity(1, 3, 4, 'cups')).toBe('1⅓');
        // 3 cups for 2 servings, cooking for 1 → 1.5 → "1½".
        expect(scaleQuantity(3, 2, 1, 'cups')).toBe('1½');
    });

    it('renders clean wholes without a decimal', () => {
        expect(scaleQuantity(200, 2, 4, 'g')).toBe('400');
        expect(scaleQuantity(3, 1, 1, 'cups')).toBe('3');
    });

    it('falls back to one decimal place with the trailing zero trimmed', () => {
        // 7.55 has no nearby glyph → "7.6" (one decimal).
        expect(scaleQuantity(7.55, 1, 1, 'g')).toBe('7.6');
        // 1.15 → nowhere near a glyph → "1.2".
        expect(scaleQuantity(1.15, 1, 1, 'g')).toBe('1.2');
    });

    it('renders "0" for zero / negative continuous quantities', () => {
        expect(scaleQuantity(0, 2, 4, 'g')).toBe('0');
        expect(scaleQuantity(-5, 2, 4, 'g')).toBe('0');
    });
});

describe('scaleQuantity — DORA_VERIFY Cook-mode Chunk 6 (FU-101) checklist cases', () => {
    // These pin the literal examples the manual verify checklist calls out, so
    // a rounding/tolerance regression trips a named test instead of an
    // eyeball walk.

    it('rescale up 4→6 (1.5×): 200g → 300, 2 eggs → 3', () => {
        expect(scaleQuantity(200, 4, 6, 'g')).toBe('300');
        expect(scaleQuantity(2, 4, 6, 'eggs')).toBe(3);
    });

    it('rescale down 4→2 (0.5×): 200g → 100, 4 eggs → 2', () => {
        expect(scaleQuantity(200, 4, 2, 'g')).toBe('100');
        expect(scaleQuantity(4, 4, 2, 'eggs')).toBe(2);
    });

    it('fraction snap: 4-serving 1 cup → ¾ at 3, → 1½ at 6', () => {
        expect(scaleQuantity(1, 4, 3, 'cups')).toBe('¾');
        expect(scaleQuantity(1, 4, 6, 'cups')).toBe('1½');
    });

    it('countable rounding: 4-serving 1 egg → 1 at 3 (0.75 up, floored at 1), → 2 at 6', () => {
        expect(scaleQuantity(1, 4, 3, 'eggs')).toBe(1);
        expect(scaleQuantity(1, 4, 6, 'eggs')).toBe(2);
    });

    it('sub-tolerance fractions: 0.5 cups × 1.0 → ½', () => {
        expect(scaleQuantity(0.5, 1, 1, 'cups')).toBe('½');
    });

    it('gram fraction edge: 7.5 g × 1.0 → 7½', () => {
        // Continuous unit, so 0.5 snaps to the ½ glyph rather than rounding.
        expect(scaleQuantity(7.5, 1, 1, 'g')).toBe('7½');
    });
});

describe('scaleQuantity — defaulting rules', () => {
    it('returns null for a null quantity so unit-only rows can render', () => {
        expect(scaleQuantity(null, 4, 6, 'g')).toBeNull();
        expect(scaleQuantity(undefined, 4, 6, 'g')).toBeNull();
    });

    it('assumes 1 serving when the recipe declares none', () => {
        // servings null/0 → base 1, so cookingFor multiplies directly.
        expect(scaleQuantity(100, null, 2, 'g')).toBe('200');
        expect(scaleQuantity(100, 0, 2, 'g')).toBe('200');
    });

    it('assumes cooking-for 1 when the headcount is invalid', () => {
        expect(scaleQuantity(100, 2, 0, 'g')).toBe('50');
        expect(scaleQuantity(100, 2, NaN, 'g')).toBe('50');
        expect(scaleQuantity(100, 2, -3, 'g')).toBe('50');
    });

    it('leaves quantities untouched at a 1:1 ratio', () => {
        expect(scaleQuantity(2, 4, 4, 'eggs')).toBe(2);
        expect(scaleQuantity(250, 4, 4, 'g')).toBe('250');
    });
});
