// FU-520 workstream 1 — unit coverage for the shared relative-time formatter.
//
// `relativeTime` is the one "Nm ago / Nh ago / …" implementation shared by
// stock-item detail, the observation list, and YourPricesWidget. The unit
// boundaries (60m → 1h, 24h → 1d, 7d → 1w, 5w → months, 12mo → years) are the
// contract — pin them with a frozen clock so a boundary tweak is loud.
//
// DETERMINISM: the system clock is pinned via vi.setSystemTime; every input
// is expressed as an offset from that instant, so no wall-clock dependence.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { relativeTime } from 'src/helpers/relativeTime';

const NOW = new Date('2026-07-10T12:00:00.000Z');

/** ISO timestamp `minutes` before the pinned clock. */
function minutesAgo(minutes: number): string {
    return new Date(NOW.getTime() - minutes * 60_000).toISOString();
}
function daysAgo(days: number): string {
    return minutesAgo(days * 24 * 60);
}

describe('relativeTime — shared "N ago" formatter', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        vi.setSystemTime(NOW);
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('renders "just now" under a minute', () => {
        expect(relativeTime(minutesAgo(0))).toBe('just now');
        expect(relativeTime(NOW.toISOString())).toBe('just now');
    });

    it('renders whole minutes up to an hour', () => {
        expect(relativeTime(minutesAgo(1))).toBe('1m ago');
        expect(relativeTime(minutesAgo(59))).toBe('59m ago');
    });

    it('flips to hours at 60 minutes', () => {
        expect(relativeTime(minutesAgo(60))).toBe('1h ago');
        expect(relativeTime(minutesAgo(23 * 60 + 59))).toBe('23h ago');
    });

    it('flips to days at 24 hours', () => {
        expect(relativeTime(minutesAgo(24 * 60))).toBe('1d ago');
        expect(relativeTime(daysAgo(6))).toBe('6d ago');
    });

    it('flips to weeks at 7 days', () => {
        expect(relativeTime(daysAgo(7))).toBe('1w ago');
        expect(relativeTime(daysAgo(34))).toBe('4w ago');
    });

    it('flips to months at 5 weeks (30-day months)', () => {
        expect(relativeTime(daysAgo(35))).toBe('1mo ago');
        expect(relativeTime(daysAgo(359))).toBe('11mo ago');
    });

    it('renders years for old timestamps', () => {
        expect(relativeTime(daysAgo(365))).toBe('1y ago');
        expect(relativeTime(daysAgo(365 * 2 + 10))).toBe('2y ago');
    });

    it('renders an empty string for an empty input', () => {
        expect(relativeTime('')).toBe('');
    });

    it('truncates partial units (floors, never rounds up)', () => {
        // 1h 59m is still "1h ago" — the UI promises "at least N".
        expect(relativeTime(minutesAgo(119))).toBe('1h ago');
        // 13 days is "1w ago", not 2.
        expect(relativeTime(daysAgo(13))).toBe('1w ago');
    });
});

describe('relativeTime coarse style', () => {
    it('reads in whole days, as prose', () => {
        const ago = (days: number) => new Date(Date.now() - days * 86_400_000 - 1000).toISOString();
        expect(relativeTime(ago(0), { style: 'coarse' })).toBe('today');
        expect(relativeTime(ago(1), { style: 'coarse' })).toBe('yesterday');
        expect(relativeTime(ago(3), { style: 'coarse' })).toBe('3 days ago');
        expect(relativeTime(ago(9), { style: 'coarse' })).toBe('last week');
        expect(relativeTime(ago(21), { style: 'coarse' })).toBe('3 weeks ago');
    });
});
