<template>
    <!-- The stock-item page's Scanning tab (FU-934 split): Dora's own QR
         label, then the item's real barcodes. Only mounted when the install's
         scanning flag is on (the page hides the tab otherwise). Multi-root on
         purpose: the panel's DOM is exactly what it was before the split. -->
    <template v-if="detail">
        <!-- Dora's own QR label. Fetched through the authenticated
             http client (see useQrLabels) the first time this tab
             is opened, not on page load — most visits never come
             here. -->
        <div class="q-mb-lg">
            <div class="row items-center q-mb-sm">
                <!-- D-008 carve-out (owner, 2026-09-01): asked for
                     "QR Label" title-cased here. It's a section
                     heading, not an interactive control, so the
                     sentence-case rule for buttons/labels doesn't
                     bind it; the Help topic key stays lowercase. -->
                <div class="text-subtitle1">QR Label</div>
                <HelpHint topic="QR label" />
                <q-space />
                <BaseButton
                    variant="secondary"
                    dense
                    :icon="ICONS.print"
                    label="Print"
                    @click="openSingleQrSheet"
                />
            </div>
            <div class="row items-start">
                <AppSkeleton
                    v-if="qrLoading"
                    type="rect"
                    width="256px"
                    height="256px"
                />
                <img
                    v-else-if="qrSrc"
                    :src="qrSrc"
                    alt="QR code"
                    class="stock-detail__qr"
                />
            </div>
            <!-- The error sits BELOW the image rather than in place
                 of it: Print can fail (blocked pop-up) after the
                 code itself loaded fine, and swapping the loaded QR
                 out for that message would read as the code having
                 broken too. -->
            <div v-if="qrError" class="text-negative text-caption q-mt-sm">
                {{ qrError }}
            </div>
        </div>

        <div>
            <div class="row items-center q-mb-sm">
                <div class="text-subtitle1">Barcodes</div>
                <HelpHint topic="Barcodes" />
                <q-space />
                <BaseButton
                    variant="primary"
                    dense
                    :icon="ICONS.add"
                    label="Add barcode"
                    @click="onAddBarcodeClick"
                />
            </div>
            <div
                v-if="detail.barcodes.length === 0"
                class="dora-text-muted text-caption q-pa-md"
            >
                No barcodes yet.
            </div>
            <q-list v-else separator>
                <q-item
                    v-for="bc in detail.barcodes"
                    :key="bc.barcode_id"
                >
                    <q-item-section>
                        <q-item-label class="dora-text-monospace">
                            {{ bc.barcode }}
                        </q-item-label>
                        <!-- Feedback 2026-08-24: the `direct` rows
                             used to be captioned "direct", which is
                             what most people see and says nothing
                             on its own. Only the exception is
                             annotated now — a code that came along
                             with a linked Product, and so isn't
                             removable here. -->
                        <q-item-label
                            v-if="bc.source === 'via_product'"
                            caption
                            class="dora-text-muted"
                        >
                            (from product: {{ bc.product_name ?? '–' }})
                        </q-item-label>
                    </q-item-section>
                    <q-item-section side>
                        <BaseButton
                            :aria-label="`Remove barcode ${bc.barcode}`"
                            v-if="bc.source === 'direct'"
                            variant="icon"
                            :icon="ICONS.delete"
                            class="text-negative"
                            @click="onRemoveBarcode(bc.barcode_id)"
                        >
                            <BaseTooltip>Remove barcode</BaseTooltip>
                        </BaseButton>
                    </q-item-section>
                </q-item>
            </q-list>

            <!-- Add-barcode dialog. Textbox by default;
                 a future polish slot could add a "scan" button
                 when the camera is available. -->
            <BaseDialog
                v-model="addBarcodeOpen"
                title="Add a barcode"
                closable
                card-style="min-width: 320px; max-width: 420px"
            >
                <q-card-section>
                    <div class="text-caption dora-text-muted q-mb-sm">
                        Scanning this code will open
                        <strong>{{ detail.name }}</strong>.
                    </div>
                    <q-input
                        v-model="addBarcodeValue"
                        outlined
                        dense
                        autofocus
                        placeholder="e.g. 9300675001120"
                        label="Barcode (EAN / UPC)"
                        :error="!!addBarcodeError"
                        :error-message="addBarcodeError ?? undefined"
                        @keydown.enter.prevent="onConfirmAddBarcode"
                    />
                </q-card-section>
                <template #actions>
                    <BaseButton variant="ghost" label="Cancel" v-close-popup />
                    <BaseButton
                        variant="primary"
                        label="Add"
                        :loading="addBarcodeSaving"
                        :disable="addBarcodeValue.trim().length === 0"
                        @click="onConfirmAddBarcode"
                    />
                </template>
            </BaseDialog>
        </div>
    </template>
