// The chat chip row's rule, split out of DoraChat.vue (finalisation 11-R30).
import { describe, expect, it } from 'vitest';

import { buildChips, CHIP_LIMIT } from 'src/services/doraChips';

describe('buildChips', () => {
    it('puts the latest reply first, then fills from the pool, capped and deduped', () => {
        const chips = buildChips({ aiActive: false, suggestions: ['joke', 'joke'], cursor: 0 });
        expect(chips).toHaveLength(CHIP_LIMIT);
        expect(chips[0]?.dispatch).toEqual({ kind: 'intent', id: 'joke' });
        expect(new Set(chips.map((c) => c.key)).size).toBe(chips.length);
    });

    it('turns a suggestion into its prompt in AI mode', () => {
        const [first] = buildChips({ aiActive: true, suggestions: ['low_stock'], cursor: 0 });
        expect(first?.dispatch).toEqual({ kind: 'prompt', text: "what's running low in my pantry" });
    });

    it('moves through the pool with the cursor', () => {
        const start = buildChips({ aiActive: false, suggestions: [], cursor: 0 });
        const next = buildChips({ aiActive: false, suggestions: [], cursor: CHIP_LIMIT });
        expect(next[0]?.key).not.toBe(start[0]?.key);
    });
});
