/**
 * R-060 guard — every `var(--token)` referenced in the SPA must name a custom
 * property that `css/` actually declares.
 *
 * Why this exists as a test rather than a review habit: an undefined custom
 * property with no fallback makes the **whole declaration invalid at
 * computed-value time**, so the property silently falls back to its initial
 * value. It does not warn, does not fail the build, does not fail lint and does
 * not fail `vue-tsc`. `gap: var(--space-sm)` is not "roughly 8px" — it is zero.
 * The code reads correctly, which is exactly why humans miss it.
 *
 * Two live instances were found by hand on 2026-09-02, both mis-rendering in
 * production for months:
 *   • `--border-subtle` — referenced in 5 components, declared nowhere, so
 *     `border: 1px solid var(--border-subtle)` rendered **no border**. The
 *     dashboard's reconcile chip sat borderless in a grid of bordered cards.
 *   • `--dora-text` / `--dora-primary` / `--dora-positive` / `--dora-negative`
 *     / `--dora-muted-bg` / `--dora-*-bg` — the entire colour vocabulary of
 *     `DoraScoreCard.vue`, so the card painted from hard-coded hex fallbacks in
 *     all ten themes and answered feedback D2 ("dark mode not working") with
 *     "still broken".
 *
 * This is the low-churn, expensive-to-hand-check contract the verification
 * stance says to automate: the token scale changes rarely, and re-checking it
 * by hand means several hundred greps.
 */
import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const SRC = join(__dirname, '..', '..', 'src');
const CSS_DIR = join(SRC, 'css');

/**
 * Custom properties declared at **runtime** rather than in `css/`, so they are
 * legitimately absent from the stylesheets:
 *   • `--q-*` — Quasar writes its own palette onto `:root` from
 *     `quasar.variables.scss` at boot.
 *   • `--dora-base-font-size` — written by `themeService.ts:412` for the
 *     user's font-size preference (and referenced with a `16px` fallback).
 */
// `--vv-inset-*` are the on-screen keyboard's overlap, measured from
// `visualViewport` by `boot/keyboardInset.ts` — a runtime fact, never a token.
const RUNTIME_DECLARED = [/^--q-/, /^--dora-base-font-size$/, /^--vv-inset-(top|bottom)$/];

/**
 * Pre-existing undeclared tokens, enumerated so this suite can be **green and
 * still ratcheting**: a new undeclared token fails the build, and fixing one of
 * these forces its removal from the list (the second test asserts every entry
 * is still genuinely broken, so the list cannot rot).
 *
 * Found 2026-09-02 by this test, on its first run. Tracked as **FU-834** — an
 * app-wide sweep, deliberately out of scope for the dashboard chunk that added
 * the guard. Every one of these is R-060's named smell: reaching for a token
 * name that *looks* like the scale (`--space-sm` where the scale is
 * `--space-1..12`; `--surface-card` where the token is `--surface-component`).
 *
 * Note the first two entries: `RecipeCookMode.vue:19` is the **exact file that
 * established R-060** on 2026-08-28 — the rule was written because cook mode's
 * header was reported three times as "squished" before anyone checked whether
 * its gap tokens resolved. Two of them still don't.
 */
const KNOWN_UNDECLARED = [
    '--space-sm',          // RecipeCookMode.vue:19 — scale is --space-1..12
    '--space-xs',          // RecipeCookMode.vue:19 — ditto
    '--surface-border',    // PutAwayDialog.vue:294,307
    '--surface-card',      // VoicePicker.vue:384 (TriStateFilter fixed 2026-09-02)
    '--surface-default',
    '--surface-muted',     // RecipeNutriScore.vue:99
    '--surface-raised',    // StockItemDetailPage.vue:2788
    '--text-sm',           // HelpPage.vue:686
    '--text-warning',
    '--font-mono',         // ApiAccessSettings.vue:542
    '--overlay-pressed',   // ShoppingListDetail.vue:3009
    '--stock-row-height',
    // `--c-surface-2`, `--c-surface-3`, `--c-line-strong` and `--c-line` came
    // off this list on 2026-09-02 (dashboard chunk 6). Retiring the dashboard's
    // page-local `--c-*` alias layer (FU-747) removed `--c-line` from the
    // declared set, which exposed all four in `MarkAsWastedDialog.vue` and
    // `StocktakeRunner.vue` — they had always been painting hard-coded rgba
    // fallbacks instead of following the theme. Now on real tokens.
];

/** Recursively collect files under `dir` whose name matches one of `exts`. */
function walk(dir: string, exts: string[]): string[] {
    const out: string[] = [];
    for (const entry of readdirSync(dir)) {
        const full = join(dir, entry);
        if (statSync(full).isDirectory()) {
            out.push(...walk(full, exts));
        } else if (exts.some((e) => entry.endsWith(e))) {
            out.push(full);
        }
    }
    return out;
}

/**
 * Custom properties the app *declares*. Collected from the whole `css/` tree —
 * `tokens.scss` holds the base scale, `themes.scss` re-declares per
 * `[data-theme]`, `motion.scss` owns the durations — plus any declaration made
 * inline in a component (a page-local alias like the dashboard's `--c-*` layer
 * is a legitimate declaration, so those count too).
 */
