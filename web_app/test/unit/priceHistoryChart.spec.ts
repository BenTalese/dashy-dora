// @vitest-environment jsdom
/**
 * FU-833 step 3 — the two things `PriceHistoryChart` gained when it became the
 * app's only chart: a legend, and a text alternative.
 *
 * The a11y half is the reason this is a test rather than a look: a chart with no
 * accessible name is *invisible* to a screen reader, and nothing on screen tells
 * you that. It was also unfixable while the page used ECharts on a canvas — the
 * whole argument for the swap — so it is worth pinning that the replacement
 * actually carries it.
 */
import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import PriceHistoryChart from 'src/components/PriceHistoryChart.vue';
import type { PriceChartSeries } from 'src/composables/usePriceChartSeries';

const global = {
    stubs: {
        'q-icon': { template: '<i class="q-icon" />' },
        'q-tooltip': { template: '<span />' },
    },
};

const OATS: PriceChartSeries = {
    key: 'si1', colourSlot: 0,
    name: 'Rolled Oats',
    points: [
        { date: '2026-08-01', value: 3.4 },
        { date: '2026-08-09', value: 4 },
    ],
    contextPoints: [{ date: '2026-08-05', value: 3.9 }],
    baseline: { value: 3.5, label: 'usually $3.50/kg' },
};

function mountChart(series: PriceChartSeries[], props: Record<string, unknown> = {}) {
    return mount(PriceHistoryChart, { props: { series, ...props }, global });
}

describe('PriceHistoryChart — text alternative', () => {
    it('names itself and describes each series', () => {
        const svg = mountChart([OATS]).find('svg');
        expect(svg.attributes('role')).toBe('img');
        expect(svg.attributes('aria-label')).toContain('Rolled Oats');
        // The description carries the range and where the series ended up —
        // deliberately not a point-by-point table, which a screen reader would
        // have to read aloud in full.
        const desc = svg.find('desc').text();
        expect(desc).toContain('3 prices');
        expect(desc).toContain('$3.40 to $4.00');
        expect(desc).toContain('latest $4.00');
    });

    it('says so when there is nothing to draw', () => {
        const chart = mountChart([{ key: 'x', name: 'Nothing', colourSlot: 0, points: [] }]);
        expect(chart.find('svg').attributes('aria-label')).toBe('Price chart, no data.');
        expect(chart.find('polyline').exists()).toBe(false);
    });

    it('lets the caller override the name, for a chart whose subject is off-canvas', () => {
        const chart = mountChart([OATS], { ariaLabel: 'Price history for Rolled Oats.' });
        expect(chart.find('svg').attributes('aria-label')).toBe('Price history for Rolled Oats.');
    });
});

describe('PriceHistoryChart — legend', () => {
    it('names the series, the context line and the baseline', () => {
        const items = mountChart([OATS], { legend: true, contextLabel: 'Store offers' })
            .findAll('.chart-legend li').map((li) => li.text());
        expect(items).toEqual(['Rolled Oats', 'Store offers', 'usually $3.50/kg']);
    });

    it('leaves out the context entry when no series has one', () => {
        const items = mountChart(
            [{ key: 'a', name: 'Oats', colourSlot: 0, points: [{ date: '2026-08-01', value: 3 }] }],
            { legend: true },
        ).findAll('.chart-legend li').map((li) => li.text());
        expect(items).toEqual(['Oats']);
    });

    it('stays off unless asked for — the chart is embedded in cards that title themselves', () => {
        expect(mountChart([OATS]).find('.chart-legend').exists()).toBe(false);
    });
});

describe('PriceHistoryChart — drawing', () => {
    it('draws one line per series plus its context line, and dots every point', () => {
        const chart = mountChart([OATS]);
        expect(chart.findAll('polyline')).toHaveLength(2);
        // Two own points get dots; the context line's single point is not a dot
        // unless it is marked (a deal).
        expect(chart.findAll('circle')).toHaveLength(2);
    });

    it('emphasises a marked point, so a deal reads differently from a reading', () => {
        const chart = mountChart([{
            key: 'a', colourSlot: 0,
            name: 'Oats',
            points: [
                { date: '2026-08-01', value: 3 },
                { date: '2026-08-02', value: 2, marked: true },
            ],
        }]);
        const radii = chart.findAll('circle').map((c) => c.attributes('r'));
        expect(radii).toEqual(['2.6', '3.4']);
    });

    it('ignores a series whose points have unparseable dates rather than drawing at x=0', () => {
        const chart = mountChart([{
            key: 'a', name: 'Oats', colourSlot: 0, points: [{ date: 'not-a-date', value: 3 }],
        }]);
        expect(chart.findAll('circle')).toHaveLength(0);
    });
});

describe('PriceHistoryChart: y-axis unit (FU-705)', () => {
    const line = (key: string, unit?: string): PriceChartSeries => ({
        key, name: key, colourSlot: 0,
        points: [{ date: '2026-08-01', value: 3 }],
        ...(unit ? { unit } : {}),
    });
    const unitLabel = (series: PriceChartSeries[]) =>
        mountChart(series).findAll('text').map((t) => t.text())
            .find((t) => t.startsWith('Price ') || t.startsWith('Mixed units'));

    it('names the one unit every series shares', () => {
        expect(unitLabel([line('a', 'kg'), line('b', 'kg')])).toBe('Price per kg');
        expect(unitLabel([line('a', 'pack')])).toBe('Price per pack');
        expect(unitLabel([line('a', 'ea')])).toBe('Price each');
    });

    it('says so when two scales share the axis', () => {
        expect(unitLabel([line('a', 'pack'), line('b', 'kg')]))
            .toBe('Mixed units (per pack, per kg)');
    });

    it('claims nothing when a series does not state its unit', () => {
        expect(unitLabel([line('a', 'kg'), line('b')])).toBeUndefined();
    });
});

describe('PriceHistoryChart: baselines (FU-705)', () => {
    const withBaseline = (key: string, colourSlot: number, value: number): PriceChartSeries => ({
        key, name: key, colourSlot,
        points: [{ date: '2026-08-01', value: 3 }, { date: '2026-08-09', value: 6 }],
        baseline: { value, label: `usually ${value}` },
    });

    it('keeps a lone baseline as the muted guide', () => {
        const line = mountChart([OATS]).find('g.baseline line');
        expect(line.attributes('style')).toBeUndefined();
        expect(line.attributes('stroke-dasharray')).toBe('4,3');
    });

    it('gives several baselines a dash each and keeps their labels apart', () => {
        // Three baselines within a few cents: drawn naively, the labels stack.
        const chart = mountChart([
            withBaseline('a', 0, 4.0), withBaseline('b', 1, 4.01), withBaseline('c', 2, 4.02),
        ]);
        const groups = chart.findAll('g.baseline');
        const dashes = groups.map((g) => g.find('line').attributes('stroke-dasharray'));
        expect(new Set(dashes).size).toBe(3);
        expect(groups.every((g) => g.find('line').attributes('style')?.includes('stroke'))).toBe(true);
        const ys = groups.map((g) => Number(g.find('text').attributes('y'))).sort((p, q) => p - q);
        for (let i = 1; i < ys.length; i += 1) {
            expect(ys[i]! - ys[i - 1]!).toBeGreaterThanOrEqual(11);
        }
    });
});
