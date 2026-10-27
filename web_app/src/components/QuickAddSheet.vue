<template>
    <BaseDialog v-model="open" title="Add to list" closable position="bottom" card-style="width: 520px; max-width: 96vw" @cancel="onHide">
        <q-card-section>
            <!-- Target list -->
            <BaseSelect
                v-model="targetListId"
                emit-value
                map-options
                label="Add to"
                :options="listOptions"
                class="q-mb-md"
            />

            <q-input
                v-model="query"
                outlined
                dense
                autofocus
                clearable
                debounce="150"
                label="Search stock items"
            >
                <template #prepend>
                    <q-icon :name="ICONS.search" />
                </template>
            </q-input>

            <!-- One tap, one line on the list (owner, 2026-09-17: *"the
                 additional step after selecting an item makes it a slow/painful
                 process"*). There was a second screen carrying a quantity field
                 and a radio group of store offers, and both had a defensible
                 default nobody wanted to change: quantity 1, and no specific
                 offer — which is now the *only* behaviour, since an offer no
                 longer sets a price. Both are editable on the row afterwards,
                 where you can see the list you're editing. -->
            <q-list separator class="q-mt-sm quick-add-sheet__results">
                <q-item
                    v-for="item in results"
                    :key="item.stock_item_id"
                    clickable
                    :disable="addingId === item.stock_item_id"
                    @click="addItem(item)"
                >
                    <!-- 2026-09-01 feedback (raised on the twin picker
                         in LogPriceSheet): a filled 28px avatar with a
                         box glyph read as a different kind of thing to
                         the level dot every other list uses. R-001:
                         shared StockLevelDot, tooltip'd per D-013. -->
                    <q-item-section side>
                        <StockLevelDot :sequence="levelSequence(item.stock_level_id)" size="12px">
                            <BaseTooltip>{{ levelLabel(item.stock_level_id) }}</BaseTooltip>
                        </StockLevelDot>
                    </q-item-section>
                    <q-item-section>{{ item.name }}</q-item-section>
                    <q-item-section side>
                        <q-spinner v-if="addingId === item.stock_item_id" size="18px" />
                        <q-icon v-else :name="ICONS.add" />
                    </q-item-section>
                </q-item>
                <q-item v-if="results.length === 0">
                    <q-item-section class="dora-text-muted">
                        {{ query ? 'No matches.'
                            : stockItems.length === 0 ? 'No stock items yet.'
                                : 'Everything is already on this list.' }}
                    </q-item-section>
                </q-item>
            </q-list>
        </q-card-section>
    </BaseDialog>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import BaseSelect from 'src/components/BaseSelect.vue';
    import { ICONS } from 'src/style/icons';
    import StockLevelDot from 'src/components/stock/StockLevelDot.vue';
    import { storeToRefs } from 'pinia';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import { useQuickAdd } from 'src/composables/useQuickAdd';
    import { useShoppingListActions } from 'src/composables/useShoppingListActions';
    import type { StockItem } from 'src/models/stockItem';
    import ShoppingListApiService, {
        type FrequentlyAddedItem,
    } from 'src/services/api/shoppingListApiService';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import { computed, ref, watch } from 'vue';

    const shoppingListApi = new ShoppingListApiService();

    const { isOpen, presetStockItemId, presetListId, closeQuickAdd } = useQuickAdd();
    const { addItems } = useShoppingListActions();

    const stockItemStore = useStockItemStore();
    const stockLevelStore = useStockLevelStore();
    const shoppingListStore = useShoppingListStore();
    const { stockItems } = storeToRefs(stockItemStore);
    const { summaries, quickAddTargetListId, membership } = storeToRefs(shoppingListStore);

    // Bridge the module-level open flag to a local v-model so q-dialog's hide
    // event can close it cleanly.
    const open = computed({
        get: () => isOpen.value,
        set: (v) => {
            if (!v) closeQuickAdd();
        },
    });

    const query = ref('');
    const targetListId = ref<string | null>(null);
    const addingId = ref<string | null>(null);

    const listOptions = computed(() =>
        summaries.value
            .filter((s) => s.status !== 'done')
            .map((s) => ({
                label: s.display_name,
                value: s.shopping_list_id,
            })),
    );

    function levelSequence(id: string | null) {
        return (id ? stockLevelStore.levelById.get(id)?.sequence : undefined) ?? -1;
    }
    function levelLabel(id: string | null): string {
        return (id ? stockLevelStore.levelById.get(id)?.name : undefined) ?? 'No level set';
    }

    // Cached on each sheet-open: stock items the user has historically added
    // to a list most often. We surface these first when there's no query so
    // "the thing I always buy" is one tap away. Falls back gracefully if
    // the endpoint hasn't returned yet or fails.
    const frequentlyAdded = ref<FrequentlyAddedItem[]>([]);

    /** Frequently-added first, then the most restock-relevant (low/out), and
     *  **the same ordering under a filter** (owner, 2026-09-17). It used to
     *  drop straight to `includes()` order the moment you typed, so the item
     *  you buy every week could sit below one you have never bought. Typing
     *  narrows the set; it doesn't change what "most useful first" means.
     *
     *  The star that used to mark a frequent item is gone with it: the
     *  ordering already says so, and a row of stars is decoration on a list
     *  whose whole job is to be scanned. */
    /** Items already on the list you're adding to (owner, 2026-09-27). The
     *  server would dedupe the tap anyway, so offering them was a row that did
     *  nothing. Membership refreshes after every add, so a tapped item leaves
     *  the results, which doubles as the confirmation it landed. */
    const onTargetIds = computed(() => {
        const target = targetListId.value;
        if (!target) return new Set<string>();
        return new Set(
            (membership.value?.items ?? [])
                .filter((m) => m.unticked_list_ids.includes(target))
                .map((m) => m.stock_item_id),
        );
    });

    const results = computed(() => {
        const q = query.value?.trim().toLowerCase() ?? '';
        const candidates = stockItems.value.filter(
            (i) => !onTargetIds.value.has(i.stock_item_id),
        );
        const items = q
            ? candidates.filter((i) => i.name.toLowerCase().includes(q))
            : candidates;

        const frequentRank = new Map(
            frequentlyAdded.value.map((f, index) => [f.stock_item_id, index]),
        );
        const ordered = [...items].sort((a, b) => {
            const aRank = frequentRank.get(a.stock_item_id);
            const bRank = frequentRank.get(b.stock_item_id);
            if (aRank !== undefined || bRank !== undefined) {
                if (aRank === undefined) return 1;
                if (bRank === undefined) return -1;
                return aRank - bRank;
            }
            return levelSequence(b.stock_level_id) - levelSequence(a.stock_level_id);
        });
        return ordered.slice(0, q ? 30 : 12);
    });

    /** Tap = added. Quantity 1, no offer — the two things the second step used
     *  to ask for, at the values it already defaulted to. The sheet stays open
     *  so a shop's worth of items is one tap each, and the row reports itself
     *  through the shared `addItems` toast. */
    async function addItem(item: StockItem) {
        if (!targetListId.value || addingId.value) return;
        addingId.value = item.stock_item_id;
        try {
            await addItems(targetListId.value, [
                { stock_item_id: item.stock_item_id, quantity: 1, selected_product_id: null },
            ]);
        } finally {
            addingId.value = null;
        }
    }

    function onHide() {
        query.value = '';
        addingId.value = null;
    }

    // When the sheet opens, make sure the supporting data is loaded and apply
    // any presets the caller passed to openQuickAdd().
    watch(isOpen, async (nowOpen) => {
        if (!nowOpen) return;
        const loads: Promise<unknown>[] = [];
        loads.push(stockItemStore.ensureLoadedAsync());
        loads.push(stockLevelStore.ensureLoadedAsync());
        loads.push(shoppingListStore.ensureLoadedAsync());
        // Frequently-added is best-effort; failure shouldn't block the
        // sheet, so swallow errors and fall back to low/out ordering.
        loads.push(
            shoppingListApi
                .getFrequentlyAddedAsync(12)
                .then((items) => {
                    frequentlyAdded.value = items;
                })
                .catch(() => {
                    frequentlyAdded.value = [];
                }),
        );
        await Promise.all(loads);

        // FU-603 — final fallback prefers a planning *draft* over an
        // in-progress ('shopping') list, so a pantry cart-add doesn't default
        // into the shop you're mid-way through. An explicit preset or the
        // remembered per-tab target (quickAddTargetListId) still win first.
        const fallbackListId =
            summaries.value.find((s) => s.status === 'draft')?.shopping_list_id
            ?? listOptions.value[0]?.value
            ?? null;
        targetListId.value =
            presetListId.value ?? quickAddTargetListId.value ?? fallbackListId;

        // A caller that named an item means "add this one" — with no second
        // step left, that is the whole interaction, so it happens and the
        // sheet closes rather than opening onto a list the user didn't ask for.
        if (presetStockItemId.value) {
            const preset = stockItems.value.find(
                (i) => i.stock_item_id === presetStockItemId.value,
            );
            if (preset) {
                await addItem(preset);
                closeQuickAdd();
            }
        }
    });
</script>

<style scoped>
    .quick-add-sheet__results {
        max-height: 320px;
        overflow-y: auto;
    }
</style>
