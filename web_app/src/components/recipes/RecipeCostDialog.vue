<template>
    <!--
        Recipe cost breakdown, as a modal.

        Owner feedback 2026-08-24: the breakdown was an expansion row on the
        page ("weird as a section") holding a bare two-column table. Cost is a
        question you ask, get an answer to, and close — a modal, not a
        permanent fixture of the page. And the answer is not a list of
        numbers: it's *what dominates the bill* and *how much of the recipe we
        could actually price*. So the priced ingredients are ranked, each with
        a share bar, and the unpriced ones are grouped by why we couldn't
        price them rather than repeating "–" down a column.
    -->
    <BaseDialog
        v-model="open"
        title="Cost breakdown"
        closable
        card-style="min-width: 0; width: min(560px, 94vw)"
    >
        <q-card-section class="rcost__summary">
            <div class="rcost__totals">
                <div class="rcost__total">
                    <span class="rcost__k">Estimated total</span>
                    <span class="rcost__v">{{ total !== null ? formatMoney(total) : '–' }}</span>
                </div>
                <div v-if="props.perServing !== null" class="rcost__total">
                    <span class="rcost__k">Per serving</span>
                    <span class="rcost__v">{{ formatMoney(props.perServing) }}</span>
                </div>
            </div>

            <!-- How much of the recipe the estimate actually covers. A
                 confidence statement, not decoration: an estimate built from
                 3 of 11 ingredients is a different number to one built from
                 11 of 11, and the old table made the reader count rows. -->
            <div class="rcost__coverage">
                <div class="rcost__bar" role="img" :aria-label="coverageLabel">
                    <div class="rcost__barfill" :style="{ width: coveragePct + '%' }"></div>
                </div>
                <span class="rcost__cov">{{ coverageLabel }}</span>
            </div>
        </q-card-section>

        <q-separator />

        <q-card-section class="rcost__body">
            <template v-if="priced.length > 0">
                <!-- Owner feedback 2026-09-01: *"What are the bars on the cost
                     breakdown showing? Is it their % of the total cost?"* They
                     weren't — they were each line's share of the *dearest*
                     line, which is a fine way to rank bars and an impossible
                     one to read without being told. Share of the total is what
                     a breakdown is actually asking, so that's what the bar is
                     now, and the number is printed beside it rather than left
                     to be inferred from a bar's length. -->
                <div class="rcost__listhead">Share of the estimate</div>
                <ul class="rcost__list">
                    <li v-for="line in priced" :key="line.key">
                        <div class="rcost__row">
                            <span class="rcost__name">{{ line.name }}</span>
                            <span class="rcost__amount">{{ formatMoney(line.line_cost!) }}</span>
                            <span class="rcost__pct">{{ sharePct(line) }}%</span>
                        </div>
                        <div class="rcost__share">
                            <div
                                class="rcost__sharefill"
                                :style="{ width: sharePct(line) + '%' }"
                            ></div>
                        </div>
                        <div class="rcost__meta">
                            <span v-if="formatQuantity(line.quantity, line.unit)">
                                {{ formatQuantity(line.quantity, line.unit) }}
                            </span>
                            <span v-if="unitPriceLabel(line)">{{ unitPriceLabel(line) }}</span>
                        </div>
                    </li>
                </ul>
            </template>
            <p v-else class="rcost__empty">
                Nothing here could be priced yet.
            </p>

            <!-- Owner feedback 2026-09-01: *"'No price recorded yet' should be
                 a vertical list, not text separated by dots in a row."* Dots
                 read as one run-on sentence and wrapped mid-name; these are
                 individually actionable rows (each is an item you'd go and put
                 a price on), so they get a line each. -->
            <template v-for="group in unpricedGroups" :key="group.reason">
                <div class="rcost__grouphead">{{ group.title }}</div>
                <ul class="rcost__groupnames">
                    <li v-for="name in group.names" :key="name">{{ name }}</li>
                </ul>
            </template>
        </q-card-section>

        <template #actions>
            <BaseButton variant="ghost" label="Close" @click="open = false" />
        </template>
    </BaseDialog>
