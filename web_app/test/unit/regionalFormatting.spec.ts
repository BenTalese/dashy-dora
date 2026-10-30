/**
 * Regional formatting — the household's locale and timezone, not the device's
 * (D-006 / R-021 / R-079).
 *
 * Defects this pins (verified live under en-AU, en-US + New York and
 * de-DE + Berlin households):
 *   - the meal-plan calendar headed October "SEPTEMBER 2026" west of Greenwich,
 *     and its weekday letters were hard-coded English;
 *   - report percentages kept the English decimal point under de-DE;
 *   - "Today" / "Tomorrow" followed the device clock, so a device on a different
 *     calendar day from the household mislabelled every relative day.
 *
 * The suite runs pinned to `TZ=America/New_York` (vitest config), which is what
 * makes the month-label regression directly observable here.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

// No network: the locale probe never resolves, so the defaults stand until a
// test sets the policy by hand. Also keeps axios/Quasar out of a node run.
vi.mock('src/services/api/healthApiService', () => ({
    default: class {
        getInfoAsync() {
            return new Promise(() => undefined);
        }
    },
    invalidateHealthInfo: () => undefined,
}));

import {
    currentMoneyPolicy,
    formatFileSize,
    formatNumber,
    formatPercent,
    formatUnitPrice,
} from 'src/composables/useMoney';
import {
    formatDate,
    formatMonthYear,
    formatRelativeDay,
    weekdayLetters,
} from 'src/composables/useDateFormat';
import {
    daysFromToday,
    householdTimezone,
    localTodayIso,
    onHouseholdTimezoneChange,
    setHouseholdTimezone,
} from 'src/helpers/weekDates';

const NBSP = ' ';

function withLocale(locale: string, fn: () => void) {
    const policy = currentMoneyPolicy();
    const prior = policy.locale;
    policy.locale = locale;
    try {
        fn();
    } finally {
        policy.locale = prior;
    }
}

afterEach(() => setHouseholdTimezone(null));

describe('calendar month heading', () => {
    it('names the month the date is in, even west of Greenwich', () => {
        // Guard: the regression only shows in a negative-offset zone.
        expect(new Date(2026, 9, 1).getTimezoneOffset()).toBeGreaterThan(0);
        // The old code formatted `new Date(Date.UTC(2026, 9, 1))` — 20:00 on
        // 30 Sep in New York — and read "September 2026".
        expect(formatMonthYear('2026-10-01')).toBe('October 2026');
        expect(formatMonthYear('2026-01-01')).toBe('January 2026');
    });

    it('follows the household locale', () => {
        withLocale('de-DE', () => {
            expect(formatMonthYear('2026-10-01')).toBe('Oktober 2026');
        });
    });
});

describe('calendar weekday letters', () => {
    it('reads Monday-first in English', () => {
        expect(weekdayLetters().map((d) => d.letter).join(' ')).toBe('M T W T F S S');
    });

    it('reads Monday-first in German', () => {
        withLocale('de-DE', () => {
            expect(weekdayLetters().map((d) => d.letter).join(' ')).toBe('M D M D F S S');
        });
    });

    it('gives each letter a unique key (letters repeat)', () => {
        expect(new Set(weekdayLetters().map((d) => d.key)).size).toBe(7);
    });
});

describe('formatPercent — percentage points, household locale', () => {
    it('en-AU', () => {
        expect(formatPercent(139.5)).toBe('139.5%');
        expect(formatPercent(200.4, { signed: true })).toBe('+200.4%');
        expect(formatPercent(-12.5, { signed: true })).toBe('-12.5%');
        expect(formatPercent(0, { signed: true })).toBe('0%');
        expect(formatPercent(25)).toBe('25%');
    });

    it('de-DE uses the comma and the spaced sign', () => {
        withLocale('de-DE', () => {
            expect(formatPercent(139.5)).toBe(`139,5${NBSP}%`);
            expect(formatPercent(200.4, { signed: true })).toBe(`+200,4${NBSP}%`);
        });
    });

    it('owns its rounding and guards non-finite input (R-079)', () => {
        expect(formatPercent(33.333333333333336)).toBe('33.3%');
        expect(formatPercent(Number.NaN)).toBe('–');
        expect(formatPercent(null)).toBe('–');
    });
});

describe('formatNumber / formatFileSize / formatUnitPrice', () => {
    it('groups counts in the household locale', () => {
        expect(formatNumber(1208)).toBe('1,208');
        withLocale('de-DE', () => expect(formatNumber(1208)).toBe('1.208'));
    });

    it('keeps a pinned trailing digit for ratings', () => {
        expect(formatNumber(4, { digits: 1, minDigits: 1 })).toBe('4.0');
        withLocale('de-DE', () => expect(formatNumber(4.5, { digits: 1, minDigits: 1 })).toBe('4,5'));
    });

    it('formats file sizes', () => {
        expect(formatFileSize(512)).toBe('512 B');
        expect(formatFileSize(1536)).toBe('1.5 KB');
        withLocale('de-DE', () => expect(formatFileSize(1536)).toBe('1,5 KB'));
    });

    it('spaces a per-unit price the one way', () => {
        expect(formatUnitPrice(1.89, 'qt')).toBe('$1.89 / qt');
    });
});

describe('household timezone drives "today" (R-021)', () => {
    // 20:00 UTC on 30 Oct: 16:00 the same day in New York (the device), but
    // already 07:00 on 31 Oct in Sydney (the household).
    const now = new Date('2026-10-30T20:00:00Z');

    it('falls back to the device calendar when the zone is unknown', () => {
        expect(householdTimezone()).toBeNull();
        expect(localTodayIso(now)).toBe('2026-10-30');
        expect(daysFromToday('2026-10-31', now)).toBe(1);
        expect(formatRelativeDay('2026-10-31', now)).toBe('Tomorrow');
    });

    it("uses the household's calendar day once the zone is known", () => {
        setHouseholdTimezone('Australia/Sydney');
        expect(localTodayIso(now)).toBe('2026-10-31');
        expect(daysFromToday('2026-10-31', now)).toBe(0);
        expect(daysFromToday('2026-11-02', now)).toBe(2);
        expect(daysFromToday('2026-10-30', now)).toBe(-1);
        expect(formatRelativeDay('2026-10-31', now)).toBe('Today');
        expect(formatRelativeDay('2026-10-30', now)).toBe('Yesterday');
    });

    it('works the other way round too (household behind the device)', () => {
        setHouseholdTimezone('Pacific/Honolulu');
        // 04:00 UTC 31 Oct = 00:00 in New York on 31 Oct, 18:00 on 30 Oct in Honolulu.
        const late = new Date('2026-10-31T04:00:00Z');
        expect(localTodayIso(late)).toBe('2026-10-30');
        expect(daysFromToday('2026-10-31', late)).toBe(1);
    });

    it('ignores an unrecognised zone rather than throwing', () => {
        setHouseholdTimezone('Mars/Olympus_Mons');
        expect(householdTimezone()).toBeNull();
        expect(localTodayIso(now)).toBe('2026-10-30');
    });

    it("treats the server-default 'UTC' as not configured (device clock)", () => {
        // `AppSetting.timezone` defaults to 'UTC' and /health always sends it,
        // so an install that never chose a zone must keep the device clock.
        setHouseholdTimezone('UTC');
        expect(householdTimezone()).toBeNull();
        expect(localTodayIso(now)).toBe('2026-10-30');
        expect(formatRelativeDay('2026-10-31', now)).toBe('Tomorrow');
        // 20:00 UTC = 16:00 on the New York device clock, not 20:00.
        expect(formatDate('2026-10-30T20:00:00Z', { hour: 'numeric', hour12: false })).toBe('16');
        setHouseholdTimezone('Etc/UTC');
        expect(householdTimezone()).toBeNull();
    });

    it('drops back to the device clock when a set zone is reset to UTC', () => {
        setHouseholdTimezone('Australia/Sydney');
        expect(householdTimezone()).toBe('Australia/Sydney');
        setHouseholdTimezone('UTC');
        expect(householdTimezone()).toBeNull();
        expect(localTodayIso(now)).toBe('2026-10-30');
    });

    it('notifies subscribers only when the zone actually changes', () => {
        const seen: (string | null)[] = [];
        const off = onHouseholdTimezoneChange(() => seen.push(householdTimezone()));
        try {
            setHouseholdTimezone('Australia/Sydney');
            setHouseholdTimezone('Australia/Sydney');
            setHouseholdTimezone('UTC');
            setHouseholdTimezone(null);
        } finally {
            off();
        }
        expect(seen).toEqual(['Australia/Sydney', null]);
    });

    it('renders instants on the household clock, calendar days untouched', () => {
        setHouseholdTimezone('Australia/Sydney');
        expect(formatDate('2026-10-30T20:00:00Z', { day: 'numeric' })).toBe('31');
        // A bare date names a day; it must not be re-zoned.
        expect(formatDate('2026-10-30', { day: 'numeric' })).toBe('30');
    });
});
