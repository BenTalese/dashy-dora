// Dora's own per-item QR labels — the single place the SPA talks to the
// `/stock-items/*/qr` endpoints.
//
// Why this exists: the QR image and the print sheet used to be reached by a
// bare `<img src="…/qr">` and `window.open("…/qr/sheet")`. Both bypass the
// axios client, so neither carried the session the rest of the app uses —
// they relied on the browser volunteering the `dora_session` cookie on an
// unauthenticated subresource / top-level navigation, which it will not do
// once the SPA and the API are on different sites (and cannot do at all in
// the Capacitor shell, where the SPA origin is not the API origin). The
// result on the detail page was an empty QR dialog and a dead "Print one".
//
// Fetching through `AxiosHttpClient` and handing the browser a blob URL keeps
// exactly one auth path in the app. The sheet's QR images are inlined by the
// server as data: URIs (see `barcodes.py`) so the blob page is self-contained.
import AxiosHttpClient, { NormalisedApiError } from 'src/services/api/axiosHttpClient';
// The new-tab mechanic (R-045 fetch-through-the-client + R-046 open-on-the-
// gesture) moved to `services/files/printView` on 2026-08-19 when the recipe
// Print button needed the same thing. Re-exported here so existing importers
// of `PopupBlockedError` don't have to care where it lives.
import {
    objectUrlFor,
    openHtmlDocumentAsync,
    PopupBlockedError,
} from 'src/services/files/printView';

export { PopupBlockedError };

const http = new AxiosHttpClient();

/** A short, quotable description of why a QR call failed.
 *
 *  The detail page used to swallow the error whole and render a flat
 *  "Couldn't load this item's QR code." That is exactly why FU-648 could be
 *  investigated twice without being explained: the one person who could see
 *  the failure had nothing to report but the sentence we wrote. The status and
 *  the correlation id are already on `NormalisedApiError` — surfacing them
 *  turns the next report into a one-line diagnosis. */
export function describeQrFailure(error: unknown): string {
    if (error instanceof PopupBlockedError) {
        return 'Your browser blocked the print tab. Allow pop-ups for Dora and try again.';
    }
    if (error instanceof NormalisedApiError) {
        if (error.isNetworkError) {
            return "Couldn't reach the server for this QR code. Check the connection and try again.";
        }
        const ref = error.correlationId ? ` · Ref: ${error.correlationId.slice(0, 8)}` : '';
        // FU-648 round 4: a bare "(error 404)" was still ambiguous, and 404 is
        // the status the owner keeps reporting. There are exactly two of them
        // and they mean opposite things, so say which one it was. The server
        // spells the difference out in the problem-detail `title`: a route miss
        // answers "Endpoint was not found." (middleware / SPA catch-all), an
        // item miss answers "Entity was not found." Both endpoints proven green
        // over real HTTP on 2026-08-21 — so a route miss here means the running
        // API doesn't carry `features/data/barcodes`, i.e. the server process is
        // older than this page.
        if (error.status === 404) {
            const detail = error.details as { title?: string } | null;
            const title = typeof detail?.title === 'string' ? detail.title : '';
            if (title.toLowerCase().startsWith('endpoint')) {
                return `This server has no QR endpoint at ${error.url} (404). Update the Dora server${ref}.`;
            }
            return `That stock item no longer exists on the server (404)${ref}.`;
        }
        return `Couldn't load this item's QR code (error ${error.status})${ref}.`;
    }
    return "Couldn't load this item's QR code.";
}

/** PNG of one item's `dora://` label QR, as an object URL for `<img :src>`. */
export async function fetchQrImageUrlAsync(
    stockItemId: string,
    size = 512,
): Promise<string> {
    const blob = await http.getBlob(
        `/stock-items/${encodeURIComponent(stockItemId)}/qr?size=${size}`,
    );
    return objectUrlFor(blob);
}

/** Open the printable label sheet in a new tab.
 *  Omit `ids` to print every stock item (the server's "print all" shortcut). */
export async function openQrSheetAsync(options: {
    ids?: string[];
    layout?: string;
} = {}): Promise<void> {
    // Must stay a sync entry point: both openers claim the tab in the caller's
    // own call stack (R-046), so awaiting anything before this line would
    // re-break "Print one" exactly the way FU-648 described.
    if (options.ids && options.ids.length > 0) {
        // A selection travels in the body — a few hundred ids in a query
        // string is past what gunicorn / nginx will accept on the request line.
        return openHtmlDocumentAsync(
            '/stock-items/qr/sheet',
            'QR sheet',
            { ids: options.ids, ...(options.layout ? { layout: options.layout } : {}) },
        );
    }
    const query = options.layout
        ? `?${new URLSearchParams({ layout: options.layout }).toString()}`
        : '';
    return openHtmlDocumentAsync(`/stock-items/qr/sheet${query}`, 'QR sheet');
}
