<template>
    <!--
        FU-856: how many countable things the pack holds. A carton of eggs is
        sold as 700 g, which says nothing about how many eggs are in it, so a
        recipe's "3 eggs" stayed unpriced until this was recorded. Any
        product, ingested or custom: a scraper rarely knows it either.
    -->
    <BaseDialog
        :model-value="modelValue"
        title="Items in the pack"
        closable
        card-style="width: 360px; max-width: 95vw"
        @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    >
        <q-card-section v-if="product" class="q-gutter-sm">
            <div class="text-caption dora-text-muted">
                {{ product.name }}<span v-if="product.size"> · {{ product.size }}</span>
            </div>
            <q-input
                v-model.number="count"
                type="number"
                min="1"
                step="1"
                outlined
                dense
                autofocus
                label="How many in the pack"
                hint="For eggs or a multipack, e.g. 12. Lets recipes price 3 eggs."
                :error="!!error"
                :error-message="error"
                @keyup.enter="onSave"
            />
        </q-card-section>
        <template #actions>
            <BaseButton
                v-if="product?.pack_count != null"
                variant="danger-ghost"
                label="Clear"
                :loading="busy"
                @click="save(null)"
            />
            <q-space />
            <BaseButton variant="ghost" label="Cancel" v-close-popup />
            <BaseButton variant="primary" label="Save" :loading="busy" @click="onSave" />
        </template>
    </BaseDialog>
</template>

<script setup lang="ts">
    import { ref, watch } from 'vue';
    import { useQuasar } from 'quasar';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import ProductApiService from 'src/services/api/productApiService';
    import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import type { Product } from 'src/models/product';
    import { PACK_COUNT_RULE, parsePackCount } from 'src/helpers/packCount';

    const props = defineProps<{
        modelValue: boolean;
        product: Product | null;
    }>();

    const emit = defineEmits<{
        (e: 'update:modelValue', value: boolean): void;
        (e: 'saved'): void;
    }>();

    const $q = useQuasar();
    const api = new ProductApiService();

    const count = ref<number | null>(null);
    const error = ref('');
    const busy = ref(false);

    watch(
        () => [props.modelValue, props.product] as const,
        ([open, product]) => {
            if (!open || !product) return;
            count.value = product.pack_count;
            error.value = '';
        },
        { immediate: true },
    );

    function onSave(): void {
        const value = parsePackCount(count.value);
        if (value === null || value === undefined) {
            error.value = `Enter ${PACK_COUNT_RULE}.`;
            return;
        }
        void save(value);
    }

    async function save(value: number | null): Promise<void> {
        if (!props.product) return;
        busy.value = true;
        try {
            await api.updateAsync({ product_id: props.product.product_id, pack_count: value });
            emit('saved');
            emit('update:modelValue', false);
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not save the pack count.',
                caption: toastCaption(err),
            });
        } finally {
            busy.value = false;
        }
    }
</script>
