<template>
    <div
        ref="hostRef"
        class="chart-host"
        @pointerdown="onMove"
        @pointermove="onMove"
        @pointerleave="onLeave"
    >
        <svg
            :width="width"
            :height="height"
            :viewBox="`0 0 ${width} ${height}`"
            class="chart-svg"
            role="img"
            :aria-label="ariaLabel"
        >
            <!-- No preserveAspectRatio: the viewBox is the measured size, so the
                 SVG is never scaled, and the pointer maths below relies on that
                 (one CSS pixel is one chart unit). FU-705. -->
            <!-- The text alternative. An SVG can carry one; the ECharts canvas
                 this component replaced could not, which is what made §4.9's
                 "five charts with no accessible alternative" unfixable while it
                 stood (FU-833 step 3). `<title>` is the accessible name,
                 `<desc>` the detail — one line per series, with the range and
                 the latest value, which is what the chart is *for*. -->
            <title>{{ ariaLabel }}</title>
            <desc v-if="seriesSummaries.length > 0">{{ seriesSummaries.join(' ') }}</desc>

            <!-- Horizontal gridlines + y-axis labels -->
            <g class="gridlines">
                <line
                    v-for="(tick, i) in yTicks"
                    :key="`gl-${i}`"
                    :x1="padding.left"
                    :x2="width - padding.right"
                    :y1="tick.y"
                    :y2="tick.y"
                    class="chart-gridline"
                />
                <text
                    v-for="(tick, i) in yTicks"
                    :key="`gt-${i}`"
                    :x="padding.left - 6"
                    :y="tick.y + 3"
                    font-size="10"
                    class="chart-axis-label"
                    text-anchor="end"
                >
                    {{ formatMoney(tick.value) }}
                </text>
                <!-- What the axis measures (FU-705). -->
                <text
                    v-if="axisUnitLabel"
                    x="4"
                    y="10"
                    font-size="10"
                    class="chart-axis-label"
                    text-anchor="start"
                >
                    {{ axisUnitLabel }}
                </text>
            </g>

            <!-- X axis date labels (first / mid / last) -->
            <g v-if="xLabels.length" class="x-labels">
                <text
                    v-for="(lbl, i) in xLabels"
                    :key="`xl-${i}`"
                    :x="lbl.x"
                    :y="height - 4"
                    font-size="10"
                    class="chart-axis-label"
                    text-anchor="middle"
                >
                    {{ lbl.label }}
                </text>
            </g>

            <!-- One group per series: its own line and an optional subordinate
                 context line for the same subject. -->
            <g v-for="(s, i) in renderableSeries" :key="s.key">
                <!-- Context line — the same subject from a lesser source (store
                     offers under your own logged prices). Dashed + faint, and
                     deliberately the *same* hue: it is not a second series. -->
                <polyline
                    v-if="s.contextPath"
                    :points="s.contextPath"
                    fill="none"
                    :stroke="seriesColour(s.colourSlot)"
                    stroke-width="1.4"
                    stroke-dasharray="5,3"
                    opacity="0.5"
                />
                <circle
                    v-for="(point, j) in s.contextMarkers"
                    :key="`cm-${i}-${j}`"
                    :cx="point.x"
                    :cy="point.y"
                    r="3"
                    :fill="seriesColour(s.colourSlot)"
                    opacity="0.5"
                />

                <!-- The series' own line. -->
                <polyline
                    v-if="s.path"
                    :points="s.path"
                    fill="none"
                    :stroke="seriesColour(s.colourSlot)"
                    stroke-width="2"
                />
                <circle
                    v-for="(point, j) in s.dots"
                    :key="`o-${i}-${j}`"
                    :cx="point.x"
                    :cy="point.y"
                    :r="point.marked ? 3.4 : 2.6"
                    :fill="seriesColour(s.colourSlot)"
                />

            </g>

            <!-- Baseline reference lines (F-3), "usually $X". Their own group,
                 because placing the labels is a question about all of them at
                 once (FU-705). Inline style, not attributes: the class's
                 stroke would beat a presentation attribute. -->
            <g v-for="b in placedBaselines" :key="`bl-${b.key}`" class="baseline">
                <line
                    :x1="padding.left"
                    :x2="width - padding.right"
                    :y1="b.y"
                    :y2="b.y"
                    class="chart-baseline"
                    :stroke-dasharray="b.dash"
                    :style="b.colour ? { stroke: b.colour } : undefined"
                />
                <text
                    :x="width - padding.right"
                    :y="b.labelY"
                    font-size="10"
                    class="chart-baseline-label"
                    text-anchor="end"
                    :style="b.colour ? { fill: b.colour } : undefined"
                >
                    {{ b.label }}
                </text>
            </g>

            <!-- Hover crosshair -->
            <g v-if="hover">
                <line
                    :x1="hover.x"
                    :x2="hover.x"
                    :y1="padding.top"
                    :y2="height - padding.bottom"
                    class="chart-crosshair"
                    stroke-dasharray="3,2"
                />
            </g>
        </svg>

        <!-- Legend. Lived in the callers before — the bottom sheet hand-rolled
             one above the chart while `/price-history` and Reports had none at
             all, so two of the three consumers couldn't tell you which line was
             which (FU-833 step 3). It belongs to the thing that assigns the
             colours. -->
        <ul v-if="legend && renderableSeries.length > 0" class="chart-legend">
            <li v-for="s in renderableSeries" :key="`lg-${s.key}`">
                <span class="chart-legend__line" :style="{ background: seriesColour(s.colourSlot) }" />
                {{ s.name }}
            </li>
            <li v-if="hasContext">
                <span class="chart-legend__line chart-legend__line--dashed" />
                {{ contextLabel }}
            </li>
            <li v-for="b in placedBaselines" :key="`lb-${b.key}`">
                <!-- A real dashed line, so each entry carries its baseline's
                     own dash as well as its colour. -->
                <svg class="chart-legend__line" viewBox="0 0 14 3" aria-hidden="true">
                    <line
                        x1="0"
                        x2="14"
                        y1="1.5"
                        y2="1.5"
                        class="chart-legend__baseline"
                        :stroke-dasharray="b.dash"
                        :style="b.colour ? { stroke: b.colour } : undefined"
                    />
                </svg>
                {{ b.label }}
            </li>
        </ul>

        <!-- Hover tooltip card -->
        <div
            v-if="hover"
            class="chart-tooltip"
            :style="{ left: `${tooltipLeft}px`, top: `${tooltipTop}px` }"
        >
            <div class="chart-tooltip-date">{{ hover.dateLabel }}</div>
            <div
                v-for="s in renderableSeries"
                :key="`t-${s.key}`"
                class="chart-tooltip-row"
            >
                <span class="chart-tooltip-swatch" :style="{ background: seriesColour(s.colourSlot) }" />
                <span class="chart-tooltip-name">{{ s.name }}</span>
                <span class="chart-tooltip-price">
                    {{ hover.bySeries[s.key]?.value !== undefined
                        && hover.bySeries[s.key]?.value !== null
                        ? formatMoney(hover.bySeries[s.key]!.value!)
                        : '–' }}
                </span>
                <q-icon
                    v-if="hover.bySeries[s.key]?.marked"
                    :name="ICONS.local_offer"
                    size="12px"
                    color="positive"
                    class="q-ml-xs"
                />
            </div>
        </div>

        <div v-if="renderableSeries.length === 0" class="chart-empty">
            {{ emptyLine }}
        </div>
    </div>
