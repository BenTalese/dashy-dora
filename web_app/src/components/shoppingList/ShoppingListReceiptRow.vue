<template>
    <div class="sl-row sl-rcpt" :class="{ 'sl-rcpt--amending': amending }">
        <!-- The multiplier leads, the way it does on a printed docket. At rest
             it is type; in amend mode the same cell becomes the stepper, so
             turning the mode on doesn't move the name. -->
        <div class="sl-rcpt__lead">
            <template v-if="amending">
                <BaseButton
                    variant="icon"
                    size="sm"
                    :icon="ICONS.remove"
                    :disable="(line.quantity ?? 1) <= 1"
                    aria-label="One fewer"
                    @click="emit('adjust-quantity', -1)"
                />
                <span class="sl-rcpt__qtyvalue">{{ line.quantity ?? '–' }}</span>
                <BaseButton
                    variant="icon"
                    size="sm"
                    :icon="ICONS.add"
                    aria-label="One more"
                    @click="emit('adjust-quantity', 1)"
                />
            </template>
            <span v-else-if="(line.quantity ?? 0) > 1" class="sl-rcpt__mult">
                {{ line.quantity }}&times;
            </span>
        </div>

        <span class="sl-row__name sl-rcpt__name">{{ line.stock_item_name }}</span>

        <!-- The leader is the whole document device: it ties a name to its
             amount across a variable gap, which is exactly what the plan
             face's reserved-width columns do structurally. Decorative, so it
             is hidden from the accessibility tree.

             It only earns its place when there is something at the end of it.
             With money off — the default install, and the tier this design has
             to serve first — a rule running to the sheet edge and stopping
             reads as a number that failed to load, so the row is just a name
             and its store. -->
        <span
            v-if="moneyEnabled || amending"
            class="sl-rcpt__leader"
            aria-hidden="true"
        ></span>

        <div v-if="amending" class="sl-rcpt__edit">
            <!-- Only the fields the agreed design unlocks. Adding, removing
                 and re-ordering lines stay closed: a receipt is a record of
                 what happened, and the restock it drove has already been
                 applied. -->
            <BaseButton
                variant="ghost"
                dense
                :icon="ICONS.edit"
                :label="unitLabel"
                class="sl-rcpt__editbtn"
                @click="emit('edit-price')"
            >
                <BaseTooltip>Correct the price and store for this line</BaseTooltip>
            </BaseButton>
        </div>
        <div v-else-if="moneyEnabled" class="sl-row__money sl-rcpt__money">
            <span class="sl-row__amount">{{ lineAmount }}</span>
        </div>

        <div v-if="captionParts.length > 0" class="sl-row__meta sl-rcpt__caption">
            <span class="sl-row__note">{{ captionParts.join(' · ') }}</span>
        </div>
        <div v-if="unitNote" class="sl-row__amountnote sl-rcpt__unit">
            {{ unitNote }}
        </div>
    </div>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    /**
     * One bought line on the receipt face.
     *
     * Built on the shared row skeleton in `src/css/shoppingList.scss` — same
     * grid shell, same name and money type scale, same inset divider as the
     * plan row. That is the v4 §4.3 constraint: the receipt gets direction A's
     * document treatment, but as a variant of the row primitive rather than a
     * bespoke style island that drifts away from the rest of the surface.
     *
     * What is genuinely different is the *document* grammar — a quantity
     * multiplier, a dotted leader, and no controls at all until Amend is on —
     * and that difference is the point: the receipt face is the only face with
     * essentially no actions, so a control-free typographic layout fits it
     * natively and makes the state transition legible.
     */
    import { computed } from 'vue';
    import { ICONS } from 'src/style/icons';
    import BaseButton from 'src/components/BaseButton.vue';
    import { formatMoney } from 'src/composables/useMoney';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { priceOfLine, type ShoppingListLine } from 'src/models/shoppingList';

    const props = defineProps<{
        line: ShoppingListLine;
        amending: boolean;
    }>();

    const emit = defineEmits<{
        'edit-price': [];
        'adjust-quantity': [delta: -1 | 1];
    }>();

    const { moneyEnabled } = useMoneyEnabled();

    /** A "~" whenever the number is an estimate rather than one the user
     *  typed — on a receipt, the difference between "what it cost" and "what
     *  we think it cost" is the whole point of the document. */
    const lineAmount = computed(() => {
        if (props.line.estimated_unit_price == null) return '–';
        const prefix = props.line.estimate_source === 'actual' ? '' : '~';
        return `${prefix}${formatMoney(priceOfLine(props.line))}`;
    });

    const unitLabel = computed(() =>
        props.line.estimated_unit_price == null
            ? 'Set price'
            : formatMoney(props.line.estimated_unit_price)
    );

    const unitNote = computed(() => {
        if (!moneyEnabled.value || props.amending) return null;
        if ((props.line.quantity ?? 1) <= 1) return null;
        if (props.line.estimated_unit_price == null) return null;
        return `${formatMoney(props.line.estimated_unit_price)} each`;
    });

    const captionParts = computed(() => {
        const parts: string[] = [];
        const store = props.line.purchased_store_name ?? props.line.resolved_store_name;
        if (store) parts.push(store);
        // FU-805 — this said "estimated, no price entered" on a line that was
        // showing a price, which reads as a contradiction: the figure is right
        // there. The honest statement is where the figure came from, and the
        // server already names that rung of the ladder. The `~` on the amount
        // is the same claim in one character.
        if (props.line.estimate_source !== 'actual' && props.line.estimated_unit_price != null) {
            parts.push(props.line.prefill_source_label
                ? `estimated ${props.line.prefill_source_label}`
                : 'estimated');
        }
        return parts;
    });
