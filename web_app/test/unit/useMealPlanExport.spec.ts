// @vitest-environment jsdom
/**
 * useMealPlanExport — print-view opener. FU-682 / finalisation 02-R36: the
 * document is fetched through the authenticated client (`openHtmlDocumentAsync`)
 * rather than `window.open(baseUrl + …)`, which 401'd in the Capacitor shell
 * and on any cross-site deploy. The spec pins the API path and the encoding.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

const m = vi.hoisted(() => ({ openHtmlDocumentAsync: vi.fn(() => Promise.resolve()) }));

vi.mock('src/services/files/printView', () => ({
    openHtmlDocumentAsync: m.openHtmlDocumentAsync,
    PopupBlockedError: class extends Error {},
}));
vi.mock('quasar', () => ({ Notify: { create: vi.fn() } }));

import { useMealPlanExport } from 'src/composables/useMealPlanExport';

describe('useMealPlanExport', () => {
    afterEach(() => vi.clearAllMocks());

    it('fetches the print view through the client, by API path', () => {
        useMealPlanExport().openPrintView('plan-1');

        expect(m.openHtmlDocumentAsync).toHaveBeenCalledWith('/meal-plans/plan-1/print-view', 'Meal plan', undefined);
    });

    it('URL-encodes the plan id', () => {
        useMealPlanExport().openPrintView('a b/c?d');

        expect(m.openHtmlDocumentAsync).toHaveBeenCalledWith('/meal-plans/a%20b%2Fc%3Fd/print-view', 'Meal plan', undefined);
    });

    it('never builds a window.open URL from the API base', () => {
        const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
        useMealPlanExport().openPrintView('plan-2');
        expect(openSpy).not.toHaveBeenCalled();
        openSpy.mockRestore();
    });
});
