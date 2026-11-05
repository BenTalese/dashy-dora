// Finalisation 08-R7 — a card that ships after the user saved their layout
// lands at its registry position, not at the end. The page comment promised
// this and nothing held it: Kitchen health shipped *last* for every user with
// a saved layout. Retired ids are dropped and an unseen opt-in card inherits
// `defaultHidden`.
import { describe, expect, it } from 'vitest';

import { CARD_DEFS } from 'src/helpers/dashboardCards';
import { defaultOrder, insertMissingAtRegistryPosition, parseLayout } from 'src/helpers/cardLayout';

const ids = () => CARD_DEFS.map((c) => c.id);

describe('parseLayout', () => {
    it('returns the registry order and default-hidden set with no stored layout', () => {
        const layout = parseLayout(null, CARD_DEFS);
        expect(layout.order).toEqual(defaultOrder(CARD_DEFS));
        expect(new Set(layout.hidden)).toEqual(
            new Set(CARD_DEFS.filter((c) => c.defaultHidden).map((c) => c.id)),
        );
    });

    it('inserts a card missing from the stored order at its registry position', () => {
        const all = ids();
        // Drop the second registry card from a "saved" layout, as if it shipped
        // after the save; it must come back in second place, not last.
        const missing = all[1]!;
        const saved = all.filter((id) => id !== missing);

        const { order } = parseLayout(JSON.stringify({ order: saved, hidden: [] }), CARD_DEFS);

        expect(order).toEqual(all);
        expect(order.indexOf(missing)).toBe(1);
    });

    it('respects the user\'s own reordering when slotting a new card in', () => {
        const all = ids();
        const missing = all[2]!;
        // User moved the last card to the front; the new card still goes right
        // after the registry card that precedes it.
        const saved = [all[all.length - 1]!, ...all.slice(0, -1).filter((id) => id !== missing)];

        const order = insertMissingAtRegistryPosition([...saved], CARD_DEFS);

        expect(order.indexOf(missing)).toBe(order.indexOf(all[1]!) + 1);
        expect(order[0]).toBe(all[all.length - 1]);
        expect(new Set(order)).toEqual(new Set(all));
    });

    it('puts a missing first registry card at the front', () => {
        const all = ids();
        const order = insertMissingAtRegistryPosition(all.slice(1), CARD_DEFS);
        expect(order).toEqual(all);
    });

    it('drops retired ids and inherits defaultHidden for never-seen cards', () => {
        const optIn = CARD_DEFS.find((c) => c.defaultHidden);
        const seen = ids().filter((id) => id !== optIn?.id);

        const layout = parseLayout(JSON.stringify({ order: ['attention', 'calendar', ...seen], hidden: ['savings'] }), CARD_DEFS);

        expect(layout.order).not.toContain('attention');
        expect(layout.hidden).not.toContain('savings');
        if (optIn) expect(layout.hidden).toContain(optIn.id);
    });

    it('falls back to defaults on malformed JSON', () => {
        expect(parseLayout('{not json', CARD_DEFS).order).toEqual(defaultOrder(CARD_DEFS));
    });
});
