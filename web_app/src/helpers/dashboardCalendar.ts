/**
 * The dashboard's "What's coming" fortnight, built from `/alerts/upcoming`
 * (finalisation 08-R14). Pure: the page passes the two locale formatters, so
 * the grid is testable and the weekday names follow the household locale
 * (R-056; they were a hard-coded English list).
 */
import type { CalendarCell } from 'src/components/dashboard/WhatsComingCard.vue';
import type { Upcoming } from 'src/models/alert';
import { parseLocalIso, shiftDays } from 'src/helpers/weekDates';

export function buildCalendarCells(
    upcoming: Upcoming | null,
    maxDays: number,
    format: { relativeDay: (iso: string) => string; weekdayShort: (day: Date) => string },
): CalendarCell[] {
    if (!upcoming || !parseLocalIso(upcoming.start)) return [];
    const byDate = new Map(upcoming.dates.map((d) => [d.date, d]));
    // Never render more than the server sent: `days` is its word on how many it
    // answered with, and cells past it would read as "nothing on".
    const span = Math.min(maxDays, upcoming.days);
    const cells: CalendarCell[] = [];
    for (let i = 0; i < span; i++) {
        // `start` is the household's today (R-021), not the browser's.
        const iso = shiftDays(upcoming.start, i);
        const date = parseLocalIso(iso)!;
        const day = byDate.get(iso);
        const hasMeal = !!day && day.meals.length > 0;
        const hasExpiry = !!day && day.expiries.length > 0;
        const hasShopping = !!day && day.shopping.length > 0;
        const marks = [
            hasMeal ? 'meals' : null,
            hasExpiry ? 'expiring items' : null,
            hasShopping ? 'shopping' : null,
        ].filter(Boolean);
        cells.push({
            iso,
            dayNum: date.getDate(),
            dow: format.weekdayShort(date),
            label: `${format.relativeDay(iso)}${marks.length > 0 ? `: ${marks.join(', ')}` : ': nothing on'}`,
            isToday: i === 0,
            hasExpiry,
            hasShopping,
            hasMeal,
        });
    }
    return cells;
}
