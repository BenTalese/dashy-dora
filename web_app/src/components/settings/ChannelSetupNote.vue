<template>
    <!-- Shown by NotificationsSettings when a per-user channel is gated on an
         install-wide setup that hasn't happened yet (SMTP for email, VAPID for
         push). A warning card — not a muted footnote — so the "why is this
         toggle disabled?" answer actually pops (owner feedback). Admin viewers
         get a direct link to the setup page instead of "ask an admin", since
         they *are* the admin. One banner anatomy (D-015): this is
         `SettingsNotice` with the channel copy (finalisation 13-R18). -->
    <SettingsNotice tone="warning" :title="`${cfg.label} isn't set up on this install yet`">
        <template v-if="isAdmin">{{ cfg.adminHint }}</template>
        <template v-else>Ask an admin to {{ cfg.verb }} and this will unlock.</template>
        <template v-if="isAdmin" #actions>
            <BaseButton
                variant="secondary"
                :icon="ICONS.settings"
                :label="cfg.setupLabel"
                :to="cfg.setupPath"
            />
        </template>
    </SettingsNotice>
</template>

<script lang="ts" setup>
    import { computed } from 'vue';
    import { ICONS } from 'src/style/icons';
    import BaseButton from 'src/components/BaseButton.vue';
    import SettingsNotice from 'src/components/settings/SettingsNotice.vue';

    const props = defineProps<{
        // 'email' backs both the deals + alerts email channels (both need SMTP);
        // 'push' backs the web-push channel (needs VAPID keys).
        channel: 'email' | 'push';
        isAdmin: boolean;
    }>();

    const cfg = computed(() =>
        props.channel === 'email'
            ? {
                  label: 'Email',
                  verb: 'configure SMTP',
                  adminHint: 'Configure SMTP to start sending emails from this install.',
                  setupLabel: 'Set up email',
                  setupPath: '/settings/admin/system/email',
              }
            : {
                  label: 'Push',
                  verb: 'generate VAPID keys',
                  adminHint: 'Generate VAPID keys to enable web push on this install.',
                  setupLabel: 'Set up push',
                  setupPath: '/settings/admin/system/push',
              },
    );
</script>
