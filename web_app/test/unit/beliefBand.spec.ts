import { describe, expect, it } from 'vitest';

import { bandForSequence, sequenceForBand } from 'src/helpers/beliefBand';
import { LOW_STOCK_SEQUENCE, OUT_OF_STOCK_SEQUENCE, STOCKED_SEQUENCE } from 'src/helpers/stockStatus';

describe('beliefBand', () => {
    it('maps each band to its level sequence and back', () => {
        for (const [band, seq] of [
            ['out', OUT_OF_STOCK_SEQUENCE], ['low', LOW_STOCK_SEQUENCE], ['stocked', STOCKED_SEQUENCE],
        ] as const) {
            expect(sequenceForBand(band)).toBe(seq);
            expect(bandForSequence(seq)).toBe(band);
        }
    });

    it('has no band for an unknown band or a household extra level', () => {
        expect(sequenceForBand('plenty')).toBeNull();
        expect(sequenceForBand(null)).toBeNull();
        expect(bandForSequence(7)).toBeNull();
        expect(bandForSequence(null)).toBeNull();
    });
});
