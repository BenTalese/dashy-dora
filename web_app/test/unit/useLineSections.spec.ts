// Sectioning for the shopping-list plan/run faces. Pure logic, no Vue
// components — the rules worth pinning are the ones that only bite installs
// that leave location/group/store empty, which is most of them.
import { computed, ref } from 'vue';
import { describe, expect, it } from 'vitest';

import {
    SECTION_MODES,
    sectionProgress,
    useLineSections,
    withNestedChildren,
    type SectionMode,
} from 'src/composables/useLineSections';
import type { ShoppingListLine } from 'src/models/shoppingList';

function line(overrides: Partial<ShoppingListLine> = {}): ShoppingListLine {
    return {
        line_id: `ln-${Math.random().toString(36).slice(2)}`,
        stock_item_id: 'si-1',
        product_id: null,
        stock_item_name: 'Item',
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

function setup(lines: ShoppingListLine[], mode: SectionMode, hideTicked = false) {
    return useLineSections(computed(() => lines), ref(mode), {
        hideTicked: computed(() => hideTicked),
    });
}

describe('availability — a mode with no data disables itself', () => {
    it('marks every field-backed mode unavailable on a bare list', () => {
        const { availableModes } = setup([line(), line()], 'none');
        expect(availableModes.value.location).toBe(false);
        expect(availableModes.value.group).toBe(false);
        expect(availableModes.value.store).toBe(false);
    });

    it('always keeps the ungrouped mode available — it needs no data', () => {
        const { availableModes } = setup([], 'none');
        expect(availableModes.value.none).toBe(true);
    });

    it('needs only one line with a value to make a mode available', () => {
        const { availableModes } = setup(
            [line(), line({ stock_group_name: 'Baking' })],
            'group',
        );
        expect(availableModes.value.group).toBe(true);
    });

    it('reads store availability from the resolved store, not the offers', () => {
        // The whole point of the store ladder: someone with no products at all
        // still gets store sectioning off their usual-store tags.
        const { availableModes } = setup([line({ resolved_store_name: 'Aldi' })], 'store');
        expect(availableModes.value.store).toBe(true);
    });
});

describe('effective mode — a stale preference cannot strand the user', () => {
    it('falls back to ungrouped when the chosen mode has no data', () => {
        const { effectiveMode, sections } = setup([line(), line()], 'location');
        expect(effectiveMode.value).toBe('none');
        expect(sections.value).toHaveLength(1);
    });

    it('honours the chosen mode as soon as data exists', () => {
        const { effectiveMode } = setup(
            [line({ stock_location_breadcrumb: ['Kitchen', 'Fridge'] })],
            'location',
        );
        expect(effectiveMode.value).toBe('location');
    });
});

describe('sectioning', () => {
    it('sections location by the top crumb, not the leaf', () => {
        const { sections } = setup([
            line({ stock_item_name: 'Butter', stock_location_breadcrumb: ['Kitchen', 'Fridge'] }),
            line({ stock_item_name: 'Milk', stock_location_breadcrumb: ['Kitchen', 'Door'] }),
        ], 'location');

        expect(sections.value).toHaveLength(1);
        expect(sections.value[0]!.label).toBe('Kitchen');
    });

    it('puts valueless lines in a trailing Unsorted section, never dropping them', () => {
        const { sections, orderedLines } = setup([
            line({ stock_item_name: 'Rice' }),
            line({ stock_item_name: 'Butter', stock_group_name: 'Dairy' }),
        ], 'group');

        expect(sections.value.map((s) => s.label)).toEqual(['Dairy', 'Unsorted']);
        expect(sections.value[1]!.isUnsorted).toBe(true);
        expect(orderedLines.value).toHaveLength(2);
    });

    it('keeps Unsorted last even when it sorts first alphabetically', () => {
        const { sections } = setup([
            line({ stock_group_name: 'Zucchini things' }),
            line(),
        ], 'group');
        expect(sections.value.at(-1)!.isUnsorted).toBe(true);
    });

    it('sorts alphabetically within a section', () => {
        const { sections } = setup([
            line({ stock_item_name: 'Rice', stock_group_name: 'Pantry' }),
            line({ stock_item_name: 'Beans', stock_group_name: 'Pantry' }),
        ], 'group');
        expect(sections.value[0]!.lines.map((l) => l.stock_item_name)).toEqual(['Beans', 'Rice']);
    });

    it('leaves the ungrouped mode as one unlabelled run in sequence order', () => {
        const { sections } = setup([
            line({ stock_item_name: 'Rice' }),
            line({ stock_item_name: 'Beans' }),
        ], 'none');

        expect(sections.value).toHaveLength(1);
        expect(sections.value[0]!.label).toBeNull();
        expect(sections.value[0]!.lines.map((l) => l.stock_item_name)).toEqual(['Rice', 'Beans']);
    });
});

describe('hideTicked — the run face shrinks as you shop', () => {
    it('drops ticked lines when asked', () => {
        const { orderedLines } = setup([
            line({ stock_item_name: 'Butter', is_ticked: true }),
            line({ stock_item_name: 'Milk' }),
        ], 'none', true);

        expect(orderedLines.value.map((l) => l.stock_item_name)).toEqual(['Milk']);
    });

    it('keeps them when not asked (plan face dims instead)', () => {
        const { orderedLines } = setup([
            line({ is_ticked: true }),
            line(),
        ], 'none', false);
        expect(orderedLines.value).toHaveLength(2);
    });
});

describe('nested product lines survive sectioning', () => {
    it('places a nested child immediately after its parent', () => {
        const parent = line({ line_id: 'p', stock_item_id: 'si-9', stock_item_name: 'Butter' });
        const child = line({ line_id: 'c', stock_item_id: 'si-9', product_id: 'pr-1', stock_item_name: 'Butter 500g' });
        const other = line({ line_id: 'o', stock_item_id: 'si-8', stock_item_name: 'Milk' });

        const out = withNestedChildren([parent, other, child]);
        expect(out.map((l) => l.line_id)).toEqual(['p', 'c', 'o']);
    });

    it('keeps an orphaned child in place rather than losing it', () => {
        const orphan = line({ line_id: 'c', stock_item_id: 'si-9', product_id: 'pr-1' });
        expect(withNestedChildren([orphan]).map((l) => l.line_id)).toEqual(['c']);
    });
});

describe('sectionProgress — drives the run face collapse', () => {
    it('reports a section cleared once every member is picked', () => {
        const lines = [
            line({ stock_group_name: 'Dairy', is_ticked: true }),
            line({ stock_group_name: 'Dairy', is_ticked: true }),
        ];
        const { sections } = setup(lines, 'group', true);
        // The section has emptied from view, but progress reads the full list.
        const progress = sectionProgress(lines, { key: 'Dairy', label: 'Dairy', lines: [], isUnsorted: false }, 'group');
        expect(progress).toEqual({ total: 2, picked: 2, cleared: true });
        expect(sections.value).toHaveLength(0);
    });

    it('is not cleared while anything remains', () => {
        const lines = [
            line({ stock_group_name: 'Dairy', is_ticked: true }),
            line({ stock_group_name: 'Dairy' }),
        ];
        const progress = sectionProgress(lines, { key: 'Dairy', label: 'Dairy', lines: [], isUnsorted: false }, 'group');
        expect(progress.cleared).toBe(false);
        expect(progress.picked).toBe(1);
    });

    it('never reports an empty section as cleared', () => {
        const progress = sectionProgress([], { key: 'x', label: 'x', lines: [], isUnsorted: false }, 'group');
        expect(progress.cleared).toBe(false);
    });
});

describe('mode list', () => {
    it('exposes the four agreed modes in order', () => {
        expect(SECTION_MODES).toEqual(['location', 'group', 'store', 'none']);
    });
});
