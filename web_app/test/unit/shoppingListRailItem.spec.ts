// @vitest-environment jsdom
/**
 * FU-520 component layer — ShoppingListRailItem.
 *
 * One row of the shopping-lists rail (UX-v2 §3.1): status icon, the
 * server-resolved display name and an item-count chip (2026-09-27: the date
 * caption and the "next up" marker went). Quasar chrome mounts for real (pattern from stockLevelDot /
 * addToListButton specs).
 *
 * The four copy/delete kebab cases were deleted on 2026-08-28 along with the
 * kebab itself — both actions were already reachable from the list you're
 * looking at, and copy went entirely in favour of Save as template.
 */
import { mount } from '@vue/test-utils';
import {
    QBadge, QIcon, QItem, QItemLabel, QItemSection, QList, Quasar,
} from 'quasar';
import type { ShoppingListSummary } from 'src/models/shoppingList';
import { describe, expect, it } from 'vitest';

import ShoppingListRailItem from 'src/components/shoppingList/ShoppingListRailItem.vue';

function summaryOf(overrides: Partial<ShoppingListSummary> = {}): ShoppingListSummary {
    return {
        shopping_list_id: 'L1',
        name: null,
        display_name: 'Weekly shop',
        status: 'active',
        created_at: '2026-07-01T00:00:00Z',
        completed_at: null,
        planned_shop_date: null,
        effective_date: '2026-07-10',
        is_next_up: false,
        line_count: 5,
        ticked_count: 2,
        ...overrides,
    };
}

function mountRow(summary: ShoppingListSummary, active = false) {
    return mount(ShoppingListRailItem, {
        props: { summary, active },
        global: {
            plugins: [Quasar],
            components: { QItem, QItemSection, QItemLabel, QIcon, QBadge, QList },
        },
    });
}

describe('ShoppingListRailItem', () => {
    it('renders the display name and the item count as a chip', () => {
        const wrapper = mountRow(summaryOf());

        expect(wrapper.text()).toContain('Weekly shop');
        const chip = wrapper.find('.sl-rail-item__count');
        expect(chip.text()).toBe('5');
        expect(chip.attributes('aria-label')).toBe('5 items');
    });

    it('omits the count chip on an empty list', () => {
        const wrapper = mountRow(summaryOf({ status: 'active', line_count: 0, ticked_count: 0 }));

        expect(wrapper.find('.sl-rail-item__count').exists()).toBe(false);
    });

    it('singularises the count label', () => {
        const wrapper = mountRow(summaryOf({ status: 'active', line_count: 1, ticked_count: 0 }));

        expect(wrapper.find('.sl-rail-item__count').attributes('aria-label')).toBe('1 item');
    });

    it('never shows a "next up" marker or a date caption', () => {
        const wrapper = mountRow(summaryOf({ is_next_up: true }));
        expect(wrapper.text()).not.toContain('next up');
        expect(wrapper.text()).not.toMatch(/2026|10\/07/);
    });

    it('colours the status icon of an open list primary', () => {
        const icon = mountRow(summaryOf({ status: 'active' })).find('.q-icon');
        expect(icon.classes()).toContain('text-primary');
    });

    it('mutes the status icon and dims the row when done', () => {
        const wrapper = mountRow(summaryOf({ status: 'done' }));
        // R-002: done is the neutral state — no palette colour, muted text.
        expect(wrapper.find('.q-icon').classes()).toContain('dora-text-muted');
        expect(wrapper.find('.q-item').classes()).toContain('sl-rail-item-done');
    });

    it('emits select when the row is clicked', async () => {
        const wrapper = mountRow(summaryOf());

        await wrapper.find('.q-item').trigger('click');

        expect(wrapper.emitted('select')).toHaveLength(1);
    });
});