</template>

<script lang="ts" setup>
    /**
     * The app's price chart — inline SVG, no charting library.
     *
     * ## What changed (FU-833)
     *
     * This drew product price history and nothing else; it now draws every price
     * series in the app, and ECharts is gone from `package.json` because of it.
     * Two things made that a small change rather than a rewrite: the drawing code
     * was already general (multi-series polylines, y-ticks, x-labels, hover
     * crosshair), and the *interpretation* of a payload moved out to
     * `usePriceChartSeries.ts`, so this component no longer knows what an offer,
     * an observation or a product is. It takes lines and draws them.
     *
     * What it gained while being adopted, because the owner's decision on FU-812
     * made the a11y half non-negotiable: a **legend** (two of three consumers
     * had none, and the third hand-rolled one above the chart), and a **text
     * alternative** — `role="img"` with a generated `aria-label` plus a `<desc>`
     * naming each series' range and latest value. That last part is only
     * possible at all because this is SVG: the canvas it replaced was opaque to
     * assistive tech, which is why §4.9's finding had no fix while ECharts
     * stood.
     *
     * ## FU-705
     *
     * Pointer events, so a finger reads it too; a y-axis unit label taken from
     * the units the series state; and baselines that stay apart when there is
     * more than one (own colour and dash each, labels spread).
     */
    import { computed, ref } from 'vue';
    import { ICONS } from 'src/style/icons';
    import { seriesColour } from 'src/composables/useThemePalette';
    import { formatDate as formatLocaleDate } from 'src/composables/useDateFormat';
    import { formatMoney } from 'src/composables/useMoney';
    import type {
        PriceChartPoint, PriceChartSeries,
    } from 'src/composables/usePriceChartSeries';

    const props = defineProps<{
        series: PriceChartSeries[];
        width?: number;
        height?: number;
        /** Render the built-in legend under the plot. */
        legend?: boolean;
        /** Names the dashed subordinate line when any series has one. */
        contextLabel?: string;
        /** What to say when there is nothing to draw. The empty state is the
         *  caller's, because only the caller knows what the reader should do
         *  about it (B9). */
        emptyLine?: string;
        /** Overrides the generated accessible name. */
        ariaLabel?: string;
    }>();

    const width = computed(() => props.width ?? 720);
    const height = computed(() => props.height ?? 320);
    const legend = computed(() => props.legend ?? false);
    const contextLabel = computed(() => props.contextLabel ?? 'Store offers');
    const emptyLine = computed(
        () => props.emptyLine ?? 'Nothing to chart yet.',
    );
    // The unit label sits above the top tick, so the plot drops to make room
    // for it only when there is one.
    const padding = computed(() => ({
        top: axisUnitLabel.value ? 26 : 12, right: 16, bottom: 22, left: 48,
    }));

    // ── Y-axis unit (FU-705) ────────────────────────────────────────────
    /** "per kg", "per pack", "each". */
    function pricedPer(unit: string): string {
        if (unit === 'ea') return 'each';
        return `per ${unit}`;
    }
    /** What the y-axis measures, from the units the series state. One unit
     *  names it; different units say so, because two scales are sharing one
     *  axis and the reader should know; a series that states none means the
     *  chart can't vouch for the axis, so it claims nothing. */
    const axisUnitLabel = computed<string | null>(() => {
        const series = plottable.value;
        if (series.length === 0 || series.some((s) => !s.unit)) return null;
        const units = [...new Set(series.map((s) => s.unit!))];
        if (units.length === 1) return `Price ${pricedPer(units[0]!)}`;
        return `Mixed units (${units.map(pricedPer).join(', ')})`;
    });

    interface PlottedPoint { x: number; y: number; marked?: boolean }
    interface RenderableSeries {
        key: string;
        name: string;
        colourSlot: number;
        path: string;
        dots: PlottedPoint[];
        contextPath: string;
        contextMarkers: PlottedPoint[];
        baselineY: number | null;
        baselineLabel: string | null;
    }

    /** Every series with at least one point. A series the caller passed but
     *  which has no data contributes nothing to the axes and isn't drawn,
     *  legended or announced. */
    const plottable = computed(
        () => props.series.filter(
            (s) => s.points.length > 0 || (s.contextPoints?.length ?? 0) > 0,
        ),
    );

    /** Every point a series draws, own line and context line together — the
     *  shape the axes and the hover lookup both want. */
    function pointsOf(s: PriceChartSeries): PriceChartPoint[] {
        return [...s.points, ...(s.contextPoints ?? [])];
    }

    // Chart-space bounds across every drawn line and baseline. Both lines of a
    // series are always in the same unit (the server normalises before it
    // unions them), so they can share one axis.
    const valueBounds = computed(() => {
        const all: number[] = [];
        for (const s of plottable.value) {
            for (const p of pointsOf(s)) all.push(p.value);
            if (s.baseline != null) all.push(s.baseline.value);
        }
        if (all.length === 0) return null;
        const min = Math.min(...all);
        const max = Math.max(...all);
        const span = max - min;
        // Pad the y-axis ~5% so the top/bottom polylines don't graze the
        // chart edges; minimum span 0.5 so a perfectly-flat history still
        // looks reasonable.
        const padded = Math.max(0.5, span * 1.1);
        const centre = (min + max) / 2;
        return {
            min: Math.max(0, centre - padded / 2),
            max: centre + padded / 2,
        };
    });

    const timeBounds = computed(() => {
        const all: number[] = [];
        for (const s of plottable.value) {
            for (const p of pointsOf(s)) {
                const t = new Date(p.date).getTime();
                if (!Number.isNaN(t)) all.push(t);
            }
        }
        if (all.length === 0) return null;
        return { min: Math.min(...all), max: Math.max(...all) };
    });

    function projectX(timestamp: number): number {
        const tb = timeBounds.value;
        if (!tb) return padding.value.left;
        const innerW = width.value - padding.value.left - padding.value.right;
        if (tb.max === tb.min) return padding.value.left + innerW / 2;
        return padding.value.left + ((timestamp - tb.min) / (tb.max - tb.min)) * innerW;
    }
    function projectY(value: number): number {
        const vb = valueBounds.value;
        if (!vb) return padding.value.top;
        const innerH = height.value - padding.value.top - padding.value.bottom;
        if (vb.max === vb.min) return padding.value.top + innerH / 2;
        return padding.value.top + innerH - ((value - vb.min) / (vb.max - vb.min)) * innerH;
    }

    /** Project one line's points, dropping any with an unparseable date. */
    function project(points: PriceChartPoint[]): PlottedPoint[] {
        const out: PlottedPoint[] = [];
        for (const p of points) {
            const t = new Date(p.date).getTime();
            if (Number.isNaN(t)) continue;
            out.push({
                x: projectX(t),
                y: projectY(p.value),
                ...(p.marked ? { marked: true } : {}),
            });
        }
        return out;
    }
    const toPath = (points: PlottedPoint[]) =>
        points.map((p) => `${p.x},${p.y}`).join(' ');

    const renderableSeries = computed<RenderableSeries[]>(() =>
        plottable.value.map((s) => {
            const own = project(s.points);
            const context = project(s.contextPoints ?? []);
            return {
                key: s.key,
                name: s.name,
                colourSlot: s.colourSlot,
                path: toPath(own),
                dots: own,
                contextPath: toPath(context),
                contextMarkers: context.filter((p) => p.marked),
                baselineY: s.baseline != null ? projectY(s.baseline.value) : null,
                baselineLabel: s.baseline?.label ?? null,
            };
        }),
    );

    const hasContext = computed(
        () => renderableSeries.value.some((s) => s.contextPath.length > 0),
    );
    // ── Baselines (FU-705) ──────────────────────────────────────────────
    // One baseline stays the muted guide it always was. Several (the product
    // page, one per product with no offers) each take their series' colour and
    // a dash of their own, so the shape tells them apart as well as the hue
    // (D-001), and their labels are spread so none sits on another.
    const BASELINE_DASHES = ['4,3', '8,3', '2,2', '8,3,2,3', '1,3', '6,2'];
    const BASELINE_LABEL_GAP = 11;   // 10px labels, plus a pixel
    interface PlacedBaseline {
        key: string;
        y: number;
        labelY: number;
        label: string;
        /** Null keeps the muted guide style from the stylesheet. */
        colour: string | null;
        dash: string;
    }
    const placedBaselines = computed<PlacedBaseline[]>(() => {
        const withBaseline = renderableSeries.value.filter((s) => s.baselineY !== null);
        const many = withBaseline.length > 1;
        const placed: PlacedBaseline[] = withBaseline.map((s) => ({
            key: s.key,
            y: s.baselineY!,
            labelY: s.baselineY! - 4,
            label: s.baselineLabel ?? '',
            colour: many ? seriesColour(s.colourSlot) : null,
            dash: many
                ? BASELINE_DASHES[s.colourSlot % BASELINE_DASHES.length]!
                : BASELINE_DASHES[0]!,
        }));
        // Each label wants to sit just above its line. Walk them top to bottom
        // pushing each clear of the one above, then bottom to top pulling any
        // that ran off the plot back up.
        const top = padding.value.top + 8;
        const bottom = height.value - padding.value.bottom - 2;
        const byY = [...placed].sort((a, b) => a.y - b.y);
        let above = -Infinity;
        for (const b of byY) {
            b.labelY = Math.max(b.labelY, above + BASELINE_LABEL_GAP, top);
            above = b.labelY;
        }
        let below = Infinity;
        for (const b of [...byY].reverse()) {
            b.labelY = Math.min(b.labelY, below - BASELINE_LABEL_GAP, bottom);
            below = b.labelY;
        }
        return placed;
    });

    // ── Text alternative ────────────────────────────────────────────────
    /** One sentence per series: how many points, the range, and where it ended
     *  up. Deliberately not a point-by-point table — a screen reader reading 90
     *  daily prices aloud is worse than no alternative at all. */
    const seriesSummaries = computed(() => plottable.value.map((s) => {
        const values = pointsOf(s).map((p) => p.value);
        if (values.length === 0) return `${s.name}: no prices.`;
        const latest = s.points.at(-1)?.value ?? values.at(-1)!;
        return `${s.name}: ${values.length} price${values.length === 1 ? '' : 's'}, `
            + `${formatMoney(Math.min(...values))} to ${formatMoney(Math.max(...values))}, `
            + `latest ${formatMoney(latest)}.`;
    }));
    const ariaLabel = computed(() => {
        if (props.ariaLabel) return props.ariaLabel;
        if (plottable.value.length === 0) return 'Price chart, no data.';
        const names = plottable.value.map((s) => s.name).join(', ');
        return `Price history over time for ${names}.`;
    });

    // ── Y ticks: 4 evenly spaced over the visible range ─────────────────
    const yTicks = computed(() => {
        const vb = valueBounds.value;
        if (!vb) return [];
        const ticks: Array<{ y: number; value: number }> = [];
        for (let i = 0; i <= 4; i += 1) {
            const v = vb.min + (vb.max - vb.min) * (i / 4);
            ticks.push({ y: projectY(v), value: v });
        }
        return ticks;
    });

    const xLabels = computed(() => {
        const tb = timeBounds.value;
        if (!tb) return [];
        const fmt = (ms: number) => formatLocaleDate(ms, {
            month: 'short', day: 'numeric',
        });
        const mid = (tb.min + tb.max) / 2;
        return [
            { x: projectX(tb.min), label: fmt(tb.min) },
            { x: projectX(mid), label: fmt(mid) },
            { x: projectX(tb.max), label: fmt(tb.max) },
        ];
    });

    // ── Hover crosshair ────────────────────────────────────────────────
    interface HoverState {
        x: number;
        dateLabel: string;
        bySeries: Record<string, { value: number | null; marked: boolean }>;
    }
    const hostRef = ref<HTMLElement | null>(null);
    const hover = ref<HoverState | null>(null);

    // Pointer events, so a finger reads the chart too (FU-705): a tap or a
    // sideways drag moves the crosshair, and vertical drags still scroll the
    // page (`touch-action: pan-y` below).
    function onMove(event: PointerEvent) {
        if (!hostRef.value) return;
        const tb = timeBounds.value;
        if (!tb) return;
        const bounds = hostRef.value.getBoundingClientRect();
        const localX = event.clientX - bounds.left;
        const innerW = width.value - padding.value.left - padding.value.right;
        const ratio = Math.max(0, Math.min(1, (localX - padding.value.left) / innerW));
        const targetTime = tb.min + ratio * (tb.max - tb.min);

        const bySeries: HoverState['bySeries'] = {};
        for (const s of plottable.value) {
            // Nearest point per series, across its own line and its context
            // line — whichever actually has a reading near the cursor.
            let best: { dt: number; value: number; marked: boolean } | null = null;
            for (const p of pointsOf(s)) {
                const t = new Date(p.date).getTime();
                if (Number.isNaN(t)) continue;
                const dt = Math.abs(t - targetTime);
                if (best === null || dt < best.dt) {
                    best = { dt, value: p.value, marked: p.marked === true };
                }
            }
            bySeries[s.key] = best
                ? { value: best.value, marked: best.marked }
                : { value: null, marked: false };
        }
        hover.value = {
            x: projectX(targetTime),
            dateLabel: formatLocaleDate(targetTime),
            bySeries,
        };
    }
    // A finger lifting fires pointerleave at once; the reading stays until the
    // next tap so it can actually be read. A mouse leaving clears it.
    function onLeave(event: PointerEvent) {
        if (event.pointerType === 'mouse') hover.value = null;
    }

    // Position the tooltip so it never falls off the chart edges.
    const tooltipLeft = computed(() => {
        if (!hover.value) return 0;
        const half = 140;   // approximate tooltip width / 2
        const x = hover.value.x;
        if (x < padding.value.left + half) return padding.value.left;
        if (x > width.value - padding.value.right - half) {
            return width.value - padding.value.right - half * 2;
        }
        return x - half;
    });
    const tooltipTop = computed(() => padding.value.top + 4);
