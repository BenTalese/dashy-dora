<template>
    <!--
        PROPOSAL_RECIPE_IMAGE_STEPS — editor for the "image" steps_mode.

        The user uploads ordered photos of their recipe steps (a cookbook
        spread, a handwritten card, a printout); we resize + re-encode via
        the centralised `processImageFile` and emit data-URLs for the
        recipe save path to send.

        Intentionally the dumbest editor in the app — no captions, no
        per-image notes, no OCR. Pictures are pictures. R-007.
    -->
    <div class="recipe-step-images-editor">
        <div
            v-if="modelValue.length === 0"
            class="recipe-step-images-editor__empty dora-text-muted q-mb-sm"
        >
            {{ NO_STEP_IMAGES_COPY }}
        </div>

        <!-- Owner feedback 2026-08-27 — the same grid of small rounded tiles
             the read view uses, so switching the pencil on doesn't change what
             the method looks like, only what you can do to it. Each tile keeps
             its own reorder/remove cluster rather than a separate list row. -->
        <ol v-if="modelValue.length > 0" class="rsie">
            <li v-for="(row, index) in modelValue" :key="row.client_id" class="rsie__cell">
                <div class="rsie__tile">
                    <img
                        :src="row.preview_url"
                        :alt="`Step photo ${index + 1}`"
                        class="rsie__img"
                    />
                </div>
                <div class="rsie__acts">
                    <span class="rsie__num">{{ index + 1 }}</span>
                    <BaseButton
                        variant="icon" dense
                        :icon="ICONS.arrow_upward"
                        :aria-label="`Move step photo ${index + 1} earlier`"
                        :disable="index === 0"
                        @click="onMove(row.client_id, -1)"
                    />
                    <BaseButton
                        variant="icon" dense
                        :icon="ICONS.arrow_downward"
                        :aria-label="`Move step photo ${index + 1} later`"
                        :disable="index === modelValue.length - 1"
                        @click="onMove(row.client_id, +1)"
                    />
                    <BaseButton
                        variant="danger-icon" dense
                        :icon="ICONS.delete"
                        :aria-label="`Remove step photo ${index + 1}`"
                        @click="onRemove(row.client_id)"
                    />
                </div>
            </li>
        </ol>

        <div class="row q-gutter-sm q-mt-sm items-center">
            <ImageSourcePicker
                variant="secondary"
                take-photo-label="Take a photo"
                :pick-label="addVerb"
                multiple
                accept="image/jpeg,image/png,image/webp"
                :loading="busy"
                :disabled="atCap"
                @pick="onPick"
                @error="onError"
            />
            <div v-if="atCap" class="text-caption dora-text-muted">
                Image cap reached ({{ MAX_IMAGES }}). Remove one to add another.
            </div>
        </div>
        <div v-if="error" class="text-caption text-negative q-mt-xs">{{ error }}</div>
    </div>
</template>

<script setup lang="ts">
    import { computed, ref } from 'vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import { ICONS } from 'src/style/icons';
    import ImageSourcePicker from 'src/components/ImageSourcePicker.vue';
    import type { ProcessedImage } from 'src/services/files/imageService';
    import { NO_STEP_IMAGES_COPY } from 'src/components/recipes/recipeStepImageEditorTypes';
    import type { EditableStepImage } from 'src/components/recipes/recipeStepImageEditorTypes';
    import { newClientId } from 'src/helpers/clientId';

    const props = defineProps<{
        modelValue: EditableStepImage[];
    }>();

    const emit = defineEmits<{
        (e: 'update:modelValue', value: EditableStepImage[]): void;
    }>();

    // Soft cap mirrored from the server (recipe_step_image_access.MAX_…).
    const MAX_IMAGES = 20;

    const error = ref<string | null>(null);
    const busy = ref(false);

    const atCap = computed(() => props.modelValue.length >= MAX_IMAGES);
    const addVerb = computed(() =>
        props.modelValue.length === 0 ? 'Add images' : 'Add more',
    );

    // ImageSourcePicker emits one `pick` per file in order, so we buffer
    // into a transient queue and flush after processing settles. The cap
    // check happens here (the primitive is cap-agnostic).
    const pickQueue = ref<EditableStepImage[]>([]);
    let flushTimer: ReturnType<typeof setTimeout> | null = null;

    function onPick(image: ProcessedImage) {
        error.value = null;
        if (props.modelValue.length + pickQueue.value.length >= MAX_IMAGES) {
            error.value = `Image cap is ${MAX_IMAGES}. Some files were skipped.`;
            return;
        }
        busy.value = true;
        pickQueue.value.push({
            client_id: newClientId(),
            existing_image_id: null,
            preview_url: image.dataUrl,
            data_url: image.dataUrl,
        });
        // Coalesce a burst of `pick` events into one update so the parent
        // sees one append, not N. Settles a tick after the last emit.
        if (flushTimer) clearTimeout(flushTimer);
        flushTimer = setTimeout(flushQueue, 0);
    }

    function flushQueue() {
        flushTimer = null;
        const queued = pickQueue.value;
        pickQueue.value = [];
        busy.value = false;
        if (queued.length === 0) return;
        emit('update:modelValue', [...props.modelValue, ...queued]);
    }

    function onError(message: string) {
        error.value = message;
        busy.value = false;
    }

    function onRemove(clientId: string) {
        emit(
            'update:modelValue',
            props.modelValue.filter(row => row.client_id !== clientId),
        );
    }

    function onMove(clientId: string, delta: -1 | 1) {
        const list = [...props.modelValue];
        const idx = list.findIndex(r => r.client_id === clientId);
        if (idx < 0) return;
        const target = idx + delta;
        if (target < 0 || target >= list.length) return;
        const moved = list.splice(idx, 1)[0];
        if (!moved) return;
        list.splice(target, 0, moved);
        emit('update:modelValue', list);
    }
</script>

<style scoped lang="scss">
    /* Mirrors `RecipeStepImagesViewer`'s grid deliberately — the two faces of
       the same block. (The old rules here reached for `--space-sm`,
       `--c-line`, `--c-surface-2` and `--c-text-muted`, none of which are
       tokens this app defines; every border and colour below was silently
       inheriting nothing. D-017.) */
    .rsie {
        list-style: none;
        margin: 0;
        padding: 0;
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(128px, 1fr));
        gap: var(--space-4, 16px);
    }
    .rsie__cell { display: flex; flex-direction: column; gap: var(--space-1, 4px); }
    .rsie__tile {
        width: 100%;
        aspect-ratio: 1 / 1;
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg, 10px);
        overflow: hidden;
        background: var(--surface-sunken);
    }
    .rsie__img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .rsie__acts {
        display: flex; align-items: center; gap: var(--space-1, 4px);
        justify-content: center;
    }
    .rsie__num {
        font-size: 0.8125rem; font-weight: 700;
        font-variant-numeric: tabular-nums;
        color: var(--text-muted);
        margin-right: auto;
        padding-left: var(--space-1, 4px);
    }
</style>
