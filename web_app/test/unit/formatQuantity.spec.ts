// FU-520 workstream 1 — unit coverage for the DEC-3 unit-spacing rule.
//
// `formatQuantity` is the single source of truth for whether a unit hugs the
// number ("250g") or gets a space ("2 cloves"). Cook mode, recipes, and
// shopping lists all route through it, so a drift here shows up on three
// surfaces at once — pin the inclusion list's behaviour explicitly.
//
// Pure function only — no Vue, no network (see vitest.config.ts).
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

import { formatQuantity } from 'src/helpers/formatQuantity';

describe('formatQuantity — DEC-3 unit-spacing corpus', () => {
    // [quantity, unit, expected] — the tight-units list vs everything else.
    const CORPUS: Array<[number | string | null, string | null, string]> = [
        // metric/imperial mass + volume hug the number
        [250, 'g', '250g'],
        [2, 'ml', '2ml'],
        [1, 'kg', '1kg'],
        [1, 'l', '1l'],
        [500, 'mg', '500mg'],
        [8, 'oz', '8oz'],
        [2, 'lb', '2lb'],
        [12, 'floz', '12floz'],
        [1, 'pt', '1pt'],
        [2, 'qt', '2qt'],
        // everything else gets a space
        [2, 'cloves', '2 cloves'],
        [1, 'tbsp', '1 tbsp'],
        [3, 'cups', '3 cups'],
        [1, 'pinch', '1 pinch'],
    ];

    it.each(CORPUS)('formats %j + %j → %j', (quantity, unit, expected) => {
        expect(formatQuantity(quantity, unit)).toBe(expected);
    });

    it('is case-insensitive on the tight-units list', () => {
        expect(formatQuantity(250, 'G')).toBe('250G');
        expect(formatQuantity(2, 'ML')).toBe('2ML');
    });

    it('trims whitespace off the unit before deciding', () => {
        expect(formatQuantity(250, '  g ')).toBe('250g');
        expect(formatQuantity(2, ' cloves ')).toBe('2 cloves');
    });

    it('renders quantity-only when the unit is missing', () => {
        expect(formatQuantity(2, null)).toBe('2');
        expect(formatQuantity(2, undefined)).toBe('2');
        expect(formatQuantity(2, '   ')).toBe('2');
    });

    it('renders unit-only when the quantity is missing', () => {
        expect(formatQuantity(null, 'g')).toBe('g');
        expect(formatQuantity(undefined, 'cloves')).toBe('cloves');
        expect(formatQuantity('', 'tbsp')).toBe('tbsp');
    });

    it('renders an empty string when both are missing', () => {
        expect(formatQuantity(null, null)).toBe('');
        expect(formatQuantity('', '')).toBe('');
        expect(formatQuantity(undefined, undefined)).toBe('');
    });

    it('passes string quantities (pre-formatted fractions) through untouched', () => {
        // scaleQuantity emits glyph strings like "1½" — spacing still applies.
        expect(formatQuantity('1½', 'cups')).toBe('1½ cups');
        expect(formatQuantity('½', 'g')).toBe('½g');
    });

    // Owner report 2026-09-03: the meal planner's right rail read "needs
    // 31.333333333333332 tbsp". Aggregated week demand is a sum of scaled
    // per-recipe quantities, so a repeating third is a binary float and
    // `String()` prints all seventeen digits of it.
    describe('float artefacts', () => {
        it('rounds a repeating decimal to two places', () => {
            expect(formatQuantity(94 / 3, 'tbsp')).toBe('31.33 tbsp');
            expect(formatQuantity(0.1 + 0.2, 'l')).toBe('0.3l');
        });

        it('leaves no trailing zeros on a value that rounds clean', () => {
            expect(formatQuantity(2.0, 'cloves')).toBe('2 cloves');
            expect(formatQuantity(2.5, 'cups')).toBe('2.5 cups');
            expect(formatQuantity(2.499, 'cups')).toBe('2.5 cups');
        });

        it('keeps the fractions a recipe actually uses', () => {
            expect(formatQuantity(0.25, 'tsp')).toBe('0.25 tsp');
            expect(formatQuantity(0.5, 'kg')).toBe('0.5kg');
        });

        it('rounds a value that would otherwise show as zero to zero, not blank', () => {
            // 0.001 g is below the display precision; "0g" is the honest
            // reading of a rounded figure, and never an empty string (which
            // would render as a bare unit).
            expect(formatQuantity(0.001, 'g')).toBe('0g');
        });

        it('renders nothing for a non-finite quantity rather than "NaN"', () => {
            expect(formatQuantity(Number.NaN, 'g')).toBe('g');
            expect(formatQuantity(Number.POSITIVE_INFINITY, 'g')).toBe('g');
        });
    });
});
