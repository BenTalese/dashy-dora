<template>
    <!-- receipt-photo record-keeping. Visible only
         once the list is being shopped or finished; pure
         record-keeping (no OCR, no parsing). Multi-photo;
         tap to zoom, trash to remove. Source-pick UX
         (Take photo vs Choose image) is delegated to the
         shared ImageSourcePicker primitive (R-0NN). -->
    <div
        v-if="attachmentSectionVisible"
        class="sld-receipts q-mt-lg"
    >
        <div class="row items-center q-mb-sm">
            <div class="text-subtitle2 text-weight-medium">
                Receipts
            </div>
            <q-space />
            <ImageSourcePicker
                variant="ghost"
                take-photo-label="Take photo"
                pick-label="Choose receipt"
                :loading="attachmentUploading"
                @pick="onAttachmentPicked"
                @error="onAttachmentError"
            />
        </div>
        <div
            v-if="(detail?.attachments?.length ?? 0) === 0"
            class="text-caption dora-text-muted"
        >
            No receipts yet.
        </div>
        <div v-else class="sld-receipt-strip row q-gutter-sm">
            <div
                v-for="att in detail?.attachments"
                :key="att.attachment_id"
                class="sld-receipt-thumb"
            >
                <ShoppingListReceiptImage
                    :list-id="listId"
                    :attachment-id="att.attachment_id"
                    @click="attachmentZoomId = att.attachment_id"
                />
                <BaseButton
                    aria-label="Remove receipt"
                    variant="ghost"
                    :icon="ICONS.delete"
                    class="sld-receipt-delete"
                    dense
                    @click="onDeleteAttachment(att.attachment_id)"
                >
                    <BaseTooltip>Remove receipt</BaseTooltip>
                </BaseButton>
            </div>
        </div>
    </div>

    <!-- Full-screen receipt viewer (lightbox). Tap thumb to
         open; tap the dialog backdrop or hit Esc to close. -->
    <BaseDialog
        :model-value="attachmentZoomId !== null"
        max-width="900px"
        @update:model-value="(v) => { if (!v) attachmentZoomId = null }"
    >
        <ShoppingListReceiptImage
            v-if="attachmentZoomId"
            :list-id="listId"
            :attachment-id="attachmentZoomId"
            class="sld-receipt-zoom"
        />
    </BaseDialog>
</template>

<script lang="ts" setup>
    /**
     * Receipt photos on a list being shopped or finished, plus the lightbox.
     * Extracted from `ShoppingListDetail.vue` (FU-780).
     */
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import ImageSourcePicker from 'src/components/ImageSourcePicker.vue';
    import ShoppingListReceiptImage from 'src/components/shoppingList/ShoppingListReceiptImage.vue';
    import { ICONS } from 'src/style/icons';
    import { useShoppingListDetail } from 'src/composables/useShoppingListDetail';
    import type { ProcessedImage } from 'src/services/files/imageService';
    import { isAlreadyNotified, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useQuasar } from 'quasar';
    import { computed, ref } from 'vue';

    const $q = useQuasar();
    const { api, listId, detail, refreshDetailQuietly } = useShoppingListDetail();

    // ── Receipt attachments (FU-334) ────────────────────────────────────
    // Pure record-keeping: attach 1..N receipt photos to a `shopping` or
    // `done` list; tap to zoom; trash to remove. No OCR. ImageSourcePicker
    // owns the source-pick UX (Take photo vs Choose image) AND the
    // `processImageFile` chokepoint (R-003) — this handler just receives
    // a `ProcessedImage` and POSTs the data URL.
    const attachmentUploading = ref(false);
    const attachmentZoomId = ref<string | null>(null);

    const attachmentSectionVisible = computed(
        () => !!detail.value && detail.value.status !== 'draft',
    );

    async function onAttachmentPicked(image: ProcessedImage) {
        if (!detail.value || !listId.value) return;
        attachmentUploading.value = true;
        try {
            await api.addAttachmentAsync(listId.value, image.dataUrl);
            // Re-fetch to pick up the server-assigned id + sequence. Quietly
            // (R-084): an in-place edit, not a navigation.
            await refreshDetailQuietly();
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not attach receipt.',
                    caption: toastCaption(err),
                });
            }
        } finally {
            attachmentUploading.value = false;
        }
    }

    function onAttachmentError(message: string) {
        // ImageSourcePicker has already surfaced the inline error caption;
        // mirror it as a toast so the failure is visible even if the user
        // scrolled past the picker.
        $q.notify({
            type: 'negative',
            message: 'Could not read that image.',
            caption: message,
        });
    }

    async function onDeleteAttachment(attachmentId: string) {
        if (!detail.value) return;
        try {
            await api.deleteAttachmentAsync(listId.value, attachmentId);
            // Optimistic local removal so the strip updates without a re-fetch
            // round-trip; a failure re-reads quietly to stay authoritative.
            detail.value.attachments = (detail.value.attachments ?? []).filter(
                (a) => a.attachment_id !== attachmentId,
            );
            if (attachmentZoomId.value === attachmentId) {
                attachmentZoomId.value = null;
            }
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not remove receipt.',
                    caption: toastCaption(err),
                });
            }
            await refreshDetailQuietly();
        }
    }

</script>

<style scoped>
    /* FU-334 — receipt thumb strip + lightbox viewer. */
    .sld-receipt-strip {
        flex-wrap: wrap;
    }
    .sld-receipt-thumb {
        position: relative;
        width: 96px;
        height: 96px;
        border-radius: 6px;
        overflow: hidden;
        background: var(--surface-component);
        box-shadow: var(--elevation-2);
    }
    .sld-receipt-thumb img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        cursor: zoom-in;
        display: block;
    }
    .sld-receipt-delete {
        position: absolute;
        top: 2px;
        right: 2px;
        background: var(--surface-component);
        border-radius: 50%;
    }
    .sld-receipt-zoom {
        max-width: 100%;
        max-height: 80vh;
        display: block;
        margin: 0 auto;
    }
</style>
