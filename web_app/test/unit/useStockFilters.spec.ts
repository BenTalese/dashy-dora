// @vitest-environment jsdom
// FU-520 workstream 1 — behavioural coverage for the pantry filter engine.
//
// `useStockFilters` owns every filter / sort / summary rule on the stock
// overview (and any future stock-item picker). The composable takes its data
// as getter functions precisely so it can be exercised with fixtures — no
// pinia, no network. The rules pinned here are the ones that silently regress:
// the "empty = off" (A4) filter contract, the Model-C needs-attention rule,
// the nulls-last expiry sort, and the footer's filtered-view counts.
//
// DETERMINISM: the clock is pinned (expiry math uses Date.now); sorting uses
// an explicit 'en' collator inside the composable, so no machine-locale drift.
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { clearAllListState } from 'src/composables/useListState';
import { migrateStockSort, useStockFilters } from 'src/composables/useStockFilters';
import type { LocationNode } from 'src/models/location';
import type { Recipe } from 'src/models/recipe';
import type { Membership } from 'src/models/shoppingList';
import type { StockGroup } from 'src/models/stockGroup';
import type { StockItem } from 'src/models/stockItem';
import type { StockLevel } from 'src/models/stockLevel';
import { vi } from 'vitest';

// Pinned "now": 2026-07-10 12:00 UTC. Expiry fixtures are offsets from this.
const NOW = new Date('2026-07-10T12:00:00.000Z');

// ── Fixtures ────────────────────────────────────────────────────────────

const LEVELS: StockLevel[] = [
    { stock_level_id: 'lv-stocked', name: 'Stocked', sequence: 0 },
    { stock_level_id: 'lv-low', name: 'Low Stock', sequence: 1 },
    { stock_level_id: 'lv-out', name: 'Out of Stock', sequence: 2 },
];

function item(overrides: Partial<StockItem> & Pick<StockItem, 'stock_item_id' | 'name'>): StockItem {
    return {
        stock_group_id: null,
        stock_level_id: 'lv-stocked',
        stock_location_id: null,
        ...overrides,
    };
}

// Six items exercising the attention rule. `needs_attention` /
// `attention_kinds` are stated the way the SERVER would state them
// (`stock_attention.py`) — the client reads them and no longer re-derives
// anything from level + expiry, so a fixture that only set `expiry_date`
// would be describing an item the API could never return.
//   apple  — stocked, plain                        (quiet)
//   bread  — essential + low                       (essential_low, rank 3)
//   cheese — essential + out                       (essential_low, rank 1)
//   dill   — expiring in 3 days                    (expiring_soon,  rank 2)
//   egg    — already expired                       (expired,        rank 0)
//   flour  — low but NOT essential, currently open (quiet — Step-0 Q1)
// `attention_rank` is the server's urgency ORDER (stock_attention.py):
// expired → essential-out → expiring-soon → essential-low. Note cheese and
// bread share a kind and a severity but not a rank — out is worse than low.
const ITEMS: StockItem[] = [
    item({ stock_item_id: 'si-apple', name: 'Apple', stock_location_id: 'loc-pantry', stock_group_id: 'grp-fresh', stock_level_last_updated: '2026-07-01T00:00:00Z' }),
    item({ stock_item_id: 'si-bread', name: 'Bread', stock_level_id: 'lv-low', is_essential: true, stock_location_id: 'loc-pantry', stock_level_last_updated: '2026-07-09T00:00:00Z', needs_attention: true, attention_severity: 'high', attention_kinds: ['essential_low'], attention_rank: 3 }),
    item({ stock_item_id: 'si-cheese', name: 'Cheese', stock_level_id: 'lv-out', is_essential: true, needs_attention: true, attention_severity: 'high', attention_kinds: ['essential_low'], attention_rank: 1 }),
    item({ stock_item_id: 'si-dill', name: 'Dill', expiry_date: '2026-07-13', stock_location_id: 'loc-shelf', stock_group_id: 'grp-fresh', needs_attention: true, attention_severity: 'medium', attention_kinds: ['expiring_soon'], attention_rank: 2 }),
    item({ stock_item_id: 'si-egg', name: 'Egg', expiry_date: '2026-07-01', needs_attention: true, attention_severity: 'high', attention_kinds: ['expired'], attention_rank: 0 }),
    item({ stock_item_id: 'si-flour', name: 'Flour', stock_level_id: 'lv-low', is_open: true, stock_level_last_updated: '2026-07-05T00:00:00Z' }),
];

