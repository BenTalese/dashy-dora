// @vitest-environment jsdom
/**
 * FU-520 component layer — AddToListButton (C-7 Chunk 1/3), the unified
 * add-to-a-draft-list button behind every cart affordance (stock rows,
 * toolbars, menus, bulk bars, My Products inline lines).
 *
 * Mocking sits at the module boundary (R-003-adjacent): the four
 * composables + two Pinia stores + the API service are vi.mock'ed; the
 * Quasar chrome (QBtn/QItem/…) mounts for real, matching the pattern in
 * stockLevelDot.spec.ts. Cart-state derivation runs the REAL
 * `cartStateFor` from src/models/shoppingList — membership fixtures drive
 * the states, so the model logic is exercised too.
 */
import { flushPromises, mount } from '@vue/test-utils';
import { QBtn, QIcon, QItem, QItemSection, QPopupProxy, Quasar } from 'quasar';
import type { Membership } from 'src/models/shoppingList';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AddToListButton from 'src/components/AddToListButton.vue';

// Hoisted so the vi.mock factories below can close over them safely.
const m = vi.hoisted(() => ({
    addToList: vi.fn(),
    addItems: vi.fn(),
    removeFromList: vi.fn(),
    removeFromAllLists: vi.fn(),
    openQuickAdd: vi.fn(),
    addLineAsync: vi.fn(),
    refreshAsync: vi.fn(),
    notify: vi.fn(),
    state: {
        membership: null as Membership | null,
        stockItems: [] as Array<{ stock_item_id: string; linked_product_count?: number }>,
    },
}));

// The toasts go through `useQuasar().notify`. The real Notify plugin arms a
// 5 s auto-dismiss timer per toast that fires after jsdom tears down
// ("unhandled error from a timer"), so swap only `useQuasar` for a spy and
// keep the real components.
vi.mock('quasar', async (importOriginal) => ({
    ...(await importOriginal<typeof import('quasar')>()),
    useQuasar: () => ({ notify: m.notify }),
}));
vi.mock('src/composables/useStockItemActions', () => ({
    useStockItemActions: () => ({ addToList: m.addToList }),
}));
vi.mock('src/composables/useShoppingListActions', () => ({
    useShoppingListActions: () => ({
        addItems: m.addItems,
        removeFromList: m.removeFromList,
        removeFromAllLists: m.removeFromAllLists,
    }),
}));
vi.mock('src/composables/useQuickAdd', () => ({
    useQuickAdd: () => ({ openQuickAdd: m.openQuickAdd }),
}));
// The component reads both stores through storeToRefs. Pinia's
// storeToRefs re-wraps computeds as `() => store[key]`, which only
// unwraps on a reactive store — so the mock must be `reactive`, not a
// plain object. A computed over hoisted plain state keeps the mock at
// the store's module boundary without a real Pinia.
vi.mock('src/stores/shoppingListStore', async () => {
    const { computed, reactive } = await import('vue');
    return {
        useShoppingListStore: () => reactive({
            membership: computed(() => m.state.membership),
            refreshAsync: m.refreshAsync,
        }),
    };
});
vi.mock('src/stores/stockItemStore', async () => {
    const { computed, reactive } = await import('vue');
    return {
        useStockItemStore: () => reactive({
            stockItems: computed(() => m.state.stockItems),
        }),
    };
});
vi.mock('src/services/api/shoppingListApiService', () => ({
    default: class {
        addLineAsync = m.addLineAsync;
    },
}));

const TooltipStub = { template: '<div class="tooltip-stub"><slot /></div>' };

const ITEM = '00000000-0000-0000-0000-0000000000aa';
const PRODUCT = '00000000-0000-0000-0000-0000000000bb';

function mountButton(props: Record<string, unknown> = {}) {
    return mount(AddToListButton, {
        props,
        global: {
            plugins: [Quasar],
            components: { QBtn, QIcon, QItem, QItemSection, QPopupProxy },
            stubs: { QTooltip: TooltipStub },
        },
    });
}

/** Membership fixture: `ITEM` sits on the given unticked lists. */
function membershipWith(overrides: Partial<Membership> = {}): Membership {
    return {
        quick_add_target_list_id: null,
        items: [],
        active_lists: [],
        ...overrides,
    };
}

function onLists(listIds: string[], onTarget = false): Membership {
    return membershipWith({
        quick_add_target_list_id: onTarget ? listIds[0]! : null,
        items: [{
            stock_item_id: ITEM,
            unticked_list_ids: listIds,
            on_quick_add_target: onTarget,
        }],
        active_lists: listIds.map((id, i) => ({
            shopping_list_id: id,
            name: `List ${i + 1}`,
            status: 'draft' as const,
        })),
    });
}

beforeEach(() => {
    vi.clearAllMocks();
    m.state.membership = null;
    m.state.stockItems = [];
    m.addToList.mockResolvedValue(null);
    m.addLineAsync.mockResolvedValue({ already_on_list: false });
});

