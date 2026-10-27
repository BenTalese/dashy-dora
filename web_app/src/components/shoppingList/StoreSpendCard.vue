<template>
    <!-- "Where you'll spend it" — the plan-face store breakdown.
         Renders nothing at all unless the server resolved at least one real
         store, so it never nags installs that don't use stores. -->
    <CollapsibleCard
        v-if="buckets.length > 0"
        class="sl-store-card"
        :class="{ 'sl-store-card--flush': flush }"
        :collapsible="collapsible"
        header-toggles
        reveals="store breakdown"
    >
        <template #header>
            <div class="row items-center no-wrap q-gutter-x-sm sl-store-card__title">
                <q-icon :name="ICONS.storefront" size="18px" class="dora-text-secondary" />
                <span :class="flush ? 'sl-store-card__caption' : 'text-subtitle2'">
                    {{ title }}
                </span>
            </div>
        </template>

        <template #collapsed>
            <div class="text-caption dora-text-muted ellipsis">{{ summaryLine }}</div>
        </template>

        <template #default>
            <div class="q-pt-sm q-pb-xs">
                <!-- Proportional bar. With money on, segments are spend
                     share; with money off there is no spend to share out, so
                     it falls back to how many items each store is carrying —
                     the same question, minus the dollars. Buckets that have
                     items but no value still get a floor width so they can't
                     vanish from a bar whose own legend lists them; see
                     `segments`. -->
                <ProportionBar :segments="segments" />
            </div>

            <div class="q-pt-xs">
                <div class="row q-gutter-xs">
                    <q-chip
                        v-for="b in buckets"
                        :key="b.store_id ?? '__none__'"
                        dense
                        square
                        class="sl-store-chip"
                        :class="{ 'sl-store-chip--none': b.store_id === null }"
                    >
                        <!-- Every bucket in the bar gets a mark in the key,
                             including the catch-all: it had none, so the one
                             segment a reader is most likely to query was the
                             one the legend couldn't identify. The hatch is the
                             bar's own, shared rather than redrawn. -->
                        <span
                            class="sl-store-dot"
                            :class="{ 'dora-fill-unassigned': b.store_id === null }"
                            :style="b.store_id === null ? undefined : { background: segmentColour(b) }"
                        />
                        <span class="text-weight-medium q-mr-xs">{{ b.store_name }}</span>
                        <span class="dora-text-muted">
                            {{ b.line_count }} item{{ b.line_count === 1 ? '' : 's' }}
                            <template v-if="moneyEnabled && b.priced_line_count > 0">
                                · {{ approx(b) }}{{ formatMoney(b.subtotal) }}
                            </template>
                        </span>
                    </q-chip>
                </div>

                <div v-if="footnote" class="text-caption dora-text-muted q-mt-sm">
                    {{ footnote }}
                </div>
            </div>
        </template>
    </CollapsibleCard>
</template>

