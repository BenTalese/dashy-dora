/**
 * The one place a price payload becomes something `PriceHistoryChart` can draw.
 *
 * ## Why this file exists (FU-833)
 *
 * `PriceHistoryChart.vue` used to take `PriceHistorySeries[]` — the *product*
 * price-history DTO — and carry the interpretation of it inside the drawing
 * code: an `offersAsContext` flag, an `hasOffers()` fallback deciding whether
 * observations were drawn at all, and a `your_prices` block it reached into for
 * the baseline. That was fine while one endpoint fed it. It now has three
 * callers, two of which have nothing to do with products:
 *
 *   - `/price-history` (product offers, up to 5 series)
 *   - the stock item's "Full history" sheet (your observations ∪ offers)
 *   - Reports' **Item price movers** card (your own observations, one item)
 *
 * So the chart now takes a neutral shape (`PriceChartSeries`) and every payload
 * is mapped to it here — one module, three adapters, R-001. The chart draws; this
 * decides what "primary", "context" and "baseline" mean for a given payload,
 * which is a question about the *data*, not about the pixels.
 *
 * Nothing here computes a domain fact: baselines, per-unit normalisation and
 * date ordering all arrive server-side already (R-003). These functions only
 * reshape.
 */
import { formatMoney } from 'src/composables/useMoney';
import type {
    PriceHistorySeries,
    StockItemPriceHistory,
} from 'src/services/api/priceHistoryApiService';

/** One plotted point. `marked` draws an emphasised dot — a deal, in practice. */
export interface PriceChartPoint {
    date: string;
    value: number;
    marked?: boolean;
}

/**
 * One line on the chart, plus the optional furniture that belongs to it.
 *
 * `points` is the series' own data and is drawn solid with dots.
 * `contextPoints` is a *subordinate* second line for the same subject — drawn
 * dashed and faint — for the case where two sources answer the same question at
 * different authority: your own logged prices (primary) against the store's
 * advertised offers (context). It is not a second series; it shares the colour.
 */
export interface PriceChartSeries {
    key: string;
    name: string;
    /** The series' place in the caller's own list, which picks its colour
     *  (`seriesColour`). Stamped here rather than read from the chart's loop
     *  index: the chart drops series with no points, and the page's chips and
     *  cards must not shift onto a neighbour's colour when it does (FU-846). */
    colourSlot: number;
    points: PriceChartPoint[];
    contextPoints?: PriceChartPoint[];
    /** Dashed reference line + its own label ("usually $4.20/kg"). */
    baseline?: { value: number; label: string } | null;
    /** What one value on the primary line is the price of: `'pack'` for a
     *  shelf price, or the measure ("kg", "L", "ea") of a per-unit price. It
     *  labels the y-axis (FU-705). Left out when the payload doesn't say, and
     *  then the chart claims no unit rather than guess one. */
    unit?: string;
}

/** The unit field, only when there is one to state. */
function unitOf(unit: string | null | undefined): { unit?: string } {
    return unit ? { unit } : {};
}

/** "usually $4.20/kg" — the baseline's label, formatted once, here. */
function baselineLabel(value: number, unit: string | null | undefined): string {
    return `usually ${formatMoney(value)}${unit ? `/${unit}` : ''}`;
}

/**
 * Product price history → chart series.
 *
 * Two modes, and the branch is the interesting part. On `/price-history` the
 * offers *are* the data, so they render primary and the user's own observations
 * only appear when a product has no offers at all — the H2 fallback, which
 * exists because a per-unit observation series and a raw offer series can't
 * share one y-axis honestly. In the union view the priority inverts: your own
 * prices lead and offers fall behind them as context.
 *
 * The baseline rides with the observations, never with the offers: it is the
 * median of *your* prices, so drawing it against an offer line would compare
 * two different things on one axis.
 */
export function productSeriesToChart(
    series: PriceHistorySeries[],
    options: { offersAsContext?: boolean } = {},
): PriceChartSeries[] {
    const offersAsContext = options.offersAsContext ?? false;
    return series.map((s, colourSlot) => {
        const offers: PriceChartPoint[] = [];
        for (const p of s.points) {
            if (p.date === null || p.price === null) continue;
            offers.push({ date: p.date, value: p.price, marked: p.on_deal });
        }
        const observations: PriceChartPoint[] = [];
        for (const p of s.observation_points ?? []) {
            if (p.date === null || p.unit_price === null) continue;
            observations.push({ date: p.date, value: p.unit_price });
        }

        const showOwnData = offersAsContext || offers.length === 0;
        const ownLeads = showOwnData && observations.length > 0;
        const baseline = s.your_prices?.baseline;
        return {
            key: s.product_id,
            name: s.name,
            colourSlot,
            points: ownLeads ? observations : offers,
            ...(offersAsContext && observations.length > 0 && offers.length > 0
                ? { contextPoints: offers }
                : {}),
            baseline: showOwnData && baseline != null
                ? { value: baseline, label: baselineLabel(baseline, s.your_prices?.baseline_unit) }
                : null,
            // Offers are pack prices (FU-911). Your own prices are per unit,
            // in the unit the server quotes the observation series in.
            ...(ownLeads
                ? unitOf(s.observation_unit ?? s.your_prices?.baseline_unit)
                : offers.length > 0 ? { unit: 'pack' } : {}),
        };
    });
}

/**
 * A stock item's unioned history → one chart series.
 *
 * The server hands back a single date-sorted list tagged by `source`, every
 * point already normalised to the item's canonical unit, so both lines are
 * guaranteed to share a y-axis. Your observations lead; offers are context.
 */
export function stockItemHistoryToChart(
    history: StockItemPriceHistory | null,
): PriceChartSeries[] {
    if (!history) return [];
    const own: PriceChartPoint[] = [];
    const offers: PriceChartPoint[] = [];
    for (const p of history.points) {
        (p.source === 'observation' ? own : offers).push({
            date: p.observed_at,
            value: p.unit_price,
        });
    }
    return [{
        key: history.stock_item_id,
        name: history.name,
        colourSlot: 0,
        points: own,
        ...(offers.length > 0 ? { contextPoints: offers } : {}),
        baseline: history.baseline != null
            ? {
                value: history.baseline,
                label: baselineLabel(history.baseline, history.baseline_unit),
            }
            : null,
        // Every point arrives scaled to `display_unit` (both sources).
        ...unitOf(history.display_unit ?? history.baseline_unit),
    }];
}

