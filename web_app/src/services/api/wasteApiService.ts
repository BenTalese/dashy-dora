import AxiosHttpClient from './axiosHttpClient';

/**
 * C-waste — slim waste log. Capture is reason-only (no quantity/value/note).
 * The expiry-rescue feed (`GET /waste/rescue`) has no SPA reader: Dora's
 * `expiry_rescue` tool calls its handler server-side.
 */

export type WasteReason =
    | 'expired'
    | 'spoiled'
    | 'did_not_like'
    | 'overbought'
    | 'other';

export type LogWasteEventCommand = {
    stock_item_id: string;
    reason: WasteReason;
};

export type BulkLogWasteCommand = {
    stock_item_ids: string[];
    reason: WasteReason;
    /** Defaults to true server-side, matching the single-item row flow. */
    clear_expiry?: boolean;
};

export type BulkLoggedWasteEvent = {
    event_id: string;
    stock_item_id: string;
    /** The expiry this call cleared, echoed back so Undo can restore it. */
    previous_expiry_date: string | null;
};

export type BulkLogWasteResult = {
    events: BulkLoggedWasteEvent[];
    /** Ids that no longer exist — reported, not fatal. */
    missing_ids: string[];
};

export type BulkDeleteWasteCommand = {
    events: Array<{ event_id: string; restore_expiry_date: string | null }>;
};


export type MostWastedRow = {
    stock_item_id: string | null;
    stock_item_name: string;
    event_count: number;
    last_occurred_at: string | null;
};

export type MostRecentRow = {
    event_id: string;
    stock_item_id: string | null;
    stock_item_name: string;
    reason: WasteReason;
    occurred_at: string | null;
};

export type WasteInsights = {
    window_days: number;
    total_events: number;
    by_reason: Record<WasteReason, number>;
    most_wasted: MostWastedRow[];
    /** The same ranking per reason, for the report's reason filter. */
    most_wasted_by_reason: Record<WasteReason, MostWastedRow[]>;
    most_recent: MostRecentRow[];
};

export default class WasteApiService {
    private httpClient = new AxiosHttpClient();

    logEventAsync = async (
        command: LogWasteEventCommand,
    ): Promise<{ event_id: string }> =>
        await this.httpClient.post<{ event_id: string }, LogWasteEventCommand>(
            '/waste/events',
            command,
        );

    /** One round-trip for a whole bulk-bar selection. The server also clears
     *  each item's expiry (unless told not to) and echoes the old date back,
     *  which is what the single-item flow spent a second and third request
     *  per item doing. */
    logEventsBulkAsync = async (
        command: BulkLogWasteCommand,
    ): Promise<BulkLogWasteResult> =>
        await this.httpClient.post<BulkLogWasteResult, BulkLogWasteCommand>(
            '/waste/events/bulk',
            command,
        );

    /** Undo for the above. POST, not DELETE, because it carries a body. */
    deleteEventsBulkAsync = async (
        command: BulkDeleteWasteCommand,
    ): Promise<{ deleted_count: number; restored_count: number }> =>
        await this.httpClient.post<
            { deleted_count: number; restored_count: number },
            BulkDeleteWasteCommand
        >('/waste/events/bulk-delete', command);

    deleteEventAsync = async (eventId: string): Promise<void> =>
        await this.httpClient.delete<void>(`/waste/events/${eventId}`);

    getInsightsAsync = async (windowDays = 90): Promise<WasteInsights> =>
        await this.httpClient.get<WasteInsights>(
            `/waste/insights?window_days=${windowDays}`,
        );
}
