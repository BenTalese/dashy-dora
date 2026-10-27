<template>
    <!-- One chip, one question: can I cook this tonight? Colour carries the
         answer (D-001's out-of-stock red at the bottom, positive green at the
         top), the label names it in words so the colour is never the only
         signal, and the tooltip spells the mapping out on every state (D-013).
         The swaps that used to sit in a second chip beside this one now ride
         inside it — same menu, one object on the row. -->
    <component
        :is="hasSwaps ? 'button' : 'span'"
        class="rmic dora-chip--tint"
        :class="`dora-chip--tint-${tone}`"
        :type="hasSwaps ? 'button' : undefined"
        :aria-label="`${label}: ${ingredientName}`"
    >
        <q-icon
            :name="state === 'ready' ? ICONS.swap_horiz : ICONS.warning"
            :size="state === 'ready' ? '16px' : '14px'"
        />
        <span>{{ label }}</span>
        <q-icon v-if="hasSwaps" :name="ICONS.expand_more" size="14px" />

        <BaseTooltip>{{ tooltip }}</BaseTooltip>

        <q-menu v-if="hasSwaps" anchor="bottom left" self="top left" class="rmic__menu">
            <div class="rmic__head">
                <span class="rmic__headk">Instead of {{ ingredientName }}</span>
            </div>
            <q-list dense separator class="rmic__list">
                <q-item v-for="entry in ordered" :key="entry.sub.stock_item_id">
                    <!-- Stock level reads as the same dot-left-of-the-name it
                         does everywhere else in the app, rather than this
                         surface's own badge wording (D-013 / owner feedback
                         2026-08-27). Tooltip'd — a bare dot isn't decodable. -->
                    <q-item-section side class="rmic__dot">
                        <StockLevelDot :sequence="entry.levelSequence" size="12px">
                            <BaseTooltip>{{ entry.levelLabel }}</BaseTooltip>
                        </StockLevelDot>
                    </q-item-section>
                    <q-item-section>
                        <q-item-label class="rmic__name">
                            {{ entry.sub.name }}
                        </q-item-label>
                        <q-item-label v-if="formatSubstituteRatio(entry.sub)" caption>
                            {{ formatSubstituteRatio(entry.sub) }}
                        </q-item-label>
                        <q-item-label v-if="entry.sub.notes" caption class="dora-text-secondary">
                            {{ entry.sub.notes }}
                        </q-item-label>
                    </q-item-section>
                    <q-item-section side>
                        <AddToListButton
                            v-if="!entry.inStock"
                            :stock-item-id="entry.sub.stock_item_id"
                            variant="row"
                        />
                    </q-item-section>
                </q-item>
            </q-list>
        </q-menu>
    </component>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    /**
     * A missing ingredient's whole story, as one row-level chip.
     *
     * Was two chips — a "Missing" severity chip owned by the page and a "N
     * swaps" pill owned by this component — sitting side by side saying two
     * halves of one sentence. The owner's read (2026-08-31): *"can missing and
     * swappable be combined into one ui element somehow?"* They can, because
     * they were never two facts: "I'm out of pecorino" and "but there's grana
     * in the fridge" are one answer to one question, and the answer has three
     * possible values, which is exactly what a three-state chip is for.
     *
     *   out    (negative) — missing, and nothing recorded to use instead.
     *   swaps  (warning)  — missing, but there are recorded alternatives. All
     *                       of them are things you'd have to buy, so this
     *                       still blocks tonight; the menu says what they are.
     *   ready  (positive) — missing, but you already have a substitute in the
     *                       pantry. The row isn't blocking anything.
     *
     * The count means whatever the word beside it means: `Missing · 2 swaps`
     * counts every recorded swap (including ones you'd have to buy — that's
     * the point of showing it), `Swap ready · 2` counts the ones you actually
     * have. It's suppressed at 1 in the ready state, where it adds nothing.
     *
     * Read-only by design. Substitutes are per-cook swaps (cook mode owns
     * them) and per-item facts (the stock-item detail page owns them); nothing
     * here writes either. The menu only exists when there is something in it,
     * so the `out` state renders as a plain span rather than a dead button.
     */
    import { computed } from 'vue';

    import AddToListButton from 'src/components/AddToListButton.vue';
    import StockLevelDot from 'src/components/stock/StockLevelDot.vue';
    import { ICONS } from 'src/style/icons';
    import { formatSubstituteRatio } from 'src/helpers/substituteRatio';
    import type { SubstituteOption } from './recipeSubstituteTypes';

    const props = defineProps<{
        entries: SubstituteOption[];
        ingredientName: string;
    }>();

    /** In-stock options first — the actionable ones — then alphabetical so the
     *  order is stable between renders. */
    const ordered = computed(() =>
        [...props.entries].sort((a, b) => {
            if (a.inStock !== b.inStock) return a.inStock ? -1 : 1;
            return a.sub.name.localeCompare(b.sub.name);
        }));

    const readyCount = computed(() => props.entries.filter((e) => e.inStock).length);
    const hasSwaps = computed(() => props.entries.length > 0);

    const state = computed<'out' | 'swaps' | 'ready'>(() => {
        if (readyCount.value > 0) return 'ready';
        return hasSwaps.value ? 'swaps' : 'out';
    });

    /** The shared `.dora-chip--tint` tone this state wears. Same vocabulary
     *  the "Use soon" / "Expired" chip beside it uses, which is the point —
     *  owner, 2026-09-01: the two chips must read as one system. */
    const tone = computed(() => {
        switch (state.value) {
            case 'ready': return 'positive';
            case 'swaps': return 'warning';
            case 'out':
            default: return 'negative';
        }
    });

    const label = computed(() => {
        if (state.value === 'out') return 'Missing';
        if (state.value === 'ready') {
            return readyCount.value === 1 ? 'Swap ready' : `Swap ready · ${readyCount.value}`;
        }
        const n = props.entries.length;
        return `Missing · ${n} swap${n === 1 ? '' : 's'}`;
    });

    /* Missing means **out of stock**, never low — the server's `is_missing`,
       whose whole point is that a low ingredient is one you can usually still
       cook with (owner asked which it was, 2026-08-27). Each state says so in
       its own words so the colour is never carrying the meaning alone. */
    const tooltip = computed(() => {
        switch (state.value) {
            case 'ready':
                return readyCount.value === 1
                    ? 'Out of stock, but you have something you could use instead.'
                    : `Out of stock, but you have ${readyCount.value} things you could use instead.`;
            case 'swaps':
                return 'Out of stock. There are alternatives, but you\'d have to buy those too.';
            case 'out':
            default:
                return 'Out of stock. No substitutes linked.';
        }
    });
</script>

<style scoped lang="scss">
    /* The chip's whole look — tint, hairline, coloured glyph, neutral ink,
       28px tap target — is the shared `.dora-chip--tint` in `colours.scss`
       (see its D-002 carve-out note). It moved out of here on 2026-09-01 so
       the "Use soon" chip on the same row could wear it too; only this
       component's own behaviour is left below. */

    /* Only the two states that own a menu are pressable. */
    button.rmic {
        cursor: pointer;

        &:hover { filter: brightness(0.97); }
        &:active { filter: brightness(0.94); }
        /* A6 / D-016 — focus is never suppressed. */
        &:focus-visible {
            outline: 2px solid var(--focus-ring);
            outline-offset: 2px;
        }
    }

    .rmic__head {
        padding: var(--space-3) var(--space-4) var(--space-2);
    }

    .rmic__headk {
        font-size: var(--font-size-xs);
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: var(--text-muted);
    }

    .rmic__list {
        min-width: 260px;
        max-width: 360px;
    }

    .rmic__name {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        flex-wrap: wrap;
    }

    .rmic__dot {
        padding-right: var(--space-2);
        min-width: 0;
    }
</style>
