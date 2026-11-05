<template>
    <!-- ── Restore from a file ───────────────────────────────────── -->
    <SettingsSection>
        <template #title>Restore from a file</template>
        <template #description>
            Import an external backup. Inspect it first, then choose
            exactly what to bring in.
        </template>

        <SettingsFileDrop
            v-model="pickedFile"
            accept=".json,application/json"
            label="Choose a backup file"
            hint="Drag a .json backup here, or click to browse"
            :loading="inspecting"
            loading-text="Inspecting backup…"
            :progress="uploadProgressValue"
            @pick="onFilePicked"
            @clear="onClearPick"
        />

        <!-- Preview panel (shows once /inspect returns) -->
        <div v-if="preview" class="restore-preview">
            <div class="restore-preview__header">
                <div>
                    <div class="restore-preview__title">Backup preview</div>
                    <div class="restore-preview__sub">
                        Exported {{ formatBackupTimestamp(preview.exported_at, 'an unknown time') }} by
                        <strong>{{ preview.exported_by }}</strong>
                    </div>
                </div>
                <div class="restore-preview__count">
                    <strong>{{ selectedCount }}</strong> of <strong>{{ selectableTotal }}</strong> selected
                    <span v-if="duplicateCount">
                        · <strong>{{ duplicateCount }}</strong> duplicate{{ duplicateCount === 1 ? '' : 's' }} skipped
                    </span>
                </div>
            </div>

            <div class="restore-preview__toolbar">
                <BaseButton variant="ghost" class="text-primary" label="Select all" @click="onSelectAll" />
                <BaseButton variant="ghost" label="Clear selection" @click="onClearSelection" />
            </div>

            <q-tree
                :nodes="treeNodes"
                node-key="key"
                tick-strategy="leaf"
                v-model:ticked="tickedKeys"
                v-model:expanded="expandedKeys"
                :no-nodes-label="'Empty backup.'"
            >
                <template #default-header="prop">
                    <div class="row items-center full-width">
                        <div class="col">
                            <span>{{ prop.node.label }}</span>
                            <q-chip
                                v-if="prop.node.duplicate"
                                dense
                                size="sm"
                                color="warning"
                                text-color="dark"
                                class="q-ml-sm"
                            >
                                duplicate
                            </q-chip>
                        </div>
                        <div
                            v-if="prop.node.count !== undefined"
                            class="text-caption dora-text-muted q-ml-sm"
                        >
                            {{ prop.node.count }}
                        </div>
                    </div>
                </template>
            </q-tree>

            <div class="settings-actions">
                <BaseButton variant="ghost" label="Cancel" @click="onClearPick" />
                <BaseButton
                    variant="secondary"
                    :icon="ICONS.done_all"
                    label="Restore all (skip duplicates)"
                    :loading="restoring"
                    :disable="restoring"
                    @click="onRestoreAll"
                />
                <BaseButton
                    variant="primary"
                    :icon="ICONS.check"
                    label="Restore selection"
                    :loading="restoring"
                    :disable="restoring || selectedCount === 0"
                    @click="onRestoreSelection"
                />
            </div>
        </div>
    </SettingsSection>
    <RestoreReportDialog v-model="reportOpen" :report="report" @close="onCloseReport" />
</template>