<script lang="ts" setup>
    /**
     * The store breakdown lifted out of the "Trip" direction (C) into the plan
     * face. It answers one question the rest of the page can't: *am I about to
     * spend $50 more at Coles than at Aldi?*
     *
     * The design constraint that shaped it: product offers are a power-user
     * feature most installs will never populate. The server's store ladder
     * resolves through `usual_store_id` and past purchases before it ever looks
     * at an offer, so this card is fully populated for someone who has simply
     * tagged items "I buy this at Aldi" and shopped twice.
     *
     * That makes partial data the normal case, not an edge case — hence the
     * explicit footnote when some lines have no price. A total that silently
     * omits a third of the list is worse than one that admits the gap.
     */
    import { computed } from 'vue';
    import { ICONS } from 'src/style/icons';
    import CollapsibleCard from 'src/components/CollapsibleCard.vue';
    import ProportionBar from 'src/components/ProportionBar.vue';
    import { formatMoney } from 'src/composables/useMoney';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { storeColour } from 'src/style/storeSwatch';
    import type { StoreSpend } from 'src/models/shoppingList';

    const props = withDefaults(defineProps<{
        buckets: StoreSpend[];
        /**
         * Whether this card can close at all — *not* whether it starts closed.
         * It always starts closed (`CollapsibleCard` owns that, and it is the
         * app-wide default).
         *
         * It used to be `ref(!collapsible)` with both callers passing
         * `$q.screen.lt.md`, which meant "expanded on desktop, collapsed on a
         * phone" — and, being a `ref` seeded once at setup, it never
         * re-evaluated when the window crossed the breakpoint (FU-783). The
         * screen-size question is gone entirely rather than fixed: the one
         * caller that genuinely shouldn't collapse is the plan face's, because
         * that card now sits *inside* the overview card's expanded region,
         * where a second tap to reach the same information is a tax.
         */
        collapsible?: boolean;
        /**
         * Drop this card's own surface — no border, no radius, no padding of
         * its own — for the caller that renders it *inside* another card.
         *
         * The plan and shop faces put it in the overview card's disclosure,
         * where it kept a full bordered box and a 44px gradient header of its
         * own: a card inside a card, two nested headers, and a second rounded
         * edge 16px inside the first (owner, 2026-09-17: *"shouldn't be a card
         * within a card dropdown, looks so odd — make it a continuation of the
         * dropdown header card"*). Flush, it is a captioned region of the card
         * it sits in. The receipt face renders it standing alone and keeps the
         * surface.
         */
        flush?: boolean;
        /** Which face is asking. All three tenses are real: a draft hasn't
         *  spent anything, a receipt has spent all of it, and mid-shop is
         *  genuinely neither — some of the trolley is paid for and some isn't,
         *  so past tense there reads as a shop you've already finished. */
        tense?: 'plan' | 'shop' | 'receipt';
    }>(), { collapsible: true, flush: false, tense: 'plan' });

    const { moneyEnabled } = useMoneyEnabled();

    /** 2026-08-26 feedback: *"'Where you spent it' is a bit odd when budgets
     *  and money are off"* — and it was, because the card kept its money
     *  wording while showing nothing but item counts. All six wordings live
     *  here so the callers can't drift: the face picks the tense, the money
     *  flag picks the verb. */
    const title = computed(() => {
        switch (props.tense) {
            case 'receipt':
                return moneyEnabled.value ? 'Where you spent it' : 'Where you shopped';
            case 'shop':
                return moneyEnabled.value ? "Where you're spending" : "Where you're shopping";
            default:
                return moneyEnabled.value ? "Where you'll spend it" : "Where you'll shop";
        }
    });

    /** What each segment's width is proportional to. Money when there is
     *  money; item count otherwise. */
    function barValue(bucket: StoreSpend): number {
        return moneyEnabled.value ? bucket.subtotal : bucket.line_count;
    }

    /**
     * The bar's segments. The **widths** — including the floor that stops a
     * bucket with items but no value from vanishing out of a bar whose own
     * legend still lists it (2026-08-28 owner feedback: *"also allocate space
     * for 'no store'"*) — now live in `ProportionBar`, shared with Reports so
     * the two surfaces draw one dataset one way (R-001). What stays here is the
     * only part that is this card's business: *what* each segment is weighed
     * by, which is spend when money is on and item count when it isn't.
     */
    const segments = computed(() =>
        props.buckets
            .filter((b) => b.line_count > 0)
            .map((b) => ({
                key: b.store_id ?? '__none__',
                label: b.store_name,
                value: barValue(b),
                colour: segmentColour(b),
                isUnassigned: b.store_id === null,
            })),
    );

    const unpricedCount = computed(() =>
        props.buckets.reduce((sum, b) => sum + (b.line_count - b.priced_line_count), 0)
    );

    /** A "~" marker whenever a bucket's money is an estimate rather than
     *  something the user actually typed for this trip. */
    function approx(bucket: StoreSpend): string {
        return bucket.priced_line_count < bucket.line_count ? '~' : '';
    }

    /** Identity, not state — a store's own colour, so Woolworths reads green
     *  and Coles red (2026-08-26 feedback). It used to come from the chart
     *  ramp indexed by *position in this list*, which meant a store changed
     *  colour whenever the spend order changed. `storeColour` resolves the
     *  logo-derived `brand_colour` first and falls back to the deterministic
     *  name hash; D-001 is satisfied because the colour never encodes a state
     *  and never travels without the store's name beside it. */
    /** `undefined` for the catch-all: it has no identity colour, and the
     *  stylesheet owns its fill (an inline `background` shorthand would clobber
     *  the hatch's `background-image`). Every real store keeps its own. */
    function segmentColour(bucket: StoreSpend): string | undefined {
        if (bucket.store_id === null) return undefined;
        return storeColour(bucket.store_name, bucket.brand_colour);
    }

    const summaryLine = computed(() => {
        const parts = props.buckets.map((b) => {
            if (moneyEnabled.value && b.priced_line_count > 0) {
                return `${b.store_name} ${approx(b)}${formatMoney(b.subtotal)}`;
            }
            return `${b.store_name} ${b.line_count}`;
        });
        return parts.join(' · ');
    });

    /** How much of the list isn't priced at all. The "$X more at A than B"
     *  note that shared this line went on 2026-09-27 (owner: useless). It
     *  compared two buckets the bar above already draws side by side. */
    const footnote = computed(() => {
        const notes: string[] = [];
        // Money-gated too: with money off nothing on this card is priced, so
        // "12 items unpriced, not counted" would be describing a total the
        // user can't see and never asked for.
        if (moneyEnabled.value && unpricedCount.value > 0) {
            notes.push(
                `${unpricedCount.value} item${unpricedCount.value === 1 ? '' : 's'} unpriced, not counted`
            );
        }
        return notes.join(' · ');
    });
</script>

<style scoped>
    /* Was `q-card flat bordered`. `CollapsibleCard` owns the disclosure and
       nothing else, so the surface is stated here — the same flat-bordered
       look, minus a component wrapper that only ever contributed padding. */
    .sl-store-card {
        padding: var(--space-3);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
        background: var(--surface-component);
    }
    /* A region of its host, not a box inside it. */
    .sl-store-card--flush {
        padding: 0;
        border: none;
        border-radius: 0;
        background: none;
    }
    /* The 44px is a tap target, and it only exists where the header *is* one.
       A flush card is rendered non-collapsible, so the header toggles nothing
       and the height was pure chrome — a heading three times the size of the
       line of text it introduced. */
    .sl-store-card__title {
        min-height: 44px;
    }
    .sl-store-card--flush .sl-store-card__title {
        min-height: 0;
    }
    /* Matches `.sl-section__title`, the label the plan face already puts above
       a group of rows — so the two headings inside one card read as the same
       rank rather than as two competing voices. */
    .sl-store-card__caption {
        font-size: var(--font-size-sm);
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-secondary);
    }
    .sl-store-chip {
        background: var(--surface-sunken);
    }
    .sl-store-chip--none {
        opacity: 0.75;
    }
    .sl-store-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 6px;
        flex: none;
    }
</style>
