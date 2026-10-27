<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Cooking"
            description="How many people you usually cook for, and whether the meal planner shows batch-cooking tools. Shared by everyone."
            :icon="ICONS.restaurant"
        />

        <template v-if="ready">
            <SettingsSection>
                <template #title>Household headcount</template>
                <template #description>
                    How many people the household usually cooks for. Cook mode
                    scales a recipe's ingredients to this number. Leave it blank
                    to use each recipe's own serving size instead.
                </template>

                <SettingsRow label="People">
                    <q-input
                        v-model.number="draft.household_headcount"
                        outlined
                        dense
                        type="number"
                        :min="1"
                        :max="99"
                        style="max-width: 100px"
                        placeholder="Per recipe"
                        clearable
                        @blur="onHeadcountCommit"
                        @clear="onHeadcountCommit"
                    />
                </SettingsRow>
            </SettingsSection>

            <hr class="settings-divider settings-divider--spaced" />

            <SettingsSection>
                <template #title>Cooking style</template>
                <!-- DR-4 (FU-578 #38): plain-words explainer — the old copy
                     leaked internal terms ("cook pool", "± / log-cook",
                     "shortfall"). Say what the user gets, not the mechanism. -->
                <template #description>
                    <strong>Fresh</strong> keeps the meal planner as simple
                    scheduling, one entry per meal. <strong>Batch</strong> is
                    for households that cook once and eat it across several
                    days: the planner tracks how many servings each cook makes,
                    tells you when you've planned more meals than you've cooked,
                    and shows what's still left to cook.
                </template>

                <SettingsRow label="Cooking style">
                    <DoraSegmented
                        :model-value="draft.batch_features_enabled ? 'batch' : 'fresh'"
                        :options="cookingStyleOptions"
                        @update:model-value="onCookingStyleChange"
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
    import { refreshCookingPolicy } from 'src/composables/useCookingPolicy';

    // FU-615: the two install-wide household cooking settings (headcount +
    // cook-style), moved off the per-user record onto AppSetting. Each save
    // refreshes the shared cooking policy so cook mode and the meal planner
    // pick it up without a reload.
    const { draft, ready, save } = useAppSettingDrafts({
        household_headcount: null as number | null,
        batch_features_enabled: false,
    });

    type CookingStyle = 'fresh' | 'batch';
    const cookingStyleOptions: DoraSegmentedOption<CookingStyle>[] = [
        { label: 'Fresh', value: 'fresh' },
        { label: 'Batch', value: 'batch' },
    ];

    // Clamp to null / 1-99 (the server bounds); null means "use each recipe's
    // servings".
    function normaliseHeadcount(value: number | null): number | null {
        if (value === null || value === undefined || !Number.isFinite(value) || value < 1) {
            return null;
        }
        return Math.min(99, Math.floor(value));
    }

    function onHeadcountCommit() {
        const next = normaliseHeadcount(draft.household_headcount);
        draft.household_headcount = next;
        void save(
            { household_headcount: next },
            next === null
                ? 'Cook mode will use each recipe\'s serving size.'
                : `Cook mode will scale recipes for ${next}.`,
            refreshCookingPolicy,
        );
    }

    function onCookingStyleChange(next: CookingStyle) {
        const wantBatch = next === 'batch';
        void save(
            { batch_features_enabled: wantBatch },
            wantBatch
                ? 'Batch tools are on in the meal planner.'
                : 'Meal planner is back to pure scheduling.',
            refreshCookingPolicy,
        );
    }
</script>

<style scoped lang="scss">
</style>
