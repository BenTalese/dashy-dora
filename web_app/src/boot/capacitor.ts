// Capacitor boot.
//
// Runs before the router mounts so `loadBackendBaseUrl()` populates the
// in-module cache from `@capacitor/preferences` first. Any component that
// then reads `getBackendBaseUrl()` (axios interceptor, About screen) sees
// the persisted value synchronously.
//
// Safe on web too — `loadBackendBaseUrl()` reads localStorage as its
// non-native fallback, which is how a browser user's Settings override
// survives a reload.

import { boot } from 'quasar/wrappers';
import { loadBackendBaseUrl } from 'src/services/api/backendUrl';
import { isNativePlatform } from 'src/helpers/platform';

export default boot(async () => {
    await loadBackendBaseUrl();

    if (!isNativePlatform()) return;

    // Native-only status-bar + splash tidy. Loading these dynamically keeps
    // the web bundle free of the plugin JS.
    try {
        const { StatusBar, Style } = await import('@capacitor/status-bar');
        await StatusBar.setStyle({ style: Style.Default });
    } catch {
        // Plugin absent on this platform — harmless.
    }
    try {
        const { SplashScreen } = await import('@capacitor/splash-screen');
        await SplashScreen.hide();
    } catch {
        // Splash-screen plugin absent — harmless.
    }
});
