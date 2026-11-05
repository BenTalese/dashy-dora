import AxiosHttpClient from './axiosHttpClient';

export type ReportRange = '30d' | '90d' | '1y' | '2y' | '5y' | 'all';

// YoY only accepts bounded windows. Enforce at the type level
// so callers can't hand the endpoint a range=all it will reject.
export type YoYReportRange = Exclude<ReportRange, 'all'>;

export interface StoreSpendRow {
    store_id: string | null;
    store: string;
    /** The store's logo-derived colour, so every surface that draws this
     *  dataset paints a store the same colour (FU-814). Pass it to
     *  `storeColour(row.store, row.brand_colour)` — never hash the name into
     *  the chart ramp, which is how one store came out green on the shopping
     *  list and mauve in Reports. */
    brand_colour: string | null;
    spend: number;
    list_count: number;
}

export interface StoreSpendResponse {
    range: ReportRange;
    rows: StoreSpendRow[];
    /** Total across **every** row, server-computed (R-041). The dashboard shows
     *  only the top few stores, so it must not sum `rows` itself — that both
     *  moves a cross-collection aggregate into the browser and produces a total
     *  whose coverage the reader can't see. */
    total_spend: number;
    /** How many stores the total was built from, so a truncated list can say
     *  "top 3 of 5" rather than presenting a partial view as the whole. */
    store_count: number;
    /** Ticked lines that carried a price and made it into the total (R-041). */
    counted_lines: number;
    /** Ticked lines with no price at all, excluded from the money. Rendered as
     *  a coverage note — the report used to drop them without saying so. */
    unpriced_lines: number;
}

export interface MostBoughtRow {
    stock_item_id: string;
    name: string;
    appearances: number;
}

export interface MostBoughtResponse {
    range: ReportRange;
    rows: MostBoughtRow[];
}

/** One stock item whose own logged prices moved inside the range (chunk 4 /
 *  FU-703 D3). Every figure is per **canonical unit** and server-derived: the
 *  client never divides a total by a measure (R-003). */
export interface ItemPriceMoverRow {
    stock_item_id: string;
    name: string;
    /** The denominator both prices share — "L" / "kg" / "ea". */
    unit: string;
    first_price: number;
    last_price: number;
    delta: number;
    delta_pct: number;
    observation_count: number;
    first_observed_on: string;
    last_observed_on: string;
}

export interface ItemPriceMoversResponse {
    range: ReportRange;
    /** Biggest movement first, in either direction — a fall is as much news as
     *  a rise, so the card takes risers from the top and fallers from the
     *  bottom without re-sorting. */
    rows: ItemPriceMoverRow[];
    /** R-041 coverage. These describe the whole pantry, not the returned page:
     *  "3 movers" out of forty items means something different from "3 of 3". */
    items_with_movement: number;
    items_with_one_observation: number;
    items_with_mixed_units: number;
    /** Two readings, same price. An answer, but not a change — so it is counted
     *  here and kept out of `rows`. */
    items_unchanged: number;
}

export interface PriceDropRow {
    product_id: string;
    name: string;
    store_id: string | null;
    store_name: string;
    has_image: boolean;
    price_now: number;
    previous_low: number;
    drop_amount: number;
    drop_percent: number;
    linked_stock_item_id: string | null;
    linked_stock_item_name: string | null;
}

export interface PriceDropsResponse {
    rows: PriceDropRow[];
}

/** Spend, and how it compares with what the household usually pays (FU-831 /
 *  ADR-068). `savings_vs_usual_price` is negative when you paid more than
 *  usual; `counted` of `total` priced lines had a usual price to compare. */
export interface SavingsCapturedResponse {
    range: ReportRange;
    total_spent: number;
    savings_vs_usual_price: number;
    counted: number;
    total: number;
}

