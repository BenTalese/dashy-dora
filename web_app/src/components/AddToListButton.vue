<template>
    <!--
        C-7 Chunk 1 — the unified add-to-list button.

        Owns the decision tree for "add to a draft list" + "toggle off when
        already on a list" so every consumer (stock row, recipe ingredient,
        bulk action, …) reads the same behaviour. Visual variants below are
        chrome only — `behaviour is identical across them`.

          row      — flat round icon button (default; sits in dense lists)
          toolbar  — flat dense labelled button (page toolbars + detail pages)
          menu     — q-item entry (inside a q-menu)
          bulk     — variant for batch-add of `items[]`; one summary toast

        State-aware render via `cartStateFor` (generalised from
        useStockFilters): not-on / on_target (current draft) / on_other
        (a draft we're not currently picking) / on_multiple (>1 unticked
        list — popover).
    -->

    <!-- ── Inline-product variant ───────────────────────────────────────
         C-7 Chunk 3 — anchored on `productId` rather than `stockItemId`;
         used on the My Products row so unlinked products can be added
         to a draft list as their own product-only line. -->
    <!-- Owner 2026-10-15: drawn as the row cart, not a smaller ghost button
         of its own. Linked or not, a product's cart is the same control. -->
    <RowActionButton
        v-if="variant === 'inline-product'"
        :icon="ICONS.add_shopping_cart"
        :loading="busy"
        :disable="!productId"
        aria-label="Add to a draft list"
        @click.stop="onInlineProductClick"
    >
        <BaseTooltip>Add to a draft list</BaseTooltip>
    </RowActionButton>

    <!-- ── Bulk variant ─────────────────────────────────────────────────
         Resolves the target ONCE for the whole batch via the existing
         pick flow (sessionStorage-remembered), adds everything, surfaces
         one summary toast. -->
    <BaseButton
        v-else-if="variant === 'bulk'"
        variant="ghost"
        :icon="ICONS.add_shopping_cart"
        :label="bulkLabel"
        :loading="busy"
        :disable="!hasItems"
        @click.stop="onBulkAdd"
    />

    <!-- ── Menu variant ─────────────────────────────────────────────────
         Lives inside a q-menu; renders as a q-item. -->
    <q-item
        v-else-if="variant === 'menu'"
        clickable
        :disable="busy"
        @click="onPrimaryClick"
    >
        <q-item-section avatar>
            <q-icon :name="iconFor" :color="iconColour ?? undefined" />
        </q-item-section>
        <q-item-section>{{ menuLabel }}</q-item-section>
    </q-item>

    <!-- ── Toolbar variant ──────────────────────────────────────────────
         Renders the shared BaseButton (secondary) so it sits flush with the
         other toolbar actions on the detail/recipe pages. The cart-state
         icon still swaps to signal on/off-list; the popover anchors to it
         on `on_multiple`. Anchored on `productId` alone (an unlinked
         product's price-drop alert, owner 2026-10-17) it takes the
         inline-product flow, drawn as a labelled button. -->
    <BaseButton
        v-else-if="variant === 'toolbar'"
        variant="secondary"
        :icon="iconFor"
        :label="toolbarLabel"
        :loading="busy"
        :aria-label="toolbarLabel"
        @click.stop="stockItemId ? onPrimaryClick() : onInlineProductClick()"
    >
        <q-popup-proxy
            v-if="multiPopoverOpen"
            v-model="multiPopoverOpen"
            anchor="bottom right"
            self="top right"
        >
            <component :is="MultiListPopover" />
        </q-popup-proxy>
    </BaseButton>

    <!-- ── Row variant (default) ────────────────────────────────────────
         Routed through the shared `RowActionButton` (round 3 feedback) so
         the cart button picks up the same flat/dense/round/md style as
         every other row-cluster button without copy-paste drift. -->
    <RowActionButton
        v-else
        :class="cartFeedback"
        :icon="iconFor"
        :color="iconColour ?? undefined"
        :loading="busy"
        :aria-label="tooltip"
        @click.stop="onPrimaryClick"
    >
        <!-- D-10 (2026-08-19): the buy verdict came off this button. It rode
             here as a toned ring + tooltip reasoning from 2026-08-15, which was
             an improvement on the chip it replaced but still ambient decoration
             — an amber "wait" ring eight pixels from an amber "low stock"
             square, on a row that had eight other things to say. The verdict
             now lives only where the user went looking for it: the stock-item
             detail card and the shopping list. -->
        <BaseTooltip>{{ tooltip }}</BaseTooltip>
        <q-popup-proxy
            v-if="multiPopoverOpen"
            v-model="multiPopoverOpen"
            anchor="bottom middle"
            self="top middle"
        >
            <component :is="MultiListPopover" />
        </q-popup-proxy>
    </RowActionButton>
</template>

<script setup lang="ts">
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { computed, h, ref, type Component } from 'vue';
    import { storeToRefs } from 'pinia';
    import { QCard, QCardSection, QItem, QItemSection, QList, QSeparator, useQuasar } from 'quasar';
    import ShoppingListApiService from 'src/services/api/shoppingListApiService';
    import BaseButton from 'src/components/BaseButton.vue';
    import RowActionButton from 'src/components/RowActionButton.vue';
    import { ICONS } from 'src/style/icons';
    import { useMicroFeedback } from 'src/composables/useMicroFeedback';
    import { useQuickAdd } from 'src/composables/useQuickAdd';
    import { useShoppingListActions } from 'src/composables/useShoppingListActions';
    import { useStockItemActions } from 'src/composables/useStockItemActions';
    import { cartStateFor, type ActiveListInfo, type Membership } from 'src/models/shoppingList';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useConfirm } from 'src/composables/useConfirm';

    /**
     * `stockItemId` — single-anchor variants (row / toolbar / menu).
     * `items` — bulk variant; each entry is a stock item id (later: optional
     *   product + quantity carried by `Chunk 2`'s QuickAddSheet).
     */
    const props = withDefaults(
        defineProps<{
            stockItemId?: string;
            /** C-7 Chunk 3 — anchor a standalone product line (no
             *  stock-item placeholder). Pairs with `variant="inline-product"`
             *  on the My Products row. */
            productId?: string;
            /** Pre-decided linked product to record on the line. When set on
             *  the `row` variant (e.g. the per-product cart on My Products),
             *  the add skips the 2+-products combined modal because the user
             *  has already chosen which product to buy, and the line stores
             *  `selected_product_id` so the price picker sticks to that
             *  product. Cart state still keys off the stock item. */
            selectedProductId?: string;
            items?: string[];
            variant?: 'row' | 'toolbar' | 'menu' | 'bulk' | 'inline-product';
            /** Optional override for the row tooltip / toolbar / menu label. */
            label?: string;
        }>(),
        { variant: 'row' },
    );

    const $q = useQuasar();

    const { choose } = useConfirm();
    const shoppingListApi = new ShoppingListApiService();
    const shoppingListStore = useShoppingListStore();
    const { membership: storeMembership } = storeToRefs(shoppingListStore);
    const membership = computed<Membership | null>(
        () => (storeMembership.value as Membership | null) ?? null,
    );
    const stockItemStore = useStockItemStore();
    const { stockItems } = storeToRefs(stockItemStore);
    const actions = useStockItemActions();
    const listActions = useShoppingListActions();
    const { openQuickAdd } = useQuickAdd();

    // decision 2: 2+ linked products → always open the
    // combined `QuickAddSheet` modal (the user picks the offer + target
    // list in one surface). 0/1 products go through the existing
    // single-item flow. Read off the StockItem store, which carries the
    // count alongside the rest of the row state.
    const linkedProductCount = computed<number>(() => {
        if (!props.stockItemId) return 0;
        const item = stockItems.value.find(
            (s) => s.stock_item_id === props.stockItemId,
        );
        return item?.linked_product_count ?? 0;
    });
    /** 2+ linked products → route through the combined QuickAddSheet.
     *  Decision 2 promotes the multi-product case unconditionally; with 0/1
     *  products the single-item flow handles ambiguous drafts via the radio
     *  dialog, so it never escalates here. (FU-531: the proposal's "both axes
     *  ambiguous" draft-count branch was dropped with decision 2 — the
     *  `draftCount >= 2` tail was unreachable, so it's gone.) */
    const shouldUseCombinedModal = computed<boolean>(
        () => linkedProductCount.value >= 2,
    );

    const busy = ref(false);
    const multiPopoverOpen = ref(false);

    // ── State derivation ────────────────────────────────────────────────
    const cartState = computed(() => {
        if (!props.stockItemId) return 'none' as const;
        return cartStateFor(props.stockItemId, membership.value);
    });

    /* DR-15 / D-010 — the on/off-list flip is one of the four high-frequency
       gestures, and the only signal was the icon glyph swapping between
       `add_shopping_cart` and `shopping_cart`, which is easy to miss on a
       dense row. A 120ms bump on the button says "that landed" without
       another toast (the toast budget is D-009's problem, and the row variant
       fires dozens of times a shop).

       Row variant only. The toolbar/menu variants sit on a labelled button
       next to a text label, where a 16% scale on the whole control reads as a
       twitch rather than an acknowledgement — and those are once-per-page
       actions, not high-frequency ones, so D-010 doesn't ask for them. */
    const cartFeedback = useMicroFeedback(() => cartState.value, 'bump');

    // List of unticked lists this stock item sits on (for the multi popover).
    const onLists = computed<ActiveListInfo[]>(() => {
        if (!props.stockItemId || !membership.value) return [];
        const entry = membership.value.items.find(
            (i) => i.stock_item_id === props.stockItemId,
        );
        if (!entry) return [];
        const lookup = new Map(
            (membership.value.active_lists ?? []).map((l) => [l.shopping_list_id, l]),
        );
        return entry.unticked_list_ids
            .map((id) => lookup.get(id))
            .filter((l): l is ActiveListInfo => !!l);
    });

    const iconFor = computed(() => {
        switch (cartState.value) {
            case 'on_target':
                return ICONS.shopping_cart;
            case 'on_other':
                return ICONS.shopping_cart;
            case 'on_multiple':
                return ICONS.shopping_cart_checkout;
            case 'none':
            default:
                return ICONS.add_shopping_cart;
        }
    });
    const iconColour = computed<string | null>(() => {
        switch (cartState.value) {
            case 'on_target':
                return 'primary';
            case 'on_other':
                return 'accent';
            case 'on_multiple':
                // was 'amber-9'; now theme-aware via
                // --severity-attention (deeper than severity-low so it
                // reads as "notice me, not urgent").
                return 'severity-attention';
            case 'none':
            default:
                return null;
        }
    });
    const tooltip = computed(() => {
        // FU-603 — the picker targets any active (non-done) list, not just
        // drafts, so the copy says "a list", not "a draft list".
        switch (cartState.value) {
            case 'on_target':
                return 'On your list. Click to remove';
            case 'on_other':
                // Owner 2026-09-03: "'On another list' makes no sense in this
                // context". Right — "another" is a comparison, and outside the
                // shopping-list surface there is no first list to compare
                // against: on a recipe row the only fact is that the item is
                // already on *a* list.
                return 'On a list. Click to remove';
            case 'on_multiple':
                return 'On more than one list';
            case 'none':
            default:
                return 'Add to a list';
        }
    });
    const toolbarLabel = computed(() => {
        if (props.label) return props.label;
        switch (cartState.value) {
            case 'on_target':
            case 'on_other':
                return 'On list';
            case 'on_multiple':
                return `On ${onLists.value.length} lists`;
            case 'none':
            default:
                return 'Add to list';
        }
    });
    const menuLabel = computed(() => {
        if (props.label) return props.label;
        if (cartState.value === 'none') return 'Add to a list';
        return 'Remove from list';
    });

    // ── Bulk variant ────────────────────────────────────────────────────
    const hasItems = computed(() => (props.items?.length ?? 0) > 0);
    const bulkLabel = computed(() => {
        if (props.label) return props.label;
        const n = props.items?.length ?? 0;
        if (n === 0) return 'Add to list';
        return `Add ${n} to list`;
    });
    const emit = defineEmits<{ (e: 'bulk-done'): void }>();

    async function onBulkAdd() {
        if (!hasItems.value) return;
        busy.value = true;
        try {
            // Decision 6: one summary toast for the whole batch. Resolve
            // the target up-front via the existing single-item flow on
            // the FIRST item (handles 0-draft / ambiguous prompts +
            // remembers the pick), then drop the rest through the bulk
            // `addItems` helper which already aggregates into a single
            // toast. The first item's toast is suppressed here because
            // addItems will emit a combined one covering everything.
            const ids = props.items ?? [];
            // Prefer the membership-inferred target if there's exactly
            // one draft (no prompt needed). Otherwise route the first
            // item through the prompt flow and then batch the rest.
            const targetFromMembership =
                membership.value?.quick_add_target_list_id ?? null;
            if (targetFromMembership) {
                await listActions.addItems(
                    targetFromMembership,
                    ids.map((id) => ({ stock_item_id: id })),
                );
                emit('bulk-done');
                return;
            }
            // Ambiguous / no-draft path — let the single-item flow resolve
            // the target on the FIRST item (it prompts when 2+ drafts exist).
            // Its return value is the list the item landed on; batch the rest
            // into that same list. `quick_add_target_list_id` only fires when
            // exactly one draft exists, so it stays null here and can't stand
            // in for the picked list.
            const chosen = await actions.addToList(ids[0]!);
            if (chosen && ids.length > 1) {
                await listActions.addItems(
                    chosen,
                    ids.slice(1).map((id) => ({ stock_item_id: id })),
                );
            }
            emit('bulk-done');
        } finally {
            busy.value = false;
        }
    }

    // ── Inline-product variant click ────────────────────────────────────
    // adds a *standalone product line* (no stock-item
    // anchor). Resolves the target list via Axis B (membership.active_
    // lists filtered by status='draft'): 1 draft → silent; 2+ → picker;
    // 0 → tell the user to create a draft. Skips cart-state tracking
    // because we have no stock-item id to key membership on.
    async function onInlineProductClick() {
        if (!props.productId) return;
        const drafts = (membership.value?.active_lists ?? []).filter(
            (l) => l.status === 'draft',
        );
        let targetListId: string | null = null;
        if (drafts.length === 0) {
            $q.notify({
                type: 'info',
                message: 'No draft list yet. Create one first to add this product.',
            });
            return;
        }
        if (drafts.length === 1) {
            targetListId = drafts[0]!.shopping_list_id;
        } else {
            targetListId = await choose({
                title: 'Which list?',
                message: 'Add this product to which draft list?',
                items: drafts.map((d) => ({
                    label: d.name,
                    value: d.shopping_list_id,
                })),
                initial: drafts[0]!.shopping_list_id,
                okLabel: 'Add',
            });
            if (!targetListId) return;
        }
        busy.value = true;
        try {
            const result = await shoppingListApi.addLineAsync(targetListId, {
                product_id: props.productId,
            });
            await shoppingListStore.refreshAsync();
            $q.notify({
                type: 'positive',
                message: result.already_on_list
                    ? 'Already on your list.'
                    : 'Added as product line.',
            });
        } catch {
            $q.notify({
                type: 'negative',
                message: 'Could not add the product.',
            });
        } finally {
            busy.value = false;
        }
    }

    // ── Primary click ───────────────────────────────────────────────────
    // Decision tree (proposal §7a):
    //   - state === 'none' → add via the existing single-item flow.
    //   - state === 'on_target' or 'on_other' (exactly 1 list) → remove
    //     silently from that list.
    //   - state === 'on_multiple' (2+ lists) → open popover with
    //     "Add to another" / "Remove from <list>" / "Remove from all".
    async function onPrimaryClick() {
        if (!props.stockItemId) return;
        const stockItemId = props.stockItemId;
        if (cartState.value === 'none') {
            // Pre-decided product (My Products per-product cart) — user
            // has already chosen which linked product to buy, so skip the
            // combined modal and record `selected_product_id` on the line
            // directly. Falls back to the inferred quick-add target; on
            // ambiguous / no-draft, defers to the standard flow.
            if (props.selectedProductId) {
                const target = membership.value?.quick_add_target_list_id ?? null;
                busy.value = true;
                try {
                    if (target) {
                        await listActions.addItems(target, [{
                            stock_item_id: stockItemId,
                            selected_product_id: props.selectedProductId,
                        }]);
                    } else {
                        await actions.addToList(stockItemId);
                    }
                } finally {
                    busy.value = false;
                }
                return;
            }
            // 2+ products (and/or both axes ambiguous)
            // → combined modal so the user makes both picks in one
            // surface. Quantity lives only here (decision 5); quick
            // paths stay qty-1.
            if (shouldUseCombinedModal.value) {
                openQuickAdd({ stockItemId });
                return;
            }
            busy.value = true;
            try {
                await actions.addToList(stockItemId);
            } finally {
                busy.value = false;
            }
            return;
        }
        if (cartState.value === 'on_target' || cartState.value === 'on_other') {
            const listId = onLists.value[0]?.shopping_list_id;
            if (!listId) return;
            busy.value = true;
            try {
                await listActions.removeFromList(listId, stockItemId);
            } finally {
                busy.value = false;
            }
            return;
        }
        // on_multiple — open popover
        multiPopoverOpen.value = true;
    }

    // ── Multi-list popover (decision 1) ─────────────────────────────────
    // Inline functional component — keeps the popover tightly scoped to
    // this button without a separate file. Renders the per-list rows +
    // "Add to another" + "Remove from all" actions.
    const MultiListPopover: Component = {
        setup() {
            return () => h(QCard, { style: 'min-width: 240px' }, {
                default: () => [
                    h(QCardSection, { class: 'text-subtitle2' }, () => 'On these lists'),
                    h(QSeparator),
                    h(QList, { dense: true }, () =>
                        onLists.value.map((l) =>
                            h(QItem, {
                                clickable: true,
                                'v-close-popup': true,
                                onClick: async () => {
                                    if (!props.stockItemId) return;
                                    multiPopoverOpen.value = false;
                                    busy.value = true;
                                    try {
                                        await listActions.removeFromList(
                                            l.shopping_list_id,
                                            props.stockItemId,
                                        );
                                    } finally {
                                        busy.value = false;
                                    }
                                },
                            }, {
                                default: () => [
                                    h(QItemSection, () => `Remove from ${l.name}`),
                                ],
                            }),
                        ),
                    ),
                    h(QSeparator),
                    h(QItem, {
                        clickable: true,
                        onClick: async () => {
                            if (!props.stockItemId) return;
                            multiPopoverOpen.value = false;
                            busy.value = true;
                            try {
                                await listActions.removeFromAllLists(
                                    props.stockItemId,
                                    onLists.value.map((l) => l.shopping_list_id),
                                );
                            } finally {
                                busy.value = false;
                            }
                        },
                    }, {
                        default: () => [
                            h(QItemSection, { class: 'text-negative' }, () =>
                                `Remove from all (${onLists.value.length})`,
                            ),
                        ],
                    }),
                    h(QItem, {
                        clickable: true,
                        onClick: async () => {
                            if (!props.stockItemId) return;
                            multiPopoverOpen.value = false;
                            const stockItemId = props.stockItemId;
                            // "Add to another" — pick from active lists the
                            // item is NOT already on. Routing through the
                            // inferred-target path here picks one of the
                            // lists it's already on and toasts
                            // "Already on your list" (the original bug).
                            const onListIds = new Set(
                                onLists.value.map((l) => l.shopping_list_id),
                            );
                            const candidates = (
                                membership.value?.active_lists ?? []
                            ).filter((l) => !onListIds.has(l.shopping_list_id));
                            if (candidates.length === 0) {
                                $q.notify({
                                    type: 'info',
                                    message: 'Already on every active list.',
                                });
                                return;
                            }
                            const chosen = candidates.length === 1
                                ? candidates[0]!.shopping_list_id
                                : await choose({
                                    title: 'Add to which list?',
                                    message: 'Pick another active list.',
                                    items: candidates.map((c) => ({
                                        label: c.name,
                                        value: c.shopping_list_id,
                                    })),
                                    initial: candidates[0]!.shopping_list_id,
                                    okLabel: 'Add',
                                });
                            if (!chosen) return;
                            busy.value = true;
                            try {
                                await actions.addToList(stockItemId, chosen);
                            } finally {
                                busy.value = false;
                            }
                        },
                    }, {
                        default: () => [
                            h(QItemSection, { class: 'text-primary' }, () => 'Add to another list'),
                        ],
                    }),
                ],
            });
        },
    };
</script>
