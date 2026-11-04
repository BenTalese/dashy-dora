// @vitest-environment jsdom
// (jsdom: `useDateFormat` imports `useMoney` → `axiosHttpClient` → Quasar,
// which needs `window` at import time — same reason as relativeDay.spec.)
/**
 * FU-970 — the dashboard greeting reads the household's wall clock, not the
 * device's. Walk A had a Pago Pago household on a Sydney device: the strip said
 * Thursday and the greeting said "Friday!".
 */
import { afterEach, describe, expect, it } from 'vitest';
import { setHouseholdTimezone } from 'src/helpers/weekDates';
import { householdHour, householdTodayDate } from 'src/composables/useDateFormat';

// 10:00 Friday in Sydney (UTC+11) is 12:00 Thursday in Pago Pago (UTC-11).
const NOW = new Date('2026-10-29T23:00:00Z');

describe('household clock', () => {
    afterEach(() => setHouseholdTimezone(null));

    it("names the household's weekday, not the device's", () => {
        setHouseholdTimezone('Pacific/Pago_Pago');
        expect(householdTodayDate(NOW).getDay()).toBe(4); // Thursday
        setHouseholdTimezone('Australia/Sydney');
        expect(householdTodayDate(NOW).getDay()).toBe(5); // Friday
    });

    it("reads the hour off the household's zone", () => {
        setHouseholdTimezone('Pacific/Pago_Pago');
        expect(householdHour(NOW)).toBe(12);
        setHouseholdTimezone('Australia/Sydney');
        expect(householdHour(NOW)).toBe(10);
    });

    it('falls back to the device clock while the zone is unknown', () => {
        expect(householdHour(NOW)).toBe(NOW.getHours());
    });
});
