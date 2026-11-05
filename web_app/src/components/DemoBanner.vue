<template>
    <!-- FU-392 — persistent demo notice. Two kinds of demo:
         - an operator's DORA_DEMO_MODE install: informational only, it
           resets itself on a schedule;
         - the first-setup demo someone chose on /setup: carries the way back,
           "Set up Dora", which clears the demo out and returns to the one-time
           first-admin setup.
         A floating pill rather than a full-width bar so it never reflows the
         app layout or collides with the mobile bottom nav. -->
    <div v-if="setupDemo" class="demo-banner demo-banner--actionable" role="region" aria-label="Demo">
        <q-icon :name="ICONS.visibility" size="18px" class="demo-banner__icon" />
        <span class="demo-banner__text">This is a demo with sample data.</span>
        <BaseButton
            v-if="authStore.isAuthenticated()"
            variant="ghost"
            dense
            no-caps
            class="demo-banner__action"
            label="Set up Dora"
            :loading="leaving"
            @click="onLeave"
        />
    </div>
    <div v-else-if="demoMode" class="demo-banner" role="status">
        <q-icon :name="ICONS.visibility" size="18px" class="demo-banner__icon" />
        <span class="demo-banner__text">
            Demo mode. This sample data resets periodically.
        </span>
    </div>
</template>

<script setup lang="ts">
    import { ref } from 'vue';
    import { useRouter } from 'vue-router';
    import { useQuasar } from 'quasar';
    import { isAlreadyNotified, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import BaseButton from 'src/components/BaseButton.vue';
    import { useConfirm } from 'src/composables/useConfirm';
    import { useDemoMode } from 'src/composables/useDemoMode';
    import { useAuthStore } from 'src/stores/authStore';
    import { ICONS } from 'src/style/icons';

    const { demoMode, setupDemo } = useDemoMode();
    const { confirm } = useConfirm();
    const authStore = useAuthStore();
    const router = useRouter();
    const $q = useQuasar();
    const leaving = ref(false);

    async function onLeave() {
        const ok = await confirm({
            title: 'Set up Dora for real?',
            message: 'This clears the demo and its sample data, then takes you to the one-time setup for your first admin account.',
            okLabel: 'Clear the demo',
            destructive: true,
        });
        if (!ok) return;
        leaving.value = true;
        try {
            await authStore.leaveSetupDemoAsync();
            // A full load, so nothing the demo session cached survives into
            // the real setup.
            void router.replace('/setup').then(() => window.location.reload());
        } catch (err) {
            leaving.value = false;
            if (!isAlreadyNotified(err)) {
                $q.notify({ type: 'negative', message: "The demo couldn't be cleared. Try again.", caption: toastCaption(err) });
            }
        }
    }
</script>

<style scoped>
    .demo-banner {
        position: fixed;
        left: 50%;
        bottom: calc(env(safe-area-inset-bottom, 0px) + var(--space-3));
        transform: translateX(-50%);
        z-index: 4000;
        display: flex;
        align-items: center;
        gap: var(--space-2);
        max-width: calc(100vw - 24px);
        padding: var(--space-2) var(--space-4);
        border-radius: var(--radius-pill);
        background: var(--brand-accent);
        color: var(--text-on-accent);
        box-shadow: var(--elevation-2);
        font-size: var(--font-size-sm);
        font-weight: 600;
        pointer-events: none;
    }

    /* The setup demo's pill carries a button, so it takes clicks. */
    .demo-banner--actionable {
        pointer-events: auto;
        padding-right: var(--space-2);
    }

    .demo-banner__action {
        flex: 0 0 auto;
        color: var(--text-on-accent);
        font-weight: 700;
        text-decoration: underline;
    }

    .demo-banner__icon {
        flex: 0 0 auto;
    }

    .demo-banner__text {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
</style>
