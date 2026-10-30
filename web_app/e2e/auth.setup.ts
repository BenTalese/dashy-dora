import { test as setup, expect } from './fixtures';

// Logs in once as the seeded admin (dora/dora) and saves the session so the
// smoke specs start authenticated. Playwright's recommended auth pattern.
const AUTH_FILE = 'e2e/.auth/user.json';

setup('authenticate as the seeded admin', async ({ page }) => {
    await page.goto('/');

    // The app redirects an unauthenticated visitor to the login page.
    await page.locator('input[autocomplete="username"]').fill('dora');
    await page.locator('input[autocomplete="current-password"]').fill('dora');
    await page.getByRole('button', { name: 'Sign In' }).click();

    // Landed on the dashboard (login form gone, at the app root).
    await expect(page).toHaveURL(/#\/$/);
    await expect(page.locator('input[autocomplete="current-password"]')).toHaveCount(0);

    await page.context().storageState({ path: AUTH_FILE });
});