<script lang="ts" setup>
    /**
     * Restore from an external file: pick → chunked upload → inspect → tree →
     * commit → report. Split out of `AdminDataBackupRestore` (FU-948 (2)).
     */
    import BaseButton from 'src/components/BaseButton.vue';
    import SettingsFileDrop from 'src/components/settings/SettingsFileDrop.vue';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import RestoreReportDialog from 'src/components/settings/backup/RestoreReportDialog.vue';
    import { useChunkedUpload } from 'src/composables/useChunkedUpload';
    import { useConfirm } from 'src/composables/useConfirm';
    import { formatFileSize, formatNumber } from 'src/composables/useMoney';
    import {
        formatBackupTimestamp,
        sectionLabel,
        type RestoreReport,
        type RestoreReportRow,
    } from 'src/helpers/backupSections';
    import DataApiService, { type BackupSection } from 'src/services/api/dataApiService';
    import { isAlreadyNotified, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useAuthStore } from 'src/stores/authStore';
    import { ICONS } from 'src/style/icons';
    import { useQuasar } from 'quasar';
    import { computed, ref } from 'vue';

    const props = defineProps<{ sections: BackupSection[] }>();

    const $q = useQuasar();
    const { confirm } = useConfirm();
    const authStore = useAuthStore();
    const dataApi = new DataApiService();

    const inspecting = ref(false);
    const restoring = ref(false);
    const pickedFile = ref<File | null>(null);
    const uploadId = ref<string | null>(null);
    const preview = ref<InspectResponse | null>(null);
    const tickedKeys = ref<string[]>([]);
    const expandedKeys = ref<string[]>([]);
    // Shared chunked upload (same composable DataImport uses); it owns its
    // own `progress` ref and `inFlight` flag.
    const chunkedUpload = useChunkedUpload();
    const uploadProgressValue = chunkedUpload.progress;

    // 2 GB hard cap on the client. Matches the server's chunked-upload cap.
    const MAX_BACKUP_BYTES = 2 * 1024 * 1024 * 1024;

    const report = ref<RestoreReport | null>(null);
    const reportOpen = ref(false);

    interface InspectSampleRow {
        id: string;
        name: string;
    }
    interface InspectSample {
        rows: InspectSampleRow[];
        truncated: boolean;
    }
    interface InspectResponse {
        schema_version: number;
        exported_at: string | null;
        exported_by: string | null;
        sections: string[];
        entity_counts: Record<string, number>;
        duplicates: Record<string, string[]>;
        samples: Record<string, InspectSample>;
    }

    // Sections the user can pick into in the restore tree — the server's
    // `pickable` flag (the tables with a natural duplicate key). Sub-tables
    // (lines, ingredients, m2m, historic offers) ride along server-side via
    // CHILD_AUTO_INCLUDE, so they are never offered directly.
    const pickableKeys = computed(() =>
        props.sections.filter((s) => s.pickable).map((s) => s.key),
    );

    // Tree node structure tracks two things:
    //  - `composite` (m2m) entries use "<id>|<id>"; everything else uses the
    //    plain UUID. We mirror the server-side composite_key tuple format.
    interface TreeNode {
        key: string;
        label: string;
        section?: string;
        compositeId?: string;
        duplicate?: boolean;
        count?: number;
        children?: TreeNode[];
        tickable?: boolean;
        noTick?: boolean;
        disabled?: boolean;
    }

    const treeNodes = computed<TreeNode[]>(() => {
        if (!preview.value) return [];
        const dupes = preview.value.duplicates;
        const out: TreeNode[] = [];

        for (const section of pickableKeys.value) {
            const sample = preview.value.samples[section];
            const total = preview.value.entity_counts[section] ?? 0;
            if (!sample || total === 0) continue;

            const dupNames = new Set(dupes[section] ?? []);
            const children: TreeNode[] = sample.rows.map((row) => {
                const isDuplicate = dupNames.has(row.name);
                return {
                    key: `${section}:${row.id}`,
                    label: row.name,
                    section,
                    compositeId: row.id,
                    duplicate: isDuplicate,
                    // q-tree honours `noTick` to keep a leaf in the tree but
                    // skip ticking; combined with `disabled` it greys out.
                    noTick: isDuplicate,
                    disabled: isDuplicate,
                };
            });

            // For truncated sections, surface an overflow leaf so the user
            // knows there's more — selection beyond the sample requires
            // "Restore all (skip duplicates)".
            if (sample.truncated) {
                const hidden = total - sample.rows.length;
                children.push({
                    key: `${section}:__truncated__`,
                    label: `… and ${formatNumber(hidden, { digits: 0 })} more not shown`,
                    section,
                    noTick: true,
                    disabled: true,
                });
            }

            out.push({
                key: `section:${section}`,
                label: sectionLabel(props.sections, section),
                count: total,
                children,
            });
        }

        return out;
    });

    const selectableTotal = computed(() => {
        let n = 0;
        for (const root of treeNodes.value) {
            for (const child of root.children ?? []) {
                if (child.disabled) continue;
                if (child.duplicate) continue;
                n += 1;
            }
        }
        return n;
    });

    const duplicateCount = computed(() => {
        if (!preview.value) return 0;
        return Object.values(preview.value.duplicates).reduce((acc, arr) => acc + arr.length, 0);
    });

    // `tick-strategy="leaf"` keeps roots out of `tickedKeys`, so a plain
    // length is what we want here.
    const selectedCount = computed(() => tickedKeys.value.length);

    // ── Restore: pick → chunked upload → inspect → tree → commit ──────
    async function onFilePicked(file: File | null) {
        if (!file) return;
        if (file.size > MAX_BACKUP_BYTES) {
            $q.notify({
                type: 'negative',
                message: `That file is over the ${formatNumber(MAX_BACKUP_BYTES / 1024 / 1024 / 1024, { digits: 0 })} GB limit (${formatFileSize(file.size)}).`,
            });
            pickedFile.value = null;
            return;
        }

        inspecting.value = true;

        try {
            // ── Upload via the shared chunked-upload composable ──────
            const id = await chunkedUpload.upload(file);
            uploadId.value = id;

            // ── Inspect (server stream-parses the staged file) ───────
            preview.value = await dataApi.inspectUploadAsync<InspectResponse>(id);

            // Default expansion: first 3 pickable sections with rows.
            const sectionsWithRows = pickableKeys.value.filter((k) =>
                (preview.value?.entity_counts[k] ?? 0) > 0,
            );
            expandedKeys.value = sectionsWithRows.slice(0, 3).map((k) => `section:${k}`);
            tickedKeys.value = [];
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: "Couldn't read that backup file.",
                    caption: toastCaption(err),
                });
            }
            await onClearPick();
        } finally {
            inspecting.value = false;
        }
    }

    async function onClearPick() {
        // Best-effort abort of the staged upload so we don't leave dead
        // files lying around when the user backs out. TTL would clean
        // them eventually, but proactive is friendlier.
        if (uploadId.value) {
            await chunkedUpload.abort(uploadId.value);
        }
        chunkedUpload.reset();
        pickedFile.value = null;
        uploadId.value = null;
        preview.value = null;
        tickedKeys.value = [];
        expandedKeys.value = [];
    }

    function onSelectAll() {
        const keys: string[] = [];
        for (const root of treeNodes.value) {
            for (const child of root.children ?? []) {
                if (child.disabled || child.duplicate) continue;
                keys.push(child.key);
            }
        }
        tickedKeys.value = keys;
    }

    function onClearSelection() {
        tickedKeys.value = [];
    }

    async function onRestoreSelection() {
        await confirmAndRestore('partial');
    }

    async function onRestoreAll() {
        await confirmAndRestore('all_skip_duplicates');
    }

    async function confirmAndRestore(mode: 'partial' | 'all_skip_duplicates'): Promise<void> {
        const summary = mode === 'partial'
            ? `${selectedCount.value} selected item(s) will be imported. Duplicates will be skipped.`
            : `Everything in the backup will be imported, except rows that already exist locally.`;
        const ok = await confirm({
            title: 'Confirm restore',
            message: `${summary} This can't be undone.`,
            okLabel: 'Restore',
        });
        if (ok) await doRestore(mode);
    }

    async function doRestore(mode: 'partial' | 'all_skip_duplicates') {
        if (!uploadId.value) return;
        restoring.value = true;
        try {
            const selection: Record<string, string[]> = {};
            if (mode === 'partial') {
                for (const key of tickedKeys.value) {
                    const sep = key.indexOf(':');
                    if (sep < 0) continue;
                    const section = key.slice(0, sep);
                    const id = key.slice(sep + 1);
                    if (!selection[section]) selection[section] = [];
                    selection[section].push(id);
                }
            }
            const summary = await dataApi.restoreUploadAsync({
                upload_id: uploadId.value,
                selection,
                mode,
            });
            const totalCreated = Object.values(summary.created).reduce((a, b) => a + b, 0);
            const totalSkipped = Object.values(summary.skipped).reduce((a, b) => a + b, 0);

            // Build the per-section report rows — only show sections that
            // actually saw activity (created or skipped). Sub-tables that
            // were touched by parent auto-include get reported too.
            const rows: RestoreReportRow[] = [];
            for (const section of props.sections) {
                const created = summary.created[section.key] ?? 0;
                const skipped = summary.skipped[section.key] ?? 0;
                if (created === 0 && skipped === 0) continue;
                rows.push({
                    section: section.key,
                    label: section.label,
                    created,
                    skipped,
                });
            }

            report.value = {
                ok: true,
                headline:
                    `Restored ${totalCreated} row(s), skipped ${totalSkipped}` +
                    (summary.warnings.length
                        ? ` (${summary.warnings.length} warning${summary.warnings.length === 1 ? '' : 's'}).`
                        : '.'),
                rows,
                warnings: summary.warnings,
            };
            reportOpen.value = true;
            // The staged file was consumed server-side; forget the id (so the
            // clear below doesn't abort, and 404, a phantom upload) and drop
            // the preview + tree — their Restore buttons would otherwise stay
            // live over an upload that no longer exists.
            uploadId.value = null;
            await onClearPick();
        } catch (err) {
            report.value = {
                ok: false,
                headline: toastCaption(err),
                rows: [],
                warnings: [],
            };
            reportOpen.value = true;
        } finally {
            restoring.value = false;
        }
    }

    // a successful restore can invalidate `authStore.currentUser`
    // (users table restored ⇒ different `is_admin`, or the caller's row is
    // gone entirely). "Reload now" is the operator's recommended path, but
    // if they hit Close instead, at least sync the auth cache so the router
    // guard + admin surfaces stop believing the stale identity. Other
    // stores stay potentially stale — the "Reload now" affordance still
    // exists for that. A 401 from a deleted-user refresh is handled by
    // the axios interceptor (clears currentUser → login redirect).
    async function onCloseReport() {
        reportOpen.value = false;
        if (report.value?.ok) {
            try {
                await authStore.refreshAsync();
            } catch {
                // Swallow — interceptor handles auth-invalidating errors.
            }
        }
    }
</script>

<style scoped lang="scss">
    // ── Restore preview panel ─────────────────────────────────────────
    .restore-preview {
        display: flex;
        flex-direction: column;
        gap: var(--space-3);
        padding: var(--space-4);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        background: var(--surface-component);
    }
    .restore-preview__header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: var(--space-3);
        flex-wrap: wrap;
    }
    .restore-preview__title {
        font-size: 0.9375rem;
        font-weight: 700;
        color: var(--text-primary);
    }
    .restore-preview__sub {
        font-size: 0.8125rem;
        color: var(--text-muted);
    }
    .restore-preview__count {
        font-size: 0.8125rem;
        color: var(--text-secondary);
    }
    .restore-preview__toolbar {
        display: flex;
        align-items: center;
        gap: var(--space-2);
    }
</style>
