import { describe, expect, it, vi } from 'vitest';

import { useCardLayout } from 'src/composables/useCardLayout';
import type { CardLayout } from 'src/helpers/cardLayout';
import { CARD_DEFS, type CardId } from 'src/helpers/dashboardCards';
import { REPORT_CARD_DEFS } from 'src/helpers/reportCards';

function layout(opts: { stored?: CardLayout<CardId> | null; money?: boolean; products?: boolean } = {}) {
    const persist = vi.fn();
    const l = useCardLayout({
        defs: CARD_DEFS,
        stored: () => (opts.stored ? JSON.stringify(opts.stored) : null),
        persist,
        moneyEnabled: () => opts.money ?? true,
        productsEnabled: () => opts.products ?? true,
    });
    return { l, persist };
}

describe('useCardLayout', () => {
    it('opens on the registry defaults: kitchen health first, opt-in cards hidden', () => {
        const { l } = layout();
        expect(l.menuCards.value[0]!.id).toBe('dora_score');
        expect(l.cardRendered('price_drops')).toBe(false);
        expect(l.cardRendered('my_budget')).toBe(true);
    });

    it('drops a gated card from the page and the menu when its feature is off', () => {
        const { l } = layout({ money: false });
        expect(l.cardRendered('my_budget')).toBe(false);
        expect(l.menuCards.value.map((c) => c.id)).not.toContain('my_budget');
    });

    it('toggles a card and saves the layout', () => {
        const { l, persist } = layout();
        l.toggleCard('restock');
        expect(l.cardRendered('restock')).toBe(false);
        expect(persist).toHaveBeenLastCalledWith(expect.objectContaining({ hidden: expect.arrayContaining(['restock']) }));
    });

    it('moves over available cards only, so a gated neighbour is skipped', () => {
        const { l } = layout({ money: false });
        const peers = l.menuCards.value.map((c) => c.id);
        expect(peers).not.toContain('my_budget');
        expect(l.canMove(peers[0]!, 'up')).toBe(false);
        l.moveCard(peers[1]!, 'up');
        expect(l.menuCards.value.map((c) => c.id).slice(0, 2)).toEqual([peers[1], peers[0]]);
    });

    it('drops a dragged card into the target slot', () => {
        const { l, persist } = layout();
        const before = l.menuCards.value.map((c) => c.id);
        l.dropCardOn(before[2]!, before[0]!);
        expect(l.menuCards.value[0]!.id).toBe(before[2]);
        expect(persist).toHaveBeenCalled();
    });
});

describe('useCardLayout on the Reports table (FU-832)', () => {
    function reports(money: boolean, hidden: string[] = []) {
        return useCardLayout({
            defs: REPORT_CARD_DEFS,
            stored: () => JSON.stringify({ order: REPORT_CARD_DEFS.map((c) => c.id), hidden }),
            persist: vi.fn(),
            moneyEnabled: () => money,
            productsEnabled: () => true,
        });
    }

    it('reads the money gate off the table', () => {
        const l = reports(false);
        expect(l.cardRendered('spend')).toBe(false);
        expect(l.cardRendered('price_changes')).toBe(false);
        expect(l.cardRendered('waste')).toBe(true);
    });

    it('keeps the wide cards wide and pairs the other two', () => {
        const l = reports(true);
        expect(l.cardCol('spend')).toBe('col-12');
        expect(l.cardCol('waste')).toBe('col-12 col-sm-6');
        expect(l.cardCol('kitchen_memory')).toBe('col-12 col-sm-6');
    });

    it('widens the survivor of the pair when the other is hidden', () => {
        const l = reports(true, ['kitchen_memory']);
        expect(l.cardCol('waste')).toBe('col-12');
    });
});
