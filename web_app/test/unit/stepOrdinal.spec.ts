import { describe, expect, it } from 'vitest';
import { stripLeadingOrdinal } from 'src/helpers/stepOrdinal';

describe('stripLeadingOrdinal (FU-857)', () => {
    it.each([
        ['1. Render the pancetta', 'Render the pancetta'],
        ['2) Boil the pasta', 'Boil the pasta'],
        ['3: Toss', 'Toss'],
        ['Step 4 — Plate up', 'Plate up'],
        ['step 5: Serve', 'Serve'],
        ['(6) Rest', 'Rest'],
        ['2 eggs, beaten', '2 eggs, beaten'],
        ['1.5 cups of stock go in', '1.5 cups of stock go in'],
        ['1.', '1.'],
    ])('%s', (input, expected) => {
        expect(stripLeadingOrdinal(input)).toBe(expected);
    });
});