describe('AddToListButton — row variant (default)', () => {
    it('renders the add icon with an add tooltip when not on any list', () => {
        const wrapper = mountButton({ stockItemId: ITEM });

        expect(wrapper.find('.q-icon').classes()).toContain('mdi-cart-plus');
        expect(wrapper.find('button').attributes('aria-label'))
            .toBe('Add to a list');
    });

    it('swaps to a primary-coloured cart when on the quick-add target', () => {
        m.state.membership = onLists(['L1'], true);
        const wrapper = mountButton({ stockItemId: ITEM });

        expect(wrapper.find('.q-icon').classes()).toContain('mdi-cart');
        expect(wrapper.find('button').classes()).toContain('text-primary');
        expect(wrapper.find('button').attributes('aria-label'))
            .toBe('On your list. Click to remove');
    });

    it('uses the accent colour for a non-target draft list', () => {
        m.state.membership = onLists(['L1'], false);
        const wrapper = mountButton({ stockItemId: ITEM });

        expect(wrapper.find('button').classes()).toContain('text-accent');
        expect(wrapper.find('button').attributes('aria-label'))
            .toBe('On a list. Click to remove');
    });

    it('escalates to the attention checkout icon when on multiple lists', () => {
        m.state.membership = onLists(['L1', 'L2']);
        const wrapper = mountButton({ stockItemId: ITEM });

        expect(wrapper.find('.q-icon').classes()).toContain('mdi-cart-check');
        expect(wrapper.find('button').classes()).toContain('text-severity-attention');
        expect(wrapper.find('button').attributes('aria-label'))
            .toBe('On more than one list');
    });

    it('click on "none" adds via the single-item flow', async () => {
        const wrapper = mountButton({ stockItemId: ITEM });

        await wrapper.find('button').trigger('click');
        await flushPromises();

        expect(m.addToList).toHaveBeenCalledWith(ITEM);
        expect(m.removeFromList).not.toHaveBeenCalled();
    });

    it('shows the loading spinner while the add is in flight', async () => {
        let resolveAdd!: () => void;
        m.addToList.mockReturnValueOnce(
            new Promise<void>((resolve) => { resolveAdd = resolve; }),
        );
        const wrapper = mountButton({ stockItemId: ITEM });

        await wrapper.find('button').trigger('click');
        expect(wrapper.find('.q-spinner').exists()).toBe(true);

        resolveAdd();
        await flushPromises();
        expect(wrapper.find('.q-spinner').exists()).toBe(false);
    });

    it('click on a single-list state removes from that list silently', async () => {
        m.state.membership = onLists(['L1'], true);
        const wrapper = mountButton({ stockItemId: ITEM });

        await wrapper.find('button').trigger('click');
        await flushPromises();

        expect(m.removeFromList).toHaveBeenCalledWith('L1', ITEM);
        expect(m.addToList).not.toHaveBeenCalled();
    });

    it('click on on_multiple opens the manage popover instead of mutating', async () => {
        m.state.membership = onLists(['L1', 'L2']);
        const wrapper = mountButton({ stockItemId: ITEM });

        expect(wrapper.findComponent(QPopupProxy).exists()).toBe(false);
        await wrapper.find('button').trigger('click');
        await flushPromises();

        expect(wrapper.findComponent(QPopupProxy).exists()).toBe(true);
        expect(m.addToList).not.toHaveBeenCalled();
        expect(m.removeFromList).not.toHaveBeenCalled();
        expect(m.removeFromAllLists).not.toHaveBeenCalled();
    });

    it('routes 2+ linked products through the combined QuickAdd sheet', async () => {
        m.state.stockItems = [{ stock_item_id: ITEM, linked_product_count: 2 }];
        const wrapper = mountButton({ stockItemId: ITEM });

        await wrapper.find('button').trigger('click');
        await flushPromises();

        expect(m.openQuickAdd).toHaveBeenCalledWith({ stockItemId: ITEM });
        expect(m.addToList).not.toHaveBeenCalled();
    });

    it('records selected_product_id on the line when pre-decided with a target', async () => {
        m.state.membership = membershipWith({
            quick_add_target_list_id: 'L1',
            active_lists: [{ shopping_list_id: 'L1', name: 'Groceries', status: 'draft' }],
        });
        const wrapper = mountButton({
            stockItemId: ITEM,
            selectedProductId: PRODUCT,
        });

        await wrapper.find('button').trigger('click');
        await flushPromises();

        expect(m.addItems).toHaveBeenCalledWith('L1', [{
            stock_item_id: ITEM,
            selected_product_id: PRODUCT,
        }]);
        expect(m.openQuickAdd).not.toHaveBeenCalled();
    });

    it('falls back to the standard flow when pre-decided but no target', async () => {
        const wrapper = mountButton({
            stockItemId: ITEM,
            selectedProductId: PRODUCT,
        });

        await wrapper.find('button').trigger('click');
        await flushPromises();

        expect(m.addToList).toHaveBeenCalledWith(ITEM);
        expect(m.addItems).not.toHaveBeenCalled();
    });
});

