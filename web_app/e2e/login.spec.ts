import { test, expect } from './fixtures';

// FU-540 — the login flow itself, exercised fresh (no saved session). This is
// the one journey that can't rely on auth.setup's stored state, so it clears
// it and drives the real form → cookie → redirect handshake.
test.use({ storageState: { cookies: [], origins: [] } });

test('an unauthenticated visitor can log in and reach the dashboard', async ({ page }) => {
    await page.goto('/');

    // Bounced to the login form.
    const username = page.locator('input[autocomplete="username"]');
    await expect(username).toBeVisible();

    await username.fill('dora');
    await page.locator('input[autocomplete="current-password"]').fill('dora');
    await page.getByRole('button', { name: 'Sign In' }).click();

    // Redirected to the dashboard; the login form is gone.
    // Hash-mode router: the dashboard is `/#/` (a bare `/$` also matched
    // the server root before the router had moved anywhere).
    await expect(page).toHaveURL(/#\/$/);
    await expect(page.locator('input[autocomplete="current-password"]')).toHaveCount(0);
    await expect(page.locator('.q-layout').first()).toBeVisible();
});

test('bad credentials are rejected with a visible error', async ({ page }) => {
    await page.goto('/');
    await page.locator('input[autocomplete="username"]').fill('dora');
    await page.locator('input[autocomplete="current-password"]').fill('wrong-password');
    await page.getByRole('button', { name: 'Sign In' }).click();

    // Stays on login and surfaces the failure (copy from LoginPage.vue).
    await expect(page.getByText(/sign-in failed/i)).toBeVisible();
    await expect(page.locator('input[autocomplete="current-password"]')).toBeVisible();
});
