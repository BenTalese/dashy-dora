import { describe, expect, it } from 'vitest';

import { buildCalendarCells } from 'src/helpers/dashboardCalendar';
import type { Upcoming } from 'src/models/alert';

const format = {
    relativeDay: (iso: string) => `day ${iso}`,
    weekdayShort: (day: Date) => ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'][day.getDay()]!,
};

function upcoming(over: Partial<Upcoming> = {}): Upcoming {
    return { start: '2026-10-26', end: '2026-11-08', days: 14, dates: [], ...over };
}

describe('buildCalendarCells', () => {
    it('starts on the household today and runs the fortnight', () => {
        const cells = buildCalendarCells(upcoming(), 14, format);
        expect(cells).toHaveLength(14);
        expect(cells[0]).toMatchObject({ iso: '2026-10-26', dayNum: 26, dow: 'Mo', isToday: true });
        expect(cells[6]!.iso).toBe('2026-11-01');
        expect(cells.filter((c) => c.isToday)).toHaveLength(1);
    });

    it('marks what is on each day, in words for screen readers', () => {
        const cells = buildCalendarCells(upcoming({
            dates: [{
                date: '2026-10-27',
                meals: [{ recipe_id: 'r', recipe_name: 'Ragu', slot: 'Dinner' }],
                expiries: [{ stock_item_id: 's', name: 'Milk' }],
                shopping: [],
            }],
        }), 14, format);
        expect(cells[1]).toMatchObject({ hasMeal: true, hasExpiry: true, hasShopping: false });
        expect(cells[1]!.label).toBe('day 2026-10-27: meals, expiring items');
        expect(cells[2]!.label).toBe('day 2026-10-28: nothing on');
    });

    it('never renders more days than the server answered for', () => {
        expect(buildCalendarCells(upcoming({ days: 5 }), 14, format)).toHaveLength(5);
        expect(buildCalendarCells(null, 14, format)).toEqual([]);
    });
});
