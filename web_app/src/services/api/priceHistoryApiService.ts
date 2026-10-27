import AxiosHttpClient from './axiosHttpClient';

export type PriceRange = '30d' | '90d' | '1y' | 'all';

export interface PriceHistoryPoint {
    date: string | null;
    unit_price: number | null;
    list_price: number | null;
    on_deal: boolean;
}

// the user's own observation points (per-unit, "your data").
// `on_deal`/`list_price` don't apply (an observation isn't an offer), so this
// is a lighter shape than PriceHistoryPoint.
export interface PriceObservationPoint {
    date: string | null;
    unit_price: number | null;
    store_name?: string | null;
}

// per-series baseline block (F-3). Server-derived (R-003);
// the chart renders the reference line + above-usual chip, never recomputes.
export interface SeriesYourPrices {
    baseline: number | null;
    baseline_unit: string | null;
    current: number | null;
    above_baseline: boolean;
    sample_count: number;
}

export interface PriceHistorySeries {
    product_id: string;
    name: string;
    store: string;
    points: PriceHistoryPoint[];
    /** FU-227 chunk 6 (H2) — the user's own price observations for this
     *  product, normalised per-unit. The chart renders them only when the
     *  product has no offer points (H2 fallback) on the per-product page, or
     *  always when `offersAsContext` (the bottom-sheet union view). */
    observation_points?: PriceObservationPoint[];
    /** FU-227 chunk 6 (F-3) — baseline + above-usual signal for the chart's
     *  reference line. Null when below MIN_SAMPLES / no observations. */
    your_prices?: SeriesYourPrices | null;
    current: {
        unit_price: number | null;
        list_price: number | null;
        deal_pct: number | null;
    } | null;
    all_time_low: { unit_price: number; date: string | null } | null;
}

// per-stock-item unioned series for the "Full history"
// bottom-sheet. Points are tagged by `source` and already scaled to
// `display_unit` server-side.
export interface StockItemPriceHistoryPoint {
    observed_at: string;
    unit_price: number;
    source: 'observation' | 'offer';
    store_name: string | null;
}

export interface StockItemPriceHistory {
    stock_item_id: string;
    name: string;
    display_unit: string | null;
    baseline: number | null;
    baseline_unit: string | null;
    current: number | null;
    above_baseline: boolean;
    sample_count: number;
    points: StockItemPriceHistoryPoint[];
}

export interface PriceAlert {
    price_alert_id: string;
    product_id: string;
    product_name: string;
    store_name: string;
    threshold_unit_price: number;
    created_at: string | null;
}

export default class PriceHistoryApiService {
    private http = new AxiosHttpClient();

    seriesAsync = async (
        productIds: string[], range: PriceRange = '90d',
    ): Promise<{ series: PriceHistorySeries[] }> => {
        const ids = productIds.map(encodeURIComponent).join(',');
        return await this.http.get<{ series: PriceHistorySeries[] }>(
            `/price-history?product_ids=${ids}&range=${range}`,
        );
    };

    createAlertAsync = async (
        productId: string, thresholdUnitPrice: number,
    ): Promise<{ price_alert_id: string }> =>
        await this.http.post<
            { price_alert_id: string },
            { product_id: string; threshold_unit_price: number }
        >('/price-history/alerts', {
            product_id: productId,
            threshold_unit_price: thresholdUnitPrice,
        });

    listAlertsAsync = async (): Promise<{ items: PriceAlert[] }> =>
        await this.http.get<{ items: PriceAlert[] }>('/price-history/alerts');

    deleteAlertAsync = async (alertId: string): Promise<void> =>
        await this.http.delete<void>(
            `/price-history/alerts/${encodeURIComponent(alertId)}`,
        );
}
