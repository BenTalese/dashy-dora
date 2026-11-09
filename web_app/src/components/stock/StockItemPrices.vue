<template>
    <!-- Your prices: the widget (baseline, latest, Log a price, Full history)
         plus the recent observations with edit and remove. Lives on the
         Products tab beside preferred buys and linked products (FU-990). -->
    <div v-if="detail">
        <YourPricesWidget
            :your-prices="detail.your_prices ?? null"
            :prefill="detail.price_entry_prefill ?? null"
            :stores="storesList"
            :busy="busy"
            :stock-item-id="stockItemId"
            :item-name="detail.name"
            @submit="addObservation"
        >
            <!-- Owner 2026-10-17 restyle: a labelled
                 section, amounts in one right-hand column
                 (D-018), the measure + when/where as the
                 row's text. -->
            <div v-if="priceObservations.length" class="dora-your-prices__recent">
                <div class="dora-your-prices__label dora-your-prices__recent-label">Recent prices</div>
                <q-list separator class="dora-your-prices__list">
                    <q-item
                        v-for="obs in shownObservations"
                        :key="obs.observation_id"
                    >
                        <q-item-section>
                            <q-item-label>{{ formatObsMeasure(obs) }}</q-item-label>
                            <q-item-label caption>
                                {{ relativeTime(obs.observed_at) }}
                                <span v-if="obs.store_name"> · {{ obs.store_name }}</span>
                                <span v-if="obs.shopping_list_name"> · from {{ obs.shopping_list_name }}</span>
                            </q-item-label>
                        </q-item-section>
                        <q-item-section side class="dora-your-prices__price">
                            {{ formatMoney(obs.total_price) }}
                        </q-item-section>
                        <q-item-section side>
                            <div class="row no-wrap">
                                <BaseButton
                                    variant="icon"
                                    :icon="ICONS.edit"
                                    :disable="busy"
                                    aria-label="Edit price"
                                    @click="editingObservation = obs"
                                >
                                    <BaseTooltip>Edit</BaseTooltip>
                                </BaseButton>
                                <BaseButton
                                    variant="icon"
                                    :icon="ICONS.delete_outline"
                                    :disable="busy"
                                    aria-label="Remove price"
                                    @click="deleteObservation(obs)"
                                >
                                    <BaseTooltip>Remove</BaseTooltip>
                                </BaseButton>
                            </div>
                        </q-item-section>
                    </q-item>
                </q-list>
                <BaseButton
                    v-if="priceObservations.length > RECENT_PRICES_SHOWN"
                    variant="subtle"
                    class="q-mt-xs"
                    :label="showAllObservations ? 'Show fewer' : `Show all ${priceObservations.length}`"
                    @click="showAllObservations = !showAllObservations"
                />
            </div>
        </YourPricesWidget>

        <BaseDialog
            :model-value="editingObservation !== null"
            title="Edit price"
            closable
            @update:model-value="(open: boolean) => { if (!open) editingObservation = null; }"
        >
            <q-card-section v-if="editingObservation">
                <PriceEntry
                    mode="shelf"
                    :initial="editingObservation"
                    :stores="storesList"
                    :busy="busy"
                    @submit="updateObservation"
                    @cancel="editingObservation = null"
                />
            </q-card-section>
        </BaseDialog>
    </div>
</template>

<script lang="ts" setup>
    import { computed, ref } from 'vue';
    import { useQuasar } from 'quasar';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import PriceEntry from 'src/components/dora/PriceEntry.vue';
    import YourPricesWidget from 'src/components/dora/YourPricesWidget.vue';
    import { useConfirm } from 'src/composables/useConfirm';
    import { formatMoney } from 'src/composables/useMoney';
    import { useStockItemDetail } from 'src/composables/useStockItemDetail';
    import { formatQuantity } from 'src/helpers/formatQuantity';
    import { relativeTime } from 'src/helpers/relativeTime';
    import type { PriceEntryValue, PriceObservation } from 'src/models/stockItemDetail';
    import { isAlreadyNotified, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useStoresStore } from 'src/stores/storesStore';
    import { ICONS } from 'src/style/icons';

    const { stockItemApi, stockItemId, detail, busy, withBusyReload } = useStockItemDetail();
    const $q = useQuasar();
    const stockItemStore = useStockItemStore();
    const storesStore = useStoresStore();

    // Prices (FU-227 chunk 3): YourPricesWidget owns the entry UX via
    // the shared PriceEntry component. This tab just exposes the list (with
    // delete) and a submit handler that talks to the API. R-003: server
    // derives per-unit cost; we never divide here.
    const priceObservations = computed(() => detail.value?.price_observations ?? []);
    // FU-706: a frequently logged item ran to hundreds of rows mid-tab.
    const RECENT_PRICES_SHOWN = 5;
    const showAllObservations = ref(false);
    const shownObservations = computed(() => (
        showAllObservations.value
            ? priceObservations.value
            : priceObservations.value.slice(0, RECENT_PRICES_SHOWN)
    ));
    const editingObservation = ref<PriceObservation | null>(null);
    const { confirm } = useConfirm();

    // Stores list for the optional store picker in PriceEntry (A2).
    const storesList = computed(() => storesStore.stores);

    async function addObservation(value: PriceEntryValue, done: () => void) {
        try {
            await withBusyReload(() => stockItemApi.addPriceObservationAsync(stockItemId.value, value));
        } catch (err) {
            // FU-976: the rejection used to escape to the global handler, so
            // a 5xx showed the http client's toast *and* the "oopsie": two
            // toasts for one failure. One now; the dialog stays open.
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: "Couldn't log the price.",
                    caption: toastCaption(err),
                });
            }
            return;
        }
        stockItemStore.invalidatePriceFacts(stockItemId.value);
        // Only close the widget's dialog once the save landed (a throw above
        // keeps it open with the typed values).
        done();
    }
    // Multipack (FU-227 follow-up): "4 × 125g" instead of "500g flat" when
    // the observation carries a pack count. Per-pack = total / count.
    function formatObsMeasure(obs: PriceObservation): string {
        if (obs.pack_count != null && obs.pack_count > 1) {
            return `${obs.pack_count} × ${formatQuantity(obs.total_measure / obs.pack_count, obs.unit)}`;
        }
        return formatQuantity(obs.total_measure, obs.unit);
    }

    async function updateObservation(value: PriceEntryValue) {
        const obs = editingObservation.value;
        if (!obs) return;
        try {
            await withBusyReload(() => stockItemApi.updatePriceObservationAsync(
                stockItemId.value, obs.observation_id, value,
            ));
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: "Couldn't save the price.",
                    caption: toastCaption(err),
                });
            }
            return;
        }
        editingObservation.value = null;
        stockItemStore.invalidatePriceFacts(stockItemId.value);
    }

    async function deleteObservation(obs: PriceObservation) {
        const ok = await confirm({
            title: 'Remove this price?',
            message: `${formatMoney(obs.total_price)} for ${formatObsMeasure(obs)}, ${relativeTime(obs.observed_at)}.`,
            okLabel: 'Remove',
            destructive: true,
        });
        if (!ok) return;
        await withBusyReload(() =>
            stockItemApi.deletePriceObservationAsync(stockItemId.value, obs.observation_id),
        );
        stockItemStore.invalidatePriceFacts(stockItemId.value);
    }
</script>
