/** Every sentence the app says about connectivity — the banner and the
 *  five toasts used to carry their own copies, and the 2026-08-23 "offline
 *  is read-only" correction (R-052) had to be applied in two files
 *  (finalisation 17-R11). Offline promises nothing about syncing: you can
 *  look, you can't change. */
export const OFFLINE_COPY = {
    /** Your own connection is down — yours to fix. */
    offline: "You're offline. You can look around, but not make changes.",
    /** The network is up but Dora isn't answering — Dora's problem. */
    unreachable: "Can't reach Dora. You can look around, but not make changes.",
    backOnline: 'Back online.',
    stillDown: "Still can't reach the server.",
    networkDetected: 'Network detected. Checking the server…',
} as const;
