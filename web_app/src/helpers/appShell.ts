/**
 * R-036 / ADR-032 — the fixed-height app-shell contract for a `<q-page>`'s
 * `:style-fn`. QPage hands over the layout's live chrome `offset` (header, plus
 * the OfflineBanner when it shows) and the viewport `height`, so the page fills
 * exactly the area below the header without a hardcoded pixel guess. `height`
 * is 0 only before Quasar's first screen measure; calc() covers that paint.
 */
export function appShellStyleFn(offset: number, height: number): { height: string } {
    return {
        height: height === 0 ? `calc(100vh - ${offset}px)` : `${height - offset}px`,
    };
}
