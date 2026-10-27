import { Dark, setCssVar } from 'quasar';
import { readonly, ref, type Ref } from 'vue';
import type {
    FontFamilyPreference,
    FontSizePreference,
    ThemePreference,
} from 'src/models/auth';
import { notifyThemeChanged } from 'src/composables/useThemePalette';

/*
 * DS1 — Themed palettes.
 *
 * Two things happen on theme apply:
 *   1. `document.documentElement.setAttribute('data-theme', name)` —
 *      drives the semantic CSS tokens declared in css/themes.scss
 *      (`--brand-primary`, `--surface-page`, `--semantic-warning`, …).
 *   2. `syncQuasarPaletteFromCssVars()` — copies the now-active values
 *      into Quasar's own component palette (`--q-primary`, `--q-warning`, …)
 *      so q-btn / q-chip / q-banner honour the theme without per-call
 *      colour overrides.
 *
 * **Single source of truth = `css/themes.scss`.** (FU-004 collapse,
 * 2026-06-26.) Step (2) used to mirror the palette values in a TS
 * `palette: { primary: 'hsl(150, 60%, 36%)', … }` dict per theme — two
 * sources that had to match by hand. They do today, but the dict was a
 * latent drift hazard. The reads from `getComputedStyle` mean the SCSS
 * file is the only place a hue lives.
 *
 * Adding a new theme is now a 1-step change: append a `[data-theme="x"]`
 * block to themes.scss + a TS row to `THEMES` for its picker metadata
 * (label / blurb / swatch / isDark). No palette values in the TS row.
 * The fun-name catalogue is the source of truth for the Preferences
 * picker UI.
 */

/**
 * Compile-time contract for **Quasar palette key names** that the rest of the
 * app references by `nameOf<ThemePalette>('positive')` (see
 * `helpers/stockLevelLogic.ts`). Values are never read — it's the key set
 * that matters. FU-004: this used to hold runtime hex strings per theme; now
 * the values come from CSS custom properties (themes.scss).
 */
export interface ThemePalette {
    primary: string;
    secondary: string;
    accent: string;
    page: string;
    component: string;
    positive: string;
    negative: string;
    info: string;
    warning: string;
    text: string;
    disabled: string;
    border: string;
    divider: string;
    focus: string;
}

/**
 * The CSS custom property each Quasar palette key reads from. The SCSS file
 * defines every one of these per `[data-theme]` block, so this map is the
 * single bridge between the two systems.
 */
const QUASAR_PALETTE_FROM_CSS_VAR: Record<keyof ThemePalette, string> = {
    primary: '--brand-primary',
    secondary: '--brand-secondary',
    accent: '--brand-accent',
    page: '--surface-page',
    component: '--surface-component',
    positive: '--semantic-positive',
    negative: '--semantic-negative',
    info: '--semantic-info',
    warning: '--semantic-warning',
    text: '--text-primary',
    disabled: '--text-muted',
    border: '--border-default',
    divider: '--divider',
    focus: '--focus-ring',
};

export interface ThemeOption {
    /** key persisted on User.theme + sent over the wire. */
    key: ThemePreference;
    /** Fun display name shown in the preference picker. */
    label: string;
    /** Short description shown under the label. */
    blurb: string;
    /** One-line preview swatch hex strip (3 hexes) for the picker UI.
     *  This is the *branded* preview, not the resolved palette — it can
     *  diverge slightly from the operational palette by design (e.g. a
     *  toned-down primary still wants the punchier swatch in the picker). */
    swatch: [string, string, string];
    /** Whether Quasar's Dark.set() should be flipped on for this theme. */
    isDark: boolean;
}