const TREE: LocationNode[] = [
    {
        location_id: 'loc-pantry',
        name: 'Pantry',
        kind: 'zone',
        parent_id: null,
        sequence: 0,
        direct_item_count: 2,
        descendant_item_count: 3,
        items: [],
        children: [
            {
                location_id: 'loc-shelf',
                name: 'Middle shelf',
                kind: 'section',
                parent_id: 'loc-pantry',
                sequence: 0,
                direct_item_count: 1,
                descendant_item_count: 1,
                items: [],
                children: [],
            },
        ],
    },
];

const GROUPS: StockGroup[] = [
    { stock_group_id: 'grp-fresh', name: 'Fresh produce' },
];

// Recipe fixture — only the fields the composable reads. The full Recipe
// type is a large DTO; building it wholesale would drown the test in noise.
const RECIPES = [
    {
        recipe_id: 'rcp-pie',
        name: 'Apple pie',
        ingredients: [
            { stock_item_id: 'si-apple' },
            { stock_item_id: 'si-egg' },
            { stock_item_id: null },
        ],
    },
] as unknown as Recipe[];

const MEMBERSHIP: Membership = {
    quick_add_target_list_id: 'list-a',
    items: [
        { stock_item_id: 'si-apple', unticked_list_ids: ['list-a'], on_quick_add_target: true },
        { stock_item_id: 'si-bread', unticked_list_ids: ['list-a', 'list-b'], on_quick_add_target: true },
    ],
};

/**
 * Build the composable over the standard fixture set, pinned to NAME-ascending.
 *
 * The composable's own default axis is `attention` (D-9, Chunk 4) — asserted
 * separately below. Every filtering test here is about *which* items survive a
 * predicate, and reading those assertions is far easier against alphabetical
 * order than against an urgency ramp that shifts whenever a fixture's
 * attention state changes. Sorting tests set their own axis anyway.
 */
function makeFilters(overrides: {
    membership?: Membership | null;
} = {}) {
    const filters = makeFiltersOnDefaultSort(overrides);
    filters.sortBy.value = 'name';
    filters.sortDir.value = 'asc';
    return filters;
}

/** Same fixtures, sort left exactly as the composable ships it. */
function makeFiltersOnDefaultSort(overrides: {
    membership?: Membership | null;
} = {}) {
    return useStockFilters({
        stockItems: () => ITEMS,
        stockLevels: () => LEVELS,
        locationTree: () => TREE,
        recipes: () => RECIPES,
        stockGroups: () => GROUPS,
        membership: () => ('membership' in overrides ? overrides.membership ?? null : MEMBERSHIP),
    });
}

function names(filters: ReturnType<typeof makeFilters>): string[] {
    return filters.filteredStockItems.value.map((i) => i.name);
}

beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    clearAllListState();
});
afterEach(() => {
    vi.useRealTimers();
});

// ── Filtering ───────────────────────────────────────────────────────────

