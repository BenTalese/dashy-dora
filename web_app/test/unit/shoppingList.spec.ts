// FU-520 workstream 1 — unit coverage for the shopping-list model helpers.
//
// `cartStateFor` drives the cart button's colour/behaviour on every stock row
// in the app; `chosenOfferFor` / `priceOfLine` are the
// per-line display math the charter's state-ownership rule explicitly leaves
// on the client (list-level totals are server-owned). The offer-fallback and
// actual-price-override rules are the tricky parts — pin them.
//
// Pure functions only — no Vue, no network (see vitest.config.ts).
import { describe, expect, it } from 'vitest';

import {
    cartStateFor,
    chosenOfferFor,
    priceOfLine,
    type LineProductOffer,
    type Membership,
    type ShoppingListLine,
} from 'src/models/shoppingList';

// ── Fixture builders ────────────────────────────────────────────────────
// Full required shape once, overridable per test — keeps each case about
// the one field it varies.

function offer(overrides: Partial<LineProductOffer> = {}): LineProductOffer {
    return {
        product_id: 'p-1',
        name: 'Milk 2L',
        brand: null,
        store_id: 's-1',
        store_name: 'Corner Shop',
        size: '2L',
        price_now: 3.5,
        price_was: null,
        is_selected: false,
        ...overrides,
    };
}

function line(overrides: Partial<ShoppingListLine> = {}): ShoppingListLine {
    return {
        line_id: 'ln-1',
        stock_item_id: 'si-1',
        product_id: null,
        stock_item_name: 'Milk',
        stock_location_id: null,
        stock_location_breadcrumb: [],
        quantity: 1,
        is_ticked: false,
        selected_product_id: null,
        sequence: 0,
        is_auto_added: false,
        actual_unit_price: null,
        purchased_store_id: null,
        purchased_store_name: null,
        planned_store_id: null,
        usual_store_id: null,
        planned_store_name: null,
        prefill_source_label: null,
        offers: [],
        deferred_by_budget: false,
        deferred_reason: null,
        stock_group_id: null,
        stock_group_name: null,
        estimated_unit_price: null,
        estimate_source: 'none',
        last_paid_store_id: null,
        last_paid_store_name: null,
        resolved_store_id: null,
        resolved_store_name: null,
        ...overrides,
    };
}

function membership(
    items: Array<{ id: string; lists: string[]; onTarget?: boolean }>,
): Membership {
    return {
        quick_add_target_list_id: null,
        items: items.map((i) => ({
            stock_item_id: i.id,
            unticked_list_ids: i.lists,
            on_quick_add_target: i.onTarget ?? false,
        })),
    };
}

// ── cartStateFor ─────────────────────────────────────────────────────────

describe('cartStateFor — cart-button state from membership', () => {
    it('is "none" without an item id or membership payload', () => {
        expect(cartStateFor(null, membership([]))).toBe('none');
        expect(cartStateFor('si-1', null)).toBe('none');
    });

    it('is "none" when the item is not on any unticked list', () => {
        expect(cartStateFor('si-1', membership([]))).toBe('none');
        expect(cartStateFor('si-1', membership([{ id: 'si-1', lists: [] }]))).toBe('none');
    });

    it('is "on_target" on exactly one list that is the quick-add target', () => {
        const m = membership([{ id: 'si-1', lists: ['list-a'], onTarget: true }]);
        expect(cartStateFor('si-1', m)).toBe('on_target');
    });

    it('is "on_other" on exactly one list that is NOT the quick-add target', () => {
        const m = membership([{ id: 'si-1', lists: ['list-a'], onTarget: false }]);
        expect(cartStateFor('si-1', m)).toBe('on_other');
    });

    it('is "on_multiple" on two or more unticked lists, regardless of target', () => {
        const m = membership([{ id: 'si-1', lists: ['list-a', 'list-b'], onTarget: true }]);
        expect(cartStateFor('si-1', m)).toBe('on_multiple');
    });

    it('keys strictly off the requested item, not its neighbours', () => {
        const m = membership([
            { id: 'si-1', lists: ['list-a'] },
            { id: 'si-2', lists: [] },
        ]);
        expect(cartStateFor('si-2', m)).toBe('none');
    });
});

// ── chosenOfferFor ──────────────────────────────────────────────────────

describe('chosenOfferFor — selected offer with cheapest fallback', () => {
    it('returns the explicitly selected offer when present', () => {
        const cheap = offer({ product_id: 'p-cheap', price_now: 2 });
        const picked = offer({ product_id: 'p-picked', price_now: 5 });
        const l = line({ offers: [cheap, picked], selected_product_id: 'p-picked' });
        expect(chosenOfferFor(l)?.product_id).toBe('p-picked');
    });

    it('falls back to the first (cheapest-sorted) offer when the selection is stale', () => {
        const cheap = offer({ product_id: 'p-cheap', price_now: 2 });
        const l = line({ offers: [cheap], selected_product_id: 'p-gone' });
        expect(chosenOfferFor(l)?.product_id).toBe('p-cheap');
    });

    it('falls back to the first offer when nothing is selected', () => {
        const l = line({ offers: [offer({ product_id: 'p-first' }), offer({ product_id: 'p-second' })] });
        expect(chosenOfferFor(l)?.product_id).toBe('p-first');
    });

    it('returns null when the line has no offers', () => {
        expect(chosenOfferFor(line())).toBeNull();
    });
});

// ── priceOfLine ─────────────────────────────────────────────────────────

// The ladder that picks the unit price (actual → last paid → offer → none)
// now lives on the server and arrives as `estimated_unit_price`; the client
// only multiplies by quantity. These tests moved with it — they used to pin
// the actual→offer fallback here, which was a second copy of a domain rule.
describe('priceOfLine — per-line display price', () => {
    it('multiplies the server-resolved estimate by quantity', () => {
        const l = line({ quantity: 3, estimated_unit_price: 2.5 });
        expect(priceOfLine(l)).toBe(7.5);
    });

    it('defaults a null quantity to 1', () => {
        const l = line({ quantity: null, estimated_unit_price: 4 });
        expect(priceOfLine(l)).toBe(4);
    });

    it('is zero when the server resolved no price', () => {
        expect(priceOfLine(line({ quantity: 5 }))).toBe(0);
    });

    it('does not re-derive the ladder from offers', () => {
        // An offer is present but the server resolved no estimate. The client
        // must not "helpfully" fall back to the offer — that is precisely the
        // duplicated rule this change removed, and it would let the two
        // disagree about what a shop costs.
        const l = line({ quantity: 2, offers: [offer({ price_now: 99 })] });
        expect(priceOfLine(l)).toBe(0);
    });

    it('does not re-derive the ladder from actual_unit_price either', () => {
        // Same reasoning from the other end: `actual` is the top rung, but the
        // server is what applies it. A line carrying an actual price with no
        // resolved estimate is a server bug, not something to paper over here.
        const l = line({ quantity: 2, actual_unit_price: 3 });
        expect(priceOfLine(l)).toBe(0);
    });

    it('uses the estimate the server picked, whatever rung it came from', () => {
        const l = line({
            quantity: 2,
            estimated_unit_price: 3,
            estimate_source: 'historic',
            offers: [offer({ price_now: 99 })],
        });
        expect(priceOfLine(l)).toBe(6);
    });
});
