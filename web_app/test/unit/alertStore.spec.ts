// Store-layer coverage — alertStore, the thin server-truth cache behind the
// header bell badge, the alerts hub, and Dora's attention intent. The
// behavioural contracts worth pinning:
//   * counts are SERVER-derived (C-9.1 / R-003) — the badge must read
//     `actionable_count` verbatim, never recompute from `items`,
//   * every mutation is api-call-then-refresh so all surfaces agree,
//   * a failed mutation must NOT refresh (no half-applied view) and a failed
//     refresh must keep the previous data intact with flags reset.
//
// API service mocked at the module boundary; real store on fresh Pinia.
import { createPinia, setActivePinia } from 'pinia';
import type { Alert, Alerts } from 'src/models/alert';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useAlertStore } from 'src/stores/alertStore';

const m = vi.hoisted(() => ({
    getAlertsAsync: vi.fn(),
    snoozeAsync: vi.fn(),
    clearSuppressionAsync: vi.fn(),
    dismissAsync: vi.fn(),
    dismissAllAsync: vi.fn(),
}));

vi.mock('src/services/api/alertApiService', () => ({
    default: class {
        getAlertsAsync = m.getAlertsAsync;
        snoozeAsync = m.snoozeAsync;
        clearSuppressionAsync = m.clearSuppressionAsync;
        dismissAsync = m.dismissAsync;
        dismissAllAsync = m.dismissAllAsync;
    },
}));

function alert(id: string, overrides: Partial<Alert> = {}): Alert {
    return {
        alert_id: id,
        kind: 'essential_low',
        severity: 'medium',
        stock_item_id: 'SI-1',
        stock_item_name: 'Milk',
        target_id: null,
        message: 'Milk is low',
        detail: null,
        related_date: null,
        started_on: null,
        amount: null,
        snoozed_until: null,
        tier: 'actionable',
        ...overrides,
    };
}

function payload(overrides: Partial<Alerts> = {}): Alerts {
    return {
        items: [],
        snoozed: [],
        high_count: 0,
        medium_count: 0,
        low_count: 0,
        actionable_count: 0,
        snoozed_count: 0,
        ...overrides,
    };
}

beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    m.getAlertsAsync.mockResolvedValue(payload());
    for (const fn of [
        m.snoozeAsync, m.clearSuppressionAsync, m.dismissAsync,
        m.dismissAllAsync,
    ]) fn.mockResolvedValue(undefined);
});

describe('alertStore — server-derived badge state', () => {
    it('starts empty with zeroed counts before any fetch', () => {
        const store = useAlertStore();

        expect(store.badgeCount).toBe(0);
        expect(store.totalCount).toBe(0);
        expect(store.snoozedCount).toBe(0);
        expect(store.snoozedAlerts).toEqual([]);
    });

    it('badge reads actionable_count verbatim — never recomputed from items (R-003)', async () => {
        // Deliberately inconsistent payload: 1 item, server says 7 actionable.
        // The store must trust the server number, proving no client recompute.
        m.getAlertsAsync.mockResolvedValue(payload({
            items: [alert('A1')],
            actionable_count: 7,
            snoozed_count: 3,
        }));
        const store = useAlertStore();

        await store.refreshAsync();

        expect(store.badgeCount).toBe(7);
        expect(store.totalCount).toBe(1); // items.length — display count
        expect(store.snoozedCount).toBe(3); // server field, not snoozed.length
    });

    it('snoozedUntil looks the cutoff up in the server snoozed set', async () => {
        m.getAlertsAsync.mockResolvedValue(payload({
            snoozed: [alert('A2', { snoozed_until: '2026-07-18T00:00:00Z' })],
        }));
        const store = useAlertStore();
        await store.refreshAsync();

        expect(store.snoozedUntil('A2')).toBe('2026-07-18T00:00:00Z');
        expect(store.snoozedUntil('A-unknown')).toBeNull();
    });
});

describe('alertStore — refresh error handling', () => {
    it('keeps the previous payload and resets loading when a refresh fails', async () => {
        m.getAlertsAsync.mockResolvedValueOnce(payload({ actionable_count: 2 }));
        const store = useAlertStore();
        await store.refreshAsync();

        m.getAlertsAsync.mockRejectedValueOnce(new Error('offline'));
        await store.refreshAsync();

        expect(store.badgeCount).toBe(2); // stale-but-consistent beats blank
        expect(store.loadError).toContain('offline');
        expect(store.loading).toBe(false);
    });

    it('clears loadError on the next successful refresh', async () => {
        m.getAlertsAsync.mockRejectedValueOnce(new Error('offline'));
        const store = useAlertStore();
        await store.refreshAsync();
        expect(store.loadError).not.toBeNull();

        await store.refreshAsync();
        expect(store.loadError).toBeNull();
    });
});

describe('alertStore — mutation-then-refresh contract', () => {
    it('snoozeAlert defaults to 7 days and refetches the server truth', async () => {
        const store = useAlertStore();
        m.getAlertsAsync.mockResolvedValue(payload({ snoozed_count: 1 }));

        await store.snoozeAlert('A1');

        expect(m.snoozeAsync).toHaveBeenCalledWith('A1', 7);
        expect(m.getAlertsAsync).toHaveBeenCalledTimes(1);
        expect(store.snoozedCount).toBe(1);
    });

    it('passes a custom snooze duration through', async () => {
        const store = useAlertStore();

        await store.snoozeAlert('A1', 30);

        expect(m.snoozeAsync).toHaveBeenCalledWith('A1', 30);
    });

    it('each mutation hits its endpoint then refreshes (dismiss/unsnooze/dismiss-all)', async () => {
        const store = useAlertStore();

        await store.dismissAlert('A1');
        await store.unsnoozeAlert('A1');
        await store.dismissAllAsync();

        expect(m.dismissAsync).toHaveBeenCalledWith('A1');
        expect(m.clearSuppressionAsync).toHaveBeenCalledWith('A1');
        expect(m.dismissAllAsync).toHaveBeenCalledTimes(1);
        expect(m.getAlertsAsync).toHaveBeenCalledTimes(3); // one refresh per mutation
    });

    it('a failed mutation propagates, does NOT refresh, and leaves local state untouched', async () => {
        m.getAlertsAsync.mockResolvedValueOnce(payload({ actionable_count: 4 }));
        const store = useAlertStore();
        await store.refreshAsync();
        m.dismissAsync.mockRejectedValueOnce(new Error('409'));

        await expect(store.dismissAlert('A1')).rejects.toThrow('409');

        expect(m.getAlertsAsync).toHaveBeenCalledTimes(1); // only the seed fetch
        expect(store.badgeCount).toBe(4); // no optimistic drop to roll back
    });
});
