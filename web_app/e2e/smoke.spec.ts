import { test, expect } from './fixtures';
import { type Page } from '@playwright/test';

// FU-540 — authenticated navigation smoke. Uses the saved admin session
// (see auth.setup.ts). Each key route must: load its lazily-imported page
// chunk, render the app shell, stay authenticated, and NOT throw or hit the
// render error boundary. This is the integration layer unit/component tests
// can't reach — real routing, cookie auth, and the SPA↔API handshake.

// Fails the test on any uncaught page error (a real render/JS crash — the
// kind the ErrorBoundary would otherwise swallow into a friendly screen).
function guardPageErrors(page: Page): string[] {
    const errors: string[] = [];
    page.on('pageerror', (err) => errors.push(err.message));
    return errors;
}

// The router runs in HASH mode (quasar.config vueRouterMode) — a plain
// path like `/stock` just serves index.html and the router falls back to
// the dashboard, silently testing `/` five times. Routes must be `/#/...`.
const ROUTES: { path: string; name: string }[] = [
    { path: '/#/', name: 'Dashboard' },
    { path: '/#/stock', name: 'Stock' },
    { path: '/#/cookbook', name: 'Cookbook' },
    { path: '/#/meal-plans', name: 'Meal plans' },
    { path: '/#/shopping-lists', name: 'Shopping lists' },
];

for (const route of ROUTES) {
    test(`${route.name} loads, renders the shell, stays authenticated`, async ({ page }) => {
        const errors = guardPageErrors(page);

        await page.goto(route.path);
        await page.waitForLoadState('networkidle');

        // The route actually mounted (its meta.title landed) — guards against
        // the hash-mode fallback quietly rendering the dashboard instead.
        await expect(page).toHaveTitle(new RegExp(route.name, 'i'));
        // Authenticated — not bounced back to the login form.
        await expect(page.locator('input[autocomplete="current-password"]')).toHaveCount(0);
        // The Quasar app shell rendered (not a blank page / white-screen crash).
        await expect(page.locator('.q-layout').first()).toBeVisible();
        // The render error boundary did NOT catch a crash on this page.
        await expect(page.getByText(/something went wrong/i)).toHaveCount(0);

        expect(errors, `uncaught page errors on ${route.path}`).toEqual([]);
    });
}

test('the dashboard actually talks to the API (real handshake)', async ({ page }) => {
    // Prove the built SPA reaches the backend over the shared origin with a
    // live session. Any /api 2xx isn't enough — the public capabilities probe
    // answers 200 on the login page too — so wait for the session read itself
    // (`GET /api/auth/me` only 200s for an authenticated cookie).
    const meOk = page.waitForResponse(
        (r) => new URL(r.url()).pathname === '/api/auth/me'
            && r.request().method() === 'GET'
            && r.status() === 200,
        { timeout: 15_000 },
    );
    await page.goto('/#/');
    await meOk;
    // And the handshake landed on the app, not the login form.
    await expect(page.locator('input[autocomplete="current-password"]')).toHaveCount(0);
    await expect(page.locator('.q-layout').first()).toBeVisible();
});
