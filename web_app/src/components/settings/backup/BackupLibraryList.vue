<template>
    <!-- One row per persisted backup; retention prunes the oldest above the
         cap on every new create. External-file restore is its own section. -->
    <SettingsSection>
        <template #title>Backup library</template>
        <template #description>
            Snapshots stored on the server. Keeps the most recent
            {{ retentionCount }}; older backups drop off on the next create.
        </template>

        <div v-if="loading" class="backup-state">
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
                            v-if="row.status === 'failed'"
                            dense
                            size="sm"
                            class="dora-chip--tint-negative"
                            :icon="ICONS.error"
                        >
                            Damaged
                            <BaseTooltip max-width="300px">
                                This file no longer matches the copy Dora saved, so it can't be downloaded or restored.
                            </BaseTooltip>
                        </q-chip>
                        <q-chip
                            v-if="sensitiveLabel(row)"
                            dense
                            size="sm"
                            color="warning"
                            text-color="dark"
                            :icon="ICONS.warning"
                        >
                            Sensitive
                            <BaseTooltip max-width="300px">
                                This backup contains {{ sensitiveLabel(row) }}.
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
                        @click="emit('download', row)"
                    >
                        <BaseTooltip>Download</BaseTooltip>
                    </BaseButton>
                    <BaseButton
                        aria-label="Restore this backup"
                        variant="icon"
                        :icon="ICONS.cloud_upload"
                        @click="emit('restore', row)"
                    >
                        <BaseTooltip>Restore this backup</BaseTooltip>
                    </BaseButton>
                    <BaseButton
                        aria-label="Delete backup"
                        variant="icon"
                        :icon="ICONS.delete"
                        @click="emit('delete', row)"
                    >
                        <BaseTooltip>Delete</BaseTooltip>
                    </BaseButton>
                </div>
            </div>
        </div>
    </SettingsSection>
</template>

<script lang="ts" setup>
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import { formatFileSize } from 'src/composables/useMoney';
    import { formatBackupTimestamp, sensitiveSectionsLabel } from 'src/helpers/backupSections';
    import type { BackupRow, BackupSection } from 'src/services/api/dataApiService';
    import { ICONS } from 'src/style/icons';

    const props = defineProps<{
        library: BackupRow[];
        loading: boolean;
        retentionCount: number;
        sections: BackupSection[];
    }>();

    const emit = defineEmits<{
        download: [row: BackupRow];
        restore: [row: BackupRow];
        delete: [row: BackupRow];
    }>();

    function sensitiveLabel(row: BackupRow): string {
        return sensitiveSectionsLabel(props.sections, row.sections);
    }
</script>

<style scoped lang="scss">
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
        color: var(--primary-ink);
        margin-bottom: var(--space-1);
    }
    .backup-empty__hint {
        font-size: 0.8125rem;
        color: var(--text-muted);
    }
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
        color: var(--primary-ink);
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
</style>
