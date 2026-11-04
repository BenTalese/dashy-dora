// @vitest-environment jsdom
// FU-934 / finalisation 06-R32 (CHUNK_06 test plan: `lifecycleTimeline.spec.ts`).
//
// The stock-item History tab's timeline used to be a computed inside
// `StockItemDetailPage.vue`; the page split lifted it into the pure
// `helpers/lifecycleTimeline.ts`. Pinned here: the merge across event kinds,
// newest-first ordering (date-only rows at local midnight), the
// restocked / dropped wording keyed to the level *sequence* (never the name),
// and the synthetic Opened / Checked rows.
//
// Pure functions, no network — but `formatMoney` / `formatDate` sit in modules
// that import the http client (and so Quasar's client bundle), hence jsdom.
import { describe, expect, it } from 'vitest';

import { buildLifecycleTimeline, eventTime } from 'src/helpers/lifecycleTimeline';
import { LOW_STOCK_SEQUENCE, STOCKED_SEQUENCE } from 'src/helpers/stockStatus';
import type { StockItemDetail } from 'src/models/stockItemDetail';

function detail(overrides: Partial<StockItemDetail>): StockItemDetail {
    return {
        level_history: [],
        waste_events: [],
        recent_list_adds: [],
        purchase_events: [],
        cook_events: [],
        expiry_events: [],
        is_open: false,
        opened_on: null,
        last_checked_at: null,
        ...overrides,
    } as unknown as StockItemDetail;
}

describe('buildLifecycleTimeline', () => {
    it('is empty for an item with no history', () => {
        expect(buildLifecycleTimeline(detail({}))).toEqual([]);
    });

    it('merges every kind and sorts newest first', () => {
        const events = buildLifecycleTimeline(detail({
            level_history: [
                { changed_at: '2026-10-01T09:00:00Z', stock_level_name: 'Stocked', stock_level_sequence: STOCKED_SEQUENCE },
            ],
            waste_events: [{ occurred_at: '2026-10-03T09:00:00Z', reason: 'expired' }],
            recent_list_adds: [{ added_at: '2026-10-02T09:00:00Z', shopping_list_id: 'l1', shopping_list_name: 'Weekly' }],
            cook_events: [{ occurred_at: '2026-10-04T09:00:00Z', recipe_id: null, recipe_name: 'Soup', meals_cooked: 3 }],
        }));
        expect(events.map((e) => e.id.split('-')[0])).toEqual(['cook', 'waste', 'add', 'level']);
        expect(events[0]!.title).toBe('Used in Soup · 3 meals');
        expect(events[2]!.title).toBe('Added to Weekly');
    });

    it('names a move out of / into short stock by sequence, not by name', () => {
        const events = buildLifecycleTimeline(detail({
            level_history: [
                // Deliberately out of order: the helper walks them forwards in time.
                { changed_at: '2026-10-03T09:00:00Z', stock_level_name: 'Plenty', stock_level_sequence: STOCKED_SEQUENCE },
                { changed_at: '2026-10-01T09:00:00Z', stock_level_name: 'Plenty', stock_level_sequence: STOCKED_SEQUENCE },
                { changed_at: '2026-10-02T09:00:00Z', stock_level_name: 'Getting low', stock_level_sequence: LOW_STOCK_SEQUENCE },
            ],
        }));
        expect(events.map((e) => e.title)).toEqual([
            'Restocked → Plenty',
            'Dropped to Getting low',
            'Level → Plenty',
        ]);
    });

    it('adds Opened from current state and Checked only when it is not the last level change', () => {
        const sameAsLevel = buildLifecycleTimeline(detail({
            level_history: [
                { changed_at: '2026-10-01T09:00:00Z', stock_level_name: 'Stocked', stock_level_sequence: STOCKED_SEQUENCE },
            ],
            last_checked_at: '2026-10-01T09:00:00Z',
        }));
        expect(sameAsLevel.some((e) => e.id.startsWith('checked-'))).toBe(false);

        const events = buildLifecycleTimeline(detail({
            is_open: true,
            opened_on: '2026-10-05',
            last_checked_at: '2026-10-06T09:00:00Z',
        }));
        expect(events.map((e) => e.title)).toEqual(['Checked (still correct)', 'Opened']);
        // A date-only row keeps its calendar date and sorts at local midnight.
        expect(events[1]!.at).toBe('2026-10-05');
        expect(eventTime('2026-10-05')).toBe(new Date(2026, 9, 5).getTime());
    });

    it('words an expiry push by its delta', () => {
        const [pushed] = buildLifecycleTimeline(detail({
            expiry_events: [{
                occurred_at: '2026-10-01T09:00:00Z',
                kind: 'pushed',
                previous_expiry_date: '2026-10-02',
                new_expiry_date: '2026-10-09',
                delta_days: 7,
            }],
        }));
        expect(pushed!.title).toBe('Pushed expiry +7 days');
        expect(pushed!.color).toBe('lifecycle-expiry-changed');
    });
});
