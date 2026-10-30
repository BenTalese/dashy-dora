<template>
    <!--
        FU-300 — dashboard quick-action "Log a price" surface. Two-step:
          1. Pick a stock item. Shortlist = most-recently-priced first, then
             low/out as the top-up (owner, 2026-09-04). It reads like
             QuickAddSheet's shortlist but keys off the right history: what you
             last *priced*, not what you most often add to a list.
          2. Log the price via the shared PriceEntry component (shelf mode,
             prefilled from the item's last observation).
        Mounted once in MainLayout; any screen pops it via
        useLogPrice().openLogPrice().

        Once an item is picked the title is just its name (owner, 2026-09-17).
        "Log a price ·" was narrating the dialog back to someone who had opened
        it on purpose and already taken a step inside it; the form underneath
        says what it is. The picker step keeps the verb, because there the name
        doesn't exist yet.
    -->
    <BaseDialog
        v-model="open"
        :title="selectedItem ? selectedItem.name : 'Log a price'"
        closable
        position="bottom"
        card-style="width: 520px; max-width: 96vw"
        @cancel="onHide"
    >
        <q-card-section>
            <!-- Step 1 — item picker. -->
            <template v-if="!selectedItem">
                <q-input
                    v-model="query"
                    outlined
                    dense
                    autofocus
                    clearable
                    debounce="150"
                    label="Search stock items"
                />
                <q-list separator class="q-mt-sm log-price-sheet__results">
                    <q-item
                        v-for="item in results"
                        :key="item.stock_item_id"
                        clickable
                        @click="selectItem(item)"
                    >
                        <!-- 2026-09-01 feedback: this was a 28px filled avatar
                             with a box glyph inside it, which read as a different
                             kind of thing to the level dot every other list in the
                             app uses. R-001: it's the shared StockLevelDot now.
                             Tooltip'd because a bare dot isn't decodable on its
                             own (D-013). -->
                        <q-item-section side>
                            <StockLevelDot :sequence="levelSequence(item.stock_level_id)" size="12px">
                                <BaseTooltip>{{ levelLabel(item.stock_level_id) }}</BaseTooltip>
                            </StockLevelDot>
                        </q-item-section>
                        <q-item-section>{{ item.name }}</q-item-section>
                        <q-item-section side>
                            <q-icon :name="ICONS.chevron_right" />
                        </q-item-section>
                    </q-item>
                    <q-item v-if="results.length === 0">
                        <q-item-section class="dora-text-muted">
                            {{ query ? 'No matches.' : 'No stock items yet.' }}
                        </q-item-section>
                    </q-item>
                </q-list>
            </template>

            <!-- Step 2 — the shared entry form. -->
            <template v-else>
                <!-- 2026-08-21 feedback: "mentions stock item name twice".
                     It did — here and in the dialog title. The title is the
                     canonical place for what the dialog is about, so this row
                     is now just the way back to the picker. -->
                <div class="row items-center q-mb-sm">
                    <BaseButton
                        variant="ghost"
                        dense
                        :icon="ICONS.arrow_back"
                        label="Pick a different item"
                        @click="backToPicker"
                    />
                </div>
                <AppSpinner v-if="prefillLoading" />
                <PriceEntry
                    v-else
                    mode="shelf"
                    :prefill="prefill"
                    :stores="storesList"
                    :busy="submitting"
                    @submit="onSubmit"
                    @cancel="closeLogPrice"
                />
            </template>
        </q-card-section>
    </BaseDialog>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import AppSpinner from 'src/components/AppSpinner.vue';
    import StockLevelDot from 'src/components/stock/StockLevelDot.vue';
    import PriceEntry from 'src/components/dora/PriceEntry.vue';
    import { ICONS } from 'src/style/icons';
    import { storeToRefs } from 'pinia';
    import type { PriceEntryPrefill } from 'src/models/stockItemDetail';
    import type { StockItem } from 'src/models/stockItem';
    import StockItemApiService, {
        type RecentlyPricedItem,
    } from 'src/services/api/stockItemApiService';
    import { useLogPrice } from 'src/composables/useLogPrice';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import { useStoresStore } from 'src/stores/storesStore';
    import { useQuasar } from 'quasar';
    import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { computed, ref, watch } from 'vue';

    const stockItemApi = new StockItemApiService();
    const $q = useQuasar();

    const { isOpen, presetStockItemId, closeLogPrice } = useLogPrice();

    const stockItemStore = useStockItemStore();
    const stockLevelStore = useStockLevelStore();
    const storesStore = useStoresStore();
    const { stockItems } = storeToRefs(stockItemStore);
    const storesList = computed(() => storesStore.stores);

    const open = computed({
        get: () => isOpen.value,
        set: (v) => {
            if (!v) closeLogPrice();
        },
    });

    const query = ref('');
    const selectedItem = ref<StockItem | null>(null);
    const prefill = ref<PriceEntryPrefill | null>(null);
    const prefillLoading = ref(false);
    const submitting = ref(false);

    function levelSequence(id: string | null): number {
        return (id ? stockLevelStore.levelById.get(id)?.sequence : undefined) ?? -1;
    }
    function levelLabel(id: string | null): string {
        return (id ? stockLevelStore.levelById.get(id)?.name : undefined) ?? 'No level set';
    }

    // Cached on each sheet-open: the items you logged a price for most
    // recently, server-ordered (`/stock-items/recently-priced`). Price logging
    // is bursty and repetitive, so "what did I price last?" beats stock level
    // as the opening guess (owner, 2026-09-04). Best-effort — an empty list
    // just leaves the old low/out ordering in charge.
    const recentlyPriced = ref<RecentlyPricedItem[]>([]);

    const results = computed(() => {
        const q = query.value?.trim().toLowerCase() ?? '';
        const items = [...stockItems.value];
        if (q) {
            return items.filter((i) => i.name.toLowerCase().includes(q)).slice(0, 30);
        }
        // No query: lead with most-recently-priced, then top up with the
        // most-restock-relevant (low/out first) so a household that has never
        // logged a price still gets a useful shortlist.
        const lookup = new Map(items.map((i) => [i.stock_item_id, i]));
        const seen = new Set<string>();
        const ordered: StockItem[] = [];
        for (const r of recentlyPriced.value) {
            const item = lookup.get(r.stock_item_id);
            if (item && !seen.has(item.stock_item_id)) {
                ordered.push(item);
                seen.add(item.stock_item_id);
            }
        }
        const remaining = items
            .filter((i) => !seen.has(i.stock_item_id))
            .sort((a, b) => levelSequence(b.stock_level_id) - levelSequence(a.stock_level_id));
        return [...ordered, ...remaining].slice(0, 12);
    });

    async function selectItem(item: StockItem) {
        selectedItem.value = item;
        prefill.value = null;
        prefillLoading.value = true;
        try {
            prefill.value = await stockItemApi.getPriceEntryPrefillAsync(item.stock_item_id);
        } catch {
            // Silent — the form is still usable without prefill.
        } finally {
            prefillLoading.value = false;
        }
    }

    function clearSelection() {
        selectedItem.value = null;
        prefill.value = null;
    }

    // FU-585: the Back arrow returns to a *clean* picker — clearing the search
    // as well as the selection — so Back matches dismiss (both reset to the
    // smart shortlist) rather than dropping the user back on a filtered list.
    function backToPicker() {
        query.value = '';
        clearSelection();
    }

    async function onSubmit(value: {
        total_price: number;
        total_measure: number;
        unit: string;
        store_id: string | null;
        pack_count: number | null;
    }) {
        if (!selectedItem.value) return;
        submitting.value = true;
        try {
            await stockItemApi.addPriceObservationAsync(selectedItem.value.stock_item_id, value);
            stockItemStore.invalidatePriceFacts(selectedItem.value.stock_item_id);
            $q.notify({
                type: 'positive',
                message: `Logged a price for ${selectedItem.value.name}.`,
                timeout: 2500,
            });
            closeLogPrice();
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: "Couldn't log the price.",
                caption: toastCaption(err),
            });
        } finally {
            submitting.value = false;
        }
    }

    function onHide() {
        query.value = '';
        clearSelection();
    }

    // On open, load supporting data + apply preset. If a preset stock item
    // was passed, jump straight to step 2.
    watch(isOpen, async (nowOpen) => {
        if (!nowOpen) return;
        await Promise.all([
            stockItemStore.ensureLoadedAsync(),
            stockLevelStore.ensureLoadedAsync(),
            storesStore.ensureLoadedAsync(),
            // Best-effort: failure shouldn't block the sheet, so swallow it and
            // fall back to the low/out ordering.
            stockItemApi
                .getRecentlyPricedAsync(12)
                .then((items) => {
                    recentlyPriced.value = items;
                })
                .catch(() => {
                    recentlyPriced.value = [];
                }),
        ]);
        if (presetStockItemId.value) {
            const preset = stockItems.value.find(
                (i) => i.stock_item_id === presetStockItemId.value,
            );
            if (preset) await selectItem(preset);
        }
    });
</script>

<style scoped>
    .log-price-sheet__results {
        max-height: 320px;
        overflow-y: auto;
    }
</style>
