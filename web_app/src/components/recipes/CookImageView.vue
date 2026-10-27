<template>
    <!--
        PROPOSAL_RECIPE_IMAGE_STEPS — cook-mode renderer for `steps_mode
        === 'image'`. Ingredients panel + finish flow stay shared with the
        other modes (rendered by the host page, not here).

        Owner feedback 2026-08-28: *"When in image mode, I feel there should be
        one image displayed at a time, with next/prev buttons, and a zoom
        function maybe? Text might be small to read."* It was a vertical scroll
        of every photo at once, which on a phone means the cook scrolls to find
        their place and loses it the moment they touch the screen with a floury
        hand. It is now paged: one photo, the same Previous/Next pair the step
        view uses, and a zoom that actually magnifies (2.5x with pan) rather
        than just showing the same fit-to-screen image bigger — which is the
        whole point when the photo is of a page of small print.
    -->
    <div class="cook-image-view">
        <div
            v-if="images.length === 0"
            class="cook-image-view__empty dora-text-muted text-center q-pa-xl"
        >
            This recipe is in image mode but has no images yet.
            Add some from the recipe's edit page.
        </div>

        <template v-else>
            <CookStepProgress :current="index" :total="images.length" noun="Photo" class="q-mb-md" />

            <div class="cook-image-view__frame">
                <img
                    v-if="currentImage && !failed.has(currentImage.image_id)"
                    :src="srcFor(currentImage)"
                    :alt="`Step ${index + 1}`"
                    class="cook-image-view__image"
                    @click="openZoom()"
                    @error="markFailed(currentImage.image_id)"
                />
                <!-- A broken <img> renders its alt text, which here reads as a
                     plain "Step 1" line and is indistinguishable from a recipe
                     that simply has no photo. Say what actually happened. -->
                <div v-else class="cook-image-view__broken dora-text-muted text-center q-pa-xl">
                    <q-icon :name="ICONS.image_not_supported" size="32px" />
                    <div class="text-caption q-mt-xs">This step's photo couldn't be loaded.</div>
                </div>
                <BaseButton
                    v-if="currentImage && !failed.has(currentImage.image_id)"
                    variant="filled-icon"
                    :icon="ICONS.zoom_in"
                    class="cook-image-view__zoom-trigger"
                    aria-label="Zoom this photo"
                    @click="openZoom()"
                >
                    <BaseTooltip>Zoom in</BaseTooltip>
                </BaseButton>
            </div>

            <!-- The step view's nav row, so muscle memory carries between the
                 two faces. -->
            <CookNavRow
                class="q-mt-md"
                :size="navSize"
                :can-prev="index > 0"
                :is-last="isLast"
                @prev="previous"
                @next="next"
            />
        </template>

        <q-dialog v-model="zoomOpen" maximized>
            <q-card class="cook-image-view__zoom">
                <q-card-section class="cook-image-view__zoom-bar row items-center q-pa-sm">
                    <span class="text-subtitle2">Photo {{ index + 1 }} of {{ images.length }}</span>
                    <q-space />
                    <BaseButton
                        variant="icon"
                        :icon="magnified ? ICONS.zoom_out : ICONS.zoom_in"
                        :aria-label="magnified ? 'Fit photo to screen' : 'Magnify photo'"
                        @click="magnified = !magnified"
                    >
                        <BaseTooltip>{{ magnified ? 'Fit to screen' : 'Magnify' }}</BaseTooltip>
                    </BaseButton>
                    <BaseButton
                        variant="icon"
                        :icon="ICONS.close"
                        aria-label="Close zoom"
                        @click="zoomOpen = false"
                    >
                        <BaseTooltip>Close</BaseTooltip>
                    </BaseButton>
                </q-card-section>
                <!-- Scroll container, so the magnified image can be panned by
                     dragging on touch and scrolling on desktop without any
                     gesture code of our own. -->
                <div class="cook-image-view__zoom-body">
                    <img
                        v-if="currentImage && !failed.has(currentImage.image_id)"
                        :src="srcFor(currentImage)"
                        :alt="`Step ${index + 1}`"
                        class="cook-image-view__zoom-image"
                        :class="{ 'cook-image-view__zoom-image--magnified': magnified }"
                        @click="magnified = !magnified"
                        @error="markFailed(currentImage.image_id)"
                    />
                    <div v-else class="dora-text-muted text-center q-pa-xl">
                        <q-icon :name="ICONS.image_not_supported" size="48px" />
                        <div class="q-mt-sm">This step's photo couldn't be loaded.</div>
                    </div>
                </div>
                <!-- Paging stays available while zoomed: comparing two photos
                     of small print means flipping between them at size, not
                     closing the dialog twice. -->
                <q-card-section class="cook-image-view__zoom-nav q-pa-sm">
                    <CookNavRow
                        :can-prev="index > 0"
                        :is-last="isLast"
                        page-only
                        @prev="previous"
                        @next="index += 1"
                    />
                </q-card-section>
            </q-card>
        </q-dialog>
    </div>
