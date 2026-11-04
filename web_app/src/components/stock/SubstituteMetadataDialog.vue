<template>
    <BaseDialog
        v-model="open"
        :title="title"
        closable
        card-style="min-width: 360px; max-width: 520px"
    >
        <q-card-section>
            <!-- Feedback 2026-08-24: the paragraph explaining where notes and
                 ratios surface moved to Help → Guides ("Substitutes"), reachable
                 from the (?) beside the Substitutes heading. It was permanent
                 chrome on a dialog you open to type one line. -->
            <q-input
                v-model="notesDraft"
                type="textarea"
                outlined
                dense
                autogrow
                maxlength="255"
                placeholder="e.g. 1:1 in soups, but don't use in baking"
                label="Note"
                :error="!!notesError"
                :error-message="notesError ?? undefined"
            />

            <div class="row items-center q-mt-md q-mb-xs">
                <q-toggle
                    v-model="ratioEnabled"
                    :label="ratioEnabled ? 'Ratio set' : 'Add a ratio'"
                />
            </div>
            <div v-if="ratioEnabled" class="sub-ratio-row column q-gutter-sm">
                <div class="row items-center q-gutter-sm wrap">
                    <q-input
                        v-model.number="qtyInDraft"
                        type="number"
                        step="any"
                        min="0"
                        outlined
                        dense
                        style="max-width: 110px"
                        label="Qty"
                        hide-bottom-space
                    />
                    <BaseSelect
                        v-model="unitInDraft"
                        :options="unitOptions"
                        emit-value
                        map-options
                        use-input
                        input-debounce="0"
                        @filter="onUnitFilter"
                        style="min-width: 130px"
                        label="Unit"
                        hide-bottom-space
                    />
                    <span class="dora-text-muted">of {{ fromName }}</span>
                </div>
                <div class="row items-center q-gutter-sm wrap">
                    <q-icon :name="ICONS.arrow_forward" class="dora-text-muted" />
                    <q-input
                        v-model.number="qtyOutDraft"
                        type="number"
                        step="any"
                        min="0"
                        outlined
                        dense
                        style="max-width: 110px"
                        label="Qty"
                        hide-bottom-space
                    />
                    <BaseSelect
                        v-model="unitOutDraft"
                        :options="unitOptions"
                        emit-value
                        map-options
                        use-input
                        input-debounce="0"
                        @filter="onUnitFilter"
                        style="min-width: 130px"
                        label="Unit"
                        hide-bottom-space
                    />
                    <span class="dora-text-muted">of {{ toName }}</span>
                </div>
                <div v-if="ratioError" class="text-negative text-caption">
                    {{ ratioError }}
                </div>
            </div>
        </q-card-section>

        <template #actions>
            <BaseButton variant="ghost" label="Cancel" v-close-popup />
            <BaseButton
                variant="primary"
                label="Save"
                :loading="saving"
                :disable="!canSave"
                @click="onSave"
            />
        </template>
    </BaseDialog>
</template>

