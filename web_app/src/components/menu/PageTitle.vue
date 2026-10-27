<template>
    <!-- No `shrink`: with flex: 0 0 auto a long title claimed its full
         content width and got pushed out of the toolbar instead of
         truncating. Flexing lets Quasar's built-in ellipsis do its job. -->
    <q-toolbar-title class="dora-pageTitle text-accent">
        {{ label }}
    </q-toolbar-title>
</template>

<script setup lang="ts">
    defineProps<{
        label: string;
    }>();
</script>

<style scoped>
    .dora-pageTitle {
        font-family: 'Cute Dino', sans-serif;
        /* A6 — scale token (was fixed 24px) so it follows the text-size pref. */
        font-size: var(--font-size-2xl);
        margin-top: 4px;
        opacity: 0.9;
        min-width: 0;
    }

    /* Mobile only surface for this component, but the step down is kept in
       a query so a future desktop caller isn't silently shrunk too. One
       token step (2xl → xl) — still well clear of the 12px D-003 floor. */
    @media (max-width: 1023px) {
        .dora-pageTitle {
            font-size: var(--font-size-xl);
        }
    }
</style>
