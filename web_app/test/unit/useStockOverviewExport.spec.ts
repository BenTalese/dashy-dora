// @vitest-environment jsdom
/**
 * Large-selection exports travel as a JSON body, not a query string.
 *
 * ~39 bytes per uuid in `ids=` runs past gunicorn's 8190-byte request line at
 * ~200 items, so a big Stock Overview filter got a 400/414 ("Couldn't
 * export…", a dead print tab). Pins the routing: a selection POSTs, no
 * selection keeps the plain GET, and the print tab is still claimed inside
 * the click (R-046) before the fetch.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MockInstance } from 'vitest';

const m = vi.hoisted(() => ({
    get: vi.fn(),
    post: vi.fn(() => Promise.resolve('<html>sheet</html>')),
    getFile: vi.fn(() => Promise.resolve({ blob: new Blob(['x']), filename: 'all.csv' })),
    postFile: vi.fn(() => Promise.resolve({ blob: new Blob(['x']), filename: 'picked.csv' })),
    getBlob: vi.fn(),
    openHtmlDocumentAsync: vi.fn(() => Promise.resolve()),
    triggerSave: vi.fn(),
    notify: vi.fn(),
}));

vi.mock('src/services/api/axiosHttpClient', () => ({
    default: class {
        get = m.get;
        post = m.post;
        getFile = m.getFile;
        postFile = m.postFile;
        getBlob = m.getBlob;
    },
    NormalisedApiError: class extends Error {},
}));
vi.mock('src/services/files/printView', () => ({
    openHtmlDocumentAsync: m.openHtmlDocumentAsync,
    objectUrlFor: () => 'blob:doc',
    PopupBlockedError: class PopupBlockedError extends Error {},
}));
vi.mock('src/services/files/downloadHelpers', () => ({ triggerSave: m.triggerSave }));
vi.mock('src/services/errorHandling/apiErrorHandler', () => ({ toastCaption: () => '' }));
vi.mock('quasar', () => ({ Notify: { create: m.notify } }));

import { useStockOverviewExport } from 'src/composables/useStockOverviewExport';
import { openQrSheetAsync } from 'src/composables/useQrLabels';

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe('stock overview + QR sheet — selection travels in the body', () => {
    let target: { opener: unknown; document: { write: () => void; close: () => void }; location: { replace: ReturnType<typeof vi.fn> }; close: ReturnType<typeof vi.fn> };
    let openSpy: MockInstance<typeof window.open>;

    beforeEach(() => {
        target = {
            opener: {},
            document: { write: vi.fn(), close: vi.fn() },
            location: { replace: vi.fn() },
            close: vi.fn(),
        };
        openSpy = vi.spyOn(window, 'open').mockReturnValue(target as unknown as Window);
    });
    afterEach(() => {
        vi.clearAllMocks();
        openSpy.mockRestore();
    });

    it('POSTs the CSV export when a selection is given', async () => {
        await useStockOverviewExport().downloadCsv(['a', 'b']);

        expect(m.postFile).toHaveBeenCalledWith('/stock-items/export?format=csv', { ids: ['a', 'b'] }, { retryAsRead: true });
        expect(m.getFile).not.toHaveBeenCalled();
        expect(m.triggerSave).toHaveBeenCalledWith(expect.any(Blob), 'picked.csv');
    });

    it('keeps the plain GET for an unfiltered CSV export', async () => {
        await useStockOverviewExport().downloadCsv();

        expect(m.getFile).toHaveBeenCalledWith('/stock-items/export?format=csv');
        expect(m.postFile).not.toHaveBeenCalled();
    });

    it('POSTs an empty selection rather than exporting everything', async () => {
        await useStockOverviewExport().downloadCsv([]);

        expect(m.postFile).toHaveBeenCalledWith('/stock-items/export?format=csv', { ids: [] }, { retryAsRead: true });
    });

    it('hands a selection to the shared print helper as a body', () => {
        useStockOverviewExport().openPrintView(['a']);

        expect(m.openHtmlDocumentAsync).toHaveBeenCalledWith('/stock-items/print-view', 'Stock', { ids: ['a'] });
    });

    it('keeps the GET print view when nothing is filtered', () => {
        useStockOverviewExport().openPrintView();

        expect(m.openHtmlDocumentAsync).toHaveBeenCalledWith('/stock-items/print-view', 'Stock', undefined);
        expect(m.post).not.toHaveBeenCalled();
    });

    it('hands a QR sheet selection and its layout to the shared helper as a body', async () => {
        await openQrSheetAsync({ ids: ['x', 'y'], layout: 'a4-21up' });

        expect(m.openHtmlDocumentAsync).toHaveBeenCalledWith(
            '/stock-items/qr/sheet', 'QR sheet', { ids: ['x', 'y'], layout: 'a4-21up' },
        );
    });

    it('keeps the GET "print all" QR sheet', async () => {
        await openQrSheetAsync({ layout: 'a4-21up' });

        expect(m.openHtmlDocumentAsync).toHaveBeenCalledWith('/stock-items/qr/sheet?layout=a4-21up', 'QR sheet');
        expect(m.post).not.toHaveBeenCalled();
    });
});
