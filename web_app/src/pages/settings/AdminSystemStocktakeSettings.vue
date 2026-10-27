<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Stocktake"
            description="How often Dora asks you to check each item, and whether she self-tunes that per item from how fast it actually moves."
            :icon="ICONS.fact_check"
        />

        <template v-if="ready">
            <!-- 2026-08-20 owner feedback — the install-wide master switch.
                 Off hides the whole surface: the Stock-overview button, the
                 row's needs-check marker, the per-item toggle on an item's
                 detail page, and the queue itself (the server stops resolving an
                 overdue set, so the alerts bell goes quiet too). This page is
                 the only way back on, which is why it stays in the nav and
                 keeps rendering when the feature is off. -->
            <SettingsSection>
                <template #title>Stocktake</template>
                <template #description>
                    Stocktake is the guided count that walks you through items
                    Dora hasn't seen in a while. Turning it off hides it; nothing
                    is deleted.
                </template>

                <SettingsRow label="Enabled">
                    <q-toggle
                        :model-value="draft.stocktake_enabled"
                        @update:model-value="onEnabledChange"
                    />
                </SettingsRow>

                <SettingsRow
                    v-if="draft.stocktake_enabled"
                    label="New items"
                    help="Whether an item you add joins the stocktake rotation straight away. Off means you opt each item in from its detail page."
                >
                    <q-toggle
                        :model-value="draft.stocktake_new_items_opt_in"
                        @update:model-value="onOptInChange"
                    />
                </SettingsRow>
            </SettingsSection>

            <hr v-if="draft.stocktake_enabled" class="settings-divider settings-divider--spaced" />

            <SettingsSection v-if="draft.stocktake_enabled">
                <template #title>Default check cadence</template>
                <template #description>
                    The baseline cadence applied to every item. Individual
                    items can move faster if they're flagged Essential (one
                    band faster) or if Auto self-tuning is on (below).
                </template>

                <SettingsRow label="Cadence">
                    <DoraSegmented
                        :model-value="draft.stocktake_default_cadence_band"
                        :options="BAND_OPTIONS"
                        @update:model-value="onBandChange"
                    />
                </SettingsRow>
            </SettingsSection>

            <hr v-if="draft.stocktake_enabled" class="settings-divider settings-divider--spaced" />

            <SettingsSection v-if="draft.stocktake_enabled">
                <template #title>Auto self-tuning</template>
                <template #description>
                    When on, Dora checks fast-moving items more often and
                    stable ones less. Turn off to use the default cadence above
                    for every item.
                </template>

                <SettingsRow label="Auto">
                    <q-toggle
                        :model-value="draft.stocktake_auto_tuning_enabled"
                        @update:model-value="onAutoChange"
                    />
                </SettingsRow>
            </SettingsSection>
        </template>
    </div>
</template>

<script lang="ts" setup>
    import { ICONS } from 'src/style/icons';
    import { useAppSettingDrafts } from 'src/composables/useAppSettingDrafts';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import DoraSegmented, { type DoraSegmentedOption } from 'src/components/settings/DoraSegmented.vue';
    import type { CadenceBand } from 'src/services/api/stocktakeApiService';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import { refreshStocktakePolicy } from 'src/composables/useStocktakePolicy';

    /**
     * PROPOSAL_STOCKTAKE_MODE §8: the global stocktake dials, each a
     * single-value control saved on change.
     */
    const BAND_OPTIONS: DoraSegmentedOption<CadenceBand>[] = [
        { label: 'Weekly', value: 'weekly' },
        { label: 'Fortnightly', value: 'fortnightly' },
        { label: 'Monthly', value: 'monthly' },
    ];

    const { draft, ready, save } = useAppSettingDrafts({
        stocktake_enabled: true,
        stocktake_new_items_opt_in: true,
        stocktake_default_cadence_band: 'fortnightly' as CadenceBand,
        stocktake_auto_tuning_enabled: true,
    });

    // The master switch changes what `/api/health features.stocktake` answers,
    // and every gated surface reads that through one cache, so refresh it or
    // the Stock-overview button stays visible until a reload (FU-580).
    const { refresh: refreshFeatureFlags } = useFeatureFlags();

    function onEnabledChange(next: boolean) {
        void save(
            { stocktake_enabled: next },
            next ? 'Stocktake is on.' : 'Stocktake is off.',
            refreshFeatureFlags,
        );
    }

    function onOptInChange(next: boolean) {
        // The create-item dialog seeds its Stocktake toggle from this value
        // via /api/health, so the policy cache is re-probed.
        void save(
            { stocktake_new_items_opt_in: next },
            next
                ? 'New items will join the stocktake rotation.'
                : 'New items start out of the stocktake rotation.',
            refreshStocktakePolicy,
        );
    }

    function onBandChange(next: CadenceBand) {
        void save({ stocktake_default_cadence_band: next }, 'Default cadence saved.');
    }

    function onAutoChange(next: boolean) {
        void save(
            { stocktake_auto_tuning_enabled: next },
            next ? 'Auto self-tuning on.' : 'Auto self-tuning off.',
        );
    }
</script>

<style scoped lang="scss">
</style>
