// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { downloadCsv } from 'src/services/files/downloadHelpers';

let saved: Blob | null = null;

beforeEach(() => {
    saved = null;
    URL.createObjectURL = vi.fn((blob: Blob) => {
        saved = blob;
        return 'blob:test';
    });
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
});

afterEach(() => {
    vi.restoreAllMocks();
});

async function csvOf(rows: unknown[][]): Promise<string> {
    downloadCsv(['a', 'b'], rows, 'out.csv');
    expect(saved).not.toBeNull();
    return await saved!.text();
}

describe('downloadCsv cell escaping', () => {
    it('leaves plain cells bare', async () => {
        expect(await csvOf([['x', 1]])).toBe('a,b\nx,1');
    });

    it('quotes commas, quotes and line feeds', async () => {
        expect(await csvOf([['a,b', 'say "hi"'], ['line\nbreak', '']]))
            .toBe('a,b\n"a,b","say ""hi"""\n"line\nbreak",');
    });

    it('quotes a lone carriage return', async () => {
        expect(await csvOf([['one\rtwo', 'ok']])).toBe('a,b\n"one\rtwo",ok');
    });
});