<script setup lang="ts">
    /**
     * FU-034 — edit dialog for a substitute pair's metadata (free-text
     * note + optional structured ratio). Direction is presented from the
     * viewing stock item's perspective: "qty + unit of {fromName}" →
     * "qty + unit of {toName}". The server flips into canonical storage.
     *
     * Used from `StockItemDetailPage.vue`'s substitutes tab. Emits `save`
     * with the metadata bundle when the user confirms.
     */
    import { computed, ref, watch } from 'vue';
    import { useUnitOptions } from 'src/composables/useUnitOptions';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseSelect from 'src/components/BaseSelect.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import { ICONS } from 'src/style/icons';

    interface Props {
        modelValue: boolean;
        fromName: string;
        toName: string;
        initialNotes: string | null;
        initialRatioQuantityIn: number | null;
        initialRatioUnitIn: string | null;
        initialRatioQuantityOut: number | null;
        initialRatioUnitOut: string | null;
        saving?: boolean;
    }
    const props = withDefaults(defineProps<Props>(), { saving: false });
    const emit = defineEmits<{
        (e: 'update:modelValue', value: boolean): void;
        (e: 'save', payload: {
            notes: string | null;
            ratio_quantity_in: number | null;
            ratio_unit_in: string | null;
            ratio_quantity_out: number | null;
            ratio_unit_out: string | null;
        }): void;
    }>();

    const open = computed({
        get: () => props.modelValue,
        set: (value) => emit('update:modelValue', value),
    });

    const title = computed(
        () => `Substitute: ${props.fromName} ↔ ${props.toName}`,
    );

    // ── Draft state ────────────────────────────────────────────────────
    const notesDraft = ref('');
    const ratioEnabled = ref(false);
    const qtyInDraft = ref<number | null>(null);
    const unitInDraft = ref<string | null>(null);
    const qtyOutDraft = ref<number | null>(null);
    const unitOutDraft = ref<string | null>(null);

    // Hydrate drafts from props every time the dialog re-opens so a
    // cancelled edit doesn't leak into the next session.
    watch(
        () => props.modelValue,
        (isOpen) => {
            if (!isOpen) return;
            notesDraft.value = props.initialNotes ?? '';
            const hasRatio
                = props.initialRatioQuantityIn !== null
                && props.initialRatioUnitIn !== null
                && props.initialRatioQuantityOut !== null
                && props.initialRatioUnitOut !== null;
            ratioEnabled.value = hasRatio;
            qtyInDraft.value = props.initialRatioQuantityIn ?? null;
            unitInDraft.value = props.initialRatioUnitIn ?? null;
            qtyOutDraft.value = props.initialRatioQuantityOut ?? null;
            unitOutDraft.value = props.initialRatioUnitOut ?? null;
        },
        { immediate: true },
    );

    // ── Unit picker ────────────────────────────────────────────────────
    // UNIT_TABLE keys include every alias ("ml", "millilitre", "millilitres").
    // De-duplicated by canonical form, searchable by alias — shared with the
    // recipe ingredient editor (R-001).
    // Narrowed to the install's measurement system, with the currently-saved
    // unit-in kept offered so an existing substitute row survives a system
    // change. (unit-out shares the same list; the pair is nearly always in
    // one system, and keeping both exceptions would mean two lists.)
    const { unitOptions, onUnitFilter } = useUnitOptions(
        undefined,
        () => unitInDraft.value,
    );

    // ── Validation ─────────────────────────────────────────────────────
    const notesError = computed<string | null>(() =>
        notesDraft.value.length > 255
            ? 'Keep it to 255 characters.'
            : null,
    );
    const ratioError = computed<string | null>(() => {
        if (!ratioEnabled.value) return null;
        if (qtyInDraft.value == null || qtyOutDraft.value == null
            || !unitInDraft.value || !unitOutDraft.value) {
            return 'Fill in both quantity + unit on each side.';
        }
        if (qtyInDraft.value <= 0 || qtyOutDraft.value <= 0) {
            return 'Quantities must be greater than zero.';
        }
        return null;
    });
    const canSave = computed(
        () => !notesError.value && !ratioError.value && !props.saving,
    );

    function onSave(): void {
        if (!canSave.value) return;
        const trimmedNote = notesDraft.value.trim();
        emit('save', {
            notes: trimmedNote.length === 0 ? null : trimmedNote,
            ratio_quantity_in: ratioEnabled.value ? qtyInDraft.value : null,
            ratio_unit_in: ratioEnabled.value ? unitInDraft.value : null,
            ratio_quantity_out: ratioEnabled.value ? qtyOutDraft.value : null,
            ratio_unit_out: ratioEnabled.value ? unitOutDraft.value : null,
        });
    }
</script>

<style scoped>
    .sub-ratio-row {
        padding: 8px 12px;
        background: var(--surface-sunken);
        border-radius: 6px;
    }
</style>
