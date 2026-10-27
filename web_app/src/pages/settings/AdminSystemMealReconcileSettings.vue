<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Meal reconciliation"
            description="Whether Dora assumes past meals were cooked, or asks you to confirm them."
            :icon="ICONS.event_note"
        />

        <template v-if="ready">
            <SettingsSection>
                <template #title>Assume past-day meals were cooked</template>
                <template #description>
                    When on, past meals are marked cooked automatically and Dora
                    keeps a <strong>log</strong>. When off, they wait on the
                    reconcile page for you to confirm.
                </template>

                <SettingsRow label="Auto-drain">
                    <q-toggle
                        :model-value="draft.auto_drain_past_meals"
                        @update:model-value="onAutoDrainChange"
                    />
                </SettingsRow>
            </SettingsSection>

            <hr class="settings-divider settings-divider--spaced" />

            <SettingsSection>
                <template #title>{{ draft.auto_drain_past_meals ? 'Meal log' : 'Reconcile past meals' }}</template>
                <template #description>
                    <template v-if="draft.auto_drain_past_meals">
                        See what Dora did with past meals. Open to everyone.
                    </template>
                    <template v-else>
                        Confirm past meals. Open to everyone.
                    </template>
                </template>

                <SettingsRow label="Open">
                    <BaseButton
                        variant="secondary"
                        :label="draft.auto_drain_past_meals ? 'View meal log' : 'Go to reconcile'"
                        :icon="ICONS.event_note"
                        :to="'/meal-plans/reconcile'"
                    />
                </SettingsRow>
            </SettingsSection>
        </template>
    </div>
</template>

<script lang="ts" setup>
    // FU-317 Chunk 6: the single install-wide dial for the reconcile feature
    // (proposal D5). Saving re-probes `/health` so `/meal-plans/reconcile`
    // flips between the log (auto) and the runner (manual) without a reload.
    import { ICONS } from 'src/style/icons';
    import { useAppSettingDrafts } from 'src/composables/useAppSettingDrafts';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import { refreshReconcilePolicy } from 'src/composables/useReconcilePolicy';
    import BaseButton from 'src/components/BaseButton.vue';

    const { draft, ready, save } = useAppSettingDrafts({ auto_drain_past_meals: true });

    function onAutoDrainChange(next: boolean) {
        void save(
            { auto_drain_past_meals: next },
            next ? 'Past meals will auto-drain.' : 'Past meals will wait for you to confirm.',
            refreshReconcilePolicy,
        );
    }
</script>

<style scoped lang="scss">
    .settings-page { display: flex; flex-direction: column; }
</style>