</template>

<script lang="ts" setup>
    import { computed } from 'vue';

    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import { formatMoney } from 'src/composables/useMoney';
    import { formatQuantity } from 'src/helpers/formatQuantity';
    import { requoteUnitPrice } from 'src/helpers/unitPriceDisplay';
    import { useMeasurementSystem } from 'src/composables/useMeasurementSystem';
    import type { RecipeCostLine, RecipeCostUnpricedReason } from 'src/models/recipe';

    const { system: measurementSystem } = useMeasurementSystem();

    const props = defineProps<{
        modelValue: boolean;
        lines: RecipeCostLine[];
        /** Server-derived estimate. Null when nothing could be priced. */
        total: number | null;
        pricedCount: number;
        totalCount: number;
        /** Server-derived per-serving cost (R-003); null without servings. */
        perServing: number | null;
    }>();

    const emit = defineEmits<{ (e: 'update:modelValue', value: boolean): void }>();

    const open = computed({
        get: () => props.modelValue,
        set: (v) => emit('update:modelValue', v),
    });


    type PricedLine = RecipeCostLine & { key: string };

    /** Dearest first: the actionable read of a bill is what dominates it. */
    const priced = computed<PricedLine[]>(() =>
        props.lines
            .filter((l) => l.line_cost !== null)
            .map((l, i) => ({ ...l, key: `${l.name}-${i}` }))
            .sort((a, b) => (b.line_cost ?? 0) - (a.line_cost ?? 0)));

    /** Each line as a percentage of the estimate — the question the bar was
     *  always being read as (owner, 2026-09-01). The denominator is the sum of
     *  the priced lines rather than `props.total`, so the shares add to 100%
     *  even when the server's total carries rounding the lines don't. */
    const pricedTotal = computed(() =>
        priced.value.reduce((sum, l) => sum + (l.line_cost ?? 0), 0));

    function sharePct(line: PricedLine): number {
        if (pricedTotal.value <= 0) return 0;
        return Math.round(((line.line_cost ?? 0) / pricedTotal.value) * 100);
    }

    /** "$0.00 / g" is what a per-gram price rounds to in cents, and it reads
     *  as free.
     *
     *  This used to flip to per-kilo/per-litre below a $0.05 threshold of its
     *  own — a second, quieter answer to a question the domain already owns,
     *  which meant the same product could read "/kg" here and "/100g" in the
     *  YourPrices widget, and neither followed the install's measurement
     *  system. It now goes through the shared convention (owner feedback
     *  2026-09-13: match what real store websites show). */
    function unitPriceLabel(line: RecipeCostLine): string | null {
        if (line.unit_price === null || !line.priced_unit) return null;
        const quoted = requoteUnitPrice(
            line.unit_price, line.priced_unit, measurementSystem.value,
        );
        if (quoted === null) return `${formatMoney(line.unit_price)} / ${line.priced_unit}`;
        return `${formatMoney(quoted.amount)} / ${quoted.unit}`;
    }

    const coveragePct = computed(() => {
        if (props.totalCount <= 0) return 0;
        return Math.round((props.pricedCount / props.totalCount) * 100);
    });
    const coverageLabel = computed(
        () => `Priced ${props.pricedCount} of ${props.totalCount} ingredients`);

    /** The server ships reason ids; this map is the only copy of their
     *  wording, grouped so a recipe with eight unlinked rows reads as one
     *  sentence rather than eight. */
    const REASON_TITLES: Record<RecipeCostUnpricedReason, string> = {
        no_link: 'Not linked to a pantry item',
        no_price: 'No price recorded yet',
        no_quantity: 'No amount on the ingredient',
        unit_no_pack_count: "Priced by weight, and we don't know how many come in a pack",
        unit_no_pack_size: "Priced per pack, and the pack size isn't recorded",
        unit_unknown_density: "Can't convert between weight and volume for this ingredient",
        unit_wrong_food: "That unit doesn't apply to this ingredient",
        unit_mismatch: "Units don't match the price",
    };

    const unpricedGroups = computed(() => {
        const buckets = new Map<RecipeCostUnpricedReason, string[]>();
        for (const line of props.lines) {
            if (line.line_cost !== null || !line.reason) continue;
            const names = buckets.get(line.reason) ?? [];
            names.push(line.name);
            buckets.set(line.reason, names);
        }
        return [...buckets.entries()].map(([reason, names]) => ({
            reason,
            title: REASON_TITLES[reason],
            names,
        }));
    });
