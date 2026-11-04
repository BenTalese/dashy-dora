<template>
    <!-- The stock-item page's Substitutes tab (FU-934 split): the list, the
         note / ratio editor and the add-substitute picker. A row click is
         emitted up: the page knows whether it's the overview's peek (swap the
         peek's id) or the routed page (navigate). Multi-root on purpose: the
         panel's DOM is exactly what it was before the split. -->
    <template v-if="detail">
        <div class="row items-center q-mb-sm">
            <div class="text-subtitle1">Substitutes</div>
            <HelpHint topic="Substitutes" />
            <q-space />
            <BaseButton variant="primary" dense :icon="ICONS.add" label="Add substitute" @click="openSubstitutePicker" />
        </div>

        <div v-if="detail.substitutes.length === 0" class="dora-text-muted text-caption q-pa-md">
            No substitutes yet. Add items that can stand in for this one.
        </div>

        <q-list v-else separator>
            <q-item
                v-for="sub in detail.substitutes"
                :key="sub.stock_item_id"
                clickable
                @click="onOpenSubstitute(sub.stock_item_id)"
            >
                <q-item-section avatar class="stock-detail__sub-dot">
                    <StockLevelDot :sequence="sub.stock_level_sequence" size="12px">
                        <BaseTooltip>{{ sub.stock_level_name ?? 'No level set' }}</BaseTooltip>
                    </StockLevelDot>
                </q-item-section>
                <q-item-section>
                    <q-item-label>{{ sub.name }}</q-item-label>
                    <!-- optional ratio shown above
                         notes; cook-mode picker mirrors this
                         same layout so the user reads the
                         swap the same way in both places. -->
                    <q-item-label v-if="formatSubstituteRatio(sub)" caption class="dora-text-secondary">
                        {{ formatSubstituteRatio(sub) }}
                    </q-item-label>
                    <q-item-label v-if="sub.notes" caption class="dora-text-muted">
                        {{ sub.notes }}
                    </q-item-label>
                </q-item-section>
                <q-item-section side>
                    <!-- pencil icon opens the metadata
                         edit dialog (notes + ratio). Sits next
                         to the unlink action so the substitute
                         row carries both lifecycle controls
                         without the row getting cluttered. -->
                    <div class="row no-wrap items-center">
                        <BaseButton
                            :aria-label="`Edit note or ratio for ${sub.name}`"
                            variant="icon"
                            :icon="ICONS.edit"
                            @click.stop="onEditSubstituteMetadata(sub)"
                        >
                            <BaseTooltip>Edit note / ratio</BaseTooltip>
                        </BaseButton>
                        <BaseButton
                            :aria-label="`Remove substitute ${sub.name}`"
                            variant="icon"
                            :icon="ICONS.link_off"
                            class="text-negative"
                            @click.stop="onRemoveSubstitute(sub.stock_item_id)"
                        >
                            <BaseTooltip>Remove substitute</BaseTooltip>
                        </BaseButton>
                    </div>
                </q-item-section>
            </q-item>
        </q-list>

        <!-- metadata edit dialog. v-model-controlled
             open state + a snapshot of the substitute being
             edited (driven by `onEditSubstituteMetadata`). -->
        <SubstituteMetadataDialog
            v-if="editingSubstitute"
            v-model="substituteMetadataOpen"
            :from-name="detail.name"
            :to-name="editingSubstitute.name"
            :initial-notes="editingSubstitute.notes"
            :initial-ratio-quantity-in="editingSubstitute.ratio_quantity_in"
            :initial-ratio-unit-in="editingSubstitute.ratio_unit_in"
            :initial-ratio-quantity-out="editingSubstitute.ratio_quantity_out"
            :initial-ratio-unit-out="editingSubstitute.ratio_unit_out"
            :saving="substituteMetadataSaving"
            @save="onSaveSubstituteMetadata"
        />
    </template>

    <!-- ── Add-substitute picker dialog ───────────────────────────── -->
    <BaseDialog v-model="subPickerOpen" title="Add a substitute" closable card-style="width: 560px; max-width: 95vw">
        <q-card-section>
            <SearchInput v-model="subSearch" autofocus :debounce="150" placeholder="Search stock items" />
        </q-card-section>
        <q-card-section class="q-pt-none stock-detail__picker-list">
            <q-list separator>
                <!-- Feedback 2026-08-21: no leading box glyph — every row
                     in a stock-item picker is a stock item, so the icon
                     said nothing and just indented the names. The action
                     is a link, not an addition: the green chain reads as
                     "tie this to that". -->
                <q-item v-for="si in substituteCandidates" :key="si.stock_item_id" clickable @click="onAddSubstitute(si.stock_item_id)">
                    <q-item-section>{{ si.name }}</q-item-section>
                    <q-item-section side>
                        <BaseButton
                            variant="icon"
                            :icon="ICONS.add_link"
                            color="positive"
                            :aria-label="`Link ${si.name} as a substitute`"
                        >
                            <BaseTooltip>Link as a substitute</BaseTooltip>
                        </BaseButton>
                    </q-item-section>
                </q-item>
                <q-item v-if="substituteCandidates.length === 0">
                    <q-item-section class="dora-text-muted">No matching items.</q-item-section>
                </q-item>
            </q-list>
        </q-card-section>
    </BaseDialog>
</template>

<script lang="ts" setup>
    import { computed, ref } from 'vue';
    import { storeToRefs } from 'pinia';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import SearchInput from 'src/components/SearchInput.vue';
    import HelpHint from 'src/components/help/HelpHint.vue';
    import StockLevelDot from 'src/components/stock/StockLevelDot.vue';
    import SubstituteMetadataDialog from 'src/components/stock/SubstituteMetadataDialog.vue';
    import { useStockItemDetail } from 'src/composables/useStockItemDetail';
    import { formatSubstituteRatio } from 'src/helpers/substituteRatio';
    import type { Substitute } from 'src/models/stockItemDetail';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { ICONS } from 'src/style/icons';

    const emit = defineEmits<{
        /** A substitute row was clicked. The page decides where it opens:
         *  in the peek (embedded) or full-page (routed). */
        (e: 'open-substitute', stockItemId: string): void;
    }>();

    const { stockItemApi, stockItemId, detail, withBusyReload } = useStockItemDetail();
    const { stockItems } = storeToRefs(useStockItemStore());

    // ── Add-substitute picker ────────────────────────────────────────────
    const subPickerOpen = ref(false);
    const subSearch = ref('');
    const substituteCandidates = computed(() => {
        const existing = new Set((detail.value?.substitutes ?? []).map((s) => s.stock_item_id));
        const q = subSearch.value.trim().toLowerCase();
        return stockItems.value
            .filter(
                (si) =>
                    si.stock_item_id !== stockItemId.value &&
                    !existing.has(si.stock_item_id) &&
                    (!q || si.name.toLowerCase().includes(q)),
            )
            .slice(0, 30);
    });
    function openSubstitutePicker() {
        subSearch.value = '';
        subPickerOpen.value = true;
    }
    async function onAddSubstitute(substituteId: string) {
        subPickerOpen.value = false;
        await withBusyReload(() => stockItemApi.addSubstituteAsync(stockItemId.value, substituteId));
    }
    async function onRemoveSubstitute(substituteId: string) {
        await withBusyReload(() => stockItemApi.removeSubstituteAsync(stockItemId.value, substituteId));
    }
    function onOpenSubstitute(substituteId: string) {
        emit('open-substitute', substituteId);
    }

    // ── FU-034: substitute metadata edit dialog ─────────────────────────
    const substituteMetadataOpen = ref(false);
    const substituteMetadataSaving = ref(false);
    const editingSubstitute = ref<Substitute | null>(null);

    function onEditSubstituteMetadata(sub: Substitute) {
        editingSubstitute.value = sub;
        substituteMetadataOpen.value = true;
    }
    async function onSaveSubstituteMetadata(payload: {
        notes: string | null;
        ratio_quantity_in: number | null;
        ratio_unit_in: string | null;
        ratio_quantity_out: number | null;
        ratio_unit_out: string | null;
    }) {
        const sub = editingSubstitute.value;
        if (!sub) return;
        substituteMetadataSaving.value = true;
        try {
            await withBusyReload(() =>
                stockItemApi.updateSubstituteAsync(
                    stockItemId.value,
                    sub.stock_item_id,
                    payload,
                ),
            );
            substituteMetadataOpen.value = false;
            editingSubstitute.value = null;
        } finally {
            substituteMetadataSaving.value = false;
        }
    }
</script>

<style scoped>
    .stock-detail__sub-dot {
        min-width: 28px;
    }
    .stock-detail__picker-list {
        max-height: 60vh;
        overflow: auto;
    }
</style>
