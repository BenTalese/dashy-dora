import { describe, expect, it } from 'vitest';
import { hasLineChoices, lineOffers, pickedLineChoice, type LineChoice } from 'src/models/shoppingList';

const offer = { product_id: 'p1', brand: null, name: 'Vitasoy 1L', size: '1L', store_id: 's', store_name: 'Coles', price_now: 3, price_was: null, is_selected: true };
const buy = { preferred_buy_id: 'b1', label: 'Oat Milky' };

function choice(
    offers: LineChoice['offers'],
    preferredBuys: LineChoice['preferredBuys'],
    picks: Partial<Pick<LineChoice, 'selectedProductId' | 'preferredBuyId'>> = {},
): LineChoice {
    return { itemName: 'Milk', offers, preferredBuys, selectedProductId: null, preferredBuyId: null, ...picks };
}

describe('item choices: products and preferred buys together (FU-990)', () => {
    it('offers both sources when products are on, preferred buys only when off', () => {
        const c = choice([offer], [buy]);
        expect(lineOffers(c, true)).toEqual([offer]);
        expect(lineOffers(c, false)).toEqual([]);
        expect(hasLineChoices(c, true)).toBe(true);
        expect(hasLineChoices(choice([offer], []), false)).toBe(false);
    });

    it('a preferred buy is pickable on an item that has linked products', () => {
        const c = choice([offer], [buy], { preferredBuyId: 'b1' });
        expect(pickedLineChoice(c, true)).toEqual({ kind: 'preferred', id: 'b1', label: 'Oat Milky' });
    });

    it('a picked offer shows over a stale hint, and only while products are on', () => {
        const c = choice([offer], [buy], { selectedProductId: 'p1', preferredBuyId: 'b1' });
        expect(pickedLineChoice(c, true)).toEqual({ kind: 'offer', id: 'p1', label: 'Vitasoy 1L' });
        expect(pickedLineChoice(c, false)).toEqual({ kind: 'preferred', id: 'b1', label: 'Oat Milky' });
    });
});
