<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Budget"
            :icon="ICONS.savings"
            description="Set a shared grocery budget for the household. Dora tracks spend across every finished shopping list and surfaces dollar figures on recipes, lists, and the dashboard."
        />

        <div
            v-if="!moneyInstallEnabled"
            class="settings-page__note dora-text-muted"
        >
            This install has money features turned off. Ask an admin to enable
            them in Admin → Money.
        </div>

        <SettingsSection v-else>
            <template #title>Grocery budget</template>
            <SettingsRow label="Amount">
                <q-input
                    v-model.number="budgetAmountDraft"
                    type="number"
                    step="1"
                    min="0"
                    :prefix="currencySymbol"
                    outlined
                    dense
                    placeholder="Off"
                    style="max-width: 160px"
                    @blur="onBudgetAmountBlur"
                    @keydown.enter.prevent="onBudgetAmountBlur"
                />
            </SettingsRow>

            <SettingsRow v-if="budgetActive" label="Period">
                <DoraSegmented
                    :model-value="budgetPeriodDraft"
                    :options="budgetPeriodOptions"
                    @update:model-value="onBudgetPeriodChange"
                />
            </SettingsRow>
        </SettingsSection>
    </div>
</template>

<script lang="ts" setup>
    import type { BudgetPeriod } from 'src/models/auth';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { useMoney } from 'src/composables/useMoney';
    import { computed, ref, watch } from 'vue';
    import { useSettingsSave } from 'src/composables/useSettingsSave';
    import { useBudgetSettings } from 'src/composables/useBudgetSettings';
    import BudgetApiService from 'src/services/api/budgetApiService';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import { ICONS } from 'src/style/icons';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import DoraSegmented, { type DoraSegmentedOption } from 'src/components/settings/DoraSegmented.vue';

    // budget input prefix follows the install currency symbol.
    const { currencySymbol } = useMoney();
    // Money is a single install-wide concern now — no per-user layer.
    const { moneyEnabled: moneyInstallEnabled } = useMoneyEnabled();

    // Household budget (install-wide, moved off User). Read from /api/health
    // via the shared composable; written via the any-user budget endpoint.
    const { budgetAmount, budgetPeriod, refreshBudgetPolicy } = useBudgetSettings();
    const budgetApi = new BudgetApiService();

    const budgetAmountDraft = ref<number | null>(budgetAmount.value);
    const budgetPeriodDraft = ref<BudgetPeriod>(budgetPeriod.value);

    // "Active" = a positive amount is set. Value-driven: no amount ⇒ off, so
    // the period picker only appears once there's a budget to apply it to.
    const budgetActive = computed(
        () => budgetAmountDraft.value != null && budgetAmountDraft.value > 0,
    );

    const budgetPeriodOptions: DoraSegmentedOption<BudgetPeriod>[] = [
        { label: 'Weekly', value: 'weekly' },
        { label: 'Monthly', value: 'monthly' },
    ];

    // R-003 / FU-601 — shared save-toast helper (see useSettingsSave).
    const { update } = useSettingsSave();

    // Keep drafts in sync when the household budget changes elsewhere (another
    // member edits it, or the initial health probe resolves).
    watch(budgetAmount, (v) => { budgetAmountDraft.value = v; });
    watch(budgetPeriod, (v) => { budgetPeriodDraft.value = v; });

    async function onBudgetAmountBlur() {
        const value = budgetAmountDraft.value;
        // Normalise to the value-driven contract: null / NaN / ≤0 all mean off.
        const next = value == null || Number.isNaN(value) || value <= 0 ? null : value;
        if (next === (budgetAmount.value ?? null)) return;
        const result = await update(
            next === null ? 'Grocery budget turned off.' : 'Grocery budget updated.',
            () => budgetApi.updateSettingsAsync({ amount: next }),
        );
        if (result === null) {
            budgetAmountDraft.value = budgetAmount.value;
            return;
        }
        await refreshBudgetPolicy();
    }

    async function onBudgetPeriodChange(value: BudgetPeriod) {
        const previous = budgetPeriodDraft.value;
        budgetPeriodDraft.value = value;
        const result = await update('Budget period updated.', () =>
            budgetApi.updateSettingsAsync({ period: value }),
        );
        if (result === null) {
            budgetPeriodDraft.value = previous;
            return;
        }
        await refreshBudgetPolicy();
    }
</script>

<style scoped lang="scss">
    .settings-page__note {
        font-size: var(--font-size-sm);
        line-height: 1.4;
        margin-top: var(--space-1);
    }
</style>
