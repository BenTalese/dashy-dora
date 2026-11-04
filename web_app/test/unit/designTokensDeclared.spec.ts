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
 * Custom properties declared at **runtime** by code this suite can't see, so
 * they are legitimately absent from the stylesheets:
 *   • `--q-*` — Quasar writes its own palette onto `:root` from
 *     `quasar.variables.scss` at boot.
 *
 * Runtime declarations made from *our* code don't belong here — the scan picks
 * them up itself: `style.setProperty('--x', …)` (the user's font size in
 * `themeService.ts`, the keyboard inset in `boot/keyboardInset.ts`) and a
 * quoted key in a style binding (`{ '--stock-row-height': … }` in
 * `StockOverview.vue`). See `declaredProperties()`.
 */
const RUNTIME_DECLARED = [/^--q-/];

/**
 * Pre-existing undeclared tokens, enumerated so this suite can be **green and
 * still ratcheting**: a new undeclared token fails the suite, and fixing one of
 * these forces its removal from the list (the third test asserts every entry
 * is still genuinely broken, so the list cannot rot).
 *
 * Found 2026-09-02 by this test, on its first run (FU-834: 21 tokens). Swept
 * 2026-11-04: each call site repointed at the token it meant
 * (`--surface-border` → `--border-default`, `--surface-card` /
 * `--surface-default` → `--surface-component`, `--surface-muted` →
 * `--surface-sunken`, `--overlay-pressed` → `--elevation-2`, `--text-warning`
 * → body ink), `--font-mono` declared as a real token in `tokens.scss`, and
 * `--stock-row-height` recognised as the runtime declaration it always was.
 * `--space-sm` / `--space-xs` were only ever a *comment* in
 * `RecipeCookMode.vue` by then. **The list's target is empty.**
 */
const KNOWN_UNDECLARED: string[] = [];

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
    // Runtime declarations from script: `el.style.setProperty('--x', …)` and a
    // quoted key in a `:style` object (`{ '--x': … }`). Both write a real
    // custom property onto an element; the second form is invisible to the
    // regex above because the quote sits between the name and the colon.
    for (const file of walk(SRC, ['.vue', '.ts'])) {
        const text = readFileSync(file, 'utf8');
        for (const m of text.matchAll(/setProperty\(\s*['"`](--[A-Za-z0-9_-]+)['"`]/g)) {
            declared.add(m[1]!);
        }
        for (const m of text.matchAll(/['"](--[A-Za-z0-9_-]+)['"]\s*:/g)) {
            declared.add(m[1]!);
        }
    }
    return declared;
}

type Reference = { token: string; file: string; line: number; hasFallback: boolean };

/**
 * Every token reference in `.vue` / `.scss` / `.ts` under `src/`:
 *   • `var(--token)` anywhere, and
 *   • a token *name* read from script as a bare string literal —
 *     `getPropertyValue('--surface-page')`, the Quasar palette map in
 *     `themeService.ts`, `paletteToken('--semantic-warning', …)`,
 *     `motionDurationMs('--motion-slow')`. An undeclared name there reads back
 *     as `''` — the same silent failure, one layer up.
 * A quoted name followed by `:` is a declaration (see `declaredProperties`),
 * and so is the first argument of `setProperty`; neither is a reference.
 */
function references(): Reference[] {
    const out: Reference[] = [];
    const files = walk(SRC, ['.vue', '.scss', '.css', '.ts']);
    for (const file of files) {
        const isScript = file.endsWith('.ts') || file.endsWith('.vue');
        const lines = readFileSync(file, 'utf8').split(/\r?\n/);
        lines.forEach((line, i) => {
            const at = { file: relative(SRC, file).replace(/\\/g, '/'), line: i + 1 };
            for (const m of line.matchAll(/var\(\s*(--[A-Za-z0-9_-]+)\s*(,)?/g)) {
                out.push({ token: m[1]!, ...at, hasFallback: m[2] === ',' });
            }
            // Script string literals only, and not in a `//` / `*` comment line
            // (prose examples like `getPropertyValue('--x')`).
            if (!isScript || /^\s*(\/\/|\*|\/\*)/.test(line)) return;
            for (const m of line.matchAll(/(setProperty\(\s*)?(['"])(--[A-Za-z][A-Za-z0-9_-]*)\2(\s*:)?/g)) {
                if (m[1] || m[4]) continue;
                out.push({ token: m[3]!, ...at, hasFallback: false });
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
        // The script-side scans are live too.
        expect(declared.has('--stock-row-height')).toBe(true);
        expect(declared.has('--dora-base-font-size')).toBe(true);
        expect(
            refs.some((r) => r.token === '--focus-ring' && r.file === 'services/themeService.ts'),
        ).toBe(true);
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
