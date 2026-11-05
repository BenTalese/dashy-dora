<template>
    <!--
        Read-only viewer for the `image` steps_mode.

        Rebuilt 2026-08-27 from owner feedback: "image steps should just show a
        grid of the images in order with numbers above or under the image.
        Image should be small rounded box shape, and when hovered has an effect
        that shows you can click it, and clicking it previews the image for you
        to read." The previous shape was one full-width photo per row, stacked —
        a page you scrolled rather than a method you scanned, and at 480px wide
        each one was still too small to read a handwritten card from.

        It renders whatever rows the page hands it, which since the same batch
        is the *form's* list rather than the last-loaded recipe's: photos picked
        in this edit session have a `data:` preview and no saved id yet, and
        showing nothing until Save was the "image steps are not showing" bug.
        Each photo renders through `RecipeStepPhoto`, which fetches a saved
        one through the HTTP client (R-045, FU-931).
    -->
    <div v-if="images.length === 0" class="rsiv__empty">
        {{ NO_STEP_IMAGES_COPY }}
    </div>

    <template v-else>
        <ol class="rsiv">
            <li v-for="(image, index) in images" :key="image.client_id" class="rsiv__cell">
                <button
                    type="button"
                    class="rsiv__tile"
                    :aria-label="`Open step photo ${index + 1} full size`"
                    @click="openAt(index)"
                >
                    <RecipeStepPhoto
                        :recipe-id="recipeId"
                        :image-id="image.existing_image_id"
                        :data-url="image.data_url"
                        :alt="`Step photo ${index + 1}`"
                        class="rsiv__img"
                    />
                    <span class="rsiv__veil"><q-icon :name="ICONS.zoom_in" size="26px" /></span>
                </button>
                <span class="rsiv__num">{{ index + 1 }}</span>
            </li>
        </ol>

        <!-- Maximised, because the whole point of opening it is that the
             thumbnail was too small to read. Prev/next because a method is
             walked, not sampled. -->
        <BaseDialog
            v-model="previewOpen"
            :title="`Step photo ${previewIndex + 1} of ${images.length}`"
            closable
            maximized
        >
            <q-card-section class="rsiv__preview">
                <RecipeStepPhoto
                    v-if="previewImage"
                    :recipe-id="recipeId"
                    :image-id="previewImage.existing_image_id"
                    :data-url="previewImage.data_url"
                    :alt="`Step photo ${previewIndex + 1}`"
                    class="rsiv__previewimg"
                />
            </q-card-section>
            <template #actions>
                <BaseButton
                    variant="ghost"
                    :icon="ICONS.chevron_left"
                    label="Previous"
                    :disable="previewIndex === 0"
                    @click="previewIndex -= 1"
                />
                <BaseButton
                    variant="ghost"
                    :icon="ICONS.chevron_right"
                    label="Next"
                    :disable="previewIndex >= images.length - 1"
                    @click="previewIndex += 1"
                />
            </template>
        </BaseDialog>
    </template>
</template>

<script setup lang="ts">
    import RecipeStepPhoto from 'src/components/recipes/RecipeStepPhoto.vue';
    import { computed, ref } from 'vue';

    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import { ICONS } from 'src/style/icons';
    import { NO_STEP_IMAGES_COPY } from 'src/components/recipes/recipeStepImageEditorTypes';
    import type { EditableStepImage } from 'src/components/recipes/recipeStepImageEditorTypes';

    const props = defineProps<{
        images: EditableStepImage[];
        recipeId: string;
    }>();

    const previewOpen = ref(false);
    const previewIndex = ref(0);
    const previewImage = computed(() => props.images[previewIndex.value] ?? null);

    function openAt(index: number) {
        previewIndex.value = index;
        previewOpen.value = true;
    }
</script>

<style scoped lang="scss">
    .rsiv {
        list-style: none;
        margin: 0;
        padding: 0;
        display: grid;
        /* Small rounded boxes that reflow, rather than one column of
           full-bleed photos — the owner's ask, and it finally uses the
           method column's width. */
        grid-template-columns: repeat(auto-fill, minmax(128px, 1fr));
        gap: var(--space-4);
    }
    .rsiv__cell {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--space-1);
    }
    .rsiv__tile {
        appearance: none; padding: 0; border: 1px solid var(--border-default);
        background: var(--surface-sunken);
        position: relative;
        display: block;
        width: 100%;
        aspect-ratio: 1 / 1;
        border-radius: var(--radius-lg);
        overflow: hidden;
        cursor: pointer;
        transition:
            border-color var(--motion-fast) ease,
            box-shadow var(--motion-fast) ease;
    }
    .rsiv__tile:hover,
    .rsiv__tile:focus-visible {
        border-color: var(--brand-primary);
        box-shadow: 0 0 0 2px var(--brand-primary-soft);
        outline: none;
    }
    .rsiv__img { width: 100%; height: 100%; object-fit: cover; display: block; }
    /* The "you can click this" effect. Hidden until hover/focus rather than a
       permanent scrim, so the photo is the photo at rest. */
    .rsiv__veil {
        position: absolute; inset: 0;
        display: flex; align-items: center; justify-content: center;
        background: var(--overlay-scrim);
        color: var(--text-inverse);
        opacity: 0;
        transition: opacity var(--motion-fast) ease;
    }
    .rsiv__tile:hover .rsiv__veil,
    .rsiv__tile:focus-visible .rsiv__veil { opacity: 1; }
    .rsiv__num {
        font-size: var(--font-size-sm); font-weight: 700;
        font-variant-numeric: tabular-nums;
        color: var(--text-muted);
    }
    .rsiv__empty { color: var(--text-muted); font-size: var(--font-size-sm); }

    .rsiv__preview {
        display: flex; align-items: center; justify-content: center;
        /* The dialog is maximised; leave room for its header and actions. */
        height: calc(100vh - 140px);
    }
    .rsiv__previewimg {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
        border-radius: var(--radius-md);
    }
</style>