describe('AddToListButton — toolbar variant', () => {
    it('labels by cart state (Add to list / On N lists)', () => {
        expect(mountButton({ stockItemId: ITEM, variant: 'toolbar' })
            .find('button').text()).toContain('Add to list');

        m.state.membership = onLists(['L1', 'L2']);
        expect(mountButton({ stockItemId: ITEM, variant: 'toolbar' })
            .find('button').text()).toContain('On 2 lists');
    });
});

describe('AddToListButton — menu variant', () => {
    it('renders a q-item whose label tracks membership', () => {
        expect(mountButton({ stockItemId: ITEM, variant: 'menu' })
            .find('.q-item').text()).toContain('Add to a list');

        m.state.membership = onLists(['L1'], true);
        expect(mountButton({ stockItemId: ITEM, variant: 'menu' })
            .find('.q-item').text()).toContain('Remove from list');
    });

    it('click runs the same primary decision tree', async () => {
        const wrapper = mountButton({ stockItemId: ITEM, variant: 'menu' });

        await wrapper.find('.q-item').trigger('click');
        await flushPromises();

        expect(m.addToList).toHaveBeenCalledWith(ITEM);
    });
});

describe('AddToListButton — bulk variant', () => {
    it('disables with no items and counts them in the label otherwise', () => {
        const empty = mountButton({ variant: 'bulk', items: [] });
        expect(empty.find('button').attributes('disabled')).toBeDefined();
        expect(empty.find('button').text()).toContain('Add to list');

        const three = mountButton({ variant: 'bulk', items: ['a', 'b', 'c'] });
        expect(three.find('button').attributes('disabled')).toBeUndefined();
        expect(three.find('button').text()).toContain('Add 3 to list');
    });

    it('batches everything into the inferred target and emits bulk-done', async () => {
        m.state.membership = membershipWith({ quick_add_target_list_id: 'L1' });
        const wrapper = mountButton({ variant: 'bulk', items: ['a', 'b', 'c'] });

        await wrapper.find('button').trigger('click');
        await flushPromises();

        expect(m.addItems).toHaveBeenCalledWith('L1', [
            { stock_item_id: 'a' },
            { stock_item_id: 'b' },
            { stock_item_id: 'c' },
        ]);
        expect(m.addToList).not.toHaveBeenCalled();
        expect(wrapper.emitted('bulk-done')).toHaveLength(1);
    });

    it('on the ambiguous path, resolves via item 1 then batches the rest into the picked list', async () => {
        // No inferred target (2+ drafts) — the first item goes through the
        // prompting single-item flow, which returns the list it landed on;
        // items 2..N must follow that same list (the original silently-dropped
        // bug when the target was read from now-removed session memory).
        m.state.membership = membershipWith();
        m.addToList.mockResolvedValue('L2');
        const wrapper = mountButton({ variant: 'bulk', items: ['a', 'b', 'c'] });

        await wrapper.find('button').trigger('click');
        await flushPromises();

        expect(m.addToList).toHaveBeenCalledWith('a');
        expect(m.addItems).toHaveBeenCalledWith('L2', [
            { stock_item_id: 'b' },
            { stock_item_id: 'c' },
        ]);
        expect(wrapper.emitted('bulk-done')).toHaveLength(1);
    });
});

describe('AddToListButton — inline-product variant', () => {
    it('disables without a productId', () => {
        const wrapper = mountButton({ variant: 'inline-product' });
        expect(wrapper.find('button').attributes('disabled')).toBeDefined();
    });

    it('adds a product-only line to the single draft and refreshes', async () => {
        m.state.membership = membershipWith({
            active_lists: [
                { shopping_list_id: 'L1', name: 'Groceries', status: 'draft' },
                { shopping_list_id: 'L9', name: 'Done', status: 'done' },
            ],
        });
        const wrapper = mountButton({
            variant: 'inline-product',
            productId: PRODUCT,
        });

        await wrapper.find('button').trigger('click');
        await flushPromises();

        expect(m.addLineAsync).toHaveBeenCalledWith('L1', { product_id: PRODUCT });
        expect(m.refreshAsync).toHaveBeenCalled();
        expect(m.notify).toHaveBeenCalledWith(expect.objectContaining({
            type: 'positive', message: 'Added as product line.',
        }));
    });

    it('does nothing but nudge when no draft list exists', async () => {
        m.state.membership = membershipWith({
            active_lists: [
                { shopping_list_id: 'L9', name: 'Done', status: 'done' },
            ],
        });
        const wrapper = mountButton({
            variant: 'inline-product',
            productId: PRODUCT,
        });

        await wrapper.find('button').trigger('click');
        await flushPromises();

        expect(m.addLineAsync).not.toHaveBeenCalled();
        expect(m.notify).toHaveBeenCalledWith(expect.objectContaining({
            type: 'info',
            message: 'No draft list yet. Create one first to add this product.',
        }));
    });
});