function declaredProperties(): Set<string> {
    const declared = new Set<string>();
    const files = [
        ...walk(CSS_DIR, ['.scss', '.css']),
        ...walk(SRC, ['.vue']),
    ];
    for (const file of files) {
        const text = readFileSync(file, 'utf8');
        // `--name:` in a declaration position. Also catches `@property --name`
        // and inline `style="--x: y"`, which are equally real declarations.
        for (const m of text.matchAll(/(--[A-Za-z0-9_-]+)\s*:/g)) {
            declared.add(m[1]!);
        }
    }
    return declared;
}

type Reference = { token: string; file: string; line: number; hasFallback: boolean };

/** Every `var(--token)` reference in `.vue` / `.scss` / `.ts` under `src/`. */
function references(): Reference[] {
    const out: Reference[] = [];
    const files = walk(SRC, ['.vue', '.scss', '.css', '.ts']);
    for (const file of files) {
        const lines = readFileSync(file, 'utf8').split(/\r?\n/);
        lines.forEach((line, i) => {
            for (const m of line.matchAll(/var\(\s*(--[A-Za-z0-9_-]+)\s*(,)?/g)) {
                out.push({
                    token: m[1]!,
                    file: relative(SRC, file).replace(/\\/g, '/'),
                    line: i + 1,
                    hasFallback: m[2] === ',',
                });
            }
        });
    }
    return out;
}

describe('R-060 — design tokens are declared before they are referenced', () => {
    const declared = declaredProperties();
    const refs = references();
    const isRuntime = (token: string) => RUNTIME_DECLARED.some((re) => re.test(token));

    /** Undeclared references, grouped by token name. */
    const undeclaredByToken = (() => {
        const byToken = new Map<string, string[]>();
        for (const r of refs) {
            if (declared.has(r.token) || isRuntime(r.token)) continue;
            const sites = byToken.get(r.token) ?? [];
            sites.push(`${r.file}:${r.line}${r.hasFallback ? ' (has fallback)' : ''}`);
            byToken.set(r.token, sites);
        }
        return byToken;
    })();

    it('finds tokens and references to check (guards against a vacuous pass)', () => {
        // If the traversal silently breaks, every assertion below passes for the
        // wrong reason — which would be worse than having no test at all.
        expect(declared.size).toBeGreaterThan(100);
        expect(refs.length).toBeGreaterThan(500);
        expect(declared.has('--surface-component')).toBe(true);
        expect(declared.has('--space-4')).toBe(true);
    });

    it('introduces no NEW undeclared custom property', () => {
        const unexpected = [...undeclaredByToken.entries()].filter(
            ([token]) => !KNOWN_UNDECLARED.includes(token),
        );
        const report = unexpected
            .map(([token, sites]) => `  ${token}\n${sites.map((s) => `    ${s}`).join('\n')}`)
            .join('\n');
        expect(
            unexpected.map(([token]) => token),
            `Undeclared custom property (R-060). An undefined custom property with ` +
                `no fallback makes the WHOLE declaration invalid at computed-value time, ` +
                `so the property silently falls back to its initial value — it does not ` +
                `warn, does not fail the build and does not fail lint. Declare it in ` +
                `css/tokens.scss (and every [data-theme] block in themes.scss), or point ` +
                `the reference at a token that exists:\n${report}`,
        ).toEqual([]);
    });

    it('keeps the KNOWN_UNDECLARED ratchet honest — fixed tokens must be removed from it', () => {
        // Without this, the allowlist rots into a permanent exemption list and
        // the guard quietly stops guarding.
        const nowDeclared = KNOWN_UNDECLARED.filter(
            (token) => !undeclaredByToken.has(token),
        );
        expect(
            nowDeclared,
            `These tokens are no longer undeclared (or no longer referenced), so ` +
                `they must be deleted from KNOWN_UNDECLARED in this file — see FU-834.`,
        ).toEqual([]);
    });

    it('the dashboard and its shared components reference only declared tokens', () => {
        // The surfaces the 2026-09-02 R-060 sweep fixed. Held to the strict rule
        // with no allowlist, so the two families that were broken here
        // (`--border-subtle`, `--dora-*`) cannot come back.
        const swept = (file: string) =>
            file.startsWith('components/dashboard/') ||
            file === 'pages/DashboardPage.vue' ||
            file === 'components/BaseSelect.vue' ||
            file === 'components/filters/TriStateFilter.vue';
        const offenders = refs
            .filter((r) => swept(r.file) && !declared.has(r.token) && !isRuntime(r.token))
            .map((r) => `${r.token} @ ${r.file}:${r.line}`);
        expect(offenders).toEqual([]);
    });

    it('uses the type-scale tokens as lengths, never multiplied by 1rem', () => {
        // `--font-size-*` are rem lengths with a 12px floor on `xs` (D-003,
        // finalisation 20-R12). They used to be unitless multipliers that every
        // consumer scaled by `calc(var(…) * 1rem)` itself — a floor can't be
        // expressed that way, and a bare `var()` of a ratio silently dropped
        // the declaration (08-R22). The two conventions can't coexist.
        const multiplied = walk(SRC, ['.vue', '.scss', '.css'])
            .flatMap((path) => readFileSync(path, 'utf8').split('\n').map((line, i) => ({ path, line, n: i + 1 })))
            .filter(({ line }) => /calc\(var\(--font-size-[a-z0-9]+\)\s*\*\s*1r?em\)/.test(line))
            .map(({ path, n }) => `${path.slice(SRC.length + 1)}:${n}`);
        expect(multiplied).toEqual([]);
        const tokens = readFileSync(join(CSS_DIR, 'tokens.scss'), 'utf8');
        expect(tokens).toMatch(/--font-size-xs:\s*max\(12px,\s*0\.75rem\);/);
    });
});
