/** Routes reachable without a session. Read by the router guard and by the
 *  auth store's expired-session handler (which can't import the router
 *  without a cycle) — one list (R-003; finalisation 15-R5). */
export const PUBLIC_ROUTES: ReadonlySet<string> = new Set<string>([
    '/login',
    // fresh-install first-admin setup. Reachable without a session by definition.
    '/setup',
    // native app first-run instance picker. Reachable before any backend is
    // configured (there is no backend to authenticate against until this
    // step completes).
    '/setup/backend',
    // A1 out-of-band auth surfaces — reachable from email links without an
    // existing session.
    '/verify-email',
    '/forgot-password',
    '/reset-password',
]);

/** The current hash-mode path, without the query string. */
export function currentHashPath(): string {
    if (typeof window === 'undefined') return '/';
    const raw = window.location.hash.replace(/^#/, '') || '/';
    return raw.split('?')[0] ?? '/';
}
