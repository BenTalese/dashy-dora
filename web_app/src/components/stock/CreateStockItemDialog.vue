<template>
    <BaseDialog
        :model-value="modelValue"
        :title="dialogTitle"
        closable
        card-style="width: 600px; max-width: 95vw"
        @update:model-value="onDialogUpdate"
        @cancel="resetForm"
    >
            <q-card-section>
                <!-- 2026-08-21 feedback: "location input is too wide on the
                     right (possibly same issue we faced on the stock item
                     details page?)". Same issue, same cause. This was
                     `q-gutter-md`, which spaces children by putting a -16px
                     margin on the container and +16px on each child — so the
                     container's content box is 16px WIDER than the card. Every
                     child that sizes to content is fine with that; the location
                     picker is the one that doesn't, because a `use-input`
                     QSelect carries `width: 100%` (see the `.q-select--with-input`
                     rule in app.scss), and 100% of the over-wide container
                     overhangs the card by exactly one gutter on the right.
                     A flex column with `gap` spaces the same way without
                     negative margins, so 100% means 100% of the card. -->
                <q-form @submit.prevent="onSubmit" class="create-stock-item__fields">
                    <FormErrorSummary :message="generalError" />

                    <!-- barcode-to-add suggestion banner. Shown when
                         the dialog opens from a scan flow with either an OFF
                         suggestion (source='off') or an EAN-only prefill
                         (unknown barcode, OFF miss or product_no_link). Uses
                         --surface-sunken for consistency with the FU-012
                         sub-bar treatment. -->
                    <div v-if="prefill?.barcode" class="dora-suggestion-banner">
                        <img
                            v-if="prefill.imageUrl"
                            :src="prefill.imageUrl"
                            alt=""
                            class="dora-suggestion-image"
                        />
                        <div class="col">
                            <div class="text-caption dora-text-muted">
                                <template v-if="prefill.source === 'off'">
                                    Suggested from <strong>Open Food Facts</strong>. Check it before saving.
                                </template>
                                <template v-else-if="prefill.source === 'product_no_link'">
                                    This barcode matches a known product. Add a stock item to link it.
                                </template>
                                <template v-else>
                                    Adding a stock item for a scanned barcode.
                                </template>
                            </div>
                            <div class="text-caption q-mt-xs">
                                Barcode <code>{{ prefill.barcode }}</code>
                                <span v-if="prefill.brand"> · {{ prefill.brand }}</span>
                                <span v-if="prefill.quantity"> · {{ prefill.quantity }}</span>
                            </div>
                            <div v-if="prefill.categories" class="text-caption dora-text-muted q-mt-xs">
                                {{ prefill.categories }}
                            </div>
                        </div>
                    </div>

                    <q-input
                        v-model="form.name"
                        outlined
                        autofocus
                        label="Name"
                        :error="!!fieldErrors.name"
                        :error-message="fieldErrors.name"
                        @update:model-value="clearField('name')"
                        :rules="[(v: string) => (!!v && v.trim().length > 0) || 'Name is required']"
                    />
                    <q-select
                        v-model="form.stock_level_id"
                        :options="stockLevels"
                        :option-label="(o: StockLevel) => o.name"
                        :option-value="(o: StockLevel) => o.stock_level_id"
                        emit-value
                        map-options
                        outlined
                        label="Stock level"
                        :error="!!fieldErrors.stock_level_id"
                        :error-message="fieldErrors.stock_level_id"
                        @update:model-value="clearField('stock_level_id')"
                        :rules="[(v: string) => !!v || 'Pick a stock level']"
                    >
                        <!-- Feedback (stock overview): show the level
                             colour-dot on the *trigger* too, not just in
                             the dropdown list — keeps this picker
                             consistent with the detail-page picker. -->
                        <template #selected-item="scope">
                            <span class="row items-center no-wrap">
                                <StockLevelDot
                                    :sequence="selectedLevelSequence"
                                    dot-class="q-mr-sm"
                                />
                                {{ scope.opt.name }}
                            </span>
                        </template>
                        <template #option="scope">
                            <q-item v-bind="scope.itemProps">
                                <q-item-section avatar>
                                    <StockLevelDot :sequence="scope.opt.sequence" />
                                </q-item-section>
                                <q-item-section>{{ scope.opt.name }}</q-item-section>
                            </q-item>
                        </template>
                    </q-select>
                    <!-- Round-10: location picker mirrors the filter +
                         detail-page picker — path-labelled options walked
                         from the location tree, searchable on type,
                         clearable. The dialog hydrates the tree on open
                         so the picker is populated even if the parent
                         page hasn't loaded it yet. -->
                    <q-select
                        v-model="form.stock_location_id"
                        :options="locationOptions"
                        emit-value
                        map-options
                        use-input
                        fill-input
                        hide-selected
                        input-debounce="200"
                        clearable
                        outlined
                        label="Location (optional)"
                        :error="!!fieldErrors.stock_location_id"
                        :error-message="fieldErrors.stock_location_id"
                        @filter="filterLocations"
                        @update:model-value="clearField('stock_location_id')"
                    />

                    <!-- The create dialog only carries fields that are
                         permanent properties of the item. Expiry is a
                         per-batch fact that changes over the item's life,
                         so it lives on the detail page / stocktake, not
                         here. Stock group takes its place. -->
                    <q-select
                        v-model="form.stock_group_id"
                        :options="groupOptions"
                        emit-value
                        map-options
                        clearable
                        outlined
                        label="Stock group (optional)"
                        :error="!!fieldErrors.stock_group_id"
                        :error-message="fieldErrors.stock_group_id"
                        @update:model-value="clearField('stock_group_id')"
                    />

                    <!-- 2026-08-28 feedback: usual store is a permanent
                         property of the item (same class as group/location),
                         so it belongs on the create form rather than only on
                         the detail page. Option list mirrors the detail
                         page's picker, logo and all, so the two surfaces
                         read the same. Plain q-select, matching its siblings
                         here — this dialog is still on the pre-BaseSelect
                         shape (FU-675); migrate the whole form at once, not
                         one field into a different scale. -->
                    <q-select
                        v-model="form.usual_store_id"
                        :options="storeOptions"
                        emit-value
                        map-options
                        clearable
                        outlined
                        label="Usual store (optional)"
                        :error="!!fieldErrors.usual_store_id"
                        :error-message="fieldErrors.usual_store_id"
                        @update:model-value="clearField('usual_store_id')"
                    >
                        <template #option="{ opt, itemProps }">
                            <q-item v-bind="itemProps">
                                <q-item-section
                                    avatar
                                    style="min-width: 0; padding-right: 8px"
                                >
                                    <StoreLogo
                                        :name="opt.label"
                                        :store-id="opt.value"
                                        :has-image="opt.has_image"
                                        :height="20"
                                        :width="34"
                                    />
                                </q-item-section>
                                <q-item-section>
                                    <q-item-label>{{ opt.label }}</q-item-label>
                                </q-item-section>
                            </q-item>
                        </template>
                    </q-select>

                    <div class="row items-center q-gutter-sm">
                        <q-toggle v-model="form.is_essential" label="Essential" />
                        <q-icon :name="ICONS.info_outline" size="16px" class="dora-text-secondary">
                            <!-- 2026-08-21, owner-approved copy. The old text
                                 ("shows up in 'essentials' auto-generate
                                 sources… different from auto-add…") explained
                                 the flag by naming two internal mechanisms and
                                 never mentioned the thing the user actually
                                 sees: an essential is what makes a row raise
                                 attention when it runs low (`stock_attention.py`,
                                 kind `essential_low`). D-014 — say what it does
                                 for you, not what it does in the code. Kept
                                 word-identical to the detail page's copy. -->
                            <BaseTooltip max-width="320px">
                                Something you always want in the house. Dora
                                chases it up as soon as it runs low, instead of
                                waiting until it's gone.
                            </BaseTooltip>
                        </q-icon>
                    </div>

                    <!-- 2026-08-28 feedback. Gated on the install-wide
                         stocktake switch for the same reason the detail
                         page's row is: a per-item opt-in to a feature the
                         install has turned off is just a confusing switch.
                         Starts at the install's new-item default
                         (`stocktake_policy.new_items_opt_in`) so the toggle
                         shows the position the item is really created in —
                         the server applies that same default when the field
                         is omitted. Copy kept word-identical to the detail
                         page's tooltip. -->
                    <div v-if="stocktakeEnabled" class="row items-center q-gutter-sm">
                        <q-toggle v-model="form.stocktake_alerts_are_enabled" label="Stocktake" />
                        <q-icon :name="ICONS.info_outline" size="16px" class="dora-text-secondary">
                            <BaseTooltip max-width="320px">
                                Controls whether this item ever joins the
                                stocktake queue.
                            </BaseTooltip>
                        </q-icon>
                    </div>

                </q-form>
            </q-card-section>
            <template #actions>
                <BaseButton variant="ghost" label="Cancel" v-close-popup />
                <BaseButton variant="primary" label="Add" :loading="saving" @click="onSubmit" />
            </template>
    </BaseDialog>
</template>

<script setup lang="ts">
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { storeToRefs } from 'pinia';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import FormErrorSummary from 'src/components/FormErrorSummary.vue';
    import StockLevelDot from 'src/components/stock/StockLevelDot.vue';
    import StoreLogo from 'src/components/StoreLogo.vue';
    import type { StockLevel } from 'src/models/stockLevel';
    import type { CreateStockItemPrefill } from 'src/components/stock/createStockItemPrefill';
    import BarcodeApiService from 'src/services/api/barcodeApiService';
    import { useStockGroupStore } from 'src/stores/stockGroupStore';
    import type { CreateStockItemCommand } from 'src/services/api/stockItemApiService';
    import { useFormErrors } from 'src/composables/useFormErrors';
    import { useLocationStore } from 'src/stores/locationStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import { useLocationOptions } from 'src/composables/useLocationOptions';
    import { useStoresStore } from 'src/stores/storesStore';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import { useStocktakePolicy } from 'src/composables/useStocktakePolicy';
    import { useQuasar } from 'quasar';
    import { ICONS } from 'src/style/icons';
    import { computed, reactive, ref, watch } from 'vue';

    // Prefill type lives in a sibling `.ts` file so page callers
    // resolve it under ESLint's TS parser (which doesn't always trace
    // named exports across `.vue` boundaries).
    const props = defineProps<{
        modelValue: boolean;
        prefill?: CreateStockItemPrefill | null;
    }>();
    const emit = defineEmits<{
        (e: 'update:modelValue', value: boolean): void;
        /** `stockItemId` lets a caller act on the new item — the unlinked-
         *  ingredients linker links it to the group it was created from. */
        (e: 'created', stockItemId: string): void;
    }>();

    const $q = useQuasar();
    const barcodeApi = new BarcodeApiService();
    const stockGroupStore = useStockGroupStore();

    const dialogTitle = computed(() =>
        props.prefill?.barcode ? 'Add a stock item from scan' : 'Add a stock item',
    );

    const stockItemStore = useStockItemStore();
    const stockLevelStore = useStockLevelStore();
    const locationStore = useLocationStore();
    const storesStore = useStoresStore();
    const { stockLevels } = storeToRefs(stockLevelStore);
    const { stocktake: stocktakeEnabled } = useFeatureFlags();
    const { newItemsOptIn } = useStocktakePolicy();

    // Walk the location tree into path-labelled options — same shape as
    // the Stock Overview filter and the detail-page picker so the user
    // gets a single, consistent location-pick experience.
    const { locationOptions, filterLocations } = useLocationOptions(() => locationStore.tree);

    // Stock groups — fetched straight from the API like the detail-page
    // picker does; there's no store for them and this dialog is the only
    // other consumer.
    const groupOptions = computed(() =>
        stockGroupStore.stockGroups.map((g) => ({ label: g.name, value: g.stock_group_id })),
    );

    // Same option shape as the detail-page picker (label/value plus the flag
    // StoreLogo needs to choose an uploaded image over its swatch fallback).
    const storeOptions = computed(() =>
        storesStore.stores.map((s) => ({
            label: s.name,
            value: s.store_id,
            has_image: s.has_image,
        })),
    );

    const defaultForm = (): CreateStockItemCommand => ({
        name: props.prefill?.name?.trim() || '',
        stock_level_id: stockLevels.value[0]?.stock_level_id ?? '',
        stock_location_id: null,
        stock_group_id: null,
        is_essential: false,
        usual_store_id: null,
        stocktake_alerts_are_enabled: newItemsOptIn.value,
    });

    const form: CreateStockItemCommand = reactive(defaultForm());
    const saving = ref(false);
    // Sequence of the currently-picked level — drives the trigger dot.
    // q-select with `emit-value` only hands `#selected-item` the resolved
    // option object, but we still need to derive sequence here because
    // the form holds the id. Recomputed reactively so the dot updates
    // the instant the user picks a new level.
    const selectedLevelSequence = computed<number | null>(() => {
        const id = form.stock_level_id;
        if (!id) return null;
        const seq = stockLevelStore.levelById.get(id ?? '')?.sequence;
        return typeof seq === 'number' ? seq : null;
    });
    // R-001 form-error plumbing.
    const { fieldErrors, generalError, handleSaveError, reset: resetFormErrors } = useFormErrors();

    function resetForm() {
        Object.assign(form, defaultForm());
        resetFormErrors();
    }

    function clearField(field: string) {
        if (fieldErrors.value[field]) {
            const next = { ...fieldErrors.value };
            delete next[field];
            fieldErrors.value = next;
        }
    }

    // Seed the form whenever the dialog opens — picks up newly-added stock
    // levels since last close. Also ensure the location tree is loaded so
    // the picker is populated even if the parent page hasn't hydrated it
    // yet (round-10 fix: the dialog used to read from `stockLocations`
    // which a parent might never have loaded).
    watch(
        () => props.modelValue,
        (open) => {
            if (open) {
                resetForm();
                void locationStore.ensureLoadedAsync();
                void storesStore.ensureLoadedAsync();
                void stockGroupStore.ensureLoadedAsync();
            }
        },
    );

    function onDialogUpdate(value: boolean) {
        emit('update:modelValue', value);
    }

    async function onSubmit() {
        saving.value = true;
        resetFormErrors();
        try {
            const created = await stockItemStore.createStockItemAsync({
                name: form.name.trim(),
                stock_level_id: form.stock_level_id,
                stock_location_id: form.stock_location_id,
                stock_group_id: form.stock_group_id || null,
                is_essential: form.is_essential ?? false,
                usual_store_id: form.usual_store_id || null,
                // Send only when the toggle is actually on screen — with
                // stocktake switched off install-wide there is no toggle, so
                // let the server apply its own default rather than posting a
                // value the user never saw.
                ...(stocktakeEnabled.value
                    ? { stocktake_alerts_are_enabled: form.stocktake_alerts_are_enabled ?? true }
                    : {}),
            });
            // if the dialog was opened from a scan flow with a
            // barcode prefill, register the EAN against the new stock
            // item so the next scan of the same code lands on this item
            // instead of re-triggering the add-flow. A conflict here (rare
            // race — another registration happened between lookup and
            // submit) is surfaced as a warning but doesn't undo the
            // create; the item exists, the user can add the barcode
            // manually if the race really matters.
            if (props.prefill?.barcode) {
                try {
                    await barcodeApi.registerAsync({
                        barcode: props.prefill.barcode,
                        stock_item_id: created.stock_item_id,
                    });
                } catch (regErr) {
                    $q.notify({
                        type: 'warning',
                        message: 'Item added, but the barcode was already registered elsewhere.',
                        caption: regErr instanceof Error ? regErr.message : String(regErr),
                    });
                }
            }
            emit('created', created.stock_item_id);
            emit('update:modelValue', false);
        } catch (err) {
            handleSaveError(err, 'Could not add the item. Please review the form.');
        } finally {
            saving.value = false;
        }
    }
</script>

<style scoped>
    /* Replaces `q-gutter-md` on the form — same 16px rhythm, but with `gap`
       instead of the gutter's negative container margin, which made the form
       16px wider than its card and pushed any `width: 100%` child (the
       location picker) off the right edge. */
    .create-stock-item__fields {
        display: flex;
        flex-direction: column;
        gap: var(--space-4, 16px);
    }

    /* P8-02 — scan-driven prefill banner. Uses the same sunken-well
       treatment as FU-012 filter sub-bars so the "this data came from
       elsewhere" affordance reads consistently across surfaces. */
    .dora-suggestion-banner {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 10px 12px;
        background: var(--surface-sunken);
        border-radius: 6px;
    }
    .dora-suggestion-image {
        width: 56px;
        height: 56px;
        object-fit: cover;
        border-radius: 4px;
        flex-shrink: 0;
        background: var(--surface-default);
    }
</style>
