<template>
    <BaseDialog
        :model-value="modelValue"
        title="Watch this price"
        closable
        card-style="width: 380px; max-width: 95vw"
        @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    >
        <q-card-section v-if="product" class="column q-gutter-sm">
            <div class="text-body2">{{ product.name }}</div>
            <div v-if="product.price_now != null" class="text-caption dora-text-muted">
                {{ formatMoney(product.price_now) }} now<template v-if="product.store_name">
                    at {{ product.store_name }}</template>
            </div>
            <MoneyInput
                v-model="threshold"
                label="Alert me at or below"
                autofocus
            />
            <div class="text-caption dora-text-muted">
                You get one alert each time the price reaches this.
            </div>
        </q-card-section>
        <template #actions>
            <BaseButton
                v-if="watch"
                variant="danger-ghost"
                label="Stop watching"
                :loading="busy"
                @click="onRemove"
            />
            <q-space />
            <BaseButton variant="ghost" label="Cancel" v-close-popup />
            <BaseButton
                variant="primary"
                label="Save"
                :loading="busy"
                :disable="!threshold || threshold <= 0"
                @click="onSave"
            />
        </template>
    </BaseDialog>
</template>

<script setup lang="ts">
    /** Set, change or clear the current user's price watch on one product
     *  (owner 2026-10-15: "allow setting price drop alerts directly here").
     *  A product carries at most one watch per user: saving replaces it. The
     *  alert itself is evaluated by `GET /alerts` as the `price_drop` kind. */
    import { ref, watch as watchRef } from 'vue';
    import { useQuasar } from 'quasar';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import MoneyInput from 'src/components/MoneyInput.vue';
    import { formatMoney } from 'src/composables/useMoney';
    import PriceHistoryApiService, { type PriceAlert } from 'src/services/api/priceHistoryApiService';
    import { isAlreadyNotified, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useAlertStore } from 'src/stores/alertStore';
    import type { Product } from 'src/models/product';

    const props = defineProps<{
        modelValue: boolean;
        product: Product | null;
        /** The user's existing watch on this product, if any. */
        watch: PriceAlert | null;
    }>();

    const emit = defineEmits<{
        (e: 'update:modelValue', value: boolean): void;
        (e: 'saved'): void;
    }>();

    const $q = useQuasar();
    const api = new PriceHistoryApiService();
    const alertStore = useAlertStore();
    const threshold = ref<number | null>(null);
    const busy = ref(false);

    watchRef(
        () => props.modelValue,
        (open) => {
            if (!open) return;
            threshold.value = props.watch?.threshold_unit_price ?? null;
        },
    );

    async function onSave(): Promise<void> {
        if (!props.product || !threshold.value) return;
        busy.value = true;
        try {
            await api.createAlertAsync(props.product.product_id, threshold.value);
            $q.notify({
                type: 'positive', 
                message: `Watching for ${formatMoney(threshold.value)} or less.`,
            });
            emit('saved');
            emit('update:modelValue', false);
            void alertStore.refreshAsync();
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative', 
                    message: "Couldn't save the price watch.",
                    caption: toastCaption(err),
                });
            }
        } finally {
            busy.value = false;
        }
    }

    async function onRemove(): Promise<void> {
        if (!props.watch) return;
        busy.value = true;
        try {
            await api.deleteAlertAsync(props.watch.price_alert_id);
            emit('saved');
            emit('update:modelValue', false);
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative', 
                    message: "Couldn't remove the price watch.",
                    caption: toastCaption(err),
                });
            }
        } finally {
            busy.value = false;
        }
    }
</script>
