<template>
    <div
        class="sl-row sl-row--hoverable"
        :class="{
            'sl-row--reorderable': canReorder,
            'sl-row--ticked': line.is_ticked,
            'sl-row--focused': focused,
            'sl-row--nested': nested,
            'sl-row--product-only': productOnly,
            'sl-row--no-money': !moneyEnabled,
            'sl-row--priced': moneyEnabled && price > 0,
        }"
    >
        <!-- Decorative grip only — the whole row is the draggable element
             (R-022, whole-row mode). Hidden on touch, where pointer DnD does
             not exist and the arrows in the action cell are the real path. -->
        <div v-if="canReorder" class="sl-row__grip dora-dnd-handle">
            <q-icon :name="ICONS.drag_indicator" size="16px" />
            <BaseTooltip>Drag to reorder</BaseTooltip>
        </div>

        <!-- Quantity. A tile at rest, a stepper on approach where there is a
             pointer to approach with (owner call 2026-08-31). The stepper
             buttons are always in the layout and only their opacity changes,
             so revealing them cannot reflow the row.

             No stepper on touch (owner, 2026-09-27). The buttons sat either
             side of the tile at `opacity: 0` and were still live, so a tap
             beside the number changed it with nothing visible under the thumb.
             A tap on the tile opens the number field instead, which is one
             tap rather than the old arm-then-tap. -->
        <div class="sl-row__qty">
            <BaseButton
                variant="icon"
                size="sm"
                class="sl-row__step"
                :icon="ICONS.remove"
                aria-label="One fewer"
                :disable="lineDone || (line.quantity ?? 1) <= 1"
                @click="emit('adjust-quantity', -1)"
            />
            <button
                type="button"
                class="sl-row__tile"
                :disabled="lineDone"
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
            <BaseButton
                variant="icon"
                size="sm"
                class="sl-row__step"
                :icon="ICONS.add"
                aria-label="One more"
                :disable="lineDone"
                @click="emit('adjust-quantity', 1)"
            />
        </div>

        <!-- The name leads, at the size of the thing you actually read. It was
             losing to a larger money figure and three chip variants; the
             metadata below it is now typographically subordinate rather than
             competing.

             The `.sl-row__main` wrapper is gone (2026-09-17). It was a box
             holding three stacked children inside a *single* grid cell, which
             is what made the phone layout impossible to fix: the cell measured
             123px at 375px while its contents measured 219px, and a wrapper
             can't hand its children to a different column. Every cell is placed
             explicitly on the grid now — the same shape `ShoppingListReceiptRow`
             already uses, so the two faces reason about their rows the same way. -->
        <div class="sl-row__namerow">
            <!-- Name and Dora's mark travel together: on a phone the name row
                 dissolves into the grid so the verdict can drop under the
                 quantity, and the mark must stay beside the name it
                 qualifies. -->
            <div class="sl-row__namegroup">
                <!-- The "which one" picker; see `LineChoicePicker`. An item
                     with nothing to choose from is plain text, the common
                     case. -->
                <LineChoicePicker
                    v-if="hasChoices"
                    :choice="choice"
                    :disable="lineDone"
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
                <!-- Only on lines nothing the user did put here: the low-stock
                     trigger dropped them on while they were elsewhere in the
                     app. Burger not wand: the wand means "a model is involved"
                     and a stock rule isn't one (2026-09-19). -->
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
            <BuyVerdictBadgeInline
                v-if="!nested && line.stock_item_id"
                class="sl-row__verdict"
                :stock-item-id="line.stock_item_id"
                @action="emit('verdict-action', $event)"
            />
        </div>

        <!-- One caption line, and now only one thing on it: where you plan
             to buy this. The buy-hint menu moved onto the name (above), and
             the two notes that used to sit here went entirely (2026-09-17):
             "last paid at Northside Farmers Market" and "from what you last
             paid" narrated the provenance of a number printed beside them, on
             every row, forever. -->
        <div class="sl-row__meta">
            <BaseDropdown
                v-if="storeOptions.length > 0"
                flat
                dense
                no-caps
                class="sl-row__metabtn"
                :disable="lineDone"
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
                    <!-- Always "Any store", never the resolved store's name.
                         This option means *no store chosen*; labelling it with
                         whatever the ladder resolved is what made "any" and
                         "usual" read as the same setting. -->
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

        <!-- Money reads as type, not as a control: a draft price is a
             server-resolved estimate, and the thing that edits it is the shop
             face. Tabular so the column scans down the list.

             Its own column on a desktop, its own line under the name on a
             phone — see the stylesheet. -->
        <!-- The figure, and nothing under it. "from your last receipt" /
             "from Coles offer" was a second line on every priced row
             explaining where a number came from, when the number is editable
             and the answer doesn't change what you'd do (2026-09-17). -->
        <div v-if="moneyEnabled && price > 0" class="sl-row__money">
            <div class="sl-row__amount">~{{ formatMoney(price) }}</div>
        </div>

        <!-- Reorder sits next to delete on a desktop and moves to the row's
             second line on a phone, so it is its own cell rather than two more
             buttons inside the delete cell. At the D-004 touch size three
             buttons in one cell claim 140px of a 375px row and leave the name
             145px, which wraps it under its own Buy chip — the arrows are the
             least urgent control on the row and the one that can move.

             Revealed on approach where there is a pointer; always present
             where there isn't, because hover-only is a loss on touch and the
             arrows are the only reorder path a thumb has. -->
        <div v-if="canReorder" class="sl-row__reorder">
            <BaseButton
                variant="icon"
                size="sm"
                class="sl-row__act"
                :icon="ICONS.collapse"
                aria-label="Move up"
                :disable="isFirst"
                @click="emit('move', -1)"
            >
                <BaseTooltip>Move up</BaseTooltip>
            </BaseButton>
            <BaseButton
                variant="icon"
                size="sm"
                class="sl-row__act"
                :icon="ICONS.expand"
                aria-label="Move down"
                :disable="isLast"
                @click="emit('move', 1)"
            >
                <BaseTooltip>Move down</BaseTooltip>
            </BaseButton>
        </div>

        <div class="sl-row__actions">
            <BaseButton
                variant="danger-icon"
                size="sm"
                :icon="ICONS.delete_outline"
                aria-label="Remove from list"
                :disable="lineDone"
                @click="emit('remove')"
            >
                <BaseTooltip>Remove from list</BaseTooltip>
            </BaseButton>
        </div>
    </div>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    /**
     * One line on the shopping list's plan face.
     *
     * Extracted from `ShoppingListDetail.vue` (v4 chunk 1), where it was an
     * inline `q-item` laying out with flex against four competing `min-width`
     * floors — name `flex: 1 1 0`, quantity 150px, store select 132px, price
     * button 96px. Because nothing shared a column, every row measured itself
     * and the money, quantity and store positions drifted by name length. That
     * is the whole of the "elements all over the place, misaligned and weirdly
     * offset" report, and it is why this is a **grid** rather than a tidier
     * flex row.
     *
     * `q-item` is gone on purpose (R-001 / v4 §5). It ships its own padding,
     * min-heights and `--side` alignment rules, and the page's stylesheet was
     * already spending a whole media block undoing them — building a new
     * surface on top of that would have landed as "slightly nicer than before".
     * The row owns its own structure now, the same trade `CollapsibleCard`
     * makes.
     *
     * Nothing was cut. Every affordance catalogued in
     * `05_investigations/SHOPPING_LIST_BASELINE.md` §5.1 is still here; three
     * moved: the store select became a menu button on the caption line, the
     * three chip variants became caption text, and the reorder arrows joined
     * delete instead of forming a stacked column of their own.
     */
    import { computed, nextTick, ref, useTemplateRef } from 'vue';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import { ICONS } from 'src/style/icons';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDropdown from 'src/components/BaseDropdown.vue';
    import BuyVerdictBadgeInline from 'src/components/stock/BuyVerdictBadgeInline.vue';
    import StoreLogo from 'src/components/StoreLogo.vue';
    import { formatMoney } from 'src/composables/useMoney';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import LineChoicePicker from 'src/components/shoppingList/LineChoicePicker.vue';
    import {
        hasLineChoices, pickedLineChoice, type LineChoice, type ShoppingListLine,
    } from 'src/models/shoppingList';
    import type { BuyVerdict } from 'src/services/api/buyVerdictApiService';

    const props = defineProps<{
        line: ShoppingListLine;
        /** The list is finished — every mutation on the row is closed. */
        lineDone: boolean;
        canReorder: boolean;
        isFirst: boolean;
        isLast: boolean;
        focused: boolean;
        nested: boolean;
        productOnly: boolean;
        /** Server-resolved line estimate; the row never derives it (R-003). */
        price: number;
        /** Every store. `label` is what the menu shows (the item's standing
         *  choice carries a "(usual)" marker); `name` is the bare store name
         *  the caption shows. The "no choice" option is the row's own, and
         *  always reads "Any store" — see the template. */
        storeOptions: { value: string; label: string; name: string }[];
    }>();

    const emit = defineEmits<{
        move: [delta: -1 | 1];
        remove: [];
        'adjust-quantity': [delta: -1 | 1];
        'set-quantity': [value: number | null];
        'planned-store': [value: string | null];
        'pick-offer': [productId: string];
        'pick-hint': [preferredBuyId: string | null];
        'verdict-action': [action: BuyVerdict['one_tap_action']['kind']];
    }>();

    const { moneyEnabled } = useMoneyEnabled();
    const { products: productsEnabled } = useFeatureFlags();

    // ── Quantity ──────────────────────────────────────────────────────
    const editingQty = ref(false);
    const qtyInput = useTemplateRef<HTMLInputElement>('qtyInput');

    async function onTileClick(): Promise<void> {
        if (props.lineDone) return;
        editingQty.value = true;
        await nextTick();
        qtyInput.value?.focus();
        qtyInput.value?.select();
    }

    /** A quantity below one is not a quantity (owner, 2026-09-27); the way
     *  to have none of something is the delete button. Anything else that
     *  isn't a whole number ≥ 1 is dropped rather than guessed at. */
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

    /** What the row calls this line: the thing you picked, else the item's
     *  own name. One name per row, never a name plus a chip naming it again. */
    const displayName = computed(
        () => pickedLineChoice(choice.value, productsEnabled.value)?.label ?? props.line.stock_item_name,
    );

    /** The parent's `pick-offer` toggles: re-sending the picked id clears it. */
    function onPickOffer(id: string | null): void {
        const next = id ?? props.line.selected_product_id;
        if (next) emit('pick-offer', next);
    }

    /** The caption shows the store's *name* — never the "(usual)" marker. That
     *  suffix exists to point out the standing choice while you are choosing;
     *  on the row it would assert something about this line that isn't true of
     *  it ("Coles (usual)" reads as a kind of store), and it would be on most
     *  rows, since the usual store is what a line is prefilled with. */
    const storeLabel = computed(
        () => props.storeOptions.find((o) => o.value === props.line.planned_store_id)?.name
            ?? 'Any store',
    );
