/**
 * 11-D1: Dora's `app_help` tool answers how-to questions from the same guides
 * the Help pages render. The guides live here in `helpContent.ts`; the server
 * reads a JSON export of them (`dora_api/features/help/help_corpus.json`). This
 * spec is the drift guard: it fails when the two disagree.
 *
 * After editing a guide, refresh the export with:
 *     DORA_UPDATE_HELP_CORPUS=1 npx vitest run test/unit/helpCorpusExport.spec.ts
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { HELP_TOPICS } from 'src/help/helpContent';

const EXPORT_PATH = resolve(__dirname, '../../../dora_api/features/help/help_corpus.json');

function corpus() {
    return HELP_TOPICS.map((topic) => ({
        slug: topic.slug,
        title: topic.title,
        blurb: topic.blurb,
        entries: topic.entries.map((e) => ({
            slug: e.slug,
            title: e.title,
            summary: e.summary,
            how: e.how ?? null,
            setting: e.setting?.label ?? null,
            setting_path: e.setting?.path ?? null,
            note: e.note ?? null,
            path: e.path ?? null,
        })),
    }));
}

describe('help corpus export', () => {
    it('matches helpContent.ts', () => {
        const expected = JSON.stringify(corpus(), null, 2) + '\n';
        if (process.env.DORA_UPDATE_HELP_CORPUS === '1') {
            writeFileSync(EXPORT_PATH, expected, 'utf8');
        }
        const actual = readFileSync(EXPORT_PATH, 'utf8');
        expect(actual, 'help_corpus.json is stale: run with DORA_UPDATE_HELP_CORPUS=1').toBe(expected);
    });
});