</template>

<script setup lang="ts">
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { computed, reactive, ref, watch } from 'vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import CookNavRow from 'src/components/recipes/CookNavRow.vue';
    import CookStepProgress from 'src/components/recipes/CookStepProgress.vue';
    import { recipeStepImageUrl } from 'src/services/api/recipeApiService';
    import { ICONS } from 'src/style/icons';
    import type { RecipeStepImage } from 'src/models/recipe';

    const props = defineProps<{
        recipeId: string;
        images: RecipeStepImage[];
        /** The host's nav button size (it knows the viewport; R-019). */
        navSize?: 'md' | 'lg' | undefined;
    }>();

    /** Image mode had no way to end a cook: the host page renders its
     *  Previous/Repeat/Next row only for the step faces, and `openFinish()` is
     *  reached from that row's last "Next". So a photo recipe could be cooked
     *  but never finished — no stock decrement, no meals logged. The last
     *  photo's Next is "Finish" and the host owns what that means. */
    const emit = defineEmits<{ (e: 'finish'): void }>();

    const index = ref(0);
    const zoomOpen = ref(false);
    const magnified = ref(false);
    /** Image ids whose fetch failed, so the row can say so rather than
     *  degrading to bare alt text. `reactive` (not `ref`) because a Set
     *  mutated in place needs deep reactivity to re-render. */
    const failed = reactive(new Set<string>());

    const currentImage = computed<RecipeStepImage | null>(() => props.images[index.value] ?? null);
    const isLast = computed(() => index.value >= props.images.length - 1);

    // A recipe re-fetched with fewer photos (or swapped entirely) must not
    // leave the pager pointing past the end at a blank frame.
    watch(
        () => props.images.length,
        (length) => {
            if (index.value > length - 1) index.value = Math.max(0, length - 1);
        },
    );

    // Magnification is a per-viewing choice, not a sticky preference: reopening
    // the dialog should start fit-to-screen.
    watch(zoomOpen, (open) => {
        if (!open) magnified.value = false;
    });

    /** R-003 — the step-image URL has one builder, `recipeStepImageUrl`, which
     *  prefixes `resolveBaseURL()`. This component hand-rolled the path as a
     *  literal `/api/...`, which only resolves when the SPA is served from the
     *  same origin as the API. Anywhere else — the dev server, the desktop
     *  bundle, a reverse-proxied self-host on a sub-path — every step image
     *  404'd and the browser fell back to the `alt` text, which is exactly the
     *  reported *"photo steps don't appear, it's just text like 'step 1', and
     *  tapping it shows a broken modal"* (owner feedback 2026-08-27). */
    function srcFor(image: RecipeStepImage): string {
        return recipeStepImageUrl(props.recipeId, image.image_id);
    }

    function markFailed(imageId: string) {
        failed.add(imageId);
    }

    function openZoom() {
        zoomOpen.value = true;
    }

    function previous() {
        if (index.value > 0) index.value -= 1;
    }

    function next() {
        if (isLast.value) {
            zoomOpen.value = false;
            emit('finish');
            return;
        }
        index.value += 1;
    }
</script>

<style scoped lang="scss">
    .cook-image-view {
        margin-bottom: var(--space-6);
    }
    .cook-image-view__frame {
        position: relative;
        display: flex;
    }
    .cook-image-view__image {
        width: 100%;
        height: auto;
        max-height: 70vh;
        object-fit: contain;
        border-radius: var(--radius-md);
        border: 1px solid var(--border-default);
        background: var(--surface-sunken);
        cursor: zoom-in;
    }
    .cook-image-view__broken {
        flex: 1 1 auto;
        border: 1px dashed var(--border-default);
        border-radius: var(--radius-md);
        background: var(--surface-sunken);
    }
    /* Sits on the photo rather than beside it — the photo is the whole surface
       in this mode, and a control below it would push the nav row off a phone. */
    .cook-image-view__zoom-trigger {
        position: absolute;
        top: var(--space-3);
        right: var(--space-3);
    }
    .cook-image-view__zoom {
        background: var(--surface-component);
        display: flex;
        flex-direction: column;
    }
    .cook-image-view__zoom-bar,
    .cook-image-view__zoom-nav {
        flex: 0 0 auto;
        background: var(--surface-elevated);
    }
    .cook-image-view__zoom-body {
        flex: 1 1 auto;
        overflow: auto;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .cook-image-view__zoom-image {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
        cursor: zoom-in;
    }
    /* `max-width: none` is what lets the image exceed the scroll container and
       therefore be panned; without it the scale() would just clip. */
    .cook-image-view__zoom-image--magnified {
        max-width: none;
        max-height: none;
        width: 250%;
        cursor: zoom-out;
    }
</style>
