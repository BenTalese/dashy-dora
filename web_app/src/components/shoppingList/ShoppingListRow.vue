<template>
    <div
        class="sl-row sl-row--hoverable"
        :class="{
            'sl-row--ticked': line.is_ticked,
            'sl-row--focused': focused,
            'sl-row--nested': nested,
            'sl-row--product-only': productOnly,
            'sl-row--no-money': !moneyEnabled,
            'sl-row--no-verdict': !showVerdict,
        }"
    >
        <!-- The tick is its own target (UX v5 S8). The whole row used to be
             one, which left the name picker, store and price fighting a
             row-sized click handler. -->
        <button
            type="button"
            class="sl-row__tick"
            role="checkbox"
            :aria-checked="line.is_ticked"
            :aria-label="`${line.is_ticked ? 'Untick' : 'Tick'} ${line.stock_item_name}`"
            @click="emit('toggle')"
        >
            <q-icon
                :name="line.is_ticked ? ICONS.check_box : ICONS.check_box_outline_blank"
                size="28px"
                :color="line.is_ticked ? 'positive' : undefined"
            />
        </button>

        <!-- Quantity: the tile alone, tap to type (UX v5 S7). -->
        <div class="sl-row__qty">
            <button
                type="button"
                class="sl-row__tile"
                :aria-label="`Quantity ${line.quantity ?? 1}, edit`"
                @click="onTileClick"
            >
                <input
                    v-if="editingQty"
                    ref="qtyInput"
                    class="sl-row__tile-input"
                    type="number"
                    inputmode="numeric"
                    min="1"
                    step="1"
                    :value="line.quantity ?? ''"
                    @blur="onQtyCommit"
                    @keydown.enter.prevent="($event.target as HTMLInputElement).blur()"
                />
                <span v-else>{{ line.quantity ?? '–' }}</span>
            </button>
        </div>

        <!-- Name and Dora's mark travel together. -->
        <div class="sl-row__namegroup">
            <!-- The "which one" picker; see `LineChoicePicker`. An item with
                 nothing to choose from is plain text, the common case. -->
            <LineChoicePicker
                v-if="hasChoices"
                :choice="choice"
                :struck="line.is_ticked"
                @pick-offer="onPickOffer"
                @pick-hint="emit('pick-hint', $event)"
            />
            <span
                v-else
                class="sl-row__name"
                :class="{
                    'sl-row__name--struck': line.is_ticked,
                    'sl-row__name--plain': nested || productOnly,
                }"
            >
                <q-icon
                    v-if="nested || productOnly"
                    :name="ICONS.shopping_bag"
                    size="14px"
                    class="q-mr-xs dora-text-muted"
                />
                {{ displayName }}
                <BaseTooltip v-if="productOnly">
                    Not linked to a stock item
                </BaseTooltip>
                <BaseTooltip v-else-if="nested">Nested product</BaseTooltip>
            </span>
            <!-- Only on lines the low-stock trigger put here. -->
            <q-icon
                v-if="line.is_auto_added"
                :name="ICONS.dora_voice"
                size="14px"
                class="sl-row__automark"
                role="img"
                :aria-label="`Dora added ${line.stock_item_name} when it ran low`"
            >
                <BaseTooltip>Dora added this when it ran low</BaseTooltip>
            </q-icon>
        </div>

        <!-- Where you plan to buy it. -->
        <div class="sl-row__meta">
            <BaseDropdown
                v-if="storeOptions.length > 0"
                flat
                dense
                no-caps
                class="sl-row__metabtn"
            >
                <template #label>
                    <StoreLogo
                        v-if="line.planned_store_id"
                        :name="storeLabel"
                        :store-id="line.planned_store_id"
                        :height="16"
                        :width="24"
                        inline
                    />
                    <span class="ellipsis">{{ storeLabel }}</span>
                </template>
                <q-list style="min-width: 200px">
                    <!-- Always "Any store": this option means *no store
                         chosen*, never the store the ladder resolved. -->
                    <q-item
                        v-close-popup
                        clickable
                        :active="!line.planned_store_id"
                        @click="emit('planned-store', null)"
                    >
                        <q-item-section class="dora-text-muted">Any store</q-item-section>
                    </q-item>
                    <q-separator />
                    <q-item
                        v-for="opt in storeOptions"
                        :key="opt.value"
                        v-close-popup
                        clickable
                        :active="line.planned_store_id === opt.value"
                        @click="emit('planned-store', opt.value)"
                    >
                        <q-item-section avatar style="min-width: 0; padding-right: 8px">
                            <StoreLogo :name="opt.name" :store-id="opt.value" :height="20" :width="34" />
                        </q-item-section>
                        <q-item-section>{{ opt.label }}</q-item-section>
                    </q-item>
                </q-list>
                <BaseTooltip>Where you plan to buy this</BaseTooltip>
            </BaseDropdown>
        </div>

        <!-- One control for the estimate and what you paid: the figure shows
             the estimate (`~`) until a price is entered, and a tap opens the
             price sheet either way. -->
        <div v-if="moneyEnabled" class="sl-row__money">
            <BaseButton
                variant="ghost"
                dense
                class="sl-row__price"
                :class="{ 'sl-row__price--estimate': !paid }"
                :label="priceLabel"
                @click="emit('capture-price')"
            >
                <BaseTooltip>
                    {{ paid ? 'The price you entered' : 'Record what you paid' }}
                </BaseTooltip>
            </BaseButton>
        </div>

        <!-- Beside delete on a desktop (UX v5 S9), on the caption line on a
             phone; see the stylesheet. -->
        <BuyVerdictBadgeInline
            v-if="showVerdict"
            class="sl-row__verdict"
            :stock-item-id="line.stock_item_id!"
            @action="emit('verdict-action', $event)"
        />

        <div class="sl-row__actions">
            <BaseButton
                variant="danger-icon"
                size="sm"
                :icon="ICONS.delete_outline"
                aria-label="Remove from list"
                @click="emit('remove')"
            >
                <BaseTooltip>Remove from list</BaseTooltip>
            </BaseButton>
        </div>
    </div>
