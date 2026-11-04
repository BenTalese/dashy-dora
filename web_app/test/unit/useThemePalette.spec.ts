// @vitest-environment jsdom
/**
 * FU-824 — theme-token reads must invalidate when the theme changes.
 *
 * Three surfaces independently reached for
 * `getComputedStyle(document.documentElement).getPropertyValue('--x')` because
 * they can't express a colour in CSS (an SVG stroke, a canvas chart series).
 * That read is correct and **not reactive**, so a `computed()` wrapping it
 * registers no dependency on the theme: the value is sampled once and frozen,
 * and a theme switch leaves the surface painted in the previous theme's
 * colours. Two of the three shipped a comment claiming otherwise, and Reports
 * had a `themeTick` ref that was read but never incremented.
 *
 * These tests pin the contract the fix depends on: a `computed()` calling
 * `paletteToken` re-evaluates after `notifyThemeChanged()`.
 */
import { beforeEach, describe, expect, it } from 'vitest';
import { computed } from 'vue';
import {
    categoricalColour,
    categoricalColours,
    notifyThemeChanged,
    paletteToken,
    paletteTokens,
    useThemePalette,
} from 'src/composables/useThemePalette';

/** Paint a token onto the document root, the way a `[data-theme]` block does. */
function setToken(name: string, value: string) {
    document.documentElement.style.setProperty(name, value);
}

describe('paletteToken', () => {
    beforeEach(() => {
        document.documentElement.style.cssText = '';
    });

    it('reads a custom property off the document root', () => {
        setToken('--semantic-positive', 'rgb(1, 2, 3)');
        expect(paletteToken('--semantic-positive')).toBe('rgb(1, 2, 3)');
    });

    it('returns the fallback when the token is absent', () => {
        expect(paletteToken('--not-a-token', '#abcdef')).toBe('#abcdef');
    });

    it('returns the fallback rather than an empty string for a blank value', () => {
        setToken('--blank', '   ');
        expect(paletteToken('--blank', '#fallback')).toBe('#fallback');
    });

    it('reads several tokens with per-token fallbacks', () => {
        setToken('--chart-1', 'red');
        expect(paletteTokens(['--chart-1', '--chart-2'], ['x', 'blue'])).toEqual([
            'red',
            'blue',
        ]);
    });
});

describe('reactivity — the whole point of the composable', () => {
    beforeEach(() => {
        document.documentElement.style.cssText = '';
    });

    it('a computed() over paletteToken re-evaluates after a theme change', () => {
        setToken('--semantic-negative', 'rgb(200, 90, 79)');
        let evaluations = 0;
        const colour = computed(() => {
            evaluations += 1;
            return paletteToken('--semantic-negative', '#fallback');
        });

        expect(colour.value).toBe('rgb(200, 90, 79)');
        expect(evaluations).toBe(1);

        // Re-reading without a theme change must NOT re-evaluate (the cache is
        // still valid — this is what makes the token read cheap).
        expect(colour.value).toBe('rgb(200, 90, 79)');
        expect(evaluations).toBe(1);

        // The theme switches: new token value, and the computed must pick it up.
        setToken('--semantic-negative', 'rgb(10, 20, 30)');
        // Before `notifyThemeChanged`, the stale value is still cached — this
        // asserts the dependency is on the notification, not on luck.
        expect(colour.value).toBe('rgb(200, 90, 79)');

        notifyThemeChanged();
        expect(colour.value).toBe('rgb(10, 20, 30)');
        expect(evaluations).toBe(2);
    });

    it('exposes a monotonic themeVersion for consumers that need it directly', () => {
        const { themeVersion } = useThemePalette();
        const before = themeVersion.value;
        notifyThemeChanged();
        notifyThemeChanged();
        expect(themeVersion.value).toBe(before + 2);
    });

    it('invalidates a multi-token computed too (the chart-series case)', () => {
        setToken('--chart-1', 'a');
        setToken('--chart-2', 'b');
        const series = computed(() => paletteTokens(['--chart-1', '--chart-2']));
        expect(series.value).toEqual(['a', 'b']);

        setToken('--chart-1', 'c');
        notifyThemeChanged();
        expect(series.value).toEqual(['c', 'b']);
    });
});

describe('categoricalColours — one chart, no shared hues (FU-976)', () => {
    beforeEach(() => {
        document.documentElement.style.cssText = '';
    });

    it('gives "Pantry staples" and "Fruit & Veg" different colours', () => {
        // They collide under the bare per-key hash; that is the walk-D bug.
        const colours = categoricalColours(['Pantry staples', 'Fruit & Veg']);
        expect(colours.get('Pantry staples')).not.toBe(colours.get('Fruit & Veg'));
    });

    it('never repeats a colour while the ramp has room', () => {
        const keys = ['Dairy', 'Meat', 'Pantry staples', 'Fruit & Veg', 'Frozen', 'Bakery'];
        const colours = categoricalColours(keys);
        expect(new Set(colours.values()).size).toBe(keys.length);
    });

    it('depends on the set, not the order the rows arrive in', () => {
        const a = categoricalColours(['Dairy', 'Pantry staples', 'Fruit & Veg']);
        const b = categoricalColours(['Fruit & Veg', 'Dairy', 'Pantry staples']);
        expect([...b.entries()].sort()).toEqual([...a.entries()].sort());
    });

    it('keeps a lone key on its own hashed hue', () => {
        expect(categoricalColours(['Dairy']).get('Dairy')).toBe(categoricalColour('Dairy'));
    });
});
