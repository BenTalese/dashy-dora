// @vitest-environment jsdom
/**
 * The one "open a server document in a new tab" mechanic (R-045 / R-046):
 * the tab is claimed synchronously, the document is fetched through the
 * client (GET, or POST when a body is given — a large selection's ids
 * overflow the request line as a query string), and a failed fetch closes
 * the tab rather than stranding the reader on "Preparing…".
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MockInstance } from 'vitest';

const m = vi.hoisted(() => ({
    get: vi.fn(() => Promise.resolve('<html>get</html>')),
    post: vi.fn(() => Promise.resolve('<html>post</html>')),
}));
vi.mock('src/services/api/axiosHttpClient', () => ({
    default: class { get = m.get; post = m.post; },
}));

import { openHtmlDocumentAsync, PopupBlockedError } from 'src/services/files/printView';

describe('openHtmlDocumentAsync', () => {
    let target: { opener: unknown; document: { write: () => void; close: () => void }; location: { replace: ReturnType<typeof vi.fn> }; close: ReturnType<typeof vi.fn> };
    let openSpy: MockInstance<typeof window.open>;

    beforeEach(() => {
        target = { opener: {}, document: { write: vi.fn(), close: vi.fn() }, location: { replace: vi.fn() }, close: vi.fn() };
        openSpy = vi.spyOn(window, 'open').mockReturnValue(target as unknown as Window);
        vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:doc'), revokeObjectURL: vi.fn() });
        m.get.mockClear(); m.post.mockClear();
    });
    afterEach(() => { openSpy.mockRestore(); vi.unstubAllGlobals(); });

    it('claims the tab before fetching, then GETs without a body', async () => {
        const pending = openHtmlDocumentAsync('/x/print-view', 'X');
        expect(openSpy).toHaveBeenCalled();
        await pending;
        expect(m.get).toHaveBeenCalledWith('/x/print-view');
        expect(m.post).not.toHaveBeenCalled();
        expect(target.location.replace).toHaveBeenCalledWith('blob:doc');
    });

    it('POSTs when a body is given', async () => {
        await openHtmlDocumentAsync('/x/print-view', 'X', { ids: ['a'] });
        expect(m.post).toHaveBeenCalledWith('/x/print-view', { ids: ['a'] }, { retryAsRead: true });
        expect(m.get).not.toHaveBeenCalled();
        expect(target.location.replace).toHaveBeenCalledWith('blob:doc');
    });

    it('closes the tab and rethrows when the fetch fails', async () => {
        m.post.mockRejectedValueOnce(new Error('boom'));
        await expect(openHtmlDocumentAsync('/x', 'X', { ids: ['a'] })).rejects.toThrow('boom');
        expect(target.close).toHaveBeenCalled();
    });

    it('reports a blocked pop-up instead of fetching', async () => {
        openSpy.mockReturnValue(null);
        await expect(openHtmlDocumentAsync('/x', 'X', { ids: ['a'] })).rejects.toBeInstanceOf(PopupBlockedError);
        expect(m.post).not.toHaveBeenCalled();
    });
});
