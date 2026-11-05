<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="QR labels"
            description="Print Dora's own QR labels. Pick items, choose a sheet layout, and open a printable sheet. Print them to scan for quick actions on your items."
        />

        <!-- Off-state: install-wide `scanning_enabled` gate. The nav link is
             also hidden when the flag is off, so this banner mostly appears
             for admins reaching the page by URL / a stale bookmark. -->
        <q-banner
            v-if="scanningLoaded && !scanningEnabled"
            class="dora-bg-sunken dora-text-secondary q-mb-md"
            rounded
        >
            <template #avatar>
                <q-icon :name="ICONS.info" />
            </template>
            Scanning &amp; QR labels are turned off. An admin can enable them in
            <router-link to="/settings/admin/system/stock">Settings → Admin → Stock</router-link>.
        </q-banner>

        <!-- Owner 2026-09-03: was a bare `q-card flat bordered` — Quasar's
             default chrome rather than the app's. `.settings-card` is the
             shared settings-worklist panel (see css/settingsCards.scss); the
             picker rows stack on a phone instead of squeezing. -->
        <div v-if="scanningEnabled" class="settings-card">
            <div class="settings-card__head qr-head">
                <SearchInput
                    v-model="sheetFilter"
                    label="Filter items"
                    class="qr-head__filter"
                />
                <BaseSelect
                    v-model="sheetLayout"
                    :options="layoutOptions"
                    label="Sheet layout"
                    emit-value
                    map-options
                    class="qr-head__layout"
                />
                <div class="qr-head__bulk">
                    <BaseButton
                        variant="secondary"
                        dense
                        label="All"
                        @click="onSelectAllVisible"
                    />
                    <BaseButton
                        variant="secondary"
                        dense
                        label="None"
                        @click="selectedItemIds = []"
                    />
                </div>
            </div>

            <div class="qr-picker">
                <label
                    v-for="item in filteredStockItems"
                    :key="item.stock_item_id"
                    class="settings-card__row qr-picker__row"
                >
                    <q-checkbox
                        :model-value="selectedItemIds.includes(item.stock_item_id)"
                        :label="item.name"
                        @update:model-value="toggleItem(item.stock_item_id)"
                    />
                </label>
            </div>

            <div class="settings-card__foot">
                <BaseButton
                    variant="secondary"
                    label="Print all items"
                    :icon="ICONS.print"
                    @click="openSheet({ allItems: true })"
                />
                <BaseButton
                    variant="primary"
                    :icon="ICONS.picture_as_pdf"
                    :label="`Open sheet (${selectedItemIds.length})`"
                    :disable="selectedItemIds.length === 0"
                    @click="openSheet({ allItems: false })"
                />
            </div>
        </div>
    </div>
</template>

<script lang="ts" setup>
    import { Notify } from 'quasar';
    import SearchInput from 'src/components/SearchInput.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseSelect from 'src/components/BaseSelect.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import { ICONS } from 'src/style/icons';
    import { computed, onMounted, ref } from 'vue';
    import { describeQrFailure, openQrSheetAsync } from 'src/composables/useQrLabels';
    import { useScanningEnabled } from 'src/composables/useScanningEnabled';
    import { useStockItemStore } from 'src/stores/stockItemStore';

    const { scanningEnabled, scanningLoaded } = useScanningEnabled();
    const stockItemStore = useStockItemStore();

    // this page owns the Print QR labels surface only. The Scan
    // tab that used to live alongside it on /data/barcodes was removed:
    // every page that needs scanning already has its own Scan button
    // (Stock Overview toolbar, Add-to-list flows, etc.), and per-item
    // barcode registration lives on the stock item detail page.
    const sheetFilter = ref('');
    const sheetLayout = ref('a4-21up');
    const layoutOptions = [
        { label: 'A4 21-up (3 × 7)', value: 'a4-21up' },
        { label: 'Avery 5160 (US Letter, 3 × 10)', value: 'avery-5160' },
    ];
    const selectedItemIds = ref<string[]>([]);

    const filteredStockItems = computed(() => {
        const needle = sheetFilter.value.trim().toLowerCase();
        const all = stockItemStore.stockItems ?? [];
        if (!needle) return all;
        return all.filter((s) => s.name.toLowerCase().includes(needle));
    });

    function toggleItem(id: string) {
        const idx = selectedItemIds.value.indexOf(id);
        if (idx >= 0) selectedItemIds.value.splice(idx, 1);
        else selectedItemIds.value.push(id);
    }

    function onSelectAllVisible() {
        selectedItemIds.value = filteredStockItems.value.map((s) => s.stock_item_id);
    }

    // Sync entry so the click's gesture still reaches `window.open` (R-046),
    // and the rejection is reported rather than voided — a blocked pop-up used
    // to look identical to the button not being wired up.
    function openSheet(args: { allItems: boolean }) {
        openQrSheetAsync({
            layout: sheetLayout.value,
            ...(args.allItems ? {} : { ids: selectedItemIds.value }),
        }).catch((err: unknown) => {
            Notify.create({
                type: 'negative',
                
                message: describeQrFailure(err),
            });
        });
    }

    onMounted(async () => {
        await stockItemStore.ensureLoadedAsync();
    });
</script>

<style scoped lang="scss">
    .qr-head__filter { flex: 1 1 220px; min-width: 0; }
    .qr-head__layout { flex: 1 1 200px; min-width: 0; }
    .qr-head__bulk { flex: 0 0 auto; display: flex; gap: var(--space-2); }
    /* The item list scrolls inside the card rather than growing the page —
       a large pantry would otherwise push the sheet buttons off-screen. */
    .qr-picker {
        max-height: 360px;
        overflow-y: auto;
    }
    .qr-picker__row {
        cursor: pointer;
        padding-block: var(--space-1);
    }
    .qr-picker__row:hover {
        background: var(--surface-sunken);
    }
    /* The whole row is the label, so the checkbox owns the text and both the
       tick and the name are one 44px target (D-004). */
    .qr-picker__row :deep(.q-checkbox__label) {
        font-size: 0.9375rem;
        color: var(--text-primary);
    }
</style>
