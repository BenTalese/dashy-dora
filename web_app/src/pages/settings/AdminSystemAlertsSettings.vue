<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Expiring-soon window"
            description="When an item starts showing as expiring soon, for everyone in the household. Each person still chooses which alerts they get in their own Notifications settings."
            :icon="ICONS.notifications"
        />

        <template v-if="ready">
            <SettingsSection>
                <template #title>Expiring-soon window</template>
                <template #description>
                    Items within this many days of their expiry date show as
                    "expiring soon".
                </template>

                <SettingsRow label="Days">
                    <q-input
                        v-model.number="draft.expiring_soon_window_days"
                        type="number"
                        outlined
                        dense
                        style="max-width: 140px"
                        :min="1"
                        :max="365"
                        :loading="saving"
                        @blur="onSaveWindow"
                    />
                </SettingsRow>
            </SettingsSection>

            <!-- PROPOSAL_STOCKTAKE_MODE §7 — the "Default stocktake
                 reminder" section that used to live here (a numeric
                 days-per-item value backed by `default_days_until_
                 stocktake_alert`) is superseded by the band system.
                 The two new global dials live on the dedicated
                 Settings → Stocktake page. -->
        </template>
    </div>
</template>

<script lang="ts" setup>
    import { ICONS } from 'src/style/icons';
    import { useAppSettingDrafts } from 'src/composables/useAppSettingDrafts';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';

    const { draft, ready, saving, save, reset } = useAppSettingDrafts({ expiring_soon_window_days: 7 });

    function onSaveWindow() {
        const value = draft.expiring_soon_window_days;
        if (typeof value !== 'number' || Number.isNaN(value)) {
            reset();
            return;
        }
        void save({ expiring_soon_window_days: value }, 'Expiring-soon window saved.');
    }
</script>

<style scoped lang="scss">
</style>