// Picker metadata per theme. Operational palette values live in
// `css/themes.scss` under each `[data-theme="…"]` block — FU-004
// (resolved 2026-06-26) collapsed the duplicated TS palette dict into
// runtime reads from those CSS vars.
export const THEMES: Record<string, ThemeOption> = {
    // ───────── Pesto family ─────────────────────────────────────────
    'pesto': {
        key: 'pesto', label: 'Pesto',
        blurb: 'Fresh garden green + teal with a golden accent.',
        swatch: ['hsl(150,76%,39%)', 'hsl(189,100%,26%)', 'hsl(50,99%,56%)'],
        isDark: false,
    },
    'pesto-dark': {
        key: 'pesto-dark', label: 'Pesto Dark',
        blurb: 'Forest teal with bright lime.',
        swatch: ['hsl(150,75%,55%)', 'hsl(170,28%,30%)', 'hsl(225,100%,93%)'],
        isDark: true,
    },

    // ───────── Lemon Tart family ────────────────────────────────────
    'lemon-tart': {
        key: 'lemon-tart', label: 'Lemon Tart',
        blurb: 'Warm yellow on cream, the original Dora look.',
        swatch: ['hsl(40,88%,67%)', 'hsl(189,100%,26%)', 'hsl(48,99%,56%)'],
        isDark: false,
    },
    'lemon-tart-dark': {
        key: 'lemon-tart-dark', label: 'Lemon Tart Dark',
        blurb: 'Charcoal, gold and sunset orange.',
        swatch: ['hsl(46,100%,50%)', 'hsl(105,47%,36%)', 'hsl(23,100%,57%)'],
        isDark: true,
    },

    // ───────── Blueberry family ─────────────────────────────────────
    'blueberry': {
        key: 'blueberry', label: 'Blueberry',
        blurb: 'Cool cobalt + navy. Focused, easy on long-session eyes.',
        swatch: ['hsl(218,76%,56%)', 'hsl(220,60%,22%)', 'hsl(195,90%,60%)'],
        isDark: false,
    },
    'blueberry-dark': {
        key: 'blueberry-dark', label: 'Blueberry Dark',
        blurb: 'Muted teal + lavender on near-black. Twilight blueberry patch.',
        swatch: ['hsl(193,25%,66%)', 'hsl(184,14%,47%)', 'hsl(232,41%,75%)'],
        isDark: true,
    },

    // ───────── Cherry Cola family ───────────────────────────────────
    'cherry-cola': {
        key: 'cherry-cola', label: 'Cherry Cola',
        blurb: 'Bold cherry red + cocoa, served with a caramel accent.',
        swatch: ['hsl(352,65%,50%)', 'hsl(355,50%,18%)', 'hsl(36,85%,56%)'],
        isDark: false,
    },
    'cherry-cola-dark': {
        key: 'cherry-cola-dark', label: 'Cherry Cola Dark',
        blurb: 'Deep merlot + olive sage. Cellar-rich and unapologetic.',
        swatch: ['hsl(98,60%,70%)', 'hsl(2,16%,19%)', 'hsl(74,36%,44%)'],
        isDark: true,
    },

    // ───────── Sourdough family ─────────────────────────────────────
    'sourdough': {
        key: 'sourdough', label: 'Sourdough',
        blurb: 'Toasty amber + brown crust on a proofed cream. Rustic.',
        swatch: ['hsl(33,72%,55%)', 'hsl(28,36%,28%)', 'hsl(45,88%,60%)'],
        isDark: false,
    },
    'sourdough-dark': {
        key: 'sourdough-dark', label: 'Sourdough Dark',
        blurb: 'Warm browns and honey on dark.',
        swatch: ['hsl(33,80%,60%)', 'hsl(28,30%,40%)', 'hsl(45,90%,65%)'],
        isDark: true,
    },

    // ───────── Salt & Pepper family (the neutral pair) ────────────────────
    // Owner, 2026-09-03 (revising his own earlier brief): "make it more
    // neutral … a modern OS look with light/dark theme where you hardly see
    // colour. There should only be maybe one accent colour." Achromatic
    // blue-greys carry the family; one blue does primary + accent + focus.
    // See the block comment in css/themes.scss for why the warm-graphite
    // first cut didn't answer the brief.
    'salt-pepper': {
        key: 'salt-pepper', label: 'Salt & Pepper',
        blurb: 'Desktop-plain greys, one blue accent. Barely a colour.',
        swatch: ['hsl(214,16%,95%)', 'hsl(214,12%,30%)', 'hsl(212,78%,36%)'],
        isDark: false,
    },
    'salt-pepper-dark': {
        key: 'salt-pepper-dark', label: 'Salt & Pepper Dark',
        blurb: 'The same greys after dark, same single blue accent.',
        swatch: ['hsl(214,10%,15%)', 'hsl(210,16%,94%)', 'hsl(204,88%,74%)'],
        isDark: true,
    },

    // ───────── Dragonfruit family (the colourful one) ─────────────────────
    'dragonfruit': {
        key: 'dragonfruit', label: 'Dragonfruit',
        blurb: 'Magenta rind + green tips on pale flesh. The bright one.',
        swatch: ['hsl(330,72%,50%)', 'hsl(168,55%,24%)', 'hsl(140,65%,52%)'],
        isDark: false,
    },
    'dragonfruit-dark': {
        key: 'dragonfruit-dark', label: 'Dragonfruit Dark',
        blurb: 'Hot pink and lime on near-black.',
        swatch: ['hsl(330,70%,66%)', 'hsl(165,30%,32%)', 'hsl(145,60%,58%)'],
        isDark: true,
    },
};

