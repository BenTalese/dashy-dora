<template>
    <!--
        FU-227 chunk 3 — stock-overview row "Log a price" button (G1/G2/G3).
        Sits in the right-cluster between the spacer and the expiry button
        on `StockItemRow.vue`. Money-gated (the parent renders this with
        `v-if="moneyEnabled"` — we don't re-check here).

        Tap → opens the shared `PriceEntry` widget in shelf mode inside a
        `BaseDialog`. Prefill is lazily fetched on dialog open from the
        item-detail endpoint (G3 — "prefilled, one visible Log"). If the
        fetch fails, the form still opens — just without prefill.
    -->
    <RowActionButton
        :icon="ICONS.cash_plus"
        :loading="busy"
        :aria-label="`Log a price for ${itemName}`"
        @click="onOpen"
    >
        <BaseTooltip>Log a price</BaseTooltip>
    </RowActionButton>

    <BaseDialog
        v-model="dialogOpen"
        :title="`Log a price · ${itemName}`"
        closable
        @cancel="dialogOpen = false"
    >
        <q-card-section>
            <PriceEntry
                mode="shelf"
                :prefill="prefill"
                :stores="storesList"
                :busy="submitting"
                @submit="onSubmit"
                @cancel="dialogOpen = false"
            />
        </q-card-section>
    </BaseDialog>
</template>

<script setup lang="ts">
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { computed, ref } from 'vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import PriceEntry from 'src/components/dora/PriceEntry.vue';
    import RowActionButton from 'src/components/RowActionButton.vue';
    import { ICONS } from 'src/style/icons';
    import StockItemApiService from 'src/services/api/stockItemApiService';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useStoresStore } from 'src/stores/storesStore';
    import type { PriceEntryPrefill } from 'src/models/stockItemDetail';

    const props = defineProps<{
        stockItemId: string;
        itemName: string;
    }>();

    const emit = defineEmits<{
        (e: 'logged'): void;
    }>();

    const stockItemApi = new StockItemApiService();
    const storesStore = useStoresStore();
    const stockItemStore = useStockItemStore();
    const storesList = computed(() => storesStore.stores);

    const dialogOpen = ref(false);
    const busy = ref(false);              // loading state for the row button
    const submitting = ref(false);        // POST in flight
    const prefill = ref<PriceEntryPrefill | null>(null);

    async function onOpen() {
        // Open the dialog immediately so the user feels responsive; fetch
        // prefill in parallel and let the watch inside PriceEntry seed once
        // it arrives. Failure leaves the form usable in unprefilled state.
        dialogOpen.value = true;
        prefill.value = null;
        busy.value = true;
        try {
            void storesStore.ensureLoadedAsync();
            prefill.value = await stockItemApi.getPriceEntryPrefillAsync(props.stockItemId);
        } catch {
            // Silent — form still works without prefill.
        } finally {
            busy.value = false;
        }
    }

    async function onSubmit(value: {
        total_price: number;
        total_measure: number;
        unit: string;
        store_id: string | null;
        pack_count: number | null;
    }) {
        submitting.value = true;
        try {
            await stockItemApi.addPriceObservationAsync(props.stockItemId, value);
            stockItemStore.invalidatePriceFacts(props.stockItemId);
            emit('logged');
            dialogOpen.value = false;
        } finally {
            submitting.value = false;
        }
    }
</script>
