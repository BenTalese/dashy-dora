<template>
    <!-- ── Result dialog ─────────────────────────────────────────── -->
    <BaseDialog v-model="open" card-style="min-width: 420px; max-width: 720px">
            <q-card-section class="row items-center q-gutter-md">
                <q-icon
                    :name="result?.ok ? ICONS.check_circle : ICONS.error"
                    :color="result?.ok ? 'positive' : 'negative'"
                    size="32px"
                />
                <div>
                    <div class="text-h6">
                        {{ result?.headline ?? '' }}
                    </div>
                    <div v-if="result?.subline" class="text-caption dora-text-muted">
                        {{ result.subline }}
                    </div>
                </div>
            </q-card-section>
            <q-separator />
            <q-card-section v-if="result?.rows.length" class="q-pa-none">
                <!-- Rows mount a chunk at a time as the box scrolls (R-106);
                     an error row's reason makes it taller than the rest. -->
                <div ref="rowsBox" class="import-result__rows">
                    <q-item v-for="item in renderedRows" :key="item.row_number" dense>
                        <q-item-section avatar>
                            <q-chip
                                dense
                                size="sm"
                                :color="rowChipColour(item.status) ?? undefined"
                                :text-color="rowChipColour(item.status) ? 'white' : undefined"
                                :class="{ 'dora-bg-sunken dora-text-secondary': !rowChipColour(item.status) }"
                            >
                                {{ rowChipLabel(item.status) }}
                            </q-chip>
                        </q-item-section>
                        <q-item-section>
                            <q-item-label class="text-caption">
                                Row {{ item.row_number }}: {{ item.name || '(blank)' }}
                            </q-item-label>
                            <q-item-label
                                v-if="item.reason"
                                caption
                                class="text-negative"
                            >
                                {{ item.reason }}
                            </q-item-label>
                        </q-item-section>
                    </q-item>
                    <div v-if="hasMoreRows" ref="rowsSentinel" class="import-result__sentinel" />
                </div>
            </q-card-section>
            <template #actions>
                <BaseButton
                    v-if="errorRows.length"
                    variant="ghost"
                    label="Download error rows (CSV)"
                    :icon="ICONS.download"
                    @click="downloadErrorRows"
                />
                <BaseButton variant="ghost" label="Close" @click="emit('close')" />
            </template>
    </BaseDialog>
</template>

<script lang="ts" setup>
    /** The spreadsheet import's per-row report. Split out of
     *  `AdminDataImport` (FU-948 (3)). */
    import { computed, ref, watch } from 'vue';
    import { useIncrementalRender } from 'src/composables/useIncrementalRender';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import type {
        SpreadsheetImportResult,
        SpreadsheetRowReport,
    } from 'src/services/api/dataApiService';
    import { downloadCsv } from 'src/services/files/downloadHelpers';
    import { ICONS } from 'src/style/icons';

    const open = defineModel<boolean>({ required: true });
    const props = defineProps<{ result: SpreadsheetImportResult | null }>();

    const rowsBox = ref<HTMLElement | null>(null);
    const {
        visible: renderedRows,
        hasMore: hasMoreRows,
        sentinel: rowsSentinel,
        reset: resetRenderedRows,
    } = useIncrementalRender({
        items: computed(() => props.result?.rows ?? []),
        key: 'import-result-rows',
        chunk: 60,
        rootMargin: '300px 0px',
        root: rowsBox,
    });
    watch(() => props.result, resetRenderedRows);
    const emit = defineEmits<{ close: [] }>();

    const errorRows = computed(
        () => props.result?.rows.filter((r) => r.status === 'error') ?? [],
    );

    // R-002: neutral "skipped" routes through `dora-bg-sunken` /
    // `dora-text-secondary` (see template), not a `grey-N` literal.
    function rowChipColour(status: SpreadsheetRowReport['status']): string | null {
        if (status === 'created') return 'positive';
        if (status === 'skipped_duplicate') return null;
        return 'negative';
    }
    function rowChipLabel(status: SpreadsheetRowReport['status']): string {
        if (status === 'created') return 'ok';
        if (status === 'skipped_duplicate') return 'dup';
        return 'err';
    }

    // Lets the user iterate on a partially-bad spreadsheet without
    // squinting at the result dialog — they fix the highlighted rows
    // offline and re-import only those.
    function downloadErrorRows() {
        const rows = errorRows.value;
        if (!rows.length) return;
        downloadCsv(
            ['row_number', 'name', 'reason'],
            rows.map((r) => [r.row_number, r.name, r.reason ?? '']),
            'dora-import-errors.csv',
        );
    }
</script>

<style scoped>
    .import-result__rows {
        max-height: 360px;
        overflow-y: auto;
    }
    .import-result__sentinel {
        height: 1px;
    }
</style>
