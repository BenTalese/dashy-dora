<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Backup & restore"
            help="Back up your install"
            description="Save your install to a JSON file. Passwords are never included."
        >
            <template #actions>
                <BaseButton
                    variant="primary"
                    :icon="ICONS.add"
                    label="New backup"
                    :loading="generating"
                    @click="createDialogOpen = true"
                />
            </template>
        </SettingsPageHeader>

        <BackupLibraryList
            :library="library"
            :loading="libraryLoading"
            :retention-count="retentionCount"
            :sections="backupSections"
            @download="onDownloadRow"
            @restore="onRestoreRow"
            @delete="onDeleteRow"
        />

        <BackupCreateDialog
            v-model="createDialogOpen"
            :sections="backupSections"
            :generating="generating"
            @generate="onGenerate"
        />

        <hr class="settings-divider" />

        <BackupRestorePanel :sections="backupSections" />

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
    /**
     * Backup & restore. The page owns the service calls for the library and
     * its settings; the library list, the create dialog and the file-restore
     * flow are their own components (FU-948 (2)).
     */
    import BaseButton from 'src/components/BaseButton.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import BackupCreateDialog from 'src/components/settings/backup/BackupCreateDialog.vue';
    import BackupLibraryList from 'src/components/settings/backup/BackupLibraryList.vue';
    import BackupRestorePanel from 'src/components/settings/backup/BackupRestorePanel.vue';
    import { useConfirm } from 'src/composables/useConfirm';
    import { formatBackupTimestamp } from 'src/helpers/backupSections';
    import DataApiService, { type BackupRow, type BackupSection } from 'src/services/api/dataApiService';
    import { triggerSave } from 'src/services/files/downloadHelpers';
    import { isAlreadyNotified, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useAppSettingsStore } from 'src/stores/appSettingsStore';
    import { ICONS } from 'src/style/icons';
    import { useQuasar } from 'quasar';
    import { computed, onMounted, ref } from 'vue';

    const $q = useQuasar();
    const { confirm } = useConfirm();
    const appSettingsStore = useAppSettingsStore();
    const dataApi = new DataApiService();

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

    // The section catalogue — `restore_shared.SECTIONS`, served by
    // `GET /api/data/backup/sections` — drives the create dialog, the restore
    // tree, the sensitive warnings and the restore report. One source
    // (finalisation 18-R2 / 18-R3).
    const backupSections = ref<BackupSection[]>([]);

    async function loadSections(): Promise<void> {
        try {
            backupSections.value = await dataApi.backupSectionsAsync();
        } catch (e) {
            if (!isAlreadyNotified(e)) {
                $q.notify({
                    type: 'negative',
                    message: "Couldn't load the backup sections.",
                    caption: toastCaption(e),
                });
            }
        }
    }

    // ── Library: load / create / download / restore / delete ──────────
    async function loadLibrary(): Promise<void> {
        libraryLoading.value = true;
        try {
            library.value = await dataApi.listBackupsAsync();
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: "Couldn't load backups.",
                    caption: toastCaption(err),
                });
            }
        } finally {
            libraryLoading.value = false;
        }
    }

    async function onGenerate(keys: string[]) {
        generating.value = true;
        try {
            await dataApi.createBackupAsync(keys);
            $q.notify({
                type: 'positive',
                message: 'Backup saved to the library.',
                timeout: 3000,
            });
            createDialogOpen.value = false;
            await loadLibrary();
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: "Couldn't create backup.",
                    caption: toastCaption(err),
                });
            }
        } finally {
            generating.value = false;
        }
    }

    async function onDownloadRow(row: BackupRow) {
        try {
            const { blob, filename } = await dataApi.downloadBackupAsync(row.backup_id);
            triggerSave(blob, filename ?? `dora-backup-${row.created_at.slice(0, 10)}.json`);
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: "Couldn't download backup.",
                    caption: toastCaption(err),
                });
            }
            await loadLibrary();
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
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: "Restore failed.",
                    caption: toastCaption(err),
                });
            }
            await loadLibrary();
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
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: "Couldn't delete backup.",
                    caption: toastCaption(err),
                });
            }
        }
    }

    // Library / row formatting helpers.
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
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: "Couldn't load library settings.",
                    caption: toastCaption(err),
                });
            }
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
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: "Couldn't save library settings.",
                    caption: toastCaption(err),
                });
            }
        } finally {
            savingSettings.value = false;
        }
    }

    onMounted(async () => {
        await Promise.all([loadSections(), loadLibrary(), loadLibrarySettings()]);
    });


</script>

<style scoped lang="scss">
    .backup-settings-retention {
        max-width: 120px;
    }

    .backup-settings-path {
        min-width: 280px;
    }
</style>