describe('useStockFilters — filtering', () => {
    it('shows everything, name-ascending, when no filter is active', () => {
        const f = makeFilters();
        expect(names(f)).toEqual(['Apple', 'Bread', 'Cheese', 'Dill', 'Egg', 'Flour']);
        expect(f.activeFilterCount.value).toBe(0);
    });

    it('search is case-insensitive and every whitespace-separated token must match', () => {
        // "full cream" is one search, not two: matching ANY token made a
        // two-word query wider than either word alone (QA 2026-10-30).
        const f = makeFilters();
        f.searchText.value = '  APP   egg ';
        expect(names(f)).toEqual([]);
        f.searchText.value = ' ap LE ';
        expect(names(f)).toEqual(['Apple']);
    });

    it('search with no hits yields an empty list, not an error', () => {
        const f = makeFilters();
        f.searchText.value = 'zzz';
        expect(names(f)).toEqual([]);
    });

    it('level filter: null means OFF, an id narrows to that level (A4)', () => {
        const f = makeFilters();
        expect(f.levelFilter.value).toBeNull();
        f.levelFilter.value = 'lv-low';
        expect(names(f)).toEqual(['Bread', 'Flour']);
        f.levelFilter.value = null;
        expect(names(f)).toHaveLength(6);
    });

    it('location filter matches the exact node only (no descendant roll-up)', () => {
        const f = makeFilters();
        f.locationFilter.value = 'loc-pantry';
        expect(names(f)).toEqual(['Apple', 'Bread']);
        f.locationFilter.value = 'loc-shelf';
        expect(names(f)).toEqual(['Dill']);
    });

    it('group filter narrows to the selected stock group', () => {
        const f = makeFilters();
        f.groupFilter.value = 'grp-fresh';
        expect(names(f)).toEqual(['Apple', 'Dill']);
    });

    it('essentials-only keeps just the flagged items', () => {
        const f = makeFilters();
        f.essentialsOnly.value = true;
        expect(names(f)).toEqual(['Bread', 'Cheese']);
    });

    it('open-only keeps just the currently-open items', () => {
        const f = makeFilters();
        f.openOnly.value = true;
        expect(names(f)).toEqual(['Flour']);
    });

    it('needs-attention narrows to what the SERVER flagged, nothing re-derived', () => {
        const f = makeFilters();
        f.hasAlertOnly.value = true;
        // Flour (low, not essential) deliberately absent — Step-0 Q1.
        expect(names(f)).toEqual(['Bread', 'Cheese', 'Dill', 'Egg']);
    });

    // The two "needs-check" cases were deleted 2026-08-21 with the chip: the
    // stocktake queue is no longer a filter axis here (it still paints the
    // row's dashed marker, which StockOverview owns).

    it('expiring-soon keeps the expiry-flagged items (FU-583 freshness deep-link)', () => {
        const f = makeFilters();
        f.expiringSoonOnly.value = true;
        // Dill is expiring_soon, Egg is expired; both are the expiry axis.
        // The chip reads the server's kinds rather than re-measuring days,
        // so the admin's configurable window governs it too (B1).
        expect(names(f)).toEqual(['Dill', 'Egg']);
        expect(f.activeFilterCount.value).toBe(1);
    });

    it('cart filter: on_list keeps items on any unticked list, off_list the rest', () => {
        const f = makeFilters();
        f.cartFilter.value = 'on_list';
        expect(names(f)).toEqual(['Apple', 'Bread']);
        f.cartFilter.value = 'off_list';
        expect(names(f)).toEqual(['Cheese', 'Dill', 'Egg', 'Flour']);
    });

    it('cart filter treats a missing membership payload as nothing-on-a-list', () => {
        const f = makeFilters({ membership: null });
        f.cartFilter.value = 'on_list';
        expect(names(f)).toEqual([]);
    });

    it('recipe filter narrows to the recipe\'s linked ingredients and exposes its name', () => {
        const f = makeFilters();
        f.recipeFilter.value = 'rcp-pie';
        expect(names(f)).toEqual(['Apple', 'Egg']);
        expect(f.recipeFilterContext.value?.name).toBe('Apple pie');
    });

    it('an orphaned recipe id silently disables the filter rather than emptying the list', () => {
        const f = makeFilters();
        f.recipeFilter.value = 'rcp-deleted';
        expect(f.recipeFilterContext.value).toBeNull();
        expect(names(f)).toHaveLength(6);
    });

    it('filters compose with AND semantics', () => {
        const f = makeFilters();
        f.levelFilter.value = 'lv-low';
        f.essentialsOnly.value = true;
        expect(names(f)).toEqual(['Bread']);
    });

    it('attention is the server\'s answer even when the level says otherwise', () => {
        // The item claims a Stocked level and carries no expiry date, so every
        // client-side rule that ever existed would call it quiet. The server
        // says it needs attention, and the server wins — that is the whole
        // point of Chunk 3b (B1–B4 were all the client disagreeing).
        const overridden: StockItem[] = [
            item({
                stock_item_id: 'si-x', name: 'X', is_essential: true,
                needs_attention: true, attention_severity: 'high',
                attention_kinds: ['essential_low'],
            }),
        ];
        const f = useStockFilters({
            stockItems: () => overridden,
            stockLevels: () => LEVELS,
            locationTree: () => [],
            recipes: () => [],
            stockGroups: () => [],
            membership: () => null,
        });
        f.hasAlertOnly.value = true;
        expect(names(f)).toEqual(['X']);
    });
});

// ── Sorting ─────────────────────────────────────────────────────────────

