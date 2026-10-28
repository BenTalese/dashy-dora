/**
 * Screenshots for the help guides, bundled from `src/assets/help/*.png`.
 *
 * A guide names its image by basename (`image: 'stock-rows'`); a name with no
 * file simply renders no figure, so content can be written before the shot is
 * taken and a retired shot never breaks a page. Shots are captured from the
 * seeded demo household at 1280px wide, 2× scale, light Pesto, and cropped to
 * the surface they explain (see the worklog, 2026-10-29).
 */
const FILES = import.meta.glob<string>('../assets/help/*.png', {
    eager: true,
    query: '?url',
    import: 'default',
});

export function helpImageUrl(name: string | undefined): string | null {
    if (!name) return null;
    return FILES[`../assets/help/${name}.png`] ?? null;
}

export function helpImageNames(): string[] {
    return Object.keys(FILES).map((k) => k.replace('../assets/help/', '').replace(/\.png$/, ''));
}
