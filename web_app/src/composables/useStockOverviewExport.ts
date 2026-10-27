/**
 * Stock-overview (install-wide) export. Sibling to the per-entity
 * composables — no id, just CSV + print-view of every stock item grouped
 * by location.
 */
import { Notify } from 'quasar';
import AxiosHttpClient from 'src/services/api/axiosHttpClient';
import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
import { describeQrFailure, openQrSheetAsync } from 'src/composables/useQrLabels';
import { openPrintDocument } from 'src/composables/usePrintDocument';
import { triggerSave } from 'src/services/files/downloadHelpers';

const http = new AxiosHttpClient();

export function useStockOverviewExport() {

    /** C-1 Chunk 1 / L67 — when `ids` is provided, the server filters the
     *  export to that set so CSV mirrors the on-screen filtered list. An
     *  empty array intentionally exports zero rows (matches what the
     *  filter shows); pass `undefined` to export everything. */
    async function downloadCsv(ids?: string[]): Promise<void> {
        try {
            const idsParam =
                ids !== undefined
                    ? `&ids=${encodeURIComponent(ids.join(','))}`
                    : '';
            const { blob, filename } = await http.getFile(`/stock-items/export?format=csv${idsParam}`);
            triggerSave(blob, filename ?? 'stock-overview.csv');
        } catch (err) {
            Notify.create({
                type: 'negative',
                message: "Couldn't export the stock overview.",
                caption: toastCaption(err),
            });
        }
    }

    /** C-1 Chunk 1 / L67 — print-view honours the same `ids` filter as
     *  the CSV export. Pass `undefined` to print everything. */
    function openPrintView(ids?: string[]): void {
        const idsParam =
            ids !== undefined
                ? `?ids=${encodeURIComponent(ids.join(','))}`
                : '';
        // FU-682 / R-045: fetched through the client, not `window.open(baseUrl…)`.
        openPrintDocument(`/stock-items/print-view${idsParam}`, 'Stock');
    }

    // Stays sync-entry so the click's gesture reaches `window.open` (R-046);
    // the failure is caught rather than dropped, because the most likely one is
    // a blocked pop-up, and a print button that does nothing at all is the
    // worst version of that.
    function openQrSheet(ids: string[]): void {
        if (ids.length === 0) return;
        openQrSheetAsync({ layout: 'a4-21up', ids }).catch((err: unknown) => {
            Notify.create({
                type: 'negative',
                message: describeQrFailure(err),
            });
        });
    }

    return { downloadCsv, openPrintView, openQrSheet };
}

