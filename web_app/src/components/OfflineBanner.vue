<template>
    <!-- Offline is READ-ONLY (owner decision 2026-08-23). The write queue that
         used to back this banner is gone, so the copy makes no promise about
         syncing — it says what's true (you can look, you can't change) and
         nothing more. Two variants because the distinction is actionable:
         your own connection is your problem to fix, an unreachable server is
         Dora's. -->
    <ShellBanner :show="!isFullyOnline" :icon="online ? ICONS.sync_problem : ICONS.wifi_off" tone="negative">
        {{ message }}
        <template #actions>
            <BaseButton
                variant="ghost"
                size="sm"
                class="dora-text-on-primary"
                :icon="reconnecting ? ICONS.sync : ICONS.refresh"
                :label="reconnecting ? 'Checking…' : 'Retry'"
                :loading="reconnecting"
                @click="retryNow"
            />
        </template>
    </ShellBanner>
</template>

<script lang="ts" setup>
    import BaseButton from 'src/components/BaseButton.vue';
    import ShellBanner from 'src/components/ShellBanner.vue';
    import { useNetworkStatus } from 'src/composables/useNetworkStatus';
    import { OFFLINE_COPY } from 'src/helpers/offlineCopy';
    import { ICONS } from 'src/style/icons';
    import { computed } from 'vue';

    const { online, apiReachable, isFullyOnline, reconnecting, retryNow } =
        useNetworkStatus();

    const message = computed(() => {
        if (!online.value) return OFFLINE_COPY.offline;
        if (!apiReachable.value) return OFFLINE_COPY.unreachable;
        return '';
    });
</script>
