<template>
    <!-- Renders nothing when there's no discount, so callers can drop it in
         without guarding at every site (four of them got that guard subtly
         different — FU-885). -->
    <q-badge
        v-if="discountPct !== null"
        class="discount-chip"
        :class="`discount-chip--${size}`"
        color="positive"
        text-color="white"
    >
        {{ discountPct }}% off
    </q-badge>
</template>

<script setup lang="ts">
    /** The one "% off" badge (FU-885 / feedback PH-6).
     *
     *  Was implemented four times — `MyProductsPage`, `StockItemDetailPage`,
     *  the (dead) `ProductChip`, and Price History, which also rendered it a
     *  different colour and a smaller size. The owner asked why it "feels
     *  different elsewhere"; it was, in three ways at once.
     *
     *  **Green, not red.** The two old spellings disagreed (`negative` on the
     *  product surfaces, `positive` on Price History) and the app's own
     *  semantics break the tie: D-001 reserves escalation red for urgency —
     *  out of stock, destructive, error. A discount is good news, so painting
     *  it red both misreads and competes with the states that genuinely need
     *  the alarm colour. The My Products card was the clearest symptom: the
     *  discount was red while its *out of stock* badge was amber, exactly
     *  inverting D-001's escalation.
     *
     *  Percentage rounding lives here rather than at the call sites (D-006:
     *  one formatting authority).
     */
    import { computed } from 'vue';
    import { discountPercent } from 'src/helpers/offerLogic';

    const props = withDefaults(
        defineProps<{
            /** Current price. Ignored when `pct` is supplied. */
            priceNow?: number | null;
            /** Pre-discount price. No badge unless this is genuinely higher. */
            priceWas?: number | null;
            /** A percentage the **server** already worked out (Price History's
             *  `deal_pct`). Wins over `priceNow`/`priceWas`: where the server
             *  owns the calculation, the client must not produce a second
             *  answer to the same question (R-003). This component is the one
             *  authority on how the badge *renders*, not on where the number
             *  comes from. */
            pct?: number | null;
            /** `sm` matches surrounding caption text; `md` is the default and
             *  is what a card face wants. Not a free-form size — two options
             *  keep the badge recognisable across surfaces. */
            size?: 'sm' | 'md';
        }>(),
        { priceNow: null, priceWas: null, pct: null, size: 'md' },
    );

    const discountPct = computed<number | null>(() => {
        if (props.pct != null) return props.pct > 0 ? Math.round(props.pct) : null;
        return discountPercent({ price_now: props.priceNow, price_was: props.priceWas });
    });
</script>

<style scoped>
    .discount-chip {
        font-weight: 600;
    }
    /* D-003: 12px is the hard floor and this badge carries a value, so `sm`
       sits at the floor rather than below it. The owner's note was that this
       chip was "a little small/hard to read" (MP-10, PH-5) — `md` is the
       default for that reason. */
    .discount-chip--sm {
        font-size: var(--font-size-xs);
    }
    .discount-chip--md {
        font-size: var(--font-size-sm);
    }
</style>
