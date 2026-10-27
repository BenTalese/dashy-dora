import AxiosHttpClient from './axiosHttpClient';
import type { Page } from './queryStringBuilder';

/**
 * One row of `GET /api/data/backup/sections` — the server's backup section
 * catalogue (`restore_shared.SECTIONS`). The Backup & restore page builds
 * its create-dialog, restore tree, sensitive-data warnings and restore
 * report from this; it never carries its own copy (R-003 — the copy it
 * used to carry named `product_barcodes` and lacked nine sections, so the
 * default *New backup* was refused and UI backups omitted recipe steps;
 * finalisation 18-R2 / 18-R3).
 */
export interface BackupSection {
    key: string;
    label: string;
    /** Display grouping — "Core data" / "Optional". */
    category: string;
    /** Ticked by default in the create dialog. */
    default_on: boolean;
    /** Carries data Dora flags before writing it to disk (accounts,
     *  system settings, pricing history). */
    sensitive: boolean;
    /** Offered row-by-row in the restore tree; link/line tables ride
     *  along with their parents and are not pickable. */
    pickable: boolean;
}

/** One saved backup in the library (`GET /api/data/backups`). */
export interface BackupRow {
    backup_id: string;
    created_at: string;
    created_by_user_id: string | null;
    created_by_username: string | null;
    size_bytes: number;
    sections: string[];
    sha256: string;
    status: string;
    trigger_kind: string;
}

export interface RestoreSummary {
    created: Record<string, number>;
    skipped: Record<string, number>;
    warnings: string[];
}

export interface ImportTemplate {
    section: string;
    label: string;
    caption: string;
    headers: string[];
}

export interface SpreadsheetRowReport {
    row_number: number;
    status: 'created' | 'skipped_duplicate' | 'error';
    name: string;
    reason: string | null;
}

export interface SpreadsheetCommitResult {
    summary: { created: number; skipped: number; errors: number; halted: number };
    rows: SpreadsheetRowReport[];
}

/**
 * Admin data endpoints (`/api/data/*`): the backup library, inspect/restore,
 * and spreadsheet import. The two data pages used to call every one of these
 * with a raw `fetch` + hand-built URL + their own error reader (FU-716 /
 * finalisation 18-R7); through the client they get the request id, the
 * timeout policy and `toastCaption` like every other call.
 */
export default class DataApiService {
    private httpClient = new AxiosHttpClient();

    backupSectionsAsync = async (): Promise<BackupSection[]> => {
        const resp = await this.httpClient.get<{ sections: BackupSection[] }>(
            '/data/backup/sections',
        );
        return resp.sections;
    };

    listBackupsAsync = async (limit = 200): Promise<BackupRow[]> => {
        const page = await this.httpClient.get<Page<BackupRow>>(
            `/data/backups?limit=${limit}&sort=created_at:desc`,
        );
        return page.items;
    };

    createBackupAsync = async (sections: string[]): Promise<void> => {
        await this.httpClient.post<unknown, { sections: string[] }>('/data/backups', { sections });
    };

    downloadBackupAsync = async (backupId: string) =>
        await this.httpClient.getFile(`/data/backups/${encodeURIComponent(backupId)}/download`);

    restoreBackupAsync = async (backupId: string): Promise<RestoreSummary> =>
        await this.httpClient.post<RestoreSummary, Record<string, never>>(
            `/data/backups/${encodeURIComponent(backupId)}/restore`, {},
        );

    deleteBackupAsync = async (backupId: string): Promise<void> => {
        await this.httpClient.delete<void>(`/data/backups/${encodeURIComponent(backupId)}`);
    };

    inspectUploadAsync = async <TPreview>(uploadId: string): Promise<TPreview> =>
        await this.httpClient.post<TPreview, { upload_id: string }>('/data/backup/inspect', { upload_id: uploadId });

    restoreUploadAsync = async (body: {
        upload_id: string;
        selection: Record<string, string[]>;
        mode: string;
    }): Promise<RestoreSummary> =>
        await this.httpClient.post<RestoreSummary, typeof body>('/data/backup/restore', body);

    importTemplatesAsync = async (): Promise<ImportTemplate[]> => {
        const resp = await this.httpClient.get<{ sections: ImportTemplate[] }>('/data/import/templates');
        return resp.sections ?? [];
    };

    downloadImportTemplateAsync = async (section: string) =>
        await this.httpClient.getFile(`/data/import/templates/${encodeURIComponent(section)}.csv`);

    inspectSpreadsheetAsync = async <TInspect>(body: { upload_id: string; filename: string }): Promise<TInspect> =>
        await this.httpClient.post<TInspect, typeof body>('/data/import/spreadsheet/inspect', body);

    commitSpreadsheetAsync = async (body: {
        upload_id: string;
        filename: string;
        sheet: string;
        column_map: Record<string, string | null>;
        options: Record<string, unknown>;
    }): Promise<SpreadsheetCommitResult> =>
        await this.httpClient.post<SpreadsheetCommitResult, typeof body>('/data/import/spreadsheet/commit', body);
}
