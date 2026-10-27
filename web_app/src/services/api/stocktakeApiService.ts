import AxiosHttpClient from './axiosHttpClient';

/**
 * PROPOSAL_STOCKTAKE_MODE §7 — server-owned cadence bands (R-003 SoT).
 * The SPA renders these, never re-derives them. `cadence_band` is the
 * resolved band after global default + Auto + Low/Out + Essential; the
 * matching `cadence_days` (7/14/30) travels alongside for convenience.
 */
export type CadenceBand = 'weekly' | 'fortnightly' | 'monthly';

/** What the queue (`/stocktake/queue`) and a session row (`/stocktake/session`)
 *  share: one item, its band, and why it sits where it does (05-R36). */
export interface StocktakeItemBase {
    stock_item_id: string;
    name: string;
    stock_level_name: string | null;
    stock_location_name: string | null;
    cadence_band: CadenceBand;
    /** Whole days past the resolved band's window. Under Chunk 1's
     *  grace-period rule this is always ≥ 1 for anything in the
     *  queue (0-or-negative rows are filtered server-side). */
    overdue_days: number;
    /** Flagged essential. Drives whether the Stocktake button glows — see
     *  `essential_total`. */
    is_essential: boolean;
    /**
     * Chunk 5 / D-1 — why this item sits where it does.
     *
     *   `uncertain` — Dora has evidence but isn't sure. Checking tells us the
     *                 most, so these lead the queue, least-certain first.
     *   `overdue`   — no evidence. Falls back to most-overdue first.
     *   `confident` — Dora already worked this out; sinks to the bottom.
     *
     * Always `overdue` when the user has stock inference switched off.
     */
    check_rank: 'uncertain' | 'overdue' | 'confident';
    /** The belief's own band / confidence / wording, or null when there's no
     *  inference for this item. The runner shows `belief_reason` verbatim —
     *  server-owned copy (R-003), so the reason a row is first is the same
     *  sentence everywhere it appears. */
    belief_band: string | null;
    belief_confidence: 'high' | 'medium' | 'low' | null;
    belief_reason: string | null;
}

export interface StocktakeQueueItem extends StocktakeItemBase {
    cadence_days: number;
    last_checked_at: string | null;
}

export interface StocktakeQueueResponse {
    items: StocktakeQueueItem[];
    total: number;
    /**
     * How many of the overdue items are flagged **essential** — counted over
     * the whole overdue set, not the returned page.
     *
     * Owner call 2026-08-20: the Stocktake button glows again (D-14 had removed
     * it outright), but only when this is > 0. "Something is due a count" is
     * ambient; "something you said matters is due a count" is worth an
     * interruption. Read this rather than counting `items` — beyond `limit` the
     * page stops being representative, which is exactly the busy pantry where
     * the glow matters most.
     */
    essential_total: number;
    /**
     * Which engine ordered the list (Chunk 5 / D-1): `belief` when the user has
     * stock inference on, `cadence` otherwise. Read this rather than inferring
     * from the rows — with inference off every row is `overdue`, which is
     * indistinguishable from "inference on, nothing has evidence yet", and the
     * two deserve different explanations.
     */
    ranked_by: 'belief' | 'cadence';
}

/**
 * A Review or Walk row (Chunk 6 / D-4). One shape for both phases — what
 * differs between them is the *affordances*, not the data.
 */
export interface StocktakeSessionItem extends StocktakeItemBase {
    stock_level_id: string | null;
    /** Root-first path — `["Pantry", "Middle shelf", "Top shelf"]`. Owner
     *  feedback 2026-09-01: the walk is the moment you go and *find* the
     *  thing, and "Top shelf" alone doesn't say which shelf of what. Render
     *  through `formatLocation(…, 'full')`. Empty when the item has no
     *  location. */
    stock_location_breadcrumb: string[];
}

/** A Sweep row: what left rotation, when, and off the back of what. */
export interface StocktakeSweptItem {
    stock_item_id: string;
    name: string;
    stock_level_name: string | null;
    stock_location_name: string | null;
    stock_location_breadcrumb: string[];
    dropped_out_at: string;
    /** Shown to the user — "Dora's stopped tracking this" is only fair if you
     *  can see what it's based on. */
    last_activity_at: string;
}

/**
 * The three-phase session: **shrink → work → tidy** (D-4).
 *
 * `review` is Dora's confident set — agreeing is one tap, from a desk.
 * `walk` is what needs eyes on a shelf, least-certain first.
 * `sweep` is what dropped out of rotation since `last_session_at`.
 *
 * Any phase can be empty and is then skipped silently: an early-days household
 * has no confident items for months (high confidence needs ~3 logged
 * purchases), and a user with inference off gets no `review` at all by design.
 */
export interface StocktakeSessionResponse {
    review: StocktakeSessionItem[];
    walk: StocktakeSessionItem[];
    sweep: StocktakeSweptItem[];
    ranked_by: 'belief' | 'cadence';
    last_session_at: string | null;
}

export default class StocktakeApiService {
    private http = new AxiosHttpClient();

    queueAsync = async (limit = 50): Promise<StocktakeQueueResponse> =>
        await this.http.get<StocktakeQueueResponse>(`/stocktake/queue?limit=${limit}`);

    /** The runner's read. Separate from `queueAsync` because the overview polls
     *  that one on every page load and shouldn't pay for the Sweep pass or the
     *  belief wording — both endpoints share every rule underneath. */
    sessionAsync = async (): Promise<StocktakeSessionResponse> =>
        await this.http.get<StocktakeSessionResponse>('/stocktake/session');

    /** Moves the Sweep watermark to now. Called once, when the run reaches its
     *  summary — never per phase and never on abandon, because a watermark that
     *  passes a departure hides it for good. */
    completeSessionAsync = async (): Promise<{ last_session_at: string }> =>
        await this.http.post<{ last_session_at: string }, Record<string, never>>(
            '/stocktake/session/complete', {},
        );

    checkOneAsync = async (stockItemId: string): Promise<{ last_checked_at: string }> =>
        await this.http.post<{ last_checked_at: string }, Record<string, never>>(
            `/stock-items/${encodeURIComponent(stockItemId)}/check`, {},
        );

    /** PROPOSAL_STOCKTAKE_MODE §5 — Push (3-day snooze). Server sets a
     *  fixed 3-day `snoozed_until`; makes no truth claim about the
     *  stock, so `last_checked_at` is deliberately NOT bumped. */
    snoozeAsync = async (stockItemId: string): Promise<{ snoozed_until: string }> =>
        await this.http.post<{ snoozed_until: string }, Record<string, never>>(
            `/stock-items/${encodeURIComponent(stockItemId)}/snooze`, {},
        );

    bulkCheckAsync = async (ids: string[]): Promise<{ checked: number }> =>
        await this.http.post<{ checked: number }, { ids: string[] }>(
            '/stocktake/bulk-check', { ids },
        );
}