// culinary memory. Three new report shapes that back the new
// "Memory" section on /reports.
export interface MealsCookedTopRow {
    recipe_id: string | null;
    recipe_name: string;
    cook_count: number;
    meals_total: number;
}
export interface MealsCookedBucketPoint {
    date: string;   // ISO date at the start of the bucket
    cook_count: number;
    meals_total: number;
}
export interface MealsCookedResponse {
    range: ReportRange;
    cook_count: number;
    meals_total: number;
    /** Distinct recipes cooked in the range. A different fact from `cook_count`
     *  — "14 cooks, 9 different recipes" — and the one that sends you back to
     *  the cookbook (REPORTS_PAGE_REVIEW.md §3.8). */
    distinct_recipes: number;
    /** Repertoire, deliberately NOT range-scoped: these two are facts about the
     *  cookbook, measured over the last 365 days, so a 30-day view doesn't
     *  report that you've abandoned almost everything you own. */
    total_recipes: number;
    uncooked_recipes: number;
    top_recipes: MealsCookedTopRow[];
    timeline: MealsCookedBucketPoint[];
}

export interface SpendByCategoryRow {
    category: string;
    spent: number;
    item_count: number;
    share_pct: number;
}
export interface SpendByCategoryResponse {
    range: ReportRange;
    total_spent: number;
    rows: SpendByCategoryRow[];
}

export interface SpendYoYCategoryRow {
    category: string;
    current: number;
    previous: number;
    delta: number;
    /** null when previous == 0 — a new-category is undefined YoY, not
     *  +∞% or +100%. UI renders "new" in that case. */
    delta_pct: number | null;
}
export interface SpendYoYResponse {
    range: YoYReportRange;
    window_days: number;
    current_total: number;
    previous_total: number;
    delta: number;
    delta_pct: number | null;
    rows: SpendYoYCategoryRow[];
}

export interface RangeWindow {
    range: ReportRange;
    /** ISO date the window opens, or null for "all time" — there is no start
     *  date to name and the epoch would be a worse answer than none. */
    start: string | null;
    /** ISO date the window closes (today). */
    end: string;
    /** Length in days; null for "all time". Replaces the client-side copy of
     *  the server's range table (R-003) that used to exist purely to feed the
     *  waste endpoint, which takes days rather than a range token. */
    days: number | null;
}

export default class ReportsApiService {
    private httpClient = new AxiosHttpClient();

    /** The dates a range token resolves to. Page chrome, so it is ungated. */
    getRangeWindowAsync = (range: ReportRange) =>
        this.httpClient.get<RangeWindow>(`/reports/range-window?range=${range}`);

    getSpendByStoreAsync = (range: ReportRange) =>
        this.httpClient.get<StoreSpendResponse>(`/reports/spend-by-store?range=${range}`);

    getMostBoughtAsync = (range: ReportRange, limit = 10) =>
        this.httpClient.get<MostBoughtResponse>(`/reports/most-bought-items?range=${range}&limit=${limit}`);

    /** Omit `range` for all-time (the endpoint's default). */
    getSavingsCapturedAsync = (range: ReportRange) =>
        this.httpClient.get<SavingsCapturedResponse>(`/reports/savings-captured?range=${range}`);

    getPriceDropsAsync = (limit = 5) =>
        this.httpClient.get<PriceDropsResponse>(`/reports/price-drops?limit=${limit}`);

    // ── P8-09 memory ────────────────────────────────────────────────
    getMealsCookedAsync = (range: ReportRange, limit = 10) =>
        this.httpClient.get<MealsCookedResponse>(
            `/reports/meals-cooked?range=${range}&limit=${limit}`,
        );

    getSpendByCategoryAsync = (range: ReportRange) =>
        this.httpClient.get<SpendByCategoryResponse>(
            `/reports/spend-by-category?range=${range}`,
        );

    getSpendYearOverYearAsync = (range: YoYReportRange) =>
        this.httpClient.get<SpendYoYResponse>(
            `/reports/spend-year-over-year?range=${range}`,
        );

    /** "Which of my own items got more expensive?" — the everyday-user price
     *  report, built from stock-item observations rather than the product
     *  catalogue, so it works on an install that has never touched products. */
    getItemPriceMoversAsync = (range: ReportRange, limit = 8) =>
        this.httpClient.get<ItemPriceMoversResponse>(
            `/reports/item-price-movers?range=${range}&limit=${limit}`,
        );
}