</template>

<script lang="ts" setup>
    import { ref } from 'vue';
    import { useQuasar } from 'quasar';
    import AppSkeleton from 'src/components/AppSkeleton.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import HelpHint from 'src/components/help/HelpHint.vue';
    import { useStockItemDetail } from 'src/composables/useStockItemDetail';
    import { NormalisedApiError } from 'src/services/api/axiosHttpClient';
    import BarcodeApiService from 'src/services/api/barcodeApiService';
    import { describeApiError, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { ICONS } from 'src/style/icons';

    // The QR label's state lives on the page context (so the fetched code
    // survives this panel unmounting on a tab switch); opening this tab is
    // what triggers the fetch — see `useStockItemDetail`.
    const {
        stockItemId,
        detail,
        qrSrc,
        qrLoading,
        qrError,
        openSingleQrSheet,
        withBusyReload,
    } = useStockItemDetail();

    const $q = useQuasar();
    const barcodeApi = new BarcodeApiService();

    // ── FU-056: barcode add / remove ────────────────────────────────────
    const addBarcodeOpen = ref(false);
    const addBarcodeValue = ref('');
    const addBarcodeError = ref<string | null>(null);
    const addBarcodeSaving = ref(false);

    function onAddBarcodeClick() {
        addBarcodeValue.value = '';
        addBarcodeError.value = null;
        addBarcodeOpen.value = true;
    }
    async function onConfirmAddBarcode() {
        const raw = addBarcodeValue.value.trim();
        if (!raw) return;
        addBarcodeError.value = null;
        addBarcodeSaving.value = true;
        try {
            await withBusyReload(() => barcodeApi.registerAsync({
                barcode: raw,
                stock_item_id: stockItemId.value,
            }).then(() => undefined));
            addBarcodeOpen.value = false;
            $q.notify({
                type: 'positive',
                message: 'Barcode added.',
            });
        } catch (err) {
            // 2026-08-21 feedback: pasting an EAN answered "endpoint was not
            // found", which reads as our bug in the barcode itself. It isn't a
            // validation failure at all — it's the API not carrying
            // POST /api/data/barcodes, which is registered in the same module
            // as the QR endpoint the owner also gets a 404 from. Both were
            // proven green over real HTTP on 2026-08-21 (including the exact
            // ISBN-13 he tried), so translate the route miss into the thing he
            // can act on instead of echoing the server's wording.
            addBarcodeError.value = describeBarcodeFailure(err);
        } finally {
            addBarcodeSaving.value = false;
        }
    }
    /** Route-miss 404s get named as such; everything else keeps the server's
     *  own message (already friendly — duplicates, blank values, …). */
    function describeBarcodeFailure(err: unknown): string {
        if (err instanceof NormalisedApiError && err.status === 404) {
            const detail = err.details as { title?: string } | null;
            const title = typeof detail?.title === 'string' ? detail.title : '';
            if (title.toLowerCase().startsWith('endpoint')) {
                return `This server has no barcode endpoint at ${err.url}. Update the Dora server.`;
            }
        }
        return describeApiError(err) || 'Could not add barcode.';
    }

    async function onRemoveBarcode(barcodeId: string) {
        try {
            await withBusyReload(() => barcodeApi.deleteAsync(barcodeId));
            $q.notify({
                type: 'positive',
                message: 'Barcode removed.',
            });
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not remove barcode.',
                caption: toastCaption(err),
            });
        }
    }
</script>

<style scoped>
    .stock-detail__qr {
        width: 256px;
        height: 256px;
        max-width: 100%;
    }
</style>
