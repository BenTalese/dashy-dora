/**
 * Pins on the Help content (2026-10-29 redesign): the deep-link contract the
 * (?) chips depend on, the routes the guides point at, the copy rules (D-025),
 * and that every screenshot a guide names exists once it has been taken.
 */
import { describe, expect, it } from 'vitest';
import { existsSync } from 'node:fs';
import { join } from 'node:path';

import { HELP_TOPICS, allEntries, resolveDeepLink, searchHelp } from 'src/help/helpContent';
import routes from 'src/router/routes';

/** Titles other surfaces navigate to with `/help?q=<title>` (HelpHint,
 *  RunnerShell, StocktakeRunner, AssistantSettings). */
const DEEP_LINKED_TITLES = [
    'Substitutes',
    'QR label',
    'Barcodes',
    'How stocktake works',
    'Reconcile past meals',
];

function flatten(list: typeof routes, prefix = ''): string[] {
    return list.flatMap((r) => {
        const path = r.path.startsWith('/') ? r.path : `${prefix.replace(/\/$/, '')}/${r.path}`;
        return [path, ...(r.children ? flatten(r.children, path) : [])];
    });
}
const ROUTE_PATHS = flatten(routes).map((p) => p.replace(/\/+/g, '/'));

function routeExists(path: string): boolean {
    const clean = path.split('?')[0]!;
    return ROUTE_PATHS.some((rp) => {
        if (rp.includes(':')) {
            const re = new RegExp('^' + rp.replace(/:[^/()]+(\([^)]*\))?\*?/g, '[^/]+') + '$');
            return re.test(clean);
        }
        return rp === clean || rp === `${clean}/`;
    });
}

describe('help content', () => {
    it('has unique topic and guide slugs', () => {
        const topicSlugs = HELP_TOPICS.map((t) => t.slug);
        expect(new Set(topicSlugs).size).toBe(topicSlugs.length);
        const slugs = allEntries().map((h) => `${h.topic.slug}/${h.entry.slug}`);
        expect(new Set(slugs).size).toBe(slugs.length);
    });

    it('resolves every deep-linked title to exactly one guide', () => {
        for (const title of DEEP_LINKED_TITLES) {
            const hit = resolveDeepLink(title);
            expect(hit?.entry.title, title).toBe(title);
        }
        // The assistant settings link with a partial title.
        expect(resolveDeepLink('Dora thinks')?.entry.slug).toBe('dora-thinks');
        // A word many guides share is a search, not a deep link.
        expect(resolveDeepLink('list')).toBeNull();
    });

    it('points every guide and setting at a real route', () => {
        const bad: string[] = [];
        for (const { entry } of allEntries()) {
            for (const path of [entry.path, entry.setting?.path]) {
                if (path && !routeExists(path)) bad.push(`${entry.slug} → ${path}`);
            }
        }
        expect(bad).toEqual([]);
    });

    it('keeps the copy short and in the house voice', () => {
        const long: string[] = [];
        const dashes: string[] = [];
        for (const { entry } of allEntries()) {
            for (const text of [entry.title, entry.summary, entry.how, entry.note]) {
                if (!text) continue;
                if (text.includes('—')) dashes.push(entry.slug);
            }
            if (entry.summary.split(/\s+/).length > 45) long.push(entry.slug);
        }
        expect(dashes).toEqual([]);
        expect(long).toEqual([]);
    });

    it('finds guides by any of their words', () => {
        expect(searchHelp('stocktake').some((h) => h.entry.slug === 'how-stocktake-works')).toBe(true);
        expect(searchHelp('')).toEqual([]);
    });

    it('names only screenshots that exist', () => {
        const dir = join(__dirname, '..', '..', 'src', 'assets', 'help');
        const missing = allEntries()
            .filter((h) => h.entry.image && !existsSync(join(dir, `${h.entry.image}.png`)))
            .map((h) => h.entry.image!);
        expect(missing).toEqual([]);
    });
});
