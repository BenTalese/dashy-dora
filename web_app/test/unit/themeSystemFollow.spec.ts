// @vitest-environment jsdom
/**
 * FU-632 (2) / FU-578 #7b — a "System" theme follows the OS while the app is
 * open. The listener used to act only on the legacy bare `system` key, so the
 * `system-<family>` keys the picker actually stores never flipped until a
 * reload.
 */
import { describe, expect, it } from 'vitest';
import ThemeService from 'src/services/themeService';

function fakeMatchMedia() {
    let dark = false;
    const listeners: ((e: { matches: boolean }) => void)[] = [];
    window.matchMedia = ((query: string) => ({
        get matches() { return query.includes('dark') ? dark : false; },
        media: query,
        addEventListener: (_: string, fn: (e: { matches: boolean }) => void) => { listeners.push(fn); },
        removeEventListener: (_: string, fn: (e: { matches: boolean }) => void) => {
            const i = listeners.indexOf(fn);
            if (i >= 0) listeners.splice(i, 1);
        },
    })) as unknown as typeof window.matchMedia;
    return {
        setDark(value: boolean) {
            dark = value;
            [...listeners].forEach((fn) => fn({ matches: value }));
        },
    };
}

describe('a System theme follows the OS live', () => {
    it('flips a family system theme when the OS scheme changes', () => {
        const os = fakeMatchMedia();
        new ThemeService().applyForUser('system-blueberry', 'default', 'md');
        expect(document.documentElement.getAttribute('data-theme')).toBe('blueberry');

        os.setDark(true);
        expect(document.documentElement.getAttribute('data-theme')).toBe('blueberry-dark');

        os.setDark(false);
        expect(document.documentElement.getAttribute('data-theme')).toBe('blueberry');
    });

    it('leaves a fixed theme alone when the OS changes', () => {
        const os = fakeMatchMedia();
        new ThemeService().applyForUser('cherry-cola', 'default', 'md');
        os.setDark(true);
        expect(document.documentElement.getAttribute('data-theme')).toBe('cherry-cola');
    });
});
