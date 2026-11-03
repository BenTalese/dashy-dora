import { describe, expect, it } from 'vitest';
import { hasLineChoices, pickedLineChoice, usesOffers, type LineChoice } from 'src/models/shoppingList';

const offer = { product_id: 'p1', brand: null, name: 'Vitasoy 1L', size: '1L', store_id: 's', store_name: 'Coles', price_now: 3, price_was: null, is_selected: true };
const buy = { preferred_buy_id: 'b1', label: 'Oat Milky' };

function choice(offers: LineChoice['offers'], preferredBuys: LineChoice['preferredBuys']): LineChoice {
    return { itemName: 'Milk', offers, preferredBuys, selectedProductId: 'p1', preferredBuyId: 'b1' };
}

describe('which source an item choice uses (owner 2026-11-03)', () => {
    it('uses linked products only when products are on and the item has some', () => {
        expect(usesOffers(1, true)).toBe(true);
        expect(usesOffers(0, true)).toBe(false);
        expect(usesOffers(1, false)).toBe(false);
    });

    it('falls back to preferred buys for an item with no linked product on a products install', () => {
        const c = choice([], [buy]);
        expect(hasLineChoices(c, true)).toBe(true);
        expect(pickedLineChoice(c, true)).toEqual({ id: 'b1', label: 'Oat Milky' });
    });

    it('a linked product wins over preferred buys', () => {
        const c = choice([offer], [buy]);
        expect(pickedLineChoice(c, true)).toEqual({ id: 'p1', label: 'Vitasoy 1L' });
        expect(pickedLineChoice(c, false)).toEqual({ id: 'b1', label: 'Oat Milky' });
    });
});
