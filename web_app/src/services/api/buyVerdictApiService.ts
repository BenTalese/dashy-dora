import AxiosHttpClient from './axiosHttpClient';

/** P8-05 — one axis-worth of reasoning behind a buy verdict. See
 *  `PROPOSAL_BUY_VERDICT_ORACLE.md` §2.1 for the full signal table. */
export interface BuyVerdictReason {
    axis: 'price' | 'need' | 'waste' | 'plan';
    signal: string;
    label: string;
    detail?: string | null;
    /** Price-axis reasons carry their two amounts as raw numbers instead of a
     *  `detail` string — the server never formats currency (D-006), so the
     *  detail line is composed here through `formatMoney` and honours the
     *  install's currency + locale. Null on every non-price reason. */
    amount_last?: number | null;
    amount_usual?: number | null;
}

/** The verdict's suggested next tap. The mutation itself uses existing
 *  endpoints (cart button flow, stock-level PATCH); the server just
 *  emits the intent + label so the UI stays honest about the reasoning
 *  and the action side-by-side. */
export interface BuyVerdictAction {
    kind:
        | 'add_to_list'
        | 'skip'
        | 'mark_stocked'
        | 'remove_from_list'
        | 'none';
    label: string;
}

/** The transparency payload — what data the composer reasoned from.
 *  Powers the "why?" tooltip (Charter P7 preview/explain). */
export interface BuyVerdictDataUsed {
    price_samples: number;
    price_average: number | null;
    price_last: number | null;
    price_last_at: string | null;               // ISO date
    days_since_last_purchase: number | null;
    average_days_between_purchase: number | null;
    waste_events_last_12mo: number;
    purchases_last_12mo: number;
    stock_level_band: 'out' | 'low' | 'stocked' | 'unknown';
}

/** P8-06 — the time-boxed "when" attached to a `wait` verdict. Populated
 *  server-side only when the composer landed on `wait` and `_wait_hint`
 *  found a confident cycle (thin/erratic/overdue history → `null`). The
 *  reason string is the human explanation; `until` is the machine date. */
export interface BuyVerdictWaitHint {
    until: string;      // ISO date (yyyy-mm-dd)
    reason: string;
    /** Days from the household's today to `until` (server-counted). */
    days_until: number;
}

export interface BuyVerdict {
    verdict: 'buy' | 'wait' | 'skip' | 'unsure';
    /** How good the evidence is — NOT how much you should care. */
    confidence: 'high' | 'medium' | 'low';
    /** How much you should care, 0-3. Graded from the item's Essential flag
     *  against its stock band, then modulated by price and waste. Drives the
     *  card's headline wording. */
    strength: number;
    reasons: BuyVerdictReason[];
    one_tap_action: BuyVerdictAction;
    data_used: BuyVerdictDataUsed;
    // populated only on `wait` verdicts when a confident cycle
    // is detected; `null` otherwise.
    wait_hint: BuyVerdictWaitHint | null;
}

export default class BuyVerdictApiService {
    private httpClient = new AxiosHttpClient();

    /** Ask the oracle. Server composes over the user's own data only —
     *  no external calls, no crowd baselines. Returns quickly (~1 KB
     *  payload); the SPA still caches per-item to avoid re-asking on
     *  every render pass. */
    getAsync = async (stockItemId: string): Promise<BuyVerdict> =>
        await this.httpClient.get<BuyVerdict>(
            `/stock-items/${encodeURIComponent(stockItemId)}/buy-verdict`,
        );

    /** B6 — every verdict for one shopping list's lines, in one round-trip.
     *  A 40-line list asking per line meant 40 requests, each re-walking the
     *  same tables for a single item. Keyed by stock-item id; lines with no
     *  stock item behind them are simply absent. */
    getForListAsync = async (
        shoppingListId: string,
    ): Promise<Record<string, BuyVerdict>> => {
        const response = await this.httpClient.get<{
            verdicts: Record<string, BuyVerdict>;
        }>(`/shopping-lists/${encodeURIComponent(shoppingListId)}/buy-verdicts`);
        return response.verdicts ?? {};
    };
}