describe('useStockFilters — sorting', () => {
    // Direction moved off the option list and onto the shared SortControl
    // toggle (2026-08-18), so these assert axis + direction. The expected
    // orderings are unchanged from the six-combined-key era on purpose —
    // that's what makes them a regression check on the rewrite, not just a
    // restatement of the new code.
    // ── The default axis (D-9, Chunk 4) ─────────────────────────────────
    // Three bands, and they must be the SAME three the row paints (D-8):
    // outlined on top, plain in the middle, dimmed at the bottom. If these
    // two ever disagree the page tells the user one thing with position and
    // the opposite with colour, which is the defect the whole chunk exists
    // to remove.
    it('defaults to the attention axis, most urgent first', () => {
        const f = makeFiltersOnDefaultSort();
        expect(f.sortBy.value).toBe('attention');
        expect(f.sortDir.value).toBe('asc');
        // Band 0, by the server's urgency rank (2026-08-21): Egg is expired,
        // Cheese is an essential that's OUT, Dill is expiring soon, Bread is an
        // essential merely LOW. This used to be severity-then-name, which tied
        // Egg with Bread and Cheese (all `high`) and fell through to the
        // alphabet — the "seems a bit random" the owner reported.
        // Band 1: Apple, Flour (low but not essential — Step-0 Q1 says quiet).
        expect(names(f)).toEqual(['Egg', 'Cheese', 'Dill', 'Bread', 'Apple', 'Flour']);
    });

    it('sinks out-of-stock non-essentials below ordinary rows, and flips whole', () => {
        // Needs its own fixture set: the shared one has no band-2 item, and
        // adding one there would move every count assertion in this file.
        const items: StockItem[] = [
            item({ stock_item_id: 'si-1', name: 'Quiet', stock_level_id: 'lv-stocked' }),
            item({
                stock_item_id: 'si-2', name: 'Ignorable', stock_level_id: 'lv-out',
                is_out_of_stock: true,
            }),
            item({
                stock_item_id: 'si-3', name: 'Urgent', stock_level_id: 'lv-out',
                is_out_of_stock: true, is_essential: true,
                needs_attention: true, attention_severity: 'high',
                attention_kinds: ['essential_low'],
            }),
        ];
        const f = useStockFilters({
            stockItems: () => items,
            stockLevels: () => LEVELS,
            locationTree: () => [],
            recipes: () => [],
            stockGroups: () => [],
            membership: () => null,
        });
        expect(names(f)).toEqual(['Urgent', 'Quiet', 'Ignorable']);
        // Descending reverses the ramp end to end — it does NOT hold the
        // dimmed band at the bottom (unlike the expiry axis's nulls, which
        // are a property of the data rather than of urgency).
        f.sortDir.value = 'desc';
        expect(names(f)).toEqual(['Ignorable', 'Quiet', 'Urgent']);
    });

    it('name descending reverses the alphabetical order', () => {
        const f = makeFilters();
        f.sortBy.value = 'name';
        f.sortDir.value = 'desc';
        expect(names(f)).toEqual(['Flour', 'Egg', 'Dill', 'Cheese', 'Bread', 'Apple']);
    });

    it('level ascending puts the most-depleted items first, ties broken by name', () => {
        const f = makeFilters();
        f.sortBy.value = 'level';
        f.sortDir.value = 'asc';
        expect(names(f)).toEqual(['Cheese', 'Bread', 'Flour', 'Apple', 'Dill', 'Egg']);
    });

    it('level descending puts the best-stocked items first', () => {
        const f = makeFilters();
        f.sortBy.value = 'level';
        f.sortDir.value = 'desc';
        expect(names(f)).toEqual(['Apple', 'Dill', 'Egg', 'Bread', 'Flour', 'Cheese']);
    });

    it('updated descending orders by last stock-level touch, newest first', () => {
        const f = makeFilters();
        f.sortBy.value = 'updated';
        f.sortDir.value = 'desc';
        // Bread (07-09) > Flour (07-05) > Apple (07-01) > the never-updated.
        expect(names(f).slice(0, 3)).toEqual(['Bread', 'Flour', 'Apple']);
    });

    it('expiry ascending puts nearest expiry first and items without a date last', () => {
        const f = makeFilters();
        f.sortBy.value = 'expiry';
        f.sortDir.value = 'asc';
        expect(names(f).slice(0, 2)).toEqual(['Egg', 'Dill']);
        // No-expiry items follow, ordered by least-recently-updated then name:
        // Cheese has no update date → first, then Apple (07-01) < Flour
        // (07-05) < Bread (07-09).
        expect(names(f).slice(2)).toEqual(['Cheese', 'Apple', 'Flour', 'Bread']);
    });

    it('expiry descending flips the dated items but still sinks the undated', () => {
        const f = makeFilters();
        f.sortBy.value = 'expiry';
        f.sortDir.value = 'desc';
        // Nulls-last is a property of the data, not the direction — reversing
        // must not float the no-expiry items to the top.
        expect(names(f).slice(0, 2)).toEqual(['Dill', 'Egg']);
        expect(names(f).slice(2)).toEqual(['Cheese', 'Apple', 'Flour', 'Bread']);
    });
});

