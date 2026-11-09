<template>
    <!-- Preferred buys (FU-211): free-text "what I actually buy" reminders.
         Not a product or SKU, so they sit beside linked products rather than
         giving way to them (FU-990). -->
    <div v-if="detail">
        <div class="dora-text-secondary text-weight-bold q-mb-sm row items-center q-gutter-xs">
            <span>Preferred buys</span>
            <q-icon :name="ICONS.info_outline" size="14px" class="dora-text-muted">
                <BaseTooltip max-width="320px">
                    What you actually buy for this, e.g.
                    “Vitasoy Oat Milky 1L”.
                </BaseTooltip>
            </q-icon>
        </div>
        <!-- A-Z as the server sends them (R-003); reminders are scanned, not
             ranked, so there is no reorder. -->
        <q-list
            v-if="preferredBuys.length"
            separator
            bordered
            class="rounded-borders q-mb-sm"
        >
            <q-item
                v-for="pb in preferredBuys"
                :key="pb.preferred_buy_id"
            >
                <q-item-section>
                    <q-input
                        v-if="editingBuyId === pb.preferred_buy_id"
                        v-model="editingBuyLabel"
                        dense
                        outlined
                        autofocus
                        maxlength="255"
                        @blur="saveBuyRename(pb)"
                        @keydown.enter.prevent="saveBuyRename(pb)"
                        @keydown.esc.prevent="editingBuyId = null"
                    />
                    <q-item-label v-else>{{ pb.label }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                    <div class="row items-center no-wrap">
                        <BaseButton
                            :aria-label="`Rename ${pb.label}`"
                            variant="icon"
                            :icon="ICONS.edit"
                            :disable="busy"
                            @click="startBuyRename(pb)"
                        >
                            <BaseTooltip>Rename</BaseTooltip>
                        </BaseButton>
                        <BaseButton
                            :aria-label="`Remove ${pb.label}`"
                            variant="icon"
                            :icon="ICONS.delete_outline"
                            :disable="busy"
                            @click="deleteBuy(pb)"
                        >
                            <BaseTooltip>Remove</BaseTooltip>
                        </BaseButton>
                    </div>
                </q-item-section>
            </q-item>
        </q-list>
        <div class="row items-center no-wrap q-gutter-sm">
            <q-input
                v-model="newBuyLabel"
                dense
                outlined
                class="col"
                maxlength="255"
                placeholder="Add a preferred buy"
                @keydown.enter.prevent="addBuy"
            />
            <BaseButton
                variant="primary"
                :icon="ICONS.add"
                label="Add"
                :disable="!newBuyLabel.trim() || busy"
                @click="addBuy"
            />
        </div>
    </div>
</template>

<script lang="ts" setup>
    import { computed } from 'vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { useStockItemDetail } from 'src/composables/useStockItemDetail';
    import type { PreferredBuy } from 'src/models/stockItemDetail';
    import { ICONS } from 'src/style/icons';

    const {
        stockItemApi,
        stockItemId,
        detail,
        busy,
        newBuyLabel,
        editingBuyId,
        editingBuyLabel,
        withBusyReload,
    } = useStockItemDetail();

    const preferredBuys = computed(() => detail.value?.preferred_buys ?? []);

    async function addBuy() {
        const label = newBuyLabel.value.trim();
        if (!label) return;
        await withBusyReload(() => stockItemApi.addPreferredBuyAsync(stockItemId.value, label));
        newBuyLabel.value = '';
    }
    function startBuyRename(pb: PreferredBuy) {
        editingBuyId.value = pb.preferred_buy_id;
        editingBuyLabel.value = pb.label;
    }
    async function saveBuyRename(pb: PreferredBuy) {
        if (editingBuyId.value !== pb.preferred_buy_id) return;
        const label = editingBuyLabel.value.trim();
        editingBuyId.value = null;
        if (!label || label === pb.label) return;
        await withBusyReload(() =>
            stockItemApi.updatePreferredBuyAsync(stockItemId.value, pb.preferred_buy_id, label),
        );
    }
    async function deleteBuy(pb: PreferredBuy) {
        await withBusyReload(() =>
            stockItemApi.deletePreferredBuyAsync(stockItemId.value, pb.preferred_buy_id),
        );
    }
</script>
