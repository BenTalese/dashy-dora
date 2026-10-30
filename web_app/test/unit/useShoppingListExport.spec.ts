// @vitest-environment jsdom
/**
 * useShoppingListExport — print-view opener; the third of FU-682's three
 * `window.open(baseUrl…)` print views (finalisation 03 §C10 R-045). Same
 * contract as the meal-plan and recipe openers: fetched through the client.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

const m = vi.hoisted(() => ({ openHtmlDocumentAsync: vi.fn(() => Promise.resolve()) }));

vi.mock('src/services/files/printView', () => ({
    openHtmlDocumentAsync: m.openHtmlDocumentAsync,
    PopupBlockedError: class extends Error {},
}));
vi.mock('quasar', () => ({ Notify: { create: vi.fn() } }));

import { useShoppingListExport } from 'src/composables/useShoppingListExport';

describe('useShoppingListExport', () => {
    afterEach(() => vi.clearAllMocks());

    it('fetches the print view through the client, by API path', () => {
        useShoppingListExport().openPrintView('list-1');

        expect(m.openHtmlDocumentAsync).toHaveBeenCalledWith('/shopping-lists/list-1/print-view', 'Shopping list', undefined);
    });

    it('URL-encodes the list id', () => {
        useShoppingListExport().openPrintView('a b');

        expect(m.openHtmlDocumentAsync).toHaveBeenCalledWith('/shopping-lists/a%20b/print-view', 'Shopping list', undefined);
    });
});