</script>

<style scoped lang="scss">
    .rcost__summary {
        display: flex;
        flex-direction: column;
        gap: var(--space-3, 12px);
    }
    .rcost__totals {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-6, 24px);
    }
    .rcost__total { display: flex; flex-direction: column; gap: 2px; }
    .rcost__k {
        font-size: calc(var(--font-size-xs) * 1rem);
        font-weight: 700;
        letter-spacing: 0.07em;
        text-transform: uppercase;
        color: var(--text-muted);
    }
    .rcost__v {
        font-size: 1.5rem;
        font-weight: 700;
        font-variant-numeric: tabular-nums;
    }

    .rcost__coverage { display: flex; align-items: center; gap: var(--space-3, 12px); }
    .rcost__bar {
        flex: 1;
        height: 6px;
        border-radius: var(--radius-pill, 999px);
        background: var(--surface-sunken);
        overflow: hidden;
    }
    .rcost__barfill { height: 100%; background: var(--brand-primary); }
    .rcost__cov {
        font-size: 0.8125rem;
        color: var(--text-muted);
        white-space: nowrap;
    }

    .rcost__body { max-height: 52vh; overflow-y: auto; }
    .rcost__listhead {
        font-size: calc(var(--font-size-xs) * 1rem);
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--text-muted);
    }
    .rcost__list { list-style: none; margin: 0; padding: 0; }
    .rcost__list > li { padding: var(--space-2, 8px) 0; }
    .rcost__row {
        display: flex;
        align-items: baseline;
        gap: var(--space-3, 12px);
    }
    .rcost__name { flex: 1; min-width: 0; }
    .rcost__amount { font-weight: 700; font-variant-numeric: tabular-nums; }
    /* Fixed width so the column of percentages lines up under itself — the
       bar is the shape of the share, this is the value of it. */
    .rcost__pct {
        min-width: 3.25rem;
        text-align: right;
        font-variant-numeric: tabular-nums;
        font-size: 0.8125rem;
        color: var(--text-muted);
    }
    .rcost__share {
        height: 4px;
        border-radius: var(--radius-pill, 999px);
        background: var(--surface-sunken);
        overflow: hidden;
        margin-top: var(--space-1, 4px);
    }
    /* A line that rounds to 0% still gets a visible sliver rather than an
       empty track — but the printed number stays honest about the rounding.

       Owner feedback 2026-09-08: the fill was `--brand-primary-soft`, which in
       the dark themes is a low-alpha wash of the brand hue (pesto's is a 22%
       green) sitting on a near-black sunken track — the filled part was
       effectively invisible. The bar's job is to be read at a glance, so it
       wears the solid brand ink the coverage bar above it does; it stays
       distinguishable from that one by being thinner, which is a difference
       that survives both themes. */
    .rcost__sharefill {
        height: 100%;
        min-width: 2px;
        background: var(--brand-primary);
    }
    .rcost__meta {
        display: flex;
        gap: var(--space-3, 12px);
        margin-top: 2px;
        font-size: 0.75rem;
        color: var(--text-muted);
    }

    .rcost__grouphead {
        margin-top: var(--space-4, 16px);
        font-size: calc(var(--font-size-xs) * 1rem);
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--text-muted);
    }
    .rcost__groupnames {
        list-style: none;
        margin: var(--space-2, 8px) 0 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .rcost__groupnames > li {
        padding: var(--space-2, 8px) var(--space-3, 12px);
        border-radius: var(--radius-sm, 4px);
        background: var(--surface-sunken);
        font-size: 0.875rem;
        color: var(--text-primary);
    }
    .rcost__empty { color: var(--text-muted); font-size: 0.875rem; margin: 0; }
</style>
