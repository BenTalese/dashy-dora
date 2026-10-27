// Finalisation 14-R9 — one TS mirror of the server's headcount bounds.
import { describe, expect, it } from 'vitest';

import { normaliseHeadcount } from 'src/models/household';

describe('normaliseHeadcount', () => {
    it('maps absent / sub-one / non-finite values to null', () => {
        expect(normaliseHeadcount(null)).toBeNull();
        expect(normaliseHeadcount(undefined)).toBeNull();
        expect(normaliseHeadcount(0)).toBeNull();
        expect(normaliseHeadcount(Number.NaN)).toBeNull();
    });

    it('floors fractions and caps at 99', () => {
        expect(normaliseHeadcount(1.7)).toBe(1);
        expect(normaliseHeadcount(4)).toBe(4);
        expect(normaliseHeadcount(150)).toBe(99);
    });
});
