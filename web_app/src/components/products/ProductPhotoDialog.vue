<template>
    <!--
        Owner 2026-10-17: "are we able to set images for custom products?
        Should only be able to for those." Custom products only: an ingested
        product's picture comes from its source, and the API refuses a change
        there (422), so the card never offers this for one.

        Same shape as the recipe photo: the picture is the uploader
        (ImageEditTile, click it to pick), with Change / Remove spelled out
        underneath for anyone who doesn't think to tap a photo. A pick saves
        straight away, like a store logo — there is nothing else in the dialog
        to confirm it against.
    -->
    <BaseDialog
        :model-value="modelValue"
        title="Product photo"
        closable
        card-style="width: 360px; max-width: 95vw"
        @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    >
        <q-card-section v-if="product">
            <ImageEditTile
                ref="tile"
                class="product-photo__tile"
                :label="hasImage ? `Change the photo of ${product.name}` : `Add a photo of ${product.name}`"
                shape="rounded"
                fill
                :busy="busy"
                @pick="onPick"
                @error="onPickError"
            >
                <!-- Keyed on `version` so a replaced photo refetches: the
                     thumb only reloads when its id or has-image flag changes,
                     and a re-upload changes neither. -->
                <ProductThumb
                    :key="version"
                    fill
                    :product-id="product.product_id"
                    :has-image="hasImage"
                    :alt="product.name"
                    icon-size="48px"
                />
            </ImageEditTile>
            <div v-if="pickError" class="text-caption text-negative q-mt-xs">{{ pickError }}</div>
        </q-card-section>
        <template #actions>
            <BaseButton
                v-if="hasImage"
                variant="danger-ghost"
                :icon="ICONS.delete_outline"
                label="Remove photo"
                :loading="busy"
                @click="onRemove"
            />
            <q-space />
            <BaseButton
                variant="primary"
                :icon="ICONS.photo_camera"
                :label="hasImage ? 'Change photo' : 'Add photo'"
                :loading="busy"
                @click="tile?.openPicker()"
            />
        </template>
    </BaseDialog>
</template>

<script setup lang="ts">
    import { ref, watch } from 'vue';
    import { useQuasar } from 'quasar';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import ImageEditTile from 'src/components/ImageEditTile.vue';
    import ProductThumb from 'src/components/products/ProductThumb.vue';
    import ProductApiService from 'src/services/api/productApiService';
    import { isAlreadyNotified, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import type { ProcessedImage } from 'src/services/files/imageService';
    import type { Product } from 'src/models/product';
    import { ICONS } from 'src/style/icons';

    const props = defineProps<{
        modelValue: boolean;
        product: Product | null;
    }>();

    const emit = defineEmits<{
        (e: 'update:modelValue', value: boolean): void;
        /** The photo changed — the page reloads so the card's flag follows. */
        (e: 'saved'): void;
    }>();

    const $q = useQuasar();
    const api = new ProductApiService();

    const tile = ref<InstanceType<typeof ImageEditTile> | null>(null);
    const busy = ref(false);
    const pickError = ref<string | null>(null);
    // Local copy of the flag: the `product` prop is the page's snapshot from
    // when the dialog opened, and stays stale until the page's reload lands.
    const hasImage = ref(false);
    const version = ref(0);

    watch(
        () => [props.modelValue, props.product] as const,
        ([open, product]) => {
            if (!open || !product) return;
            hasImage.value = product.has_image;
            pickError.value = null;
        },
        { immediate: true },
    );

    async function save(payload: { image: string } | { clear_image: true }, failure: string) {
        if (!props.product) return false;
        busy.value = true;
        try {
            await api.updateAsync({ product_id: props.product.product_id, ...payload });
            version.value += 1;
            emit('saved');
            return true;
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: failure,
                    caption: toastCaption(err),
                });
            }
            return false;
        } finally {
            busy.value = false;
        }
    }

    async function onPick(image: ProcessedImage) {
        // ImageEditTile → processImageFile() has already resized + re-encoded
        // under the install image policy (R-003); the API stores it verbatim.
        pickError.value = null;
        if (await save({ image: image.dataUrl }, 'Could not save the photo.')) {
            hasImage.value = true;
        }
    }

    function onPickError(message: string) {
        pickError.value = message;
    }

    async function onRemove() {
        pickError.value = null;
        if (await save({ clear_image: true }, 'Could not remove the photo.')) {
            hasImage.value = false;
        }
    }
</script>

<style scoped>
    .product-photo__tile {
        width: 100%;
        aspect-ratio: 1 / 1;
        overflow: hidden;
        border-radius: var(--radius-lg);
        background: var(--surface-sunken);
    }
</style>