</template>

<script lang="ts" setup>
    /**
     * One line on an active shopping list (UX v5): the plan row and the shop
     * row merged, because an open list is built, ticked and priced in the same
     * place. Ticked rows reuse it in the Collected section with every control
     * still live, so a price can be entered after the fact.
     *
     * A grid, never a flex row: every column is fixed or `1fr` so quantity,
     * money and actions land on the same x down the page (v4 chunk 1).
     */
    import { computed, nextTick, ref, useTemplateRef } from 'vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDropdown from 'src/components/BaseDropdown.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import StoreLogo from 'src/components/StoreLogo.vue';
    import BuyVerdictBadgeInline from 'src/components/stock/BuyVerdictBadgeInline.vue';
    import LineChoicePicker from 'src/components/shoppingList/LineChoicePicker.vue';
    import { useBuyVerdictEnabled } from 'src/composables/useBuyVerdictEnabled';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import { formatMoney } from 'src/composables/useMoney';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import {
        hasLineChoices, pickedLineChoice, priceOfLine,
        type LineChoice, type ShoppingListLine,
    } from 'src/models/shoppingList';
    import type { BuyVerdict } from 'src/services/api/buyVerdictApiService';
    import { ICONS } from 'src/style/icons';

    const props = defineProps<{
        line: ShoppingListLine;
        focused: boolean;
        nested: boolean;
        productOnly: boolean;
        /** Every store. `label` is what the menu shows (the item's standing
         *  choice carries a "(usual)" marker); `name` is the bare store name
         *  the caption shows. */
        storeOptions: { value: string; label: string; name: string }[];
    }>();

    const emit = defineEmits<{
        toggle: [];
        remove: [];
        'set-quantity': [value: number];
        'planned-store': [value: string | null];
        'pick-offer': [productId: string];
        'pick-hint': [preferredBuyId: string | null];
        'verdict-action': [action: BuyVerdict['one_tap_action']['kind']];
        'capture-price': [];
    }>();

    const { moneyEnabled } = useMoneyEnabled();
    const { buyVerdictEnabled } = useBuyVerdictEnabled();
    const { products: productsEnabled } = useFeatureFlags();

    const showVerdict = computed(
        () => buyVerdictEnabled.value && !props.nested && !!props.line.stock_item_id,
    );

    // ── Quantity ──────────────────────────────────────────────────────
    const editingQty = ref(false);
    const qtyInput = useTemplateRef<HTMLInputElement>('qtyInput');

    async function onTileClick(): Promise<void> {
        editingQty.value = true;
        await nextTick();
        qtyInput.value?.focus();
        qtyInput.value?.select();
    }

    /** A quantity below one is not a quantity; the way to have none of
     *  something is the delete button. */
    function onQtyCommit(event: Event): void {
        editingQty.value = false;
        const raw = (event.target as HTMLInputElement).value.trim();
        const next = Number(raw);
        if (raw === '' || !Number.isInteger(next) || next < 1) return;
        if (next === props.line.quantity) return;
        emit('set-quantity', next);
    }

    // ── The "which one" picker ────────────────────────────────────────
    const choice = computed<LineChoice>(() => ({
        itemName: props.line.stock_item_name,
        offers: props.line.offers,
        preferredBuys: props.line.preferred_buys ?? [],
        selectedProductId: props.line.selected_product_id,
        preferredBuyId: props.line.preferred_buy_id ?? null,
    }));

    const hasChoices = computed(
        () => !props.nested && hasLineChoices(choice.value, productsEnabled.value),
    );

    const displayName = computed(
        () => pickedLineChoice(choice.value, productsEnabled.value)?.label ?? props.line.stock_item_name,
    );

    /** The parent's `pick-offer` toggles: re-sending the picked id clears it. */
    function onPickOffer(id: string | null): void {
        const next = id ?? props.line.selected_product_id;
        if (next) emit('pick-offer', next);
    }

    /** The store's bare name, never the "(usual)" marker the menu shows. */
    const storeLabel = computed(
        () => props.storeOptions.find((o) => o.value === props.line.planned_store_id)?.name
            ?? 'Any store',
    );

    // ── Price ─────────────────────────────────────────────────────────
    /** The line total, read off the server's ladder (R-003). */
    const paid = computed(() => props.line.estimate_source === 'actual');
    const priceLabel = computed(() => {
        if (props.line.estimated_unit_price == null) return 'Price';
        const money = formatMoney(priceOfLine(props.line));
        return paid.value ? money : `~${money}`;
    });