/** Family groupings for the Preferences picker. Each card renders one
 *  family with a Light / Dark toggle inside, so users can pick a vibe
 *  AND a mode separately. `system` is rendered as its own card. */
export interface ThemeFamily {
    key: string;            // family slug, not a theme key
    label: string;          // shown as the card title
    blurb: string;          // 1-line description
    light: string;          // theme key for the light variant
    dark: string;           // theme key for the dark variant
    system: string;         // theme key for the system-follows-OS variant
}

export const THEME_FAMILIES: readonly ThemeFamily[] = [
    {
        key: 'pesto',
        label: 'Pesto',
        blurb: "Fresh garden green + teal with a golden accent. Dora's default.",
        light: 'pesto', dark: 'pesto-dark', system: 'system-pesto',
    },
    {
        key: 'lemon-tart',
        label: 'Lemon Tart',
        blurb: 'Warm yellow on cream by day, charcoal + sunset by night.',
        light: 'lemon-tart', dark: 'lemon-tart-dark', system: 'system-lemon-tart',
    },
    {
        key: 'blueberry',
        label: 'Blueberry',
        blurb: 'Cool cobalt and navy.',
        light: 'blueberry', dark: 'blueberry-dark', system: 'system-blueberry',
    },
    {
        key: 'cherry-cola',
        label: 'Cherry Cola',
        blurb: 'Bold cherry red + cocoa, with a caramel pop.',
        light: 'cherry-cola', dark: 'cherry-cola-dark', system: 'system-cherry-cola',
    },
    {
        key: 'sourdough',
        label: 'Sourdough',
        blurb: 'Toasty amber + brown crust. Rustic any time of day.',
        light: 'sourdough', dark: 'sourdough-dark', system: 'system-sourdough',
    },
    {
        key: 'salt-pepper',
        label: 'Salt & Pepper',
        blurb: 'Plain greys and a single blue, light or dark.',
        light: 'salt-pepper', dark: 'salt-pepper-dark', system: 'system-salt-pepper',
    },
    {
        key: 'dragonfruit',
        label: 'Dragonfruit',
        blurb: 'Magenta rind + green tips. The bright one.',
        light: 'dragonfruit', dark: 'dragonfruit-dark', system: 'system-dragonfruit',
    },
];

/** The theme keys an older build saved, mapped to the key that replaced them.
 *  The server still accepts them (`user.py`), so both the applier and the
 *  picker read a stored key through this one table (R-003). */
const LEGACY_THEME_KEYS: Record<string, string> = {
    light: 'pesto',
    avocado: 'pesto',
    'pesto-noir': 'pesto-dark',
    'midnight-snack': 'lemon-tart-dark',
    dark: 'pesto-dark',
};

function currentThemeKey(themeKey: string): string {
    return LEGACY_THEME_KEYS[themeKey] ?? themeKey;
}

/** Reverse index: given a theme key (e.g. 'pesto-dark' / 'system-cherry-cola')
 *  return its family + which mode the picker should show as active. A legacy
 *  key decodes as the theme it now renders. */
export function familyAndModeOf(storedKey: string): { family: ThemeFamily; mode: 'system' | 'light' | 'dark' } | null {
    const themeKey = currentThemeKey(storedKey);
    for (const fam of THEME_FAMILIES) {
        if (fam.system === themeKey) return { family: fam, mode: 'system' };
        if (fam.light === themeKey) return { family: fam, mode: 'light' };
        if (fam.dark === themeKey) return { family: fam, mode: 'dark' };
    }
    // Legacy bare `system` maps to the Pesto family in system mode.
    if (themeKey === 'system') {
        return { family: THEME_FAMILIES[0]!, mode: 'system' };
    }
    return null;
}

/** Resolve (mode, family) back into the persistable theme key. The
 *  picker reads `themeKeyFor('dark', 'cherry-cola')` etc. to figure out
 *  what to save when the user clicks a card. */
export function themeKeyFor(
    mode: 'system' | 'light' | 'dark',
    family: ThemeFamily,
): ThemePreference {
    if (mode === 'system') return family.system as ThemePreference;
    if (mode === 'dark') return family.dark as ThemePreference;
    return family.light as ThemePreference;
}

/** What does the OS currently prefer? Returns 'dark' or 'light', with
 *  'light' as the fallback when matchMedia isn't available. */
