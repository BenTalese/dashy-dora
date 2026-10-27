<template>
    <!-- The card is deliberately not one big link: the low and out legend rows
         and donut segments deep-link to the *filtered* stock view
         (`?level_id=…`), which is the useful destination. The header's
         unfiltered "View →" went with every other card's header link on
         2026-09-08 (owner: *"you can just click the main menu buttons"*) — and
         the nav's Stock entry is precisely that unfiltered view, so nothing is
         lost but the duplication (FU-299's segment links are untouched). -->
    <!-- "My stock", not "Pantry" (owner, 2026-09-04). The app's noun for these
         things is *stock* everywhere else — the route is `/stock`, the entity is
         `StockItem`, the nav item says Stock — and this card was the last place
         calling them the pantry. -->
    <DashboardCard :icon="ICONS.inventory_2" title="My stock">
        <div class="dora-stock-body">
            <svg
                viewBox="0 0 36 36"
                class="dora-donut"
                :aria-label="`${total} stock items: ${inStock} in stock, ${low} low, ${out} out`"
            >
                <circle class="dora-donut-track" cx="18" cy="18" r="15.915" />
                <circle
                    v-for="(seg, i) in segments"
                    :key="seg.label"
                    cx="18"
                    cy="18"
                    r="15.915"
                    fill="none"
                    stroke-width="4"
                    :stroke="seg.colour"
                    :stroke-dasharray="`${seg.percent} ${100 - seg.percent}`"
                    :stroke-dashoffset="seg.offset"
                    :style="{ transitionDelay: `${i * 60}ms`, cursor: seg.link ? 'pointer' : undefined }"
                    :role="seg.link ? 'link' : undefined"
                    :tabindex="seg.link ? 0 : undefined"
                    :aria-label="seg.link ? `View ${seg.label} items` : undefined"
                    class="dora-donut-seg"
                    :class="{ 'dora-donut-seg--link': seg.link }"
                    @click="seg.link && emit('open', seg.link)"
                    @keydown.enter="seg.link && emit('open', seg.link)"
                    @keydown.space.prevent="seg.link && emit('open', seg.link)"
                />
                <text x="18" y="17" text-anchor="middle" class="dora-donut-big">
                    {{ total }}
                </text>
                <text x="18" y="22.5" text-anchor="middle" class="dora-donut-sub">items</text>
            </svg>
            <ul class="dora-legend">
                <li>
                    <span class="dora-dot dora-dot-ok"></span>
                    <span class="dora-legend-num">{{ inStock }}</span>
                    <span class="dora-legend-label">in stock</span>
                </li>
                <li>
                    <router-link class="dora-legend-link" :to="lowLink">
                        <span class="dora-dot dora-dot-warn"></span>
                        <span class="dora-legend-num">{{ low }}</span>
                        <span class="dora-legend-label">running low</span>
                    </router-link>
                </li>
                <li>
                    <router-link class="dora-legend-link" :to="outLink">
                        <span class="dora-dot dora-dot-bad"></span>
                        <span class="dora-legend-num">{{ out }}</span>
                        <span class="dora-legend-label">out</span>
                    </router-link>
                </li>
            </ul>
        </div>
    </DashboardCard>
</template>

<script lang="ts" setup>
    /**
     * The "My stock" donut: how the stock is split between in-stock, low
     * and out.
     *
     * The segment colours are resolved by the page through
     * `useThemePalette.paletteToken`, not here — an SVG `stroke` can't take a
     * CSS custom property through an attribute, so the value has to be read off
     * the document. That read used to be a one-shot `getComputedStyle` with a
     * comment claiming the donut recoloured on a theme switch; it didn't
     * (FU-824). It does now, because `paletteToken` carries a dependency on the
     * theme version.
     *
     * Extracted from `DashboardPage.vue` (FU-829).
     */
    import { ICONS } from 'src/style/icons';
    import DashboardCard from 'src/components/dashboard/DashboardCard.vue';

    export type DonutSegment = {
        label: string;
        percent: number;
        offset: number;
        colour: string;
        /** Filtered-stock route, or null for the residual "in stock" slice —
         *  which has no `?level_id` to filter by, so it isn't clickable. */
        link: string | null;
    };

    defineProps<{
        total: number;
        inStock: number;
        low: number;
        out: number;
        segments: DonutSegment[];
        lowLink: string;
        outLink: string;
    }>();

    const emit = defineEmits<{ (e: 'open', path: string): void }>();
</script>

<style scoped lang="scss">
    /* Moved with the card (R-027); off the page-local `--c-*` aliases, which
       resolve to nothing from a component (R-060). */
    /* Owner 2026-09-08 — *"Perhaps also make the my stock graph and text centred
       seeing as it still doesn't take up the whole card? Too much empty space."*

       The 09-04 pass already let the donut grow into the card (`clamp(132px,
       42%, 220px)`), which fixed the *small circle* half of the complaint but
       not the *left-hugging* half: donut + three short legend rows are narrower
       than a half-width desktop column, so the pair sat against the leading edge
       with the slack all on one side. `justify-content: center` splits the slack
       either side instead, which reads as a composition rather than as content
       that ran out.

       Deliberately NOT `flex: 1` on the legend to fill the row: that would
       stretch the gap between each count and its label to the card's width, so
       "12" and "in stock" would drift apart on a wide screen — worse than the
       empty space it removed. Centring the group is the change; the group's own
       internals stay content-sized. */
    .dora-stock-body {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: var(--space-5);
    }
    /* Owner 2026-09-04 — *"it looks a bit sparse on desktop width (very empty).
       Could we … make the graph that is there expand to take up the space."*
       The donut was pinned at 132px, so in a half-width column on a wide screen
       the card was a small circle, three short legend rows, and a lot of nothing.

       It now grows with the card and stops at 220px. Both bounds matter: the
       floor keeps the centre figure legible when the card is a phone-width
       column, and the ceiling stops a 1920px dashboard rendering a dinner
       plate. `flex-shrink` had to go with the fixed width — with it, the donut
       would refuse to give the legend room as the card narrows.

       R-078: sized from the *card's* width via flex, not from the viewport. A
       container-sized component never branches on the screen. */
    .dora-donut {
        flex: 0 1 auto;
        width: clamp(132px, 42%, 220px);
        height: auto;
        aspect-ratio: 1;
        min-width: 132px;
        transform: rotate(-90deg);
    }
    .dora-donut-track {
        fill: none;
        stroke: var(--surface-sunken);
        stroke-width: 4;
    }
    .dora-donut-seg {
        transition: stroke-dasharray var(--motion-slow) var(--motion-ease), stroke-dashoffset var(--motion-slow) var(--motion-ease), opacity var(--motion-fast) var(--motion-ease);
    }
    /* FU-299 — clickable low/out segments.
       This used to set `outline: none` on `:focus` with an opacity change as
       its only replacement — which A6 forbids outright ("never `outline: none`
       without a replacement"), and D-016 compounds, because an identical
       opacity shift makes hover and focus indistinguishable. Fixed in chunk 6:
       hover keeps the dim, focus gets a real ring. `:focus-visible` rather than
       `:focus` so a mouse click on a segment doesn't leave a ring behind. */
    .dora-donut-seg--link:hover {
        opacity: 0.8;
    }
    .dora-donut-seg--link:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    /* Legend rows deep-link to the filtered pantry view; low/out are the "act"
       segments — underline on hover, keep the row layout stable. */
    .dora-legend-link {
        display: contents;
        color: inherit;
        text-decoration: none;
    }
    .dora-legend-link:hover .dora-legend-label,
    .dora-legend-link:focus .dora-legend-label {
        text-decoration: underline;
    }
    /* SVG text inherits the parent's -90deg rotation; rotate the text nodes back
       so the centre label reads normally. */
    .dora-donut-big,
    .dora-donut-sub {
        transform: rotate(90deg);
        transform-origin: 18px 18px;
    }
    /* R-002 carve-out: SVG `font-size` inside a viewBox is in USER UNITS, not
       CSS px, so the `--font-size-*` rem ratios cannot express it — a token here
       would be wrong, not merely unconventional. The viewBox is 36 units wide
       rendered at 132px, so the scale factor is 132/36 ≈ 3.67: 7.5 units ≈ 27px
       effective. The effective size is what D-003 governs, and it is checked
       here in the comment because no tooling can see it. */
    .dora-donut-big {
        font-size: 7.5px;
        font-weight: 700;
        fill: var(--text-primary);
    }
    /* Was 3 units ≈ 11px effective — under D-003's 12px floor (§4.3 counted it
       among the eight). 3.4 units × 3.67 ≈ 12.5px, which clears it. Same
       user-units carve-out as `.dora-donut-big` above. */
    .dora-donut-sub {
        font-size: 3.4px;
        fill: var(--text-secondary);
        text-transform: lowercase;
        letter-spacing: 0.05em;
    }
    /* A flex column since the group above is centred: the three rows keep a
       common leading edge relative to each other (so the dots form a line)
       while the *pair* — donut + legend — centres as one unit. Without this the
       `ul` would fill the flex line and the rows would spread. */
    .dora-legend {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        font-size: calc(var(--font-size-sm) * 1rem);
    }
    .dora-legend li {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        padding: var(--space-1) 0;
    }

    .dora-dot {
        width: 9px;
        height: 9px;
        border-radius: var(--radius-pill);
        flex-shrink: 0;
    }
    .dora-dot-ok { background: var(--semantic-positive); }
    .dora-dot-warn { background: var(--semantic-warning); }
    .dora-dot-bad { background: var(--semantic-negative); }
    .dora-legend-num {
        font-weight: 600;
        min-width: 1.4em;
        text-align: right;
    }
    .dora-legend-label {
        color: var(--text-secondary);
    }

    @media (prefers-reduced-motion: reduce) {
        .dora-donut-seg {
            transition: none !important;
        }
    }
</style>
