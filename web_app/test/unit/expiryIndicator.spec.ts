// @vitest-environment jsdom
// Expiry tone is a calendar-day comparison against the local date, so an item
// expiring today stays "soon" all day rather than flipping to "expired" once
// UTC midnight of its date has passed.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { expiryToneFor } from 'src/helpers/expiryIndicator';

describe('expiryToneFor', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        // Late local morning, built from local parts so the test holds in any zone.
        vi.setSystemTime(new Date(2026, 9, 29, 11, 30));
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('keeps an item expiring today as soon, not expired', () => {
        expect(expiryToneFor('2026-10-29')).toBe('soon');
    });

    it('marks yesterday as expired', () => {
        expect(expiryToneFor('2026-10-28')).toBe('expired');
    });

    it('treats up to 7 days out as soon and beyond as ok', () => {
        expect(expiryToneFor('2026-11-05')).toBe('soon');
        expect(expiryToneFor('2026-11-06')).toBe('ok');
    });

    it('returns none for missing or unparseable dates', () => {
        expect(expiryToneFor(null)).toBe('none');
        expect(expiryToneFor(undefined)).toBe('none');
        expect(expiryToneFor('')).toBe('none');
        expect(expiryToneFor('not a date')).toBe('none');
    });
});
