<template>
    <!-- A screenshot inside a guide: the app's own card radius and hairline,
         a soft lift, and the image cropped to the surface it explains. Renders
         nothing when the shot has not been taken yet (see helpImages.ts). -->
    <figure v-if="src" class="help-shot">
        <img :src="src" :alt="alt" loading="lazy" decoding="async" class="help-shot__img" />
        <figcaption v-if="caption" class="help-shot__caption">{{ caption }}</figcaption>
    </figure>
</template>

<script setup lang="ts">
    import { computed } from 'vue';
    import { helpImageUrl } from 'src/help/helpImages';

    const props = defineProps<{
        name: string | undefined;
        alt: string;
        caption?: string;
    }>();

    const src = computed(() => helpImageUrl(props.name));
</script>

<style scoped lang="scss">
    .help-shot {
        margin: var(--space-4) 0 0;
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
    }
    .help-shot__img {
        display: block;
        width: 100%;
        max-width: 720px;
        height: auto;
        border-radius: var(--radius-lg);
        border: 1px solid var(--border-default);
        box-shadow: var(--elevation-card);
        background: var(--surface-sunken);
    }
    /* A light-theme capture on a dark page glares; take the edge off. */
    :root[data-theme$="-dark"] .help-shot__img {
        filter: brightness(0.88);
    }
    .help-shot__caption {
        font-size: var(--font-size-xs);
        color: var(--text-muted);
    }
</style>
