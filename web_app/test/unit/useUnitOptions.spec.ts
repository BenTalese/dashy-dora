/**
 * The unit picker's vocabulary.
 *
 * Pinned because the list stopped being a suggestion on 2026-08-26: the recipe
 * ingredient editor dropped `new-value-mode`, so whatever this returns is now
 * the *only* thing a user can pick. The narrowing is the part worth a test —
 * the generated `UNIT_TABLE` spans six dimensions, and a regeneration that
 * added, say, a new energy unit would silently put it in the ingredient
 * dropdown if the filter were dropped.
 */
import { afterEach, describe, expect, it } from 'vitest';

import { useUnitOptions } from 'src/composables/useUnitOptions';
import {
    unitsForSystem,
    useMeasurementSystem,
    __resetMeasurementSystemForTests,
} from 'src/composables/useMeasurementSystem';
import type { MeasurementSystem } from 'src/generated/units_table';

const INGREDIENT_DIMENSIONS = ['volume', 'mass', 'count'] as const;

/** Drive the install's system directly — the composable's ref is the seam,
 *  and going through it keeps the test on the same path the app uses rather
 *  than mocking `/api/health`. */
function setSystem(value: MeasurementSystem): void {
    useMeasurementSystem().system.value = value;
}

afterEach(() => {
    __resetMeasurementSystemForTests();
});

describe('useUnitOptions', () => {
    it('de-duplicates the table down to one row per canonical form', () => {
        const { allUnitOptions } = useUnitOptions();
        const values = allUnitOptions.value.map((o) => o.value);
        expect(new Set(values).size).toBe(values.length);
        // "tablespoon" / "tablespoons" / "tbsp" / "T" are four aliases, one row.
        expect(values.filter((v) => v === 'tbsp')).toHaveLength(1);
    });

    it('narrows to the dimensions an ingredient can be measured in', () => {
        const { allUnitOptions } = useUnitOptions(INGREDIENT_DIMENSIONS);
        const values = allUnitOptions.value.map((o) => o.value);

        // Present: the three ingredient dimensions, including the informal
        // words the removed free-text escape used to be needed for.
        for (const unit of ['g', 'kg', 'ml', 'L', 'cup', 'tbsp', 'tsp',
            'ea', 'pack', 'dozen', 'pinch', 'dash']) {
            expect(values).toContain(unit);
        }
        // Absent: energy and length. Nobody measures an ingredient in kJ.
        for (const unit of ['kJ', 'kcal', 'J', 'cm', 'mm', 'm', 'ft', 'in']) {
            expect(values).not.toContain(unit);
        }
    });

    it('searches aliases but never escapes the narrowing', () => {
        const { unitOptions, onUnitFilter } = useUnitOptions(INGREDIENT_DIMENSIONS);

        // Typing a unit's long form finds its canonical abbreviation.
        onUnitFilter('tablespoons', (cb) => cb());
        expect(unitOptions.value.map((o) => o.value)).toContain('tbsp');

        // A term that only matches an out-of-dimension unit finds nothing,
        // rather than leaking it back in through the alias search.
        onUnitFilter('kilojoule', (cb) => cb());
        expect(unitOptions.value).toHaveLength(0);

        // Clearing restores the full narrowed list.
        onUnitFilter('', (cb) => cb());
        expect(unitOptions.value.length).toBeGreaterThan(10);
        expect(unitOptions.value.map((o) => o.value)).not.toContain('kJ');
    });

    // The measurement system (owner ask 2026-08-27). Worth pinning for the
    // same reason the dimension narrowing is: the picker is a closed list, so
    // anything this drops is a unit the user can no longer choose.
    it('offers only the install system\'s units, plus the universal ones', () => {
        setSystem('us');
        const { allUnitOptions } = useUnitOptions(INGREDIENT_DIMENSIONS);
        const values = allUnitOptions.value.map((o) => o.value);

        for (const unit of ['fl oz', 'qt', 'gal', 'oz', 'lb', 'US cup', 'US tbsp']) {
            expect(values).toContain(unit);
        }
        // Metric-only units are gone — including the two whose *names* survive
        // in the US system at a different size, which is exactly why they are
        // separate rows in the table.
        for (const unit of ['ml', 'L', 'g', 'kg', 'cup', 'tbsp']) {
            expect(values).not.toContain(unit);
        }
        // Universal units survive every system: the informal cooking amounts
        // and the count units.
        for (const unit of ['pinch', 'dash', 'smidgen', 'tsp', 'ea', 'pack', 'dozen']) {
            expect(values).toContain(unit);
        }
    });

    it('gives imperial the metric core as well as the imperial units', () => {
        setSystem('imperial');
        const values = useUnitOptions(INGREDIENT_DIMENSIONS)
            .allUnitOptions.value.map((o) => o.value);

        // The UK sells and cooks in metric *and* imperial, so it gets both.
        for (const unit of ['g', 'kg', 'ml', 'L', 'oz', 'lb', 'fl oz', 'pt']) {
            expect(values).toContain(unit);
        }
        // But not the US-specific sizes: an imperial pint is 568 ml, not 473.
        for (const unit of ['qt', 'gal', 'US cup', 'US tbsp', 'stick']) {
            expect(values).not.toContain(unit);
        }
    });

    it('keeps a row\'s existing unit offered even when the system excludes it', () => {
        setSystem('metric');
        const values = useUnitOptions(INGREDIENT_DIMENSIONS, () => 'lb')
            .allUnitOptions.value.map((o) => o.value);

        // An imported US recipe on a metric install must not have its saved
        // `lb` vanish from its own dropdown — that would be silent data loss
        // the first time the row was edited.
        expect(values).toContain('lb');
        expect(values).toContain('g');
        // The exception is exactly one unit wide, not a hole in the filter.
        expect(values).not.toContain('oz');
    });

    it('keeps a saved word the table has never heard of (FU-786: loaf)', () => {
        setSystem('metric');
        const values = useUnitOptions(INGREDIENT_DIMENSIONS, () => 'loaf')
            .allUnitOptions.value.map((o) => o.value);
        expect(values).toContain('loaf');
    });

    it('offers cooking words only when asked (FU-902)', () => {
        setSystem('metric');
        const plain = useUnitOptions(INGREDIENT_DIMENSIONS).allUnitOptions.value.map((o) => o.value);
        const cooking = useUnitOptions(INGREDIENT_DIMENSIONS, undefined, { cookingWords: true })
            .allUnitOptions.value.map((o) => o.value);
        expect(plain).not.toContain('clove');
        expect(cooking).toEqual(expect.arrayContaining(['clove', 'sprig', 'rasher', 'stalk', 'head', 'slice']));
    });
});

describe('unitsForSystem', () => {
    it('never returns an empty vocabulary for an unknown system', () => {
        // Falls back to metric rather than emptying every dropdown in the app,
        // which is the failure mode a bad setting value would otherwise cause.
        const offered = unitsForSystem('nonsense' as MeasurementSystem);
        expect(offered.size).toBeGreaterThan(0);
        expect(offered.has('pinch')).toBe(true);
    });
});
