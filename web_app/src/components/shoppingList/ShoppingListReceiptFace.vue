<template>
    <div class="sl-receipt">
        <!-- Amend is a mode, and a mode you are in must say so. The banner also
             carries the one consequence a user cannot see: correcting a price
             here does NOT re-run the restock. -->
        <q-banner
            v-if="amending"
            class="q-mb-md dora-bg-warning-soft"
            rounded
            dense
        >
            <template #avatar>
                <q-icon :name="ICONS.edit" color="warning" />
            </template>
            <div class="text-body2">
                <strong>Amending this receipt.</strong>
                You can change price, store and quantity.
            </div>
            <template #action>
                <BaseButton variant="ghost" label="Done" @click="emit('stop-amend')" />
            </template>
        </q-banner>

        <!-- Paper on a desk. Flat by owner call (v4 §7.2): the plan and shop
             faces carry the hero gradient, and the receipt not carrying it is
             what makes the state transition legible at a glance — the list
             visibly stops being a thing you act on. -->
        <div class="sl-receipt-sheet">
            <!-- No header row. It read "n items bought · Shopped <date>", which
                 is word-for-word what the overview card directly above already
                 says (its count, its date stamp and its Receipt pill), and two
                 headers stacked 40px apart is the duplication this rebuild is
                 meant to remove. The card is this document's header; the sheet
                 owns the itemisation and its total. -->
            <div class="sl-receipt-lines">
                <ShoppingListReceiptRow
                    v-for="line in boughtLines"
                    :key="line.line_id"
                    :line="line"
                    :amending="amending"
                    @edit-price="emit('edit-price', line)"
                    @adjust-quantity="emit('adjust-quantity', line, $event)"
                />
            </div>

            <!-- The total was in the header. On a document it belongs under
                 the itemisation, above a rule, where the eye already is when
                 it finishes reading the lines. -->
            <div v-if="moneyEnabled" class="sl-receipt-total">
                <span class="sl-receipt-total__label">Total</span>
                <span class="sl-receipt-total__leader" aria-hidden="true"></span>
                <span class="sl-receipt-total__value">
                    {{ formatMoney(detail.totals.total_price) }}
                </span>
                <span v-if="unpricedCount > 0" class="sl-receipt-total__note">
                    {{ unpricedCount }} not priced
                </span>
            </div>

            <div v-if="skippedLines.length > 0" class="sl-receipt-skipped">
                <div class="sl-receipt-skipped__label">
                    Didn't buy ({{ skippedLines.length }})
                </div>
                <div class="row q-gutter-xs">
                    <q-chip
                        v-for="line in skippedLines"
                        :key="line.line_id"
                        dense
                        square
                        class="dora-bg-sunken"
                    >
                        {{ line.stock_item_name }}
                    </q-chip>
                </div>
            </div>
        </div>

        <!-- "Where you spent it" is gone from here (2026-09-17). It lives in
             the overview card's disclosure, which is where the plan and shop
             faces have always shown it — rendering it as a standalone card
             below the sheet meant the same panel jumped to a different part of
             the page when a list finished. -->
    </div>
</template>

<script lang="ts" setup>
    /**
     * The receipt face — a finished list as a record of what happened.
     *
     * It replaces the old "DONE is DRAFT with everything disabled" rendering,
     * which showed a full editing surface greyed out: every stepper, drag
     * handle and delete button still on screen, all of them inert. That taught
     * the user nothing about the trip and made the page look broken.
     *
     * The data for a real receipt was already there and unused: what was
     * bought, what it cost, where from, and what got skipped. This shows that,
     * read-only, and puts the corrections behind an explicit **Amend** mode so
     * the default state of a historical record is "you cannot fat-finger it".
     */
    import { computed } from 'vue';
    import { ICONS } from 'src/style/icons';
    import BaseButton from 'src/components/BaseButton.vue';
    import ShoppingListReceiptRow from 'src/components/shoppingList/ShoppingListReceiptRow.vue';
    import { formatMoney } from 'src/composables/useMoney';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import type { ShoppingListDetail, ShoppingListLine } from 'src/models/shoppingList';

    const props = defineProps<{
        detail: ShoppingListDetail;
        amending: boolean;
    }>();

    const emit = defineEmits<{
        'stop-amend': [];
        'edit-price': [line: ShoppingListLine];
        'adjust-quantity': [line: ShoppingListLine, delta: -1 | 1];
    }>();

    const { moneyEnabled } = useMoneyEnabled();

    // Deferred-by-budget lines are not part of the active list and the server's
    // totals skip them, so the receipt must too — otherwise a line could appear
    // in the itemisation with no money behind it in the header.
    const activeLines = computed(() =>
        props.detail.lines.filter((l) => !l.deferred_by_budget)
    );
    const boughtLines = computed(() => activeLines.value.filter((l) => l.is_ticked));
    const skippedLines = computed(() => activeLines.value.filter((l) => !l.is_ticked));

    const unpricedCount = computed(() =>
        boughtLines.value.filter((l) => l.estimated_unit_price == null).length
    );

</script>

<style scoped>
    /* The same slab the plan face's list and panels use (chunk 1/2), one step
       up in radius to match the overview card — a receipt is a sheet, so it
       gets the sheet's corner. Flat: no gradient band, by owner call. */
    .sl-receipt-sheet {
        background: var(--surface-component);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-xl);
        box-shadow: var(--elevation-card);
        overflow: hidden;
    }

    /* A docket has margins. The itemisation used to run 8px from the sheet's
       top edge and sit on the same inline padding as a list row, which is what
       made a *document* read as a bordered list that happened to have dots in
       it. The extra room is the cheapest thing on this face and the most of
       what "polished" means here. */
    .sl-receipt-lines {
        padding-block: var(--space-4);
    }

    /* Under the itemisation, above its own rule — where a total goes on a
       document. Same four-track idea as the row, collapsed to three. */
    /* The total's own tracks are the row's, minus the multiplier: label,
       leader, amount. Its leader therefore starts and ends where every line's
       does, so the figures stack in one column and the dots run along one
       margin — the thing that makes a column of numbers read as a sum rather
       than as four more entries. */
    .sl-receipt-total {
        display: grid;
        grid-template-columns: max-content minmax(var(--space-6), 1fr) auto;
        align-items: end;
        column-gap: var(--space-3);
        padding: var(--space-4);
        border-top: 1px dashed var(--border-strong);
    }
    .sl-receipt-total__label {
        font-size: calc(var(--font-size-sm) * 1rem);
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-secondary);
    }
    .sl-receipt-total__leader {
        align-self: end;
        border-bottom: 1px dotted var(--border-strong);
        margin-bottom: 0.42em;
        opacity: 0.7;
    }
    .sl-receipt-total__value {
        font-size: calc(var(--font-size-2xl) * 1rem);
        font-weight: 700;
        font-variant-numeric: tabular-nums;
        line-height: 1.1;
    }
    /* Sits under the figure it qualifies — the headline can be short and the
       user has to be able to see that it is. */
    .sl-receipt-total__note {
        grid-column: 3;
        justify-self: end;
        font-size: calc(var(--font-size-xs) * 1rem);
        color: var(--text-muted);
    }

    .sl-receipt-skipped {
        padding: var(--space-3) var(--space-4);
        background: var(--surface-sunken);
    }
    .sl-receipt-skipped__label {
        font-size: calc(var(--font-size-xs) * 1rem);
        color: var(--text-muted);
        margin-bottom: var(--space-1);
    }

    @media (max-width: 599px) {
        .sl-receipt-total,
        .sl-receipt-skipped {
            padding-inline: var(--space-3);
        }
    }
</style>
