<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Stock"
            description="Install-wide stock defaults: how Dora auto-adds items when they run low, and whether this install can scan barcodes and print QR labels."
            :icon="ICONS.inventory_2"
        />

        <template v-if="ready">
            <SettingsSection>
                <template #title>Auto-add on low</template>
                <template #description>
                    When a stock item transitions to Low or Out, Dora can
                    silently drop it onto your primary shopping list (with
                    an undoable toast). Pick which items this fires for.
                    Essential items are the ones you've marked with the
                    flag on the stock overview.
                </template>

                <SettingsRow label="Fire for">
                    <DoraSegmented
                        :model-value="draft.auto_add_mode"
                        :options="MODE_OPTIONS"
                        @update:model-value="onModeChange"
                    />
                </SettingsRow>
            </SettingsSection>

            <!-- Moved here from the retired Features page 2026-09-03 (owner:
                 *"scanning & qr can go to stock section"*). It is a stock
                 affordance — the camera jumps to a stock item and the labels go
                 on shelves — so it reads better beside the other stock
                 defaults than in a pile of unrelated install switches. -->
            <SettingsSection>
                <template #title>Scanning &amp; QR labels</template>

                <SettingsRow inline>
                    <template #label>
                        Scanning enabled
                        <InfoTip label="Scanning and QR labels">
                            Point the camera at a product barcode to jump
                            straight to the stock item it's linked to, and print
                            Dora's own QR labels for shelves and containers.
                            Dora never looks up prices from a scan.
                        </InfoTip>
                    </template>
                    <q-toggle
                        :model-value="draft.scanning_enabled"
                        @update:model-value="onScanningToggle"
                    />
                </SettingsRow>

                <!-- A warning, not a block (2026-09-27): most browsers withhold
                     the camera on plain http, but not all. Shown only when the
                     page reading it is on http, and only once scanning is on. -->
                <q-banner
                    v-if="draft.scanning_enabled && cameraInsecure"
                    dense
                    rounded
                    class="dora-bg-warning-soft q-mt-sm"
                >
                    <template #avatar>
                        <q-icon :name="ICONS.info_outline" />
                    </template>
                    <div class="text-body2">
                        This page is on plain <code>http://</code>, so some
                        browsers won't allow the camera. The Android app and
                        HTTPS always work.
                    </div>
                </q-banner>
            </SettingsSection>
        </template>
    </div>
</template>

<script lang="ts" setup>
    import { ICONS } from 'src/style/icons';
    import type { AutoAddMode } from 'src/services/api/appSettingsApiService';
    import { useAppSettingDrafts } from 'src/composables/useAppSettingDrafts';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import DoraSegmented, { type DoraSegmentedOption } from 'src/components/settings/DoraSegmented.vue';
    import InfoTip from 'src/components/help/InfoTip.vue';
    import { insecureContextWarning } from 'src/helpers/cameraAvailability';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import { useScanningEnabled } from 'src/composables/useScanningEnabled';

    /**
     * FU-511: install-wide auto-add mode, which replaced the per-item
     * `StockItem.auto_add_when_low` toggle. Saved on change.
     */
    const MODE_OPTIONS: DoraSegmentedOption<AutoAddMode>[] = [
        { label: 'Off', value: 'off' },
        { label: 'Essential only', value: 'essential_only' },
        { label: 'All items', value: 'all' },
    ];

    const { draft, ready, save } = useAppSettingDrafts({
        auto_add_mode: 'essential_only' as AutoAddMode,
        scanning_enabled: false,
    });

    // FU-580: scanning has its own module-level probe composable (separate
    // from useFeatureFlags), so a toggle refreshes that cache too or the gated
    // UI (the scan button, the QR labels nav entry) stays stale until a reload.
    const { refreshScanning } = useScanningEnabled();
    const { refresh: refreshFeatureFlags } = useFeatureFlags();
    // Same authority the scan overlay consults, so the warning here and the
    // explainer there can't drift apart (R-003).
    const cameraInsecure = insecureContextWarning() !== null;

    function onScanningToggle(value: boolean) {
        void save(
            { scanning_enabled: value },
            value ? 'Scanning & QR labels enabled.' : 'Scanning & QR labels disabled.',
            () => Promise.all([refreshScanning(), refreshFeatureFlags()]),
        );
    }

    function onModeChange(next: AutoAddMode) {
        void save({ auto_add_mode: next }, 'Auto-add mode saved.');
    }
</script>

<style scoped lang="scss">
    .settings-page { display: flex; flex-direction: column; }
</style>
