// Money opt-in is a single install-wide concern (owner call: money is
// "kitchen setup, not personal"). The old per-user `money_features_enabled`
// layer was removed — if the install has money on (`AppSetting.money_enabled`,
// server-owned via `/api/health`), dollar surfaces render for everyone; off
// hides them for everyone. There is no per-user gate to layer.
//
// Consumers read a single `moneyEnabled.value` boolean from here rather than
// touching the flag directly. Render gates (cost estimates, plan budgets,
// dashboard budget card, etc.) all key off this.

import { computed } from 'vue';
import { useFeatureFlags } from 'src/composables/useFeatureFlags';

export function useMoneyEnabled() {
    const { money: installMoney } = useFeatureFlags();

    /** The install-wide money flag, the only gate for dollar surfaces. */
    const moneyEnabled = computed(() => installMoney.value);

    return { moneyEnabled };
}
