<template>
    <!--
        R-Phase 6 §9-I — skeleton screens. Same shape as the real surface
        so the layout doesn't shift on hydrate (Doherty + reduces CLS).
        Two variants align with the planner's layouts: the day-card list
        and the mobile single-day focus.
    -->
    <div
        class="skeleton"
        :class="`skeleton--${variant}`"
        role="status"
        aria-live="polite"
        aria-label="Loading meal plan…"
    >
        <!-- Direction A: 3 day cards in a stack -->
        <template v-if="variant === 'list'">
            <q-card
                v-for="i in 3"
                :key="`l-${i}`"
                flat bordered
                class="skeleton__day q-mb-sm"
            >
                <q-skeleton type="QToolbar" height="32px" />
                <div class="q-pa-sm column q-gutter-xs">
                    <q-skeleton v-for="j in 2" :key="`l-${i}-${j}`" type="rect" height="32px" />
                </div>
            </q-card>
        </template>

        <!-- Mobile single-day focus -->
        <template v-else>
            <div class="skeleton__day-strip">
                <q-skeleton v-for="i in 7" :key="`m-${i}`" type="rect" height="44px" />
            </div>
            <div class="q-mt-md column q-gutter-sm">
                <q-skeleton type="text" width="50%" height="28px" />
                <q-skeleton type="rect" height="56px" />
                <q-skeleton type="rect" height="56px" />
            </div>
        </template>
    </div>
</template>

<script lang="ts" setup>
    withDefaults(
        defineProps<{
            variant?: 'list' | 'mobile';
        }>(),
        { variant: 'list' },
    );
</script>

<style scoped>
    .skeleton {
        width: 100%;
    }
    .skeleton__day-strip {
        display: grid;
        grid-template-columns: repeat(7, minmax(0, 1fr));
        gap: var(--space-1);
    }
</style>
