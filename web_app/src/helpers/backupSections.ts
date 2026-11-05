// Display helpers shared by the backup page's pieces (FU-948 (2)). The section
// catalogue itself is the server's (`GET /api/data/backup/sections`).
import { formatDateTime } from 'src/composables/useDateFormat';
import type { BackupSection } from 'src/services/api/dataApiService';

export function formatBackupTimestamp(iso: string | null, unknown = 'unknown'): string {
    if (!iso) return unknown;
    try {
        return formatDateTime(iso) || iso;
    } catch {
        return iso;
    }
}

export function sectionLabel(sections: readonly BackupSection[], key: string): string {
    return sections.find((s) => s.key === key)?.label ?? key;
}

/** The sensitive sections among `keys`, lower-cased and listed ("users,
 *  system settings"), or '' when there are none. Which sections count is the
 *  server's `Section.sensitive` flag. */
export function sensitiveSectionsLabel(sections: readonly BackupSection[], keys: readonly string[]): string {
    const sensitive = new Set(sections.filter((s) => s.sensitive).map((s) => s.key));
    return keys
        .filter((k) => sensitive.has(k))
        .map((k) => sectionLabel(sections, k).toLowerCase())
        .join(', ');
}

export interface RestoreReportRow {
    section: string;
    label: string;
    created: number;
    skipped: number;
}

export interface RestoreReport {
    ok: boolean;
    headline: string;
    rows: RestoreReportRow[];
    warnings: string[];
}
