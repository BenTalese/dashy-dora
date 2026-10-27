// @vitest-environment jsdom
/**
 * FU-833 — the four price payloads, mapped onto one chart.
 *
 * Worth pinning: the mapping *is* the behaviour that used to live inside
 * `PriceHistoryChart.vue` as `offersAsContext` + `hasOffers()`, and getting it
 * wrong is silent — a chart still draws, it just draws the wrong line or drops
 * a baseline. It is also pure, synchronous and low-churn, which is the bar the
 * lean testing stance sets.
 *
 * The two rules that are not obvious from the types:
 *   1. On `/price-history` offers lead, and your own observations appear **only**
 *      for a product with no offers at all — a per-unit observation series and a
 *      raw offer series can't honestly share one y-axis.
 *   2. The baseline is the median of *your* prices, so it rides with the
 *      observations and never with an offer line.
 *
 * jsdom, not node: the adapter formats the baseline label through the app's one
 * money authority (`formatMoney`), which reaches Quasar — a `window` away.
 */
import { describe, expect, it } from 'vitest';
import {
    productSeriesToChart,
    stockItemHistoryToChart,
} from 'src/composables/usePriceChartSeries';
import type {
    PriceHistorySeries,
    StockItemPriceHistory,
} from 'src/services/api/priceHistoryApiService';

function productSeries(over: Partial<PriceHistorySeries> = {}): PriceHistorySeries {
    return {
        product_id: 'p1',
        name: 'Choceur Dark 70%',
        store: 'Aldi',
        points: [],
        observation_points: [],
        your_prices: null,
        current: null,
        all_time_low: null,
        ...over,
    };
}

describe('productSeriesToChart', () => {
    it('draws offers as the series on the product page', () => {
        const [s] = productSeriesToChart([productSeries({
            points: [
                { date: '2026-08-01', unit_price: 3, list_price: 3, on_deal: false },
                { date: '2026-08-08', unit_price: 2.5, list_price: 3, on_deal: true },
            ],
        })]);
        expect(s!.points).toEqual([
            { date: '2026-08-01', value: 3, marked: false },
            { date: '2026-08-08', value: 2.5, marked: true },
        ]);
        expect(s!.contextPoints).toBeUndefined();
    });

    it('falls back to your own prices — and their baseline — when a product has no offers', () => {
        const [s] = productSeriesToChart([productSeries({
            points: [],
            observation_points: [{ date: '2026-08-02', unit_price: 4.2, store_name: 'Aldi' }],
            your_prices: {
                baseline: 4, baseline_unit: 'kg', current: 4.2,
                above_baseline: true, sample_count: 5,
            },
        })]);
        expect(s!.points).toEqual([{ date: '2026-08-02', value: 4.2 }]);
        expect(s!.baseline).toEqual({ value: 4, label: 'usually $4.00/kg' });
    });

    it('never draws the baseline against an offer line', () => {
        // The baseline is the median of the user's own prices; an offer series
        // is a different measurement, so pinning it under one would compare two
        // unlike things on one axis.
        const [s] = productSeriesToChart([productSeries({
            points: [{ date: '2026-08-01', unit_price: 3, list_price: 3, on_deal: false }],
            observation_points: [{ date: '2026-08-02', unit_price: 4.2, store_name: null }],
            your_prices: {
                baseline: 4, baseline_unit: 'kg', current: 4.2,
                above_baseline: true, sample_count: 5,
            },
        })]);
        expect(s!.points).toEqual([{ date: '2026-08-01', value: 3, marked: false }]);
        expect(s!.baseline).toBeNull();
    });

    it('inverts the priority in the union view: your prices lead, offers become context', () => {
        const [s] = productSeriesToChart([productSeries({
            points: [{ date: '2026-08-01', unit_price: 3, list_price: 3, on_deal: true }],
            observation_points: [{ date: '2026-08-02', unit_price: 4.2, store_name: null }],
            your_prices: {
                baseline: 4, baseline_unit: 'kg', current: 4.2,
                above_baseline: true, sample_count: 5,
            },
        })], { offersAsContext: true });
        expect(s!.points).toEqual([{ date: '2026-08-02', value: 4.2 }]);
        expect(s!.contextPoints).toEqual([{ date: '2026-08-01', value: 3, marked: true }]);
        expect(s!.baseline?.value).toBe(4);
    });

    it('drops points the server could not price or date', () => {
        const [s] = productSeriesToChart([productSeries({
            points: [
                { date: null, unit_price: 3, list_price: 3, on_deal: false },
                { date: '2026-08-08', unit_price: null, list_price: 3, on_deal: false },
            ],
        })]);
        expect(s!.points).toEqual([]);
    });
});

describe('stockItemHistoryToChart', () => {
    const history: StockItemPriceHistory = {
        stock_item_id: 'si1',
        name: 'Rolled Oats',
        display_unit: 'kg',
        baseline: 3.5,
        baseline_unit: 'kg',
        current: 4,
        above_baseline: true,
        sample_count: 4,
        points: [
            { observed_at: '2026-08-01', unit_price: 3.4, source: 'observation', store_name: 'Aldi' },
            { observed_at: '2026-08-05', unit_price: 3.9, source: 'offer', store_name: 'Coles' },
            { observed_at: '2026-08-09', unit_price: 4, source: 'observation', store_name: 'Aldi' },
        ],
    };

    it('leads with your observations and puts offers behind them', () => {
        const [s] = stockItemHistoryToChart(history);
        expect(s!.points.map((p) => p.value)).toEqual([3.4, 4]);
        expect(s!.contextPoints?.map((p) => p.value)).toEqual([3.9]);
        expect(s!.baseline).toEqual({ value: 3.5, label: 'usually $3.50/kg' });
    });

    it('omits the context line when there are no offers to draw', () => {
        const [s] = stockItemHistoryToChart({
            ...history,
            points: history.points.filter((p) => p.source === 'observation'),
        });
        expect(s!.contextPoints).toBeUndefined();
    });

    it('maps nothing when there is no history', () => {
        expect(stockItemHistoryToChart(null)).toEqual([]);
    });
});

