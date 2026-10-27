<template>
    <!--
        DR-2 / D-013 — the row-state legend. Stock rows speak a colour/edge
        language; D-013 requires that language be decodable in-UI (before this
        existed, the dimmed row in particular read as a rendering bug —
        FU-578 #33/#44).

        Chunk 4 (D-8 §"After (4)") shrank what there is to decode from nine
        channels to four, and this file is the honest measure of that: it used
        to explain two attention tiers, three cart-button verdict rings, a
        belief ring and a pulsing level box. All of those are gone — not
        re-described, gone — so what's left is the level, one three-band row
        treatment, the essential edge, and the dashed "might be wrong" marker.
        If this file ever grows back to that size, the row encoding has got
        too dense again; that's the signal the plan asked for.

        The level swatches are DERIVED, not hand-drawn: we iterate the
        household's actual level rows (so a renamed "Out of stock" → "None
        left" shows its real name) and colour each via the same
        `colourForSequence` authority + `bg-*` / `dora-bg-neutral` classes the
        row's level button uses (R-003) — the legend cannot drift from the
        rows it explains.
    -->
    <div class="stock-row-legend">
        <div class="stock-row-legend__title row items-center no-wrap">
            <q-icon :name="ICONS.help_outline" size="16px" class="q-mr-xs dora-text-muted" />
            What the row colours mean
        </div>

        <div class="stock-row-legend__grid">
            <!-- 1. The level box — one per real level row, escalating
                 green → amber → red (D-001), plus its two edge states. -->
            <div class="stock-row-legend__section-label">The level box</div>
            <div
                v-for="level in sortedLevels"
                :key="level.stock_level_id"
                class="stock-row-legend__item row items-center no-wrap"
            >
                <span
                    class="stock-row-legend__swatch stock-row-legend__swatch--square"
                    :class="swatchClass(level.sequence)"
                    aria-hidden="true"
                />
                <span class="stock-row-legend__text">{{ level.name }}</span>
            </div>
            <div class="stock-row-legend__item row items-center no-wrap">
                <span
                    class="stock-row-legend__swatch stock-row-legend__swatch--square stock-row-legend__swatch--unset"
                    aria-hidden="true"
                />
                <span class="stock-row-legend__text">Level not set</span>
            </div>
            <!-- D-5: ONE marker for "this number might be wrong", whichever
                 reason fired. The reason itself is words, in the picker. -->
            <div class="stock-row-legend__item row items-center no-wrap">
                <span
                    class="stock-row-legend__swatch stock-row-legend__swatch--square stock-row-legend__swatch--uncertain"
                    aria-hidden="true"
                />
                <span class="stock-row-legend__text">
                    Dashed ring: this level may be out of date. The level picker
                    says why.
                </span>
            </div>

            <!-- 2. The row itself — one three-band ramp (D-8). Listed in
                 ramp order, which is also the order the default sort puts
                 them in: position and appearance say the same thing. -->
            <div class="stock-row-legend__section-label">The row</div>
            <div class="stock-row-legend__item row items-center no-wrap">
                <span class="stock-row-legend__row-swatch stock-row-legend__row-swatch--alert" aria-hidden="true" />
                <span class="stock-row-legend__text">
                    Outlined: expired or expiring soon, or an essential that's low
                    or out.
                </span>
            </div>
            <div class="stock-row-legend__item row items-center no-wrap">
                <span class="stock-row-legend__row-swatch" aria-hidden="true" />
                <span class="stock-row-legend__text">Plain: nothing to do.</span>
            </div>
            <div class="stock-row-legend__item row items-center no-wrap">
                <span class="stock-row-legend__row-swatch stock-row-legend__row-swatch--dim" aria-hidden="true" />
                <span class="stock-row-legend__text">
                    Dimmed: out of stock, but not essential.
                </span>
            </div>
            <div class="stock-row-legend__item row items-center no-wrap">
                <span class="stock-row-legend__row-swatch stock-row-legend__row-swatch--essential" aria-hidden="true" />
                <span class="stock-row-legend__text">Essential item (left edge)</span>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
    import { computed } from 'vue';
    import { ICONS } from 'src/style/icons';
    import { colourForSequence } from 'src/helpers/stockLevelLogic';
    import type { StockLevel } from 'src/models/stockLevel';

    const props = defineProps<{
        /** The household's live level rows (renamed seeds included). */
        levels: readonly StockLevel[];
    }>();

    // Escalating order (Stocked → Low → Out → any custom) so the legend
    // reads top-down like the urgency ramp it documents.
    const sortedLevels = computed(() =>
        [...props.levels].sort((a, b) => a.sequence - b.sequence),
    );

    // Same mapping the row's level button uses (`levelButtonClass`): a
    // `bg-{semantic}` utility class, or the neutral token for unknown.
    function swatchClass(sequence: number): string {
        const colour = colourForSequence(sequence);
        return colour ? `bg-${colour}` : 'dora-bg-neutral';
    }
</script>

<style scoped lang="scss">
    .stock-row-legend {
        margin-top: var(--space-2);
        padding-top: var(--space-3);
        border-top: 1px solid color-mix(in srgb, var(--text-primary) 12%, transparent);
    }
    .stock-row-legend__title {
        font-size: var(--font-size-sm);
        font-weight: 600;
        color: var(--text-secondary);
        margin-bottom: var(--space-2);
    }
    .stock-row-legend__grid {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-1) var(--space-4);
    }
    /* Force a line break before each section label so the two sections head
       their own column of items. */
    .stock-row-legend__section-label {
        flex-basis: 100%;
        font-size: var(--font-size-xs);
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: var(--text-muted);
        margin-top: var(--space-2);
    }
    .stock-row-legend__item {
        flex: 0 1 auto;
        gap: var(--space-2);
        min-height: 22px;
    }
    .stock-row-legend__text {
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
    }

    /* Level swatch — mirrors the row's 32px level button at legend scale. */
    .stock-row-legend__swatch {
        flex: 0 0 auto;
        width: 16px;
        height: 16px;
        border-radius: var(--radius-sm, 4px);
    }
    .stock-row-legend__swatch--unset {
        background: var(--surface-component);
        border: 1px dashed color-mix(in srgb, var(--text-primary) 24%, transparent);
    }
    /* Same recipe as `.stock-row__level-btn--uncertain`, at legend scale, on
       a stocked-green fill so it's clear the marker rides an ordinary level
       rather than replacing it. Like the row, the dashes sit on a ring
       OUTSIDE the swatch with a gap (2026-08-22 feedback), so the fill stays
       an unbroken block. Halved against the row — 2px dashes, 1px gap, on a
       16px swatch against the row's 32px — because the row's 3px/2px on a
       box this small reads as nearly solid. The extra 3px of bleed is why
       the swatch needs its own margin below. */
    .stock-row-legend__swatch--uncertain {
        background: var(--semantic-positive);
        position: relative;
        margin: 3px;
    }
    .stock-row-legend__swatch--uncertain::after {
        content: '';
        position: absolute;
        inset: -3px;
        border: 2px dashed color-mix(in srgb, var(--text-primary) 65%, transparent);
        border-radius: calc(var(--radius-sm, 4px) + 3px);
    }

    /* Row-treatment swatches — a mini row (28×18) carrying the same
       treatment the real row does, so the mapping is visual not verbal.
       The bare class IS the "plain" band. */
    .stock-row-legend__row-swatch {
        flex: 0 0 auto;
        width: 28px;
        height: 18px;
        border-radius: var(--radius-sm, 4px);
        background: var(--surface-component);
        border: 1px solid color-mix(in srgb, var(--text-primary) 12%, transparent);
    }
    .stock-row-legend__row-swatch--essential {
        /* left-edge secondary stripe, matching StockItemRow. */
        border-left: 6px solid var(--brand-secondary-strong);
    }
    .stock-row-legend__row-swatch--alert {
        border-color: var(--semantic-negative);
        box-shadow: inset 0 0 0 1px var(--semantic-negative);
    }
    .stock-row-legend__row-swatch--dim {
        background: color-mix(in srgb, var(--text-primary) 22%, var(--surface-component));
        opacity: 0.62;
    }
</style>
