<template>
    <BaseDialog
        v-model="open"
        title="Add a custom product"
        closable
        card-style="min-width: 420px; max-width: 520px"
    >
        <q-card-section class="q-pb-none">
            <div class="text-caption dora-text-muted">
                For a shop Dora can't check automatically, like a butcher or a
                market stall.
            </div>
        </q-card-section>

        <q-card-section class="q-gutter-md">
            <q-input
                v-model="form.name"
                outlined
                dense
                autofocus
                label="Product name *"
                :error="!!errors.name"
                :error-message="errors.name"
            />
            <q-input v-model="form.brand" outlined dense label="Brand" />

            <BaseSelect
                v-model="form.storeName"
                :options="storeOptions"
                emit-value
                map-options
                label="Store *"
                empty-text="Choose a store"
                dialog-title="Store"
                :error="!!errors.storeName"
                :error-message="errors.storeName"
            >
                <template #option="{ opt, itemProps }">
                    <q-item v-bind="itemProps">
                        <q-item-section avatar style="min-width: 0; padding-right: 8px">
                            <StoreLogo :name="opt.label" :height="20" :width="34" />
                        </q-item-section>
                        <q-item-section>
                            <q-item-label>{{ opt.label }}</q-item-label>
                        </q-item-section>
                    </q-item>
                </template>
            </BaseSelect>
            <!-- The endpoint refuses to auto-create stores (they're
                 user-curated in Settings), so say where to add one rather than
                 letting the save fail with a validation error. -->
            <div class="text-caption dora-text-muted">
                Not listed?
                <router-link to="/settings/stores" class="text-primary">
                    Add the store first
                </router-link>.
            </div>

            <div class="row q-col-gutter-sm">
                <div class="col-6">
                    <MoneyInput
                        v-model="form.priceNow"
                        label="Price *"
                        :error="!!errors.priceNow"
                        :error-message="errors.priceNow"
                    />
                </div>
                <div class="col-6">
                    <q-input
                        v-model="form.size"
                        outlined
                        dense
                        label="Size *"
                        hint="e.g. 1kg, 500ml"
                        :error="!!errors.size"
                        :error-message="errors.size"
                    />
                </div>
            </div>

            <!-- FU-856: a pack sold by weight doesn't say how many are in it,
                 so a recipe's "3 eggs" can't be priced without this. -->
            <q-input
                v-model.number="form.packCount"
                type="number"
                min="1"
                step="1"
                outlined
                dense
                label="Items in the pack"
                hint="Optional. For eggs or a multipack, e.g. 12"
                :error="!!errors.packCount"
                :error-message="errors.packCount"
            />

            <!-- Owner 2026-10-17: custom products can carry a photo (an
                 ingested one's comes from its source). Optional, so it sits
                 last; the card's menu can add or change it later. -->
            <ImageUploadField
                :preview-url="form.image"
                :name="form.name"
                :alt="form.name ? `Photo of ${form.name}` : 'Product photo'"
                @pick="form.image = $event"
                @clear="form.image = null"
            />
        </q-card-section>

        <template #actions>
            <BaseButton variant="ghost" label="Cancel" v-close-popup />
            <BaseButton
                variant="primary"
                label="Add product"
                :loading="busy"
                @click="onSave"
            />
        </template>
    </BaseDialog>
</template>

<script setup lang="ts">
    /** Hand-enter a product Dora can't scrape (OD-2).
     *
     *  `PreferredBuy` was meant to cover this and can't: it is a label with no
     *  price, store or history, so a user wanting to record "the butcher's
     *  mince is $12/kg" had to choose between a note they couldn't compare and
     *  a product they couldn't create.
     *
     *  Deliberately fewer fields than the shape `POST /products` accepts. A
     *  scraper fills stockcode, availability and a was-price because it
     *  has them; asking a person to type them would be asking for data they
     *  don't have to make the form look complete. `size_value`/`size_unit` are
     *  split out of the single "Size" box here rather than asked for twice.
     *  (A photo *is* offered, optionally — owner 2026-10-17 — since a phone
     *  camera makes it easy and only custom products can carry one.)
     */
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import BaseSelect from 'src/components/BaseSelect.vue';
    import ImageUploadField from 'src/components/ImageUploadField.vue';
    import MoneyInput from 'src/components/MoneyInput.vue';
    import StoreLogo from 'src/components/StoreLogo.vue';
    import ProductApiService from 'src/services/api/productApiService';
    import StoresApiService from 'src/services/api/storesApiService';
    import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useQuasar } from 'quasar';
    import { computed, reactive, ref, watch } from 'vue';
    import { PACK_COUNT_RULE, parsePackCount } from 'src/helpers/packCount';
    import { UNIT_TABLE } from 'src/generated/units_table';

    const open = defineModel<boolean>({ required: true });
    const emit = defineEmits<{ (e: 'created'): void }>();

    const $q = useQuasar();
    const productApi = new ProductApiService();
    const storesApi = new StoresApiService();

    const busy = ref(false);
    const stores = ref<{ store_id: string; name: string }[]>([]);

    const form = reactive({
        name: '',
        brand: '',
        storeName: null as string | null,
        priceNow: null as number | null,
        size: '',
        packCount: null as number | string | null,
        image: null as string | null,
    });
    const errors = reactive({
        name: '', storeName: '', priceNow: '', size: '', packCount: '',
    });

    const storeOptions = computed(
        () => stores.value.map((s) => ({ label: s.name, value: s.name })),
    );

    watch(open, async (isOpen) => {
        if (!isOpen) return;
        form.name = '';
        form.brand = '';
        form.storeName = null;
        form.priceNow = null;
        form.size = '';
        form.packCount = null;
        form.image = null;
        Object.keys(errors).forEach((k) => { errors[k as keyof typeof errors] = ''; });
        try {
            stores.value = await storesApi.listAllAsync();
        } catch {
            stores.value = [];
        }
    });

    // Clear each field's error as soon as the user addresses it. Without this
    // the message stays until the next save attempt, so a corrected field goes
    // on shouting at someone who has already fixed it — which reads as the form
    // not noticing, and trains people to ignore the red.
    watch(() => form.name, (v) => { if (v.trim()) errors.name = ''; });
    watch(() => form.storeName, (v) => { if (v) errors.storeName = ''; });
    watch(() => form.priceNow, (v) => { if (v !== null && v > 0) errors.priceNow = ''; });
    watch(() => form.size, (v) => {
        if (splitSize(v).value !== null) errors.size = '';
    });

    /** Split "1kg" / "500 ml" into value + unit.
     *
     *  The API wants `size`, `size_value` and `size_unit` separately — a
     *  scraper has all three. Asking a person for the same fact three times
     *  would be silly, so one box is parsed. Returns nulls when it can't, and
     *  the caller treats that as a validation failure rather than guessing.
     */
    function splitSize(raw: string): { value: number | null; unit: string | null } {
        const match = /^\s*([\d.]+)\s*([a-zA-Z]+)\s*$/.exec(raw);
        if (!match) return { value: null, unit: null };
        const value = Number.parseFloat(match[1]!);
        if (!Number.isFinite(value) || value <= 0) return { value: null, unit: null };
        // Stored as the unit table's key (`kg`, `ml`, `l`), the casing every
        // ingested row carries; a unit Dora can't cost is rejected here.
        const unit = match[2]!.toLowerCase();
        if (!(unit in UNIT_TABLE)) return { value: null, unit: null };
        return { value, unit };
    }

    /** Blank is fine (most products are one item or free weight). */
    const packCountValue = (): number | null | undefined => parsePackCount(form.packCount);

    function validate(): { value: number; unit: string } | null {
        Object.keys(errors).forEach((k) => { errors[k as keyof typeof errors] = ''; });
        let ok = true;

        if (!form.name.trim()) { errors.name = 'Give it a name.'; ok = false; }
        if (!form.storeName) { errors.storeName = 'Pick a store.'; ok = false; }
        if (form.priceNow === null || form.priceNow <= 0) {
            errors.priceNow = 'Enter what it costs.';
            ok = false;
        }

        if (packCountValue() === undefined) {
            errors.packCount = `Use ${PACK_COUNT_RULE}, or leave it blank.`;
            ok = false;
        }

        const size = splitSize(form.size);
        if (size.value === null || size.unit === null) {
            errors.size = 'Use a number and a unit Dora knows, like 1kg or 500ml.';
            ok = false;
        }

        return ok && size.value !== null && size.unit !== null
            ? { value: size.value, unit: size.unit }
            : null;
    }

    async function onSave(): Promise<void> {
        const size = validate();
        if (size === null) return;

        busy.value = true;
        try {
            await productApi.createAsync({
                name: form.name.trim(),
                brand: form.brand.trim() || null,
                store_name: form.storeName!,
                price_now: form.priceNow!,
                // price_was omitted on purpose — the server reads that as
                // "no markdown" rather than a discount from zero.
                size: form.size.trim(),
                size_value: size.value,
                size_unit: size.unit,
                pack_count: packCountValue() ?? null,
                is_active: true,
                is_available: true,
                image: form.image,
                merchant_stockcode: null,
                web_url: null,
            });
            $q.notify({
                type: 'positive',
                message: 'Custom product added.',
            });
            open.value = false;
            emit('created');
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not add the product.',
                caption: toastCaption(err),
            });
        } finally {
            busy.value = false;
        }
    }
</script>