export function osPrefersDark(): boolean {
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

const osDark = ref(false);
let osDarkWatched = false;

/** `osPrefersDark` as a ref that follows the OS setting, for a picker that
 *  previews "system" themes. One app-lifetime listener however many pages
 *  read it, so nothing has to remove it on unmount. */
export function osPrefersDarkRef(): Readonly<Ref<boolean>> {
    if (!osDarkWatched && typeof window !== 'undefined' && window.matchMedia) {
        osDarkWatched = true;
        const mql = window.matchMedia('(prefers-color-scheme: dark)');
        osDark.value = mql.matches;
        mql.addEventListener('change', (e) => { osDark.value = e.matches; });
    }
    return readonly(osDark);
}

/** Map any persisted value (including legacy keys) to a current concrete
 *  theme key in `THEMES`. `system-<family>` and the legacy bare `system`
 *  flip between the family's light + dark variant based on the OS's
 *  `prefers-color-scheme`. */
function resolveThemeKey(stored: ThemePreference): string {
    const pref = currentThemeKey(stored) as ThemePreference;
    if (pref === 'system') return osPrefersDark() ? 'pesto-dark' : 'pesto';
    // Round-19: per-family system keys. Lookup the family + flip on OS pref.
    if (typeof pref === 'string' && pref.startsWith('system-')) {
        const family = THEME_FAMILIES.find((f) => f.system === pref);
        if (family) return osPrefersDark() ? family.dark : family.light;
        return osPrefersDark() ? 'pesto-dark' : 'pesto';
    }
    return THEMES[pref] ? pref : 'pesto';
}

// A6 — re-spaced steps (ratios ~0.85 / 1.0 / 1.25 / 1.4) with a very slightly
// larger base than the old 16px. These drive the root font-size, so all
// rem-based text (incl. the --font-size-* ratio tokens) scales with them.
const FONT_SIZE_PX: Record<FontSizePreference, string> = {
    sm: '14px',
    md: '16.5px',
    lg: '20.5px',
    xl: '23px',
};

const SYSTEM_FALLBACK =
    "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
const FONT_FAMILY_CSS: Record<FontFamilyPreference, string> = {
    default: '',
    urbanist: `'Urbanist Variable', 'Urbanist', ${SYSTEM_FALLBACK}`,
    nunito: `'Nunito Variable', 'Nunito', ${SYSTEM_FALLBACK}`,
    inter: `'Inter Variable', 'Inter', ${SYSTEM_FALLBACK}`,
    lexend: `'Lexend Variable', 'Lexend', ${SYSTEM_FALLBACK}`,
    plus_jakarta_sans: `'Plus Jakarta Sans Variable', 'Plus Jakarta Sans', ${SYSTEM_FALLBACK}`,
};

// FU-614 (R-003) — the single source of the font-family picker vocabulary,
// shared by the Preferences segmented control and the onboarding wizard.
// "Nunito (Default)" names the default (the app's base body font); the standalone
// 'nunito' option is intentionally dropped as a confusing duplicate of it —
// `coalesceFontFamily` folds any legacy 'nunito' selection back onto 'default'.
const FONT_FAMILY_OPTIONS: { value: FontFamilyPreference; label: string }[] = [
    { value: 'default', label: 'Nunito (Default)' },
    { value: 'urbanist', label: 'Urbanist' },
    { value: 'inter', label: 'Inter' },
    { value: 'lexend', label: 'Lexend' },
    { value: 'plus_jakarta_sans', label: 'Plus Jakarta Sans' },
];

/** The font-family picker options, with optional per-surface label overrides —
 *  e.g. the compact Preferences control shortens "Plus Jakarta Sans" to fit. */
export function fontFamilyOptions(
    labelOverrides: Partial<Record<FontFamilyPreference, string>> = {},
): { value: FontFamilyPreference; label: string }[] {
    return FONT_FAMILY_OPTIONS.map((o) => ({ value: o.value, label: labelOverrides[o.value] ?? o.label }));
}

/** Fold a stored font-family onto an offered option: `undefined` or the retired
 *  standalone 'nunito' both map to 'default' (which renders as Nunito), so the
 *  picker always shows a valid selection. */
export function coalesceFontFamily(f: FontFamilyPreference | undefined): FontFamilyPreference {
    return f === undefined || f === 'nunito' ? 'default' : f;
}

let mediaQuery: MediaQueryList | null = null;
let mediaQueryListener: ((event: MediaQueryListEvent) => void) | null = null;
let cachedThemePref: ThemePreference = 'system';

function applyThemeKey(themeKey: string) {
    const theme = THEMES[themeKey];
    if (!theme) return;
    // set data-theme FIRST so the SCSS custom properties for the
    // target theme are live before we read them back into Quasar's palette.
    if (typeof document !== 'undefined') {
        document.documentElement.setAttribute('data-theme', themeKey);
    }
    syncQuasarPaletteFromCssVars();
    Dark.set(theme.isDark);
    // FU-824 — surfaces that can't express a colour in CSS (the dashboard's SVG
    // donut, chart series) read their tokens off the document with
    // `getComputedStyle`, which is not reactive. Tell them the theme moved so
    // their computeds re-evaluate; without this they keep the old theme's
    // colours until something else happens to invalidate them.
    notifyThemeChanged();
}

/**
 * Copy each Quasar palette key (--q-primary, --q-positive, …) from the
 * corresponding semantic CSS var defined in `css/themes.scss`. Reading from
 * the document root catches whichever `[data-theme]` block is currently
 * active — so a per-theme palette dict in TS is no longer needed.
 *
 * `setCssVar` accepts plain hsl/rgb/hex strings; modern HSL syntax
 * (`hsl(150 60% 36%)`) and Quasar are both happy with that form.
 */
function syncQuasarPaletteFromCssVars() {
    if (typeof document === 'undefined' || typeof window === 'undefined') return;
    const computed = window.getComputedStyle(document.documentElement);
    for (const [qKey, cssVar] of Object.entries(QUASAR_PALETTE_FROM_CSS_VAR)) {
        const value = computed.getPropertyValue(cssVar).trim();
        if (value) setCssVar(qKey, value);
    }
    // FU-709 — the dark page background, resolved 2026-09-03.
    //
    // `css/app.scss` paints `body { background-color: var(--q-page) }`, but
    // Quasar ships `body.body--dark { background: var(--q-dark-page) }` — a
    // *class* selector, so it out-specifies ours, and nothing ever set
    // `--q-dark-page`. Every dark theme therefore painted Quasar's
    // `$dark-page` (#14171a) and each block's hand-authored `--surface-page`
    // (Pesto Dark #00120B, Cherry Cola #2E0014, …) was dead code — visible
    // only where a component happened to paint the token directly, which is
    // how it was found (a peek header reading as a deliberate dark-green
    // band). The FU held it as an owner-visible design call rather than
    // slipping it in; the owner made it: *"Did we stop colouring everything
    // in the app like the background? Could adjust the background with each
    // theme to have a tint of the main colour of that theme."* That is option
    // (a) — honour the authored colours — so the dark page reads from the
    // same token as the light one, and the per-theme tint paints in both
    // modes. One token, one source of truth (R-003).
    const page = computed.getPropertyValue('--surface-page').trim();
    if (page) setCssVar('dark-page', page);
}

function attachSystemListener() {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    detachSystemListener();
    mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    mediaQueryListener = () => {
        if (cachedThemePref === 'system') {
            applyThemeKey(resolveThemeKey('system'));
        }
    };
    mediaQuery.addEventListener('change', mediaQueryListener);
}

function detachSystemListener() {
    if (mediaQuery && mediaQueryListener) {
        mediaQuery.removeEventListener('change', mediaQueryListener);
    }
    mediaQuery = null;
    mediaQueryListener = null;
}

// Brand default — the theme used pre-auth and as the fallback for users
// without a saved preference. Bumping this is the single edit needed to
// shift the unauthenticated paint.
export const DEFAULT_THEME_KEY = 'pesto';

export default class ThemeService {
    /** Initial paint on boot — uses the OS preference until the
     *  user's saved theme arrives from /auth/me, then re-paints. */
    applyTheme = () => {
        cachedThemePref = 'system';
        applyThemeKey(resolveThemeKey('system'));
        attachSystemListener();
    };

    /** Apply the brand default theme. Used pre-auth and on sign-out so
     *  the app never silently flips into dark mode without the user
     *  asking — which was breaking the login page when the OS was in
     *  dark mode. */
    applyDefault = () => {
        cachedThemePref = DEFAULT_THEME_KEY as ThemePreference;
        applyThemeKey(DEFAULT_THEME_KEY);
        detachSystemListener();
    };

    /** Apply the signed-in user's persisted preferences. Safe to call
     *  on every auth-store change — idempotent. */
    applyForUser = (
        theme: ThemePreference,
        fontFamily: FontFamilyPreference,
        fontSize: FontSizePreference,
    ) => {
        cachedThemePref = theme;
        applyThemeKey(resolveThemeKey(theme));
        if (theme === 'system') attachSystemListener();
        else detachSystemListener();

        if (typeof document !== 'undefined') {
            document.documentElement.style.setProperty(
                '--dora-base-font-size',
                FONT_SIZE_PX[fontSize],
            );
            const family = FONT_FAMILY_CSS[fontFamily];
            if (family) {
                document.body.style.fontFamily = family;
            } else {
                document.body.style.removeProperty('font-family');
            }
        }
    };
}