</script>

<style scoped lang="scss">
    .chart-host { position: relative; touch-action: pan-y; }
    .chart-svg { display: block; }
    .chart-gridline { stroke: var(--divider); }
    .chart-axis-label { fill: var(--text-muted); }
    .chart-crosshair { stroke: var(--border-strong); }
    /* FU-227 chunk 6 — baseline reference line ("usually $X"). Muted so it
       reads as a guide behind the data lines, not another series. */
    .chart-baseline { stroke: var(--text-muted); stroke-width: 1; opacity: 0.7; }
    .chart-baseline-label { fill: var(--text-muted); font-variant-numeric: tabular-nums; }
    .chart-legend {
        list-style: none;
        margin: var(--space-2) 0 0;
        padding: 0;
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-1) var(--space-4);
        font-size: var(--font-size-xs);
        color: var(--text-secondary);

        li {
            display: flex;
            align-items: center;
            gap: var(--space-2);
        }
    }
    .chart-legend__line {
        width: 14px;
        height: 3px;
        border-radius: var(--radius-xs);
        flex: 0 0 auto;
    }
    /* The dashed entries carry the same distinction the lines do: a repeating
       gradient reads as a dashed rule at 14px, where a border-style dash
       doesn't (D-001 — the shape is the channel, not just the colour). */
    .chart-legend__line--dashed {
        background: repeating-linear-gradient(
            to right,
            currentColor 0 4px,
            transparent 4px 7px
        );
        color: var(--text-secondary);
    }
    .chart-legend__baseline { stroke: var(--text-muted); stroke-width: 2; }
    .chart-tooltip {
        position: absolute;
        background: var(--surface-component);
        /* Its own ink, from the same theme as its ground: inherited text read
           dark-on-dark in the dark themes (FU-708 PH7). */
        color: var(--text-primary);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
        padding: var(--space-2) var(--space-3);
        font-size: var(--font-size-xs);
        pointer-events: none;
        box-shadow: 0 2px 8px var(--overlay-active);
        min-width: 200px;
    }
    .chart-tooltip-date {
        font-weight: 600;
        margin-bottom: var(--space-1);
        color: var(--text-secondary);
    }
    .chart-tooltip-row {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        line-height: 1.4;
    }
    .chart-tooltip-swatch {
        width: 10px;
        height: 10px;
        border-radius: var(--radius-xs);
        display: inline-block;
    }
    .chart-tooltip-name { flex: 1; }
    .chart-tooltip-price { font-variant-numeric: tabular-nums; }
    .chart-empty {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--text-muted);
        pointer-events: none;
    }
</style>
