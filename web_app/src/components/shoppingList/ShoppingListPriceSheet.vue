<template>
    <!-- The line editor for the run and receipt faces. A bottom sheet, not
         a popover: mid-shop the phone is one-handed and the keyboard eats
         the top half of the screen, so the fields have to sit where a thumb
         already is. One editor, both faces — the receipt's Amend reuses it
         rather than growing a second form.

         2026-08-28: it now carries **quantity** too. It was price-only, so
         the one thing you routinely discover at the shelf — "they only had
         the 2-pack", "grab three while they're on special" — could not be
         recorded without leaving the list. -->
    <BaseDialog
        v-model="priceSheetOpen"
        position="bottom"
        card-class="sld-price-sheet"
        card-style="width: 100%; max-width: 520px"
        :title="priceSheetLine?.stock_item_name ?? 'Price'"
        closable
    >
        <q-card-section class="sld-price-sheet__body">
            <!-- "Price each", not "Price per unit" (owner, 2026-09-17:
                 *"What unit? I haven't told you and I can't see what
                 you're assuming"*). The honest answer is that it was never
                 a measurement unit: this value is the price of **one of
                 them**, and the line total is it × quantity. Nothing here
                 needs a gram or a litre — which is exactly why this sheet
                 looks different from the *log a price* form, where the
                 number becomes a price-per-100g observation in the item's
                 history and a measure is unavoidable. Two records, two
                 shapes; the label was the only thing lying about it. -->
            <!-- FU-890: the shared price field. Not dense here: the sheet
                 is a focused one-field moment, so it keeps the full height. -->
            <MoneyInput
                v-model="priceEditorDraft.price"
                :dense="false"
                autofocus
                label="Price each"
                input-class="sld-price-sheet-input"
                @keydown.enter.prevent="savePriceSheet"
            />
            <!-- The arithmetic said out loud, so "each" needs no
                 explaining once you have typed a quantity above one. -->
            <div v-if="priceSheetLineTotal" class="text-caption dora-text-muted sld-price-sheet__total">
                {{ priceEditorDraft.quantity ?? 1 }} × {{ fmtMoney(priceEditorDraft.price ?? 0) }}
                = <strong>{{ priceSheetLineTotal }}</strong>
            </div>

            <!-- Pulling an offer in is an *act*, not an assumption
                 (2026-09-17). Offers stopped prefilling prices anywhere —
                 an advertised number is the shop's claim, not your money —
                 so this is the one place one becomes a price, by tapping
                 it, at the shelf, where you can see whether it's true. -->
            <div v-if="priceSheetOffers.length > 0" class="sld-price-sheet__offers">
                <div class="text-caption dora-text-muted">Seen at</div>
                <div class="row q-gutter-xs">
                    <q-chip
                        v-for="offer in priceSheetOffers"
                        :key="offer.product_id"
                        clickable
                        outline
                        dense
                        @click="useOfferPrice(offer)"
                    >
                        <StoreLogo
                            :name="offer.store_name"
                            :store-id="offer.store_id"
                            :height="16"
                            :width="24"
                            inline
                        />
                        {{ fmtMoney(offer.price_now ?? 0) }} at {{ offer.store_name }}
                        <BaseTooltip>Use this as the price each</BaseTooltip>
                    </q-chip>
                </div>
            </div>

            <!-- Stepper rather than a number field: a second keyboard on a
                 sheet that already has one open is a worse target than two
                 44px buttons (D-004), and quantities here are ±1 in
                 practice. -->
            <div class="row items-center q-gutter-sm">
                <span class="col dora-text-secondary">Quantity</span>
                <BaseButton
                    variant="icon"
                    :icon="ICONS.remove"
                    aria-label="One fewer"
                    :disable="(priceEditorDraft.quantity ?? 1) <= 1"
                    @click="priceEditorDraft.quantity = Math.max(1, (priceEditorDraft.quantity ?? 1) - 1)"
                />
                <span class="sld-sheet-qty">{{ priceEditorDraft.quantity ?? 1 }}</span>
                <BaseButton
                    variant="icon"
                    :icon="ICONS.add"
                    aria-label="One more"
                    @click="priceEditorDraft.quantity = (priceEditorDraft.quantity ?? 1) + 1"
                />
            </div>
            <BaseSelect
                v-if="allStoreOptions.length > 0"
                v-model="priceEditorDraft.store_id"
                :options="allStoreOptions"
                emit-value
                map-options
                clearable
                label="Bought from"
            >
                <template #option="{ opt, itemProps }">
                    <q-item v-bind="itemProps">
                        <q-item-section avatar style="min-width: 0; padding-right: 8px">
                            <StoreLogo :name="opt.label" :store-id="opt.value" :height="20" :width="34" />
                        </q-item-section>
                        <q-item-section>{{ opt.label }}</q-item-section>
                    </q-item>
                </template>
            </BaseSelect>
        </q-card-section>
        <template #actions>
            <BaseButton
                v-if="priceSheetLine && priceSheetLine.actual_unit_price != null"
                variant="danger-ghost"
                label="Clear"
                @click="clearPriceSheet"
            />
            <BaseButton variant="ghost" label="Cancel" v-close-popup />
            <BaseButton variant="primary" label="Save" @click="savePriceSheet" />
        </template>
    </BaseDialog>
</template>

<script lang="ts" setup>
    /**
     * The line editor for the run and receipt faces — price each, quantity and
     * bought-from, as a bottom sheet. Extracted from `ShoppingListDetail.vue`
     * (FU-780) with its draft and save path; the page opens it through
     * `show(line)`.
     */
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import BaseSelect from 'src/components/BaseSelect.vue';
    import MoneyInput from 'src/components/MoneyInput.vue';
    import StoreLogo from 'src/components/StoreLogo.vue';
    import { ICONS } from 'src/style/icons';
    import { formatMoney } from 'src/composables/useMoney';
    import { useShoppingListDetail } from 'src/composables/useShoppingListDetail';
    import {
        chosenOfferFor,
        type LineProductOffer,
        type ShoppingListLine,
    } from 'src/models/shoppingList';
    import type { UpdateLineCommand } from 'src/services/api/shoppingListApiService';
    import { useStoresStore } from 'src/stores/storesStore';
    import { isAlreadyNotified, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useQuasar } from 'quasar';
    import { computed, reactive, ref } from 'vue';

    const $q = useQuasar();
    const {
        api, listId, detail, setLineQuantity, refreshDetailQuietly,
    } = useShoppingListDetail();

    // Every store the household has — "Bought from" offers them all. The page
    // loads the store on mount (R-016 lazy hydration).
    const storesStore = useStoresStore();
    const allStoreOptions = computed(() =>
        storesStore.stores.map((s) => ({ value: s.store_id, label: s.name })),
    );

    function fmtMoney(v: number | null | undefined): string {
        return formatMoney(v ?? 0);
    }

    // ── P2-02: actual price + merchant override ─────────────────────────
    // A small popover sits behind the price button on each line. Users tap
    // it mid-shop or at finish time to type what the till actually charged
    // and (optionally) confirm which merchant they bought from. Both flow
    // into the assistant's purchase-history stats.
    const priceEditorDraft = reactive<{
        line_id: string | null;
        price: number | null;
        store_id: string | null;
        quantity: number | null;
    }>({ line_id: null, price: null, store_id: null, quantity: null });

    function onOpenPriceEditor(line: ShoppingListLine) {
        priceEditorDraft.line_id = line.line_id;
        // Seed with the existing override, else the server-resolved prefill
        // (D3: prior receipt, else chosen offer — source-labelled), so the
        // common case is "confirm one number".
        // The server's money ladder (actual → picked offer → what you last
        // paid) already names the best number, so the sheet reads it rather
        // than re-ranking. The old `?? chosenOfferFor(line)` fallback let the
        // *cheapest* offer prefill a price nobody picked, which 2026-09-17 had
        // ruled out everywhere else.
        priceEditorDraft.price = line.estimated_unit_price ?? null;
        // Seed from the server-resolved store, not just the offer's: since the
        // picker below widened to the resolved / last-paid stores, seeding only
        // from an offer left a products-free user looking at an option list with
        // nothing selected.
        // Prefill chain, per the store ladder: bought-from wins, else whatever
        // the ladder resolved (which is now the list's planned store before the
        // item's usual one), else the offer's. Each rung is a *default* for the
        // next — nothing is written back up the chain, so buying somewhere once
        // never rewrites where you plan or usually shop.
        priceEditorDraft.store_id =
            line.purchased_store_id
            ?? line.resolved_store_id
            ?? chosenOfferFor(line)?.store_id
            ?? null;
        priceEditorDraft.quantity = line.quantity ?? 1;
    }

    function storeOptionsFor(line: ShoppingListLine) {
        const seen = new Map<string, string>();
        // Offers are the power-user case. Someone who has never linked a
        // product still has a resolved store (their usual, or where they last
        // bought it), and without these the picker was empty for them — which
        // made "Bought from" invisible on exactly the installs the money ladder
        // was rebuilt to serve.
        const candidates: [string | null, string | null][] = [
            [line.purchased_store_id, line.purchased_store_name],
            [line.resolved_store_id, line.resolved_store_name],
            [line.last_paid_store_id, line.last_paid_store_name],
            ...line.offers.map(
                (o) => [o.store_id, o.store_name] as [string | null, string | null]
            ),
        ];
        for (const [id, name] of candidates) {
            if (id && name && !seen.has(id)) seen.set(id, name);
        }
        return Array.from(seen, ([value, label]) => ({ value, label }));
    }

    async function savePriceEditor(line: ShoppingListLine) {
        if (priceEditorDraft.line_id !== line.line_id) return;
        const nextPrice = priceEditorDraft.price;
        const nextStore = priceEditorDraft.store_id;
        // Empty/zero/negative input clears the *price* rather than storing a
        // meaningless number. The backend rejects negatives anyway; this saves
        // the round-trip.
        if (nextPrice == null || Number.isNaN(nextPrice) || nextPrice <= 0) {
            // ...but only the price. This used to call `clearPriceOverride`,
            // which clears the price *and* the store — so picking "Bought
            // from" on a line you hadn't priced saved nothing at all, and the
            // row stayed in its old bucket under Order-by → Store. That is
            // FU-769, reported in August as a refresh gap and confirmed live
            // on 2026-09-17 to be this: the store never reached the server.
            // Two fields, two decisions; a blank price is not an instruction
            // about the store.
            if (nextStore) {
                await saveStoreOnly(line, nextStore);
            } else {
                await clearPriceOverride(line);
            }
            return;
        }
        await writeLinePurchase(
            line,
            { price: nextPrice, storeId: nextStore ?? null },
            {
                actual_unit_price: nextPrice,
                ...(nextStore
                    ? { purchased_store_id: nextStore }
                    : { clear_purchased_store: true }),
            },
            'Could not save the price.',
        );
    }

    /** The one optimistic write for a line's price and bought-from store:
     *  show the new pair, send `command`, and put the old pair back (with
     *  `failMessage`) if the server refuses (03-R19). */
    async function writeLinePurchase(
        line: ShoppingListLine,
        next: { price: number | null; storeId: string | null },
        command: UpdateLineCommand,
        failMessage: string,
    ) {
        const previous = {
            price: line.actual_unit_price,
            storeId: line.purchased_store_id,
            storeName: line.purchased_store_name,
        };
        line.actual_unit_price = next.price;
        line.purchased_store_id = next.storeId;
        line.purchased_store_name = next.storeId
            ? storeOptionsFor(line).find((o) => o.value === next.storeId)?.label ?? null
            : null;
        try {
            await api.updateLineAsync(listId.value, line.line_id, command);
        } catch (err) {
            line.actual_unit_price = previous.price;
            line.purchased_store_id = previous.storeId;
            line.purchased_store_name = previous.storeName;
            if (!isAlreadyNotified(err)) {
                $q.notify({ type: 'negative', message: failMessage, caption: toastCaption(err) });
            }
        }
    }

    // ── Price capture sheet (run + receipt faces) ───────────────────────
    // Same draft and the same save path as the plan face's popover — only the
    // container differs, because the ergonomics do. Both faces then reload:
    // the money ladder and the store breakdown are server-owned (R-003), so
    // after a price lands the client asks for the new numbers rather than
    // guessing which rung the server would now pick.
    const priceSheetLine = ref<ShoppingListLine | null>(null);
    const priceSheetOpen = ref(false);

    function openPriceSheet(line: ShoppingListLine) {
        onOpenPriceEditor(line);
        priceSheetLine.value = line;
        priceSheetOpen.value = true;
    }

    async function savePriceSheet() {
        const line = priceSheetLine.value;
        if (!line) return;
        priceSheetOpen.value = false;
        // Quantity first and separately: it is the one field here that is not
        // part of the price/store pair, and `savePriceEditor` short-circuits to
        // `clearPriceOverride` when the price is blank — which would silently
        // drop a quantity edit made on a line the user never priced.
        const nextQuantity = priceEditorDraft.quantity;
        if (nextQuantity != null && nextQuantity !== (line.quantity ?? 1)) {
            await setLineQuantity(line, nextQuantity);
        }
        await savePriceEditor(line);
        await refreshDetailQuietly();
    }

    /** Record where a line was bought without claiming what it cost.
     *
     *  The honest state for "I picked this up at Aldi but didn't note the
     *  price": the store is a fact the user gave, the price is one they
     *  didn't, and a price the user never typed must not survive as an
     *  override. Optimistic like its siblings, and rolled back the same way.
     */
    async function saveStoreOnly(line: ShoppingListLine, storeId: string) {
        await writeLinePurchase(
            line,
            { price: null, storeId },
            { clear_actual_unit_price: true, purchased_store_id: storeId },
            'Could not save the store.',
        );
    }

    /** The line's offers, only while they can still be acted on. A receipt is
     *  a record: what a shop is advertising today has nothing to say about a
     *  trip that already happened. */
    const priceSheetOffers = computed(() => {
        if (!priceSheetLine.value || detail.value?.status === 'done') return [];
        return priceSheetLine.value.offers.filter((o) => o.price_now != null);
    });

    /** Only once there is more than one of them — at quantity 1 the line total
     *  and the price each are the same number, and printing it twice explains
     *  nothing. */
    const priceSheetLineTotal = computed(() => {
        const price = priceEditorDraft.price;
        const qty = priceEditorDraft.quantity ?? 1;
        if (price == null || Number.isNaN(price) || price <= 0 || qty <= 1) return null;
        return fmtMoney(price * qty);
    });

    function useOfferPrice(offer: LineProductOffer): void {
        if (offer.price_now == null) return;
        priceEditorDraft.price = offer.price_now;
        // The offer names a store as surely as it names a price, and the two
        // arriving together is the point — you are recording one purchase.
        priceEditorDraft.store_id = offer.store_id;
    }

    async function clearPriceSheet() {
        const line = priceSheetLine.value;
        if (!line) return;
        priceSheetOpen.value = false;
        await clearPriceOverride(line);
        await refreshDetailQuietly();
    }

    async function clearPriceOverride(line: ShoppingListLine) {
        if (line.actual_unit_price == null && line.purchased_store_id == null) return;
        await writeLinePurchase(
            line,
            { price: null, storeId: null },
            { clear_actual_unit_price: true, clear_purchased_store: true },
            'Could not clear the price.',
        );
    }

    defineExpose({ show: openPriceSheet });
</script>

<style scoped>
    /* One rhythm down the sheet. It had none: `q-card-section` brought its own
       16px top padding which the field's own `q-pt-none` then cancelled, so the
       price input sat flush against the title, then `q-mt-md` opened a 16px gap
       before Quantity and `q-mt-sm` left 8px before the store — three different
       spacings, none of them chosen. One gap, stated once. */
    .sld-price-sheet__body {
        display: flex;
        flex-direction: column;
        gap: var(--space-4);
        padding-top: var(--space-2);
    }
    /* Hangs off the field it describes rather than starting a new block. */
    .sld-price-sheet__total {
        margin-top: calc(var(--space-4) * -1 + var(--space-1));
    }
    .sld-price-sheet__offers {
        display: flex;
        flex-direction: column;
        gap: var(--space-1);
    }
    .sld-sheet-qty {
        min-width: 2ch;
        text-align: center;
        font-variant-numeric: tabular-nums;
        font-size: 1.1rem;
    }
</style>
