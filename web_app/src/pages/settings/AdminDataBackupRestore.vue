<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Backup & restore"
            description="Save your install to a JSON file. Passwords are never included."
            :icon="ICONS.cloud_download"
        >
            <template #actions>
                <BaseButton
                    variant="primary"
                    :icon="ICONS.add"
                    label="New backup"
                    :loading="generating"
                    @click="openCreateDialog"
                />
            </template>
        </SettingsPageHeader>

        <!-- Backup library. One row per persisted backup; retention (default 5)
             prunes the oldest above the cap on every new create. Rows carry
             Download / Restore / Delete actions; external-file restore is the
             section below. -->
        <SettingsSection>
            <template #title>Backup library</template>
            <template #description>
                Snapshots stored on the server. Keeps the most recent
                {{ retentionCount }}; older backups drop off on the next create.
            </template>

            <div v-if="libraryLoading" class="backup-state">
                <q-spinner size="18px" />
                <span>Loading backups…</span>
            </div>
            <div v-else-if="library.length === 0" class="backup-empty">
                <q-icon :name="ICONS.cloud_download" size="34px" class="backup-empty__icon" />
                <div>No backups yet.</div>
                <div class="backup-empty__hint">
                    Click <strong>New backup</strong> to create your first snapshot.
                </div>
            </div>
            <div v-else class="backup-list">
                <div v-for="row in library" :key="row.backup_id" class="backup-row">
                    <q-icon :name="ICONS.cloud_download" size="22px" class="backup-row__icon" />
                    <div class="backup-row__main">
                        <div class="backup-row__title">
                            {{ formatBackupTimestamp(row.created_at) }}
                            <q-chip
                                v-if="rowIncludesSensitive(row)"
                                dense
                                size="sm"
                                color="warning"
                                text-color="dark"
                                :icon="ICONS.warning"
                            >
                                Sensitive
                                <BaseTooltip max-width="300px">
                                    This backup contains {{ sensitiveSectionsLabel(row) }}.
                                </BaseTooltip>
                            </q-chip>
                        </div>
                        <div class="backup-row__meta">
                            {{ formatFileSize(row.size_bytes) }}
                            · {{ row.sections.length }} section{{ row.sections.length === 1 ? '' : 's' }}
                            <span v-if="row.created_by_username">
                                · by {{ row.created_by_username }}
                            </span>
                        </div>
                    </div>
                    <div class="backup-row__actions">
                        <BaseButton
                            aria-label="Download backup"
                            variant="icon"
                            :icon="ICONS.download"
                            @click="onDownloadRow(row)"
                        >
                            <BaseTooltip>Download</BaseTooltip>
                        </BaseButton>
                        <BaseButton
                            aria-label="Restore this backup"
                            variant="icon"
                            :icon="ICONS.cloud_upload"
                            @click="onRestoreRow(row)"
                        >
                            <BaseTooltip>Restore this backup</BaseTooltip>
                        </BaseButton>
                        <BaseButton
                            aria-label="Delete backup"
                            variant="icon"
                            :icon="ICONS.delete"
                            @click="onDeleteRow(row)"
                        >
                            <BaseTooltip>Delete</BaseTooltip>
                        </BaseButton>
                    </div>
                </div>
            </div>
        </SettingsSection>

        <!-- New-backup dialog — section picker with sensitive-data warning. -->
        <BaseDialog v-model="createDialogOpen" card-style="min-width: 480px; max-width: 640px">
            <q-card-section>
                <div class="text-h6">New backup</div>
                <div class="text-caption dora-text-muted q-mt-xs">
                    Pick which sections to include. Passwords are never included.
                </div>
            </q-card-section>
            <q-separator />
            <q-card-section class="q-pb-none">
                <q-banner
                    v-if="createIncludesSensitive"
                    class="dora-bg-warning-soft q-mb-md text-caption"
                    dense
                    rounded
                >
                    <template #avatar>
                        <q-icon :name="ICONS.warning" color="warning" />
                    </template>
                    This backup will include {{ createSensitiveLabel }}.
                </q-banner>
                <q-expansion-item
                    v-for="(group, idx) in backupSectionGroups"
                    :key="group.category"
                    :label="group.category"
                    :caption="`${countSelectedInGroup(group)} of ${group.sections.length} selected`"
                    :default-opened="idx === 0"
                    dense
                    header-class="q-px-none"
                >
                    <div class="row items-center q-gutter-x-sm q-mb-xs">
                        <BaseButton
                            variant="ghost"
                            dense
                            size="sm"
                            label="All"
                            @click="toggleGroup(group, true)"
                        />
                        <BaseButton
                            variant="ghost"
                            dense
                            size="sm"
                            label="None"
                            @click="toggleGroup(group, false)"
                        />
                    </div>
                    <q-checkbox
                        v-for="section in group.sections"
                        :key="section.key"
                        v-model="backupSelected[section.key]"
                        dense
                        :label="section.label"
                        class="block"
                    />
                </q-expansion-item>
            </q-card-section>
            <template #actions>
                <BaseButton variant="ghost" label="Cancel" v-close-popup />
                <BaseButton
                    variant="primary"
                    :icon="ICONS.cloud_download"
                    label="Generate"
                    :loading="generating"
                    :disable="generating || selectedBackupKeys.length === 0"
                    @click="onGenerate"
                />
            </template>
        </BaseDialog>

        <hr class="settings-divider" />

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
                            Exported {{ formatDate(preview.exported_at) }} by
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

        <!-- ── Restore report (shown after a commit) ─────────────────── -->
        <BaseDialog v-model="reportOpen" card-style="min-width: 360px; max-width: 600px">
                <q-card-section class="row items-center q-gutter-md">
                    <q-icon
                        :name="report?.ok ? ICONS.check_circle : ICONS.error"
                        :color="report?.ok ? 'positive' : 'negative'"
                        size="32px"
                    />
                    <div>
                        <div class="text-h6">
                            {{ report?.ok ? 'Restore complete' : 'Restore failed' }}
                        </div>
                        <div class="text-caption dora-text-muted">
                            {{ report?.headline ?? '' }}
                        </div>
                    </div>
                </q-card-section>
                <q-separator />
                <q-card-section v-if="report?.rows.length" class="q-py-none">
                    <q-list dense separator>
                        <q-item v-for="row in report.rows" :key="row.section">
                            <q-item-section>
                                <q-item-label>{{ row.label }}</q-item-label>
                            </q-item-section>
                            <q-item-section side>
                                <q-item-label class="text-caption">
                                    <span class="text-positive">+{{ row.created }}</span>
                                    <span class="dora-text-secondary"> · {{ row.skipped }} skipped</span>
                                </q-item-label>
                            </q-item-section>
                        </q-item>
                    </q-list>
                </q-card-section>
                <q-card-section v-if="report?.warnings.length" class="q-pt-sm">
                    <q-expansion-item
                        :label="`${report.warnings.length} warning(s)`"
                        :icon="ICONS.warning"
                        dense
                    >
                        <q-list dense>
                            <q-item v-for="(w, i) in report.warnings" :key="i">
                                <q-item-section class="text-caption">{{ w }}</q-item-section>
                            </q-item>
                        </q-list>
                    </q-expansion-item>
                </q-card-section>
                <template #actions>
                    <BaseButton variant="ghost" label="Close" @click="onCloseReport" />
                    <BaseButton
                        v-if="report?.ok"
                        :icon="ICONS.refresh"
                        label="Reload now"
                        @click="reloadNow"
                    />
                </template>
        </BaseDialog>

        <hr class="settings-divider" />

        <!-- library retention + storage-path admin settings. Sits
             near the bottom of the page because it's operator-configuration,
             not day-to-day workflow. -->
        <SettingsSection>
            <template #title>Library settings</template>
            <template #description>
                Where backups land on disk, and how many to keep.
            </template>

            <SettingsRow
                label="Retention count"
                help="Oldest above this cap auto-drop on each new backup."
            >
                <q-input
                    v-model.number="retentionInput"
                    type="number"
                    outlined
                    dense
                    min="1"
                    max="100"
                    class="backup-settings-retention"
                />
            </SettingsRow>
            <SettingsRow
                label="Storage path"
                help="Absolute path on the server. Leave blank for DORA_DATA_DIR/backups. Must be writeable."
            >
                <q-input
                    v-model="storagePathInput"
                    outlined
                    dense
                    clearable
                    placeholder="(default: DORA_DATA_DIR/backups)"
                    class="backup-settings-path"
                />
            </SettingsRow>
            <div class="settings-actions">
                <BaseButton
                    variant="ghost"
                    label="Discard"
                    :disable="!librarySettingsDirty"
                    @click="resetLibrarySettings"
                />
                <BaseButton
                    variant="primary"
                    :icon="ICONS.save"
                    label="Save"
                    :loading="savingSettings"
                    :disable="!librarySettingsDirty || savingSettings"
                    @click="onSaveLibrarySettings"
                />
            </div>
        </SettingsSection>

    </div>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import { formatDateTime as formatLocaleDateTime } from 'src/composables/useDateFormat';
    import { formatFileSize, formatNumber } from 'src/composables/useMoney';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import SettingsFileDrop from 'src/components/settings/SettingsFileDrop.vue';
    import { ICONS } from 'src/style/icons';
    import { useQuasar } from 'quasar';
    import { computed, onMounted, ref } from 'vue';
    import { useChunkedUpload } from 'src/composables/useChunkedUpload';
    import DataApiService, { type BackupRow, type BackupSection } from 'src/services/api/dataApiService';
    import { triggerSave } from 'src/services/files/downloadHelpers';
    import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useAuthStore } from 'src/stores/authStore';
    import { useAppSettingsStore } from 'src/stores/appSettingsStore';
    import { useConfirm } from 'src/composables/useConfirm';

    const $q = useQuasar();

    const { confirm } = useConfirm();
    const authStore = useAuthStore();
    const appSettingsStore = useAppSettingsStore();

    // library-facing state. Old download-only path retired;
    // "Create backup" now POSTs the library create endpoint, and the
    // list at the top of the page shows every persisted backup.
    const library = ref<BackupRow[]>([]);
    const libraryLoading = ref(false);
    const generating = ref(false);
    const createDialogOpen = ref(false);

    // Retention + storage path settings (loaded once on mount, saved on
    // "Save"). Split from the runtime state so the "dirty" check is honest
    // even if the user cancels and reopens.
    const retentionCount = ref<number>(5);
    const storagePath = ref<string>('');
    const retentionInput = ref<number>(5);
    const storagePathInput = ref<string>('');
    const savingSettings = ref(false);

    const inspecting = ref(false);
    const restoring = ref(false);

    const pickedFile = ref<File | null>(null);
    const uploadId = ref<string | null>(null);
    const preview = ref<InspectResponse | null>(null);
    const tickedKeys = ref<string[]>([]);
    const expandedKeys = ref<string[]>([]);
    // Upload progress (0..1) used by the file picker overlay.
    // Shared chunked upload — same composable DataImport uses. The
    // composable owns its own `progress` ref and `inFlight` flag.
    const chunkedUpload = useChunkedUpload();
    const uploadProgressValue = chunkedUpload.progress;

    // 2 GB hard cap on the client. Matches the server's chunked-upload cap.
    const MAX_BACKUP_BYTES = 2 * 1024 * 1024 * 1024;

    // ── Restore report state ──────────────────────────────────────────
    interface ReportRow {
        section: string;
        label: string;
        created: number;
        skipped: number;
    }
    interface RestoreReport {
        ok: boolean;
        headline: string;
        rows: ReportRow[];
        warnings: string[];
    }
    const report = ref<RestoreReport | null>(null);
    const reportOpen = ref(false);

    // "last backup" now derives from the library list (`SELECT
    // MAX(created_at)`), not the retired User.last_backup_at column. The
    // header caption at the top of the library card reads the count; a
    // per-row "how long ago" is on each library row.

    // sensitive sections warning. Optional sections carry data
    // Dora doesn't want written to disk casually. Chips + banner surface
    // this so the choice is visible; not blocked (admins may legitimately
    // need a full-fidelity dump for a migration). Which sections count as
    // sensitive is the server's `Section.sensitive` flag — read off the
    // catalogue below, not listed here.
    const sensitiveKeys = computed(() =>
        new Set(backupSections.value.filter((s) => s.sensitive).map((s) => s.key)),
    );
    function sensitiveKeysIn(sections: string[]): string[] {
        return sections.filter((k) => sensitiveKeys.value.has(k));
    }
    function sensitiveLabel(keys: string[]): string {
        return keys.map((k) => sectionLabel(k).toLowerCase()).join(', ');
    }
    function rowIncludesSensitive(row: BackupRow): boolean {
        return sensitiveKeysIn(row.sections).length > 0;
    }
    function sensitiveSectionsLabel(row: BackupRow): string {
        return sensitiveLabel(sensitiveKeysIn(row.sections));
    }
    const createIncludesSensitive = computed(() =>
        sensitiveKeysIn(selectedBackupKeys.value).length > 0,
    );
    const createSensitiveLabel = computed(() =>
        sensitiveLabel(sensitiveKeysIn(selectedBackupKeys.value)),
    );

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

    // The section catalogue — `restore_shared.SECTIONS`, served by
    // `GET /api/data/backup/sections`. It drives the checkbox order and
    // defaults in the Create-backup dialog, the restore tree's pickable
    // sections and labels, the sensitive-data warnings and the restore
    // report. This page used to carry its own copy of the list and the two
    // drifted: the copy named `product_barcodes` (server key `barcodes`), so
    // every default *New backup* was refused, and it lacked the nine recipe
    // vocabulary / step / link sections, so a backup made here silently
    // omitted recipe steps (finalisation 18-R2 / 18-R3). One source now.
    const dataApi = new DataApiService();
    const backupSections = ref<BackupSection[]>([]);
    const backupSelected = ref<Record<string, boolean>>({});

    async function loadSections(): Promise<void> {
        try {
            backupSections.value = await dataApi.backupSectionsAsync();
            backupSelected.value = Object.fromEntries(
                backupSections.value.map((s) => [s.key, s.default_on]),
            );
        } catch (e) {
            $q.notify({
                type: 'negative',
                message: "Couldn't load the backup sections.",
                caption: toastCaption(e),
            });
        }
    }

    function sectionLabel(key: string): string {
        return backupSections.value.find((s) => s.key === key)?.label ?? key;
    }

    interface BackupSectionGroup {
        category: string;
        sections: BackupSection[];
    }
    const backupSectionGroups = computed<BackupSectionGroup[]>(() => {
        const byCategory = new Map<string, BackupSection[]>();
        for (const s of backupSections.value) {
            const bucket = byCategory.get(s.category) ?? [];
            bucket.push(s);
            byCategory.set(s.category, bucket);
        }
        return Array.from(byCategory.entries()).map(([category, sections]) => ({
            category,
            sections,
        }));
    });

    function countSelectedInGroup(group: BackupSectionGroup): number {
        return group.sections.filter((s) => backupSelected.value[s.key]).length;
    }

    function toggleGroup(group: BackupSectionGroup, on: boolean) {
        for (const s of group.sections) {
            backupSelected.value[s.key] = on;
        }
    }

    const selectedBackupKeys = computed(() =>
        backupSections.value.filter((s) => backupSelected.value[s.key]).map((s) => s.key),
    );

    // Sections the user can pick into in the restore tree — the server's
    // `pickable` flag (the tables with a natural duplicate key). Sub-tables
    // (lines, ingredients, m2m, historic offers) ride along server-side via
    // CHILD_AUTO_INCLUDE, so they are never offered directly.
    const pickableKeys = computed(() =>
        backupSections.value.filter((s) => s.pickable).map((s) => s.key),
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
                label: sectionLabel(section),
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

    function formatDate(iso: string | null): string {
        if (!iso) return 'an unknown time';
        try {
            return formatLocaleDateTime(iso) || iso;
        } catch {
            return iso;
        }
    }

    // ── Library: load / create / download / restore / delete ──────────
    async function loadLibrary(): Promise<void> {
        libraryLoading.value = true;
        try {
            library.value = await dataApi.listBackupsAsync();
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: "Couldn't load backups.",
                caption: toastCaption(err),
            });
        } finally {
            libraryLoading.value = false;
        }
    }

    function openCreateDialog() {
        createDialogOpen.value = true;
    }

    async function onGenerate() {
        generating.value = true;
        try {
            await dataApi.createBackupAsync(selectedBackupKeys.value);
            $q.notify({
                type: 'positive',
                message: 'Backup saved to the library.',
                timeout: 3000,
            });
            createDialogOpen.value = false;
            await loadLibrary();
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: "Couldn't create backup.",
                caption: toastCaption(err),
            });
        } finally {
            generating.value = false;
        }
    }

    async function onDownloadRow(row: BackupRow) {
        try {
            const { blob, filename } = await dataApi.downloadBackupAsync(row.backup_id);
            triggerSave(blob, filename ?? `dora-backup-${row.created_at.slice(0, 10)}.json`);
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: "Couldn't download backup.",
                caption: toastCaption(err),
            });
        }
    }

    async function onRestoreRow(row: BackupRow) {
        // Confirm — restore inserts arbitrary rows across every table; the
        // library fast-path skips inspect/preview, so a two-step confirm is
        // the correct friction.
        const ok = await confirm({
            title: 'Restore this backup?',
            message: `This will import every section in the ${formatBackupTimestamp(row.created_at)} backup, skipping any rows that already exist. Users, settings, or historic offers included in the file will be applied if you saved them.`,
            okLabel: 'Restore',
            persistent: true,
        });
        if (!ok) return;
        try {
            const summary = await dataApi.restoreBackupAsync(row.backup_id);
            $q.notify({
                type: 'positive',
                message: 'Restore complete.',
                caption: summarizeRestore(summary),
                timeout: 4000,
            });
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: "Restore failed.",
                caption: toastCaption(err),
            });
        }
    }

    async function onDeleteRow(row: BackupRow) {
        const ok = await confirm({
            title: 'Delete this backup?',
            message: `The ${formatBackupTimestamp(row.created_at)} backup will be removed from the library and the file will be deleted from disk. This can't be undone.`,
            okLabel: 'Delete',
            destructive: true,
            persistent: true,
        });
        if (!ok) return;
        try {
            await dataApi.deleteBackupAsync(row.backup_id);
            library.value = library.value.filter((r) => r.backup_id !== row.backup_id);
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: "Couldn't delete backup.",
                caption: toastCaption(err),
            });
        }
    }

    // Library / row formatting helpers.
    function formatBackupTimestamp(iso: string | null): string {
        if (!iso) return 'unknown';
        try {
            return formatLocaleDateTime(iso) || iso;
        } catch {
            return iso;
        }
    }
    function summarizeRestore(body: unknown): string {
        const created = (body as { created?: Record<string, unknown> } | null)?.created ?? {};
        const total = Object.values(created).reduce((a: number, b: unknown) => a + Number(b || 0), 0);
        return total === 0
            ? 'No new rows. Everything was a duplicate.'
            : `${total} row${total === 1 ? '' : 's'} imported.`;
    }

    // ── Library settings (retention + storage path) ───────────────────
    const librarySettingsDirty = computed(() =>
        retentionInput.value !== retentionCount.value
        || storagePathInput.value !== storagePath.value,
    );

    async function loadLibrarySettings(): Promise<void> {
        try {
            const settings = await appSettingsStore.loadAsync();
            retentionCount.value = settings.backup_retention_count;
            storagePath.value = settings.backup_storage_path;
            retentionInput.value = retentionCount.value;
            storagePathInput.value = storagePath.value;
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: "Couldn't load library settings.",
                caption: toastCaption(err),
            });
        }
    }

    function resetLibrarySettings() {
        retentionInput.value = retentionCount.value;
        storagePathInput.value = storagePath.value;
    }
    async function onSaveLibrarySettings() {
        savingSettings.value = true;
        try {
            const saved = await appSettingsStore.saveAsync({
                backup_retention_count: Number(retentionInput.value),
                backup_storage_path: (storagePathInput.value ?? '').trim(),
            });
            retentionCount.value = saved.backup_retention_count;
            storagePath.value = saved.backup_storage_path;
            resetLibrarySettings();
            $q.notify({
                type: 'positive',
                message: 'Library settings saved.',
                timeout: 2500,
            });
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: "Couldn't save library settings.",
                caption: toastCaption(err),
            });
        } finally {
            savingSettings.value = false;
        }
    }

    onMounted(async () => {
        await Promise.all([loadSections(), loadLibrary(), loadLibrarySettings()]);
    });


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
            $q.notify({
                type: 'negative',
                message: "Couldn't read that backup file.",
                caption: toastCaption(err),
            });
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
            const rows: ReportRow[] = [];
            for (const section of backupSections.value) {
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

    function reloadNow() {
        // Hard reload — cheapest way to make sure every store reflects the
        // new data with zero risk of stale in-memory state.
        window.location.reload();
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
    .backup-settings-retention {
        max-width: 120px;
    }

    .backup-settings-path {
        min-width: 280px;
    }


    // ── Backup library states ─────────────────────────────────────────
    .backup-state {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        color: var(--text-secondary);
        font-size: 0.875rem;
    }
    .backup-empty {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--space-1);
        padding: var(--space-6) var(--space-4);
        border: 1.5px dashed var(--border-strong);
        border-radius: var(--radius-lg);
        background: var(--surface-elevated);
        color: var(--text-secondary);
        text-align: center;
    }
    .backup-empty__icon {
        color: var(--brand-primary);
        margin-bottom: var(--space-1);
    }
    .backup-empty__hint {
        font-size: 0.8125rem;
        color: var(--text-muted);
    }

    // ── Backup library rows ───────────────────────────────────────────
    .backup-list {
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
    }
    .backup-row {
        display: flex;
        align-items: center;
        gap: var(--space-3);
        padding: var(--space-3) var(--space-4);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        background: var(--surface-component);
        transition: border-color 160ms ease, background 160ms ease;
    }
    .backup-row:hover {
        border-color: var(--brand-primary);
        background: color-mix(in srgb, var(--brand-primary) 4%, var(--surface-component));
    }
    .backup-row__icon {
        color: var(--brand-primary);
        flex: 0 0 auto;
    }
    .backup-row__main {
        flex: 1 1 auto;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .backup-row__title {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        font-size: 0.9375rem;
        font-weight: 600;
        color: var(--text-primary);
    }
    .backup-row__meta {
        font-size: 0.8125rem;
        color: var(--text-muted);
    }
    .backup-row__actions {
        flex: 0 0 auto;
        display: flex;
        align-items: center;
        gap: var(--space-1);
    }

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
