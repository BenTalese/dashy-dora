<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Money"
            description="Whether this install talks about money at all."
            :icon="ICONS.savings"
        />

        <template v-if="ready">
            <SettingsSection>
                <SettingsRow inline>
                    <template #label>
                        Money &amp; budgets
                        <InfoTip label="Money and budgets">
                            Turns on recipe cost estimates, shopping-list totals,
                            price history and budget tracking.
                        </InfoTip>
                    </template>
                    <q-toggle
                        :model-value="draft.money_enabled"
                        @update:model-value="onMoneyToggle"
                    />
                </SettingsRow>
            </SettingsSection>
        </template>
    </div>
</template>

<script lang="ts" setup>
    // Owner 2026-09-03 — the Features page was dissolved and its switches sent
    // to the surfaces they govern. Money got a page of its own under Kitchen
    // features rather than a row on the personal `/settings/budget` page,
    // because that page is itself hidden when this flag is off: the switch
    // would have been the one control you can't reach once you've used it.
    import { ICONS } from 'src/style/icons';
    import { useAppSettingDrafts } from 'src/composables/useAppSettingDrafts';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import InfoTip from 'src/components/help/InfoTip.vue';

    const { draft, ready, save } = useAppSettingDrafts({ money_enabled: false });
    // Money gates a nav entry and a dozen surfaces off the cached
    // `/api/health` answer, so a flip has to invalidate that cache.
    const { refresh: refreshFeatureFlags } = useFeatureFlags();

    function onMoneyToggle(next: boolean) {
        void save(
            { money_enabled: next },
            next ? 'Money & budgets enabled.' : 'Money & budgets disabled.',
            refreshFeatureFlags,
        );
    }
</script>

<style scoped lang="scss">
</style>
