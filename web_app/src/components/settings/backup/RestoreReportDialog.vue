<template>
    <!-- Shown after a restore commits (or fails). -->
    <BaseDialog v-model="open" card-style="min-width: 360px; max-width: 600px">
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
            <BaseButton variant="ghost" label="Close" @click="emit('close')" />
            <BaseButton
                v-if="report?.ok"
                :icon="ICONS.refresh"
                label="Reload now"
                @click="reloadNow"
            />
        </template>
    </BaseDialog>
</template>

<script lang="ts" setup>
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import type { RestoreReport } from 'src/helpers/backupSections';
    import { ICONS } from 'src/style/icons';

    const open = defineModel<boolean>({ required: true });
    defineProps<{ report: RestoreReport | null }>();
    const emit = defineEmits<{ close: [] }>();

    function reloadNow() {
        // Hard reload — cheapest way to make sure every store reflects the
        // new data with zero risk of stale in-memory state.
        window.location.reload();
    }
</script>
