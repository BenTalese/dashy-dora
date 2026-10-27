/**
 * Recipe export: the print view (recipe card). The CSV download went with
 * the owner's "export to csv feels weird, remove feature here" (RECIPE
 * DETAIL feedback); its server route is an owner call (FU-933).
 */
import { Notify } from 'quasar';
import { openHtmlDocumentAsync, PopupBlockedError } from 'src/services/files/printView';
import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';

export function useRecipeExport() {
    /** Reported 2026-08-19 as "Print button 404s".
     *
     *  It was `window.open(`${baseUrl}/recipes/.../print-view`)` — the exact
     *  R-045 violation signal (a `window.open` built from `resolveBaseURL()`).
     *  That navigation is authenticated only if the browser volunteers the
     *  session cookie, which it does on a same-site dev box (the route returns
     *  200 there, which is why this survived) and declines once the SPA and API
     *  are on different sites — and can never do in the Capacitor shell, whose
     *  SPA origin is not the API origin. The server then answers 401/404 and
     *  the user gets a raw problem document in a new tab.
     *
     *  Same defect the QR sheet had (ADR-041/042); this sibling was never
     *  swept. Now fetched through the client and handed to the tab as a blob,
     *  with the tab claimed on the gesture (R-046) — so this **must** stay a
     *  sync entry point, no `await` before the call below.
     */
    function openPrintView(recipeId: string): void {
        void openHtmlDocumentAsync(
            `/recipes/${encodeURIComponent(recipeId)}/print-view`,
            'Recipe',
        ).catch((err) => {
            // A blocked pop-up is the user's to fix ("allow pop-ups"), not a
            // bug report — so it gets its own sentence and no error ref.
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

    return { openPrintView };
}

