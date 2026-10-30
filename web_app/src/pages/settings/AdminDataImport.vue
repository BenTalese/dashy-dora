<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Import"
            description="Bring stock items in from a spreadsheet. Upload an .xlsx or .csv, map columns to Dora's fields, preview, then commit. Errors are reported row-by-row."
            :icon="ICONS.file_upload"
        >
            <template v-if="templates.length" #actions>
                <!-- per-section CSV template. "Download a blank one" is a peer
                     choice to "upload one you already have", so it sits in the
                     page-header action slot. Single-section installs get one
                     button; the menu appears when more sections land. -->
                <BaseButton
                    v-if="templates.length === 1"
                    variant="secondary"
                    :icon="ICONS.file_download"
                    label="Download template"
                    :loading="templatesLoading"
                    @click="onDownloadTemplate(templates[0]!)"
                >
                    <BaseTooltip>{{ templates[0]!.caption }}</BaseTooltip>
                </BaseButton>
                <BaseButton
                    v-else
                    variant="secondary"
                    :icon="ICONS.file_download"
                    label="Download template"
                >
                    <q-menu auto-close>
                        <q-list dense style="min-width: 220px">
                            <q-item
                                v-for="template in templates"
                                :key="template.section"
                                clickable
                                @click="onDownloadTemplate(template)"
                            >
                                <q-item-section>
                                    <q-item-label>{{ template.label }}</q-item-label>
                                    <q-item-label caption>{{ template.caption }}</q-item-label>
                                </q-item-section>
                            </q-item>
                        </q-list>
                    </q-menu>
                </BaseButton>
            </template>
        </SettingsPageHeader>

        <!-- ── Upload ────────────────────────────────────────────────── -->
        <SettingsSection>
            <template #title>Upload a spreadsheet</template>
            <template #description>
                Required column: <strong>name</strong>. Optional: level,
                location, group, expiry, is&nbsp;essential.
            </template>

            <SettingsFileDrop
                v-model="pickedFile"
                accept=".xlsx,.csv"
                label="Choose a spreadsheet"
                hint="Drag an .xlsx or .csv here, or click to browse"
                :loading="uploading || inspecting"
                :loading-text="uploading ? 'Uploading…' : 'Reading spreadsheet…'"
                :progress="progress"
                @pick="onFilePicked"
                @clear="onClearPick"
            />
        </SettingsSection>

        <!-- ── Sheet selector (when more than one sheet) ─────────────── -->
        <template v-if="inspect && inspect.sheets.length > 1">
            <hr class="settings-divider" />
            <SettingsSection>
                <template #title>Pick a sheet</template>
                <template #description>
                    This workbook has more than one sheet. Choose which to import.
                </template>
                <q-option-group
                    v-model="selectedSheet"
                    :options="sheetOptions"
                    color="primary"
                    inline
                />
            </SettingsSection>
        </template>

        <q-banner
            v-if="inspect && inspect.warnings.length"
            class="dora-bg-warning-soft text-warning import-warnings"
            rounded
        >
            <template #avatar>
                <q-icon :name="ICONS.warning" />
            </template>
            <ul class="q-my-none q-pl-md">
                <li v-for="(w, i) in inspect.warnings" :key="i">{{ w }}</li>
            </ul>
        </q-banner>

        <!-- ── Column mapping ────────────────────────────────────────── -->
        <template v-if="inspect && selectedSheet">
            <hr class="settings-divider" />
            <SettingsSection>
                <template #title>Map columns</template>
                <template #description>
                    Pick a spreadsheet column for each Dora field. Obvious
                    matches are auto-selected from the column names.
                </template>
                <div class="mapping-grid">
                    <q-select
                        v-for="target in targetFields"
                        :key="target"
                        v-model="columnMap[target]"
                        :options="columnOptions"
                        :label="targetLabel(target)"
                        outlined
                        dense
                        clearable
                        emit-value
                        map-options
                    >
                        <template #after>
                            <q-icon
                                v-if="target === 'name' && !columnMap[target]"
                                name="warning"
                                color="negative"
                                size="20px"
                            >
                                <BaseTooltip>Required</BaseTooltip>
                            </q-icon>
                        </template>
                    </q-select>
                </div>
            </SettingsSection>

            <!-- ── Preview ───────────────────────────────────────────── -->
            <template v-if="previewRows.length">
                <hr class="settings-divider" />
                <SettingsSection>
                    <template #title>Preview</template>
                    <template #description>
                        First {{ previewRows.length }} row{{ previewRows.length === 1 ? '' : 's' }},
                        shown exactly as they'll map into Dora.
                    </template>
                    <div class="preview-scroll">
                        <q-markup-table dense flat class="preview-table">
                            <thead>
                                <tr>
                                    <th
                                        v-for="target in targetFields"
                                        :key="target"
                                        class="text-left"
                                    >
                                        {{ targetLabel(target) }}
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="(row, idx) in resolvedPreview" :key="idx">
                                    <td
                                        v-for="target in targetFields"
                                        :key="target"
                                        :class="row[target] === null ? 'dora-text-muted' : ''"
                                    >
                                        {{ row[target] ?? '–' }}
                                    </td>
                                </tr>
                            </tbody>
                        </q-markup-table>
                    </div>
                </SettingsSection>
            </template>

            <!-- ── Options ───────────────────────────────────────────── -->
            <hr class="settings-divider" />
            <SettingsSection>
                <template #title>Options</template>
                <template #description>
                    How Dora handles duplicates and missing references while importing.
                </template>
                <SettingsRow
                    label="Skip duplicates"
                    help="Rows whose name already exists locally are left alone."
                >
                    <q-toggle v-model="options.skip_duplicates" />
                </SettingsRow>
                <SettingsRow
                    label="Create missing locations"
                    help="Locations referenced by rows are created on the fly if you haven't got them yet."
                >
                    <q-toggle v-model="options.create_missing_locations" />
                </SettingsRow>
                <SettingsRow
                    label="Create missing groups"
                    help="Same, for groups. Levels are never created automatically."
                >
                    <q-toggle v-model="options.create_missing_groups" />
                </SettingsRow>
                <SettingsRow
                    label="Halt on first error"
                    help="Rolls the whole import back on any row-level failure. Off ⇒ valid rows land; errors are reported row-by-row."
                >
                    <q-toggle v-model="options.halt_on_error" />
                </SettingsRow>
                <div class="settings-actions">
                    <BaseButton variant="ghost" label="Cancel" @click="onClearPick" />
                    <BaseButton
                        variant="primary"
                        :icon="ICONS.check"
                        label="Import"
                        :loading="committing"
                        :disable="committing || !columnMap.name"
                        @click="onCommit"
                    />
                </div>
            </SettingsSection>
        </template>

        <!-- ── Result dialog ─────────────────────────────────────────── -->
        <BaseDialog v-model="resultOpen" card-style="min-width: 420px; max-width: 720px">
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
                    <q-virtual-scroll
                        :items="result.rows"
                        :virtual-scroll-item-size="38"
                        style="max-height: 360px"
                        v-slot="{ item }"
                    >
                        <q-item dense>
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
                    </q-virtual-scroll>
                </q-card-section>
                <template #actions>
                    <BaseButton
                        v-if="errorRows.length"
                        variant="ghost"
                        label="Download error rows (CSV)"
                        :icon="ICONS.download"
                        @click="downloadErrorRows"
                    />
                    <BaseButton variant="ghost" label="Close" @click="onResultClose" />
                </template>
        </BaseDialog>
    </div>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import SettingsFileDrop from 'src/components/settings/SettingsFileDrop.vue';
    import { ICONS } from 'src/style/icons';
    import { useQuasar } from 'quasar';
    import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { computed, onMounted, reactive, ref, watch } from 'vue';
    import DataApiService, { type ImportTemplate, type SpreadsheetRowReport } from 'src/services/api/dataApiService';
    import { downloadCsv, triggerSave } from 'src/services/files/downloadHelpers';
    import { useChunkedUpload } from 'src/composables/useChunkedUpload';
    import { useConfirm } from 'src/composables/useConfirm';

    const $q = useQuasar();

    const { confirm } = useConfirm();
    const { progress, upload, abort, reset: resetUpload } = useChunkedUpload();
    const dataApi = new DataApiService();

    // per-section CSV templates. Loaded once on mount; the
    // download button in the header offers a single click when there's
    // one section (today's shape) or a menu when more land later.
    const templates = ref<ImportTemplate[]>([]);
    const templatesLoading = ref(false);
    async function loadTemplates(): Promise<void> {
        try {
            templates.value = await dataApi.importTemplatesAsync();
        } catch (err) {
            // Non-fatal — the file picker still works without a template.
            // Log-only; no toast because the user didn't ask for this yet.
            console.warn('[Import templates] load failed:', err);
        }
    }
    async function onDownloadTemplate(template: ImportTemplate): Promise<void> {
        templatesLoading.value = true;
        try {
            const { blob, filename } = await dataApi.downloadImportTemplateAsync(template.section);
            triggerSave(blob, filename ?? `dora-import-${template.section}.csv`);
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: "Couldn't download the template.",
                caption: toastCaption(err),
            });
        } finally {
            templatesLoading.value = false;
        }
    }
    onMounted(() => {
        void loadTemplates();
    });

    // Target field labels — match the brief / server-side TARGET_FIELDS.
    const FIELD_LABELS: Record<string, string> = {
        name: 'Name (required)',
        level: 'Stock level',
        location: 'Location',
        group: 'Group',
        expiry: 'Expiry date',
        is_essential: 'Is essential',
    };
    function targetLabel(target: string): string {
        return FIELD_LABELS[target] ?? target;
    }

    interface InspectResponse {
        sheets: string[];
        preview_rows: Record<string, Array<Array<unknown>>>;
        detected_columns: Record<string, string[]>;
        auto_mapping: Record<string, Record<string, string | null>>;
        target_fields: string[];
        warnings: string[];
    }

    interface ImportResult {
        ok: boolean;
        headline: string;
        subline: string;
        rows: SpreadsheetRowReport[];
    }

    // ── State ────────────────────────────────────────────────────────
    const pickedFile = ref<File | null>(null);
    const uploadId = ref<string | null>(null);
    const uploading = ref(false);
    const inspecting = ref(false);
    const committing = ref(false);

    const inspect = ref<InspectResponse | null>(null);
    const selectedSheet = ref<string | null>(null);
    const columnMap = reactive<Record<string, string | null>>({
        name: null, level: null, location: null,
        group: null, expiry: null, is_essential: null,
    });
    const options = reactive({
        skip_duplicates: true,
        create_missing_locations: false,
        create_missing_groups: false,
        halt_on_error: false,
    });

    const result = ref<ImportResult | null>(null);
    const resultOpen = ref(false);

    const targetFields = computed(() => inspect.value?.target_fields ?? Object.keys(FIELD_LABELS));

    const sheetOptions = computed(() => (inspect.value?.sheets ?? []).map((name) => ({
        label: name, value: name,
    })));

    const columnOptions = computed(() => {
        if (!inspect.value || !selectedSheet.value) return [];
        const cols = inspect.value.detected_columns[selectedSheet.value] ?? [];
        return cols.filter((c) => c).map((c) => ({ label: c, value: c }));
    });

    const previewRows = computed(() => {
        if (!inspect.value || !selectedSheet.value) return [];
        return inspect.value.preview_rows[selectedSheet.value] ?? [];
    });

    // Walks the preview rows through the current column map so the user can
    // see exactly which cell maps to which target.
    const resolvedPreview = computed(() => {
        if (!inspect.value || !selectedSheet.value) return [];
        const header = inspect.value.detected_columns[selectedSheet.value] ?? [];
        return previewRows.value.map((row) => {
            const out: Record<string, unknown> = {};
            for (const target of targetFields.value) {
                const colName = columnMap[target];
                if (!colName) {
                    out[target] = null;
                    continue;
                }
                const idx = header.indexOf(colName);
                out[target] = idx >= 0 && idx < row.length ? row[idx] : null;
            }
            return out;
        });
    });

    const errorRows = computed(
        () => result.value?.rows.filter((r) => r.status === 'error') ?? [],
    );

    // When inspect lands or the user picks a different sheet, snap the
    // column map to the server's auto-pick for that sheet.
    watch(selectedSheet, (sheet) => {
        if (!inspect.value || !sheet) return;
        const auto = inspect.value.auto_mapping[sheet] ?? {};
        for (const target of targetFields.value) {
            columnMap[target] = auto[target] ?? null;
        }
    });

    // ── File pick → upload → inspect ─────────────────────────────────
    async function onFilePicked(file: File | null) {
        if (!file) return;
        inspect.value = null;
        selectedSheet.value = null;
        uploading.value = true;
        try {
            const id = await upload(file);
            uploadId.value = id;
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Upload failed.',
                caption: toastCaption(err),
            });
            await onClearPick();
            return;
        } finally {
            uploading.value = false;
        }

        inspecting.value = true;
        try {
            inspect.value = await dataApi.inspectSpreadsheetAsync<InspectResponse>({
                upload_id: uploadId.value,
                filename: file.name,
            });
            // Default to the first sheet so the mapping UI is immediately useful.
            selectedSheet.value = inspect.value?.sheets[0] ?? null;
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: "Couldn't read that spreadsheet.",
                caption: toastCaption(err),
            });
            await onClearPick();
        } finally {
            inspecting.value = false;
        }
    }

    async function onClearPick() {
        if (uploadId.value) {
            await abort(uploadId.value);
            uploadId.value = null;
        }
        resetUpload();
        pickedFile.value = null;
        inspect.value = null;
        selectedSheet.value = null;
        for (const target of Object.keys(columnMap)) {
            columnMap[target] = null;
        }
    }

    // ── Commit ───────────────────────────────────────────────────────
    async function onCommit() {
        if (!selectedSheet.value || !pickedFile.value) return;
        // A completed (non-halted) commit consumes the staged file server-side,
        // so a retry after "errors: N" has nothing left to import — say so
        // rather than no-op'ing silently.
        if (!uploadId.value) {
            $q.notify({
                type: 'warning',
                message: 'Pick the file again to import it.',
            });
            return;
        }
        if (!columnMap.name) {
            $q.notify({
                type: 'warning',
                message: 'Map a column to "Name" before importing.',
            });
            return;
        }

        const confirmed = await confirm({
            title: 'Confirm import',
            message: `Import rows from "${selectedSheet.value}"? This can't be undone.`,
            okLabel: 'Import',
        });
        if (!confirmed) return;

        committing.value = true;
        try {
            const body = await dataApi.commitSpreadsheetAsync({
                upload_id: uploadId.value,
                filename: pickedFile.value.name,
                sheet: selectedSheet.value,
                column_map: { ...columnMap },
                options: { ...options },
            });
            const headline =
                body.summary.halted
                    ? 'Import halted'
                    : `Imported ${body.summary.created} row(s)`;
            const subline =
                `${body.summary.skipped} skipped · ${body.summary.errors} error(s)` +
                (body.summary.halted ? ' (rolled back)' : '');
            result.value = {
                ok: !body.summary.halted && body.summary.errors === 0,
                headline,
                subline,
                rows: body.rows,
            };
            resultOpen.value = true;
            // A non-halted commit consumes the staged file server-side; forget
            // the id so a later abort doesn't 404 chasing a phantom upload. A
            // halted import rolls back and KEEPS the file, so the id stays and
            // the user can fix the mapping and retry.
            if (!body.summary.halted) uploadId.value = null;
        } catch (err) {
            result.value = {
                ok: false,
                headline: 'Import failed',
                subline: toastCaption(err),
                rows: [],
            };
            resultOpen.value = true;
        } finally {
            committing.value = false;
        }
    }

    function onResultClose() {
        resultOpen.value = false;
        // After a successful import we want a clean slate; after a failure
        // the user might want to tweak the mapping and retry, so leave
        // state in place.
        if (result.value?.ok) {
            void onClearPick();
        }
    }

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

<style scoped lang="scss">
    .import-warnings {
        margin-bottom: var(--space-4);
    }
    // Responsive field grid for the column mapping — auto-fills as many
    // columns as fit at a comfortable min width, so it reflows cleanly
    // instead of the old fixed 3-up q-col-gutter layout.
    .mapping-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
        gap: var(--space-3);
    }
    .preview-scroll {
        overflow-x: auto;
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
    }
    .preview-table {
        background: var(--surface-component);
        :deep(thead th) {
            font-weight: 700;
            color: var(--text-secondary);
            background: var(--surface-sunken);
        }
    }
</style>