</script>

<style scoped>
    /* The grid shell, the divider and the name/money type scale live in
       `src/css/shoppingList.scss` — the receipt face is built on the same
       skeleton (v4 chunk 3). What this block owns is the plan face's own
       track list and its controls.

       The quantity and action cells are sized for their *revealed* state, so
       a hover reveals opacity and nothing else. Reserving that space is
       deliberate: a reveal that reflowed the row would put the misalignment
       back as a motion bug. */
    /* Four tracks on a desktop: quantity, name, money, actions — and every one
       of them fixed or `1fr`, never content-measured, so the three right-hand
       columns land on the same x down the whole page.

       The action track is **derived from the button metric** rather than typed
       as a number (2026-09-17). It was a literal `104px` holding three 36px
       buttons and two 4px gaps — 116px of content in a 104px cell — so the
       first reorder arrow rendered 12px outside its own column, on top of the
       money. Under `pointer: coarse` `BaseButton` raises every icon button to
       the D-004 floor of 44px, which took the same cell to 140px: the overlap
       the owner reported on a phone was the desktop bug, twice as bad, on the
       one device where the arrows are never hidden by `opacity`. A width
       written as an arithmetic fact of what it holds cannot drift from it
       again. */
    .sl-row {
        --sl-cols:
            var(--sl-qty-w) minmax(0, 1fr) var(--sl-money-w)
            var(--sl-reorder-w) var(--sl-act-btn);
        --sl-qty-w: 104px;
        --sl-money-w: 7rem;
        --sl-act-btn: 36px;
        --sl-reorder-w: 0px;
    }
    @media (pointer: coarse) {
        .sl-row {
            --sl-act-btn: 44px;
        }
    }
    /* The money column is fixed, not `auto` — `auto` measured the longest of
       "~$5.80" and "from your last receipt" *per row*, which is why the figures
       sat at x=850 on one line and x=869 on the next.

       Reserved even on a row with no price, so the column holds down the page;
       collapsed entirely when the *install* has no money, which is the default
       and not an edge case (both flags ship off in `health_check.py`). */
    .sl-row--no-money {
        --sl-money-w: 0px;
    }

    /* ── Placement ───────────────────────────────────────────────────
       Stated for every cell, on both breakpoints, because the row is now flat:
       the name, caption and offers are grid children in their own right rather
       than three things stacked inside one cell. */
    .sl-row__qty {
        grid-column: 1;
        grid-row: 1 / span 3;
    }
    .sl-row__namerow {
        grid-column: 2;
        grid-row: 1;
    }
    .sl-row__meta {
        grid-column: 2;
        grid-row: 2;
    }
    /* `span 3`, not `1 / -1`: this grid declares no `grid-template-rows`, so
       every row is implicit and a negative line number resolves against an
       explicit grid that is one line long — `1 / -1` silently collapses to a
       single row. That pinned row 1 to the 44px quantity tile and added 18px
       of dead air above every caption. Spanning past the last row is safe;
       empty implicit rows have no height. */
    .sl-row__money {
        grid-column: 3;
        grid-row: 1 / span 3;
    }
    .sl-row__reorder {
        grid-column: 4;
        grid-row: 1 / span 3;
    }
    .sl-row__actions {
        grid-column: 5;
        grid-row: 1 / span 3;
    }
    /* The grip is absolutely positioned in the row's own left padding rather
       than taking a grid column. It was a fifth column, hidden by
       `@media (hover: none)` while the column count changed on
       `max-width: 599px` — two different conditions for one layout, so a
       375px hover-capable viewport rendered five children into four columns
       and the quantity tile landed on top of the caption. Out of the grid,
       that class of mismatch cannot happen again. */
    .sl-row--reorderable {
        padding-left: calc(var(--space-4) + 16px);
        --sl-reorder-w: calc(var(--sl-act-btn) * 2 + var(--space-1) * 3);
    }
    /* A ticked line on the plan face is history; the cells that describe it
       recede, the controls that act on it do not. (It was one `opacity` on the
       wrapper that no longer exists.) */
    .sl-row--ticked .sl-row__namegroup,
    .sl-row--ticked .sl-row__verdict,
    .sl-row--ticked .sl-row__meta,
    .sl-row--ticked .sl-row__money {
        opacity: 0.6;
    }
    .sl-row--nested {
        padding-left: var(--space-8);
    }
    .sl-row--product-only {
        background: var(--surface-sunken);
    }

    .sl-row__grip {
        position: absolute;
        left: var(--space-1);
        top: 0;
        bottom: 0;
        width: 18px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--text-muted);
        opacity: 0;
        transition: opacity var(--motion-fast, 120ms) var(--motion-ease, ease);
    }

    /* ── Quantity ───────────────────────────────────────────────────── */
    .sl-row__qty {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: var(--space-1);
    }
    .sl-row__step {
        opacity: 0;
        transition: opacity var(--motion-fast, 120ms) var(--motion-ease, ease);
    }
    .sl-row__tile {
        width: 44px;
        height: 44px;
        flex: none;
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
    .sl-row__tile:hover:not(:disabled) {
        border-color: var(--border-strong);
    }
    .sl-row__tile:disabled {
        cursor: default;
        opacity: 0.6;
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
    .sl-row__namerow {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        flex-wrap: wrap;
        min-width: 0;
    }
    .sl-row__namegroup {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        min-width: 0;
    }
    /* Dora's mark sits with the name, at caption ink so it never competes
       with the thing you're reading. `--accent-mark` is the 3:1 tier D-002
       grades icons at; `--text-muted` would put a 12px glyph under the floor
       (D-003 bans muted ink for anything that carries meaning). */
    .sl-row__automark {
        color: var(--accent-mark);
        flex: 0 0 auto;
    }
    /* The verdict badge is pushed to the far end of the name row rather than
       sitting flush against the title: it's an opinion about the item, not
       part of its name, and the mark now occupies the slot beside the name. */
    .sl-row__verdict {
        margin-left: auto;
    }
    /* The two menu buttons on the caption line read as caption text that
       happens to be pressable — they were an outlined select and a bordered
       dropdown, i.e. two more boxes on a row that had too many.

       Quasar's `.q-btn` ships `min-height: 2.572em`, its own padding and a
       `q-btn-dropdown` caret sized for a real button. Left alone they stayed
       button-shaped and the caption line still read as a row of form
       controls — the exact "slightly nicer than before" outcome v4 §5 warns
       about. Scoped specificity beats `.q-btn`, so these land. */
    .sl-row__metabtn {
        font-size: var(--font-size-xs);
        font-weight: 400;
        color: var(--text-secondary);
        min-height: 20px;
        padding: 0 2px;
        border-radius: var(--radius-sm);
        /* A `q-btn` sizes to its label and will not shrink, so a long buy hint
           ("Sideways Roasters house blend, whole bean" measures 291px) used to
           push the whole caption line out through the side of its column. The
           caption is subordinate type: it truncates. */
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
    /* The caret is the only thing saying "there are options", so it stays —
       but at the weight of a caption, not of a select. */
    .sl-row__metabtn :deep(.q-btn-dropdown__arrow) {
        margin-left: 0;
        font-size: 14px;
        opacity: 0.55;
    }
    /* ── Actions ────────────────────────────────────────────────────── */
    .sl-row__reorder,
    .sl-row__actions {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: var(--space-1);
    }
    .sl-row__act {
        opacity: 0;
        transition: opacity var(--motion-fast, 120ms) var(--motion-ease, ease);
    }

    /* Reveal-on-approach, but only where there is something to approach with.
       On touch the reorder arrows are permanently visible (they are a thumb's
       only reorder path) and the stepper doesn't exist at all — `display:
       none`, not `opacity: 0`, because an invisible button is still a live
       one. */
    @media (hover: hover) {
        .sl-row:hover .sl-row__grip,
        .sl-row:focus-within .sl-row__grip,
        .sl-row:hover .sl-row__act,
        .sl-row:focus-within .sl-row__act,
        .sl-row:hover .sl-row__step,
        .sl-row:focus-within .sl-row__step {
            opacity: 1;
        }
    }
    @media (hover: none) {
        .sl-row__act {
            opacity: 1;
        }
        .sl-row__grip,
        .sl-row__step {
            display: none;
        }
        .sl-row {
            --sl-qty-w: 44px;
        }
    }

    @media (prefers-reduced-motion: reduce) {
        .sl-row__grip,
        .sl-row__act,
        .sl-row__step {
            transition: none;
        }
    }

    /* ── Phone ──────────────────────────────────────────────────────
       Two lines, laid out the way the owner drew them (2026-09-27):

         [qty] [name ▾ ················] [~$4.50]
         [Buy] [Coles ▾ ·········] [↑] [↓] [🗑]

       Line one is the thing and what it costs; line two is where you'll buy it
       and the controls that move or remove it. The verdict sits under the
       quantity tile, which is the one cell on line two with nothing in it.
       It was pushing the name off its own line from the far end of the name
       row. The name row dissolves (`display: contents`) so its two children
       can land in different cells; the name keeps Dora's mark beside it
       because they share `.sl-row__namegroup`.

       Four tracks: quantity, a flexible middle, the reorder pair, delete. The
       money spans the last two on line one, so it right-aligns over the
       controls whether or not the list can be reordered. */
    @media (max-width: 599px) {
        .sl-row {
            --sl-cols: var(--sl-qty-w) minmax(0, 1fr) auto var(--sl-act-btn);
            --sl-qty-w: 44px;
            row-gap: var(--space-1);
        }
        .sl-row__step {
            display: none;
        }
        .sl-row--reorderable {
            padding-left: calc(var(--space-3) + 14px);
        }
        .sl-row__qty {
            grid-column: 1;
            grid-row: 1;
        }
        .sl-row__namerow {
            display: contents;
        }
        .sl-row__namegroup {
            grid-column: 2 / -1;
            grid-row: 1;
        }
        .sl-row--priced .sl-row__namegroup {
            grid-column: 2;
        }
        .sl-row__money {
            grid-column: 3 / -1;
            grid-row: 1;
            justify-self: end;
            text-align: right;
        }
        /* Icon-only on a phone: the cell is the 44px quantity track, and the
           glyph already differs per verdict (cart / clock / cross / ?), so the
           word is not the only carrier of the meaning (D-013). The badge
           states its label as an `aria-label` for the same reason. */
        .sl-row__verdict {
            grid-column: 1;
            grid-row: 2;
            justify-self: center;
            margin: 0;
        }
        .sl-row__verdict :deep(.q-chip__content) {
            display: none;
        }
        .sl-row__verdict :deep(.q-chip__icon) {
            margin: 0;
        }
        .sl-row__meta {
            grid-column: 2;
            grid-row: 2;
            flex-wrap: nowrap;
            overflow: hidden;
        }
        .sl-row__reorder {
            grid-column: 3;
            grid-row: 2;
        }
        .sl-row__actions {
            grid-column: 4;
            grid-row: 2;
        }
        .sl-row--nested {
            padding-left: var(--space-6);
        }
    }
</style>