</script>

<style scoped>
    /* The grid shell, the divider and the name/money type scale live in
       `src/css/shoppingList.scss`. This block owns the active row's tracks
       and controls.

       Desktop, one line of controls (UX v5 §4):
         [tick] [qty] name / store        [price] [verdict] [delete]
       Every track is fixed or `1fr`, never content-measured, so the right-hand
       columns line up down the page. The action track is derived from the
       button metric so it can't drift from what it holds. */
    .sl-row {
        --sl-cols:
            var(--sl-tick-w) var(--sl-qty-w) minmax(0, 1fr) var(--sl-money-w)
            var(--sl-verdict-w) var(--sl-act-btn);
        --sl-tick-w: 48px;
        --sl-qty-w: 44px;
        --sl-money-w: 7rem;
        --sl-verdict-w: 6.5rem;
        --sl-act-btn: 36px;
        padding-left: var(--space-2);
    }
    @media (pointer: coarse) {
        .sl-row {
            --sl-act-btn: 44px;
        }
    }
    /* Money and the verdict both ship off by default; their columns collapse
       rather than reserving dead space. */
    .sl-row--no-money {
        --sl-money-w: 0px;
    }
    .sl-row--no-verdict {
        --sl-verdict-w: 0px;
    }

    .sl-row__tick {
        grid-column: 1;
        grid-row: 1 / span 2;
        width: 48px;
        height: 48px;
        border: 0;
        background: none;
        border-radius: var(--radius-lg);
        color: var(--text-secondary);
        cursor: pointer;
        display: grid;
        place-items: center;
        padding: 0;
    }
    .sl-row__tick:hover {
        background: var(--surface-sunken);
    }
    .sl-row__tick:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: -2px;
    }
    .sl-row__qty {
        grid-column: 2;
        grid-row: 1 / span 2;
    }
    .sl-row__namegroup {
        grid-column: 3;
        grid-row: 1;
        display: flex;
        align-items: center;
        gap: var(--space-2);
        min-width: 0;
    }
    .sl-row__meta {
        grid-column: 3;
        grid-row: 2;
    }
    .sl-row__money {
        grid-column: 4;
        grid-row: 1 / span 2;
    }
    .sl-row__verdict {
        grid-column: 5;
        grid-row: 1 / span 2;
        justify-self: end;
    }
    .sl-row__actions {
        grid-column: 6;
        grid-row: 1 / span 2;
        display: flex;
        justify-content: flex-end;
    }

    /* A ticked line is in the trolley: what describes it recedes, the
       controls that act on it do not. */
    .sl-row--ticked .sl-row__namegroup,
    .sl-row--ticked .sl-row__verdict,
    .sl-row--ticked .sl-row__meta {
        opacity: 0.6;
    }
    .sl-row--nested {
        padding-left: var(--space-6);
    }
    .sl-row--product-only {
        background: var(--surface-sunken);
    }

    /* ── Quantity ───────────────────────────────────────────────────── */
    .sl-row__tile {
        width: 44px;
        height: 44px;
        border: 1px solid transparent;
        border-radius: var(--radius-lg);
        background: var(--surface-sunken);
        color: var(--text-primary);
        font: inherit;
        font-size: var(--font-size-md);
        font-weight: 700;
        font-variant-numeric: tabular-nums;
        letter-spacing: -0.02em;
        cursor: pointer;
        display: grid;
        place-items: center;
        padding: 0;
    }
    .sl-row__tile:hover {
        border-color: var(--border-strong);
    }
    .sl-row__tile-input {
        width: 100%;
        height: 100%;
        border: 0;
        background: none;
        text-align: center;
        font: inherit;
        color: inherit;
        appearance: textfield;
        -moz-appearance: textfield;
        padding: 0;
    }
    .sl-row__tile-input::-webkit-outer-spin-button,
    .sl-row__tile-input::-webkit-inner-spin-button {
        -webkit-appearance: none;
        margin: 0;
    }

    /* ── Name + caption ─────────────────────────────────────────────── */
    /* Dora's mark at the 3:1 tier D-002 grades icons at. */
    .sl-row__automark {
        color: var(--accent-mark);
        flex: 0 0 auto;
    }
    /* The store menu reads as caption text that happens to be pressable.
       Scoped specificity beats `.q-btn`'s own min-height and padding. */
    .sl-row__metabtn {
        font-size: var(--font-size-xs);
        font-weight: 400;
        color: var(--text-secondary);
        min-height: 20px;
        padding: 0 2px;
        border-radius: var(--radius-sm);
        max-width: 100%;
        min-width: 0;
    }
    .sl-row__metabtn :deep(.q-btn__content) > span,
    .sl-row__metabtn :deep(.block) {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        min-width: 0;
    }
    .sl-row__metabtn:hover {
        background: var(--surface-sunken);
    }
    .sl-row__metabtn :deep(.q-btn__content) {
        gap: 2px;
        flex-wrap: nowrap;
    }
    .sl-row__metabtn :deep(.q-icon) {
        font-size: 13px;
    }
    .sl-row__metabtn :deep(.q-btn-dropdown__arrow) {
        margin-left: 0;
        font-size: 14px;
        opacity: 0.55;
    }

    /* ── Price ──────────────────────────────────────────────────────── */
    .sl-row__price {
        font-size: var(--font-size-lg);
        font-weight: 600;
        font-variant-numeric: tabular-nums;
        min-width: 72px;
    }
    .sl-row__price--estimate {
        color: var(--text-secondary);
        font-weight: 500;
    }

    /* ── Phone ──────────────────────────────────────────────────────
       Two lines, controls on the name's line (UX v5 S10):

         [tick] [qty] [name ··········] [~$4.50] [delete]
                      [Coles ▾ ·· verdict]

       The verdict joins the caption line as its glyph alone; the glyph
       already differs per verdict, so the word isn't the only carrier of the
       meaning (D-013) and the badge keeps its `aria-label`. */
    @media (max-width: 599px) {
        .sl-row {
            --sl-cols:
                var(--sl-tick-w) var(--sl-qty-w) minmax(0, 1fr) auto var(--sl-act-btn);
            --sl-tick-w: 44px;
            padding-left: var(--space-1);
            row-gap: 2px;
        }
        .sl-row__tick {
            width: 44px;
            height: 44px;
        }
        .sl-row__namegroup {
            grid-column: 3 / span 1;
        }
        .sl-row--no-money .sl-row__namegroup {
            grid-column: 3 / span 2;
        }
        /* The shared `.sl-row__money` floor (6rem) is a desktop column
           width; here it would take the name's room. */
        .sl-row__money {
            grid-column: 4;
            grid-row: 1;
            justify-self: end;
            min-width: 0;
        }
        .sl-row__price {
            font-size: var(--font-size-md);
            min-width: 0;
            padding-inline: var(--space-1);
        }
        .sl-row__actions {
            grid-column: 5;
            grid-row: 1;
        }
        .sl-row__meta {
            grid-column: 3;
            grid-row: 2;
            flex-wrap: nowrap;
            overflow: hidden;
        }
        .sl-row__verdict {
            grid-column: 4 / span 2;
            grid-row: 2;
            justify-self: end;
        }
        .sl-row__verdict :deep(.q-chip__content) {
            display: none;
        }
        .sl-row__verdict :deep(.q-chip__icon) {
            margin: 0;
        }
        .sl-row--nested {
            padding-left: var(--space-4);
        }
    }
</style>
