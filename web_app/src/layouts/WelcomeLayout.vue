<template>
    <!-- Minimal first-run shell: no header chrome at all — the mascot, the
         progress rail and the "Skip onboarding" escape now live inline at the
         top of the wizard itself (a slim, single row), so the whole viewport
         goes to the onboarding screens.

         Onboarding is a self-contained dark canvas regardless of the user's
         chosen theme: `data-theme="pesto-dark"` pins every semantic token to
         the dark palette so the wizard's cards can never render light-on-dark
         (which is what happened when a light-theme user re-entered the tour).
         Focus stays on the scene, not the backdrop. -->
    <q-layout view="hHh Lpr lFf" class="welcome-layout" data-theme="pesto-dark">
        <q-page-container>
            <OfflineBanner />
            <router-view v-slot="{ Component }">
                <FadeTransition mode="out-in">
                    <component :is="Component" />
                </FadeTransition>
            </router-view>
        </q-page-container>
    </q-layout>
</template>

<script setup lang="ts">
    import OfflineBanner from 'src/components/OfflineBanner.vue';
    import FadeTransition from 'src/components/transitions/FadeTransition.vue';
</script>

<style scoped>
    .welcome-layout {
        /* The layout pins `data-theme="pesto-dark"`, so the tokens are the
           right values (R-002; finalisation 14-R21). */
        background: var(--surface-page);
        color: var(--text-primary);
        min-height: 100vh;
    }
</style>