</script>

<style scoped>
    /* Four tracks: multiplier, name, leader, amount. The name track is
       `max-content` bounded by 0 so a short name lets the leader run long (the
       document look) while a long one still shrinks rather than pushing the
       amount off the sheet. */
    .sl-rcpt {
        --sl-cols: var(--sl-rcpt-lead) minmax(0, max-content) minmax(var(--space-6), 1fr) auto;
        --sl-rcpt-lead: 2.25rem;
        align-items: end;
        padding-block: var(--space-2);
    }
    /* No divider. The shared skeleton gives every row an inset rule, which is
       right for the two faces that are lists of things you act on — but this
       face already ties a name to its amount with a dotted leader, and a
       document that uses *both* reads as neither: a ruled table with stray
       dots in it. The leader is the device; the rule goes (2026-09-17).

       What separates two lines on a docket is space, so the rows get a little
       more of it in exchange. */
    .sl-rcpt + .sl-rcpt::before {
        content: none;
    }
    .sl-rcpt + .sl-rcpt {
        padding-top: var(--space-3);
    }
    .sl-rcpt--amending {
        --sl-rcpt-lead: 104px;
        align-items: center;
    }

    .sl-rcpt__lead {
        grid-column: 1;
        grid-row: 1;
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: var(--space-1);
    }
    .sl-rcpt--amending .sl-rcpt__lead {
        justify-content: center;
    }
    .sl-rcpt__mult,
    .sl-rcpt__qtyvalue {
        font-variant-numeric: tabular-nums;
        color: var(--text-secondary);
    }
    .sl-rcpt__qtyvalue {
        min-width: 20px;
        text-align: center;
    }

    .sl-rcpt__name {
        grid-column: 2;
        grid-row: 1;
    }

    /* Sits on the name's baseline rather than the cell's centre, so a name
       that wraps to two lines keeps its leader on the last one. */
    .sl-rcpt__leader {
        grid-column: 3;
        grid-row: 1;
        align-self: end;
        border-bottom: 1px dotted var(--border-strong);
        margin-bottom: 0.42em;
        opacity: 0.7;
    }
    .sl-rcpt--amending .sl-rcpt__leader {
        align-self: center;
        margin-bottom: 0;
    }

    .sl-rcpt__money,
    .sl-rcpt__edit {
        grid-column: 4;
        grid-row: 1;
    }
    .sl-rcpt__editbtn {
        font-variant-numeric: tabular-nums;
    }

    /* Hangs directly under the name rather than a caption's default 2px
       below it — on a document the store is part of the same entry, not a
       second line of its own. */
    .sl-rcpt__caption {
        grid-column: 2 / 4;
        grid-row: 2;
        margin-top: 0;
    }
    .sl-rcpt__unit {
        grid-column: 4;
        grid-row: 2;
        text-align: right;
    }

    @media (max-width: 599px) {
        .sl-rcpt {
            --sl-rcpt-lead: 1.75rem;
            --sl-cols: var(--sl-rcpt-lead) minmax(0, max-content) minmax(var(--space-3), 1fr) auto;
        }
        .sl-rcpt--amending {
            --sl-rcpt-lead: 92px;
        }
        /* The unit price is the one number a phone receipt can lose: the line
           amount above it is the figure being read, and "each" is derivable
           from the multiplier. Stated here as of 2026-09-17 — it used to ride
           on a blanket `.sl-row__amountnote { display: none }` in the shared
           sheet, which was really the plan row's problem and left with it. */
        .sl-rcpt__unit {
            display: none;
        }
        .sl-rcpt__caption {
            grid-column: 2 / -1;
        }
        /* The amount is the only thing in this track and the leader pays for
           the gap, so it never needs more room than the figure. */
        .sl-rcpt__money {
            max-width: 5.5rem;
        }
    }
</style>
