import { Notify } from 'quasar';
import { openHtmlDocumentAsync, PopupBlockedError } from 'src/services/files/printView';
import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';

/** FU-682 / R-045 — mirrors `useRecipeExport.openPrintView`: the document is
 *  fetched through the authenticated client and handed to a tab claimed on
 *  the gesture (R-046), so this must stay a sync entry point. A raw
 *  `window.open(baseUrl + …)` only worked where the browser volunteered the
 *  session cookie — never in the Capacitor shell or a cross-site deploy. */
export function openPrintDocument(path: string, title: string, body?: unknown): void {
    void openHtmlDocumentAsync(path, title, body).catch((err) => {
        Notify.create(err instanceof PopupBlockedError
            ? {
                type: 'negative',
                message: 'Your browser blocked the print tab. Allow pop-ups for Dora and try again.',
            }
            : {
                type: 'negative',
                message: "Couldn't open the print view.",
                caption: toastCaption(err),
            });
    });
}
