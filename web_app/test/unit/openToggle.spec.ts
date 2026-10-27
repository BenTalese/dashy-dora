// DR-5 (FU-578 #2) — the pure decision → patch mapping that gates the
// stock-item open/seal mutation. The behaviour under test is the trap fix:
// a dismissed/cancelled prompt must produce NO patch (server untouched),
// while Skip/Update/seal each map to the right PATCH body. The dialog itself
// is a thin promise wrapper in useStockItemActions; this pins the contract it
// feeds without mounting Quasar.
import { buildOpenTogglePatch, type OpenToggleTarget } from 'src/helpers/openToggle';
import { describe, expect, it } from 'vitest';

const sealedItem: OpenToggleTarget = {
    stock_item_id: 'SI-1',
    name: 'Milk',
    is_open: false,
    expiry_date: '2026-09-01',
};
const openItem: OpenToggleTarget = {
    stock_item_id: 'SI-2',
    name: 'Jam',
    is_open: true,
    expiry_date: '2026-09-01',
};

describe('buildOpenTogglePatch', () => {
    it('seals an open item with a single unconditional patch (no prompt/decision)', () => {
        expect(buildOpenTogglePatch(openItem, null)).toEqual({
            stock_item_id: 'SI-2',
            is_open: false,
        });
    });

    it('returns null (NO mutation) when opening was aborted — decision missing', () => {
        // The DR-5 guarantee: backdrop/Escape/Cancel ⇒ nothing is written.
        expect(buildOpenTogglePatch(sealedItem, null)).toBeNull();
    });

    it('returns null (NO mutation) when opening was aborted — decision open:false', () => {
        expect(buildOpenTogglePatch(sealedItem, { open: false })).toBeNull();
    });

    it('Skip opens the item and omits expiry_date (leave unchanged)', () => {
        const patch = buildOpenTogglePatch(sealedItem, { open: true, expiry: undefined });
        expect(patch).toEqual({ stock_item_id: 'SI-1', is_open: true });
        expect(patch).not.toHaveProperty('expiry_date');
    });

    it('Update opens the item and sets a differing expiry', () => {
        expect(
            buildOpenTogglePatch(sealedItem, { open: true, expiry: '2026-10-15' }),
        ).toEqual({ stock_item_id: 'SI-1', is_open: true, expiry_date: '2026-10-15' });
    });

    it('Update with the same expiry omits expiry_date (unchanged ⇒ not sent)', () => {
        const patch = buildOpenTogglePatch(sealedItem, {
            open: true,
            expiry: '2026-09-01',
        });
        expect(patch).toEqual({ stock_item_id: 'SI-1', is_open: true });
        expect(patch).not.toHaveProperty('expiry_date');
    });

    it('treats a missing current expiry as empty — clearing (null) is a change', () => {
        const noExpiry: OpenToggleTarget = { stock_item_id: 'SI-3', name: 'Rice', is_open: false };
        expect(buildOpenTogglePatch(noExpiry, { open: true, expiry: null })).toEqual({
            stock_item_id: 'SI-3',
            is_open: true,
            expiry_date: null,
        });
    });
});
