/**
 * Shared helpers for "fetch a file from the API and save it via the
 * browser". Used by every in-context export composable + the backup
 * download. Centralised so the Content-Disposition regex and the
 * <a download> trick live in one place.
 */

/** Pull a filename out of a Content-Disposition header. Returns null
 *  when the header is missing or doesn't carry a filename. */
export function parseFilename(header: string | null): string | null {
    if (!header) return null;
    const match = /filename="?([^";]+)"?/i.exec(header);
    return match ? match[1]! : null;
}

/** Trigger a browser download of a blob. Cleans up the object URL
 *  after the click so we don't leak memory across many exports. */
/** Build an RFC-4180 CSV from rows and hand it to the browser as a download
 *  (finalisation 18-R8 — the import page carried its own escaper + anchor
 *  click). Cells are quoted when they hold a comma, quote, CR or LF. */
export function downloadCsv(
    header: readonly string[],
    rows: ReadonlyArray<ReadonlyArray<unknown>>,
    filename: string,
): void {
    const escape = (v: unknown): string => {
        let s: string;
        if (v === null || v === undefined) s = '';
        else if (typeof v === 'string') s = v;
        else if (typeof v === 'number' || typeof v === 'boolean' || typeof v === 'bigint') s = String(v);
        else s = JSON.stringify(v) ?? '';
        return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const lines = [header.join(','), ...rows.map((r) => r.map(escape).join(','))];
    triggerSave(new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' }), filename);
}

export function triggerSave(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
}
