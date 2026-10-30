// The "you skipped the welcome wizard" stamp behind the dashboard's 24h
// "finish setting up" banner. Keyed per user: on a shared device the next
// person must not inherit someone else's banner (and its Continue, which
// restarts *their* onboarding). Storage may be disabled (private mode); every
// helper fails soft, which only means the banner doesn't show.

function keyFor(userId: string): string {
    return `dora.onboarding.skipped_at.${userId}`;
}

export function markOnboardingSkipped(userId: string | null | undefined): void {
    if (!userId) return;
    try {
        localStorage.setItem(keyFor(userId), new Date().toISOString());
    } catch {
        // Banner just won't fire.
    }
}

export function onboardingSkippedAt(userId: string | null | undefined): Date | null {
    if (!userId) return null;
    try {
        const raw = localStorage.getItem(keyFor(userId));
        if (!raw) return null;
        const stamped = new Date(raw);
        return Number.isFinite(stamped.getTime()) ? stamped : null;
    } catch {
        return null;
    }
}

export function clearOnboardingSkipped(userId: string | null | undefined): void {
    if (!userId) return;
    try {
        localStorage.removeItem(keyFor(userId));
    } catch {
        // Ignore.
    }
}
