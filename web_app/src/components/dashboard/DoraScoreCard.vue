<template>
    <!-- dashboard's kitchen-health card. Reads the composite +
         per-component breakdown from `useDoraScore()`; renders each
         component in its own box.

         The `InfoTip` beside the title went on 2026-09-08 (*"I don't think we
         need the info chip for this widget?"*) — and he is right for a reason
         worth writing down: every sentence that tip carried is now *shown*.
         The ring names its window, each signal box states its own reason in
         plain words, and a dormant box says "not counted" on its face. A tip
         explaining a card that explains itself is a card that doesn't. -->
    <DashboardCard :icon="ICONS.favorite" title="Kitchen health">
        <div v-if="loading && !score" class="dora-text-muted text-caption">
            Loading…
        </div>

        <div v-else-if="!score" class="dora-text-muted text-caption">
            Kitchen health will appear here once you've been using
            Dora for a bit.
        </div>

        <div v-else-if="score.composite === null" class="dora-text-muted text-caption">
            Kitchen health appears once you've tracked a few stock
            items.
        </div>

        <template v-else>
            <!-- Owner 2026-09-08 — *"Can make the top area of the card look
                 more pretty/interesting/satisfying. Maybe a hollow circle
                 design or something else?"* A hollow ring it is, and it earns
                 its place beyond decoration: the old head was a bare numeral
                 beside the words "out of 100", which asked the reader to hold
                 a scale in their head. A ring *is* the scale — 72 out of 100
                 is 72% of the way round, readable before you read the digits.

                 Same SVG idiom as `StockDonutCard`'s donut, deliberately: one
                 `stroke-dasharray` arc on a 15.915r circle (circumference ≈
                 100, so the array value is literally the percentage), rotated
                 -90deg so it starts at twelve o'clock. Unlike that donut this
                 one takes no runtime palette read — the arc is a single
                 traffic-light class, so plain CSS `stroke` works and there is
                 no `paletteToken` dependency to keep honest (FU-824). -->
            <div class="dora-score-hero">
                <div class="dora-score-hero__dial">
                    <svg
                        viewBox="0 0 36 36"
                        class="dora-score-ring"
                        role="img"
                        :aria-label="`Kitchen health ${score.composite} out of 100, last ${score.window_days} days`"
                    >
                        <circle class="dora-score-ring__track" cx="18" cy="18" r="15.915" />
                        <circle
                            class="dora-score-ring__arc"
                            :class="barClass(score.composite)"
                            cx="18"
                            cy="18"
                            r="15.915"
                            :stroke-dasharray="`${score.composite} ${100 - score.composite}`"
                        />
                    </svg>
                    <!-- Just the number (owner, 2026-09-27: "we know it's out of
                         100"). The ring already is the scale. -->
                    <div class="dora-score-hero__figure" aria-hidden="true">
                        <span class="dora-score-hero__number">{{ score.composite }}</span>
                    </div>
                </div>
                <div class="dora-score-hero__caption">
                    <!-- The trend moved off the card header and under the ring.
                         It was the `#action` slot's only occupant, and with
                         every other card's header now bare, one card carrying a
                         floating chip up there read as leftover chrome. It also
                         belongs to the number, not to the card. -->
                    <span
                        v-if="score.trend_direction && score.trend_direction !== 'flat'"
                        class="dora-score-trend"
                        :class="`dora-score-trend--${score.trend_direction}`"
                        :aria-label="trendAriaLabel"
                    >
                        <q-icon :name="trendIcon" size="16px" />
                        <span class="dora-score-trend__delta">
                            {{ score.trend_delta! > 0 ? '+' : '' }}{{ score.trend_delta }}
                        </span>
                    </span>
                    <span class="dora-score-hero__window">
                        last {{ score.window_days }} days
                    </span>
                </div>
            </div>

            <ul class="dora-score-components">
                <!-- Owner 2026-09-08 — *"Put each signal in its own card/box to
                     visually separate it better."* They were five stacked
                     label/bar/reason triplets separated only by a gap, so at a
                     glance the card was one fifteen-line block. Each is a
                     sunken box now, which is also what finally makes a dormant
                     signal legible: dimming a row inside a run of rows just
                     looked like a rendering glitch. -->
                <li
                    v-for="c in score.components"
                    :key="c.key"
                    class="dora-score-component"
                    :class="{ 'dora-score-component--dormant': c.score === null }"
                >
                    <div class="dora-score-component__head">
                        <span class="dora-score-component__label">{{ c.label }}</span>
                        <!-- Owner 2026-09-08 — *"'No budget set' I feel should
                             render same as auto meal reconciliation."* Those two
                             ARE the same state (a dormant signal, excluded from
                             the mean) and they rendered differently for one
                             reason: budget alone carried a "Set a budget →"
                             action. With the row links gone the two are
                             identical by construction — which is why this says
                             "not counted" rather than a bare em-dash. The dash
                             looked like a missing value; the words say it is
                             deliberately outside the average, which is the
                             honest claim (P3, and the reason `_score_budget`
                             returns None rather than 0). -->
                        <span
                            class="dora-score-component__score"
                            :class="{ 'dora-score-component__score--dormant': c.score === null }"
                        >
                            {{ c.score === null ? 'not counted' : c.score }}
                        </span>
                    </div>
                    <div
                        v-if="c.score !== null"
                        class="dora-score-component__bar"
                        :aria-label="`${c.label} score ${c.score} out of 100`"
                    >
                        <div
                            class="dora-score-component__bar-fill"
                            :style="{ width: `${c.score}%` }"
                            :class="barClass(c.score)"
                        />
                    </div>
                    <!-- The action links went with every other card's links
                         (owner, 2026-09-08: *"Remove the quick links to things
                         on each row (makes it too busy looking)"*). Five rows
                         each ending in a green "Expiring items →" / "Reconcile
                         meals →" was five calls to action on a card whose job is
                         to *report*, and the reason text — the thing you'd read
                         to decide whether to act — was competing with them for
                         the same line. The whole `actionLinkFor` map is deleted;
                         the routes it named are all one tap away in the nav,
                         which is the batch's standing argument. -->
                    <div class="dora-score-component__reason">{{ c.reason }}</div>
                </li>
            </ul>
        </template>
    </DashboardCard>
</template>

<script setup lang="ts">
    /**
     * P8-08 — Dora Score dashboard card.
     *
     * The component is pure presentation over `useDoraScore()`:
     * loading, empty (brand-new install, no data), zero-scoring, and
     * the full breakdown all live here. The composable owns caching
     * (5-min stale window) and fetch orchestration; this file only
     * renders what it hands back.
     *
     * Owner review 2026-09-04 swapped two components (see
     * `DoraScoreComponentKey` server-side for the reasoning). The 2026-09-08
     * batch then reworked the card's *presentation* on five items — a hollow
     * ring instead of a bare numeral, one box per signal, no InfoTip, no
     * per-row action links, and dormant signals rendering identically whatever
     * made them dormant. Each is annotated at its site in the template above.
     *
     * **This card links nowhere.** The plan-adherence signal that stood in for
     * the old "Reconcile past meals" card was cut on 2026-09-27;
     * `/meal-plans/reconcile` is reachable from the meal-plans header nudge.
     */
    import { computed } from 'vue';
    import DashboardCard from 'src/components/dashboard/DashboardCard.vue';
    import { ICONS } from 'src/style/icons';
    import { useDoraScore } from 'src/composables/useDoraScore';

    const { doraScore: score, loading } = useDoraScore();

    const trendIcon = computed(() => {
        if (score.value?.trend_direction === 'up') return ICONS.trending_up;
        if (score.value?.trend_direction === 'down') return ICONS.trending_down;
        return ICONS.trending_flat;
    });

    const trendAriaLabel = computed(() => {
        const s = score.value;
        if (!s || s.trend_delta === null) return '';
        return s.trend_delta > 0
            ? `Up ${s.trend_delta} points from a week ago`
            : `Down ${Math.abs(s.trend_delta)} points from a week ago`;
    });

    function barClass(v: number): string {
        // Traffic-light banding for the ring and the mini-bar fills — the
        // composite number is honest and the shape is a story cue.
        // Server owns the score; the client just paints the tone.
        if (v >= 80) return 'dora-score--good';
        if (v >= 50) return 'dora-score--fair';
        return 'dora-score--weak';
    }

    /* `actionLinkFor` and the `useMoneyEnabled` guard it carried are deleted
       (owner, 2026-09-08 — no row links). The guard was FU-823/R-058
       belt-and-braces against a "Set a budget →" link leaking onto a money-off
       install; with no link there is nothing to leak. The **server** gate is
       the one that mattered and it is untouched: `compute_score` omits the
       budget component entirely when money features are off, so a money-off
       install renders four boxes, not a dormant fifth. */
</script>

<style scoped>
    /* R-060 sweep (2026-09-02): every colour in this block used to reference a
       `--dora-*` custom property — `--dora-text`, `--dora-primary`,
       `--dora-positive(-bg)`, `--dora-negative(-bg)`, `--dora-muted-bg`,
       `--dora-text-muted` — and **none of them has ever been declared** (only
       `--dora-disc-bg` and `--dora-halo*` exist). So the card painted from its
       hard-coded hex fallbacks in all ten themes, light and dark: the "fair" bar
       and the action links came out yellow where the app's action colour is
       green, and the bar track was a black wash that disappeared on a dark
       surface. `--dora-text` had no fallback at all, so that declaration was
       invalid and the score's headline number silently inherited.
       Now on the real A1 tokens. This is also the honest close-out of feedback
       D2 ("dark mode not working"), which Phase 0 of the dashboard rebuild
       marked done. */

    /* ── The ring (owner 2026-09-08) ──────────────────────────────────────
       Three layers stacked in the same grid cell: the SVG, the figure, and the
       caption below it. A grid rather than absolute positioning so the ring's
       intrinsic size sets the block's height and the figure centres in it
       without magic offsets. */
    /* Centred in the card (owner, 2026-09-27), with the trend and window on one
       line under the ring rather than in a column beside it. */
    .dora-score-hero {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--space-2);
        margin-bottom: var(--space-4);
    }
    .dora-score-hero__dial {
        display: grid;
        place-items: center;
    }
    .dora-score-ring {
        grid-area: 1 / 1;
        /* Bounded like the donut's: big enough that the figure inside stays
           legible in a phone-width column, small enough that a 1920px dashboard
           doesn't render a dinner plate. Fixed rather than `clamp`ed on a
           percentage — this one shares its cell with the figure, so a growing
           ring would need the figure to grow with it. */
        width: 92px;
        height: 92px;
        transform: rotate(-90deg);
    }
    .dora-score-ring__track {
        fill: none;
        /* A1: an inset well sits on `--surface-sunken`, not a black wash. */
        stroke: var(--surface-sunken);
        stroke-width: 3;
    }
    .dora-score-ring__arc {
        fill: none;
        stroke-width: 3;
        stroke-linecap: round;
        transition: stroke-dasharray var(--motion-slow) ease-out;
    }
    /* The figure sits in the ring's own cell, centred over it. `pointer-events`
       off so it never eats a tap meant for anything underneath. */
    .dora-score-hero__figure {
        grid-area: 1 / 1;
        pointer-events: none;
    }
    .dora-score-hero__number {
        /* A2's ladder tops out at `--font-size-3xl` (30px). */
        font-size: var(--font-size-3xl);
        font-weight: 600;
        line-height: 1;
        color: var(--text-primary);
    }
    .dora-score-hero__caption {
        display: flex;
        align-items: center;
        gap: var(--space-2);
    }
    .dora-score-hero__window {
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
    }

    .dora-score-trend {
        display: inline-flex;
        align-items: center;
        gap: var(--space-1);
        padding: var(--space-1) var(--space-2);
        border-radius: var(--radius-pill);
        font-size: var(--font-size-xs);
        font-weight: 500;
    }
    /* A1 soft-token rule: a `-soft` token is a background only; the text on it
       takes the full-strength semantic token. */
    .dora-score-trend--up {
        background: var(--semantic-positive-soft);
        color: var(--semantic-positive);
    }
    .dora-score-trend--down {
        background: var(--semantic-negative-soft);
        color: var(--semantic-negative);
    }

    /* ── One box per signal (owner 2026-09-08) ───────────────────────────── */
    .dora-score-components {
        list-style: none;
        padding: 0;
        margin: 0;
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
    }
    .dora-score-component {
        padding: var(--space-2) var(--space-3);
        /* D-017 — a box nested in a card is `--radius-md`; A1 — a nested well
           sits on `--surface-sunken` with a hairline, not on a shadow (a
           five-deep stack of elevated boxes inside one card is noise). */
        border-radius: var(--radius-md);
        background: var(--surface-sunken);
        border: 1px solid var(--border-default);
    }
    /* A dormant signal is a *stated* fact ("not counted"), so it no longer
       leans on opacity to say so — 0.55 on a box that is now bordered read as
       disabled, and one of these (budget with no target set) is something the
       reader might well want to act on. Flat ground, no border, and the words
       carry it. D-002: never a contrast reduction as the only signal. */
    .dora-score-component--dormant {
        background: transparent;
        border-style: dashed;
    }

    .dora-score-component__head {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: var(--space-2);
        margin-bottom: var(--space-1);
    }
    .dora-score-component__label {
        font-weight: 600;
    }
    .dora-score-component__score {
        font-variant-numeric: tabular-nums;
        font-weight: 600;
        flex-shrink: 0;
    }
    .dora-score-component__score--dormant {
        /* Words, not a number, so it takes the caption scale and the readable
           secondary token rather than sitting at the score's weight. */
        font-size: var(--font-size-xs);
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--text-secondary);
    }

    .dora-score-component__bar {
        height: 4px;
        border-radius: var(--radius-pill);
        /* A1: an inset well sits on `--surface-sunken`. Inside a box that is
           itself sunken, the track needs the hairline colour to stay visible. */
        background: var(--border-default);
        overflow: hidden;
    }
    .dora-score-component__bar-fill {
        height: 100%;
        border-radius: var(--radius-pill);
        transition: width var(--motion-slow) ease-out;
    }
    /* Traffic-light banding straight off A1's semantic table, which names these
       exact roles: positive = "good scores", warning = "fair scores". One set of
       classes for the ring and the bars — they mean the same thing, so a future
       retune moves both (they were two parallel sets before). */
    .dora-score--good {
        background: var(--semantic-positive);
        stroke: var(--semantic-positive);
    }
    .dora-score--fair {
        background: var(--semantic-warning);
        stroke: var(--semantic-warning);
    }
    .dora-score--weak {
        background: var(--semantic-negative);
        stroke: var(--semantic-negative);
    }

    .dora-score-component__reason {
        margin-top: var(--space-1);
        font-size: var(--font-size-xs);
        /* Was `--text-muted` while it shared a line with a green action link.
           With the link gone the reason is the only sentence in the box and the
           thing you actually read, so it takes the readable secondary token
           (D-002). */
        color: var(--text-secondary);
    }

    @media (prefers-reduced-motion: reduce) {
        .dora-score-ring__arc,
        .dora-score-component__bar-fill {
            transition: none !important;
        }
    }
</style>
