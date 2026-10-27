import { describe, expect, it } from 'vitest';

import { inferenceTone, inferenceTooltip } from 'src/helpers/inferenceHint';

describe('inferenceHint', () => {
    it('words an at-risk hint for each surface, naming the items', () => {
        expect(inferenceTooltip('at_risk', ['milk', 'eggs'], 'plan'))
            .toBe('Dora thinks you may have run out of milk, eggs since you planned this.');
        expect(inferenceTooltip('at_risk', ['milk'], 'recipe'))
            .toBe("Everything's recorded as in stock, but Dora thinks you may have run out of milk.");
    });

    it('words a maybe-cookable hint the same on both surfaces', () => {
        const expected = "Recorded as missing milk, but Dora thinks you're back in stock.";
        expect(inferenceTooltip('maybe_cookable', ['milk'], 'plan')).toBe(expected);
        expect(inferenceTooltip('maybe_cookable', ['milk'], 'recipe')).toBe(expected);
    });

    it('tones at-risk as a warning and back-in-stock as positive', () => {
        expect(inferenceTone('at_risk')).toBe('warning');
        expect(inferenceTone('maybe_cookable')).toBe('positive');
    });
});
