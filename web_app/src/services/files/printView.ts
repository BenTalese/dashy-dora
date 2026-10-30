// The one implementation of "open a server-rendered document in a new tab".
//
// It exists because the mechanic is two rules deep and both are easy to get
// wrong in ways that only show up somewhere you aren't:
//
//   R-045 — the document lives behind `/api/*`, so it must be fetched through
//   `AxiosHttpClient`, never handed to `window.open` as a URL. A bare
//   `window.open(apiUrl)` carries the session only if the browser volunteers
//   the cookie, which it declines cross-site and cannot do at all in the
//   Capacitor shell. It works perfectly on a dev box and 401/404s in a real
//   deployment.
//   R-046 — but fetching first is what breaks the open: a `window.open` that
//   can't be attributed to the click is blocked outright on mobile. So the tab
//   is opened synchronously, inside the caller's own call stack, and navigated
//   to the blob when the fetch lands.
//
// Extracted 2026-08-19 from `useQrLabels.openQrSheetAsync` when the recipe
// Print button turned out to be an un-swept R-045 violation of the same shape
// (reported as "Print button 404s"). Any future print view calls this.
import AxiosHttpClient from 'src/services/api/axiosHttpClient';

const http = new AxiosHttpClient();

/** Blob URLs are revoked on a timer rather than immediately: the consumer is
 *  a just-opened window / an <img> that hasn't decoded yet. A minute is long
 *  past both, and short enough that a print session doesn't leak the pages. */
const BLOB_TTL_MS = 60_000;

export function objectUrlFor(blob: Blob): string {
    const url = URL.createObjectURL(blob);
    setTimeout(() => URL.revokeObjectURL(url), BLOB_TTL_MS);
    return url;
}

/** Raised when the browser refused to open the print tab. Distinct from an
 *  API failure because the user's fix is different — allow pop-ups, don't
 *  report a bug — so the caller can say so. */
export class PopupBlockedError extends Error {
    constructor() {
        super('The browser blocked the print tab.');
        this.name = 'PopupBlockedError';
    }
}

/** Fetch an HTML document from `path` (an API path, no origin) and show it in
 *  a new tab. Must be called **synchronously from the click handler** — the
 *  first thing it does is claim the tab. With `body` the document is POSTed
 *  (a large selection's ids overflow the request line as a query string —
 *  gunicorn caps it at 8190 bytes, ~200 uuids); without it, GET.
 *
 *  Throws `PopupBlockedError` if the browser refused the tab, or whatever
 *  `AxiosHttpClient` throws if the fetch failed; the caller owns the wording,
 *  because "couldn't load your QR labels" and "couldn't print this recipe"
 *  are not the same sentence. */
export async function openHtmlDocumentAsync(
    path: string,
    placeholderTitle: string,
    body?: unknown,
): Promise<void> {
    // `noopener` is deliberately NOT passed: with it, `window.open` returns
    // null by spec and there'd be no handle to navigate. The opener reference
    // is severed by hand below instead, which gets the same protection — and
    // the destination is a blob: URL this app just built, not a third party.
    const target = window.open('', '_blank');
    if (!target) throw new PopupBlockedError();
    try {
        target.opener = null;
    } catch {
        // Cross-origin-ish edge; the blob we're about to load is ours anyway.
    }
    // Something to look at if the document is slow — a blank tab reads as broken.
    try {
        target.document.write(
            `<!doctype html><title>${placeholderTitle}</title><p>Preparing…`,
        );
        target.document.close();
    } catch {
        // Some shells disallow document.write into a fresh window; harmless.
    }

    try {
        const html = body === undefined
            ? await http.get<string>(path)
            // A print view only rides a POST because its selection would
            // overflow the request line; it is still a read, so it retries
            // like the GET path does.
            : await http.post<string>(path, body, { retryAsRead: true });
        const url = objectUrlFor(new Blob([html], { type: 'text/html' }));
        // `replace`, not `href`: the placeholder shouldn't sit in the tab's
        // history where Back would return the user to "Preparing…".
        target.location.replace(url);
    } catch (error) {
        // Don't strand the reader on the placeholder — close it and let the
        // caller report the failure where they're actually looking.
        try {
            target.close();
        } catch {
            // Already gone.
        }
        throw error;
    }
}
