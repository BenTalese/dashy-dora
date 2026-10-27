<template>
    <!-- Pinned under the header when a newer frontend build has been cached by
         the service worker and needs a reload to take effect. Shown to every
         user (their own browser holds the new assets; an admin can't reload it
         for them). Dismissible — reappears next session if still stale.
         Sits below OfflineBanner in MainLayout; accent tone so it reads as
         informational, not an error. -->
    <ShellBanner :show="showUpdate" :icon="ICONS.refresh" tone="accent">
        A new version of Dora is ready. Reload to pick it up.
        <template #actions>
            <BaseButton
                variant="ghost"
                size="sm"
                class="dora-text-on-primary"
                :icon="ICONS.refresh"
                label="Reload"
                @click="onReload"
            />
            <BaseButton
                variant="icon"
                size="sm"
                class="dora-text-on-primary"
                :icon="ICONS.close"
                aria-label="Dismiss"
                @click="onDismiss"
            />
        </template>
    </ShellBanner>
</template>

<script lang="ts" setup>
    import BaseButton from 'src/components/BaseButton.vue';
    import ShellBanner from 'src/components/ShellBanner.vue';
    import { ICONS } from 'src/style/icons';
    import {
        applyUpdateReload,
        dismissUpdate,
        updateAvailablePrompt,
    } from 'src/composables/usePwaLifecycle';

    const showUpdate = updateAvailablePrompt();

    function onReload() {
        applyUpdateReload();
    }
    function onDismiss() {
        dismissUpdate();
    }
</script>
