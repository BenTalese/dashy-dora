import { Notify } from 'quasar';
import { boot } from 'quasar/wrappers';
import { clientLog } from 'src/composables/useClientLogger';

// Boot ordering: this runs before route navigation, so any boot-time
// errors after this module loads will land in the backend stream too.
export default boot(({ app }) => {
    app.config.errorHandler = (err, vm, info) => {
        const message = err instanceof Error ? err.message : String(err);
        console.error('Vue Error:', err, vm, info);
        Notify.create({ type: 'oopsie' });
        // Ship to /api/client-logs so the server-side log stream sees the
        // crash too. Rate-limited and best-effort — never raises.
        clientLog.error(message, {
            origin: 'vue',
            vueInfo: info,
            stack: err instanceof Error ? err.stack : undefined,
        });
    };
});

/** Browser notices that arrive through `window.onerror` but are not errors.
 *
 *  "ResizeObserver loop completed with undelivered notifications" is the
 *  browser telling itself it ran out of frame budget delivering resize
 *  callbacks; the spec expects it, it self-corrects on the next frame, and
 *  there is nothing for a user or a developer to act on. Chrome reports it
 *  through `window.onerror` anyway, so without this filter it took the full
 *  crash path: an "Oops, something went wrong" toast for nothing.
 *
 *  Found on My Products (2026-09-06), whose card grid reflows hard enough at a
 *  viewport change to reproduce it every time; it is not specific to that page.
 */
const BENIGN_BROWSER_NOTICES = [/ResizeObserver loop/i];

window.onerror = function (msg, url, line, col, error) {
    const text = typeof msg === 'string' ? msg : '';
    if (BENIGN_BROWSER_NOTICES.some((pattern) => pattern.test(text))) {
        // Deliberately silent: not a toast, and not shipped to
        // /api/client-logs either — logging a non-event as an error just moves
        // the noise somewhere it's harder to ignore.
        return;
    }
    console.error('Javascript Error:', msg, url, line, col, error);
    Notify.create({ type: 'oopsie' });
    clientLog.error(typeof msg === 'string' ? msg : 'window.onerror', {
        origin: 'window',
        url,
        line,
        col,
        stack: error instanceof Error ? error.stack : undefined,
    });
};

window.addEventListener('unhandledrejection', function (event) {
    Notify.create({ type: 'oopsie' });
    const reason = event.reason;
    const message =
        reason instanceof Error
            ? reason.message
            : typeof reason === 'string'
              ? reason
              : 'unhandled promise rejection';
    clientLog.error(message, {
        origin: 'promise',
        stack: reason instanceof Error ? reason.stack : undefined,
    });
});
