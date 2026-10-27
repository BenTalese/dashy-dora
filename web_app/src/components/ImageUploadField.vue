<template>
    <!--
        Generic image upload field. Owns the preview/placeholder render and
        the Remove button; the source-pick UX (Take photo vs Choose image)
        is delegated to the shared `ImageSourcePicker` primitive (FU-334 /
        R-0NN) so the camera-vs-gallery story stays one decision instead of
        per-site.

        The parent owns the value (preview URL + whether it changed) and the
        commit semantics — this component only emits `pick` (data URL ready)
        and `clear`. Originally built for recipes (RecipeImageField),
        generalised when further surfaces (account avatar, store logo) adopted
        it (R-001 second-consumer threshold). (Stock-item image *editing* was
        removed — items show their linked product's image, not a user upload —
        so the old FU-126 stock-item consumer no longer exists; see FU-607.)
        Current consumer: the custom-product create dialog (2026-10-17).
    -->
    <div class="image-upload-field">
        <div class="image-upload-field__preview" :style="previewUrl ? '' : placeholderStyle">
            <img v-if="previewUrl" :src="previewUrl" :alt="altText" />
            <span v-else class="image-upload-field__placeholder">{{ initial }}</span>
        </div>
        <div class="row q-gutter-sm q-mt-sm items-center">
            <ImageSourcePicker
                variant="secondary"
                take-photo-label="Take a photo"
                :pick-label="`${actionVerb} image`"
                @pick="onPick"
                @error="onError"
            />
            <BaseButton
                v-if="canClear"
                variant="ghost"
                :icon="ICONS.delete_outline"
                label="Remove"
                @click="emit('clear')"
            />
        </div>
        <div v-if="error" class="text-caption text-negative q-mt-xs">{{ error }}</div>
    </div>
</template>

<script setup lang="ts">
    import { computed, ref } from 'vue';
    import { ICONS } from 'src/style/icons';
    import BaseButton from 'src/components/BaseButton.vue';
    import ImageSourcePicker from 'src/components/ImageSourcePicker.vue';
    import type { ProcessedImage } from 'src/services/files/imageService';

    const props = defineProps<{
        previewUrl: string | null;
        name?: string;
        alt?: string;
        // When omitted, Remove appears whenever `previewUrl` is set
        // (existing call-site behaviour). Surfaces with a fallback preview
        // (e.g. product image on a stock item) pass `false` so the button
        // reads "Add image" and Remove is hidden — the user never uploaded
        // that image, so there's nothing to remove.
        canClear?: boolean;
    }>();

    const emit = defineEmits<{
        (e: 'pick', dataUrl: string): void;
        (e: 'clear'): void;
    }>();

    const error = ref<string | null>(null);

    const initial = computed(() => (props.name?.trim()[0] ?? '?').toUpperCase());
    const placeholderStyle = computed(() => {
        let hash = 0;
        for (const ch of props.name ?? '') hash = (hash * 31 + ch.charCodeAt(0)) % 360;
        return `background: hsl(${hash}, 45%, 42%)`;
    });
    const altText = computed(() => props.alt ?? props.name ?? 'Image');
    const canClear = computed(() =>
        props.canClear !== undefined ? props.canClear : !!props.previewUrl,
    );
    const actionVerb = computed(() => (canClear.value ? 'Change' : 'Add'));

    function onPick(image: ProcessedImage) {
        error.value = null;
        emit('pick', image.dataUrl);
    }
    function onError(message: string) {
        error.value = message;
    }
</script>

<style scoped lang="scss">
    .image-upload-field__preview {
        width: 100%;
        height: 180px;
        border-radius: var(--radius-lg);
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .image-upload-field__preview img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    /* R-002 carve-out: the placeholder sits on the name-hashed hsl fill set
       inline above, not on a themed surface, so its ink is the fixed
       near-white that holds against every hue that hash can produce. */
    .image-upload-field__placeholder {
        font-size: var(--font-size-3xl);
        font-weight: 700;
        color: rgba(255, 255, 255, 0.92);
    }
</style>