describe('migrateStockSort — persisted sorts survive the axis/direction split', () => {
    it('translates every legacy combined key to the pair it meant', () => {
        expect(migrateStockSort('name_asc')).toEqual({ sortBy: 'name', sortDir: 'asc' });
        expect(migrateStockSort('name_desc')).toEqual({ sortBy: 'name', sortDir: 'desc' });
        expect(migrateStockSort('level_lowest')).toEqual({ sortBy: 'level', sortDir: 'asc' });
        expect(migrateStockSort('level_highest')).toEqual({ sortBy: 'level', sortDir: 'desc' });
        expect(migrateStockSort('updated_recent')).toEqual({ sortBy: 'updated', sortDir: 'desc' });
        expect(migrateStockSort('expiry_asc')).toEqual({ sortBy: 'expiry', sortDir: 'asc' });
    });

    it('leaves an already-migrated axis alone, on its conventional direction', () => {
        expect(migrateStockSort('expiry')).toEqual({ sortBy: 'expiry', sortDir: 'asc' });
        expect(migrateStockSort('updated')).toEqual({ sortBy: 'updated', sortDir: 'desc' });
    });

    it('falls back to the DEFAULT axis (attention) for junk or missing values', () => {
        // D-9 moved the default off Name. A stored 'name' is still honoured —
        // that's a choice someone made — but nothing stored means the new
        // default, not the old one.
        expect(migrateStockSort(null)).toEqual({ sortBy: 'attention', sortDir: 'asc' });
        expect(migrateStockSort('nonsense')).toEqual({ sortBy: 'attention', sortDir: 'asc' });
        expect(migrateStockSort('name')).toEqual({ sortBy: 'name', sortDir: 'asc' });
    });
});

// ── Options and helpers ──────────────────────────────────────

describe('useStockFilters — options and helpers', () => {
    it('location options render full "parent › child" paths, alphabetically', () => {
        const f = makeFilters();
        expect(f.allLocationOptions.value).toEqual([
            { label: 'Pantry', value: 'loc-pantry' },
            { label: 'Pantry › Middle shelf', value: 'loc-shelf' },
        ]);
    });

    it('filterLocations narrows the searchable options and restores on empty', () => {
        const f = makeFilters();
        const runNow = (cb: () => void) => cb();
        f.filterLocations('shelf', runNow);
        expect(f.locationOptions.value).toEqual([
            { label: 'Pantry › Middle shelf', value: 'loc-shelf' },
        ]);
        f.filterLocations('', runNow);
        expect(f.locationOptions.value).toHaveLength(2);
    });

    it('activeFilterCount counts set filters but never the search text', () => {
        const f = makeFilters();
        f.searchText.value = 'milk';
        expect(f.activeFilterCount.value).toBe(0);
        f.levelFilter.value = 'lv-low';
        f.essentialsOnly.value = true;
        f.cartFilter.value = 'on_list';
        expect(f.activeFilterCount.value).toBe(3);
    });

    it('clearFilters resets every filter and the search box', () => {
        const f = makeFilters();
        f.searchText.value = 'x';
        f.levelFilter.value = 'lv-low';
        f.essentialsOnly.value = true;
        f.openOnly.value = true;
        f.hasAlertOnly.value = true;
        f.expiringSoonOnly.value = true;
        f.cartFilter.value = 'on_list';
        f.recipeFilter.value = 'rcp-pie';

        f.clearFilters();

        expect(names(f)).toHaveLength(6);
        expect(f.activeFilterCount.value).toBe(0);
        expect(f.searchText.value).toBe('');
    });

    it('footerCounts reflect the FILTERED view with shortened level labels', () => {
        const f = makeFilters();
        f.levelFilter.value = 'lv-low';
        const counts = f.footerCounts.value;
        const byLabel = new Map(counts.map((c) => [c.label, c.value]));

        expect(byLabel.get('Shown')).toBe(2); // Bread + Flour
        expect(byLabel.get('Needs attention')).toBe(1); // Bread only (Model C)
        // "Low Stock" / "Out of Stock" are shortened for the sticky row.
        expect(byLabel.get('Low')).toBe(2);
        expect(byLabel.get('Out')).toBe(0);
        expect(byLabel.get('Stocked')).toBe(0);
        expect(byLabel.get('Essential')).toBe(1); // Bread
        expect(byLabel.get('On a list')).toBe(1); // Bread (on two lists → counted once)
    });
});
