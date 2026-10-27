import { computed, ref } from 'vue';

/**
 * FU-824 — a reactive read of the *live* theme's CSS custom properties.
 *
 * ## The bug this exists to fix
 *
 * Some surfaces can't express a colour in CSS — an SVG `stroke`, a canvas
 * series, a chart palette — so they read the token off the document with
 * `getComputedStyle(document.documentElement).getPropertyValue('--x')`. That
 * read is correct, and it is **not reactive**: `getComputedStyle` is a plain DOM
 * call, so a `computed()` wrapping it registers no dependency on the theme and
 * never re-evaluates when the theme changes. The value is sampled once and
 * frozen.
 *
 * Three surfaces had independently hit this, and two of them shipped a comment
 * claiming behaviour they did not have:
 *
 *  - `DashboardPage.vue`'s stock donut — *"Read the semantic-* tokens off the
 *    document so the donut recolours when the user switches theme without a full
 *    reload."* It does not; the computed's only dependencies are the summary and
 *    two route links.
 *  - `ReportsPage.vue`'s `chartPalette` — someone recognised the problem and
 *    added a `themeTick` ref to invalidate it, then never incremented it
 *    anywhere. Dead state advertising a fix.
 *  - `usePriceHistoryPalette.seriesColour` — the same one-shot read, no
 *    invalidation. That file is now gone: its `seriesColour` moved into this
 *    one (FU-833), so the ramp and the token read are no longer two hops.
 *
 * ## How this works
 *
 * `themeService.applyThemeKey()` is the single place that writes
 * `data-theme` on `<html>`, so it calls `notifyThemeChanged()` right after —
 * one explicit notification rather than a MutationObserver watching for it
 * (R-019: no magic). Reading a token through `paletteToken()` touches the
 * version ref first, so any `computed()` that calls it gains a dependency on the
 * theme and re-evaluates on the next switch.
 *
 * R-003: this is the one place the app converts "a token name" into "the colour
 * it currently resolves to". Don't add a fourth private copy.
 */

/** Bumped on every theme application. Exported read-only via the composable. */
const themeVersion = ref(0);

/**
 * Tell the palette layer the theme changed. Called by
 * `themeService.applyThemeKey` immediately after `data-theme` is written and
 * Quasar's palette is resynced — at which point the new custom properties are
 * live and a read returns the new values.
 */
export function notifyThemeChanged(): void {
    themeVersion.value += 1;
}

/**
 * Resolve a CSS custom property against the live theme.
 *
 * Call this **inside** a `computed()` (or a render function) so the version
 * dependency is registered — that is what makes the result recolour on a theme
 * switch. Outside a reactive scope it still returns the right value, it just
 * won't invalidate.
 *
 * `fallback` covers SSR/no-document and a genuinely absent token. Per R-060 a
 * token you reference should exist, so a fallback here is a safety net, not a
 * licence to invent token names.
 */
export function paletteToken(name: string, fallback = ''): string {
    // Register the dependency BEFORE the DOM read, so the read is what gets
    // re-run when the theme changes.
    void themeVersion.value;
    if (typeof document === 'undefined' || typeof window === 'undefined') {
        return fallback;
    }
    const value = window
        .getComputedStyle(document.documentElement)
        .getPropertyValue(name)
        .trim();
    return value || fallback;
}

/** Resolve several tokens at once — the common case for a chart series or a
 *  multi-segment SVG. Same reactivity rules as `paletteToken`. */
export function paletteTokens(names: string[], fallbacks: string[] = []): string[] {
    return names.map((name, i) => paletteToken(name, fallbacks[i] ?? ''));
}

/**
 * The categorical chart ramp, as the app's six `--chart-N` tokens.
 *
 * Folded in from `usePriceHistoryPalette.ts` (**FU-833** step 5), which was a
 * six-line wrapper over `paletteToken` living beside the price chart. It lives
 * here because this file is already the one place that turns a token name into
 * the colour it currently resolves to (R-003), and because the ramp has three
 * consumers now — the price chart's series, the picker chips that must match
 * them, and Reports' categorical buckets.
 *
 * The hex fallbacks mirror the Pesto defaults so a pre-paint call still returns
 * a sensible colour rather than an empty string.
 */
const CHART_RAMP_FALLBACKS: readonly string[] = [
    'hsl(150, 76%, 39%)',  // --chart-1 (primary)
    'hsl(189, 100%, 32%)', // --chart-2 (secondary)
    'hsl(50, 95%, 50%)',   // --chart-3 (accent)
    'hsl(20, 85%, 60%)',   // --chart-4 (warm tertiary)
    'hsl(280, 50%, 58%)',  // --chart-5 (cool tertiary)
    'hsl(220, 45%, 55%)',  // --chart-6 (cool quaternary)
];

/**
 * Colour for the *n*th series, by position. Stable for as long as the selection
 * is, so a chip in a picker, the polyline it selected and the swatch in a
 * comparison card all agree. Wraps past the end of the ramp.
 *
 * Call it inside a `computed()` or a render function — same reactivity rule as
 * `paletteToken`, for the same reason.
 */
export function seriesColour(index: number): string {
    const slot = ((index % CHART_RAMP_FALLBACKS.length) + CHART_RAMP_FALLBACKS.length)
        % CHART_RAMP_FALLBACKS.length;
    return paletteToken(`--chart-${slot + 1}`, CHART_RAMP_FALLBACKS[slot]);
}

/**
 * Colour for a named category (a spend group, a waste reason): the key hashes
 * onto the same ramp `seriesColour` walks, so one key keeps its hue between
 * renders and across cards. Six slots, so distinct keys can collide (FU-843).
 */
export function categoricalColour(key: string): string {
    let hash = 0;
    for (let i = 0; i < key.length; i++) hash = (hash * 31 + key.charCodeAt(i)) | 0;
    return seriesColour(Math.abs(hash));
}

export function useThemePalette() {
    return {
        /** Increments on each theme application. Depend on this directly if you
         *  need to invalidate something `paletteToken` doesn't cover. */
        themeVersion: computed(() => themeVersion.value),
        paletteToken,
        paletteTokens,
        seriesColour,
        categoricalColour,
    };
}
