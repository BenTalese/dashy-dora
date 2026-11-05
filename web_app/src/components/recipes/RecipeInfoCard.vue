<template>
    <!--
        Owner feedback 2026-08-29 — "copy nutrition card style for version
        information and additional information (consistency)".

        The nutrition rollup already wore this treatment (flat bordered card,
        one muted leading glyph, a caption heading, body in the column beside
        it) and the two panels either side of it wore nothing, so the details
        list read as one styled drawer between two unstyled ones. Rather than
        copy the markup a second and third time, the chrome moved here and all
        three callers render through it (R-001) — which is also what stops the
        three drifting apart again the next time one of them is edited.
    -->
    <q-card flat bordered class="ric">
        <q-card-section class="row items-start q-gutter-sm no-wrap">
            <q-icon :name="icon" size="22px" class="dora-text-muted" />
            <div class="col">
                <div v-if="heading" class="text-caption dora-text-muted ric__heading">
                    {{ heading }}
                    <slot name="heading-after" />
                </div>
                <slot />
            </div>
        </q-card-section>
    </q-card>
</template>

<script lang="ts" setup>
    defineProps<{
        /** An `ICONS` value — the card's single leading glyph. */
        icon: string;
        /** Caption-weight title inside the card. Omit for a card whose
         *  expansion header already names it and would only be echoed. */
        heading?: string;
    }>();
</script>

<style scoped>
    .ric { margin-bottom: var(--space-4); }
    .ric__heading { margin-bottom: var(--space-1); }
</style>
